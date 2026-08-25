"""add document version uniqueness

Revision ID: b31d0a1f9e22
Revises: 708b967de978
Create Date: 2026-08-21

"""

from collections.abc import Sequence

from alembic import op

revision: str = "b31d0a1f9e22"
down_revision: str | Sequence[str] | None = "708b967de978"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_document_versions_document_version",
        "document_versions",
        ["document_id", "version_number"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_document_versions_document_version",
        "document_versions",
        type_="unique",
    )