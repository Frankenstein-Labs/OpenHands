from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.database.supabase import SupabaseClient
from app.worker.queue import Job

ACTIVE_RUN_STATUSES = 'queued,provisioning,running,waiting'


async def reap_stale_runs(client: SupabaseClient, job: Job) -> dict[str, Any]:
    older_than_minutes = int(job.payload.get('older_than_minutes', 120))
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(minutes=older_than_minutes)).isoformat()
    await client.request(
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
