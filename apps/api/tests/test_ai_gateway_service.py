from uuid import uuid4

import pytest

from app.ai_gateway.types import GenerationResult, Usage
from app.schemas.ai_gateway import GenerateIn
from app.services.ai_gateway import AIGatewayService, BudgetExceeded, ModelUnavailable

ORG = uuid4()

PROVIDER_ROW = {'id': 'p1', 'kind': 'openai_compatible', 'enabled': True}
MODEL_ROW = {
    'id': 'm1',
    'provider_id': 'p1',
    'task': 'general',
    'status': 'active',
    'modalities': ['text'],
    'supports_streaming': True,
}


class FakeModelsRepository:
    async def list_providers(self, access_token):
        return [PROVIDER_ROW]

    async def list_models(self, access_token):
        return [MODEL_ROW]


class FakeUsageRepository:
    def __init__(self, limit: float = 100.0, used: float = 0.0) -> None:
        self.entitlement = {'credits_limit': limit, 'credits_used': used}
        self.events: list = []

    async def get_entitlement(self, access_token, organization_id):
        return self.entitlement

    async def record_event(self, **kwargs):
        self.events.append(kwargs)
        return {'id': 'event'}


class StubProvider:
    configured = True

    def __init__(self, result: GenerationResult) -> None:
        self.result = result
        self.calls: list = []

    async def generate(self, request):
        self.calls.append(request)
        return self.result


class StubRegistry:
    def __init__(self, provider: StubProvider) -> None:
        self.provider = provider

    def build_enabled(self, rows):
        return {'p1': self.provider}


def _service(provider: StubProvider, usage: FakeUsageRepository) -> AIGatewayService:
    return AIGatewayService(FakeModelsRepository(), usage, StubRegistry(provider))


@pytest.mark.asyncio
async def test_generate_records_metered_usage() -> None:
    provider = StubProvider(
        GenerationResult(model='m1', content='hello', usage=Usage(input_tokens=10, output_tokens=40))
    )
    usage = FakeUsageRepository()
    service = _service(provider, usage)
    payload = GenerateIn(model_id='m1', messages=[{'role': 'user', 'content': 'hi'}])

    result = await service.generate('token', ORG, 'user-1', payload)

    assert result['content'] == 'hello'
    assert result['credits_charged'] == 0.05
    assert usage.events[0]['event_type'] == 'llm_tokens'
    assert usage.events[0]['quantity'] == 50
    assert usage.events[0]['credits'] == 0.05


@pytest.mark.asyncio
async def test_generate_rejects_exhausted_budget_without_calling_provider() -> None:
    provider = StubProvider(GenerationResult(model='m1', content='x'))
    usage = FakeUsageRepository(limit=10.0, used=10.0)
    service = _service(provider, usage)
    payload = GenerateIn(model_id='m1', messages=[{'role': 'user', 'content': 'hi'}])

    with pytest.raises(BudgetExceeded):
        await service.generate('token', ORG, 'user-1', payload)
    assert provider.calls == []
    assert usage.events == []


@pytest.mark.asyncio
async def test_generate_rejects_max_tokens_above_remaining_credits() -> None:
    provider = StubProvider(GenerationResult(model='m1', content='x'))
    usage = FakeUsageRepository(limit=1.0, used=0.0)
    service = _service(provider, usage)
    payload = GenerateIn(model_id='m1', messages=[{'role': 'user', 'content': 'hi'}], max_tokens=5000)

    with pytest.raises(BudgetExceeded):
        await service.generate('token', ORG, 'user-1', payload)
    assert provider.calls == []


@pytest.mark.asyncio
async def test_generate_rejects_unconfigured_model() -> None:
    provider = StubProvider(GenerationResult(model='m1', content='x'))
    usage = FakeUsageRepository()
    service = _service(provider, usage)
    payload = GenerateIn(model_id='unknown-model', messages=[{'role': 'user', 'content': 'hi'}])

    with pytest.raises(ModelUnavailable):
        await service.generate('token', ORG, 'user-1', payload)
