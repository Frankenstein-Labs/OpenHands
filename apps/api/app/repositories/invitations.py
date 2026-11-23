from __future__ import annotations

from typing import Any
from uuid import UUID

from app.database.supabase import SupabaseClient, SupabaseRequestError

_SELECT = 'id,organization_id,email,role,status,expires_at,created_at'


class InvitationsRepository:
    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    async def create(self, access_token: str, organization_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        result = await self.client.request(
            'POST', 'invitations', access_token=access_token,
            json={**data, 'organization_id': str(organization_id)},
            prefer='return=representation',
        )
        return result[0] if isinstance(result, list) else result

    async def list(self, access_token: str, organization_id: UUID) -> list[dict[str, Any]]:
        result = await self.client.request(
            'GET', 'invitations', access_token=access_token,
            params={
                'select': _SELECT,
                'organization_id': f'eq.{organization_id}',
                'order': 'created_at.desc',
            },
        )
        return result or []

    async def accept(self, access_token: str, token_hash: str) -> Any:
        try:
            return await self.client.rpc(
                'accept_organization_invitation',
                {'invitation_token_hash': token_hash},
                access_token=access_token,
            )
        except SupabaseRequestError as exc:
            # The RPC raises a 22023 (invalid/expired) error that PostgREST reports as 400.
            if exc.status_code == 400:
                return None
            raise
