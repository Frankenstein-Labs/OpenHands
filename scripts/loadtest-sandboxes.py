#!/usr/bin/env python3
"""Measure how many real Agent Server sandboxes one host can start at once.

Each worker provisions a container through the production provider, waits for
the Agent Server inside it, records the time, the resident memory and whether
it succeeded, then tears the container down.

Usage:
    PYTHONPATH=apps/api python3 scripts/loadtest-sandboxes.py --count 10
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'apps/api'))

import httpx  # noqa: E402

from app.sandbox.base import Sandbox, SandboxLimits, SandboxSpec  # noqa: E402
from app.sandbox.docker import DockerSandboxProvider  # noqa: E402


@dataclass
class Sample:
    ok: bool
    seconds: float
    rss_mb: float
    error: str = ''


async def rss_mb(provider: DockerSandboxProvider, sandbox: Sandbox) -> float:
    process = await asyncio.create_subprocess_exec(
        'docker', 'stats', '--no-stream', '--format', '{{.MemUsage}}', sandbox.id,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
    )
    out, _ = await process.communicate()
    text = out.decode(errors='replace').strip().split('/')[0].strip()
    for unit, factor in (('GiB', 1024.0), ('MiB', 1.0), ('KiB', 1 / 1024)):
        if text.endswith(unit):
            try:
                return float(text[: -len(unit)].strip()) * factor
            except ValueError:
                return 0.0
    return 0.0


async def wait_ready(sandbox: Sandbox, timeout: float) -> bool:
    if not sandbox.api_url:
        return False
    headers = {'X-Session-API-Key': sandbox.session_api_key or ''}
    deadline = time.monotonic() + timeout
    async with httpx.AsyncClient(timeout=5.0) as client:
        while time.monotonic() < deadline:
            try:
                response = await client.get(f'{sandbox.api_url}/health', headers=headers)
                if response.status_code == 200:
                    return True
            except httpx.HTTPError:
                pass
            await asyncio.sleep(1.0)
    return False


async def one(provider: DockerSandboxProvider, image: str, memory_mb: int, timeout: float) -> Sample:
    started = time.monotonic()
    sandbox = None
    try:
        sandbox = await provider.provision(
            SandboxSpec(
                organization_id=uuid4(),
                run_id=uuid4(),
                image=image,
                limits=SandboxLimits(cpus=1.0, memory_mb=memory_mb, pids=256, disk_mb=1024),
            )
        )
        ready = await wait_ready(sandbox, timeout)
        seconds = time.monotonic() - started
        if not ready:
            return Sample(False, seconds, 0.0, 'never ready')
        return Sample(True, seconds, await rss_mb(provider, sandbox))
    except Exception as exc:  # noqa: BLE001 - a failure is a data point here
        return Sample(False, time.monotonic() - started, 0.0, str(exc)[:80])
    finally:
        if sandbox:
            try:
                await provider.stop(sandbox)
            except Exception:  # noqa: BLE001
                pass


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))
    return ordered[index]


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--count', type=int, default=10)
    parser.add_argument('--image', default='ghcr.io/openhands/agent-server:1.63.1-python')
    parser.add_argument('--memory-mb', type=int, default=1024)
    parser.add_argument('--timeout', type=float, default=300.0)
    parser.add_argument('--workspace-root', default='/tmp/cortex-sandbox-loadtest')
    args = parser.parse_args()

    provider = DockerSandboxProvider(workspace_root=args.workspace_root, network='cortex-sandboxes')
    started = time.monotonic()
    try:
        samples = await asyncio.gather(
            *(one(provider, args.image, args.memory_mb, args.timeout) for _ in range(args.count))
        )
    finally:
        await provider.aclose()
    elapsed = time.monotonic() - started

    ready = [s.seconds for s in samples if s.ok]
    rss = [s.rss_mb for s in samples if s.ok and s.rss_mb]
    failures = [s for s in samples if not s.ok]
    print(
        f'sandboxes={args.count} image={args.image} memory_limit_mb={args.memory_mb} '
        f'wall_seconds={elapsed:.1f}'
    )
    print('started,failed,startup_p50_s,startup_p95_s,startup_max_s,rss_mean_mb,rss_total_mb')
    print(
        f'{len(ready)},{len(failures)},{percentile(ready, 0.5):.1f},'
        f'{percentile(ready, 0.95):.1f},{(max(ready) if ready else 0):.1f},'
        f'{(statistics.fmean(rss) if rss else 0):.0f},{(sum(rss)):.0f}'
    )
    for sample in failures[:5]:
        print(f'failure: {sample.error}', file=sys.stderr)
    print(json.dumps({'started': len(ready), 'failed': len(failures)}))
    return 0 if not failures else 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
