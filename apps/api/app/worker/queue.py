from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol


@dataclass
class Job:
    id: str
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    organization_id: str | None = None
    attempts: int = 0
    max_attempts: int = 3


def new_job(
    job_type: str,
    payload: dict[str, Any] | None = None,
    *,
    organization_id: str | None = None,
    max_attempts: int = 3,
) -> Job:
    return Job(
        id=uuid.uuid4().hex,
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


class JobQueue(Protocol):
    async def enqueue(self, job: Job) -> bool: ...
    async def dequeue(self, timeout: int = 5) -> Job | None: ...
    async def requeue(self, job: Job) -> None: ...
    async def dead_letter(self, job: Job, error: str) -> None: ...


class RedisJobQueue:
    def __init__(
        self,
        redis_client: Any,
        *,
        queue: str = 'cortex:jobs',
        dead_letter_queue: str = 'cortex:dead',
        seen_ttl: int = 86400,
    ) -> None:
        self.redis = redis_client
        self.queue = queue
        self.dead_letter_queue = dead_letter_queue
        self.seen_ttl = seen_ttl

    def _seen_key(self, job_id: str) -> str:
        return f'{self.queue}:seen:{job_id}'

    async def enqueue(self, job: Job) -> bool:
        created = await self.redis.set(self._seen_key(job.id), '1', nx=True, ex=self.seen_ttl)
        if not created:
            return False
        await self.redis.rpush(self.queue, encode_job(job))
        return True

    async def dequeue(self, timeout: int = 5) -> Job | None:
        item = await self.redis.brpop(self.queue, timeout=timeout)
        if not item:
            return None
        return decode_job(item[1])

    async def requeue(self, job: Job) -> None:
        await self.redis.rpush(self.queue, encode_job(job))

    async def dead_letter(self, job: Job, error: str) -> None:
        await self.redis.rpush(self.dead_letter_queue, json.dumps({'job': asdict(job), 'error': error}))

    async def aclose(self) -> None:
        await self.redis.aclose()
