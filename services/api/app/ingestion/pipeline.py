from __future__ import annotations

import hashlib

from app.core.config import settings
from app.ingestion.chunker import chunk_blocks
from app.ingestion.embeddings import (
    EmbeddingService,
)
from app.ingestion.parsers import DocumentParser
from app.models.document_chunk import DocumentChunk


class IngestionPipeline:
    def __init__(
        self,
        *,
        parser: DocumentParser,
        embedding_service: EmbeddingService,
    ) -> None:
        self.parser = parser
        self.embedding_service = (
            embedding_service
        )

    def build_chunks(
        self,
        *,
        filename: str,
        content_type: str,
        data: bytes,
        document_version_id,
    ) -> list[DocumentChunk]:
        blocks = self.parser.parse(
            filename=filename,
            content_type=content_type,
            data=data,
        )

        drafts = chunk_blocks(blocks)

        if not drafts:
            raise ValueError(
                "Document produced no chunks."
            )

        texts = [
            draft.text
            for draft in drafts
        ]

        embeddings = (
            self.embedding_service.embed_passages(
                texts
            )
        )

        token_counts = (
            self.embedding_service.token_counts(
                texts
            )
        )

        if len(embeddings) != len(drafts):
            raise RuntimeError(
                "Embedding count does not match chunk count."
            )

        chunks: list[DocumentChunk] = []

        for index, (
            draft,
            embedding,
            token_count,
        ) in enumerate(
            zip(
                drafts,
                embeddings,
                token_counts,
            )
        ):
            content_hash = hashlib.sha256(
                draft.text.encode("utf-8")
            ).hexdigest()

            chunks.append(
                DocumentChunk(
                    document_version_id=(
                        document_version_id
                    ),
                    chunk_index=index,
                    content=draft.text,
                    content_hash=content_hash,
                    page_start=draft.page_start,
                    page_end=draft.page_end,
                    section_path=(
                        draft.section_path
                        if draft.section_path
                        else None
                    ),
                    token_count=token_count,
                    embedding=embedding,
                )
            )

        if any(
            len(chunk.embedding)
            != settings.embedding_dimension
            for chunk in chunks
        ):
            raise RuntimeError(
                "Embedding dimension does not match "
                "database configuration."
            )

        return chunks