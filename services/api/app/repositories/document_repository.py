from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.document import Document
from app.models.document_version import DocumentVersion


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        workspace_id: UUID,
        created_by: UUID,
        name: str,
        version: DocumentVersion,
    ) -> Document:
        document = Document(
            workspace_id=workspace_id,
            created_by=created_by,
            name=name,
        )

        version.document = document

        self.session.add(document)

        await self.session.flush()

        return document

    async def get_by_id(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
    ) -> Document | None:
        result = await self.session.execute(
            select(Document)
            .options(
                selectinload(Document.versions),
            )
            .where(
                Document.id == document_id,
                Document.workspace_id == workspace_id,
            )
        )

        return result.scalar_one_or_none()

    async def get_version(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        version_id: UUID,
    ) -> DocumentVersion | None:
        result = await self.session.execute(
            select(DocumentVersion)
            .join(
                Document,
                Document.id == DocumentVersion.document_id,
            )
            .where(
                Document.id == document_id,
                Document.workspace_id == workspace_id,
                DocumentVersion.id == version_id,
            )
        )

        return result.scalar_one_or_none()

    async def list_for_workspace(
        self,
        *,
        workspace_id: UUID,
    ) -> list[Document]:
        result = await self.session.execute(
            select(Document)
            .options(
                selectinload(Document.versions),
            )
            .where(
                Document.workspace_id == workspace_id,
            )
            .order_by(
                Document.created_at.desc(),
            )
        )

        return list(result.scalars().unique().all())