from fastapi import APIRouter

from app.auth.current_user import CurrentUser
from app.schemas.workspace import WorkspaceMembershipResponse


router = APIRouter(
    prefix="/me",
    tags=["me"],
)


@router.get("")
async def get_current_user(
    current_user: CurrentUser,
) -> dict:
    return {
        "id": str(current_user.id),
        "clerk_id": current_user.clerk_id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active,
    }