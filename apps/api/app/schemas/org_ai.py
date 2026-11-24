from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CredentialIn(BaseModel):
    api_key: str = Field(min_length=8, max_length=4096)


class CredentialOut(BaseModel):
    provider_id: str
    key_last4: str


class CredentialMetadataOut(BaseModel):
    provider_id: str
    key_last4: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class OrgAISettingsIn(BaseModel):
    default_model_id: str | None = None
    monthly_token_limit: int | None = Field(default=None, ge=0)
    credits_per_1k_tokens: float | None = Field(default=None, ge=0)


class OrgAISettingsOut(BaseModel):
    organization_id: str
    default_model_id: str | None = None
    monthly_token_limit: int | None = None
    credits_per_1k_tokens: float | None = None
