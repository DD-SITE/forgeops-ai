from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.current_user import get_current_user
from app.db.session import get_db_session
from app.ingestion.embeddings import get_embedding_service
from app.main import app
from app.models.document import (
    Document,
    DocumentStatus,
)
from app.models.document_chunk import DocumentChunk
from app.models.document_version import (
    DocumentVersion,
    DocumentVersionStatus,
)
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import (
    WorkspaceMember,
    WorkspaceRole,
)


class FakeEmbeddingService:
    def embed_query(
        self,
        query: str,
    ) -> list[float]:
        vector = [0.0] * 384
        vector[0] = 1.0
        return vector


@pytest.fixture
async def search_client(
    db_session,
):
    user = User(
        clerk_id=f"search_clerk_{uuid4().hex}",
        email=(
            f"search-{uuid4().hex[:8]}"
            "@forgeops.local"
        ),
        full_name="Search User",
    )

    workspace = Workspace(
        name="Search Workspace",
        slug=f"search-{uuid4().hex[:8]}",
    )

    membership = WorkspaceMember(
        user=user,
        workspace=workspace,
        role=WorkspaceRole.OWNER,
    )

    db_session.add(membership)

    # Persist user/workspace first so their UUIDs are available.
    await db_session.flush()

    document = Document(
        workspace_id=workspace.id,
        created_by=user.id,
        name="Architecture.md",
        status=DocumentStatus.READY,
    )

    db_session.add(document)

    await db_session.flush()

    version = DocumentVersion(
        document_id=document.id,
        version_number=1,
        object_key=f"test/{uuid4().hex}.md",
        original_filename="Architecture.md",
        content_type="text/markdown",
        size_bytes=100,
        status=DocumentVersionStatus.READY,
    )

    db_session.add(version)

    await db_session.flush()

    relevant_chunk = DocumentChunk(
        document_version_id=version.id,
        chunk_index=0,
        content=(
            "ForgeOps uses PostgreSQL and pgvector "
            "for semantic retrieval."
        ),
        content_hash=uuid4().hex,
        page_start=None,
        page_end=None,
        section_path=[
            "Architecture",
            "Retrieval",
        ],
        token_count=10,
        embedding=[1.0] + [0.0] * 383,
    )

    unrelated_chunk = DocumentChunk(
        document_version_id=version.id,
        chunk_index=1,
        content=(
            "The deployment dashboard displays "
            "runtime health information."
        ),
        content_hash=uuid4().hex,
        page_start=None,
        page_end=None,
        section_path=[
            "Operations",
        ],
        token_count=9,
        embedding=[0.0, 1.0] + [0.0] * 382,
    )

    db_session.add_all(
        [
            relevant_chunk,
            unrelated_chunk,
        ]
    )

    await db_session.flush()

    async def override_db():
        yield db_session

    async def override_user():
        return user

    def override_embeddings():
        return FakeEmbeddingService()

    app.dependency_overrides[get_db_session] = (
        override_db
    )

    app.dependency_overrides[get_current_user] = (
        override_user
    )

    app.dependency_overrides[
        get_embedding_service
    ] = override_embeddings

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client, user, workspace

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_semantic_search_returns_relevant_chunk(
    search_client,
):
    client, _, workspace = search_client

    response = await client.post(
        f"/api/v1/workspaces/{workspace.id}/search",
        json={
            "query": "How does ForgeOps retrieve knowledge?",
            "top_k": 5,
            "min_similarity": 0.5,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["query"] == (
        "How does ForgeOps retrieve knowledge?"
    )

    assert body["results"]

    result = body["results"][0]

    assert (
        "PostgreSQL"
        in result["content"]
    )

    assert result["similarity"] > 0.5


@pytest.mark.asyncio
async def test_non_member_cannot_search_workspace(
    search_client,
    db_session,
):
    client, _, workspace = search_client

    outsider = User(
        clerk_id=f"outsider_{uuid4().hex}",
        email=(
            f"outsider-{uuid4().hex[:8]}"
            "@forgeops.local"
        ),
        full_name="Outsider",
    )

    db_session.add(outsider)

    await db_session.flush()

    async def override_outsider():
        return outsider

    app.dependency_overrides[
        get_current_user
    ] = override_outsider

    response = await client.post(
        f"/api/v1/workspaces/{workspace.id}/search",
        json={
            "query": "PostgreSQL",
        },
    )

    assert response.status_code == 403