"""Isolation tests that run real containers.

These are the evidence that isolation comes from the container runtime and not
from the application: every assertion reads the container configuration or runs
a command inside the sandbox.
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import uuid
from pathlib import Path
from uuid import uuid4

import pytest

from app.sandbox.base import SandboxLimitError, SandboxLimits, SandboxSpec
from app.sandbox.docker import DockerSandboxProvider

pytestmark = pytest.mark.skipif(
    shutil.which('docker') is None
    or subprocess.run(['docker', 'info'], capture_output=True).returncode != 0,
    reason='docker is required for sandbox isolation tests',
)

IMAGE = 'alpine:3.20'
KEEPALIVE = ('sh', '-c', 'sleep infinity')


def _spec(*, network: str = 'none', limits: SandboxLimits | None = None, org=None, run=None):
    return SandboxSpec(
        organization_id=org or uuid4(),
        run_id=run or uuid4(),
        image=IMAGE,
        limits=limits or SandboxLimits(cpus=0.5, memory_mb=256, pids=64, disk_mb=256),
        network=network,
        command=KEEPALIVE,
    )


@pytest.fixture
def provider(tmp_path: Path):
    created = DockerSandboxProvider(workspace_root=str(tmp_path / 'sandboxes'))

    async def _cleanup() -> None:
        for sandbox in created_sandboxes:
            await created.stop(sandbox)
        await created.aclose()

    created_sandboxes: list = []
    yield created, created_sandboxes
    asyncio.run(_cleanup())


async def _provision(provider: DockerSandboxProvider, created: list, **kwargs):
    sandbox = await provider.provision(_spec(**kwargs))
    created.append(sandbox)
    return sandbox


async def _exec(provider: DockerSandboxProvider, sandbox, script: str) -> tuple[int, str]:
    process = await asyncio.create_subprocess_exec(
        provider.docker, 'exec', sandbox.id, 'sh', '-c', script,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    out, _ = await process.communicate()
    return process.returncode, out.decode(errors='replace').strip()


@pytest.mark.asyncio
async def test_runtime_enforces_cpu_memory_pids_and_hardening(provider) -> None:
    client, created = provider
    sandbox = await _provision(client, created)

    info = await client.inspect(sandbox)
    host = info['HostConfig']

    assert host['NanoCpus'] == 500_000_000
    assert host['Memory'] == 256 * 1024 * 1024
    # Swap pinned to the memory ceiling: the limit cannot be escaped by swapping.
    assert host['MemorySwap'] == host['Memory']
    assert host['PidsLimit'] == 64
    assert host['ReadonlyRootfs'] is True
    assert host['CapDrop'] == ['ALL']
    assert any('no-new-privileges' in opt for opt in host['SecurityOpt'])
    assert host['NetworkMode'] == 'none'
    assert info['Config']['User'] == client.sandbox_user


@pytest.mark.asyncio
async def test_sandbox_cannot_write_outside_its_workspace(provider) -> None:
    client, created = provider
    sandbox = await _provision(client, created)

    code_root, _ = await _exec(client, sandbox, 'touch /etc/cortex-escape')
    code_workspace, _ = await _exec(client, sandbox, 'touch /workspace/ok')

    assert code_root != 0, 'the container root filesystem must be read-only'
    assert code_workspace == 0, 'the run workspace must be writable'


@pytest.mark.asyncio
async def test_sandbox_runs_as_an_unprivileged_user(provider) -> None:
    client, created = provider
    sandbox = await _provision(client, created)

    _, uid = await _exec(client, sandbox, 'id -u')

    expected = int(client.sandbox_user.split(':')[0])
    assert uid.strip() == str(expected)
    assert expected != 0, 'the sandbox must never run as root'


@pytest.mark.asyncio
async def test_two_runs_of_two_tenants_share_no_files(provider) -> None:
    client, created = provider
    org_a, org_b = uuid4(), uuid4()
    first = await _provision(client, created, org=org_a)
    second = await _provision(client, created, org=org_b)

    Path(first.workspace, 'tenant-a.txt').write_text('a secret')
    Path(second.workspace, 'tenant-b.txt').write_text('b secret')

    _, listing = await _exec(client, first, 'ls /workspace')
    _, read_other = await _exec(client, first, f'cat {second.workspace}/tenant-b.txt')

    assert listing.split() == ['tenant-a.txt']
    assert 'b secret' not in read_other

    mounts = (await client.inspect(first))['Mounts']
    assert len(mounts) == 1
    assert mounts[0]['Source'] == first.workspace
    assert str(org_a) in first.workspace and str(org_b) not in first.workspace


@pytest.mark.asyncio
async def test_sandbox_has_no_network_route(provider) -> None:
    client, created = provider
    sandbox = await _provision(client, created)

    _, routes = await _exec(client, sandbox, 'cat /proc/net/route')
    _, interfaces = await _exec(client, sandbox, "ip -o link show | awk '{print $2}'")

    # Only the loopback interface exists and there is no default route, so a
    # sandbox cannot reach the internet or a cloud metadata endpoint.
    assert routes.strip().splitlines()[1:] == []
    assert interfaces.split() == ['lo:']


@pytest.mark.asyncio
async def test_stop_removes_the_container_and_its_files(provider) -> None:
    client, created = provider
    sandbox = await _provision(client, created)
    Path(sandbox.workspace, 'leftover.txt').write_text('x')

    await client.stop(sandbox)

    code, _ = await _exec(client, sandbox, 'true')
    assert code != 0
    assert not Path(sandbox.workspace).exists()


@pytest.mark.asyncio
async def test_disk_budget_stops_an_oversized_sandbox(provider) -> None:
    client, created = provider
    sandbox = await _provision(client, created)
    Path(sandbox.workspace, 'big.bin').write_bytes(b'0' * (2 * 1024 * 1024))

    used = await client.disk_usage_mb(sandbox)
    assert used >= 2

    with pytest.raises(SandboxLimitError):
        await client.enforce_disk_limit(sandbox, limit_mb=1)

    code, _ = await _exec(client, sandbox, 'true')
    assert code != 0


@pytest.mark.asyncio
async def test_reap_stops_expired_sandboxes_and_deletes_their_files(provider) -> None:
    client, created = provider
    sandbox = await _provision(client, created)
    await asyncio.sleep(1.2)

    reaped = await client.reap(older_than_seconds=1)

    assert str(sandbox.run_id) in reaped
    code, _ = await _exec(client, sandbox, 'true')
    assert code != 0
    assert not Path(sandbox.workspace).exists()
    created.clear()


@pytest.mark.asyncio
async def test_workspace_paths_cannot_escape_the_sandbox_root(provider) -> None:
    client, _ = provider
    spec = SandboxSpec(
        organization_id=uuid4(),
        run_id=uuid4(),
        image=IMAGE,
        network='none',
        command=KEEPALIVE,
    )
    workspace = client._workspace_for(spec.organization_id, spec.run_id)

    assert workspace.is_relative_to(client.workspace_root)
    assert str(spec.organization_id) in str(workspace)
    assert uuid.UUID(spec.run_id.hex) == spec.run_id
