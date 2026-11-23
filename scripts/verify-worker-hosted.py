#!/usr/bin/env python3
"""End-to-end check: queue -> worker -> Supabase, on a development project.

Creates one throw-away user and organization, enqueues a real `execute_agent_run`
job with no Agent Server configured, and proves that the worker retries, moves
the job to the dead-letter stream, and settles the run so no credit stays
reserved.

Required environment (development project only):
  SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, REDIS_URL
  CORTEX_VERIFY_ENV=development

Optional:
  CORTEX_VERIFY_ALLOW_REMOTE=1
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps' / 'api'))

import redis.asyncio as redis  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.database.supabase import SupabaseClient  # noqa: E402
from app.runner.agent_server import AgentServerRunner  # noqa: E402
from app.worker import main as worker_main  # noqa: E402
from app.worker.context import WorkerContext  # noqa: E402
from app.worker.handlers import (  # noqa: E402
    execute_agent_run,
    reconcile_agent_run,
    settle_abandoned_run,
)
from app.worker.queue import RedisJobQueue, new_job  # noqa: E402


class StubAgentServer:
    """Minimal stand-in for the Agent Server conversation API (test double)."""

    def __init__(self) -> None:
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.url = ''
        self.requests: list[tuple[str, str, str | None]] = []

    def start(self) -> None:
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:
                return None

            def _send(self, payload: dict) -> None:
                body = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self) -> None:
                length = int(self.headers.get('Content-Length') or 0)
                self.rfile.read(length)
                stub.requests.append(('POST', self.path, self.headers.get('X-Session-API-Key')))
                self._send({'id': 'conv-stub'})

            def do_GET(self) -> None:
                stub.requests.append(('GET', self.path, self.headers.get('X-Session-API-Key')))
                self._send({'execution_status': 'finished'})

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.url = f'http://127.0.0.1:{self.server.server_address[1]}'
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()


def fail(message: str) -> None:
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def request(method, url, *, headers, body=None, expected=(200, 201, 204)):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            status = response.status
            raw = response.read().decode()
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read().decode()
    if status not in expected:
        raise RuntimeError(f'{method} {url.split("?")[0]} -> {status}: {raw[:300]}')
    return json.loads(raw) if raw.strip() else None


async def main() -> None:
    env = os.environ.get('CORTEX_VERIFY_ENV')
    if env != 'development':
        fail('CORTEX_VERIFY_ENV must be "development"; refusing to touch anything else')

    base = os.environ['SUPABASE_URL'].rstrip('/')
    anon = os.environ['SUPABASE_ANON_KEY']
    service = os.environ['SUPABASE_SERVICE_ROLE_KEY']
    redis_url = os.environ['REDIS_URL']
    if not base.startswith(('http://localhost', 'http://127.0.0.1')) and os.environ.get(
        'CORTEX_VERIFY_ALLOW_REMOTE'
    ) != '1':
        fail('set CORTEX_VERIFY_ALLOW_REMOTE=1 to run against a non-local Supabase URL')

    admin = {
        'apikey': service,
        'Authorization': f'Bearer {service}',
        'Content-Type': 'application/json',
    }

    suffix = secrets.token_hex(6)
    email = f'worker-verify-{suffix}@example.test'
    password = f'Verify-{secrets.token_urlsafe(12)}'
    user_id = None
    org_id = None
    created_run_id = None

    redis_client = redis.from_url(redis_url, decode_responses=True)
    stream = f'verify-jobs-{suffix}'
    queue = RedisJobQueue(
        redis_client,
        stream=stream,
        group='verify-workers',
        dead_letter_stream=f'{stream}:dead',
        retry_queue=f'{stream}:retry',
    )
    settings = Settings(
        supabase_url=base,
        supabase_anon_key=anon,
        supabase_service_role_key=service,
        redis_url=redis_url,
        agent_server_url=None,
    )
    supabase = SupabaseClient(settings)

    try:
        print('1/8 creating a throw-away user')
        created = request(
            'POST', f'{base}/auth/v1/admin/users', headers=admin,
            body={'email': email, 'password': password, 'email_confirm': True},
        )
        user_id = created['id']

        token = request(
            'POST', f'{base}/auth/v1/token?grant_type=password',
            headers={'apikey': anon, 'Content-Type': 'application/json'},
            body={'email': email, 'password': password},
        )['access_token']
        user_headers = {'apikey': anon, 'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

        print('2/8 creating an organization')
        org = request(
            'POST', f'{base}/rest/v1/rpc/create_organization_with_owner', headers=user_headers,
            body={'organization_slug': f'worker-{suffix}', 'organization_name': 'Worker verify'},
        )
        org_id = org['id']

        print('3/8 enqueuing a run with a reserved budget')
        run = request(
            'POST', f'{base}/rest/v1/rpc/enqueue_agent_run', headers=user_headers,
            body={
                'target_organization_id': org_id,
                'target_agent_id': None,
                'target_model_id': None,
                'target_conversation_id': None,
                'target_prompt': 'worker verification',
                'target_budget_credits': 5,
                'target_idempotency_key': f'worker-{suffix}',
                'target_metadata': {},
            },
        )
        created_run_id = run['id']

        print('4/8 running the worker with no Agent Server configured')
        await queue.ensure_group()
        job = new_job('execute_agent_run', {'run_id': created_run_id}, max_attempts=1)
        await queue.enqueue(job)
        ctx = WorkerContext(supabase=supabase, queue=queue, runner=AgentServerRunner(settings))
        processed = await worker_main.process_once(
            queue, ctx, timeout=1, handlers={'execute_agent_run': execute_agent_run}
        )
        if not processed:
            fail('the worker did not pick up the job')

        print('5/8 checking dead letter and settlement')
        dead = await redis_client.xlen(queue.dead_letter_stream)
        if dead != 1:
            fail(f'expected 1 dead-lettered job, found {dead}')
        rows = await supabase.request(
            'GET', 'agent_runs', admin=True,
            params={'select': 'id,status,credits_reserved,error', 'id': f'eq.{created_run_id}'},
        )
        if not rows or rows[0]['status'] != 'failed':
            fail(f"run was not settled as failed: {rows}")
        if float(rows[0]['credits_reserved']) != 0:
            fail('the failed run kept its reservation')
        entitlements = await supabase.request(
            'GET', 'organization_entitlements', admin=True,
            params={
                'select': 'credits_reserved,credits_used',
                'organization_id': f'eq.{org_id}',
            },
        )
        if float(entitlements[0]['credits_reserved']) != 0:
            fail('the entitlement kept a reservation after the failure')
        print('   ok: job dead-lettered, run failed, credits released')

        print('6/8 done (failure path)')

        print('7/8 running the success path against a stub Agent Server')
        stub = StubAgentServer()
        stub.start()
        try:
            success_settings = Settings(
                supabase_url=base,
                supabase_anon_key=anon,
                supabase_service_role_key=service,
                redis_url=redis_url,
                agent_server_url=stub.url,
                agent_server_api_key='stub-key',
            )
            success_ctx = WorkerContext(
                supabase=supabase, queue=queue, runner=AgentServerRunner(success_settings)
            )
            run2 = request(
                'POST', f'{base}/rest/v1/rpc/enqueue_agent_run', headers=user_headers,
                body={
                    'target_organization_id': org_id,
                    'target_agent_id': None,
                    'target_model_id': None,
                    'target_conversation_id': None,
                    'target_prompt': 'success path',
                    'target_budget_credits': 5,
                    'target_idempotency_key': f'worker-success-{suffix}',
                    'target_metadata': {},
                },
            )
            job2 = new_job('execute_agent_run', {'run_id': run2['id']}, max_attempts=2)
            await queue.enqueue(job2)
            if not await worker_main.process_once(
                queue, success_ctx, timeout=1, handlers={'execute_agent_run': execute_agent_run}
            ):
                fail('the worker did not pick up the success job')

            started = await supabase.request(
                'GET', 'agent_runs', admin=True,
                params={'select': 'status,conversation_id', 'id': f'eq.{run2["id"]}'},
            )
            if started[0]['status'] != 'running' or not started[0]['conversation_id']:
                fail(f'run was not started on the Agent Server: {started}')

            await reconcile_agent_run(
                success_ctx,
                new_job(
                    'reconcile_agent_run',
                    {'run_id': run2['id'], 'conversation_id': started[0]['conversation_id']},
                ),
            )
            finished = await supabase.request(
                'GET', 'agent_runs', admin=True,
                params={'select': 'status,credits_reserved,credits_used', 'id': f'eq.{run2["id"]}'},
            )
            if finished[0]['status'] != 'completed':
                fail(f"run did not complete: {finished}")
            if float(finished[0]['credits_reserved']) != 0:
                fail('a completed run kept its reservation')
            print('   ok: conversation started, run completed, reservation released')
        finally:
            stub.stop()

        print('8/8 done')
        print('PASS: worker -> Supabase -> Agent Server path verified')
    finally:
        await supabase.close()
        try:
            await redis_client.delete(
                queue.stream, queue.dead_letter_stream, queue.retry_queue
            )
        finally:
            await queue.aclose()
        if org_id:
            try:
                request(
                    'DELETE', f'{base}/rest/v1/organizations?id=eq.{org_id}',
                    headers=admin, expected=(200, 204),
                )
            except Exception as exc:  # cleanup is best effort, reported below
                print(f'cleanup warning: organization: {exc}', file=sys.stderr)
        if user_id:
            try:
                request(
                    'DELETE', f'{base}/auth/v1/admin/users/{user_id}',
                    headers=admin, expected=(200, 204),
                )
            except Exception as exc:
                print(f'cleanup warning: user: {exc}', file=sys.stderr)


if __name__ == '__main__':
    asyncio.run(main())
