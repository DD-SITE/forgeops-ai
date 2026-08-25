from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.ingestion.embeddings import EmbeddingService
from app.repositories.search_repository import SearchRepository


class SearchService:
    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService,
    ) -> None:
        self.repository = SearchRepository(session)
        self.embedding_service = embedding_service

    async def search(
        self,
        *,
        workspace_id: UUID,
        query: str,
        top_k: int,
        min_similarity: float,
    ) -> list[dict]:
        normalized_query = query.strip()

        if not normalized_query:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Search query cannot be empty",
            )

        query_embedding = self.embedding_service.embed_query(normalized_query)

        if len(query_embedding) != settings.embedding_dimension:
            raise RuntimeError(
                "Query embedding dimension does not match the configured vector dimension."
            )

        results = await self.repository.hybrid_search(
            workspace_id=workspace_id,
            query_embedding=query_embedding,
            query=normalized_query,
            top_k=top_k,
            candidate_k=max(top_k, settings.agent_max_retrieval_candidates),
        )

        return [
            result
            for result in results
            if result["similarity"] >= min_similarity or result.get("keyword_score", 0.0) > 0
        ]
