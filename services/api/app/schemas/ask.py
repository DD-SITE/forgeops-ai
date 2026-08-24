from uuid import UUID

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    query: str = Field(
        min_length=2,
        max_length=2000,
    )

    top_k: int = Field(
        default=5,
        ge=1,
        le=10,
    )

    min_similarity: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
    )


class AskSource(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_name: str
    content: str
    similarity: float
    page_start: int | None
    page_end: int | None
    section_path: list[str] | None


class AskResponse(BaseModel):
    query: str
    answer: str
    sources: list[AskSource]