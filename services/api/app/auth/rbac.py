from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.current_user import CurrentUser
from app.db.session import get_db_session
from app.models.workspace_member import WorkspaceMember, WorkspaceRole


def require_workspace_role(
    *allowed_roles: WorkspaceRole,
) -> Callable:
    async def dependency(
        workspace_id: UUID,
        current_user: CurrentUser,
        session: Annotated[
            AsyncSession,
            Depends(get_db_session),
        ],
    ) -> WorkspaceMember:
        result = await session.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == current_user.id,
            )
        )

        membership = result.scalar_one_or_none()

        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this workspace",
            )

        if (
            allowed_roles
            and membership.role not in allowed_roles
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient workspace permissions",
            )

        return membership

    return dependency


WorkspaceMemberPermission = Annotated[
    WorkspaceMember,
    Depends(
        require_workspace_role(
            WorkspaceRole.OWNER,
            WorkspaceRole.ADMIN,
            WorkspaceRole.MEMBER,
        )
    ),
]


WorkspaceAdminPermission = Annotated[
    WorkspaceMember,
    Depends(
        require_workspace_role(
            WorkspaceRole.OWNER,
            WorkspaceRole.ADMIN,
        )
    ),
]


WorkspaceOwnerPermission = Annotated[
    WorkspaceMember,
    Depends(
        require_workspace_role(
            WorkspaceRole.OWNER,
        )
    ),
]