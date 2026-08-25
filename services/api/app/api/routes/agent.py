from __future__ import annotations

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.current_user import CurrentUser
from app.auth.rbac import WorkspaceMemberPermission
from app.db.session import get_db_session
from app.models.agent_run import AgentRun
from app.schemas.agent import (
    AgentActionResponse,
    AgentApprovalRequest,
    AgentRunRequest,
    AgentRunResponse,
)
from app.agent.service import AgentService


router = APIRouter(
    prefix="/workspaces/{workspace_id}/agent",
    tags=["agent"],
)


async def _get_run(
    session: AsyncSession,
    workspace_id: UUID,
    run_id: UUID,
) -> AgentRun:
    result = await session.execute(
        select(AgentRun).where(
            AgentRun.id == run_id,
            AgentRun.workspace_id == workspace_id,
        )
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return run


def _response(run: AgentRun) -> AgentRunResponse:
    return AgentRunResponse(
        id=run.id,
        thread_id=run.thread_id,
        query=run.query,
        status=run.status.value,
        answer=run.answer,
        error=run.error,
        created_at=run.created_at,
        updated_at=run.updated_at,
        completed_at=run.completed_at,
        actions=[
            AgentActionResponse(
                id=action.id,
                action_type=action.action_type,
                status=action.status.value,
                payload=action.payload,
                result=action.result,
                created_at=action.created_at,
                executed_at=action.executed_at,
            )
            for action in run.actions
        ],
    )


@router.post("/runs", response_model=AgentRunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(
    workspace_id: UUID,
    payload: AgentRunRequest,
    _: WorkspaceMemberPermission,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentRunResponse:
    service = AgentService(session)
    run = await service.create_run(
        workspace_id=workspace_id,
        user_id=current_user.id,
        query=payload.query,
    )

    async for _event in service.stream_run(run):
        pass

    await session.refresh(run)
    return _response(run)


@router.post("/runs/stream")
async def create_streaming_run(
    workspace_id: UUID,
    payload: AgentRunRequest,
    _: WorkspaceMemberPermission,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    service = AgentService(session)
    run = await service.create_run(
        workspace_id=workspace_id,
        user_id=current_user.id,
        query=payload.query,
    )

    async def event_stream():
        yield f"event: run\ndata: {json.dumps({'run_id': str(run.id)})}\n\n"
        try:
            async for event in service.stream_run(run):
                yield f"event: update\ndata: {json.dumps(event, default=str)}\n\n"
            await session.refresh(run)
            yield f"event: complete\ndata: {json.dumps(_response(run).model_dump(mode='json'))}\n\n"
        except Exception as exc:
            yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/runs/{run_id}", response_model=AgentRunResponse)
async def get_run(
    workspace_id: UUID,
    run_id: UUID,
    _: WorkspaceMemberPermission,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentRunResponse:
    return _response(await _get_run(session, workspace_id, run_id))


@router.post("/runs/{run_id}/approval", response_model=AgentRunResponse)
async def approve_run(
    workspace_id: UUID,
    run_id: UUID,
    payload: AgentApprovalRequest,
    _: WorkspaceMemberPermission,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentRunResponse:
    run = await _get_run(session, workspace_id, run_id)
    service = AgentService(session)

    try:
        await service.resume(
            run=run,
            decision=payload.decision,
            payload=payload.payload,
            approver_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    await session.refresh(run)
    return _response(run)
