#!/usr/bin/env python3
"""Verify Supabase migrations, RLS policies and tenant isolation on a DEV project.

This script creates two throw-away users and two organizations, then proves that
user B cannot read or write user A's rows. It never prints keys or tokens.

Required environment (development project only):
  SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY
  CORTEX_VERIFY_ENV=development

Optional:
  CORTEX_VERIFY_ALLOW_REMOTE=1  # accept a non-localhost URL

Exit code 0 means every check passed. Any failed check exits non-zero.
"""

from __future__ import annotations

import json
import os
import secrets
import sys
import urllib.error
import urllib.request

REQUIRED_ENV = ('SUPABASE_URL', 'SUPABASE_ANON_KEY', 'SUPABASE_SERVICE_ROLE_KEY')
TENANT_TABLES = (
    'agents',
    'agent_runs',
    'documents',
    'document_chunks',
    'files',
    'usage_events',
    'organization_invitations',
    'github_installations',
)


class CheckFailure(Exception):
    pass


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
        raise CheckFailure(f'{method} {url.split("?")[0]} -> {status}: {raw[:300]}')
    return (json.loads(raw) if raw.strip() else None), status


def guard_environment(env: dict[str, str]) -> None:
    missing = [name for name in REQUIRED_ENV if not env.get(name)]
    if missing:
        fail(f'missing environment variables: {", ".join(missing)}')
    if env.get('CORTEX_VERIFY_ENV') != 'development':
        fail('set CORTEX_VERIFY_ENV=development (production is refused)')
    url = env['SUPABASE_URL']
    if 'prod' in url.lower():
        fail('refusing to run against a URL containing "prod"')
    if not url.startswith(('http://localhost', 'http://127.0.0.1')):
        if env.get('CORTEX_VERIFY_ALLOW_REMOTE') != '1':
            fail('remote Supabase URL refused; set CORTEX_VERIFY_ALLOW_REMOTE=1 for a dev project')
        print('WARNING: remote Supabase URL. Confirm it is a dedicated development project.')


class Supabase:
    def __init__(self, env: dict[str, str]) -> None:
        self.base = env['SUPABASE_URL'].rstrip('/')
        self.anon = env['SUPABASE_ANON_KEY']
        self.service = env['SUPABASE_SERVICE_ROLE_KEY']

    def admin_headers(self) -> dict[str, str]:
        return {
            'apikey': self.service,
            'Authorization': f'Bearer {self.service}',
            'Content-Type': 'application/json',
        }

    def user_headers(self, token: str, *, representation: bool = False) -> dict[str, str]:
        headers = {
            'apikey': self.anon,
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }
        if representation:
            headers['Prefer'] = 'return=representation'
        return headers

    def create_user(self, email: str, password: str) -> str:
        payload, _ = request(
            'POST',
            f'{self.base}/auth/v1/admin/users',
            headers=self.admin_headers(),
            body={'email': email, 'password': password, 'email_confirm': True},
        )
        return payload['id']

    def sign_in(self, email: str, password: str) -> str:
        payload, _ = request(
            'POST',
            f'{self.base}/auth/v1/token?grant_type=password',
            headers={'apikey': self.anon, 'Content-Type': 'application/json'},
            body={'email': email, 'password': password},
        )
        return payload['access_token']

    def create_org(self, token: str, slug: str, name: str) -> dict:
        payload, _ = request(
            'POST',
            f'{self.base}/rest/v1/rpc/create_organization_with_owner',
            headers=self.user_headers(token),
            body={'organization_slug': slug, 'organization_name': name},
        )
        return payload

    def insert(self, token: str, table: str, row: dict) -> dict:
        payload, _ = request(
            'POST',
            f'{self.base}/rest/v1/{table}',
            headers=self.user_headers(token, representation=True),
            body=row,
        )
        if isinstance(payload, list):
            return payload[0] if payload else {}
        return payload or {}

    def select(self, token: str, table: str, query: str) -> list:
        payload, _ = request(
            'GET',
            f'{self.base}/rest/v1/{table}?{query}',
            headers=self.user_headers(token),
        )
        return payload or []

    def rpc(self, token: str | None, function: str, body: dict, *, admin: bool = False):
        headers = self.admin_headers() if admin else self.user_headers(token or '')
        payload, _ = request(
            'POST', f'{self.base}/rest/v1/rpc/{function}', headers=headers, body=body
        )
        return payload

    def delete_admin(self, table: str, query: str) -> None:
        request('DELETE', f'{self.base}/rest/v1/{table}?{query}', headers=self.admin_headers())


