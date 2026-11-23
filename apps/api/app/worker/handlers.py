from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.database.supabase import SupabaseRequestError
from app.worker.context import WorkerContext
from app.worker.queue import Job, new_job

logger = logging.getLogger(__name__)

ACTIVE_RUN_STATUSES = 'queued,provisioning,running,waiting'
TERMINAL_STATUSES = {'completed', 'failed', 'cancelled', 'expired'}
RECONCILE_DELAY_SECONDS = 15
RECONCILE_MAX_ATTEMPTS = 240


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _get_run(ctx: WorkerContext, run_id: str) -> dict[str, Any] | None:
    rows = await ctx.supabase.request(
        'GET', 'agent_runs', admin=True,
        params={'select': '*', 'id': f'eq.{run_id}', 'limit': '1'},
    )
    return rows[0] if rows else None


async def _patch_run(ctx: WorkerContext, run_id: str, fields: dict[str, Any]) -> None:
    await ctx.supabase.request(
        'PATCH', 'agent_runs', admin=True,
        params={'id': f'eq.{run_id}'},
        json={**fields, 'updated_at': _now()},
    )


async def _settle(
    ctx: WorkerContext,
    run_id: str,
    status: str,
    credits_used: float = 0.0,
    error: str | None = None,
) -> None:
    try:
        await ctx.supabase.request(
            'POST', 'rpc/settle_agent_run', admin=True,
            json={
                'target_run_id': run_id,
                'target_status': status,
                'target_credits_used': credits_used,
                'target_error': error,
            },
        )
    except SupabaseRequestError as exc:
        logger.error('settlement failed run=%s status=%s error=%s', run_id, status, exc)


async def reap_stale_runs(ctx: WorkerContext, job: Job) -> dict[str, Any]:
    older_than_minutes = int(job.payload.get('older_than_minutes', 120))
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(minutes=older_than_minutes)).isoformat()
    await ctx.supabase.request(
        'PATCH', 'agent_runs', admin=True,
        params={
            'status': f'in.({ACTIVE_RUN_STATUSES})',
            'updated_at': f'lt.{cutoff}',
        },
        json={
            'status': 'expired',
            'error': 'run expired by worker cleanup',
            'finished_at': now.isoformat(),
        },
    )
    return {'older_than_minutes': older_than_minutes, 'cutoff': cutoff}


async def execute_agent_run(ctx: WorkerContext, job: Job) -> dict[str, Any]:
    run_id = job.payload.get('run_id')
    if not run_id:
        raise ValueError('execute_agent_run requires a run_id')
    run = await _get_run(ctx, run_id)
    if run is None:
        return {'skipped': 'run not found'}
    if run['status'] in TERMINAL_STATUSES:
        return {'skipped': run['status']}
    if run['status'] != 'queued':
        return {'skipped': run['status']}

    await _patch_run(ctx, run_id, {'status': 'provisioning', 'started_at': _now()})
    conversation = await ctx.runner.start(
        prompt=run.get('prompt') or '',
        model_id=run.get('model_id'),
        title=f'cortex-run-{run_id}',
        working_dir=f'{ctx.runner.settings.agent_server_workspace_root}/{run_id}',
    )
    conversation_id = conversation.get('id') or conversation.get('conversation_id')
    await _patch_run(ctx, run_id, {'status': 'running', 'conversation_id': conversation_id})

    await ctx.queue.schedule(
        new_job(
            'reconcile_agent_run',
            {'run_id': run_id, 'conversation_id': conversation_id},
            organization_id=job.organization_id,
            max_attempts=RECONCILE_MAX_ATTEMPTS,
        ),
        RECONCILE_DELAY_SECONDS,
    )
    return {'conversation_id': conversation_id}


async def reconcile_agent_run(ctx: WorkerContext, job: Job) -> dict[str, Any]:
    run_id = job.payload.get('run_id')
    conversation_id = job.payload.get('conversation_id')
    if not run_id or not conversation_id:
        raise ValueError('reconcile_agent_run requires run_id and conversation_id')
    run = await _get_run(ctx, run_id)
    if run is None or run['status'] in TERMINAL_STATUSES:
        return {'skipped': 'terminal'}

    state = await ctx.runner.status(conversation_id)
    status = str(state.get('execution_status') or state.get('status') or '').lower()
    if status in {'finished', 'completed', 'idle'}:
        await _settle(ctx, run_id, 'completed')
        return {'settled': 'completed'}
    if status in {'error', 'failed', 'stuck', 'stopped'}:
        await _settle(ctx, run_id, 'failed', error=f'agent server reported {status}')
        return {'settled': 'failed'}

    await ctx.queue.schedule(job, RECONCILE_DELAY_SECONDS)
    return {'rescheduled': True}


async def settle_abandoned_run(ctx: WorkerContext, job: Job) -> None:
    """Called when a job exhausts its retries so a run cannot stay reserved forever."""
    run_id = job.payload.get('run_id')
    if not run_id:
        return
    run = await _get_run(ctx, run_id)
    if run is None or run['status'] in TERMINAL_STATUSES:
        return
    await _settle(ctx, run_id, 'failed', error='job exhausted retries')
