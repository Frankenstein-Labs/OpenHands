import httpx
import pytest

from app.api.v1.models import get_models_service
from app.main import app
from app.security.jwt import CurrentUser, get_access_token, get_current_user
from app.services.models import ModelsService


def model(model_id, provider_id, status='active', **overrides):
    base = {
        'id': model_id, 'provider_id': provider_id, 'display_name': model_id,
        'description': None, 'task': 'general', 'modalities': ['text'],
        'context_window': 4096, 'max_output_tokens': None, 'supports_tools': True,
        'supports_streaming': True, 'supports_vision': False, 'supports_embeddings': False,
        'input_cost_per_1k': None, 'output_cost_per_1k': None, 'currency': 'USD',
        'status': status, 'limits': {}, 'capabilities': {},
    }
    base.update(overrides)
    return base


class FakeModelsRepository:
    def __init__(self, providers, models):
        self.providers = providers
        self.models = models

    async def list_providers(self, token):
        return self.providers

    async def list_models(self, token):
        return self.models

    async def get_model(self, token, model_id):
        return next((m for m in self.models if m['id'] == model_id), None)


def repository():
    providers = [
        {'id': 'enabled', 'name': 'Enabled', 'kind': 'openai_compatible', 'base_url': None,
         'enabled': True, 'capabilities': {}},
        {'id': 'disabled', 'name': 'Disabled', 'kind': 'openrouter', 'base_url': None,
         'enabled': False, 'capabilities': {}},
    ]
    models = [
        model('enabled/active', 'enabled', 'active'),
        model('enabled/preview', 'enabled', 'preview'),
        model('disabled/active', 'disabled', 'active'),
    ]
    return FakeModelsRepository(providers, models)


@pytest.mark.asyncio
async def test_only_active_model_on_enabled_provider_is_available() -> None:
    service = ModelsService(repository())

    available = await service.list_available('token')

    assert [m['id'] for m in available] == ['enabled/active']
    assert available[0]['available'] is True


@pytest.mark.asyncio
async def test_catalogue_lists_every_model_with_status_flags() -> None:
    service = ModelsService(repository())

    models = await service.list_models('token')

    by_id = {m['id']: m for m in models}
    assert by_id['enabled/preview']['available'] is False
    assert by_id['disabled/active']['provider_enabled'] is False


@pytest.mark.asyncio
async def test_is_available_rejects_preview_model() -> None:
    service = ModelsService(repository())

    assert await service.is_available('token', 'enabled/active') is True
    assert await service.is_available('token', 'enabled/preview') is False
    assert await service.is_available('token', 'missing') is False


class FakeModelsRouteService:
    async def list_available(self, token):
        return [model('enabled/active', 'enabled')]

    async def list_providers(self, token):
        return [{'id': 'enabled', 'name': 'Enabled', 'kind': 'openai_compatible',
                 'base_url': None, 'enabled': True, 'capabilities': {}}]


@pytest.fixture
def models_route():
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id='u1', role='authenticated', email=None, claims={}
    )
    app.dependency_overrides[get_access_token] = lambda: 'verified-user-token'
    app.dependency_overrides[get_models_service] = lambda: FakeModelsRouteService()
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_available_models_route(models_route) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
        response = await client.get('/api/v1/models/available')

    assert response.status_code == 200
    assert response.json()[0]['id'] == 'enabled/active'
