#!/usr/bin/env python3
"""Validate the sandbox engine against the real Agent Server image.

Every check drives the production code path (`DockerSandboxProvider`), not a
reimplementation: the script provisions containers exactly the way a run does,
then attacks them.

Usage:
    PYTHONPATH=apps/api python3 scripts/validate-sandbox-engine.py \
        --image ghcr.io/openhands/agent-server:1.63.1-python

Exit code is 0 only when every check passes.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'apps/api'))

from app.sandbox.base import Sandbox, SandboxLimits, SandboxSpec  # noqa: E402
from app.sandbox.docker import DockerSandboxProvider  # noqa: E402


@dataclass
class Result:
    name: str
    ok: bool
    detail: str


RESULTS: list[Result] = []


def record(name: str, ok: bool, detail: str) -> None:
    RESULTS.append(Result(name, ok, detail))
    print(f'{"PASS" if ok else "FAIL"}  {name}: {detail}', flush=True)


async def docker(*args: str, timeout: float = 120.0) -> tuple[int, str]:
    process = await asyncio.create_subprocess_exec(
        'docker', *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        out, _ = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError:
        process.kill()
        return 124, 'timeout'
    return process.returncode, out.decode(errors='replace').strip()


async def sh(sandbox: Sandbox, command: str, timeout: float = 60.0) -> tuple[int, str]:
    return await docker('exec', sandbox.id, 'sh', '-lc', command, timeout=timeout)


async def wait_ready(sandbox: Sandbox, timeout: float = 180.0) -> tuple[bool, float]:
    started = time.monotonic()
    key = sandbox.session_api_key or ''
    while time.monotonic() - started < timeout:
        code, _ = await docker(
            'exec', sandbox.id, 'sh', '-lc',
            f'curl -sS -m 2 -o /dev/null -w "%{{http_code}}" '
            f'-H "X-Session-API-Key: {key}" http://127.0.0.1:8000/health',
            timeout=20,
        )
        if code == 0:
            _, out = await docker(
                'exec', sandbox.id, 'sh', '-lc',
                f'curl -sS -m 2 -o /dev/null -w "%{{http_code}}" '
                f'-H "X-Session-API-Key: {key}" http://127.0.0.1:8000/health',
                timeout=20,
            )
            if out.strip() == '200':
                return True, time.monotonic() - started
        await asyncio.sleep(1.0)
    return False, time.monotonic() - started


async def mem_usage(sandbox: Sandbox) -> str:
    code, out = await docker(
        'stats', '--no-stream', '--format', '{{.MemUsage}} {{.CPUPerc}}', sandbox.id
    )
    return out if code == 0 else 'unknown'


async def check_real_agent_server(provider: DockerSandboxProvider, image: str) -> Sandbox | None:
    spec = SandboxSpec(
        organization_id=uuid4(),
        run_id=uuid4(),
        image=image,
        limits=SandboxLimits(cpus=2.0, memory_mb=3072, pids=512, disk_mb=4096),
    )
    provision_started = time.monotonic()
    sandbox = await provider.provision(spec)
    ready, ready_seconds = await wait_ready(sandbox)
    provision_seconds = time.monotonic() - provision_started
    record(
        'real-agent-server/ready',
        ready,
        f'container+ready in {provision_seconds:.1f}s (ready probe {ready_seconds:.1f}s)',
    )
    if not ready:
        code, logs = await docker('logs', '--tail', '20', sandbox.id)
        print(logs)
        return sandbox

    key = sandbox.session_api_key or ''
    # /health is intentionally public; a data endpoint must not be.
    _, unauthenticated = await docker(
        'exec', sandbox.id, 'sh', '-lc',
        'curl -sS -m 3 -o /dev/null -w "%{http_code}" '
        'http://127.0.0.1:8000/api/conversations/search?limit=1',
    )
    record(
        'real-agent-server/requires-key',
        unauthenticated.strip() in {'401', '403'},
        f'/api/conversations/search without X-Session-API-Key -> {unauthenticated.strip()}',
    )
    _, authenticated = await docker(
        'exec', sandbox.id, 'sh', '-lc',
        f'curl -sS -m 3 -o /dev/null -w "%{{http_code}}" '
        f'-H "X-Session-API-Key: {key}" http://127.0.0.1:8000/api/conversations/search?limit=1',
    )
    record(
        'real-agent-server/keyed-request',
        authenticated.strip() == '200',
        f'/api/conversations/search with the sandbox key -> {authenticated.strip()}',
    )
    record('real-agent-server/memory', True, await mem_usage(sandbox))
    return sandbox


async def check_network(sandbox: Sandbox) -> None:
    code, out = await sh(
        sandbox, 'curl -sS -m 4 -o /dev/null -w "%{http_code}" http://1.1.1.1/ || echo blocked'
    )
    record('network/no-internet', 'blocked' in out or out.strip() == '000',
           f'internet egress -> {out.strip()[:40]}')

    code, out = await sh(sandbox, 'getent hosts example.com || echo no-dns')
    record('network/no-dns', 'no-dns' in out, f'DNS resolution -> {out.strip()[:40]}')

    code, out = await sh(
        sandbox,
        'curl -sS -m 4 -o /dev/null -w "%{http_code}" http://169.254.169.254/latest/meta-data/ '
        '|| echo blocked',
    )
    record('network/no-cloud-metadata', 'blocked' in out or out.strip() == '000',
           f'metadata endpoint -> {out.strip()[:40]}')

    code, out = await sh(
        sandbox,
        'test -S /var/run/docker.sock && echo socket-present || echo no-socket',
    )
    record('network/no-docker-socket', 'no-socket' in out, 'host docker socket is not mounted')

    code, out = await sh(sandbox, 'id -u')
    record('identity/non-root', out.strip() not in {'0', ''}, f'uid inside sandbox -> {out.strip()}')


async def check_cpu_limit(provider: DockerSandboxProvider, image: str) -> None:
    spec = SandboxSpec(
        organization_id=uuid4(),
        run_id=uuid4(),
        image=image,
        limits=SandboxLimits(cpus=0.5, memory_mb=1024, pids=128, disk_mb=512),
    )
    sandbox = await provider.provision(spec)
    try:
        ready, _ = await wait_ready(sandbox, timeout=240)
        if not ready:
            record('limits/cpu', False, 'sandbox never became ready')
            return
        # Burn a fixed amount of CPU time and compare it with wall time: a
        # 0.5 CPU quota forces wall time to be roughly twice the CPU time.
        script = (
            "python3 - <<'PY'\n"
            "import time\n"
            "w0, c0 = time.time(), time.process_time()\n"
            "while time.process_time() - c0 < 2.0:\n"
            "    pass\n"
            "print(f'{time.process_time() - c0:.2f} {time.time() - w0:.2f}')\n"
            "PY"
        )
        _, out = await sh(sandbox, script, timeout=120)
        parts = out.split()
        cpu_s = float(parts[-2]) if len(parts) >= 2 else 0.0
        wall_s = float(parts[-1]) if len(parts) >= 2 else 0.0
        ratio = wall_s / cpu_s if cpu_s else 0.0
        record(
            'limits/cpu',
            ratio >= 1.5,
            f'{cpu_s:.2f}s of CPU work took {wall_s:.2f}s of wall time '
            f'(ratio {ratio:.2f}; a 0.5 CPU quota needs >= 1.5)',
        )
    finally:
        await provider.stop(sandbox)


async def check_memory_limit(provider: DockerSandboxProvider, image: str) -> None:
    spec = SandboxSpec(
        organization_id=uuid4(),
        run_id=uuid4(),
        image=image,
        limits=SandboxLimits(cpus=1.0, memory_mb=512, pids=128, disk_mb=512),
    )
    sandbox = await provider.provision(spec)
    try:
        ready, _ = await wait_ready(sandbox, timeout=240)
        if not ready:
            record('limits/memory', False, 'sandbox never became ready')
            return
        # 2 GiB in a 512 MiB container must be refused by the kernel.
        _, cgroup = await sh(sandbox, 'cat /sys/fs/cgroup/memory.max 2>/dev/null || echo unknown')
        code, out = await sh(
            sandbox,
            'python3 -c "b=bytearray(1024*1024*2048); print(len(b))"',
            timeout=180,
        )
        killed = code in {137, 143} or 'killed' in out.lower()
        record(
            'limits/memory',
            killed,
            f'2 GiB bytearray in a 512 MiB sandbox (cgroup {cgroup.strip()}) '
            f'-> exit {code}, output {out.strip()[:40]!r}',
        )
    finally:
        await provider.stop(sandbox)


async def check_pid_limit(provider: DockerSandboxProvider, image: str) -> None:
    spec = SandboxSpec(
        organization_id=uuid4(),
        run_id=uuid4(),
        image=image,
        limits=SandboxLimits(cpus=1.0, memory_mb=1024, pids=64, disk_mb=512),
    )
    sandbox = await provider.provision(spec)
    try:
        ready, _ = await wait_ready(sandbox, timeout=240)
        if not ready:
            record('limits/pids', False, 'sandbox never became ready')
            return
        code, out = await sh(
            sandbox,
            'ok=0; fail=0; i=0; while [ $i -lt 200 ]; do '
            '(sleep 30 &) 2>/dev/null && ok=$((ok+1)) || fail=$((fail+1)); '
            'i=$((i+1)); done; echo "spawned=$ok failed=$fail"',
            timeout=120,
        )
        record(
            'limits/pids',
            'failed=' in out and not out.strip().endswith('failed=0'),
            f'200 background processes with --pids-limit 64 -> {out.strip()[-40:]}',
        )
    finally:
        await provider.stop(sandbox)


async def check_disk_and_isolation(
    provider: DockerSandboxProvider, image: str
) -> None:
    spec_a = SandboxSpec(
        organization_id=uuid4(),
        run_id=uuid4(),
        image=image,
        limits=SandboxLimits(cpus=1.0, memory_mb=1024, pids=128, disk_mb=64),
    )
    sandbox_a = await provider.provision(spec_a)
    try:
        ready, _ = await wait_ready(sandbox_a, timeout=240)
        if not ready:
            record('limits/disk', False, 'sandbox never became ready')
            record('isolation/cross-tenant', False, 'sandbox never became ready')
            return

        await sh(sandbox_a, 'echo tenant-a > /workspace/a.txt && ls /workspace')
        # A second run of another organization must not see that file.
        spec_b = SandboxSpec(
            organization_id=uuid4(),
            run_id=uuid4(),
            image=image,
            limits=SandboxLimits(cpus=1.0, memory_mb=1024, pids=128, disk_mb=64),
        )
        sandbox_b = await provider.provision(spec_b)
        try:
            ready_b, _ = await wait_ready(sandbox_b, timeout=240)
            _, listing = await sh(sandbox_b, 'ls -A /workspace')
            record(
                'isolation/cross-tenant',
                ready_b and 'a.txt' not in listing,
                f'other tenant workspace listing -> {listing.strip()[:40]!r}',
            )
            _, escape = await sh(sandbox_b, 'ls /var/lib/cortex/sandboxes 2>&1 || echo denied')
            record(
                'isolation/host-path',
                'denied' in escape or 'No such file' in escape,
                'sandbox cannot list the host workspace root',
            )
        finally:
            await provider.stop(sandbox_b)

        # 200 MiB written into a 64 MiB budget must be rejected by the probe.
        await sh(sandbox_a, 'dd if=/dev/zero of=/workspace/big.bin bs=1M count=200 2>/dev/null; true')
        from app.sandbox.base import SandboxLimitError

        try:
            await provider.enforce_disk_limit(sandbox_a, 64)
        except SandboxLimitError as exc:
            record('limits/disk', True, f'disk probe refused an over-quota workspace: {exc}')
        else:
            record('limits/disk', False, 'disk probe accepted a 200 MiB workspace with a 64 MiB budget')
    finally:
        await provider.stop(sandbox_a)


async def check_reap(provider: DockerSandboxProvider, image: str) -> None:
    spec = SandboxSpec(
        organization_id=uuid4(),
        run_id=uuid4(),
        image=image,
        limits=SandboxLimits(cpus=0.5, memory_mb=512, pids=64, disk_mb=256),
    )
    sandbox = await provider.provision(spec)
    stopped = await provider.reap(older_than_seconds=0)
    code, _ = await docker('inspect', sandbox.id)
    record(
        'lifecycle/reap',
        code != 0 and not Path(sandbox.workspace).exists(),
        f'reap removed {len(stopped)} container(s); container gone={code != 0}, '
        f'workspace gone={not Path(sandbox.workspace).exists()}',
    )


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', default='ghcr.io/openhands/agent-server:1.63.1-python')
    parser.add_argument('--workspace-root', default='/tmp/cortex-engine-validation')
    parser.add_argument('--skip-limits', action='store_true')
    args = parser.parse_args()

    provider = DockerSandboxProvider(workspace_root=args.workspace_root, network='cortex-sandboxes')
    started = time.monotonic()
    sandbox = None
    try:
        sandbox = await check_real_agent_server(provider, args.image)
        if sandbox:
            await check_network(sandbox)
            await check_disk_and_isolation(provider, args.image)
            if not args.skip_limits:
                await check_cpu_limit(provider, args.image)
                await check_memory_limit(provider, args.image)
                await check_pid_limit(provider, args.image)
            await check_reap(provider, args.image)
    finally:
        if sandbox:
            await provider.stop(sandbox)
        await provider.aclose()

    failed = [r for r in RESULTS if not r.ok]
    print('\n' + json.dumps({'checks': len(RESULTS), 'failed': len(failed),
                             'seconds': round(time.monotonic() - started, 1)}, indent=None))
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
