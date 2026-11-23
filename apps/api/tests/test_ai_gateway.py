import json
from decimal import Decimal

import httpx
import pytest

from app.ai_gateway import (
    FrankensteinProvider,
    GenerationRequest,
    Message,
    ModelRouter,
    ModelSpec,
    NoAvailableModel,
    OpenAICompatibleProvider,
    Provider,
    ProviderError,
    ProviderNotConfigured,
    estimate_cost,
)
from app.ai_gateway.types import GenerationResult, Usage


def make_provider(handler, *, base_url='https://llm.test/v1', api_key='secret'):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OpenAICompatibleProvider(base_url=base_url, api_key=api_key, client=client)


def a_request(**overrides):
    return GenerationRequest(model='m', messages=[Message('user', 'hi')], **overrides)


@pytest.mark.asyncio
async def test_generate_parses_content_and_usage() -> None:
    observed = {}

    async def handler(req: httpx.Request) -> httpx.Response:
        observed['url'] = str(req.url)
        observed['auth'] = req.headers.get('authorization')
        observed['body'] = json.loads(req.content)
        return httpx.Response(
            200,
            json={
                'model': 'm',
                'choices': [{'message': {'content': 'hello'}, 'finish_reason': 'stop'}],
                'usage': {'prompt_tokens': 3, 'completion_tokens': 2},
            },
        )

    provider = make_provider(handler)
    result = await provider.generate(a_request())
    await provider.aclose()

    assert result.content == 'hello'
    assert result.usage.total_tokens == 5
    assert observed['url'] == 'https://llm.test/v1/chat/completions'
    assert observed['auth'] == 'Bearer secret'
    assert observed['body']['messages'] == [{'role': 'user', 'content': 'hi'}]


@pytest.mark.asyncio
async def test_retryable_status_is_flagged_retryable() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text='slow down')

    provider = make_provider(handler)
    with pytest.raises(ProviderError) as info:
        await provider.generate(a_request())
    await provider.aclose()

    assert info.value.status_code == 429
    assert info.value.retryable is True


@pytest.mark.asyncio
async def test_unconfigured_provider_is_never_called() -> None:
    provider = OpenAICompatibleProvider(base_url=None)
    with pytest.raises(ProviderNotConfigured):
        await provider.generate(a_request())


@pytest.mark.asyncio
async def test_stream_yields_deltas() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        body = 'data: {"choices":[{"delta":{"content":"He"}}]}\n\n'
        body += 'data: {"choices":[{"delta":{"content":"llo"}}]}\n\n'
        return httpx.Response(200, text=body)

    provider = make_provider(handler)
    chunks = [chunk async for chunk in provider.stream(a_request(stream=True))]
    await provider.aclose()

    assert ''.join(chunks) == 'Hello'


@pytest.mark.asyncio
async def test_embeddings_and_health() -> None:
    async def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith('/embeddings'):
            return httpx.Response(200, json={'data': [{'embedding': [0.1, 0.2]}]})
        return httpx.Response(200, json={'data': []})

    provider = make_provider(handler)
    vectors = await provider.embeddings('m', ['a'])
    healthy = await provider.health()
    await provider.aclose()

    assert vectors == [[0.1, 0.2]]
    assert healthy is True


@pytest.mark.asyncio
async def test_frankenstein_requires_endpoint() -> None:
    provider = FrankensteinProvider(base_url=None)
    with pytest.raises(ProviderNotConfigured):
        await provider.generate(a_request())
    assert await provider.health() is False


class FakeProvider(Provider):
    def __init__(self, name, *, fail=None, configured=True):
        super().__init__(base_url='https://x/v1' if configured else None)
        self.name = name
        self.fail = fail
        self.calls = []

    async def generate(self, request):
        self.calls.append(request.model)
        if self.fail:
            raise self.fail
        return GenerationResult(model=request.model, content=self.name, usage=Usage(1, 1))


@pytest.mark.asyncio
async def test_router_prefers_task_matching_model() -> None:
    providers = {'p1': FakeProvider('p1'), 'p2': FakeProvider('p2')}
    models = {
        'coding/fast': ModelSpec('coding/fast', 'p1', task='coding'),
        'general/ok': ModelSpec('general/ok', 'p2', task='general'),
    }
    result = await ModelRouter(models, providers).generate(a_request(), task='coding')
    assert result.content == 'p1'


@pytest.mark.asyncio
async def test_router_falls_back_on_retryable_error() -> None:
    p1 = FakeProvider('p1', fail=ProviderError('boom', retryable=True))
    p2 = FakeProvider('p2')
    models = {
        'a': ModelSpec('a', 'p1', task='general'),
        'b': ModelSpec('b', 'p2', task='general'),
    }
    result = await ModelRouter(models, {'p1': p1, 'p2': p2}).generate(a_request(), task='general')
    assert result.content == 'p2'
    assert p2.calls == ['b']


@pytest.mark.asyncio
async def test_non_idempotent_request_is_not_retried() -> None:
    p1 = FakeProvider('p1', fail=ProviderError('boom', retryable=True))
    p2 = FakeProvider('p2')
    models = {
        'a': ModelSpec('a', 'p1', task='general'),
        'b': ModelSpec('b', 'p2', task='general'),
    }
    with pytest.raises(ProviderError):
        await ModelRouter(models, {'p1': p1, 'p2': p2}).generate(
            a_request(idempotent=False), task='general'
        )
    assert p2.calls == []


@pytest.mark.asyncio
async def test_router_raises_when_no_provider_configured() -> None:
    models = {'a': ModelSpec('a', 'p1', task='general')}
    with pytest.raises(NoAvailableModel):
        await ModelRouter(models, {'p1': FakeProvider('p1', configured=False)}).generate(a_request())


def test_estimate_cost_uses_declared_pricing() -> None:
    spec = ModelSpec('m', 'p', input_cost_per_1k=0.5, output_cost_per_1k=1.5)
    assert estimate_cost(Usage(1000, 1000), spec) == Decimal('2.000000')
    assert estimate_cost(Usage(5, 5), ModelSpec('m', 'p')) == Decimal('0')
