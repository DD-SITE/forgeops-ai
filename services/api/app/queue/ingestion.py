from __future__ import annotations

import asyncio
import os
import socket
from uuid import UUID

import redis.asyncio as redis
from redis.exceptions import (
    ConnectionError as RedisConnectionError,
    ResponseError,
    TimeoutError as RedisTimeoutError,
)

from app.core.config import settings


class IngestionQueue:
    """Redis Streams queue with a consumer group.

    PostgreSQL remains the durable job source of truth; the stream is the
    delivery mechanism. A job is acknowledged only after the worker has
    handled it, allowing recovery after worker crashes.
    """

    group_name = "forgeops-workers"
    @property
    def consumer_name(self) -> str:
        return f"{socket.gethostname()}-{os.getpid()}"

    def __init__(self) -> None:
        self.client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=None,
            health_check_interval=30,
        )
        self._group_ready = False

    async def _ensure_group(self) -> None:
        if self._group_ready:
            return

        try:
            await self.client.xgroup_create(
                settings.ingestion_queue_name,
                self.group_name,
                id="0",
                mkstream=True,
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

        self._group_ready = True

    async def enqueue(self, job_id: UUID) -> None:
        await self._ensure_group()
        await self.client.xadd(
            settings.ingestion_queue_name,
            {"job_id": str(job_id)},
            maxlen=10000,
            approximate=True,
        )

    async def dequeue(
        self,
        timeout: int,
    ) -> tuple[str, UUID] | None:
        while True:
            try:
                await self._ensure_group()
                result = await self.client.xreadgroup(
                    groupname=self.group_name,
                    consumername=self.consumer_name,
                    streams={settings.ingestion_queue_name: ">"},
                    count=1,
                    block=max(timeout, 1) * 1000,
                )

                if not result:
                    return None

                _, messages = result[0]
                message_id, fields = messages[0]
                return message_id, UUID(fields["job_id"])

            except RedisTimeoutError:
                await asyncio.sleep(1)
            except RedisConnectionError:
                self._group_ready = False
                await asyncio.sleep(2)

    async def ack(self, message_id: str) -> None:
        await self.client.xack(
            settings.ingestion_queue_name,
            self.group_name,
            message_id,
        )

    async def length(self) -> int:
        return int(await self.client.xlen(settings.ingestion_queue_name))

    async def ping(self) -> bool:
        try:
            return bool(await self.client.ping())
        except (RedisConnectionError, RedisTimeoutError):
            return False

    async def close(self) -> None:
        await self.client.aclose()
