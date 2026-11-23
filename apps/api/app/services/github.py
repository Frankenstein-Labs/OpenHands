from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from app.github.webhooks import verify_webhook_signature
from app.repositories.github import GitHubRepository


class GitHubNotLinked(Exception):
    pass


class GitHubAppClientProtocol(Protocol):
    async def get_installation(self, installation_id: int) -> dict[str, Any]: ...
    async def list_installation_repositories(self, installation_id: int) -> list[dict[str, Any]]: ...


class GitHubService:
    def __init__(
        self,
        repository: GitHubRepository,
        app_client: GitHubAppClientProtocol,
        webhook_secret: str | None,
    ) -> None:
        self.repository = repository
        self.app_client = app_client
        self.webhook_secret = webhook_secret or ''

    async def link_installation(
        self, access_token: str, organization_id: UUID, installation_id: int
    ) -> dict[str, Any]:
        installation = await self.app_client.get_installation(installation_id)
        account = installation.get('account', {}) if isinstance(installation, dict) else {}
        row = await self.repository.create_installation(
            access_token, organization_id,
            {
                'installation_id': installation_id,
                'account_login': account.get('login', 'unknown'),
                'account_type': account.get('type'),
                'status': 'active',
            },
        )
        repositories = await self.app_client.list_installation_repositories(installation_id)
        await self.repository.upsert_repositories(access_token, organization_id, row['id'], repositories)
        return row

    async def list_installations(self, access_token: str, organization_id: UUID) -> list[dict[str, Any]]:
        return await self.repository.list_installations(access_token, organization_id)

    async def list_repositories(self, access_token: str, organization_id: UUID) -> list[dict[str, Any]]:
        return await self.repository.list_repositories(access_token, organization_id)

    async def handle_webhook(
        self,
        event_name: str,
        delivery_id: str,
        raw_body: bytes,
        payload: dict[str, Any],
        signature: str | None,
    ) -> dict[str, str]:
        verify_webhook_signature(self.webhook_secret, raw_body, signature)
        event = await self.repository.record_webhook_event(
            {
                'delivery_id': delivery_id,
                'event_name': event_name,
                'payload': payload,
                'status': 'received',
            }
        )
        if event is None:
            return {'status': 'duplicate'}
        status = 'ignored'
        if event_name == 'installation':
            action = payload.get('action')
            installation_id = (payload.get('installation') or {}).get('id')
            new_status = {
                'deleted': 'revoked',
                'suspended': 'suspended',
                'unsuspended': 'active',
            }.get(action)
            if installation_id and new_status:
                await self.repository.set_installation_status(installation_id, new_status)
                status = 'processed'
        await self.repository.update_webhook_event(event['id'], status)
        return {'status': status}
