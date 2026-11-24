from __future__ import annotations

from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from app.ai_gateway.types import GenerationResult, Usage
from app.schemas.ai_gateway import GenerateIn
from app.security.secrets import SecretBox, SecretBoxUnavailable, SecretDecryptError
from app.services.ai_gateway import AIGatewayService, BudgetExceeded
from app.services.org_ai import InvalidCredential, OrgAIService

ORG = uuid4()


def _box() -> SecretBox:
    return SecretBox(Fernet.generate_key().decode())


class FakeOrgAIRepository:
    def __init__(self) -> None:
        self.stored: list[dict] = []
        self.settings: dict | None = None

    async def list_credentials(self, access_token, organization_id):
        return [
            {'provider_id': row['provider_id'], 'key_last4': row['key_last4']}
            for row in self.stored
        ]

    async def set_credential(self, access_token, organization_id, provider_id, ciphertext, key_last4):
        self.stored.append(
            {
                'provider_id': provider_id,
                'ciphertext': ciphertext,
                'key_last4': key_last4,
            }
        )
        return 'credential-id'

    async def revoke_credential(self, access_token, organization_id, provider_id):
        before = len(self.stored)
        self.stored = [row for row in self.stored if row['provider_id'] != provider_id]
        return len(self.stored) != before

    async def secrets(self, organization_id):
        return [
            {'provider_id': row['provider_id'], 'ciphertext': row['ciphertext']}
            for row in self.stored
        ]

    async def get_settings(self, access_token, organization_id):
        return self.settings

    async def get_settings_admin(self, organization_id):
        return self.settings

    async def set_settings(self, access_token, organization_id, **kwargs):
        self.settings = {'organization_id': str(organization_id), **kwargs}


def test_secret_box_never_stores_the_plaintext() -> None:
    box = _box()
    key = 'sk-live-abcdef123456'

    ciphertext = box.encrypt(key)

    assert ciphertext != key
    assert key not in ciphertext
    assert box.decrypt(ciphertext) == key


def test_secret_box_refuses_to_work_without_a_key() -> None:
    with pytest.raises(SecretBoxUnavailable):
        SecretBox(None)
    with pytest.raises(SecretBoxUnavailable):
        SecretBox('not-a-fernet-key')


def test_a_credential_encrypted_with_another_key_cannot_be_read() -> None:
    ciphertext = _box().encrypt('sk-live-abcdef123456')

    with pytest.raises(SecretDecryptError):
        _box().decrypt(ciphertext)


@pytest.mark.asyncio
async def test_set_credential_encrypts_before_storing() -> None:
    repository = FakeOrgAIRepository()
    service = OrgAIService(repository, _box())

    result = await service.set_credential('token', ORG, 'openai', 'sk-live-abcdef123456')

    stored = repository.stored[0]
    assert 'sk-live-abcdef123456' not in stored['ciphertext']
    assert stored['key_last4'] == '3456'
    assert result == {'provider_id': 'openai', 'key_last4': '3456'}


@pytest.mark.asyncio
async def test_set_credential_refuses_to_store_without_encryption() -> None:
    service = OrgAIService(FakeOrgAIRepository(), None)

    with pytest.raises(InvalidCredential, match='CORTEX_SECRET_KEY'):
        await service.set_credential('token', ORG, 'openai', 'sk-live-abcdef123456')


@pytest.mark.asyncio
async def test_masked_placeholder_and_short_keys_are_rejected() -> None:
    service = OrgAIService(FakeOrgAIRepository(), _box())

    with pytest.raises(InvalidCredential):
        await service.set_credential('token', ORG, 'openai', '**********')
    with pytest.raises(InvalidCredential):
        await service.set_credential('token', ORG, 'openai', 'short')
    with pytest.raises(InvalidCredential):
        await service.set_credential('token', ORG, 'OpenAI Key', 'sk-live-abcdef123456')


@pytest.mark.asyncio
async def test_resolve_credentials_skips_rows_that_cannot_be_decrypted() -> None:
    repository = FakeOrgAIRepository()
    box = _box()
    service = OrgAIService(repository, box)
    await service.set_credential('token', ORG, 'openai', 'sk-live-abcdef123456')
    repository.stored.append(
        {'provider_id': 'openrouter', 'ciphertext': _box().encrypt('sk-or-rotated'), 'key_last4': 'ated'}
    )

    resolved = await service.resolve_credentials(ORG)

    assert resolved == {'openai': 'sk-live-abcdef123456'}


