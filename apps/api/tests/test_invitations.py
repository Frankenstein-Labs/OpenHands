import hashlib
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.schemas.invitations import InvitationCreate
from app.services.invitations import InvitationError, InvitationsService

ORG = uuid4()
USER = '11111111-1111-1111-1111-111111111111'


class FakeInvitationsRepository:
    def __init__(self) -> None:
        self.stored_hash: str | None = None

    async def create(self, access_token, organization_id, data):
        self.stored_hash = data['token_hash']
        return {
            'id': uuid4(),
            'organization_id': organization_id,
            'email': data['email'],
            'role': data['role'],
            'status': data['status'],
            'expires_at': data['expires_at'],
            'created_at': datetime.now(timezone.utc),
        }

    async def list(self, access_token, organization_id):
        return []

    async def accept(self, access_token, token_hash):
        expected = hashlib.sha256(b'valid-token-value').hexdigest()
        if token_hash == expected:
            return {'organization_id': ORG, 'role': 'member'}
        return None


@pytest.mark.asyncio
async def test_create_stores_hash_not_raw_token() -> None:
    repository = FakeInvitationsRepository()
    service = InvitationsService(repository)
    result = await service.create(
        't', ORG, USER, InvitationCreate(email='A@Example.com', role='member')
    )
    assert result['email'] == 'a@example.com'
    assert repository.stored_hash == hashlib.sha256(result['token'].encode()).hexdigest()
    assert repository.stored_hash != result['token']


def test_owner_role_is_rejected_by_schema() -> None:
    with pytest.raises(ValueError):
        InvitationCreate(email='a@example.com', role='owner')


@pytest.mark.asyncio
async def test_accept_invalid_token_raises() -> None:
    service = InvitationsService(FakeInvitationsRepository())
    with pytest.raises(InvitationError):
        await service.accept('t', 'bogus')


@pytest.mark.asyncio
async def test_accept_valid_token_returns_membership() -> None:
    service = InvitationsService(FakeInvitationsRepository())
    result = await service.accept('t', 'valid-token-value')
    assert result == {'organization_id': ORG, 'role': 'member'}
