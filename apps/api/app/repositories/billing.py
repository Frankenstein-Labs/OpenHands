from __future__ import annotations

from typing import Any
from uuid import UUID

from app.database.supabase import SupabaseClient


class BillingRepository:
    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    async def list_plans(self, access_token: str) -> list[dict[str, Any]]:
        result = await self.client.request(
            'GET', 'plans', access_token=access_token,
            params={
                'select': 'id,name,included_credits,limits,active',
                'active': 'eq.true',
                'order': 'included_credits.asc',
            },
        )
        return result or []

    async def get_subscription(self, access_token: str, organization_id: UUID) -> dict[str, Any] | None:
        result = await self.client.request(
            'GET', 'billing_subscriptions', access_token=access_token,
            params={
                'select': 'organization_id,plan_id,status,provider,current_period_end',
                'organization_id': f'eq.{organization_id}',
                'limit': '1',
            },
        )
        return result[0] if result else None

    async def list_invoices(self, access_token: str, organization_id: UUID) -> list[dict[str, Any]]:
        result = await self.client.request(
            'GET', 'billing_invoices', access_token=access_token,
            params={
                'select': 'id,organization_id,provider,amount_cents,currency,status,hosted_url,created_at',
                'organization_id': f'eq.{organization_id}',
                'order': 'created_at.desc',
            },
        )
        return result or []
