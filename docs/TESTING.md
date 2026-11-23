# Testing Cortex.ai

## Backend

```bash
cd apps/api
python -m venv .venv && . .venv/bin/activate
pip install -e '.[test]'
pytest -q
ruff check app tests
```

Current result: **67 tests passed**, `ruff` clean.

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
- worker (idempotent enqueue, retry, dead letter)

## What is not yet proven

- PostgreSQL execution of migrations and RLS policies (no hosted Supabase).
- Storage bucket policies and signed URLs against a real project.
- Live provider calls (no provider credentials configured).
- Agent Server execution and sandbox isolation limits.
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
