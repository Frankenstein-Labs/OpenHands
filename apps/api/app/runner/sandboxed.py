from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from uuid import UUID

import httpx

from app.core.config import Settings, get_settings
from app.runner.agent_server import AgentServerRunner
from app.sandbox.base import (
    Sandbox,
    SandboxError,
    SandboxLimits,
    SandboxProvider,
    SandboxSpec,
)
from app.sandbox.docker import DockerSandboxProvider

logger = logging.getLogger(__name__)


class SandboxedAgentServerRunner:
    """Runs every agent conversation inside its own container.

    The runner does not implement isolation itself: it asks the sandbox
    provider for a container, waits for the Agent Server inside it to answer,
    and then talks to that server only. When anything fails, the container is
    removed so a broken run cannot leave a sandbox behind.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        provider: SandboxProvider | None = None,
        agent: AgentServerRunner | None = None,
        ready_probe: Callable[[Sandbox], Awaitable[None]] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.provider = provider or DockerSandboxProvider(
            workspace_root=self.settings.sandbox_workspace_root,
            network=self.settings.sandbox_network,
            agent_server_port=self.settings.sandbox_agent_port,
        )
        self.agent = agent or AgentServerRunner(self.settings)
        self._ready_probe = ready_probe or self._wait_until_ready

    def _limits(self) -> SandboxLimits:
        return SandboxLimits(
            cpus=self.settings.sandbox_cpus,
            memory_mb=self.settings.sandbox_memory_mb,
            pids=self.settings.sandbox_pids,
            disk_mb=self.settings.sandbox_disk_mb,
            timeout_seconds=self.settings.sandbox_timeout_seconds,
        )

    async def start(
        self,
        *,
        prompt: str,
        model_id: str | None = None,
        title: str | None = None,
        working_dir: str | None = None,
        run_id: str | None = None,
        organization_id: str | None = None,
        **_: object,
    ) -> dict:
        if not run_id or not organization_id:
            raise SandboxError('a sandboxed run needs a run_id and an organization_id')

        spec = SandboxSpec(
            organization_id=UUID(str(organization_id)),
            run_id=UUID(str(run_id)),
            image=self.settings.sandbox_image,
            limits=self._limits(),
            network=self.settings.sandbox_network,
        )
        sandbox = await self.provider.provision(spec)
        try:
            await self._ready_probe(sandbox)
            conversation = await self.agent.start(
                prompt=prompt,
                model_id=model_id,
                title=title,
                # The workspace root of the container is the bind-mounted run
                # directory, so the agent can only see its own files.
                working_dir=working_dir or '/workspace',
                base_url=sandbox.api_url,
                session_api_key=sandbox.session_api_key,
            )
        except Exception:
            await self.provider.stop(sandbox)
            raise

        return {
            **conversation,
            'sandbox': {
                'id': sandbox.id,
                'workspace': sandbox.workspace,
                'api_url': sandbox.api_url,
                'image': sandbox.image,
                'session_api_key': sandbox.session_api_key,
                'run_id': str(sandbox.run_id),
                'organization_id': str(sandbox.organization_id),
            },
        }

    async def _wait_until_ready(self, sandbox: Sandbox) -> None:
        if not sandbox.api_url:
            raise SandboxError('sandbox has no reachable address')
        deadline = asyncio.get_running_loop().time() + self.settings.sandbox_ready_timeout_seconds
        headers = {}
        key = sandbox.session_api_key or self.settings.agent_server_api_key
        if key:
            headers['X-Session-API-Key'] = key
        async with httpx.AsyncClient(timeout=5.0) as client:
            while True:
                try:
                    response = await client.get(
                        f'{sandbox.api_url}/health',
                        params={'limit': '1'},
                        headers=headers,
                    )
                    if response.status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                if asyncio.get_running_loop().time() >= deadline:
                    raise SandboxError(
                        f'sandbox {sandbox.run_id} did not become ready in time'
                    )
                await asyncio.sleep(1.0)

    async def status(
        self,
        conversation_id: str,
        *,
        base_url: str | None = None,
        session_api_key: str | None = None,
    ) -> dict:
        return await self.agent.status(
            conversation_id, base_url=base_url, session_api_key=session_api_key
        )

    async def cancel(
        self,
        conversation_id: str,
        *,
        base_url: str | None = None,
        session_api_key: str | None = None,
    ) -> None:
        await self.agent.cancel(
            conversation_id, base_url=base_url, session_api_key=session_api_key
        )

    async def enforce_limits(self, sandbox: dict | None = None) -> None:
        if not sandbox or not hasattr(self.provider, 'enforce_disk_limit'):
            return
        await self.provider.enforce_disk_limit(
            self._sandbox_from(sandbox), self.settings.sandbox_disk_mb
        )

    async def stop_sandbox(self, sandbox: dict | None = None) -> None:
        if not sandbox:
            return
        try:
            await self.provider.stop(self._sandbox_from(sandbox))
        except Exception:  # pragma: no cover - cleanup must never mask the run result
            logger.warning('failed to stop sandbox %s', sandbox.get('id'), exc_info=True)

    @staticmethod
    def _sandbox_from(sandbox: dict) -> Sandbox:
        return Sandbox(
            id=sandbox['id'],
            run_id=UUID(str(sandbox['run_id'])),
            organization_id=UUID(str(sandbox['organization_id'])),
            workspace=sandbox['workspace'],
            api_url=sandbox.get('api_url'),
            image=sandbox.get('image') or '',
            session_api_key=sandbox.get('session_api_key'),
        )

    async def aclose(self) -> None:
        await self.agent.aclose()
        await self.provider.aclose()


def build_runner(settings: Settings | None = None):
    """Pick the runner the deployment is configured for."""
    settings = settings or get_settings()
    if settings.sandbox_provider == 'docker':
        return SandboxedAgentServerRunner(settings)
    return AgentServerRunner(settings)