def _cleanup(client: Supabase, users: list[str], orgs: list[str]) -> None:
    if orgs:
        try:
            client.delete_admin('organizations', f'id=in.({",".join(orgs)})')
        except CheckFailure:
            print('   warning: organization cleanup failed')
    for user_id in users:
        try:
            request(
                'DELETE',
                f'{client.base}/auth/v1/admin/users/{user_id}',
                headers=client.admin_headers(),
                expected=(200, 204),
            )
        except CheckFailure:
            print(f'   warning: could not delete test user {user_id}')


def main() -> None:
    env = dict(os.environ)
    guard_environment(env)
    client = Supabase(env)
    created_users: list[str] = []
    created_orgs: list[str] = []
    try:
        run_checks(client, created_users, created_orgs)
    finally:
        _cleanup(client, created_users, created_orgs)


def run_checks(client: Supabase, created_users: list[str], created_orgs: list[str]) -> None:
    suffix = secrets.token_hex(4)
    password = f'Cortex-{secrets.token_urlsafe(12)}'
    email_a = f'cortex-verify-a-{suffix}@example.com'
    email_b = f'cortex-verify-b-{suffix}@example.com'

    print('1/8 creating two users')
    user_a_id = client.create_user(email_a, password)
    created_users.append(user_a_id)
    user_b_id = client.create_user(email_b, password)
    created_users.append(user_b_id)
    token_a = client.sign_in(email_a, password)
    token_b = client.sign_in(email_b, password)

    print('2/8 creating two organizations')
    org_a = client.create_org(token_a, f'verify-a-{suffix}', 'Verify A')
    org_b = client.create_org(token_b, f'verify-b-{suffix}', 'Verify B')
    org_a_id, org_b_id = org_a['id'], org_b['id']
    created_orgs.extend([org_a_id, org_b_id])
    if org_a_id == org_b_id:
        fail('organizations were not created separately')

    print('3/8 seeding tenant A data')
    agent = client.insert(
        token_a,
        'agents',
        {'organization_id': org_a_id, 'created_by': org_a['created_by'], 'name': 'A agent'},
    )
    document = client.insert(
        token_a,
        'documents',
        {
            'organization_id': org_a_id,
            'created_by': org_a['created_by'],
            'title': 'A private document',
            'source': 'manual',
            'status': 'ready',
        },
    )
    client.insert(
        token_a,
        'document_chunks',
        {
            'document_id': document['id'],
            'organization_id': org_a_id,
            'chunk_index': 0,
            'content': 'tenant a secret runbook',
            'token_count': 5,
        },
    )

    print('4/8 checking cross-tenant reads return nothing')
    for table in TENANT_TABLES:
        rows = client.select(token_b, table, f'organization_id=eq.{org_a_id}&select=id')
        if rows:
            fail(f'user B can read {len(rows)} row(s) from {table}')
        print(f'   ok: {table} is invisible to user B')

    print('5/8 checking cross-tenant writes are denied')
    patched, _ = request(
        'PATCH',
        f'{client.base}/rest/v1/agents?id=eq.{agent["id"]}',
        headers=client.user_headers(token_b, representation=True),
        body={'name': 'hijacked'},
        expected=(200, 204),
    )
    if patched:
        fail('user B updated an agent owned by organization A')
    print('   ok: cross-tenant update affects 0 rows')

    try:
        client.insert(
            token_b,
            'agents',
            {'organization_id': org_a_id, 'created_by': org_a['created_by'], 'name': 'intruder'},
        )
        fail('user B inserted an agent into organization A')
    except CheckFailure:
        print('   ok: cross-tenant insert is rejected')

    try:
        client.insert(
            token_b,
            'organization_memberships',
            {'organization_id': org_a_id, 'user_id': org_b['created_by'], 'role': 'admin'},
        )
        fail('user B granted itself a role in organization A')
    except CheckFailure:
        print('   ok: role escalation is rejected')

    print('6/8 checking tenant A still sees its own data')
    own_agents = client.select(token_a, 'agents', f'organization_id=eq.{org_a_id}&select=id')
    if not own_agents:
        fail('organization A lost access to its own agent')
    own_chunks = client.select(
        token_a, 'document_chunks', f'organization_id=eq.{org_a_id}&select=chunk_index'
    )
    if not own_chunks:
        fail('organization A lost access to its own document chunks')
    print('   ok: owner access is intact')

    print('7/8 checking run admission, reservation and settlement')
    budget = 25.0
    run = client.rpc(
        token_a,
        'enqueue_agent_run',
        {
            'target_organization_id': org_a_id,
            'target_agent_id': None,
            'target_model_id': None,
            'target_conversation_id': None,
            'target_prompt': 'verify run admission',
            'target_budget_credits': budget,
            'target_idempotency_key': f'verify-{suffix}',
            'target_metadata': {},
        },
    )
    if run['status'] != 'queued':
        fail(f"new run is not queued: {run['status']}")

    replay = client.rpc(
        token_a,
        'enqueue_agent_run',
        {
            'target_organization_id': org_a_id,
            'target_agent_id': None,
            'target_model_id': None,
            'target_conversation_id': None,
            'target_prompt': 'verify run admission',
            'target_budget_credits': budget,
            'target_idempotency_key': f'verify-{suffix}',
            'target_metadata': {},
        },
    )
    if replay['id'] != run['id']:
        fail('replaying the idempotency key created a second run')
    print('   ok: idempotent replay returns the same run')

    entitlement = client.select(
        token_a,
        'organization_entitlements',
        f'organization_id=eq.{org_a_id}&select=credits_reserved,credits_used',
    )[0]
    if float(entitlement['credits_reserved']) != budget:
        fail(f"reservation is {entitlement['credits_reserved']}, expected {budget}")
    print('   ok: budget is reserved')

    try:
        client.rpc(
            token_a,
            'enqueue_agent_run',
            {
                'target_organization_id': org_a_id,
                'target_agent_id': None,
                'target_model_id': None,
                'target_conversation_id': None,
                'target_prompt': 'second run',
                'target_budget_credits': 1,
                'target_idempotency_key': f'verify-second-{suffix}',
                'target_metadata': {},
            },
        )
        fail('a second concurrent run was accepted on the free plan')
    except CheckFailure:
        print('   ok: concurrency limit is enforced by the database')

    try:
        client.rpc(
            token_b,
            'enqueue_agent_run',
            {
                'target_organization_id': org_a_id,
                'target_agent_id': None,
                'target_model_id': None,
                'target_conversation_id': None,
                'target_prompt': 'intruder',
                'target_budget_credits': 1,
                'target_idempotency_key': f'verify-intruder-{suffix}',
                'target_metadata': {},
            },
        )
        fail('user B enqueued a run in organization A')
    except CheckFailure:
        print('   ok: cross-tenant run creation is rejected')

    settled = client.rpc(
        None,
        'settle_agent_run',
        {
            'target_run_id': run['id'],
            'target_status': 'completed',
            'target_credits_used': 5,
            'target_error': None,
        },
        admin=True,
    )
    if settled['status'] != 'completed':
        fail(f"settlement left the run in {settled['status']}")
    entitlement = client.select(
        token_a,
        'organization_entitlements',
        f'organization_id=eq.{org_a_id}&select=credits_reserved,credits_used',
    )[0]
    if float(entitlement['credits_reserved']) != 0 or float(entitlement['credits_used']) != 5:
        fail(
            'settlement did not release the reservation: '
            f"reserved={entitlement['credits_reserved']} used={entitlement['credits_used']}"
        )
    print('   ok: settlement releases the reservation and books usage')

    print('8/8 checking tenant A can still read the settled run')
    runs = client.select(token_a, 'agent_runs', f'organization_id=eq.{org_a_id}&select=id,status')
    if not any(row['id'] == run['id'] for row in runs):
        fail('owner lost access to its own run')
    other_runs = client.select(token_b, 'agent_runs', f'organization_id=eq.{org_a_id}&select=id')
    if other_runs:
        fail('user B can read runs of organization A')
    print('   ok: run visibility stays tenant-scoped')

    print('PASS: migrations, RLS, tenant isolation and run accounting verified')


if __name__ == '__main__':
    try:
        main()
    except CheckFailure as exc:
        fail(str(exc))
