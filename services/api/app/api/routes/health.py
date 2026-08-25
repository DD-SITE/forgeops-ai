from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.queue.ingestion import IngestionQueue


router = APIRouter()


@router.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    await db.execute(text("SELECT 1"))

    queue = IngestionQueue()
    try:
        redis_ok = await queue.ping()
    finally:
        await queue.close()

    return {
        "status": "ok" if redis_ok else "degraded",
        "database": "ok",
        "redis": "ok" if redis_ok else "unavailable",
    }
