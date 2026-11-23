from __future__ import annotations

from typing import Any
from uuid import UUID

from app.database.supabase import SupabaseClient


class MembershipsRepository:
    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    async def get_actor_membership(self, access_token: str, organization_id: UUID, user_id: str) -> dict[str, Any] | None:
        result = await self.client.request(
            'GET',
            'organization_memberships',
            access_token=access_token,
            params={
                'select': 'organization_id,user_id,role,created_at',
                'organization_id': f'eq.{organization_id}',
                'user_id': f'eq.{user_id}',
                'limit': '1',
            },
        )
        return result[0] if result else None

    async def list_members(self, access_token: str, organization_id: UUID) -> list[dict[str, Any]]:
        result = await self.client.request(
            'GET',
            'organization_memberships',
            access_token=access_token,
            params={
                'select': 'organization_id,user_id,role,created_at',
                'organization_id': f'eq.{organization_id}',
                'order': 'created_at.asc',
            },
        )
        return result or []

    async def add_member(self, access_token: str, organization_id: UUID, user_id: UUID, role: str) -> dict[str, Any]:
        return await self.client.rpc(
            'add_organization_member',
            {'target_organization_id': str(organization_id), 'target_user_id': str(user_id), 'target_role': role},
            access_token=access_token,
        )

    async def update_role(self, access_token: str, organization_id: UUID, user_id: UUID, role: str) -> dict[str, Any]:
        return await self.client.rpc(
            'update_organization_member_role',
            {'target_organization_id': str(organization_id), 'target_user_id': str(user_id), 'target_role': role},
            access_token=access_token,
        )

    async def remove_member(self, access_token: str, organization_id: UUID, user_id: UUID) -> None:
        await self.client.rpc(
            'remove_organization_member',
            {'target_organization_id': str(organization_id), 'target_user_id': str(user_id)},
            access_token=access_token,
        )

    async def transfer_ownership(self, access_token: str, organization_id: UUID, new_owner_user_id: UUID) -> dict[str, Any]:
        return await self.client.rpc(
            'transfer_organization_ownership',
            {'target_organization_id': str(organization_id), 'new_owner_user_id': str(new_owner_user_id)},
            access_token=access_token,
        )
