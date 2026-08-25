from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.ingestion.embeddings import (
    get_embedding_service,
)
from app.ingestion.parsers import DocumentParser
from app.ingestion.pipeline import IngestionPipeline
from app.models.ingestion_job import (
    IngestionJob,
    IngestionJobStatus,
)
from app.queue.ingestion import IngestionQueue
from app.repositories.ingestion_repository import (
    IngestionRepository,
)
from app.storage.s3 import S3Storage

logging.basicConfig(
    level=logging.INFO,
    format=("%(asctime)s | %(levelname)s | %(name)s | %(message)s"),
)

logger = logging.getLogger("forgeops.ingestion-worker")


class IngestionWorker:
    def __init__(self) -> None:
        self.queue = IngestionQueue()
        self.storage = S3Storage()
        self.parser = DocumentParser()

        self.embedding_service = get_embedding_service()

        self.pipeline = IngestionPipeline(
            parser=self.parser,
            embedding_service=self.embedding_service,
        )

        self.running = True

    async def run(self) -> None:
        logger.info("Starting ForgeOps ingestion worker")

        recovery_task = asyncio.create_task(self.recovery_loop())

        try:
            while self.running:
                try:
                    message = await self.queue.dequeue(
                        settings.worker_poll_timeout_seconds,
                    )

                    if message is None:
                        continue

                    message_id, job_id = message

                    try:
                        await self.process_job(job_id)
                    finally:
                        try:
                            await self.queue.ack(message_id)
                        except Exception:
                            logger.exception(
                                "Failed to acknowledge Redis stream message %s",
                                message_id,
                            )

                except asyncio.CancelledError:
                    raise

                except Exception:
                    logger.exception(
                        "Unexpected worker-loop error. Worker will continue running."
                    )

                    await asyncio.sleep(2)

        finally:
            self.running = False

            recovery_task.cancel()

            try:
                await recovery_task
            except asyncio.CancelledError:
                pass

            await self.queue.close()

            logger.info("Ingestion worker stopped")

    async def process_job(
        self,
        job_id: UUID,
    ) -> None:
        async with AsyncSessionLocal() as session:
            repository = IngestionRepository(session)

            job = await repository.claim_job(job_id)

            if job is None:
                return

            version = await repository.get_document_version(
                job.document_version_id,
            )

            if version is None:
                await repository.mark_failed(
                    job,
                    error_message=("Document version not found."),
                    retry=False,
                    next_attempt_at=None,
                )
                return

            await repository.mark_document_processing(version)

            try:
                data = await asyncio.to_thread(
                    self.storage.download_object,
                    object_key=version.object_key,
                )

                chunks = await asyncio.to_thread(
                    self.pipeline.build_chunks,
                    filename=version.original_filename,
                    content_type=version.content_type,
                    data=data,
                    document_version_id=version.id,
                )

                await repository.replace_chunks(
                    document_version=version,
                    chunks=chunks,
                )

                await repository.mark_completed(job)

                logger.info(
                    ("Completed ingestion job %s for version %s: %s chunks"),
                    job.id,
                    version.id,
                    len(chunks),
                )

            except Exception as exc:  # noqa: BLE001
                await self.handle_failure(
                    job,
                    exc,
                )

    async def handle_failure(
        self,
        job: IngestionJob,
        error: Exception,
    ) -> None:
        now = datetime.now(UTC)

        retry = job.attempt_count < job.max_attempts

        next_attempt_at = None

        if retry:
            delay = settings.worker_retry_base_delay_seconds * (
                2
                ** max(
                    job.attempt_count - 1,
                    0,
                )
            )

            next_attempt_at = now + timedelta(seconds=delay)

        message = f"{type(error).__name__}: {error}"

        logger.error(
            "Ingestion job %s failed: %s",
            job.id,
            message,
        )

        async with AsyncSessionLocal() as session:
            repository = IngestionRepository(session)

            fresh_job = await repository.get_job(job.id)

            if fresh_job is None:
                return

            await repository.mark_failed(
                fresh_job,
                error_message=message,
                retry=retry,
                next_attempt_at=next_attempt_at,
            )

    async def recovery_loop(self) -> None:
        while self.running:
            try:
                await self.recover_jobs()

            except asyncio.CancelledError:
                raise

            except Exception:
                logger.exception("Job recovery loop failed")

            await asyncio.sleep(settings.worker_recovery_interval_seconds)

    async def recover_jobs(self) -> None:
        now = datetime.now(UTC)

        stale_time = now - timedelta(seconds=settings.worker_stale_job_seconds)

        async with AsyncSessionLocal() as session:
            stale_processing = await session.execute(
                select(IngestionJob).where(
                    IngestionJob.status == IngestionJobStatus.PROCESSING,
                    IngestionJob.started_at < stale_time,
                )
            )

            for job in stale_processing.scalars().all():
                logger.warning(
                    "Resetting stale job %s",
                    job.id,
                )

                job.status = IngestionJobStatus.PENDING

                job.next_attempt_at = now

                job.last_error = "Worker considered stale and scheduled for recovery."

            stale_queued = await session.execute(
                select(IngestionJob).where(
                    IngestionJob.status == IngestionJobStatus.QUEUED,
                    IngestionJob.queued_at < stale_time,
                )
            )

            for job in stale_queued.scalars().all():
                job.status = IngestionJobStatus.PENDING

                job.next_attempt_at = now

            await session.commit()

        async with AsyncSessionLocal() as session:
            due_jobs = await session.execute(
                select(IngestionJob)
                .where(
                    IngestionJob.status == IngestionJobStatus.PENDING,
                    (IngestionJob.next_attempt_at.is_(None))
                    | (IngestionJob.next_attempt_at <= now),
                )
                .order_by(IngestionJob.created_at.asc())
                .limit(50)
                .with_for_update(skip_locked=True)
            )

            jobs = list(due_jobs.scalars().all())

            for job in jobs:
                job.status = IngestionJobStatus.QUEUED

                job.queued_at = now

            await session.commit()

        for job in jobs:
            try:
                await self.queue.enqueue(job.id)

            except Exception:
                logger.exception(
                    "Failed to enqueue recovered job %s",
                    job.id,
                )

                async with AsyncSessionLocal() as session:
                    repository = IngestionRepository(session)

                    fresh_job = await repository.get_job(
                        job.id,
                        for_update=True,
                    )

                    if fresh_job is not None:
                        fresh_job.status = IngestionJobStatus.PENDING

                        await session.commit()


async def main() -> None:
    worker = IngestionWorker()

    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
