import hashlib
import hmac
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.github.app_auth import build_app_jwt
from app.github.webhooks import WebhookSignatureError, verify_webhook_signature
from app.services.github import GitHubService

ORG = uuid4()


class FakeGitHubRepository:
    def __init__(self) -> None:
        self.installations: list = []
        self.repositories: list = []
        self.events: dict = {}
        self.status_updates: list = []
        self.event_status: list = []

    async def create_installation(self, access_token, organization_id, data):
        row = {
            'id': uuid4(),
            'organization_id': organization_id,
            **data,
            'created_at': datetime.now(timezone.utc),
        }
        self.installations.append(row)
        return row

    async def list_installations(self, access_token, organization_id):
        return self.installations

    async def list_repositories(self, access_token, organization_id):
        return self.repositories

    async def upsert_repositories(self, access_token, organization_id, installation_row_id, repositories):
        for repo in repositories:
            self.repositories.append(
                {
                    'id': uuid4(),
                    'organization_id': organization_id,
                    'github_repo_id': repo['id'],
                    'full_name': repo['full_name'],
                    'default_branch': repo.get('default_branch'),
                    'status': 'active',
                }
            )

    async def set_installation_status(self, installation_id, status):
        self.status_updates.append((installation_id, status))

    async def record_webhook_event(self, data):
        if data['delivery_id'] in self.events:
            return None
        row = {'id': uuid4(), **data}
        self.events[data['delivery_id']] = row
        return row

    async def update_webhook_event(self, event_id, status):
        self.event_status.append((event_id, status))


class FakeAppClient:
    async def get_installation(self, installation_id):
        return {'account': {'login': 'acme', 'type': 'Organization'}}

    async def list_installation_repositories(self, installation_id):
        return [{'id': 101, 'full_name': 'acme/repo', 'default_branch': 'main', 'permissions': {}}]


@pytest.mark.asyncio
async def test_link_installation_stores_installation_and_repositories() -> None:
    repository = FakeGitHubRepository()
    service = GitHubService(repository, FakeAppClient(), webhook_secret='secret')
    row = await service.link_installation('t', ORG, 55)
    assert row['account_login'] == 'acme'
    assert repository.repositories[0]['full_name'] == 'acme/repo'


def test_build_app_jwt_uses_rs256_and_issuer() -> None:
    import jwt
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    token = build_app_jwt('123', pem, now=1_700_000_000)
    assert jwt.get_unverified_header(token)['alg'] == 'RS256'
    claims = jwt.decode(token, key.public_key(), algorithms=['RS256'], options={'verify_exp': False})
    assert claims['iss'] == '123'


def test_verify_webhook_signature_rejects_tampering() -> None:
    body = b'{"action":"deleted"}'
    signature = 'sha256=' + hmac.new(b'secret', body, hashlib.sha256).hexdigest()
    verify_webhook_signature('secret', body, signature)
    with pytest.raises(WebhookSignatureError):
        verify_webhook_signature('secret', body, 'sha256=deadbeef')


def _signature(body: bytes, secret: str = 'secret') -> str:
    return 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_installation_webhook_revokes_linked_installation() -> None:
    repository = FakeGitHubRepository()
    service = GitHubService(repository, FakeAppClient(), webhook_secret='secret')
    body = b'{"action":"deleted","installation":{"id":55}}'
    payload = {'action': 'deleted', 'installation': {'id': 55}}
    result = await service.handle_webhook('installation', 'delivery-1', body, payload, _signature(body))
    assert result == {'status': 'processed'}
    assert repository.status_updates == [(55, 'revoked')]
    assert repository.event_status[-1][1] == 'processed'


@pytest.mark.asyncio
async def test_duplicate_webhook_delivery_is_ignored() -> None:
    repository = FakeGitHubRepository()
    service = GitHubService(repository, FakeAppClient(), webhook_secret='secret')
    body = b'{"action":"suspended","installation":{"id":55}}'
    payload = {'action': 'suspended', 'installation': {'id': 55}}
    await service.handle_webhook('installation', 'delivery-2', body, payload, _signature(body))
    result = await service.handle_webhook('installation', 'delivery-2', body, payload, _signature(body))
    assert result == {'status': 'duplicate'}
    assert repository.status_updates == [(55, 'suspended')]


@pytest.mark.asyncio
async def test_webhook_with_bad_signature_is_rejected_before_storage() -> None:
    repository = FakeGitHubRepository()
    service = GitHubService(repository, FakeAppClient(), webhook_secret='secret')
    body = b'{"action":"deleted"}'
    with pytest.raises(WebhookSignatureError):
        await service.handle_webhook(
            'installation', 'delivery-3', body, {'action': 'deleted'}, 'sha256=deadbeef'
        )
    assert repository.events == {}
