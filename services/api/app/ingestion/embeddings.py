from __future__ import annotations

from functools import lru_cache

from fastembed import TextEmbedding

from app.core.config import settings


class EmbeddingService:
    def __init__(self) -> None:
        self.model = TextEmbedding(
            model_name=settings.embedding_model_name,
        )

    def embed_passages(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        vectors = self.model.passage_embed(
            texts,
            batch_size=settings.worker_chunk_batch_size,
        )

        return [
            vector.tolist()
            for vector in vectors
        ]

    def token_counts(
        self,
        texts: list[str],
    ) -> list[int]:
        return [
            self.model.token_count(text)
            for text in texts
        ]

    def embed_query(
        self,
        query: str,
    ) -> list[float]:
        vector = next(
            iter(
                self.model.query_embed(query)
            )
        )

        return vector.tolist()


@lru_cache
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()