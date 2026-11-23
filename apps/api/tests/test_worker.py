import pytest

from app.worker import main as worker_main
from app.worker.queue import RedisJobQueue, new_job


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict = {}
        self.lists: dict = {}

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.values:
            return None
        self.values[key] = value
        return True

    async def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)
        return len(self.lists[key])

    async def brpop(self, key, timeout=0):
        items = self.lists.get(key, [])
        if not items:
            return None
        return key, items.pop(0)

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_enqueue_is_idempotent_by_job_id() -> None:
    queue = RedisJobQueue(FakeRedis())
    job = new_job('reap_stale_runs')
    assert await queue.enqueue(job) is True
    assert await queue.enqueue(job) is False
    assert len(queue.redis.lists['cortex:jobs']) == 1


@pytest.mark.asyncio
async def test_dequeue_roundtrips_job_payload() -> None:
    queue = RedisJobQueue(FakeRedis())
    job = new_job('reap_stale_runs', {'older_than_minutes': 5}, organization_id='org-1')
    await queue.enqueue(job)
    received = await queue.dequeue(timeout=1)
    assert received.id == job.id
    assert received.payload['older_than_minutes'] == 5
    assert received.organization_id == 'org-1'


@pytest.mark.asyncio
async def test_unknown_job_type_goes_to_dead_letter() -> None:
    queue = RedisJobQueue(FakeRedis())
    await queue.enqueue(new_job('mystery_job'))
    assert await worker_main.process_once(queue, client=None) is True
    assert len(queue.redis.lists['cortex:dead']) == 1


@pytest.mark.asyncio
async def test_failing_handler_retries_then_dead_letters(monkeypatch) -> None:
    async def boom(client, job):
        raise RuntimeError('boom')

    monkeypatch.setitem(worker_main.HANDLERS, 'boom_job', boom)
    queue = RedisJobQueue(FakeRedis())
    await queue.enqueue(new_job('boom_job', max_attempts=2))

    await worker_main.process_once(queue, client=None)
    assert len(queue.redis.lists.get('cortex:jobs', [])) == 1

    await worker_main.process_once(queue, client=None)
    assert len(queue.redis.lists['cortex:dead']) == 1
