from clerk_backend_api import Clerk
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.repositories.user_repository import UserRepository


def _extract_primary_email(clerk_user) -> str | None:
    primary_email_id = getattr(
        clerk_user,
        "primary_email_address_id",
        None,
    )

    email_addresses = getattr(
        clerk_user,
        "email_addresses",
        [],
    )

    for email_address in email_addresses:
        email_id = getattr(email_address, "id", None)

        if email_id == primary_email_id:
            return getattr(email_address, "email_address", None)

    if email_addresses:
        return getattr(
            email_addresses[0],
            "email_address",
            None,
        )

    return None


async def get_or_create_local_user(
    session: AsyncSession,
    clerk_user_id: str,
) -> User:
    repository = UserRepository(session)

    existing_user = await repository.get_by_clerk_id(
        clerk_user_id
    )

    if existing_user is not None:
        return existing_user

    with Clerk(
        bearer_auth=settings.clerk_secret_key,
    ) as clerk:
        response = clerk.users.get(
            user_id=clerk_user_id,
        )

    clerk_user = response

    email = _extract_primary_email(clerk_user)

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authenticated Clerk user has no verified email address",
        )

    first_name = getattr(clerk_user, "first_name", None)
    last_name = getattr(clerk_user, "last_name", None)

    full_name = " ".join(
        part
        for part in [first_name, last_name]
        if part
    ) or None

    try:
        user = await repository.create(
            clerk_id=clerk_user_id,
            email=email,
            full_name=full_name,
        )

        await session.commit()

        return user

    except Exception:
        await session.rollback()

        existing_user = await repository.get_by_clerk_id(
            clerk_user_id
        )

        if existing_user is not None:
            return existing_user

        raise