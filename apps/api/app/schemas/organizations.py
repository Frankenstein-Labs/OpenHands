from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OrganizationCreate(BaseModel):
    slug: str = Field(min_length=3, max_length=64, pattern=r'^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$')
    name: str = Field(min_length=1, max_length=160)


class OrganizationUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=160)


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    name: str
    created_by: UUID
    created_at: datetime
    updated_at: datetime
