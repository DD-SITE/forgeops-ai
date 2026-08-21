from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.current_user import get_current_user
from app.db.session import get_db_session
from app.main import app
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import (
    WorkspaceMember,
    WorkspaceRole,
)


async def create_user(
    db_session,
    *,
    email_prefix: str,
) -> User:
    user = User(
        clerk_id=f"test_clerk_{uuid4().hex}",
        email=(
            f"{email_prefix}-{uuid4().hex[:8]}"
            "@forgeops.local"
        ),
        full_name=email_prefix,
    )

    db_session.add(user)

    await db_session.flush()

    return user


async def create_workspace(
    db_session,
    *,
    owner: User,
):
    workspace = Workspace(
        name=f"Workspace {uuid4().hex[:8]}",
        slug=f"workspace-{uuid4().hex[:8]}",
    )

    membership = WorkspaceMember(
        user=owner,
        workspace=workspace,
        role=WorkspaceRole.OWNER,
    )

    db_session.add(membership)

    await db_session.flush()

    return workspace


async def add_member(
    db_session,
    *,
    workspace: Workspace,
    user: User,
    role: WorkspaceRole,
) -> WorkspaceMember:
    membership = WorkspaceMember(
        workspace=workspace,
        user=user,
        role=role,
    )

    db_session.add(membership)

    await db_session.flush()

    return membership


@pytest.fixture
async def client(db_session):
    async def override_db():
        yield db_session

    app.dependency_overrides[get_db_session] = override_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as test_client:
        yield test_client

    app.dependency_overrides.clear()


async def authenticate_as(user: User) -> None:
    async def override_current_user():
        return user

    app.dependency_overrides[
        get_current_user
    ] = override_current_user


@pytest.mark.asyncio
async def test_authenticated_user_can_create_workspace(
    client,
    db_session,
):
    user = await create_user(
        db_session,
        email_prefix="creator",
    )

    await authenticate_as(user)

    response = await client.post(
        "/api/v1/workspaces",
        json={
            "name": "Engineering",
            "slug": f"engineering-{uuid4().hex[:8]}",
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert body["name"] == "Engineering"
    assert body["id"] is not None


@pytest.mark.asyncio
async def test_non_member_cannot_access_workspace(
    client,
    db_session,
):
    owner = await create_user(
        db_session,
        email_prefix="owner",
    )

    non_member = await create_user(
        db_session,
        email_prefix="outsider",
    )

    workspace = await create_workspace(
        db_session,
        owner=owner,
    )

    await authenticate_as(non_member)

    response = await client.get(
        f"/api/v1/workspaces/{workspace.id}",
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_member_can_access_workspace(
    client,
    db_session,
):
    owner = await create_user(
        db_session,
        email_prefix="owner",
    )

    member = await create_user(
        db_session,
        email_prefix="member",
    )

    workspace = await create_workspace(
        db_session,
        owner=owner,
    )

    await add_member(
        db_session,
        workspace=workspace,
        user=member,
        role=WorkspaceRole.MEMBER,
    )

    await authenticate_as(member)

    response = await client.get(
        f"/api/v1/workspaces/{workspace.id}",
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(workspace.id)


@pytest.mark.asyncio
async def test_admin_can_remove_member(
    client,
    db_session,
):
    owner = await create_user(
        db_session,
        email_prefix="owner",
    )

    admin = await create_user(
        db_session,
        email_prefix="admin",
    )

    member = await create_user(
        db_session,
        email_prefix="member",
    )

    workspace = await create_workspace(
        db_session,
        owner=owner,
    )

    await add_member(
        db_session,
        workspace=workspace,
        user=admin,
        role=WorkspaceRole.ADMIN,
    )

    await add_member(
        db_session,
        workspace=workspace,
        user=member,
        role=WorkspaceRole.MEMBER,
    )

    await authenticate_as(admin)

    response = await client.delete(
        f"/api/v1/workspaces/{workspace.id}"
        f"/members/{member.id}",
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_member_cannot_remove_another_member(
    client,
    db_session,
):
    owner = await create_user(
        db_session,
        email_prefix="owner",
    )

    member = await create_user(
        db_session,
        email_prefix="member",
    )

    another_member = await create_user(
        db_session,
        email_prefix="another",
    )

    workspace = await create_workspace(
        db_session,
        owner=owner,
    )

    await add_member(
        db_session,
        workspace=workspace,
        user=member,
        role=WorkspaceRole.MEMBER,
    )

    await add_member(
        db_session,
        workspace=workspace,
        user=another_member,
        role=WorkspaceRole.MEMBER,
    )

    await authenticate_as(member)

    response = await client.delete(
        f"/api/v1/workspaces/{workspace.id}"
        f"/members/{another_member.id}",
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_only_assign_member_role(
    client,
    db_session,
):
    owner = await create_user(
        db_session,
        email_prefix="owner",
    )

    admin = await create_user(
        db_session,
        email_prefix="admin",
    )

    member = await create_user(
        db_session,
        email_prefix="member",
    )

    workspace = await create_workspace(
        db_session,
        owner=owner,
    )

    await add_member(
        db_session,
        workspace=workspace,
        user=admin,
        role=WorkspaceRole.ADMIN,
    )

    await add_member(
        db_session,
        workspace=workspace,
        user=member,
        role=WorkspaceRole.MEMBER,
    )

    await authenticate_as(admin)

    response = await client.patch(
        f"/api/v1/workspaces/{workspace.id}"
        f"/members/{member.id}/role",
        json={"role": "owner"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_owner_can_transfer_ownership(
    client,
    db_session,
):
    owner = await create_user(
        db_session,
        email_prefix="owner",
    )

    member = await create_user(
        db_session,
        email_prefix="member",
    )

    workspace = await create_workspace(
        db_session,
        owner=owner,
    )

    await add_member(
        db_session,
        workspace=workspace,
        user=member,
        role=WorkspaceRole.MEMBER,
    )

    await authenticate_as(owner)

    response = await client.post(
        f"/api/v1/workspaces/{workspace.id}"
        f"/transfer-ownership/{member.id}",
    )

    assert response.status_code == 200
    assert response.json()["role"] == "owner"


@pytest.mark.asyncio
async def test_unauthenticated_request_is_rejected(
    client,
):
    response = await client.get(
        "/api/v1/workspaces",
    )

    assert response.status_code == 401