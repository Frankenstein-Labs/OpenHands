from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.database.supabase import SupabaseRequestError
from app.repositories.runs import ACTIVE_STATUSES
from app.schemas.runs import RunCreate
from app.services.runs import InvalidRunState, QuotaExceeded, RunNotFound, RunsService

ORG = uuid4()
USER = '11111111-1111-1111-1111-111111111111'


class FakeRunsRepository:
    """In-memory stand-in for the SQL admission function.

    The real atomic behaviour is proven against Postgres in
    scripts/supabase-local-run-controls.sql; here the fake mirrors its contract so
    the service mapping and validation can be tested quickly.
    """

    def __init__(self, credits_limit: float = 100.0, credits_used: float = 0.0, max_concurrent: int = 5):
        self.rows: dict = {}
        self.credits_limit = credits_limit
        self.credits_used = credits_used
        self.credits_reserved = 0.0
        self.max_concurrent = max_concurrent
        self.member = True

    def _active(self):
        return [row for row in self.rows.values() if row['status'] in ACTIVE_STATUSES]

    async def enqueue(self, access_token, *, organization_id, agent_id, model_id, conversation_id,
                      prompt, budget_credits, idempotency_key, metadata=None):
        if not self.member:
            raise SupabaseRequestError(403, {'message': 'not a member of this organization'})
        if idempotency_key:
            for row in self.rows.values():
                if row.get('idempotency_key') == idempotency_key:
                    return row
        if len(self._active()) >= self.max_concurrent:
            raise SupabaseRequestError(400, {'message': 'concurrent run limit reached'})
        if self.credits_used + self.credits_reserved + budget_credits > self.credits_limit:
            raise SupabaseRequestError(400, {'message': 'insufficient credits'})
        self.credits_reserved += budget_credits
        row = {
            'id': uuid4(),
            'organization_id': organization_id,
            'agent_id': agent_id,
            'model_id': model_id,
            'conversation_id': conversation_id,
            'prompt': prompt,
            'status': 'queued',
            'budget_credits': budget_credits,
            'credits_reserved': budget_credits,
            'credits_used': 0,
            'created_by': UUID(USER),
            'error': None,
            'metadata': metadata or {},
            'idempotency_key': idempotency_key,
            'started_at': None,
            'finished_at': None,
            'created_at': datetime.now(timezone.utc),
            'updated_at': datetime.now(timezone.utc),
        }
        self.rows[row['id']] = row
        return row

    async def get(self, access_token, organization_id, run_id):
        return self.rows.get(run_id)

    async def settle(self, run_id, status, credits_used, error=None):
        row = self.rows.get(run_id)
        if row is None:
            raise SupabaseRequestError(400, {'message': 'run not found'})
        if row['status'] in ('completed', 'failed', 'cancelled', 'expired'):
            return row
        self.credits_reserved -= row['credits_reserved']
        self.credits_used += credits_used
        row.update(status=status, credits_reserved=0, credits_used=credits_used, error=error)
        return row

    async def list_events(self, access_token, organization_id, run_id):
        return []


class FakeAgentsRepository:
    async def get(self, access_token, organization_id, agent_id):
        return {'id': agent_id}


class FakeModelsService:
    async def is_available(self, access_token, model_id):
        return True


def make_service(**kwargs):
    repo = FakeRunsRepository(**kwargs)
    return RunsService(repo, FakeAgentsRepository(), FakeModelsService()), repo


@pytest.mark.asyncio
async def test_concurrency_limit_is_enforced() -> None:
    service, _ = make_service(max_concurrent=1)
    await service.create('t', ORG, USER, RunCreate(prompt='a'))
    with pytest.raises(QuotaExceeded):
        await service.create('t', ORG, USER, RunCreate(prompt='b'))


@pytest.mark.asyncio
async def test_budget_above_remaining_credits_is_rejected() -> None:
    service, _ = make_service(credits_limit=10.0, credits_used=9.0)
    with pytest.raises(QuotaExceeded):
        await service.create('t', ORG, USER, RunCreate(prompt='a', budget_credits=5))


@pytest.mark.asyncio
async def test_idempotency_key_replays_the_same_run_without_double_reserving() -> None:
    service, repo = make_service()
    first = await service.create('t', ORG, USER, RunCreate(prompt='a', budget_credits=5),
                                 idempotency_key='client-1')
    second = await service.create('t', ORG, USER, RunCreate(prompt='a', budget_credits=5),
                                  idempotency_key='client-1')
    assert first['id'] == second['id']
    assert repo.credits_reserved == 5


@pytest.mark.asyncio
async def test_cancel_refunds_the_reservation() -> None:
    service, repo = make_service()
    run = await service.create('t', ORG, USER, RunCreate(prompt='a', budget_credits=5))
    assert repo.credits_reserved == 5
    cancelled = await service.cancel('t', ORG, run['id'])
    assert cancelled['status'] == 'cancelled'
    assert cancelled['credits_reserved'] == 0
    assert repo.credits_reserved == 0
    assert repo.credits_used == 0


@pytest.mark.asyncio
async def test_cancel_completed_run_raises() -> None:
    service, repo = make_service()
    run = await service.create('t', ORG, USER, RunCreate(prompt='a'))
    repo.rows[run['id']]['status'] = 'completed'
    with pytest.raises(InvalidRunState):
        await service.cancel('t', ORG, run['id'])


@pytest.mark.asyncio
async def test_non_member_is_reported_as_not_found() -> None:
    service, repo = make_service()
    repo.member = False
    with pytest.raises(RunNotFound):
        await service.create('t', ORG, USER, RunCreate(prompt='a'))


def test_zero_budget_is_rejected_by_the_schema() -> None:
    with pytest.raises(ValidationError):
        RunCreate(prompt='a', budget_credits=0)
