from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember, WorkspaceRole


class WorkspaceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self,
        workspace_id: UUID,
    ) -> Workspace | None:
        result = await self.session.execute(
            select(Workspace).where(
                Workspace.id == workspace_id,
            )
        )

        return result.scalar_one_or_none()

    async def get_for_user(
        self,
        user_id: UUID,
    ) -> list[Workspace]:
        result = await self.session.execute(
            select(Workspace)
            .join(
                WorkspaceMember,
                WorkspaceMember.workspace_id == Workspace.id,
            )
            .where(
                WorkspaceMember.user_id == user_id,
            )
            .order_by(
                Workspace.created_at.asc(),
            )
        )

        return list(result.scalars().all())

    async def create_for_user(
        self,
        *,
        user: User,
        name: str,
        slug: str,
    ) -> Workspace:
        workspace = Workspace(
            name=name,
            slug=slug,
        )

        membership = WorkspaceMember(
            user=user,
            workspace=workspace,
            role=WorkspaceRole.OWNER,
        )

        self.session.add(membership)

        await self.session.flush()

        return workspace

    async def get_members(
        self,
        workspace_id: UUID,
    ) -> list[WorkspaceMember]:
        result = await self.session.execute(
            select(WorkspaceMember)
            .where(
                WorkspaceMember.workspace_id == workspace_id,
            )
            .order_by(
                WorkspaceMember.joined_at.asc(),
            )
        )

        return list(result.scalars().all())

    async def get_membership(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
    ) -> WorkspaceMember | None:
        result = await self.session.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )

        return result.scalar_one_or_none()

    async def update_member_role(
        self,
        *,
        membership: WorkspaceMember,
        role: WorkspaceRole,
    ) -> WorkspaceMember:
        membership.role = role

        await self.session.flush()

        return membership

    async def delete_membership(
        self,
        membership: WorkspaceMember,
    ) -> None:
        await self.session.delete(membership)

        await self.session.flush()