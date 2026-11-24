from __future__ import annotations

import asyncio
import json
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from app.sandbox.base import (
    Sandbox,
    SandboxError,
    SandboxLimitError,
    SandboxSpec,
    SandboxUnavailable,
)

RUN_LABEL = 'cortex.role=run'
CONTAINER_PREFIX = 'cortex-run-'
SANDBOX_USER = '1000:1000'


class DockerSandboxProvider:
    """One throw-away container per run, built from `docker run` arguments.

    Isolation is enforced by the container runtime, not by the application:

    * own filesystem: a per-run directory is the only bind mount, and the root
      filesystem is read-only with a small tmpfs for scratch space;
    * own process tree: `--pids-limit`, `--cap-drop ALL`, `no-new-privileges`,
      and a non-root user inside the container;
    * resource ceilings: `--cpus`, `--memory` (with swap pinned to the same
      value so the limit cannot be bypassed), and a disk ceiling enforced by
      `enforce_disk_limit`;
    * network: the sandbox joins an internal bridge with no route to the
      internet, so it cannot reach cloud metadata endpoints or the host.

    The provider shells out to the Docker CLI: no extra Python dependency, and
    the exact flags stay auditable in one place.
    """

    def __init__(
        self,
        *,
        workspace_root: str,
        network: str = 'cortex-sandboxes',
        docker: str = 'docker',
        agent_server_port: int = 8001,
        command_timeout: float = 60.0,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.network = network
        self.docker = docker
        self.agent_server_port = agent_server_port
        self.command_timeout = command_timeout
        self._network_ready = False
        # The container must be able to use the bind-mounted workspace. When the
        # API runs as root it can hand the directory to uid 1000; otherwise the
        # container runs as the API user itself, so the 0700 directory stays
        # usable without widening its permissions.
        self.sandbox_user = SANDBOX_USER if os.getuid() == 0 else f'{os.getuid()}:{os.getgid()}'

    # -- docker plumbing -------------------------------------------------
    async def _docker(self, *args: str, check: bool = True) -> str:
        try:
            process = await asyncio.create_subprocess_exec(
                self.docker,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise SandboxUnavailable('docker CLI is not available') from exc
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self.command_timeout
            )
        except TimeoutError as exc:
            process.kill()
            raise SandboxUnavailable(f'docker {args[0]} timed out') from exc
        if check and process.returncode != 0:
            detail = stderr.decode(errors='replace').strip()[:300]
            raise SandboxUnavailable(f'docker {args[0]} failed: {detail}')
        return stdout.decode(errors='replace')

    async def _ensure_network(self) -> None:
        if self._network_ready:
            return
        listing = await self._docker(
            'network', 'ls', '--filter', f'name=^{self.network}$', '--format', '{{.Name}}'
        )
        if self.network not in listing.split():
            # `--internal` removes the default route: containers can talk to the
            # host-side runner, but have no path to the internet or to cloud
            # metadata services.
            await self._docker('network', 'create', '--internal', self.network)
        self._network_ready = True

    # -- workspace -------------------------------------------------------
    def _workspace_for(self, organization_id: UUID, run_id: UUID) -> Path:
        workspace = (self.workspace_root / str(organization_id) / str(run_id)).resolve()
        if self.workspace_root not in workspace.parents:
            raise SandboxError('workspace path escapes the sandbox root')
        return workspace

    @staticmethod
    def _container_name(run_id: UUID) -> str:
        return f'{CONTAINER_PREFIX}{run_id}'

    # -- SandboxProvider -------------------------------------------------
    async def provision(self, spec: SandboxSpec) -> Sandbox:
        spec.limits.validate()
        if not spec.image:
            raise SandboxError('an image is required')
        await self._ensure_network()

        workspace = self._workspace_for(spec.organization_id, spec.run_id)
        workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.getuid() == 0:
            uid, gid = (int(part) for part in self.sandbox_user.split(':'))
            os.chown(workspace, uid, gid)

        name = self._container_name(spec.run_id)
        await self._docker('rm', '-f', name, check=False)

        args = [
            'run', '-d', '--name', name,
            '--label', RUN_LABEL,
            '--label', f'cortex.organization={spec.organization_id}',
            '--label', f'cortex.run={spec.run_id}',
            '--cpus', str(spec.limits.cpus),
            '--memory', f'{spec.limits.memory_mb}m',
            # Pinning swap to the same value removes the usual escape hatch of
            # swapping past the memory ceiling.
            '--memory-swap', f'{spec.limits.memory_mb}m',
            '--pids-limit', str(spec.limits.pids),
            '--read-only',
            '--tmpfs', '/tmp:rw,noexec,nosuid,size=64m',
            '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges',
            '--user', self.sandbox_user,
            '--ulimit', 'nofile=1024:1024',
            '--stop-timeout', '10',
            '--network', spec.network,
            '-v', f'{workspace}:/workspace:rw',
            '-w', '/workspace',
            '-e', f'CORTEX_RUN_ID={spec.run_id}',
            '-e', f'CORTEX_ORGANIZATION_ID={spec.organization_id}',
        ]
        for key, value in spec.env.items():
            args += ['-e', f'{key}={value}']
        args.append(spec.image)
        args.extend(spec.command)

        container_id = (await self._docker(*args)).strip()
        if not container_id:
            raise SandboxUnavailable('docker run returned no container id')

        api_url = None
        if spec.network != 'none':
            ip = (await self._docker(
                'inspect', '-f',
                '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}',
                container_id,
            )).strip()
            if ip:
                api_url = f'http://{ip}:{self.agent_server_port}'

        return Sandbox(
            id=container_id,
            run_id=spec.run_id,
            organization_id=spec.organization_id,
            workspace=str(workspace),
            api_url=api_url,
            image=spec.image,
        )

    async def stop(self, sandbox: Sandbox) -> None:
        await self._docker('rm', '-f', sandbox.id, check=False)
        workspace = Path(sandbox.workspace)
        if self.workspace_root in workspace.parents:
            shutil.rmtree(workspace, ignore_errors=True)

    async def inspect(self, sandbox: Sandbox) -> dict[str, Any]:
        raw = await self._docker('inspect', sandbox.id)
        data = json.loads(raw)
        return data[0] if data else {}

    async def list_active(self) -> list[dict[str, Any]]:
        ids = (await self._docker(
            'ps', '-q', '--filter', f'label={RUN_LABEL}'
        )).split()
        containers = []
        for container_id in ids:
            raw = await self._docker('inspect', container_id, check=False)
            if not raw.strip():
                continue
            data = json.loads(raw)
            if data:
                containers.append(data[0])
        return containers

    async def reap(self, older_than_seconds: int) -> list[str]:
        """Stop sandboxes older than the retention window and delete their files."""
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=older_than_seconds)
        reaped: list[str] = []
        for container in await self.list_active():
            started = container.get('State', {}).get('StartedAt')
            if not started:
                continue
            started_at = datetime.fromisoformat(started.replace('Z', '+00:00'))
            if started_at > cutoff:
                continue
            labels = container.get('Config', {}).get('Labels') or {}
            await self._docker('rm', '-f', container['Id'], check=False)
            run_id = labels.get('cortex.run')
            organization_id = labels.get('cortex.organization')
            if run_id:
                reaped.append(run_id)
                if organization_id:
                    workspace = (self.workspace_root / organization_id / run_id).resolve()
                    if self.workspace_root in workspace.parents:
                        shutil.rmtree(workspace, ignore_errors=True)
        return reaped

    async def disk_usage_mb(self, sandbox: Sandbox) -> float:
        total = 0
        workspace = Path(sandbox.workspace)
        if not workspace.exists():
            return 0.0
        for root, _dirs, files in os.walk(workspace):
            for name in files:
                try:
                    total += os.path.getsize(os.path.join(root, name))
                except OSError:
                    continue
        return round(total / (1024 * 1024), 3)

    async def enforce_disk_limit(self, sandbox: Sandbox, limit_mb: int) -> bool:
        """Stop a sandbox that outgrew its disk budget.

        `--storage-opt` needs an xfs-backed driver with project quotas, which is
        not available everywhere, so the ceiling is also enforced by measuring
        the workspace and killing the container when it is exceeded.
        """
        used = await self.disk_usage_mb(sandbox)
        if used <= limit_mb:
            return False
        await self.stop(sandbox)
        raise SandboxLimitError(
            f'sandbox {sandbox.run_id} used {used} MB, over its {limit_mb} MB budget'
        )

    async def aclose(self) -> None:
        return None
