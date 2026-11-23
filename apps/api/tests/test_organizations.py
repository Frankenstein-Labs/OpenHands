from datetime import datetime, timezone
from uuid import UUID, uuid4

import httpx
import pytest

from app.api.v1.organizations import get_organizations_service
from app.main import app
from app.security.jwt import CurrentUser, get_access_token, get_current_user
from app.services.organizations import OrganizationNotFound

ORG_ID = uuid4()
ORG = {
    'id': ORG_ID,
    'slug': 'acme-team',
    'name': 'Acme Team',
    'created_by': UUID('11111111-1111-1111-1111-111111111111'),
    'created_at': datetime.now(timezone.utc),
    'updated_at': datetime.now(timezone.utc),
}


class FakeOrganizationsService:
    async def list_organizations(self, access_token: str):
        assert access_token == 'verified-user-token'
        return [ORG]

    async def create_organization(self, access_token: str, payload):
        assert access_token == 'verified-user-token'
        return {**ORG, 'slug': payload.slug, 'name': payload.name}

    async def get_organization(self, access_token: str, organization_id: UUID):
        if organization_id != ORG_ID:
            raise OrganizationNotFound
        return ORG

    async def update_organization(self, access_token: str, organization_id: UUID, payload):
        if organization_id != ORG_ID:
            raise OrganizationNotFound
        return {**ORG, 'name': payload.name}


@pytest.fixture(autouse=True)
def authenticated_dependencies():
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id='11111111-1111-1111-1111-111111111111', role='authenticated', email='user@example.com', claims={}
    )
    app.dependency_overrides[get_access_token] = lambda: 'verified-user-token'
    app.dependency_overrides[get_organizations_service] = lambda: FakeOrganizationsService()
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_organizations_uses_authenticated_tenant_context() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
        response = await client.get('/api/v1/organizations')

    assert response.status_code == 200
    assert response.json()[0]['slug'] == 'acme-team'


@pytest.mark.asyncio
async def test_other_tenant_resource_is_not_found() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
        response = await client.get('/api/v1/organizations/22222222-2222-2222-2222-222222222222')

    assert response.status_code == 404
    assert response.json()['detail'] == 'Organization not found'


@pytest.mark.asyncio
async def test_create_organization_validates_and_delegates_to_service() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
        response = await client.post('/api/v1/organizations', json={'slug': 'new-team', 'name': 'New Team'})

    assert response.status_code == 201
    assert response.json()['name'] == 'New Team'
