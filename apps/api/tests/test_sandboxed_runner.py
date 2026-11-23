from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.core.config import Settings
from app.runner.sandboxed import SandboxedAgentServerRunner
from app.sandbox.base import Sandbox, SandboxError, SandboxSpec

RUN_ID = uuid4()
ORG_ID = uuid4()


class FakeProvider:
    def __init__(self, api_url: str | None = 'http://10.0.0.2:8001') -> None:
        self.api_url = api_url
        self.specs: list[SandboxSpec] = []
        self.stopped: list[Sandbox] = []
        self.enforced: list[tuple[Sandbox, int]] = []

    async def provision(self, spec: SandboxSpec) -> Sandbox:
        self.specs.append(spec)
        return Sandbox(
            id='container-1',
            run_id=spec.run_id,
            organization_id=spec.organization_id,
            workspace=f'/sandboxes/{spec.organization_id}/{spec.run_id}',
            api_url=self.api_url,
            image=spec.image,
        )

    async def stop(self, sandbox: Sandbox) -> None:
        self.stopped.append(sandbox)

    async def inspect(self, sandbox: Sandbox) -> dict:
        return {}

    async def reap(self, older_than_seconds: int) -> list[str]:
        return []

    async def enforce_disk_limit(self, sandbox: Sandbox, limit_mb: int) -> bool:
        self.enforced.append((sandbox, limit_mb))
        return False

    async def aclose(self) -> None:
        return None


class FakeAgent:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict] = []
        self.closed = False

    async def start(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return {'id': 'conv-1'}

    async def status(self, conversation_id, *, base_url=None):
        return {'execution_status': 'running'}

    async def cancel(self, conversation_id, *, base_url=None):
        return None

    async def aclose(self):
        self.closed = True


def _settings(**overrides) -> Settings:
    return Settings(
        agent_server_url='http://shared-agent-server',
        agent_server_api_key='session-key',
        sandbox_image='agent-server:test',
        sandbox_workspace_root='/sandboxes',
        **overrides,
    )


async def _noop_probe(sandbox) -> None:
    return None


def _runner(provider: FakeProvider, agent: FakeAgent) -> SandboxedAgentServerRunner:
    return SandboxedAgentServerRunner(
        _settings(), provider=provider, agent=agent, ready_probe=_noop_probe
    )


@pytest.mark.asyncio
async def test_start_provisions_a_sandbox_with_the_configured_limits() -> None:
    provider, agent = FakeProvider(), FakeAgent()
    runner = SandboxedAgentServerRunner(
        _settings(sandbox_cpus=2.0, sandbox_memory_mb=4096, sandbox_pids=1024),
        provider=provider,
        agent=agent,
        ready_probe=_noop_probe,
    )

    result = await runner.start(
        prompt='hello', run_id=str(RUN_ID), organization_id=str(ORG_ID)
    )

    spec = provider.specs[0]
    assert spec.run_id == RUN_ID
    assert spec.organization_id == ORG_ID
    assert spec.limits.cpus == 2.0
    assert spec.limits.memory_mb == 4096
    assert spec.limits.pids == 1024
    assert result['id'] == 'conv-1'
    assert result['sandbox']['api_url'] == 'http://10.0.0.2:8001'


@pytest.mark.asyncio
async def test_conversation_is_created_inside_the_sandbox_workspace() -> None:
    provider, agent = FakeProvider(), FakeAgent()
    runner = _runner(provider, agent)

    await runner.start(prompt='hello', run_id=str(RUN_ID), organization_id=str(ORG_ID))

    call = agent.calls[0]
    assert call['working_dir'] == '/workspace'
    assert call['base_url'] == 'http://10.0.0.2:8001'
    # The shared Agent Server URL is never used when a sandbox exists.
    assert call['base_url'] != 'http://shared-agent-server'


@pytest.mark.asyncio
async def test_a_failed_start_removes_the_sandbox() -> None:
    provider = FakeProvider()
    agent = FakeAgent(error=RuntimeError('agent server rejected the conversation'))
    runner = _runner(provider, agent)

    with pytest.raises(RuntimeError):
        await runner.start(prompt='hello', run_id=str(RUN_ID), organization_id=str(ORG_ID))

    assert len(provider.stopped) == 1
    assert provider.stopped[0].run_id == RUN_ID


@pytest.mark.asyncio
async def test_a_sandbox_without_an_address_is_rejected() -> None:
    provider = FakeProvider(api_url=None)
    # Uses the real readiness probe: a sandbox without an address is rejected
    # before any HTTP call is attempted.
    runner = SandboxedAgentServerRunner(_settings(), provider=provider, agent=FakeAgent())

    with pytest.raises(SandboxError, match='reachable address'):
        await runner.start(prompt='hello', run_id=str(RUN_ID), organization_id=str(ORG_ID))
    assert len(provider.stopped) == 1


@pytest.mark.asyncio
async def test_start_requires_a_run_and_organization() -> None:
    runner = _runner(FakeProvider(), FakeAgent())

    with pytest.raises(SandboxError):
        await runner.start(prompt='hello')
    with pytest.raises(SandboxError):
        await runner.start(prompt='hello', run_id=str(RUN_ID))


@pytest.mark.asyncio
async def test_stop_and_limit_enforcement_use_the_stored_sandbox() -> None:
    provider, agent = FakeProvider(), FakeAgent()
    runner = SandboxedAgentServerRunner(
        _settings(sandbox_disk_mb=2048),
        provider=provider,
        agent=agent,
        ready_probe=_noop_probe,
    )
    result = await runner.start(
        prompt='hello', run_id=str(RUN_ID), organization_id=str(ORG_ID)
    )

    await runner.enforce_limits(result['sandbox'])
    await runner.stop_sandbox(result['sandbox'])

    assert provider.enforced[0][1] == 2048
    assert provider.enforced[0][0].run_id == UUID(str(RUN_ID))
    assert provider.stopped[-1].id == 'container-1'


@pytest.mark.asyncio
async def test_shared_runner_has_no_sandbox_to_stop() -> None:
    from app.runner.agent_server import AgentServerRunner

    runner = AgentServerRunner(_settings())

    await runner.stop_sandbox(None)
    await runner.aclose()
