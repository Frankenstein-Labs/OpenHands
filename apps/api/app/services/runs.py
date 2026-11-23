from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.repositories.agents import AgentsRepository
from app.repositories.runs import RunsRepository
from app.repositories.usage import UsageRepository
from app.schemas.runs import RunCreate
from app.services.models import ModelsService

CANCELLABLE_STATUSES = {'queued', 'provisioning', 'running', 'waiting'}


class RunNotFound(Exception):
    pass


class InvalidRunState(Exception):
    pass


class RunValidationError(Exception):
    pass


class QuotaExceeded(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class RunsService:
    def __init__(
        self,
        runs: RunsRepository,
        usage: UsageRepository,
        agents: AgentsRepository,
        models: ModelsService,
    ) -> None:
        self.runs = runs
        self.usage = usage
        self.agents = agents
        self.models = models

    async def _enforce_quota(self, access_token: str, organization_id: UUID, budget: float) -> None:
        entitlement = await self.usage.get_entitlement(access_token, organization_id)
        if entitlement is None:
            raise QuotaExceeded('organization has no active entitlement')
        plan = await self.usage.get_plan(access_token, entitlement['plan_id'])
        limits = (plan or {}).get('limits') or {}
        max_concurrent = int(limits.get('max_concurrent_runs', 1))
        active = await self.runs.list_active(access_token, organization_id)
        if len(active) >= max_concurrent:
            raise QuotaExceeded('concurrent run limit reached')
        credits_limit = float(entitlement['credits_limit'])
        credits_used = float(entitlement['credits_used'])
        reserved = sum(float(row.get('credits_reserved') or 0) for row in active)
        if budget > credits_limit - credits_used - reserved:
            raise QuotaExceeded('insufficient credits')

    async def create(self, access_token: str, organization_id: UUID, user_id: str, payload: RunCreate) -> dict[str, Any]:
        if payload.agent_id is not None:
            agent = await self.agents.get(access_token, organization_id, payload.agent_id)
            if agent is None:
                raise RunValidationError('agent not found in organization')
        if payload.model_id is not None and not await self.models.is_available(access_token, payload.model_id):
            raise RunValidationError('model is not available')
        await self._enforce_quota(access_token, organization_id, payload.budget_credits)
        data = payload.model_dump()
        data['agent_id'] = str(payload.agent_id) if payload.agent_id else None
        data['status'] = 'queued'
        data['credits_reserved'] = payload.budget_credits
        return await self.runs.create(access_token, organization_id, user_id, data)

    async def get(self, access_token: str, organization_id: UUID, run_id: UUID) -> dict[str, Any]:
        run = await self.runs.get(access_token, organization_id, run_id)
        if run is None:
            raise RunNotFound
        return run

    async def cancel(self, access_token: str, organization_id: UUID, run_id: UUID) -> dict[str, Any]:
        run = await self.get(access_token, organization_id, run_id)
        if run['status'] not in CANCELLABLE_STATUSES:
            raise InvalidRunState(f"run in status {run['status']} cannot be cancelled")
        finished_at = datetime.now(timezone.utc).isoformat()
        updated = await self.runs.update_status(
            access_token, organization_id, run_id,
            {'status': 'cancelled', 'finished_at': finished_at, 'credits_reserved': 0},
        )
        if updated is None:
            raise RunNotFound
        return updated

    async def events(self, access_token: str, organization_id: UUID, run_id: UUID) -> list[dict[str, Any]]:
        await self.get(access_token, organization_id, run_id)
        return await self.runs.list_events(access_token, organization_id, run_id)
