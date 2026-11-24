from __future__ import annotations

import logging
import re
from typing import Any
from uuid import UUID

from app.repositories.org_ai import OrgAIRepository
from app.security.secrets import SecretBox, SecretDecryptError

logger = logging.getLogger(__name__)

PROVIDER_ID_PATTERN = re.compile(r'^[a-z0-9][a-z0-9_-]{1,63}$')
MIN_KEY_LENGTH = 8
MAX_KEY_LENGTH = 4096


class InvalidCredential(ValueError):
    pass


class OrgAIService:
    def __init__(self, repository: OrgAIRepository, secret_box: SecretBox | None) -> None:
        self.repository = repository
        self.secret_box = secret_box

    # -- credentials -----------------------------------------------------
    async def list_credentials(
        self, access_token: str, organization_id: UUID
    ) -> list[dict[str, Any]]:
        return await self.repository.list_credentials(access_token, organization_id)

    async def set_credential(
        self,
        access_token: str,
        organization_id: UUID,
        provider_id: str,
        api_key: str,
    ) -> dict[str, Any]:
        if self.secret_box is None:
            raise InvalidCredential(
                'CORTEX_SECRET_KEY is not configured; refusing to store an unencrypted key'
            )
        if not PROVIDER_ID_PATTERN.match(provider_id or ''):
            raise InvalidCredential('invalid provider id')
        key = (api_key or '').strip()
        if not MIN_KEY_LENGTH <= len(key) <= MAX_KEY_LENGTH:
            raise InvalidCredential('api key length is out of range')
        if key.startswith('********'):
            raise InvalidCredential('refusing to store a masked placeholder as a key')

        await self.repository.set_credential(
            access_token,
            organization_id,
            provider_id,
            self.secret_box.encrypt(key),
            key[-4:],
        )
        # The plaintext key is never returned or logged.
        return {'provider_id': provider_id, 'key_last4': key[-4:]}

    async def revoke_credential(
        self, access_token: str, organization_id: UUID, provider_id: str
    ) -> bool:
        return await self.repository.revoke_credential(
            access_token, organization_id, provider_id
        )

    # -- settings --------------------------------------------------------
    async def get_settings(
        self, access_token: str, organization_id: UUID
    ) -> dict[str, Any]:
        return await self.repository.get_settings(access_token, organization_id) or {
            'organization_id': str(organization_id),
            'default_model_id': None,
            'monthly_token_limit': None,
            'credits_per_1k_tokens': None,
        }

    async def update_settings(
        self,
        access_token: str,
        organization_id: UUID,
        *,
        default_model_id: str | None,
        monthly_token_limit: int | None,
        credits_per_1k_tokens: float | None,
    ) -> dict[str, Any]:
        if monthly_token_limit is not None and monthly_token_limit < 0:
            raise InvalidCredential('monthly_token_limit must be positive')
        if credits_per_1k_tokens is not None and credits_per_1k_tokens < 0:
            raise InvalidCredential('credits_per_1k_tokens must be positive')
        await self.repository.set_settings(
            access_token,
            organization_id,
            default_model_id=default_model_id,
            monthly_token_limit=monthly_token_limit,
            credits_per_1k_tokens=credits_per_1k_tokens,
        )
        return await self.get_settings(access_token, organization_id)

    # -- server-side resolution (gateway / runner) -----------------------
    async def settings_for_server(self, organization_id: UUID) -> dict[str, Any]:
        """Settings read with the service role, for gateway-side enforcement."""
        return await self.repository.get_settings_admin(organization_id) or {}

    async def resolve_credentials(self, organization_id: UUID) -> dict[str, str]:
        """Decrypt the organization's provider keys for a server-side call.

        A row that cannot be decrypted is skipped rather than taking the whole
        organization offline; the gateway then reports that provider as
        unconfigured instead of using another tenant's key.
        """
        if self.secret_box is None:
            return {}
        resolved: dict[str, str] = {}
        for row in await self.repository.secrets(organization_id):
            try:
                resolved[row['provider_id']] = self.secret_box.decrypt(row['ciphertext'])
            except SecretDecryptError:
                logger.warning(
                    'organization %s has an undecryptable credential for provider %s',
                    organization_id,
                    row['provider_id'],
                )
        return resolved
