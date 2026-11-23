from __future__ import annotations

from typing import Any

from app.database.supabase import SupabaseClient

_SELECT = (
    'id,full_name,avatar_url,locale,timezone,preferences,status,'
    'active_organization_id,created_at,updated_at'
)


class ProfilesRepository:
    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    async def get(self, access_token: str, user_id: str) -> dict[str, Any] | None:
        result = await self.client.request(
            'GET',
            'profiles',
            access_token=access_token,
            params={'select': _SELECT, 'id': f'eq.{user_id}', 'limit': '1'},
        )
        return result[0] if result else None

    async def insert(self, access_token: str, user_id: str) -> dict[str, Any]:
        result = await self.client.request(
            'POST',
            'profiles',
            access_token=access_token,
            json={'id': user_id},
            prefer='return=representation',
        )
        return result[0] if isinstance(result, list) else result

    async def patch(self, access_token: str, user_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        result = await self.client.request(
            'PATCH',
            'profiles',
            access_token=access_token,
            params={'id': f'eq.{user_id}'},
            json={**data, 'updated_at': 'now()'},
            prefer='return=representation',
        )
        return result[0] if result else None
