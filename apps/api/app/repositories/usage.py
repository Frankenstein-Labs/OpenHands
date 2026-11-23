from __future__ import annotations

from typing import Any
from uuid import UUID

from app.database.supabase import SupabaseClient

_ENTITLEMENT_SELECT = (
    'organization_id,plan_id,status,credits_limit,credits_used,'
    'period_start,period_end,updated_at'
)


class UsageRepository:
    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    async def get_entitlement(self, access_token: str, organization_id: UUID) -> dict[str, Any] | None:
        result = await self.client.request(
            'GET', 'organization_entitlements', access_token=access_token,
            params={
                'select': _ENTITLEMENT_SELECT,
                'organization_id': f'eq.{organization_id}',
                'limit': '1',
            },
        )
        return result[0] if result else None

    async def get_plan(self, access_token: str, plan_id: str) -> dict[str, Any] | None:
        result = await self.client.request(
            'GET', 'plans', access_token=access_token,
            params={'select': 'id,name,included_credits,limits,active', 'id': f'eq.{plan_id}', 'limit': '1'},
        )
        return result[0] if result else None

    async def record_event(
        self,
        *,
        organization_id: UUID,
        actor_user_id: UUID | None,
        event_type: str,
        quantity: float,
        credits: float,
        idempotency_key: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        result = await self.client.request(
            'POST', 'rpc/record_usage_event', admin=True,
            json={
                'target_organization_id': str(organization_id),
                'target_actor_user_id': str(actor_user_id) if actor_user_id else None,
                'target_event_type': event_type,
                'target_quantity': quantity,
                'target_credits': credits,
                'target_idempotency_key': idempotency_key,
                'target_metadata': metadata or {},
            },
        )
        return result if isinstance(result, dict) else None

    async def tokens_since(self, organization_id: UUID, since_iso: str) -> int:
        """Total LLM tokens booked by an organization since a timestamp."""
        rows = await self.client.request(
            'GET',
            'usage_events',
            admin=True,
            params={
                'select': 'quantity',
                'organization_id': f'eq.{organization_id}',
                'event_type': 'eq.llm_tokens',
                'created_at': f'gte.{since_iso}',
            },
        )
        return int(sum(float(row['quantity']) for row in rows or []))

    async def list_usage_events(self, access_token: str, organization_id: UUID) -> list[dict[str, Any]]:
        result = await self.client.request(
            'GET', 'usage_events', access_token=access_token,
            params={
                'select': 'event_type,quantity',
                'organization_id': f'eq.{organization_id}',
            },
        )
        return result or []
