from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.current_user import CurrentUser
from app.auth.rbac import (
    WorkspaceAdminPermission,
    WorkspaceMemberPermission,
    WorkspaceOwnerPermission,
)
from app.db.session import get_db_session
from app.models.workspace_member import (
    WorkspaceMember,
    WorkspaceRole,
)
from app.repositories.workspace_repository import (
    WorkspaceRepository,
)
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceMemberResponse,
    WorkspaceMembershipResponse,
    WorkspaceResponse,
    WorkspaceRoleUpdate,
)
from app.services.workspace_service import WorkspaceService


router = APIRouter(
    prefix="/workspaces",
    tags=["workspaces"],
)


@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workspace(
    payload: WorkspaceCreate,
    current_user: CurrentUser,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
) -> WorkspaceResponse:
    service = WorkspaceService(session)

    return await service.create_workspace(
        user=current_user,
        name=payload.name,
        slug=payload.slug,
    )


@router.get(
    "",
    response_model=list[WorkspaceResponse],
)
async def list_workspaces(
    current_user: CurrentUser,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
) -> list[WorkspaceResponse]:
    repository = WorkspaceRepository(session)

    return await repository.get_for_user(
        current_user.id,
    )


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
)
async def get_workspace(
    workspace_id: UUID,
    _: WorkspaceMemberPermission,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
) -> WorkspaceResponse:
    service = WorkspaceService(session)

    return await service.get_workspace(
        workspace_id=workspace_id,
    )


@router.get(
    "/{workspace_id}/membership",
    response_model=WorkspaceMembershipResponse,
)
async def get_membership(
    workspace_id: UUID,
    membership: WorkspaceMemberPermission,
) -> WorkspaceMembershipResponse:
    return WorkspaceMembershipResponse(
        workspace_id=workspace_id,
        role=membership.role,
    )


@router.get(
    "/{workspace_id}/members",
    response_model=list[WorkspaceMemberResponse],
)
async def list_members(
    workspace_id: UUID,
    _: WorkspaceMemberPermission,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
) -> list[WorkspaceMemberResponse]:
    service = WorkspaceService(session)

    memberships = await service.list_members(
        workspace_id=workspace_id,
    )

    return [
        WorkspaceMemberResponse(
            user_id=membership.user_id,
            role=membership.role,
            joined_at=membership.joined_at,
        )
        for membership in memberships
    ]


@router.patch(
    "/{workspace_id}/members/{user_id}/role",
    response_model=WorkspaceMemberResponse,
)
async def update_member_role(
    workspace_id: UUID,
    user_id: UUID,
    payload: WorkspaceRoleUpdate,
    actor_membership: WorkspaceAdminPermission,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
) -> WorkspaceMemberResponse:
    repository = WorkspaceRepository(session)

    target_membership = await repository.get_membership(
        workspace_id=workspace_id,
        user_id=user_id,
    )

    if target_membership is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace member not found",
        )

    service = WorkspaceService(session)

    updated_membership = await service.update_member_role(
        actor_membership=actor_membership,
        target_membership=target_membership,
        new_role=payload.role,
    )

    return WorkspaceMemberResponse(
        user_id=updated_membership.user_id,
        role=updated_membership.role,
        joined_at=updated_membership.joined_at,
    )


@router.delete(
    "/{workspace_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    workspace_id: UUID,
    user_id: UUID,
    actor_membership: WorkspaceAdminPermission,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
) -> None:
    repository = WorkspaceRepository(session)

    target_membership = await repository.get_membership(
        workspace_id=workspace_id,
        user_id=user_id,
    )

    if target_membership is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace member not found",
        )

    service = WorkspaceService(session)

    await service.remove_member(
        actor_membership=actor_membership,
        target_membership=target_membership,
    )


@router.post(
    "/{workspace_id}/transfer-ownership/{user_id}",
    response_model=WorkspaceMemberResponse,
)
async def transfer_ownership(
    workspace_id: UUID,
    user_id: UUID,
    actor_membership: WorkspaceOwnerPermission,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
) -> WorkspaceMemberResponse:
    repository = WorkspaceRepository(session)

    target_membership = await repository.get_membership(
        workspace_id=workspace_id,
        user_id=user_id,
    )

    if target_membership is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace member not found",
        )

    if target_membership.user_id == actor_membership.user_id:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already own this workspace",
        )

    previous_owner = actor_membership

    previous_owner.role = WorkspaceRole.ADMIN
    target_membership.role = WorkspaceRole.OWNER

    await session.commit()

    return WorkspaceMemberResponse(
        user_id=target_membership.user_id,
        role=target_membership.role,
        joined_at=target_membership.joined_at,
    )