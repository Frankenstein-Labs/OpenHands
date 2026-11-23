import shutil
import socket
import subprocess
import time
import uuid

import pytest
import redis as redis_sync
import redis.asyncio as redis

from app.worker import main as worker_main
from app.worker.context import WorkerContext
from app.worker.queue import RedisJobQueue, backoff_seconds, decode_job, encode_job, new_job


def _docker_ready() -> bool:
    if shutil.which('docker') is None:
        return False
    return subprocess.run(['docker', 'info'], capture_output=True).returncode == 0


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


@pytest.fixture(scope='module')
def redis_url():
    if not _docker_ready():
        pytest.skip('docker is required for Redis integration tests')
    name = f'cortex-redis-test-{uuid.uuid4().hex[:8]}'
    port = _free_port()
    subprocess.run(
        ['docker', 'run', '-d', '--name', name, '-p', f'{port}:6379', 'redis:7-alpine'],
        check=True, capture_output=True,
    )
    try:
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                if redis_sync.Redis.from_url(f'redis://127.0.0.1:{port}/0').ping():
                    break
            except Exception:
                time.sleep(0.2)
        else:
            raise RuntimeError('redis test container did not become ready')
        yield f'redis://127.0.0.1:{port}/0'
    finally:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True)


class FakeSupabase:
    async def request(self, *args, **kwargs):
        return []

    async def close(self):
        return None


class FakeRunner:
    settings = type('Settings', (), {'agent_server_workspace_root': '/tmp'})()

    async def start(self, **kwargs):
        raise AssertionError('runner should not be called by queue tests')

    async def status(self, conversation_id):
        raise AssertionError('runner should not be called by queue tests')

    async def aclose(self):
        return None


@pytest.fixture
async def queue(redis_url):
    client = redis.from_url(redis_url, decode_responses=True)
    stream = f'jobs-{uuid.uuid4().hex[:8]}'
    q = RedisJobQueue(
        client,
        stream=stream,
        group='test-group',
        dead_letter_stream=f'{stream}:dead',
        retry_queue=f'{stream}:retry',
    )
    await q.ensure_group()
    yield q
    await q.aclose()


@pytest.fixture
def ctx(queue):
    return WorkerContext(supabase=FakeSupabase(), queue=queue, runner=FakeRunner())


def test_backoff_grows_and_is_capped() -> None:
    assert backoff_seconds(1) == 2
    assert backoff_seconds(2) == 4
    assert backoff_seconds(20) == 300


def test_job_roundtrip() -> None:
    job = new_job('reap_stale_runs', {'older_than_minutes': 5}, organization_id='org-1')
    restored = decode_job(encode_job(job))
    assert restored.id == job.id
    assert restored.payload == {'older_than_minutes': 5}
    assert restored.organization_id == 'org-1'


@pytest.mark.asyncio
async def test_enqueue_is_idempotent_by_job_id(queue) -> None:
    job = new_job('reap_stale_runs')
    assert await queue.enqueue(job) is True
    assert await queue.enqueue(job) is False
    assert await queue.redis.xlen(queue.stream) == 1


@pytest.mark.asyncio
async def test_successful_job_is_acked_and_not_pending(queue, ctx) -> None:
    seen = []

    async def handler(context, job):
        seen.append(job.id)

    await queue.enqueue(new_job('ok_job'))
    assert await worker_main.process_once(queue, ctx, handlers={'ok_job': handler}) is True
    assert seen
    pending = await queue.redis.xpending(queue.stream, queue.group)
    assert pending['pending'] == 0


@pytest.mark.asyncio
async def test_failure_retries_with_backoff_then_dead_letters(queue, ctx, monkeypatch) -> None:
    monkeypatch.setattr('app.worker.queue.backoff_seconds', lambda attempts, **_: 0)

    async def boom(context, job):
        raise RuntimeError('boom')

    await queue.enqueue(new_job('boom_job', max_attempts=2))
    await worker_main.process_once(queue, ctx, handlers={'boom_job': boom})

    assert await queue.redis.zcard(queue.retry_queue) == 1
    assert await queue.promote_due() == 1

    await worker_main.process_once(queue, ctx, handlers={'boom_job': boom})
    assert await queue.redis.xlen(queue.dead_letter_stream) == 1
    pending = await queue.redis.xpending(queue.stream, queue.group)
    assert pending['pending'] == 0


@pytest.mark.asyncio
async def test_unknown_job_type_is_dead_lettered(queue, ctx) -> None:
    await queue.enqueue(new_job('mystery_job'))
    await worker_main.process_once(queue, ctx, handlers={})
    assert await queue.redis.xlen(queue.dead_letter_stream) == 1


@pytest.mark.asyncio
async def test_crashed_worker_job_is_reclaimed_and_processed(queue, ctx) -> None:
    seen = []

    async def handler(context, job):
        seen.append(job.id)

    job = new_job('crash_job')
    await queue.enqueue(job)

    # A worker takes the job and dies before acknowledging it.
    delivery = await queue.dequeue(timeout=1)
    assert delivery is not None
    assert delivery.job.id == job.id

    reclaimed = await queue.reclaim(min_idle_ms=0)
    assert len(reclaimed) == 1
    assert reclaimed[0].job.id == job.id

    await worker_main.handle_delivery(queue, ctx, reclaimed[0], handlers={'crash_job': handler})
    assert seen == [job.id]
    pending = await queue.redis.xpending(queue.stream, queue.group)
    assert pending['pending'] == 0


@pytest.mark.asyncio
async def test_job_lock_prevents_double_execution(queue) -> None:
    assert await queue.acquire_lock('job-1', 30) is True
    assert await queue.acquire_lock('job-1', 30) is False
    await queue.release_lock('job-1')
    assert await queue.acquire_lock('job-1', 30) is True


@pytest.mark.asyncio
async def test_duplicate_delivery_is_skipped_while_lock_is_held(queue, ctx) -> None:
    calls = []

    async def handler(context, job):
        calls.append(job.id)

    job = new_job('locked_job')
    await queue.enqueue(job)
    delivery = await queue.dequeue(timeout=1)
    assert delivery is not None

    assert await queue.acquire_lock(job.id, 30) is True
    await worker_main.handle_delivery(queue, ctx, delivery, handlers={'locked_job': handler})
    assert calls == []
    pending = await queue.redis.xpending(queue.stream, queue.group)
    assert pending['pending'] == 0


@pytest.mark.asyncio
async def test_delayed_job_is_not_promoted_early(queue) -> None:
    await queue.schedule(new_job('later'), delay_seconds=60)
    assert await queue.promote_due() == 0
    assert await queue.redis.xlen(queue.stream) == 0
