from __future__ import annotations

import asyncio
from uuid import UUID

import redis.asyncio as redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.core.config import settings


class IngestionQueue:
    def __init__(self) -> None:
        self.client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=None,
            health_check_interval=30,
        )

    async def enqueue(
        self,
        job_id: UUID,
    ) -> None:
        await self.client.lpush(
            settings.ingestion_queue_name,
            str(job_id),
        )

    async def dequeue(
        self,
        timeout: int,
    ) -> UUID | None:
        while True:
            try:
                result = await self.client.brpop(
                    settings.ingestion_queue_name,
                    timeout=timeout,
                )

                if result is None:
                    return None

                _, job_id = result

                return UUID(job_id)

            except RedisTimeoutError:
                # A blocking read timing out at the network layer
                # should not terminate the worker.
                await asyncio.sleep(1)

            except RedisConnectionError:
                # Redis may be temporarily unavailable.
                # Keep the worker alive and allow the next iteration
                # to reconnect through the connection pool.
                await asyncio.sleep(2)

    async def length(self) -> int:
        return await self.client.llen(
            settings.ingestion_queue_name,
        )

    async def ping(self) -> bool:
        try:
            return bool(await self.client.ping())
        except (
            RedisConnectionError,
            RedisTimeoutError,
        ):
            return False

    async def close(self) -> None:
        await self.client.aclose()