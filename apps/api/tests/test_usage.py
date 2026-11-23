from uuid import uuid4

import pytest

from app.services.usage import EntitlementNotFound, UsageService


class FakeUsageRepository:
    def __init__(self, entitlement, events=None) -> None:
        self.entitlement = entitlement
        self.events = events or []

    async def get_entitlement(self, access_token, organization_id):
        return self.entitlement

    async def get_plan(self, access_token, plan_id):
        return {'id': plan_id, 'limits': {'max_concurrent_runs': 2}}

    async def list_usage_events(self, access_token, organization_id):
        return self.events


@pytest.mark.asyncio
async def test_summary_aggregates_usage_by_type() -> None:
    org = uuid4()
    repository = FakeUsageRepository(
        {'organization_id': org, 'plan_id': 'free', 'credits_limit': 100, 'credits_used': 30},
        [
            {'event_type': 'tokens', 'quantity': 10},
            {'event_type': 'tokens', 'quantity': 5},
            {'event_type': 'runs', 'quantity': 1},
        ],
    )
    summary = await UsageService(repository).summary('t', org)
    assert summary['by_type'] == {'tokens': 15.0, 'runs': 1.0}
    assert summary['credits_remaining'] == 70.0


@pytest.mark.asyncio
async def test_missing_entitlement_raises() -> None:
    with pytest.raises(EntitlementNotFound):
        await UsageService(FakeUsageRepository(None)).summary('t', uuid4())
