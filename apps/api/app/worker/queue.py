from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

RETRY_QUEUE = 'cortex:jobs:retry'


@dataclass
class Job:
    id: str
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    organization_id: str | None = None
    attempts: int = 0
    max_attempts: int = 3


@dataclass
class Delivery:
    job: Job
    entry_id: str
    delivery_count: int = 1


def new_job(
    job_type: str,
    payload: dict[str, Any] | None = None,
    *,
    organization_id: str | None = None,
    max_attempts: int = 3,
    job_id: str | None = None,
) -> Job:
    return Job(
        id=job_id or uuid.uuid4().hex,
        type=job_type,
        payload=payload or {},
        organization_id=organization_id,
        max_attempts=max_attempts,
    )


def encode_job(job: Job) -> str:
    return json.dumps(asdict(job))


def decode_job(raw: str | bytes) -> Job:
    if isinstance(raw, bytes):
        raw = raw.decode()
    data = json.loads(raw)
    return Job(
        id=data['id'],
        type=data['type'],
        payload=data.get('payload') or {},
        organization_id=data.get('organization_id'),
        attempts=int(data.get('attempts', 0)),
        max_attempts=int(data.get('max_attempts', 3)),
    )


def backoff_seconds(attempts: int, *, base: float = 2.0, cap: float = 300.0) -> float:
    return min(cap, base * (2 ** max(attempts - 1, 0)))


class JobQueue(Protocol):
    async def enqueue(self, job: Job) -> bool: ...
    async def dequeue(self, timeout: int = 5) -> Delivery | None: ...
    async def ack(self, delivery: Delivery) -> None: ...
    async def retry(self, delivery: Delivery, error: str) -> bool: ...
    async def dead_letter(self, job: Job, error: str) -> None: ...
    async def schedule(self, job: Job, delay_seconds: float) -> None: ...
    async def promote_due(self, limit: int = 50) -> int: ...
    async def reclaim(self, min_idle_ms: int, limit: int = 20) -> list[Delivery]: ...
    async def acquire_lock(self, job_id: str, ttl_seconds: int) -> bool: ...
    async def release_lock(self, job_id: str) -> None: ...


class RedisJobQueue:
    """Reliable queue on Redis Streams.

    A plain `BRPOP` loses a job when a worker dies between pop and completion.
    This queue keeps every in-flight job in a consumer-group pending list, so a
    crashed worker's job is reclaimed by another consumer instead of vanishing.
    Delivery is at-least-once: callers must stay idempotent and take the job lock.
    """

    def __init__(
        self,
        redis_client: Any,
        *,
        stream: str = 'cortex:jobs',
        group: str = 'cortex-workers',
        consumer: str | None = None,
        dead_letter_stream: str = 'cortex:jobs:dead',
        seen_ttl: int = 86400,
        retry_queue: str = RETRY_QUEUE,
    ) -> None:
        self.redis = redis_client
        self.stream = stream
        self.group = group
        self.consumer = consumer or f'worker-{uuid.uuid4().hex[:8]}'
        self.dead_letter_stream = dead_letter_stream
        self.seen_ttl = seen_ttl
        self.retry_queue = retry_queue

    def _seen_key(self, job_id: str) -> str:
        return f'{self.stream}:seen:{job_id}'

    def _lock_key(self, job_id: str) -> str:
        return f'{self.stream}:lock:{job_id}'

    async def ensure_group(self) -> None:
        try:
            await self.redis.xgroup_create(self.stream, self.group, id='0', mkstream=True)
        except Exception as exc:  # redis raises ResponseError with BUSYGROUP
            if 'BUSYGROUP' not in str(exc):
                raise

    async def enqueue(self, job: Job) -> bool:
        created = await self.redis.set(self._seen_key(job.id), '1', nx=True, ex=self.seen_ttl)
        if not created:
            return False
        await self.redis.xadd(
            self.stream, {'job': encode_job(job)}, maxlen=100_000, approximate=True
        )
        return True

    async def dequeue(self, timeout: int = 5) -> Delivery | None:
        response = await self.redis.xreadgroup(
            self.group,
            self.consumer,
            {self.stream: '>'},
            count=1,
            block=max(timeout, 0) * 1000,
        )
        if not response:
            return None
        _, messages = response[0]
        if not messages:
            return None
        entry_id, fields = messages[0]
        return Delivery(job=decode_job(fields['job']), entry_id=entry_id)

    async def ack(self, delivery: Delivery) -> None:
        await self.redis.xack(self.stream, self.group, delivery.entry_id)

    async def retry(self, delivery: Delivery, error: str) -> bool:
        job = delivery.job
        job.attempts += 1
        await self.ack(delivery)
        if job.attempts >= job.max_attempts:
            await self.dead_letter(job, error)
            return False
        due = time.time() + backoff_seconds(job.attempts)
        await self.redis.zadd(self.retry_queue, {encode_job(job): due})
        return True

    async def dead_letter(self, job: Job, error: str) -> None:
        await self.redis.xadd(
            self.dead_letter_stream,
            {'job': encode_job(job), 'error': error[:2000]},
            maxlen=10_000,
            approximate=True,
        )

    async def schedule(self, job: Job, delay_seconds: float) -> None:
        due = time.time() + max(delay_seconds, 0)
        await self.redis.zadd(self.retry_queue, {encode_job(job): due})

    async def promote_due(self, limit: int = 50) -> int:
        due = await self.redis.zrangebyscore(
            self.retry_queue, '-inf', time.time(), start=0, num=limit
        )
        promoted = 0
        for raw in due:
            if await self.redis.zrem(self.retry_queue, raw):
                await self.redis.xadd(
                    self.stream, {'job': raw}, maxlen=100_000, approximate=True
                )
                promoted += 1
        return promoted

    async def reclaim(self, min_idle_ms: int, limit: int = 20) -> list[Delivery]:
        pending = await self.redis.xpending_range(
            self.stream, self.group, min='-', max='+', count=limit, idle=min_idle_ms
        )
        deliveries: list[Delivery] = []
        for entry in pending:
            entry_id = entry['message_id']
            claimed = await self.redis.xclaim(
                self.stream,
                self.group,
                self.consumer,
                min_idle_time=min_idle_ms,
                message_ids=[entry_id],
            )
            for claimed_id, fields in claimed:
                if not fields:
                    continue
                deliveries.append(
                    Delivery(
                        job=decode_job(fields['job']),
                        entry_id=claimed_id,
                        delivery_count=int(entry.get('times_delivered', 1)),
                    )
                )
        return deliveries

    async def acquire_lock(self, job_id: str, ttl_seconds: int) -> bool:
        return bool(
            await self.redis.set(self._lock_key(job_id), self.consumer, nx=True, ex=ttl_seconds)
        )

    async def release_lock(self, job_id: str) -> None:
        key = self._lock_key(job_id)
        current = await self.redis.get(key)
        if current in (self.consumer, self.consumer.encode()):
            await self.redis.delete(key)

    async def aclose(self) -> None:
        await self.redis.aclose()
