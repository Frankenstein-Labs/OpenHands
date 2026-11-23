from __future__ import annotations

from typing import Any
from uuid import UUID

from app.repositories.usage import UsageRepository


class EntitlementNotFound(Exception):
    pass


class UsageService:
    def __init__(self, repository: UsageRepository) -> None:
        self.repository = repository

    async def _entitlement(self, access_token: str, organization_id: UUID) -> dict[str, Any]:
        entitlement = await self.repository.get_entitlement(access_token, organization_id)
        if entitlement is None:
            raise EntitlementNotFound
        return entitlement

    async def summary(self, access_token: str, organization_id: UUID) -> dict[str, Any]:
        entitlement = await self._entitlement(access_token, organization_id)
        events = await self.repository.list_usage_events(access_token, organization_id)
        by_type: dict[str, float] = {}
        for event in events:
            key = event.get('event_type') or 'unknown'
            by_type[key] = by_type.get(key, 0.0) + float(event.get('quantity') or 0)
        credits_limit = float(entitlement['credits_limit'])
        credits_used = float(entitlement['credits_used'])
        return {
            'organization_id': entitlement['organization_id'],
            'plan_id': entitlement['plan_id'],
            'credits_limit': credits_limit,
            'credits_used': credits_used,
            'credits_remaining': credits_limit - credits_used,
            'by_type': by_type,
        }

    async def limits(self, access_token: str, organization_id: UUID) -> dict[str, Any]:
        entitlement = await self._entitlement(access_token, organization_id)
        plan = await self.repository.get_plan(access_token, entitlement['plan_id'])
        credits_limit = float(entitlement['credits_limit'])
        credits_used = float(entitlement['credits_used'])
        return {
            'organization_id': entitlement['organization_id'],
            'plan_id': entitlement['plan_id'],
            'limits': (plan or {}).get('limits') or {},
            'credits_limit': credits_limit,
            'credits_used': credits_used,
            'credits_remaining': credits_limit - credits_used,
        }

    async def entitlement(self, access_token: str, organization_id: UUID) -> dict[str, Any]:
        return await self._entitlement(access_token, organization_id)
