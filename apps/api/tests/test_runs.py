from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from app.repositories.runs import ACTIVE_STATUSES
from app.schemas.runs import RunCreate
from app.services.runs import InvalidRunState, QuotaExceeded, RunsService

ORG = uuid4()
USER = '11111111-1111-1111-1111-111111111111'


class FakeRunsRepository:
    def __init__(self) -> None:
        self.rows: dict = {}

    async def create(self, access_token, organization_id, user_id, data):
        row = {
            **data,
            'id': uuid4(),
            'organization_id': organization_id,
            'created_by': UUID(user_id),
            'conversation_id': None,
            'credits_used': 0,
            'error': None,
            'started_at': None,
            'finished_at': None,
            'created_at': datetime.now(timezone.utc),
            'updated_at': datetime.now(timezone.utc),
        }
        self.rows[row['id']] = row
        return row

    async def get(self, access_token, organization_id, run_id):
        return self.rows.get(run_id)

    async def list_active(self, access_token, organization_id):
        return [row for row in self.rows.values() if row['status'] in ACTIVE_STATUSES]

    async def update_status(self, access_token, organization_id, run_id, fields):
        row = self.rows.get(run_id)
        if row is not None:
            row.update(fields)
        return row

    async def list_events(self, access_token, organization_id, run_id):
        return []


class FakeUsageRepository:
    def __init__(self, credits_limit: float, credits_used: float, limits: dict) -> None:
        self.entitlement = {
            'organization_id': ORG,
            'plan_id': 'free',
            'credits_limit': credits_limit,
            'credits_used': credits_used,
        }
        self.limits = limits

    async def get_entitlement(self, access_token, organization_id):
        return self.entitlement

    async def get_plan(self, access_token, plan_id):
        return {'id': plan_id, 'limits': self.limits}

    async def list_usage_events(self, access_token, organization_id):
        return []


class FakeAgentsRepository:
    async def get(self, access_token, organization_id, agent_id):
        return {'id': agent_id}


class FakeModelsService:
    async def is_available(self, access_token, model_id):
        return True


def make_service(credits_limit=100.0, credits_used=0.0, limits=None):
    return RunsService(
        FakeRunsRepository(),
        FakeUsageRepository(credits_limit, credits_used, limits or {'max_concurrent_runs': 5}),
        FakeAgentsRepository(),
        FakeModelsService(),
    )


@pytest.mark.asyncio
async def test_concurrency_limit_is_enforced() -> None:
    service = make_service(limits={'max_concurrent_runs': 1})
    await service.create('t', ORG, USER, RunCreate(prompt='a'))
    with pytest.raises(QuotaExceeded):
        await service.create('t', ORG, USER, RunCreate(prompt='b'))


@pytest.mark.asyncio
async def test_budget_above_remaining_credits_is_rejected() -> None:
    service = make_service(credits_limit=10.0, credits_used=9.0)
    with pytest.raises(QuotaExceeded):
        await service.create('t', ORG, USER, RunCreate(prompt='a', budget_credits=5))


@pytest.mark.asyncio
async def test_cancel_releases_reserved_credits() -> None:
    service = make_service()
    run = await service.create('t', ORG, USER, RunCreate(prompt='a', budget_credits=5))
    cancelled = await service.cancel('t', ORG, run['id'])
    assert cancelled['status'] == 'cancelled'
    assert cancelled['credits_reserved'] == 0


@pytest.mark.asyncio
async def test_cancel_completed_run_raises() -> None:
    service = make_service()
    run = await service.create('t', ORG, USER, RunCreate(prompt='a'))
    await service.runs.update_status('t', ORG, run['id'], {'status': 'completed'})
    with pytest.raises(InvalidRunState):
        await service.cancel('t', ORG, run['id'])
