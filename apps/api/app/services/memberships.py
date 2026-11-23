from __future__ import annotations

from uuid import UUID

from app.repositories.memberships import MembershipsRepository
from app.schemas.memberships import MembershipRole


class MembershipAccessDenied(Exception):
    pass


class MembershipNotFound(Exception):
    pass


class MembershipsService:
    def __init__(self, repository: MembershipsRepository) -> None:
        self.repository = repository

    async def _require_role(self, access_token: str, organization_id: UUID, user_id: str, allowed: set[str]) -> dict:
        membership = await self.repository.get_actor_membership(access_token, organization_id, user_id)
        if membership is None:
            raise MembershipNotFound
        if membership['role'] not in allowed:
            raise MembershipAccessDenied
        return membership

    async def list_members(self, access_token: str, actor_user_id: str, organization_id: UUID):
        await self._require_role(access_token, organization_id, actor_user_id, set(MembershipRole))
        return await self.repository.list_members(access_token, organization_id)

    async def add_member(self, access_token: str, actor_user_id: str, organization_id: UUID, user_id: UUID, role: MembershipRole):
        await self._require_role(access_token, organization_id, actor_user_id, {'owner', 'admin'})
        return await self.repository.add_member(access_token, organization_id, user_id, role.value)

    async def update_role(self, access_token: str, actor_user_id: str, organization_id: UUID, user_id: UUID, role: MembershipRole):
        await self._require_role(access_token, organization_id, actor_user_id, {'owner', 'admin'})
        return await self.repository.update_role(access_token, organization_id, user_id, role.value)

    async def remove_member(self, access_token: str, actor_user_id: str, organization_id: UUID, user_id: UUID):
        await self._require_role(access_token, organization_id, actor_user_id, {'owner', 'admin'})
        await self.repository.remove_member(access_token, organization_id, user_id)

    async def transfer_ownership(self, access_token: str, actor_user_id: str, organization_id: UUID, new_owner_user_id: UUID):
        await self._require_role(access_token, organization_id, actor_user_id, {'owner'})
        return await self.repository.transfer_ownership(access_token, organization_id, new_owner_user_id)
