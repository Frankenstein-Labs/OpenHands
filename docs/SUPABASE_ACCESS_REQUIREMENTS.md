# Supabase access requirements

This document lists exactly what is needed to move from local code to a verified
deployment. Nothing here has been executed against a hosted project yet.

## What is already done without access

- 10 versioned migrations in `supabase/migrations/` (foundation, invitations,
  RBAC, profiles, AI catalog, agents/runs, files/Storage, billing, GitHub App,
  invitation acceptance).
- RLS helper functions and policies for every tenant table.
- Private Storage bucket definitions for `org-files`, `conversation-exports`,
  `run-artifacts`.
- API and worker code plus 63 unit tests, lint clean.

## Access required

A **development** Supabase project (not production) with:

| Item | Purpose |
|---|---|
| Project URL | `SUPABASE_URL` |
| Publishable key (`sb_publishable_...` or legacy anon JWT) | Frontend and user-scoped API calls |
| Secret key (`sb_secret_...` or legacy service-role JWT) | Server-owned writes (usage, audit, billing, webhooks) |
| Personal access token (`sbp_...`) or database URL | Apply migrations; the Management API path needs only the token |
| Auth redirect settings | Confirmation links must return to the app |

Provide access through environment variables or `supabase login` — never by
sharing an account password in chat or committing a key.

## Operations to perform

1. Apply migrations: `python scripts/apply-supabase-migrations.py --confirm-project <dev-ref>`
   with `SUPABASE_ACCESS_TOKEN`, or `supabase link` + `supabase db push` with the
   database password.
3. Create two test users and two organizations.
4. Run the RLS verification script (below).
5. Create the three private buckets if the migration did not (idempotent check).
6. Configure Auth: email confirmation, allowed redirect URLs, optional Google
   and GitHub OAuth providers.

## RLS verification (must pass before beta)

For each table (`organizations`, `organization_memberships`,
`organization_invitations`, `agents`, `agent_runs`, `agent_run_events`, `files`,
`billing_subscriptions`, `billing_invoices`, `usage_events`,
`organization_entitlements`, `ai_models`, `ai_providers`):

- User A (org 1) cannot `select`, `insert`, `update` or `delete` rows of org 2.
- A member cannot escalate their own role.
- A non-owner cannot transfer ownership.
- A signed-out request returns no rows.
- A file object path not prefixed by the org id is rejected.

## Destructive operations

None are required. If a reset is ever needed, use a fresh dev project or
`supabase db reset` on the **development** project only, after exporting data.
Never reset a shared or production project.

## Rollback

- Migrations are additive. To undo a specific change, write a new corrective
  migration; do not edit applied files.
- Keep a `pg_dump` before any manual SQL change.

## Variables to set after access is granted

`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`,
`SUPABASE_JWT_ISSUER`, and (worker) `REDIS_URL`. Then re-run the API tests and
the smoke checklist in `docs/TESTING.md`.
