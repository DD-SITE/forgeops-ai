"""add clerk identity to users

Revision ID: 17d155e8bb8b
Revises: a04f5c08be7f
Create Date: 2026-08-20 22:29:41.031591

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "17d155e8bb8b"
down_revision: str | Sequence[str] | None = "a04f5c08be7f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""

    # 1. Add the column as nullable so existing rows can survive.
    op.add_column(
        "users",
        sa.Column(
            "clerk_id",
            sa.String(length=255),
            nullable=True,
        ),
    )

    # 2. Give existing development/test users deterministic placeholder IDs.
    #    These are temporary and must never be used as real Clerk IDs.
    op.execute(
        """
        UPDATE users
        SET clerk_id = 'legacy_' || id::text
        WHERE clerk_id IS NULL
        """
    )

    # 3. Make the column required after every existing row has a value.
    op.alter_column(
        "users",
        "clerk_id",
        existing_type=sa.String(length=255),
        nullable=False,
    )

    # 4. Enforce uniqueness at the database level.
    op.create_index(
        op.f("ix_users_clerk_id"),
        "users",
        ["clerk_id"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(
        op.f("ix_users_clerk_id"),
        table_name="users",
    )

    op.drop_column(
        "users",
        "clerk_id",
    )