from __future__ import annotations

from typing import Any
from uuid import UUID

from app.database.supabase import SupabaseRequestError
from app.repositories.agents import AgentsRepository
from app.repositories.runs import RunsRepository
from app.schemas.runs import RunCreate
from app.services.models import ModelsService

CANCELLABLE_STATUSES = {'queued', 'provisioning', 'running', 'waiting'}
QUOTA_MESSAGES = ('insufficient credits', 'concurrent run limit', 'entitlement')


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


def _error_message(exc: SupabaseRequestError) -> str:
    detail = exc.detail
    if isinstance(detail, dict):
        return str(detail.get('message') or detail.get('details') or detail)
    if isinstance(detail, list) and detail and isinstance(detail[0], dict):
        return str(detail[0].get('message') or detail[0])
    return str(detail)


class RunsService:
    def __init__(
        self,
        runs: RunsRepository,
        agents: AgentsRepository,
        models: ModelsService,
    ) -> None:
        self.runs = runs
        self.agents = agents
        self.models = models

    async def create(
        self,
        access_token: str,
        organization_id: UUID,
        user_id: str,
        payload: RunCreate,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if payload.agent_id is not None:
            agent = await self.agents.get(access_token, organization_id, payload.agent_id)
            if agent is None:
                raise RunValidationError('agent not found in organization')
        if payload.model_id is not None and not await self.models.is_available(
            access_token, payload.model_id
        ):
            raise RunValidationError('model is not available')
        try:
            return await self.runs.enqueue(
                access_token,
                organization_id=organization_id,
                agent_id=payload.agent_id,
                model_id=payload.model_id,
                conversation_id=payload.conversation_id,
                prompt=payload.prompt,
                budget_credits=payload.budget_credits,
                idempotency_key=idempotency_key,
                metadata=payload.metadata,
            )
        except SupabaseRequestError as exc:
            message = _error_message(exc)
            if any(fragment in message for fragment in QUOTA_MESSAGES):
                raise QuotaExceeded(message) from exc
            if 'not a member' in message:
                raise RunNotFound from exc
            raise

    async def get(self, access_token: str, organization_id: UUID, run_id: UUID) -> dict[str, Any]:
        run = await self.runs.get(access_token, organization_id, run_id)
        if run is None:
            raise RunNotFound
        return run

    async def cancel(self, access_token: str, organization_id: UUID, run_id: UUID) -> dict[str, Any]:
        run = await self.get(access_token, organization_id, run_id)
        if run['status'] not in CANCELLABLE_STATUSES:
            raise InvalidRunState(f"run in status {run['status']} cannot be cancelled")
        try:
            updated = await self.runs.settle(run_id, 'cancelled', 0)
        except SupabaseRequestError as exc:
            if 'run not found' in _error_message(exc):
                raise RunNotFound from exc
            raise
        if updated is None:
            raise RunNotFound
        return updated

    async def events(self, access_token: str, organization_id: UUID, run_id: UUID) -> list[dict[str, Any]]:
        await self.get(access_token, organization_id, run_id)
        return await self.runs.list_events(access_token, organization_id, run_id)
