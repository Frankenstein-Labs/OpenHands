from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.database.supabase import SupabaseClient

_INSTALLATION_SELECT = 'id,organization_id,installation_id,account_login,account_type,status,created_at'
_REPOSITORY_SELECT = 'id,organization_id,github_repo_id,full_name,default_branch,status'


class GitHubRepository:
    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    async def create_installation(self, access_token: str, organization_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        result = await self.client.request(
            'POST', 'github_installations', access_token=access_token,
            json={**data, 'organization_id': str(organization_id)},
            prefer='return=representation',
        )
        return result[0] if isinstance(result, list) else result

    async def list_installations(self, access_token: str, organization_id: UUID) -> list[dict[str, Any]]:
        result = await self.client.request(
            'GET', 'github_installations', access_token=access_token,
            params={
                'select': _INSTALLATION_SELECT,
                'organization_id': f'eq.{organization_id}',
                'status': 'eq.active',
                'order': 'created_at.desc',
            },
        )
        return result or []

    async def list_repositories(self, access_token: str, organization_id: UUID) -> list[dict[str, Any]]:
        result = await self.client.request(
            'GET', 'github_repositories', access_token=access_token,
            params={
                'select': _REPOSITORY_SELECT,
                'organization_id': f'eq.{organization_id}',
                'status': 'eq.active',
                'order': 'full_name.asc',
            },
        )
        return result or []

    async def upsert_repositories(
        self,
        access_token: str,
        organization_id: UUID,
        installation_row_id: UUID,
        repositories: list[dict[str, Any]],
    ) -> None:
        if not repositories:
            return
        rows = [
            {
                'organization_id': str(organization_id),
                'installation_id': str(installation_row_id),
                'github_repo_id': repo['id'],
                'full_name': repo['full_name'],
                'default_branch': repo.get('default_branch'),
                'permissions': repo.get('permissions', {}),
                'status': 'active',
            }
            for repo in repositories
        ]
        await self.client.request(
            'POST', 'github_repositories', access_token=access_token,
            params={'on_conflict': 'organization_id,github_repo_id'},
            json=rows,
            prefer='resolution=merge-duplicates',
        )

    async def set_installation_status(self, installation_id: int, status: str) -> None:
        payload: dict[str, Any] = {'status': status}
        if status == 'revoked':
            payload['revoked_at'] = datetime.now(timezone.utc).isoformat()
        await self.client.request(
            'PATCH', 'github_installations', admin=True,
            params={'installation_id': f'eq.{installation_id}'},
            json=payload,
        )

    async def record_webhook_event(self, data: dict[str, Any]) -> dict[str, Any] | None:
        result = await self.client.request(
            'POST', 'github_webhook_events', admin=True,
            params={'on_conflict': 'delivery_id'},
            json=data,
            prefer='resolution=ignore-duplicates,return=representation',
        )
        return result[0] if result else None

    async def update_webhook_event(self, event_id: UUID, status: str) -> None:
        await self.client.request(
            'PATCH', 'github_webhook_events', admin=True,
            params={'id': f'eq.{event_id}'},
            json={'status': status, 'processed_at': datetime.now(timezone.utc).isoformat()},
        )
