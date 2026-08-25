from __future__ import annotations

import logging
import time

import redis.asyncio as redis
from fastapi import Request
from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Redis-backed rate limiting middleware.

    The Redis client is created lazily for each request instead of being
    created when the global FastAPI application is imported.

    This is important for pytest + httpx ASGI tests because pytest can
    create and destroy event loops between tests.
    """

    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        # Health checks should never be rate limited.
        if request.url.path.endswith("/health"):
            return await call_next(request)

        identity = request.client.host if request.client else "unknown"

        window = int(time.time()) // settings.rate_limit_window_seconds

        key = (
            f"forgeops:ratelimit:"
            f"{identity}:"
            f"{window}"
        )

        client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )

        try:
            count = await client.incr(key)

            if count == 1:
                await client.expire(
                    key,
                    settings.rate_limit_window_seconds + 1,
                )

            if count > settings.rate_limit_requests:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Rate limit exceeded",
                    },
                    headers={
                        "Retry-After": str(
                            settings.rate_limit_window_seconds
                        ),
                    },
                )

        except RedisError:
            # Redis is an availability aid, not the source of truth.
            #
            # If Redis is unavailable during development or testing,
            # allow the request to continue.
            logger.warning(
                "Redis rate limiter unavailable; "
                "allowing request to continue.",
                exc_info=True,
            )

        finally:
            # IMPORTANT:
            # Close this client while the current event loop is still alive.
            try:
                await client.aclose()
            except (RedisError, RuntimeError):
                logger.debug(
                    "Redis rate limiter client could not be closed cleanly.",
                    exc_info=True,
                )

        return await call_next(request)