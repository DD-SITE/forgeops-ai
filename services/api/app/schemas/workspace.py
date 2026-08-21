from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.workspace_member import WorkspaceRole


class WorkspaceCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=255,
    )

    slug: str = Field(
        min_length=3,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )


class WorkspaceResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


class WorkspaceMembershipResponse(BaseModel):
    workspace_id: UUID
    role: WorkspaceRole

    model_config = ConfigDict(
        from_attributes=True,
    )


class WorkspaceMemberResponse(BaseModel):
    user_id: UUID
    role: WorkspaceRole
    joined_at: datetime


class WorkspaceRoleUpdate(BaseModel):
    role: WorkspaceRole