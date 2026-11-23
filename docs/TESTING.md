# Testing Cortex.ai

## Backend

```bash
cd apps/api
python -m venv .venv && . .venv/bin/activate
pip install -e '.[test]'
pytest -q
ruff check app tests
```

Current result: **94 tests passed**, `ruff` clean.

Two suites need real infrastructure and skip themselves when it is missing:

```bash
# Redis queue integration tests: starts a redis:7-alpine container per module
pytest -q tests/test_worker.py

# SQL migrations, RLS and run accounting on a disposable Postgres
bash ../../scripts/verify-supabase-local.sh

# Hosted development project (requires SUPABASE_* and CORTEX_VERIFY_ENV)
python ../../scripts/verify-supabase-isolation.py
```

Coverage by area:

- auth/JWT and health
- organizations, memberships, RBAC, owner transfer
- invitations (hash storage, admin-only creation, acceptance RPC contract)
- agents and runs (quota, budget, cancellation, events)
- files (presign validation, path scoping, deletion)
- usage summary and limits
- billing (plans, subscription, checkout abstraction, webhook signature)
- GitHub App (JWT signing, webhook HMAC, dedupe, revocation)
- AI gateway (provider parsing/streaming/fallback, metered generation, budget)
- worker (idempotent enqueue, ack, retry with backoff, dead letter, crash
  reclaim, job lock, delayed promotion) against a real Redis container
- runner client and execute/reconcile handlers with a stubbed Agent Server
  transport

## What is not yet proven

- Live provider calls (no provider credentials configured).
- Agent Server execution: no `AGENT_SERVER_URL` is configured, so
  `execute_agent_run` fails with `RunnerUnavailable`.
- Token metering from the Agent Server, so settled `credits_used` is 0.
- Sandbox isolation limits on the target container platform.
- Concurrency/load tests (10 → 25 → 50 → 100 users) — must be run on real
  infrastructure before any capacity claim.
- Frontend Vitest/typecheck/build for the SaaS additions (no frontend changes
  were made in these phases; run `npm run typecheck && npm run lint && npm test`
  before release).

## Adding tests

- Use `httpx.ASGITransport` plus `app.dependency_overrides` for routes.
- Prefer a fake transport or fake repository over mocking the unit under test.
- Cover one happy path and the authorization/quota failure paths.
- Do not assert on literal SQL strings or duplicate schema definitions.

## RLS verification

Follow `docs/SUPABASE_ACCESS_REQUIREMENTS.md`: two users, two organizations, and
negative checks on every tenant table. Isolation evidence must be recorded in
the PR before any beta checklist item is marked done.
