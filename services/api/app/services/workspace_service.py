from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.workspace_member import (
    WorkspaceMember,
    WorkspaceRole,
)
from app.repositories.workspace_repository import (
    WorkspaceRepository,
)


class WorkspaceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = WorkspaceRepository(session)

    async def create_workspace(
        self,
        *,
        user: User,
        name: str,
        slug: str,
    ):
        try:
            workspace = await self.repository.create_for_user(
                user=user,
                name=name,
                slug=slug,
            )

            await self.session.commit()

            await self.session.refresh(workspace)

            return workspace

        except IntegrityError as exc:
            await self.session.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A workspace with this slug already exists",
            ) from exc

    async def list_user_workspaces(
        self,
        *,
        user_id: UUID,
    ):
        return await self.repository.get_for_user(
            user_id,
        )

    async def get_workspace(
        self,
        *,
        workspace_id: UUID,
    ):
        workspace = await self.repository.get_by_id(
            workspace_id,
        )

        if workspace is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )

        return workspace

    async def list_members(
        self,
        *,
        workspace_id: UUID,
    ):
        return await self.repository.get_members(
            workspace_id,
        )

    async def update_member_role(
        self,
        *,
        actor_membership: WorkspaceMember,
        target_membership: WorkspaceMember,
        new_role: WorkspaceRole,
    ):
        actor_role = actor_membership.role
        current_target_role = target_membership.role

        if (
            target_membership.user_id
            == actor_membership.user_id
            and new_role != current_target_role
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot change your own workspace role",
            )

        if (
            actor_role == WorkspaceRole.ADMIN
            and new_role != WorkspaceRole.MEMBER
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admins can only assign the member role",
            )

        if (
            actor_role != WorkspaceRole.OWNER
            and current_target_role == WorkspaceRole.OWNER
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the workspace owner can modify an owner",
            )

        if (
            new_role == WorkspaceRole.OWNER
            and actor_role != WorkspaceRole.OWNER
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the workspace owner can assign ownership",
            )

        await self.repository.update_member_role(
            membership=target_membership,
            role=new_role,
        )

        await self.session.commit()

        return target_membership

    async def remove_member(
        self,
        *,
        actor_membership: WorkspaceMember,
        target_membership: WorkspaceMember,
    ) -> None:
        if (
            actor_membership.user_id
            == target_membership.user_id
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Use workspace deletion or leave the workspace instead",
            )

        if (
            actor_membership.role == WorkspaceRole.ADMIN
            and target_membership.role
            in {
                WorkspaceRole.OWNER,
                WorkspaceRole.ADMIN,
            }
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admins cannot remove owners or other admins",
            )

        if (
            target_membership.role == WorkspaceRole.OWNER
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The workspace owner cannot be removed",
            )

        await self.repository.delete_membership(
            target_membership,
        )

        await self.session.commit()