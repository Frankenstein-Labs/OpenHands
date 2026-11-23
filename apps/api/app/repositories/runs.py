from __future__ import annotations

from typing import Any
from uuid import UUID

from app.database.supabase import SupabaseClient

ACTIVE_STATUSES = ('queued', 'provisioning', 'running', 'waiting')
_SELECT = (
    'id,organization_id,agent_id,conversation_id,created_by,model_id,status,'
    'prompt,budget_credits,credits_reserved,credits_used,error,metadata,'
    'started_at,finished_at,created_at,updated_at'
)


class RunsRepository:
    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    async def create(self, access_token: str, organization_id: UUID, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
        result = await self.client.request(
            'POST', 'agent_runs', access_token=access_token,
            json={**data, 'organization_id': str(organization_id), 'created_by': user_id},
            prefer='return=representation',
        )
        return result[0] if isinstance(result, list) else result

    async def get(self, access_token: str, organization_id: UUID, run_id: UUID) -> dict[str, Any] | None:
        result = await self.client.request(
            'GET', 'agent_runs', access_token=access_token,
            params={
                'select': _SELECT,
                'id': f'eq.{run_id}',
                'organization_id': f'eq.{organization_id}',
                'limit': '1',
            },
        )
        return result[0] if result else None

    async def list_active(self, access_token: str, organization_id: UUID) -> list[dict[str, Any]]:
        statuses = ','.join(ACTIVE_STATUSES)
        result = await self.client.request(
            'GET', 'agent_runs', access_token=access_token,
            params={
                'select': 'id,credits_reserved',
                'organization_id': f'eq.{organization_id}',
                'status': f'in.({statuses})',
            },
        )
        return result or []

    async def update_status(self, access_token: str, organization_id: UUID, run_id: UUID, fields: dict[str, Any]) -> dict[str, Any] | None:
        result = await self.client.request(
            'PATCH', 'agent_runs', access_token=access_token,
            params={'id': f'eq.{run_id}', 'organization_id': f'eq.{organization_id}'},
            json={**fields, 'updated_at': 'now()'},
            prefer='return=representation',
        )
        return result[0] if result else None

    async def list_events(self, access_token: str, organization_id: UUID, run_id: UUID) -> list[dict[str, Any]]:
        result = await self.client.request(
            'GET', 'agent_run_events', access_token=access_token,
            params={
                'select': 'id,run_id,seq,type,payload,created_at',
                'run_id': f'eq.{run_id}',
                'organization_id': f'eq.{organization_id}',
                'order': 'seq.asc',
            },
        )
        return result or []
