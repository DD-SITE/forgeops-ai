from typing import Annotated

from clerk_backend_api import AuthenticateRequestOptions, authenticate_request
from fastapi import Depends, HTTPException, Request, status

from app.core.config import settings


def require_clerk_user(request: Request) -> str:
    state = authenticate_request(
        request,
        AuthenticateRequestOptions(
            secret_key=settings.clerk_secret_key,
            authorized_parties=settings.authorized_parties,
            accepts_token=["session_token"],
        ),
    )

    if not state.is_signed_in:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    user_id = state.payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )

    return user_id


CurrentClerkUserId = Annotated[
    str,
    Depends(require_clerk_user),
]