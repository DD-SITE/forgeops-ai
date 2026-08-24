import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from botocore.exceptions import ClientError
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import (
    Document,
    DocumentStatus,
)
from app.models.document_version import (
    DocumentVersion,
    DocumentVersionStatus,
)
from app.models.ingestion_job import (
    IngestionJob,
    IngestionJobStatus,
)
from app.queue.ingestion import IngestionQueue
from app.repositories.document_repository import (
    DocumentRepository,
)
from app.storage.s3 import S3Storage


ALLOWED_FILE_TYPES = {
    ".pdf": "application/pdf",
    ".docx": (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    ),
    ".md": "text/markdown",
    ".txt": "text/plain",
}


def _safe_filename(filename: str) -> str:
    filename = Path(filename).name

    sanitized = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        filename,
    )

    sanitized = sanitized.strip("._")

    return sanitized or "document"


class DocumentService:
    def __init__(
        self,
        session: AsyncSession,
        storage: S3Storage,
    ) -> None:
        self.session = session
        self.storage = storage
        self.repository = DocumentRepository(session)

    def _validate_upload(
        self,
        *,
        filename: str,
        content_type: str,
        size_bytes: int,
    ) -> str:
        if size_bytes > settings.max_upload_size_bytes:
            raise HTTPException(
                status_code=(
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
                ),
                detail=(
                    "File exceeds the 25 MB "
                    "development upload limit."
                ),
            )

        safe_name = _safe_filename(filename)

        suffix = Path(safe_name).suffix.lower()

        expected_type = ALLOWED_FILE_TYPES.get(suffix)

        if expected_type is None:
            raise HTTPException(
                status_code=(
                    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
                ),
                detail=(
                    "Unsupported document type. "
                    "Supported formats: PDF, DOCX, "
                    "Markdown, TXT."
                ),
            )

        if content_type not in {
            expected_type,
            "application/octet-stream",
        }:
            raise HTTPException(
                status_code=(
                    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
                ),
                detail=(
                    f"Content type does not match "
                    f"the .{suffix.lstrip('.')} "
                    "file extension."
                ),
            )

        return safe_name

    async def create_upload_intent(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        filename: str,
        content_type: str,
        size_bytes: int,
    ):
        safe_name = self._validate_upload(
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
        )

        suffix = Path(safe_name).suffix.lower()

        canonical_content_type = ALLOWED_FILE_TYPES[suffix]

        document_id = uuid4()
        version_id = uuid4()

        object_key = (
            f"workspaces/{workspace_id}/"
            f"documents/{document_id}/"
            f"versions/{version_id}/"
            f"{safe_name}"
        )

        version = DocumentVersion(
            id=version_id,
            version_number=1,
            object_key=object_key,
            original_filename=safe_name,
            content_type=canonical_content_type,
            size_bytes=size_bytes,
            status=DocumentVersionStatus.PENDING_UPLOAD,
        )

        document = Document(
            id=document_id,
            workspace_id=workspace_id,
            created_by=user_id,
            name=safe_name,
            status=DocumentStatus.UPLOADING,
        )

        document.versions.append(version)

        self.session.add(document)

        try:
            await self.session.flush()

            upload_url = (
                self.storage.create_presigned_put_url(
                    object_key=object_key,
                    content_type=canonical_content_type,
                )
            )

            await self.session.commit()

        except Exception:
            await self.session.rollback()
            raise

        return {
            "document_id": document.id,
            "version_id": version.id,
            "object_key": object_key,
            "upload_url": upload_url,
            "upload_headers": {
                "Content-Type": canonical_content_type,
            },
            "expires_in_seconds": (
                settings.s3_presigned_url_expire_seconds
            ),
        }

    async def complete_upload(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        version_id: UUID,
    ):
        version = await self.repository.get_version(
            workspace_id=workspace_id,
            document_id=document_id,
            version_id=version_id,
        )

        if version is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document version not found",
            )

        document = await self.repository.get_by_id(
            workspace_id=workspace_id,
            document_id=document_id,
        )

        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )

        if version.status == DocumentVersionStatus.READY:
            return document, version

        try:
            metadata = self.storage.head_object(
                object_key=version.object_key,
            )

        except ClientError as exc:
            error_code = (
                exc.response.get(
                    "Error",
                    {},
                ).get("Code")
            )

            if error_code in {
                "404",
                "NoSuchKey",
                "NotFound",
            }:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Upload has not been completed",
                ) from exc

            raise

        actual_size = int(
            metadata.get(
                "ContentLength",
                0,
            )
        )

        actual_content_type = metadata.get(
            "ContentType",
            "",
        )

        if actual_size != version.size_bytes:
            version.status = DocumentVersionStatus.FAILED
            document.status = DocumentStatus.FAILED

            await self.session.commit()

            self.storage.delete_object(
                object_key=version.object_key,
            )

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Uploaded file size does not "
                    "match the upload intent"
                ),
            )

        if actual_content_type != version.content_type:
            version.status = DocumentVersionStatus.FAILED
            document.status = DocumentStatus.FAILED

            await self.session.commit()

            self.storage.delete_object(
                object_key=version.object_key,
            )

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Uploaded Content-Type does "
                    "not match the upload intent"
                ),
            )

        version.size_bytes = actual_size
        version.status = DocumentVersionStatus.UPLOADED
        version.uploaded_at = datetime.now(timezone.utc)

        document.status = DocumentStatus.UPLOADED

        existing_job_result = await self.session.execute(
            select(IngestionJob).where(
                IngestionJob.document_version_id
                == version.id
            )
        )

        job = existing_job_result.scalar_one_or_none()

        if job is None:
            job = IngestionJob(
                document_version_id=version.id,
                status=IngestionJobStatus.PENDING,
                attempt_count=0,
                max_attempts=settings.worker_max_attempts,
            )

            self.session.add(job)

        await self.session.commit()

        await self.session.refresh(document)
        await self.session.refresh(version)
        await self.session.refresh(job)

        try:
            queue = IngestionQueue()

            try:
                await queue.enqueue(job.id)
            finally:
                await queue.close()

        except Exception:
            # PostgreSQL remains the source of truth.
            # The worker recovery loop can dispatch
            # pending jobs later.
            pass

        return document, version

    async def list_documents(
        self,
        *,
        workspace_id: UUID,
    ) -> list[Document]:
        """
        Return all documents belonging to a workspace.

        The repository eagerly loads document versions,
        so the API route can safely access document.versions
        without triggering async lazy-loading.
        """
        return await self.repository.list_for_workspace(
            workspace_id=workspace_id,
        )