@pytest.mark.asyncio
async def test_resolve_credentials_without_a_key_returns_nothing() -> None:
    service = OrgAIService(FakeOrgAIRepository(), None)

    assert await service.resolve_credentials(ORG) == {}


# -- gateway integration -----------------------------------------------------
class FakeModelsRepository:
    async def list_providers(self, access_token):
        return [{'id': 'p1', 'kind': 'openai_compatible', 'enabled': True}]

    async def list_models(self, access_token):
        return [
            {
                'id': 'm1',
                'provider_id': 'p1',
                'task': 'general',
                'status': 'active',
                'modalities': ['text'],
            }
        ]


class FakeUsageRepository:
    def __init__(self, used_tokens: int = 0) -> None:
        self.used_tokens = used_tokens
        self.events: list = []

    async def get_entitlement(self, access_token, organization_id):
        return {'credits_limit': 100.0, 'credits_used': 0.0}

    async def tokens_since(self, organization_id, since_iso):
        return self.used_tokens

    async def record_event(self, **kwargs):
        self.events.append(kwargs)
        return {'id': 'event'}


class StubProvider:
    configured = True

    async def generate(self, request):
        return GenerationResult(model='m1', content='ok', usage=Usage(input_tokens=10, output_tokens=10))


class RecordingRegistry:
    def __init__(self, provider, credentials=None) -> None:
        self.provider = provider
        self.credentials = dict(credentials or {})
        self.base_urls: dict = {}
        self.timeout = 30.0
        self.client = None
        self.seen_credentials: list[dict] = []

    def build_enabled(self, rows, credentials=None):
        self.seen_credentials.append(dict(credentials if credentials is not None else self.credentials))
        return {'p1': self.provider}


def _gateway(usage, registry, **kwargs) -> AIGatewayService:
    return AIGatewayService(FakeModelsRepository(), usage, registry, **kwargs)


@pytest.mark.asyncio
async def test_gateway_uses_the_organization_key_instead_of_the_deployment_key() -> None:
    registry = RecordingRegistry(StubProvider(), {'p1': 'deployment-key'})
    service = _gateway(
        FakeUsageRepository(),
        registry,
        credential_resolver=lambda organization_id: _resolved({'p1': 'tenant-key'}),
    )
    payload = GenerateIn(model_id='m1', messages=[{'role': 'user', 'content': 'hi'}])

    await service.generate('token', ORG, 'user-1', payload)

    assert registry.seen_credentials[-1] == {'p1': 'tenant-key'}


@pytest.mark.asyncio
async def test_gateway_falls_back_to_the_deployment_key_for_unconfigured_tenants() -> None:
    registry = RecordingRegistry(StubProvider(), {'p1': 'deployment-key'})
    service = _gateway(
        FakeUsageRepository(),
        registry,
        credential_resolver=lambda organization_id: _resolved({}),
    )
    payload = GenerateIn(model_id='m1', messages=[{'role': 'user', 'content': 'hi'}])

    await service.generate('token', ORG, 'user-1', payload)

    assert registry.seen_credentials[-1] == {'p1': 'deployment-key'}


@pytest.mark.asyncio
async def test_gateway_rejects_a_request_over_the_organization_token_ceiling() -> None:
    registry = RecordingRegistry(StubProvider())
    service = _gateway(
        FakeUsageRepository(used_tokens=990),
        registry,
        settings_resolver=lambda organization_id: _resolved(
            {'monthly_token_limit': 1000, 'credits_per_1k_tokens': 2.0}
        ),
    )
    payload = GenerateIn(model_id='m1', messages=[{'role': 'user', 'content': 'hi'}], max_tokens=20)

    with pytest.raises(BudgetExceeded, match='monthly token limit'):
        await service.generate('token', ORG, 'user-1', payload)


@pytest.mark.asyncio
async def test_gateway_charges_the_organization_rate() -> None:
    registry = RecordingRegistry(StubProvider())
    service = _gateway(
        FakeUsageRepository(),
        registry,
        settings_resolver=lambda organization_id: _resolved({'credits_per_1k_tokens': 2.0}),
    )
    payload = GenerateIn(model_id='m1', messages=[{'role': 'user', 'content': 'hi'}])

    result = await service.generate('token', ORG, 'user-1', payload)

    assert result['credits_charged'] == 0.04


async def _resolved(value):
    return value
