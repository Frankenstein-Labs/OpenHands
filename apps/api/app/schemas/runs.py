from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RunCreate(BaseModel):
    agent_id: UUID | None = None
    model_id: str | None = Field(default=None, max_length=128)
    conversation_id: str | None = Field(default=None, max_length=128)
    prompt: str = Field(min_length=1, max_length=100000)
    # Every run reserves credits up front; a zero budget would bypass quota checks.
    budget_credits: float = Field(default=1.0, gt=0)
    metadata: dict[str, Any] = {}


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    agent_id: UUID | None = None
    conversation_id: str | None = None
    created_by: UUID
    model_id: str | None = None
    status: str
    prompt: str | None = None
    budget_credits: float
    credits_reserved: float
    credits_used: float
    error: str | None = None
    metadata: dict[str, Any] = {}
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class RunEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: UUID
    seq: int
    type: str
    payload: dict[str, Any] = {}
    created_at: datetime
