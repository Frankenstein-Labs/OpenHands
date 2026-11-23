from __future__ import annotations

from typing import Any
from uuid import UUID

from app.database.supabase import SupabaseClient


class OrganizationsRepository:
    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    async def list_for_user(self, access_token: str) -> list[dict[str, Any]]:
        result = await self.client.request(
            'GET',
            'organizations',
            access_token=access_token,
            params={'select': 'id,slug,name,created_by,created_at,updated_at', 'order': 'created_at.desc'},
        )
        return result or []

    async def create_with_owner(self, access_token: str, slug: str, name: str) -> dict[str, Any]:
        result = await self.client.rpc(
            'create_organization_with_owner',
            {'organization_slug': slug, 'organization_name': name},
            access_token=access_token,
        )
        if isinstance(result, list):
            return result[0]
        return result

    async def get_for_user(self, access_token: str, organization_id: UUID) -> dict[str, Any] | None:
        result = await self.client.request(
            'GET',
            'organizations',
            access_token=access_token,
            params={
                'select': 'id,slug,name,created_by,created_at,updated_at',
                'id': f'eq.{organization_id}',
                'limit': '1',
            },
        )
        return result[0] if result else None

    async def update_for_user(self, access_token: str, organization_id: UUID, name: str) -> dict[str, Any] | None:
        result = await self.client.request(
            'PATCH',
            'organizations',
            access_token=access_token,
            params={'id': f'eq.{organization_id}'},
            json={'name': name, 'updated_at': 'now()'},
            prefer='return=representation',
        )
        return result[0] if result else None
