from __future__ import annotations

import asyncio
import logging
import signal
import time
from collections.abc import Awaitable, Callable
from typing import Any

import redis.asyncio as redis

from app.core.config import get_settings
from app.database.supabase import SupabaseClient
from app.runner.agent_server import AgentServerRunner
from app.worker.context import WorkerContext
from app.worker.handlers import (
    execute_agent_run,
    reap_stale_runs,
    reconcile_agent_run,
    settle_abandoned_run,
)
from app.worker.queue import Delivery, Job, JobQueue, RedisJobQueue

logger = logging.getLogger(__name__)

Handler = Callable[[WorkerContext, Job], Awaitable[Any]]

HANDLERS: dict[str, Handler] = {
    'reap_stale_runs': reap_stale_runs,
    'execute_agent_run': execute_agent_run,
    'reconcile_agent_run': reconcile_agent_run,
}

JOB_LOCK_TTL_SECONDS = 900
RECLAIM_IDLE_MS = 60_000
RECLAIM_INTERVAL_SECONDS = 10.0


async def handle_delivery(
    queue: JobQueue,
    ctx: WorkerContext,
    delivery: Delivery,
    *,
    handlers: dict[str, Handler] | None = None,
) -> None:
    handlers = handlers or HANDLERS
    job = delivery.job
    handler = handlers.get(job.type)
    if handler is None:
        await queue.dead_letter(job, f'unknown job type: {job.type}')
        await queue.ack(delivery)
        return
    if not await queue.acquire_lock(job.id, JOB_LOCK_TTL_SECONDS):
        # Another consumer is already running this job (at-least-once redelivery).
        await queue.ack(delivery)
        return
    try:
        await handler(ctx, job)
    except Exception as exc:
        will_retry = await queue.retry(delivery, str(exc))
        logger.warning(
            'job failed id=%s type=%s attempt=%s retry=%s error=%s',
            job.id, job.type, job.attempts + 1, will_retry, exc,
        )
        if not will_retry:
            await settle_abandoned_run(ctx, job)
    else:
        await queue.ack(delivery)
    finally:
        await queue.release_lock(job.id)


async def process_once(
    queue: JobQueue,
    ctx: WorkerContext,
    *,
    timeout: int = 5,
    handlers: dict[str, Handler] | None = None,
) -> bool:
    await queue.promote_due()
    delivery = await queue.dequeue(timeout=timeout)
    if delivery is None:
        return False
    await handle_delivery(queue, ctx, delivery, handlers=handlers)
    return True


async def reclaim_once(
    queue: JobQueue,
    ctx: WorkerContext,
    *,
    min_idle_ms: int = RECLAIM_IDLE_MS,
    handlers: dict[str, Handler] | None = None,
) -> int:
    deliveries = await queue.reclaim(min_idle_ms)
    for delivery in deliveries:
        if delivery.delivery_count > delivery.job.max_attempts:
            await queue.dead_letter(
                delivery.job, f'job abandoned after {delivery.delivery_count} deliveries'
            )
            await queue.ack(delivery)
            await settle_abandoned_run(ctx, delivery.job)
            continue
        await handle_delivery(queue, ctx, delivery, handlers=handlers)
    return len(deliveries)


async def run_forever(
    stop: asyncio.Event | None = None,
    *,
    handlers: dict[str, Handler] | None = None,
    queue: JobQueue | None = None,
    ctx: WorkerContext | None = None,
) -> None:
    settings = get_settings()
    if queue is None and not settings.redis_url:
        raise RuntimeError('REDIS_URL is required to run the worker')
    if queue is None:
        queue = RedisJobQueue(redis.from_url(settings.redis_url, decode_responses=True))
    if ctx is None:
        ctx = WorkerContext(
            supabase=SupabaseClient(settings),
            queue=queue,
            runner=AgentServerRunner(settings),
        )
    stop = stop or asyncio.Event()
    last_reclaim = 0.0
    try:
        await queue.ensure_group()
        while not stop.is_set():
            await queue.promote_due()
            if time.monotonic() - last_reclaim >= RECLAIM_INTERVAL_SECONDS:
                last_reclaim = time.monotonic()
                await reclaim_once(queue, ctx, handlers=handlers)
            delivery = await queue.dequeue(timeout=1)
            if delivery is not None:
                await handle_delivery(queue, ctx, delivery, handlers=handlers)
    finally:
        await ctx.runner.aclose()
        await ctx.supabase.close()
        await queue.aclose()


def main() -> None:
    logging.basicConfig(level=get_settings().log_level)

    async def runner() -> None:
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop.set)
        await run_forever(stop)

    asyncio.run(runner())


if __name__ == '__main__':
    main()
