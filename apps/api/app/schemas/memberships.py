from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class MembershipRole(StrEnum):
    OWNER = 'owner'
    ADMIN = 'admin'
    MEMBER = 'member'
    VIEWER = 'viewer'


class MembershipResponse(BaseModel):
    organization_id: UUID
    user_id: UUID
    role: MembershipRole
    created_at: datetime


class AddMemberRequest(BaseModel):
    user_id: UUID
    role: MembershipRole = MembershipRole.MEMBER


class UpdateMemberRoleRequest(BaseModel):
    role: MembershipRole


class TransferOwnershipRequest(BaseModel):
    new_owner_user_id: UUID
