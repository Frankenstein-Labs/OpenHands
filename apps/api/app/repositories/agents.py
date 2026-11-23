from __future__ import annotations

from typing import Any
from uuid import UUID

from app.database.supabase import SupabaseClient

_SELECT = (
    'id,organization_id,created_by,name,description,kind,model_id,'
    'system_prompt,tools,config,archived,created_at,updated_at'
)


class AgentsRepository:
    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    async def list(self, access_token: str, organization_id: UUID) -> list[dict[str, Any]]:
        result = await self.client.request(
            'GET', 'agents', access_token=access_token,
            params={
                'select': _SELECT,
                'organization_id': f'eq.{organization_id}',
                'order': 'created_at.desc',
            },
        )
        return result or []

    async def create(self, access_token: str, organization_id: UUID, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
        result = await self.client.request(
            'POST', 'agents', access_token=access_token,
            json={**data, 'organization_id': str(organization_id), 'created_by': user_id},
            prefer='return=representation',
        )
        return result[0] if isinstance(result, list) else result

    async def get(self, access_token: str, organization_id: UUID, agent_id: UUID) -> dict[str, Any] | None:
        result = await self.client.request(
            'GET', 'agents', access_token=access_token,
            params={
                'select': _SELECT,
                'id': f'eq.{agent_id}',
                'organization_id': f'eq.{organization_id}',
                'limit': '1',
            },
        )
        return result[0] if result else None

    async def update(self, access_token: str, organization_id: UUID, agent_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        result = await self.client.request(
            'PATCH', 'agents', access_token=access_token,
            params={'id': f'eq.{agent_id}', 'organization_id': f'eq.{organization_id}'},
            json={**data, 'updated_at': 'now()'},
            prefer='return=representation',
        )
        return result[0] if result else None

    async def delete(self, access_token: str, organization_id: UUID, agent_id: UUID) -> None:
        await self.client.request(
            'DELETE', 'agents', access_token=access_token,
            params={'id': f'eq.{agent_id}', 'organization_id': f'eq.{organization_id}'},
        )
