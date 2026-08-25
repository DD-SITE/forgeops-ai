from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AgentRunRequest(BaseModel):
    query: str = Field(min_length=2, max_length=4000)


class AgentActionResponse(BaseModel):
    id: UUID
    action_type: str
    status: str
    payload: dict
    result: dict | None
    created_at: datetime
    executed_at: datetime | None


class AgentRunResponse(BaseModel):
    id: UUID
    thread_id: str
    query: str
    status: str
    answer: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    actions: list[AgentActionResponse] = Field(default_factory=list)


class AgentApprovalRequest(BaseModel):
    decision: str = Field(pattern="^(approve|edit|reject)$")
    payload: dict | None = None
