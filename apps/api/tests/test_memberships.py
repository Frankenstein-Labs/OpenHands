from datetime import datetime, timezone
from uuid import UUID, uuid4

import httpx
import pytest

from app.api.v1.memberships import get_memberships_service
from app.main import app
from app.security.jwt import CurrentUser, get_access_token, get_current_user
from app.services.memberships import MembershipAccessDenied, MembershipNotFound

ORG_ID = uuid4()
OWNER_ID = '11111111-1111-1111-1111-111111111111'
MEMBER_ID = UUID('22222222-2222-2222-2222-222222222222')
NOW = datetime.now(timezone.utc)


def membership(user_id: UUID, role: str):
    return {'organization_id': ORG_ID, 'user_id': user_id, 'role': role, 'created_at': NOW}


class FakeMembershipsService:
    actor_role = 'admin'

    async def list_members(self, token, actor_id, organization_id):
        if self.actor_role == 'none':
            raise MembershipNotFound
        return [membership(UUID(OWNER_ID), 'owner'), membership(MEMBER_ID, 'member')]

    async def add_member(self, token, actor_id, organization_id, user_id, role):
        if self.actor_role not in {'owner', 'admin'}:
            raise MembershipAccessDenied
        if self.actor_role == 'admin' and role.value == 'admin':
            raise MembershipAccessDenied
        return membership(user_id, role.value)

    async def update_role(self, token, actor_id, organization_id, user_id, role):
        if self.actor_role not in {'owner', 'admin'}:
            raise MembershipAccessDenied
        return membership(user_id, role.value)

    async def remove_member(self, token, actor_id, organization_id, user_id):
        if self.actor_role not in {'owner', 'admin'}:
            raise MembershipAccessDenied

    async def transfer_ownership(self, token, actor_id, organization_id, new_owner_user_id):
        if self.actor_role != 'owner':
            raise MembershipAccessDenied
        return membership(new_owner_user_id, 'owner')


@pytest.fixture
def membership_service():
    service = FakeMembershipsService()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=OWNER_ID, role='authenticated', email='user@example.com', claims={}
    )
    app.dependency_overrides[get_access_token] = lambda: 'verified-user-token'
    app.dependency_overrides[get_memberships_service] = lambda: service
    yield service
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_member_list_is_available_only_in_authenticated_tenant(membership_service) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
        response = await client.get(f'/api/v1/organizations/{ORG_ID}/members')

    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_admin_cannot_elevate_member_to_admin(membership_service) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
        response = await client.post(
            f'/api/v1/organizations/{ORG_ID}/members',
            json={'user_id': str(MEMBER_ID), 'role': 'admin'},
        )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_non_member_cannot_list_another_tenant(membership_service) -> None:
    membership_service.actor_role = 'none'
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
        response = await client.get(f'/api/v1/organizations/{ORG_ID}/members')

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_transfer_ownership_requires_owner(membership_service) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
        response = await client.post(
            f'/api/v1/organizations/{ORG_ID}/members/transfer-ownership',
            json={'new_owner_user_id': str(MEMBER_ID)},
        )

    assert response.status_code == 403
