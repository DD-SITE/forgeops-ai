from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentClerkUserId
from app.auth.service import get_or_create_local_user
from app.db.session import get_db_session
from app.models.user import User


async def get_current_user(
    clerk_user_id: CurrentClerkUserId,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    return await get_or_create_local_user(
        session,
        clerk_user_id,
    )


CurrentUser = Annotated[
    User,
    Depends(get_current_user),
]
