from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.agent import router as agent_router
from app.api.routes.ask import (
    router as ask_router,
)
from app.api.routes.documents import (
    router as documents_router,
)
from app.api.routes.health import (
    router as health_router,
)
from app.api.routes.search import (
    router as search_router,
)
from app.api.routes.users import (
    router as users_router,
)
from app.api.routes.workspaces import (
    router as workspaces_router,
)
from app.core.config import settings
from app.core.rate_limit import RedisRateLimitMiddleware
from app.core.observability import configure_observability
from app.agent.checkpointer import get_checkpointer


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)
configure_observability(app)


app.add_middleware(RedisRateLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.authorized_parties,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(
    health_router,
    prefix="/api/v1",
)

app.include_router(
    users_router,
    prefix="/api/v1",
)

app.include_router(
    workspaces_router,
    prefix="/api/v1",
)

app.include_router(
    documents_router,
    prefix="/api/v1",
)

app.include_router(
    search_router,
    prefix="/api/v1",
)

app.include_router(
    ask_router,
    prefix="/api/v1",
)

app.include_router(
    agent_router,
    prefix="/api/v1",
)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": "ForgeOps AI API",
        "service": "api",
        "version": settings.app_version,
    }