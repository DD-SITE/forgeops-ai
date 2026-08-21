from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.users import router as users_router
from app.api.routes.workspaces import router as workspaces_router
from app.core.config import settings


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)


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


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": "ForgeOps AI API",
        "service": "api",
        "version": settings.app_version,
    }