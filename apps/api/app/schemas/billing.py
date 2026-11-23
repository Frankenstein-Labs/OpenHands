from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    included_credits: float
    limits: dict[str, Any] = {}
    active: bool


class SubscriptionResponse(BaseModel):
    organization_id: UUID
    plan_id: str | None = None
    status: str | None = None
    provider: str | None = None
    current_period_end: datetime | None = None


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    provider: str | None = None
    amount_cents: int
    currency: str
    status: str
    hosted_url: str | None = None
    created_at: datetime


class CheckoutRequest(BaseModel):
    plan_id: str = Field(min_length=1, max_length=64)


class CheckoutResponse(BaseModel):
    url: str
    provider: str
