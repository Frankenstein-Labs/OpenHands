from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.database.supabase import SupabaseClient

_SELECT = (
    'id,organization_id,created_by,bucket,object_path,mime_type,size_bytes,'
    'checksum,status,metadata,created_at'
)


class FilesRepository:
    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    async def create(self, access_token: str, organization_id: UUID, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
        result = await self.client.request(
            'POST', 'files', access_token=access_token,
            json={**data, 'organization_id': str(organization_id), 'created_by': user_id},
            prefer='return=representation',
        )
        return result[0] if isinstance(result, list) else result

    async def list(self, access_token: str, organization_id: UUID) -> list[dict[str, Any]]:
        result = await self.client.request(
            'GET', 'files', access_token=access_token,
            params={
                'select': _SELECT,
                'organization_id': f'eq.{organization_id}',
                'status': 'neq.deleted',
                'order': 'created_at.desc',
            },
        )
        return result or []

    async def get(self, access_token: str, organization_id: UUID, file_id: UUID) -> dict[str, Any] | None:
        result = await self.client.request(
            'GET', 'files', access_token=access_token,
            params={
                'select': _SELECT,
                'id': f'eq.{file_id}',
                'organization_id': f'eq.{organization_id}',
                'limit': '1',
            },
        )
        return result[0] if result else None

    async def mark_deleted(self, access_token: str, organization_id: UUID, file_id: UUID) -> dict[str, Any] | None:
        result = await self.client.request(
            'PATCH', 'files', access_token=access_token,
            params={'id': f'eq.{file_id}', 'organization_id': f'eq.{organization_id}'},
            json={'status': 'deleted', 'deleted_at': datetime.now(timezone.utc).isoformat()},
            prefer='return=representation',
        )
        return result[0] if result else None
