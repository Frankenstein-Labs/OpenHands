from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InvitationCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: str = Field(default='member', pattern=r'^(admin|member|viewer)$')

    @field_validator('email')
    @classmethod
    def _validate_email(cls, value: str) -> str:
        candidate = value.strip().lower()
        local, _, domain = candidate.partition('@')
        if not local or not domain or '.' not in domain or ' ' in candidate:
            raise ValueError('invalid email address')
        return candidate


class InvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    email: str
    role: str
    status: str
    expires_at: datetime
    created_at: datetime


class InvitationCreatedResponse(InvitationResponse):
    token: str


class AcceptInvitationRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)


class AcceptedMembershipResponse(BaseModel):
    organization_id: UUID
    role: str
