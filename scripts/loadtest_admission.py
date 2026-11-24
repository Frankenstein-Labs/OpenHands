#!/usr/bin/env python3
"""Progressive concurrency test for run admission.

Measures the database admission path (`enqueue_agent_run`), which is where
concurrency is decided: quota, budget reservation and idempotency all happen
under a row lock there.

Each virtual user gets its own organization (tenant scale) unless `--contended`
is passed, in which case every user shares one organization and therefore one
entitlement row (lock contention). Latency is measured inside Postgres with
`clock_timestamp()`, so the numbers do not include process or HTTP overhead.

Usage:
  python3 scripts/loadtest_admission.py --users 10 --requests 20 \\
      --psql "docker exec -i cortex-local-pg psql -U postgres"

Never point this at production: it creates and deletes rows in the target
database and refuses a URL that looks like production.
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import time
import uuid

LOADTEST_SLUG_PREFIX = 'load-'
SAMPLES_TABLE = 'public.loadtest_samples'


class LoadTestError(RuntimeError):
    pass


def _psql(psql_command: str, sql: str) -> str:
    process = subprocess.run(
        [*shlex.split(psql_command), '-qtA', '-v', 'ON_ERROR_STOP=1', '-c', sql],
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        raise LoadTestError(process.stderr.strip()[:500])
    return process.stdout.strip()


def _guard(psql_command: str) -> None:
    lowered = psql_command.lower()
    if 'prod' in lowered:
        raise LoadTestError('refusing to run against a command containing "prod"')
    if os.environ.get('CORTEX_LOADTEST_CONFIRM') != '1':
        raise LoadTestError(
            'set CORTEX_LOADTEST_CONFIRM=1 to acknowledge this writes and deletes '
            'test data in the target database'
        )


def _fixture_sql(users: int, contended: bool, requests: int) -> tuple[str, list[dict]]:
    plan_id = 'loadtest'
    run_id_prefix = uuid.uuid4().hex[:8]
    tenants = 1 if contended else users
    accounts = []
    statements = [
        f"""
        insert into public.plans (id, name, included_credits, limits)
        values ('{plan_id}', 'Load test', 1000000,
                '{{"max_concurrent_runs": {max(requests + 10, 1000)}}}'::jsonb)
        on conflict (id) do update
          set limits = excluded.limits, included_credits = excluded.included_credits;
        """,
        f'drop table if exists {SAMPLES_TABLE};',
        f'create table {SAMPLES_TABLE} (latency_ms double precision, ok boolean, error text);',
    ]
    for index in range(tenants):
        user_id = str(uuid.uuid4())
        org_id = str(uuid.uuid4())
        slug = f'{LOADTEST_SLUG_PREFIX}{run_id_prefix}-{index}'
        statements.append(
            f"""
            insert into auth.users (id, email) values ('{user_id}', '{slug}@loadtest.local');
            insert into public.organizations (id, slug, name, created_by)
            values ('{org_id}', '{slug}', 'Load test {index}', '{user_id}');
            insert into public.organization_memberships (organization_id, user_id, role)
            values ('{org_id}', '{user_id}', 'owner');
            insert into public.organization_entitlements
              (organization_id, plan_id, credits_limit, period_start, period_end)
            values ('{org_id}', '{plan_id}', 1000000, now() - interval '1 day', now() + interval '30 days');
            """
        )
        accounts.append({'org_id': org_id, 'user_id': user_id})
    return '\n'.join(statements), accounts


def _worker_sql(account: dict, requests: int, tag: str) -> str:
    org_id, user_id = account['org_id'], account['user_id']
    return f"""
    set request.jwt.claim.sub = '{user_id}';
    do $$
    declare
      t0 timestamptz;
      t1 timestamptz;
      i integer;
    begin
      for i in 1..{requests} loop
        t0 := clock_timestamp();
        begin
          perform public.enqueue_agent_run(
            '{org_id}'::uuid, null, null, null, 'load {tag}', 1, '{tag}-{{i}}'
          );
          t1 := clock_timestamp();
          insert into {SAMPLES_TABLE} (latency_ms, ok)
          values (extract(epoch from (t1 - t0)) * 1000, true);
        exception when others then
          t1 := clock_timestamp();
          insert into {SAMPLES_TABLE} (latency_ms, ok, error)
          values (extract(epoch from (t1 - t0)) * 1000, false, sqlerrm);
        end;
      end loop;
    end $$;
    """


def _summary_sql() -> str:
    return f"""
    select
      count(*) as requests,
      count(*) filter (where not ok) as failures,
      round(avg(latency_ms)::numeric, 2) as avg_ms,
      round(percentile_cont(0.5) within group (order by latency_ms)::numeric, 2) as p50_ms,
      round(percentile_cont(0.95) within group (order by latency_ms)::numeric, 2) as p95_ms,
      round(percentile_cont(0.99) within group (order by latency_ms)::numeric, 2) as p99_ms,
      round(max(latency_ms)::numeric, 2) as max_ms
    from {SAMPLES_TABLE};
    """


def _errors_sql() -> str:
    return (
        f"select coalesce(error, 'none') || ' | ' || count(*)::text from {SAMPLES_TABLE} "
        'where not ok group by error order by count(*) desc limit 5;'
    )


def _cleanup_sql() -> str:
    return f"""
    delete from public.organizations where slug like '{LOADTEST_SLUG_PREFIX}%';
    delete from auth.users where email like '{LOADTEST_SLUG_PREFIX}%@loadtest.local';
    drop table if exists {SAMPLES_TABLE};
    """


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--users', type=int, default=10, help='concurrent virtual users')
    parser.add_argument('--requests', type=int, default=20, help='admissions per user')
    parser.add_argument(
        '--psql',
        default=os.environ.get('PSQL_COMMAND', 'psql'),
        help='psql command, e.g. "docker exec -i pg psql -U postgres"',
    )
    parser.add_argument(
        '--contended',
        action='store_true',
        help='all users share one organization (one entitlement row)',
    )
    args = parser.parse_args()

    try:
        _guard(args.psql)
        fixture, accounts = _fixture_sql(args.users, args.contended, args.requests)
        _psql(args.psql, fixture)

        started = time.perf_counter()
        processes: list[subprocess.Popen] = []
        failures: list[str] = []
        try:
            for index in range(args.users):
                account = accounts[index % len(accounts)]
                tag = f'{index}-{uuid.uuid4().hex[:6]}'
                process = subprocess.Popen(
                    [*shlex.split(args.psql), '-qtA', '-v', 'ON_ERROR_STOP=1', '-f', '-'],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                processes.append(process)
                process.stdin.write(_worker_sql(account, args.requests, tag))
                process.stdin.close()

            for process in processes:
                _, stderr = process.communicate()
                if process.returncode != 0:
                    failures.append(stderr.strip()[:300])
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
        elapsed = time.perf_counter() - started

        if failures:
            raise LoadTestError('; '.join(failures))

        summary = _psql(args.psql, _summary_sql())
        errors = _psql(args.psql, _errors_sql())
        _psql(args.psql, _cleanup_sql())
    except LoadTestError as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        return 1

    mode = 'shared organization' if args.contended else 'one organization per user'
    print(f'users={args.users} requests_per_user={args.requests} mode={mode}')
    print(f'wall_seconds={elapsed:.2f} throughput_rps={args.users * args.requests / elapsed:.1f}')
    print('requests,failures,avg_ms,p50_ms,p95_ms,p99_ms,max_ms')
    print(summary)
    if errors:
        print('errors:')
        print(errors)
    return 0


if __name__ == '__main__':
    sys.exit(main())
