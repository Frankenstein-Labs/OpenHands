from __future__ import annotations

import httpx

from app.core.config import Settings, get_settings


class RunnerUnavailable(RuntimeError):
    """Raised when no Agent Server is configured or reachable."""


class AgentServerRunner:
    """Thin client for the OpenHands Agent Server conversation API.

    The runner never executes user commands itself: it asks the Agent Server to
    create an isolated conversation and reports back its status.
    """

    def __init__(self, settings: Settings | None = None, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = client
        self._owns_client = client is None

    @property
    def configured(self) -> bool:
        return bool(self.settings.agent_server_url)

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.settings.agent_server_timeout_seconds)
        return self._client

    def _headers(self) -> dict[str, str]:
        headers = {'Content-Type': 'application/json'}
        if self.settings.agent_server_api_key:
            headers['X-Session-API-Key'] = self.settings.agent_server_api_key
        return headers

    def _url(self, path: str) -> str:
        base = (self.settings.agent_server_url or '').rstrip('/')
        return f'{base}{path}'

    async def start(
        self,
        *,
        prompt: str,
        model_id: str | None = None,
        title: str | None = None,
        working_dir: str | None = None,
    ) -> dict:
        if not self.configured:
            raise RunnerUnavailable('AGENT_SERVER_URL is not configured')
        payload: dict = {
            'initial_message': {
                'role': 'user',
                'content': [{'type': 'text', 'text': prompt}],
                'run': True,
            },
            'worktree': False,
        }
        if title:
            payload['title'] = title
        if model_id:
            payload['agent_settings'] = {'llm': {'model': model_id}}
        if working_dir:
            payload['workspace'] = {'kind': 'LocalWorkspace', 'working_dir': working_dir}
        response = await self._http().post(
            self._url('/api/conversations'), headers=self._headers(), json=payload
        )
        response.raise_for_status()
        return response.json()

    async def status(self, conversation_id: str) -> dict:
        if not self.configured:
            raise RunnerUnavailable('AGENT_SERVER_URL is not configured')
        response = await self._http().get(
            self._url(f'/api/conversations/{conversation_id}'), headers=self._headers()
        )
        response.raise_for_status()
        return response.json()

    async def cancel(self, conversation_id: str) -> None:
        if not self.configured:
            raise RunnerUnavailable('AGENT_SERVER_URL is not configured')
        response = await self._http().post(
            self._url(f'/api/conversations/{conversation_id}/stop'), headers=self._headers()
        )
        if response.status_code >= 400:
            raise RunnerUnavailable(f'cancel failed with {response.status_code}')

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None
