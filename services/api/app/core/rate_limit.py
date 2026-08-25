from __future__ import annotations

import time

import redis.asyncio as redis
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings


class RedisRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )

    async def dispatch(self, request: Request, call_next):
        if request.url.path.endswith("/health"):
            return await call_next(request)

        identity = request.client.host if request.client else "unknown"
        key = (
            f"forgeops:ratelimit:{identity}:"
            f"{int(time.time()) // settings.rate_limit_window_seconds}"
        )

        try:
            count = await self.client.incr(key)
            if count == 1:
                await self.client.expire(
                    key,
                    settings.rate_limit_window_seconds + 1,
                )

            if count > settings.rate_limit_requests:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded"},
                    headers={"Retry-After": str(settings.rate_limit_window_seconds)},
                )
        except Exception:
            # Redis is an availability aid, not the source of truth.
            pass

        return await call_next(request)

    async def close(self) -> None:
        await self.client.aclose()
