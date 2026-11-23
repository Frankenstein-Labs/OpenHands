from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import redis.asyncio as redis

from app.core.config import get_settings
from app.database.supabase import SupabaseClient
from app.worker.handlers import reap_stale_runs
from app.worker.queue import Job, JobQueue, RedisJobQueue

logger = logging.getLogger(__name__)

Handler = Callable[[SupabaseClient, Job], Awaitable[Any]]

HANDLERS: dict[str, Handler] = {
    'reap_stale_runs': reap_stale_runs,
}


async def process_once(queue: JobQueue, client: SupabaseClient, *, timeout: int = 5) -> bool:
    job = await queue.dequeue(timeout=timeout)
    if job is None:
        return False
    handler = HANDLERS.get(job.type)
    if handler is None:
        await queue.dead_letter(job, f'unknown job type: {job.type}')
        return True
    try:
        await handler(client, job)
    except Exception as exc:
        job.attempts += 1
        if job.attempts >= job.max_attempts:
            await queue.dead_letter(job, str(exc))
        else:
            await queue.requeue(job)
        logger.warning(
            'job failed id=%s type=%s attempts=%s error=%s',
            job.id, job.type, job.attempts, exc,
        )
    return True


async def run_forever() -> None:
    settings = get_settings()
    if not settings.redis_url:
        raise RuntimeError('REDIS_URL is required to run the worker')
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    queue = RedisJobQueue(redis_client)
    client = SupabaseClient(settings)
    try:
        while True:
            processed = await process_once(queue, client, timeout=5)
            if not processed:
                await asyncio.sleep(0.5)
    finally:
        await client.close()
        await queue.aclose()


def main() -> None:
    logging.basicConfig(level=get_settings().log_level)
    asyncio.run(run_forever())


if __name__ == '__main__':
    main()
