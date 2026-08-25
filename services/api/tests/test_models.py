from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember, WorkspaceRole


def make_clerk_id() -> str:
    return f"test_clerk_{uuid4().hex}"


@pytest.mark.asyncio
async def test_create_user_workspace_and_membership(
    db_session: AsyncSession,
) -> None:
    user = User(
        clerk_id=make_clerk_id(),
        email=f"pytest-{uuid4().hex[:8]}@forgeops.local",
        full_name="Pytest User",
    )

    workspace = Workspace(
        name="Pytest Workspace",
        slug=f"pytest-workspace-{uuid4().hex[:8]}",
    )

    membership = WorkspaceMember(
        user=user,
        workspace=workspace,
        role=WorkspaceRole.OWNER,
    )

    db_session.add(membership)
    await db_session.commit()

    await db_session.refresh(user)
    await db_session.refresh(workspace)
    await db_session.refresh(membership)

    assert user.id is not None
    assert user.clerk_id is not None
    assert workspace.id is not None
    assert membership.id is not None
    assert membership.role == WorkspaceRole.OWNER

    result = await db_session.execute(select(User).where(User.id == user.id))

    loaded_user = result.scalar_one()

    assert loaded_user.email == user.email
    assert loaded_user.clerk_id == user.clerk_id


@pytest.mark.asyncio
async def test_duplicate_workspace_membership_is_rejected(
    db_session: AsyncSession,
) -> None:
    user = User(
        clerk_id=make_clerk_id(),
        email=f"duplicate-{uuid4().hex[:8]}@forgeops.local",
        full_name="Duplicate Test User",
    )

    workspace = Workspace(
        name="Duplicate Test Workspace",
        slug=f"duplicate-workspace-{uuid4().hex[:8]}",
    )

    first_membership = WorkspaceMember(
        user=user,
        workspace=workspace,
        role=WorkspaceRole.MEMBER,
    )

    db_session.add(first_membership)
    await db_session.commit()

    second_membership = WorkspaceMember(
        user_id=user.id,
        workspace_id=workspace.id,
        role=WorkspaceRole.ADMIN,
    )

    db_session.add(second_membership)

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_duplicate_clerk_id_is_rejected(
    db_session: AsyncSession,
) -> None:
    clerk_id = make_clerk_id()

    first_user = User(
        clerk_id=clerk_id,
        email=f"first-{uuid4().hex[:8]}@forgeops.local",
        full_name="First User",
    )

    second_user = User(
        clerk_id=clerk_id,
        email=f"second-{uuid4().hex[:8]}@forgeops.local",
        full_name="Second User",
    )

    db_session.add(first_user)
    await db_session.commit()

    db_session.add(second_user)

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()
