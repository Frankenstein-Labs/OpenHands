from datetime import datetime, timezone

import httpx
import pytest

from app.api.v1.profiles import get_profiles_service
from app.main import app
from app.schemas.profiles import ProfileUpdate
from app.security.jwt import CurrentUser, get_access_token, get_current_user
from app.services.profiles import ProfilesService

NOW = datetime.now(timezone.utc)
USER_ID = '11111111-1111-1111-1111-111111111111'


def profile(**overrides):
    base = {
        'id': USER_ID, 'full_name': None, 'avatar_url': None, 'locale': 'en',
        'timezone': 'UTC', 'preferences': {}, 'status': 'active',
        'active_organization_id': None, 'created_at': NOW, 'updated_at': NOW,
    }
    base.update(overrides)
    return base


class FakeProfilesRepository:
    def __init__(self, existing=None):
        self.row = existing

    async def get(self, token, user_id):
        return self.row

    async def insert(self, token, user_id):
        self.row = profile(id=user_id)
        return self.row

    async def patch(self, token, user_id, data):
        self.row = {**(self.row or profile(id=user_id)), **data}
        return self.row


@pytest.mark.asyncio
async def test_get_or_create_inserts_missing_profile() -> None:
    repo = FakeProfilesRepository(existing=None)
    service = ProfilesService(repo)

    result = await service.get_or_create('token', USER_ID)

    assert result['id'] == USER_ID
    assert repo.row is not None


@pytest.mark.asyncio
async def test_update_only_persists_provided_fields() -> None:
    repo = FakeProfilesRepository(existing=profile(full_name='Old'))
    service = ProfilesService(repo)

    result = await service.update('token', USER_ID, ProfileUpdate(timezone='Europe/Paris'))

    assert result['timezone'] == 'Europe/Paris'
    assert result['full_name'] == 'Old'


class FakeProfilesService:
    async def get_or_create(self, token, user_id):
        return profile(full_name='Ada')

    async def update(self, token, user_id, payload):
        return profile(full_name=payload.full_name or 'Ada')


@pytest.fixture
def authenticated_profile_route():
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=USER_ID, role='authenticated', email='a@example.com', claims={}
    )
    app.dependency_overrides[get_access_token] = lambda: 'verified-user-token'
    app.dependency_overrides[get_profiles_service] = lambda: FakeProfilesService()
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_profile_route_returns_profile(authenticated_profile_route) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
        response = await client.get('/api/v1/profile')

    assert response.status_code == 200
    assert response.json()['full_name'] == 'Ada'


@pytest.mark.asyncio
async def test_patch_profile_route_updates(authenticated_profile_route) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
        response = await client.patch('/api/v1/profile', json={'full_name': 'Grace'})

    assert response.status_code == 200
    assert response.json()['full_name'] == 'Grace'


@pytest.mark.asyncio
async def test_profile_route_requires_authentication() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
        response = await client.get('/api/v1/profile')

    assert response.status_code == 401
