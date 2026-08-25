"""add ingestion jobs and vector chunks

Revision ID: c5e7f914a321
Revises: b31d0a1f9e22
Create Date: 2026-08-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import VECTOR
from sqlalchemy.dialects.postgresql import ENUM

from alembic import op

revision: str = "c5e7f914a321"
down_revision: str | Sequence[str] | None = "b31d0a1f9e22"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # pgvector extension.
    op.execute(
        "CREATE EXTENSION IF NOT EXISTS vector"
    )

    # PostgreSQL enum is created explicitly once.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_type
                WHERE typname = 'ingestion_job_status'
            ) THEN
                CREATE TYPE ingestion_job_status AS ENUM (
                    'PENDING',
                    'QUEUED',
                    'PROCESSING',
                    'COMPLETED',
                    'FAILED'
                );
            END IF;
        END
        $$;
        """
    )

    # Tell SQLAlchemy that the PostgreSQL ENUM already exists.
    ingestion_job_status = ENUM(
        "PENDING",
        "QUEUED",
        "PROCESSING",
        "COMPLETED",
        "FAILED",
        name="ingestion_job_status",
        create_type=False,
    )

    op.create_table(
        "ingestion_jobs",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "document_version_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "status",
            ingestion_job_status,
            nullable=False,
            server_default=sa.text("'PENDING'"),
        ),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "max_attempts",
            sa.Integer(),
            nullable=False,
            server_default="3",
        ),
        sa.Column(
            "last_error",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "queued_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_version_id"],
            ["document_versions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_version_id",
            name="uq_ingestion_jobs_document_version",
        ),
    )

    op.create_index(
        "ix_ingestion_jobs_document_version_id",
        "ingestion_jobs",
        ["document_version_id"],
    )

    op.create_index(
        "ix_ingestion_jobs_status",
        "ingestion_jobs",
        ["status"],
    )

    op.create_table(
        "document_chunks",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "document_version_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "chunk_index",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "content",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "content_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "page_start",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "page_end",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "section_path",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "token_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "embedding",
            VECTOR(384),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_version_id"],
            ["document_versions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_version_id",
            "chunk_index",
            name="uq_document_chunks_version_index",
        ),
    )

    op.create_index(
        "ix_document_chunks_document_version_id",
        "document_chunks",
        ["document_version_id"],
    )

    op.create_index(
        "ix_document_chunks_content_hash",
        "document_chunks",
        ["content_hash"],
    )

    op.execute(
        """
        CREATE INDEX ix_document_chunks_embedding_hnsw
        ON document_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw"
    )

    op.drop_index(
        "ix_document_chunks_content_hash",
        table_name="document_chunks",
    )

    op.drop_index(
        "ix_document_chunks_document_version_id",
        table_name="document_chunks",
    )

    op.drop_table(
        "document_chunks"
    )

    op.drop_index(
        "ix_ingestion_jobs_status",
        table_name="ingestion_jobs",
    )

    op.drop_index(
        "ix_ingestion_jobs_document_version_id",
        table_name="ingestion_jobs",
    )

    op.drop_table(
        "ingestion_jobs"
    )

    op.execute(
        "DROP TYPE IF EXISTS ingestion_job_status"
    )