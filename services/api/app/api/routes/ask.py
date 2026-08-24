from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gemini import (
    GeminiService,
    get_gemini_service,
)
from app.auth.rbac import WorkspaceMemberPermission
from app.db.session import get_db_session
from app.ingestion.embeddings import (
    EmbeddingService,
    get_embedding_service,
)
from app.schemas.ask import (
    AskRequest,
    AskResponse,
    AskSource,
)
from app.services.ask_service import AskService


router = APIRouter(
    prefix="/workspaces/{workspace_id}/ask",
    tags=["ask"],
)


@router.post(
    "",
    response_model=AskResponse,
)
async def ask(
    workspace_id: UUID,
    payload: AskRequest,
    _: WorkspaceMemberPermission,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
    embedding_service: Annotated[
        EmbeddingService,
        Depends(get_embedding_service),
    ],
    gemini_service: Annotated[
        GeminiService,
        Depends(get_gemini_service),
    ],
) -> AskResponse:
    service = AskService(
        session=session,
        embedding_service=embedding_service,
        gemini_service=gemini_service,
    )

    result = await service.ask(
        workspace_id=workspace_id,
        query=payload.query,
        top_k=payload.top_k,
        min_similarity=payload.min_similarity,
    )

    return AskResponse(
        query=result["query"],
        answer=result["answer"],
        sources=[
            AskSource(**source)
            for source in result["sources"]
        ],
    )