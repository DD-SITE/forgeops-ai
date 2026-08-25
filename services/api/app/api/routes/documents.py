from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.current_user import CurrentUser
from app.auth.rbac import WorkspaceMemberPermission
from app.core.config import settings
from app.db.session import get_db_session
from app.schemas.document import (
    DocumentListItem,
    DocumentResponse,
    DocumentUploadCompleteResponse,
    DocumentUploadIntent,
    DocumentUploadIntentResponse,
    DocumentVersionResponse,
)
from app.services.document_service import DocumentService
from app.storage.s3 import S3Storage, get_storage

router = APIRouter(
    prefix="/workspaces/{workspace_id}/documents",
    tags=["documents"],
)


def _version_response(version) -> DocumentVersionResponse:
    return DocumentVersionResponse(
        id=version.id,
        version_number=version.version_number,
        original_filename=version.original_filename,
        content_type=version.content_type,
        size_bytes=version.size_bytes,
        status=version.status.value,
        created_at=version.created_at,
        uploaded_at=version.uploaded_at,
    )


@router.post(
    "/upload-intent",
    response_model=DocumentUploadIntentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_upload_intent(
    workspace_id: UUID,
    payload: DocumentUploadIntent,
    _: WorkspaceMemberPermission,
    current_user: CurrentUser,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
    storage: Annotated[
        S3Storage,
        Depends(get_storage),
    ],
) -> DocumentUploadIntentResponse:
    service = DocumentService(
        session=session,
        storage=storage,
    )

    result = await service.create_upload_intent(
        workspace_id=workspace_id,
        user_id=current_user.id,
        filename=payload.filename,
        content_type=payload.content_type,
        size_bytes=payload.size_bytes,
    )

    return DocumentUploadIntentResponse(
        **result,
    )


@router.post(
    "/{document_id}/versions/{version_id}/complete",
    response_model=DocumentUploadCompleteResponse,
)
async def complete_upload(
    workspace_id: UUID,
    document_id: UUID,
    version_id: UUID,
    _: WorkspaceMemberPermission,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
    storage: Annotated[
        S3Storage,
        Depends(get_storage),
    ],
) -> DocumentUploadCompleteResponse:
    service = DocumentService(
        session=session,
        storage=storage,
    )

    document, version = await service.complete_upload(
        workspace_id=workspace_id,
        document_id=document_id,
        version_id=version_id,
    )

    return DocumentUploadCompleteResponse(
        document=DocumentResponse(
            id=document.id,
            workspace_id=document.workspace_id,
            created_by=document.created_by,
            name=document.name,
            status=document.status.value,
            created_at=document.created_at,
            updated_at=document.updated_at,
        ),
        version=_version_response(version),
    )


@router.get(
    "",
    response_model=list[DocumentListItem],
)
async def list_documents(
    workspace_id: UUID,
    _: WorkspaceMemberPermission,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
    storage: Annotated[
        S3Storage,
        Depends(get_storage),
    ],
):
    service = DocumentService(
        session=session,
        storage=storage,
    )

    documents = await service.list_documents(
        workspace_id=workspace_id,
    )

    items: list[DocumentListItem] = []

    for document in documents:
        latest_version = None

        if document.versions:
            latest_version = max(
                document.versions,
                key=lambda version: version.version_number,
            )

        items.append(
            DocumentListItem(
                id=document.id,
                name=document.name,
                status=document.status.value,
                created_at=document.created_at,
                latest_version=(
                    _version_response(latest_version)
                    if latest_version is not None
                    else None
                ),
            )
        )

    return items


@router.get(
    "/{document_id}/download-url",
)
async def get_download_url(
    workspace_id: UUID,
    document_id: UUID,
    _: WorkspaceMemberPermission,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
    storage: Annotated[
        S3Storage,
        Depends(get_storage),
    ],
) -> dict[str, str]:
    service = DocumentService(
        session=session,
        storage=storage,
    )

    url = await service.get_download_url(
        workspace_id=workspace_id,
        document_id=document_id,
    )

    return {
        "url": url,
        "expires_in_seconds": (settings.s3_presigned_url_expire_seconds),
    }
