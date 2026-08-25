from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus
from app.models.document_chunk import DocumentChunk
from app.models.document_version import (
    DocumentVersion,
    DocumentVersionStatus,
)
from app.models.ingestion_job import (
    IngestionJob,
    IngestionJobStatus,
)


class IngestionRepository:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.session = session

    async def get_job(
        self,
        job_id: UUID,
        *,
        for_update: bool = False,
    ) -> IngestionJob | None:
        query = select(IngestionJob).where(
            IngestionJob.id == job_id,
        )

        if for_update:
            query = query.with_for_update()

        result = await self.session.execute(query)

        return result.scalar_one_or_none()

    async def get_job_for_version(
        self,
        document_version_id: UUID,
    ) -> IngestionJob | None:
        result = await self.session.execute(
            select(IngestionJob).where(
                IngestionJob.document_version_id == document_version_id,
            )
        )

        return result.scalar_one_or_none()

    async def create_job(
        self,
        *,
        document_version_id: UUID,
        max_attempts: int,
    ) -> IngestionJob:
        job = IngestionJob(
            document_version_id=document_version_id,
            status=IngestionJobStatus.PENDING,
            attempt_count=0,
            max_attempts=max_attempts,
        )

        self.session.add(job)

        await self.session.flush()

        return job

    async def claim_job(
        self,
        job_id: UUID,
    ) -> IngestionJob | None:
        job = await self.get_job(
            job_id,
            for_update=True,
        )

        if job is None:
            return None

        if job.status in {
            IngestionJobStatus.COMPLETED,
            IngestionJobStatus.FAILED,
        }:
            await self.session.rollback()
            return None

        job.status = IngestionJobStatus.PROCESSING
        job.attempt_count += 1
        job.started_at = datetime.now(UTC)

        await self.session.commit()

        return job

    async def get_document_version(
        self,
        document_version_id: UUID,
    ) -> DocumentVersion | None:
        result = await self.session.execute(
            select(DocumentVersion).where(
                DocumentVersion.id == document_version_id,
            )
        )

        return result.scalar_one_or_none()

    async def mark_document_processing(
        self,
        document_version: DocumentVersion,
    ) -> None:
        result = await self.session.execute(
            select(Document).where(
                Document.id == document_version.document_id,
            )
        )

        document = result.scalar_one_or_none()

        if document is not None:
            document.status = DocumentStatus.PROCESSING

        document_version.status = DocumentVersionStatus.PROCESSING

        await self.session.commit()

    async def replace_chunks(
        self,
        *,
        document_version: DocumentVersion,
        chunks: list[DocumentChunk],
    ) -> None:
        await self.session.execute(
            delete(DocumentChunk).where(
                DocumentChunk.document_version_id == document_version.id,
            )
        )

        self.session.add_all(chunks)

        document_result = await self.session.execute(
            select(Document).where(
                Document.id == document_version.document_id,
            )
        )

        document = document_result.scalar_one()

        document_version.status = DocumentVersionStatus.READY

        document.status = DocumentStatus.READY

        await self.session.commit()

    async def mark_completed(
        self,
        job: IngestionJob,
    ) -> None:
        job.status = IngestionJobStatus.COMPLETED
        job.completed_at = datetime.now(UTC)
        job.last_error = None

        await self.session.commit()

    async def mark_failed(
        self,
        job: IngestionJob,
        *,
        error_message: str,
        retry: bool,
        next_attempt_at: datetime | None,
    ) -> None:
        job.last_error = error_message

        if retry:
            job.status = IngestionJobStatus.PENDING
            job.next_attempt_at = next_attempt_at
        else:
            job.status = IngestionJobStatus.FAILED

            document_version = await self.get_document_version(
                job.document_version_id,
            )

            if document_version is not None:
                document_version.status = DocumentVersionStatus.FAILED

                document_result = await self.session.execute(
                    select(Document).where(
                        Document.id == document_version.document_id,
                    )
                )

                document = document_result.scalar_one_or_none()

                if document is not None:
                    document.status = DocumentStatus.FAILED

        await self.session.commit()
