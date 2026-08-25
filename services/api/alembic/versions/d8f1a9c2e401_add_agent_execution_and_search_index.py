"""add agent execution tables and full-text search index

Revision ID: d8f1a9c2e401
Revises: c5e7f914a321
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, JSONB, TSVECTOR

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d8f1a9c2e401"
down_revision: str | Sequence[str] | None = "c5e7f914a321"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # PostgreSQL full-text search support for document chunks
    # ------------------------------------------------------------------
    op.add_column(
        "document_chunks",
        sa.Column(
            "search_vector",
            TSVECTOR(),
            sa.Computed(
                "to_tsvector('english', content)",
                persisted=True,
            ),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_document_chunks_search_vector",
        "document_chunks",
        ["search_vector"],
        postgresql_using="gin",
    )

    # ------------------------------------------------------------------
    # Agent execution enums
    #
    # Use PostgreSQL ENUM explicitly and disable SQLAlchemy's automatic
    # type creation. The migration creates each type exactly once below.
    # ------------------------------------------------------------------
    agent_run_status = ENUM(
        "QUEUED",
        "RUNNING",
        "AWAITING_APPROVAL",
        "COMPLETED",
        "REJECTED",
        "FAILED",
        name="agent_run_status",
        create_type=False,
    )

    agent_action_status = ENUM(
        "PROPOSED",
        "APPROVED",
        "REJECTED",
        "EXECUTED",
        "FAILED",
        name="agent_action_status",
        create_type=False,
    )

    bind = op.get_bind()

    agent_run_status.create(bind, checkfirst=True)
    agent_action_status.create(bind, checkfirst=True)

    # ------------------------------------------------------------------
    # Agent runs
    # ------------------------------------------------------------------
    op.create_table(
        "agent_runs",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "thread_id",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "query",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "status",
            agent_run_status,
            nullable=False,
            server_default="QUEUED",
        ),
        sa.Column(
            "answer",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "state_snapshot",
            JSONB(),
            nullable=True,
        ),
        sa.Column(
            "error",
            sa.Text(),
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
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("thread_id"),
    )

    op.create_index(
        "ix_agent_runs_workspace_id",
        "agent_runs",
        ["workspace_id"],
    )

    op.create_index(
        "ix_agent_runs_user_id",
        "agent_runs",
        ["user_id"],
    )

    op.create_index(
        "ix_agent_runs_status",
        "agent_runs",
        ["status"],
    )

    op.create_index(
        "ix_agent_runs_thread_id",
        "agent_runs",
        ["thread_id"],
    )

    # ------------------------------------------------------------------
    # Agent actions
    # ------------------------------------------------------------------
    op.create_table(
        "agent_actions",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "run_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "action_type",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "status",
            agent_action_status,
            nullable=False,
            server_default="PROPOSED",
        ),
        sa.Column(
            "payload",
            JSONB(),
            nullable=False,
        ),
        sa.Column(
            "result",
            JSONB(),
            nullable=True,
        ),
        sa.Column(
            "approved_by",
            sa.UUID(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "executed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["agent_runs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_agent_actions_run_id",
        "agent_actions",
        ["run_id"],
    )

    # ------------------------------------------------------------------
    # Audit logs
    # ------------------------------------------------------------------
    op.create_table(
        "audit_logs",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.UUID(),
            nullable=True,
        ),
        sa.Column(
            "action_type",
            sa.String(length=120),
            nullable=False,
        ),
        sa.Column(
            "resource_type",
            sa.String(length=120),
            nullable=True,
        ),
        sa.Column(
            "resource_id",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "payload",
            JSONB(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_audit_logs_workspace_id",
        "audit_logs",
        ["workspace_id"],
    )

    op.create_index(
        "ix_audit_logs_user_id",
        "audit_logs",
        ["user_id"],
    )

    op.create_index(
        "ix_audit_logs_action_type",
        "audit_logs",
        ["action_type"],
    )


def downgrade() -> None:
    # ------------------------------------------------------------------
    # Audit logs
    # ------------------------------------------------------------------
    op.drop_index(
        "ix_audit_logs_action_type",
        table_name="audit_logs",
    )

    op.drop_index(
        "ix_audit_logs_user_id",
        table_name="audit_logs",
    )

    op.drop_index(
        "ix_audit_logs_workspace_id",
        table_name="audit_logs",
    )

    op.drop_table("audit_logs")

    # ------------------------------------------------------------------
    # Agent actions
    # ------------------------------------------------------------------
    op.drop_index(
        "ix_agent_actions_run_id",
        table_name="agent_actions",
    )

    op.drop_table("agent_actions")

    # ------------------------------------------------------------------
    # Agent runs
    # ------------------------------------------------------------------
    op.drop_index(
        "ix_agent_runs_thread_id",
        table_name="agent_runs",
    )

    op.drop_index(
        "ix_agent_runs_status",
        table_name="agent_runs",
    )

    op.drop_index(
        "ix_agent_runs_user_id",
        table_name="agent_runs",
    )

    op.drop_index(
        "ix_agent_runs_workspace_id",
        table_name="agent_runs",
    )

    op.drop_table("agent_runs")

    # ------------------------------------------------------------------
    # PostgreSQL ENUM types
    # ------------------------------------------------------------------
    bind = op.get_bind()

    agent_action_status = ENUM(
        "PROPOSED",
        "APPROVED",
        "REJECTED",
        "EXECUTED",
        "FAILED",
        name="agent_action_status",
        create_type=False,
    )

    agent_run_status = ENUM(
        "QUEUED",
        "RUNNING",
        "AWAITING_APPROVAL",
        "COMPLETED",
        "REJECTED",
        "FAILED",
        name="agent_run_status",
        create_type=False,
    )

    agent_action_status.drop(bind, checkfirst=True)
    agent_run_status.drop(bind, checkfirst=True)

    # ------------------------------------------------------------------
    # Document full-text search
    # ------------------------------------------------------------------
    op.drop_index(
        "ix_document_chunks_search_vector",
        table_name="document_chunks",
    )

    op.drop_column(
        "document_chunks",
        "search_vector",
    )