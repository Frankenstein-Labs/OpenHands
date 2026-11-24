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

    def _headers(self, api_key: str | None = None) -> dict[str, str]:
        headers = {'Content-Type': 'application/json'}
        key = api_key or self.settings.agent_server_api_key
        if key:
            headers['X-Session-API-Key'] = key
        return headers

    def _url(self, path: str, base_url: str | None = None) -> str:
        base = (base_url or self.settings.agent_server_url or '').rstrip('/')
        return f'{base}{path}'

    async def start(
        self,
        *,
        prompt: str,
        model_id: str | None = None,
        title: str | None = None,
        working_dir: str | None = None,
        base_url: str | None = None,
        session_api_key: str | None = None,
        **_: object,
    ) -> dict:
        if not self.configured and not base_url:
            raise RunnerUnavailable('AGENT_SERVER_URL is not configured')
        llm: dict = {}
        model = model_id or self.settings.agent_server_llm_model
        if model:
            llm['model'] = model
        if self.settings.agent_server_llm_base_url:
            llm['base_url'] = self.settings.agent_server_llm_base_url
        if self.settings.agent_server_llm_api_key:
            llm['api_key'] = self.settings.agent_server_llm_api_key
        payload: dict = {
            'initial_message': {
                'role': 'user',
                'content': [{'type': 'text', 'text': prompt}],
                'run': True,
            },
            'worktree': False,
            # The Agent Server answers 422 unless the request carries both an
            # agent configuration and a workspace, so neither is optional here.
            'agent_settings': {'llm': llm} if llm else {},
            'workspace': {
                'kind': 'LocalWorkspace',
                'working_dir': working_dir or self.settings.agent_server_workspace_root,
            },
        }
        if title:
            payload['title'] = title
        response = await self._http().post(
            self._url('/api/conversations', base_url),
            headers=self._headers(session_api_key),
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    async def status(
        self,
        conversation_id: str,
        *,
        base_url: str | None = None,
        session_api_key: str | None = None,
    ) -> dict:
        if not self.configured and not base_url:
            raise RunnerUnavailable('AGENT_SERVER_URL is not configured')
        response = await self._http().get(
            self._url(f'/api/conversations/{conversation_id}', base_url),
            headers=self._headers(session_api_key),
        )
        response.raise_for_status()
        return response.json()

    async def cancel(
        self,
        conversation_id: str,
        *,
        base_url: str | None = None,
        session_api_key: str | None = None,
    ) -> None:
        if not self.configured and not base_url:
            raise RunnerUnavailable('AGENT_SERVER_URL is not configured')
        response = await self._http().post(
            self._url(f'/api/conversations/{conversation_id}/interrupt', base_url),
            headers=self._headers(session_api_key),
        )
        if response.status_code >= 400:
            raise RunnerUnavailable(f'cancel failed with {response.status_code}')

    async def stop_sandbox(self, sandbox: dict | None = None) -> None:
        """The shared runner owns no sandbox."""
        return None

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None
