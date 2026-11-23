from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=160)
    avatar_url: str | None = Field(default=None, max_length=2048)
    locale: str | None = Field(default=None, min_length=2, max_length=12)
    timezone: str | None = Field(default=None, max_length=64)
    preferences: dict[str, Any] | None = None
    active_organization_id: UUID | None = None


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str | None = None
    avatar_url: str | None = None
    locale: str
    timezone: str
    preferences: dict[str, Any] = {}
    status: str
    active_organization_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
