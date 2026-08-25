from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_clerk_id(self, clerk_id: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.clerk_id == clerk_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id):
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        clerk_id: str,
        email: str,
        full_name: str | None,
    ) -> User:
        user = User(
            clerk_id=clerk_id,
            email=email,
            full_name=full_name,
        )

        self.session.add(user)
        await self.session.flush()

        return user
