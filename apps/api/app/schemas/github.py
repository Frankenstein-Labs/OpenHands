from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InstallationLinkRequest(BaseModel):
    installation_id: int = Field(gt=0)


class InstallationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    installation_id: int
    account_login: str
    account_type: str | None = None
    status: str
    created_at: datetime


class RepositoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    github_repo_id: int
    full_name: str
    default_branch: str | None = None
    status: str


class WebhookAck(BaseModel):
    status: str
