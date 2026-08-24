from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gemini import GeminiService
from app.core.config import settings
from app.ingestion.embeddings import EmbeddingService
from app.repositories.search_repository import SearchRepository


class AskService:
    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService,
        gemini_service: GeminiService,
    ) -> None:
        self.repository = SearchRepository(session)
        self.embedding_service = embedding_service
        self.gemini_service = gemini_service

    async def ask(
        self,
        *,
        workspace_id: UUID,
        query: str,
        top_k: int,
        min_similarity: float,
    ) -> dict:
        normalized_query = query.strip()

        if not normalized_query:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question cannot be empty",
            )

        query_embedding = (
            self.embedding_service.embed_query(
                normalized_query
            )
        )

        if len(query_embedding) != settings.embedding_dimension:
            raise RuntimeError(
                "Query embedding dimension does not "
                "match the configured vector dimension."
            )

        results = await self.repository.semantic_search(
            workspace_id=workspace_id,
            query_embedding=query_embedding,
            top_k=top_k,
        )

        results = [
            result
            for result in results
            if result["similarity"] >= min_similarity
        ]

        if not results:
            return {
                "query": normalized_query,
                "answer": (
                    "The available documents do not contain "
                    "enough information to answer this question."
                ),
                "sources": [],
            }

        context_parts = []

        for index, result in enumerate(results, start=1):
            source = result["document_name"]

            section = result.get("section_path")
            if section:
                source += f" — {' > '.join(section)}"

            context_parts.append(
                f"""SOURCE {index}
Document: {source}
Content:
{result["content"]}
"""
            )

        context = "\n".join(context_parts)

        answer = await self.gemini_service.generate_answer(
            query=normalized_query,
            context=context,
        )

        return {
            "query": normalized_query,
            "answer": answer,
            "sources": results,
        }