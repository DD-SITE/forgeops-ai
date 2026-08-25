from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.core.config import settings


def _postgres_uri() -> str:
    """
    Convert SQLAlchemy's asyncpg URL into a psycopg-compatible
    PostgreSQL connection string for LangGraph.
    """
    return settings.database_url.replace("+asyncpg", "")


def _build_serde():
    """
    Build the optional encrypted serializer used by LangGraph.

    If LANGGRAPH_AES_KEY is configured, checkpoint payloads are
    encrypted before being persisted to PostgreSQL.
    """
    if not settings.langgraph_aes_key:
        return None

    from langgraph.checkpoint.serde.encrypted import (
        EncryptedSerializer,
    )

    os.environ["LANGGRAPH_AES_KEY"] = settings.langgraph_aes_key

    return EncryptedSerializer.from_pycryptodome_aes()


async def setup_checkpointer() -> None:
    """
    Create/update the LangGraph PostgreSQL checkpoint schema.

    This function is intended to run once during deployment/startup
    initialization, not once per agent request.
    """
    serde = _build_serde()

    kwargs = {}

    if serde is not None:
        kwargs["serde"] = serde

    async with AsyncPostgresSaver.from_conn_string(
        _postgres_uri(),
        **kwargs,
    ) as checkpointer:
        await checkpointer.setup()


@asynccontextmanager
async def get_checkpointer() -> AsyncIterator[AsyncPostgresSaver]:
    """
    Provide an AsyncPostgresSaver for an agent execution.

    The checkpoint schema must already have been initialized by
    setup_checkpointer().
    """
    serde = _build_serde()

    kwargs = {}

    if serde is not None:
        kwargs["serde"] = serde

    async with AsyncPostgresSaver.from_conn_string(
        _postgres_uri(),
        **kwargs,
    ) as checkpointer:
        yield checkpointer
