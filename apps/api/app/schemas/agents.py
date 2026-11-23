from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    kind: str = Field(default='coding', pattern=r'^(coding|general|research|custom)$')
    model_id: str | None = Field(default=None, max_length=128)
    system_prompt: str | None = Field(default=None, max_length=20000)
    tools: list[Any] = []
    config: dict[str, Any] = {}


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    kind: str | None = Field(default=None, pattern=r'^(coding|general|research|custom)$')
    model_id: str | None = Field(default=None, max_length=128)
    system_prompt: str | None = Field(default=None, max_length=20000)
    tools: list[Any] | None = None
    config: dict[str, Any] | None = None
    archived: bool | None = None


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    created_by: UUID
    name: str
    description: str | None = None
    kind: str
    model_id: str | None = None
    system_prompt: str | None = None
    tools: list[Any] = []
    config: dict[str, Any] = {}
    archived: bool
    created_at: datetime
    updated_at: datetime
