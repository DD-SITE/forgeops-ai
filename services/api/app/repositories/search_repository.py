from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_version import (
    DocumentVersion,
    DocumentVersionStatus,
)


class SearchRepository:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.session = session

    async def semantic_search(
        self,
        *,
        workspace_id: UUID,
        query_embedding: list[float],
        top_k: int,
    ) -> list[dict]:
        distance = (
            DocumentChunk.embedding.cosine_distance(
                query_embedding
            )
        )

        similarity = 1 - distance

        statement = (
            select(
                DocumentChunk.id.label(
                    "chunk_id"
                ),
                Document.id.label(
                    "document_id"
                ),
                Document.name.label(
                    "document_name"
                ),
                DocumentChunk.content,
                DocumentChunk.page_start,
                DocumentChunk.page_end,
                DocumentChunk.section_path,
                similarity.label(
                    "similarity"
                ),
            )
            .join(
                DocumentVersion,
                DocumentVersion.id
                == DocumentChunk.document_version_id,
            )
            .join(
                Document,
                Document.id
                == DocumentVersion.document_id,
            )
            .where(
                Document.workspace_id
                == workspace_id,
                DocumentVersion.status
                == DocumentVersionStatus.READY,
            )
            .order_by(distance)
            .limit(top_k)
        )

        result = await self.session.execute(
            statement
        )

        return [
            {
                "chunk_id": row.chunk_id,
                "document_id": row.document_id,
                "document_name": row.document_name,
                "content": row.content,
                "similarity": float(
                    row.similarity
                ),
                "page_start": row.page_start,
                "page_end": row.page_end,
                "section_path": (
                    list(row.section_path)
                    if row.section_path
                    else None
                ),
            }
            for row in result
        ]