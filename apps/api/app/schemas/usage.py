from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UsageSummary(BaseModel):
    organization_id: UUID
    plan_id: str | None = None
    credits_limit: float
    credits_used: float
    credits_remaining: float
    by_type: dict[str, float] = {}


class LimitsResponse(BaseModel):
    organization_id: UUID
    plan_id: str | None = None
    limits: dict[str, Any] = {}
    credits_limit: float
    credits_used: float
    credits_remaining: float


class EntitlementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    organization_id: UUID
    plan_id: str
    status: str
    credits_limit: float
    credits_used: float
    period_start: datetime | None = None
    period_end: datetime | None = None
    updated_at: datetime | None = None
