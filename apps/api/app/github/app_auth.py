from __future__ import annotations

import time
from typing import Any

import httpx
import jwt


class GitHubNotConfigured(RuntimeError):
    pass


class GitHubError(RuntimeError):
    pass


def build_app_jwt(app_id: str, private_key: str, *, now: int | None = None) -> str:
    issued_at = int(now if now is not None else time.time())
    payload = {'iat': issued_at - 60, 'exp': issued_at + 540, 'iss': str(app_id)}
    return jwt.encode(payload, private_key, algorithm='RS256')


class GitHubAppClient:
    def __init__(
        self,
        app_id: str,
        private_key: str,
        *,
        base_url: str = 'https://api.github.com',
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.app_id = app_id
        self.private_key = private_key
        self.base_url = base_url.rstrip('/')
        self.client = client or httpx.AsyncClient(timeout=20.0)

    def _app_headers(self) -> dict[str, str]:
        return {
            'Authorization': f'Bearer {build_app_jwt(self.app_id, self.private_key)}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
        }

    async def _request(self, method: str, path: str, *, headers: dict[str, str]) -> Any:
        try:
            response = await self.client.request(method, f'{self.base_url}{path}', headers=headers)
        except httpx.HTTPError as exc:
            raise GitHubError('GitHub is unavailable') from exc
        if response.is_error:
            raise GitHubError(f'GitHub returned {response.status_code}')
        if not response.content:
            return None
        return response.json()

    async def get_installation(self, installation_id: int) -> dict[str, Any]:
        return await self._request('GET', f'/app/installations/{installation_id}', headers=self._app_headers())

    async def create_installation_token(self, installation_id: int) -> str:
        data = await self._request(
            'POST', f'/app/installations/{installation_id}/access_tokens', headers=self._app_headers()
        )
        return data['token']

    async def list_installation_repositories(self, installation_id: int) -> list[dict[str, Any]]:
        token = await self.create_installation_token(installation_id)
        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
        }
        data = await self._request('GET', '/installation/repositories', headers=headers)
        return data.get('repositories', []) if data else []
