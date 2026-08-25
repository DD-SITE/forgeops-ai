from uuid import UUID

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(
        min_length=2,
        max_length=2000,
    )

    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
    )

    min_similarity: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )


class SearchResult(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_name: str

    content: str

    similarity: float

    page_start: int | None
    page_end: int | None

    section_path: list[str] | None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
