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
from app.storage.s3 import get_storage


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, dict] = {}

    def create_presigned_put_url(
        self,
        *,
        object_key: str,
        content_type: str,
    ) -> str:
        return f"http://fake-storage/{object_key}"

    def create_presigned_get_url(
        self,
        *,
        object_key: str,
    ) -> str:
        return f"http://fake-storage/download/{object_key}"

    def head_object(
        self,
        *,
        object_key: str,
    ) -> dict:
        if object_key not in self.objects:
            from botocore.exceptions import ClientError

            raise ClientError(
                {
                    "Error": {
                        "Code": "404",
                        "Message": "Not Found",
                    }
                },
                "HeadObject",
            )

        return self.objects[object_key]

    def delete_object(
        self,
        *,
        object_key: str,
    ) -> None:
        self.objects.pop(object_key, None)


@pytest.fixture
async def document_client(db_session):
    user = User(
        clerk_id=f"test_clerk_{uuid4().hex}",
        email=f"documents-{uuid4().hex[:8]}@forgeops.local",
        full_name="Document Test User",
    )

    workspace = Workspace(
        name="Document Test Workspace",
        slug=f"document-workspace-{uuid4().hex[:8]}",
    )

    membership = WorkspaceMember(
        user=user,
        workspace=workspace,
        role=WorkspaceRole.OWNER,
    )

    db_session.add(membership)

    await db_session.flush()

    fake_storage = FakeStorage()

    async def override_db():
        yield db_session

    async def override_user():
        return user

    def override_storage():
        return fake_storage

    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_storage] = override_storage

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client, user, workspace, fake_storage

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_upload_intent(
    document_client,
):
    client, _, workspace, fake_storage = document_client

    response = await client.post(
        f"/api/v1/workspaces/{workspace.id}/documents/upload-intent",
        json={
            "filename": "architecture.pdf",
            "content_type": "application/pdf",
            "size_bytes": 1024,
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert body["document_id"] is not None
    assert body["version_id"] is not None
    assert body["object_key"].startswith(f"workspaces/{workspace.id}/documents/")
    assert body["upload_url"].startswith("http://fake-storage/")

    assert fake_storage.objects == {}


@pytest.mark.asyncio
async def test_complete_upload_requires_object(
    document_client,
):
    client, _, workspace, _ = document_client

    intent_response = await client.post(
        f"/api/v1/workspaces/{workspace.id}/documents/upload-intent",
        json={
            "filename": "requirements.md",
            "content_type": "text/markdown",
            "size_bytes": 512,
        },
    )

    assert intent_response.status_code == 201

    intent = intent_response.json()

    response = await client.post(
        f"/api/v1/workspaces/{workspace.id}/documents"
        f"/{intent['document_id']}"
        f"/versions/{intent['version_id']}/complete",
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_complete_upload_after_object_exists(
    document_client,
):
    client, _, workspace, fake_storage = document_client

    intent_response = await client.post(
        f"/api/v1/workspaces/{workspace.id}/documents/upload-intent",
        json={
            "filename": "notes.txt",
            "content_type": "text/plain",
            "size_bytes": 1234,
        },
    )

    assert intent_response.status_code == 201

    intent = intent_response.json()

    fake_storage.objects[intent["object_key"]] = {
        "ContentLength": 1234,
        "ContentType": "text/plain",
    }

    response = await client.post(
        f"/api/v1/workspaces/{workspace.id}/documents"
        f"/{intent['document_id']}"
        f"/versions/{intent['version_id']}/complete",
    )

    assert response.status_code == 200

    body = response.json()

    assert body["document"]["status"] == "uploaded"
    assert body["version"]["status"] == "uploaded"
    assert body["version"]["size_bytes"] == 1234
