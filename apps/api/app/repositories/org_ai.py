from __future__ import annotations

from typing import Any
from uuid import UUID

from app.database.supabase import SupabaseClient


class OrgAIRepository:
    """Tenant-scoped AI credentials and settings.

    Metadata and settings are read with the caller's JWT so Postgres RLS and the
    definer functions decide access. Ciphertext is read with the service role
    because no client role is allowed to see it.
    """

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    async def list_credentials(
        self, access_token: str, organization_id: UUID
    ) -> list[dict[str, Any]]:
        rows = await self.client.request(
            'POST',
            'rpc/list_organization_ai_credentials',
            access_token=access_token,
            json={'target_organization_id': str(organization_id)},
        )
        return rows or []

    async def set_credential(
        self,
        access_token: str,
        organization_id: UUID,
        provider_id: str,
        ciphertext: str,
        key_last4: str,
    ) -> str:
        return await self.client.request(
            'POST',
            'rpc/set_organization_ai_credential',
            access_token=access_token,
            json={
                'target_organization_id': str(organization_id),
                'target_provider_id': provider_id,
                'target_ciphertext': ciphertext,
                'target_key_last4': key_last4,
            },
        )

    async def revoke_credential(
        self, access_token: str, organization_id: UUID, provider_id: str
    ) -> bool:
        return bool(
            await self.client.request(
                'POST',
                'rpc/revoke_organization_ai_credential',
                access_token=access_token,
                json={
                    'target_organization_id': str(organization_id),
                    'target_provider_id': provider_id,
                },
            )
        )

    async def secrets(self, organization_id: UUID) -> list[dict[str, Any]]:
        rows = await self.client.request(
            'POST',
            'rpc/organization_ai_credential_secrets',
            admin=True,
            json={'target_organization_id': str(organization_id)},
        )
        return rows or []

    async def get_settings(
        self, access_token: str, organization_id: UUID
    ) -> dict[str, Any] | None:
        rows = await self.client.request(
            'GET',
            'organization_ai_settings',
            access_token=access_token,
            params={
                'select': 'organization_id,default_model_id,monthly_token_limit,'
                          'credits_per_1k_tokens,updated_at',
                'organization_id': f'eq.{organization_id}',
                'limit': '1',
            },
        )
        return rows[0] if rows else None

    async def get_settings_admin(self, organization_id: UUID) -> dict[str, Any] | None:
        rows = await self.client.request(
            'GET',
            'organization_ai_settings',
            admin=True,
            params={
                'select': 'organization_id,default_model_id,monthly_token_limit,'
                          'credits_per_1k_tokens',
                'organization_id': f'eq.{organization_id}',
                'limit': '1',
            },
        )
        return rows[0] if rows else None

    async def set_settings(
        self,
        access_token: str,
        organization_id: UUID,
        *,
        default_model_id: str | None,
        monthly_token_limit: int | None,
        credits_per_1k_tokens: float | None,
    ) -> None:
        await self.client.request(
            'POST',
            'rpc/set_organization_ai_settings',
            access_token=access_token,
            json={
                'target_organization_id': str(organization_id),
                'target_default_model_id': default_model_id,
                'target_monthly_token_limit': monthly_token_limit,
                'target_credits_per_1k_tokens': credits_per_1k_tokens,
            },
        )
