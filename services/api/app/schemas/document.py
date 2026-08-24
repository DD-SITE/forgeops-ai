from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentUploadIntent(BaseModel):
    filename: str = Field(min_length=1, max_length=512)
    content_type: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(gt=0)


class DocumentUploadIntentResponse(BaseModel):
    document_id: UUID
    version_id: UUID
    object_key: str
    upload_url: str
    upload_headers: dict[str, str]
    expires_in_seconds: int


class DocumentVersionResponse(BaseModel):
    id: UUID
    version_number: int
    original_filename: str
    content_type: str
    size_bytes: int | None
    status: str
    created_at: datetime
    uploaded_at: datetime | None

    model_config = ConfigDict(
        from_attributes=True,
    )


class DocumentResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    created_by: UUID
    name: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


class DocumentUploadCompleteResponse(BaseModel):
    document: DocumentResponse
    version: DocumentVersionResponse


class DocumentListItem(BaseModel):
    id: UUID
    name: str
    status: str
    created_at: datetime
    latest_version: DocumentVersionResponse | None