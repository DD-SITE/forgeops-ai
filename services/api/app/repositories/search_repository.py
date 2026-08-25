from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_version import DocumentVersion, DocumentVersionStatus


class SearchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _base_statement(self, workspace_id: UUID):
        return (
            select(
                DocumentChunk.id.label("chunk_id"),
                Document.id.label("document_id"),
                Document.name.label("document_name"),
                DocumentChunk.content,
                DocumentChunk.page_start,
                DocumentChunk.page_end,
                DocumentChunk.section_path,
            )
            .join(
                DocumentVersion, DocumentVersion.id == DocumentChunk.document_version_id
            )
            .join(Document, Document.id == DocumentVersion.document_id)
            .where(
                Document.workspace_id == workspace_id,
                DocumentVersion.status == DocumentVersionStatus.READY,
            )
        )

    async def semantic_search(
        self,
        *,
        workspace_id: UUID,
        query_embedding: list[float],
        top_k: int,
    ) -> list[dict]:
        distance = DocumentChunk.embedding.cosine_distance(query_embedding)
        similarity = 1 - distance

        statement = (
            self._base_statement(workspace_id)
            .add_columns(similarity.label("similarity"))
            .order_by(distance)
            .limit(top_k)
        )
        result = await self.session.execute(statement)
        return [self._row_to_dict(row) for row in result]

    async def keyword_search(
        self,
        *,
        workspace_id: UUID,
        query: str,
        top_k: int,
    ) -> list[dict]:
        ts_query = func.websearch_to_tsquery("english", query)
        rank = func.ts_rank_cd(DocumentChunk.search_vector, ts_query)
        statement = (
            self._base_statement(workspace_id)
            .add_columns(rank.label("keyword_score"))
            .where(DocumentChunk.search_vector.op("@@")(ts_query))
            .order_by(rank.desc())
            .limit(top_k)
        )
        result = await self.session.execute(statement)
        return [self._row_to_keyword_dict(row) for row in result]

    async def hybrid_search(
        self,
        *,
        workspace_id: UUID,
        query_embedding: list[float],
        query: str,
        top_k: int,
        candidate_k: int = 30,
    ) -> list[dict]:
        semantic = await self.semantic_search(
            workspace_id=workspace_id,
            query_embedding=query_embedding,
            top_k=candidate_k,
        )
        keyword = await self.keyword_search(
            workspace_id=workspace_id,
            query=query,
            top_k=candidate_k,
        )

        # Reciprocal-rank fusion makes the two retrieval channels
        # comparable without requiring a second ML reranker.
        merged: dict[UUID, dict] = {}
        k = 60.0

        for rank, item in enumerate(semantic, start=1):
            entry = merged.setdefault(item["chunk_id"], dict(item))
            entry["semantic_rank"] = rank
            entry["rrf_score"] = entry.get("rrf_score", 0.0) + 1.0 / (k + rank)

        for rank, item in enumerate(keyword, start=1):
            entry = merged.setdefault(item["chunk_id"], dict(item))
            entry["keyword_score"] = item.get("keyword_score", 0.0)
            entry["rrf_score"] = entry.get("rrf_score", 0.0) + 1.0 / (k + rank)

        items = list(merged.values())

        # Lightweight deterministic reranker: RRF + semantic similarity
        # + lexical overlap. This is intentionally local and reproducible.
        query_terms = {token.lower() for token in query.split() if len(token) >= 3}

        for item in items:
            content_terms = set(item["content"].lower().split())
            overlap = len(query_terms & content_terms) / max(len(query_terms), 1)
            semantic_score = max(float(item.get("similarity", 0.0)), 0.0)
            item["rerank_score"] = (
                0.55 * item["rrf_score"]
                + 0.30 * semantic_score
                + 0.15 * min(overlap, 1.0)
            )
            item["similarity"] = semantic_score

        items.sort(key=lambda item: item["rerank_score"], reverse=True)
        return items[:top_k]

    @staticmethod
    def _row_to_dict(row) -> dict:
        return {
            "chunk_id": row.chunk_id,
            "document_id": row.document_id,
            "document_name": row.document_name,
            "content": row.content,
            "similarity": float(row.similarity),
            "page_start": row.page_start,
            "page_end": row.page_end,
            "section_path": list(row.section_path) if row.section_path else None,
        }

    @staticmethod
    def _row_to_keyword_dict(row) -> dict:
        return {
            "chunk_id": row.chunk_id,
            "document_id": row.document_id,
            "document_name": row.document_name,
            "content": row.content,
            "similarity": 0.0,
            "keyword_score": float(row.keyword_score),
            "page_start": row.page_start,
            "page_end": row.page_end,
            "section_path": list(row.section_path) if row.section_path else None,
        }
