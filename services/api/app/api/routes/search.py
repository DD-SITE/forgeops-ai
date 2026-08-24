from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import WorkspaceMemberPermission
from app.db.session import get_db_session
from app.ingestion.embeddings import (
    EmbeddingService,
    get_embedding_service,
)
from app.schemas.search import (
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from app.services.search_service import (
    SearchService,
)


router = APIRouter(
    prefix="/workspaces/{workspace_id}/search",
    tags=["search"],
)


@router.post(
    "",
    response_model=SearchResponse,
)
async def semantic_search(
    workspace_id: UUID,
    payload: SearchRequest,
    _: WorkspaceMemberPermission,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
    embedding_service: Annotated[
        EmbeddingService,
        Depends(get_embedding_service),
    ],
) -> SearchResponse:
    service = SearchService(
        session=session,
        embedding_service=embedding_service,
    )

    results = await service.search(
        workspace_id=workspace_id,
        query=payload.query,
        top_k=payload.top_k,
        min_similarity=payload.min_similarity,
    )

    return SearchResponse(
        query=payload.query,
        results=[
            SearchResult(**result)
            for result in results
        ],
    )