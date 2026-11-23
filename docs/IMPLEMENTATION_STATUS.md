# Implementation Status

## Project scope

Transform OpenHands Agent Canvas into an independent SaaS platform based on OpenHands, Supabase, FastAPI, Redis, Supabase Storage, GitHub App and a provider-neutral AI Gateway.

## Phase status

| Phase | Status | Evidence | Blockers / next action |
|---|---|---|---|
| Phase 0 — Audit and architecture | Documented | `OPENHANDS_PRODUCTION_AUDIT.md`, `SAAS_ARCHITECTURE_PROPOSAL.md`, `PHASE_0_SUPABASE_GITHUB_GAP_ANALYSIS.md`, `saas-architecture.mmd` | Architecture constraints are now Supabase + GitHub App + FastAPI. |
| Phase 1 — Stabilisation | Complete for the frontend baseline | Under Node `24.22.1`: `npm ci --ignore-scripts`, `npm run typecheck`, `npm run lint`, `npm run build`, `npm audit --omit=dev` all passed; Vitest: 931 files passed, 11,029 tests passed, 1 skipped, 7 todo. | Docker and Supabase CLI are not installed in this sandbox, so Docker/Supabase smoke tests remain unverified. The full audit still reports 18 development-tree vulnerabilities (17 moderate, 1 high), through Electron/tooling/ESLint/Tailwind/Stryker chains; no `--force` upgrade was used. |
| Phase 2 — Supabase foundation | In progress | Added `supabase/config.toml`, foundation migration and incremental `20261123041000_organizations_invitations.sql`; CLI `3.2.0` works. Schema now includes organizations, memberships, viewer role, invitations, plans, entitlements, usage, audit logs, RLS helpers/policies and three private Storage buckets. | `supabase db lint --local` cannot start because Docker is unavailable; SQL has not yet been executed against Postgres. |
| Phase 3 — FastAPI backend | In progress | Added `apps/api` with FastAPI app, settings, CORS, lifecycle logging, health/readiness/auth routes, JWT/JWKS verification, Supabase REST client, Dockerfile and tests. Backend tests: 10 passed; OpenAPI route check passed. | No hosted Supabase endpoint has been verified. Redis workers and database integration tests remain. |
| Phase 4 — Auth and multi-tenancy | In progress | Added membership list/add/update/remove routes, owner transfer route, repository/service separation, role checks, protected SQL RPC mutations and negative elevation/isolation tests. Backend suite: 14 passed. | Invitations API, Storage isolation and real PostgreSQL/RLS tests remain. |
| Phase 5 — GitHub App | Implemented (code + unit tests) | `app/github/` (RS256 app JWT, installation token, repository listing), `app/api/v1/github.py` (link/list installations and repositories, signed webhook endpoint), webhook dedupe by delivery id, revocation on `installation.deleted`. 8 unit tests. | A real GitHub App registration, private key and webhook URL are required to verify live. |
| Phase 6 — AI Gateway | Implemented (metered endpoint) | `app/ai_gateway/` provider abstraction (OpenAI-compatible, OpenRouter, Together, Hugging Face, Vercel AI Gateway, Frankenstein), capability-aware routing with retry rules, catalogue from `ai_models`/`ai_providers`, `POST /api/v1/ai/generate` with 402 budget enforcement and atomic usage accounting. 16 unit tests. | No provider credential is configured, so live generation is unproven. Cloudflare Workers AI adapter not implemented. |
| Phase 7 — OpenHands runner | Control plane implemented | `agent_runs`/`agent_run_events`, create/get/cancel/events routes, concurrent-run quota, budget reservation, worker cleanup (`reap_stale_runs`). 6 unit tests. | Sandbox provisioning is delegated to the Agent Server; isolation limits must be verified on the target platform. |
| Phase 8 — Redis/workers | Implemented | `apps/api/app/worker/` (job envelope, Redis queue with idempotent enqueue, retry, dead letter), `apps/worker/` package and Dockerfile. 4 unit tests. | No managed Redis provisioned yet. |
| Phase 9 — Supabase Storage/RAG | Storage implemented; RAG pending | Private buckets and `files` table with org-prefixed object paths, presign/list/download/delete routes with size and MIME validation, signed URLs. RAG ingestion is not implemented. | Requires hosted Supabase to verify bucket policies. |
| Phase 10 — Billing/quotas | Billing abstraction + quotas implemented | Provider-neutral billing service, plans/subscription/checkout/invoices routes, signed idempotent webhook, server-side quota and credit enforcement. 6 unit tests. | No Stripe account configured; no real charge is possible or attempted. |
| Phase 11 — SaaS/admin UI | Not started | Canvas settings exist; SaaS dashboard/admin surfaces do not. | Must connect only to working backend contracts. |
| Phase 12 — Production validation | Not started | Existing CI/Docker release machinery is present but SaaS stack is absent. | Requires integration, security, load, backup and restore evidence. |

## Phase 2 change log

- Added local Supabase CLI configuration without hosted credentials.
- Added versioned SQL for tenant authority, membership-based RLS, server-owned usage/audit writes, and private `org-files`, `conversation-exports` and `run-artifacts` buckets.
- Supabase CLI 3.2.0 is runnable via `npx`; local database lint is blocked by the missing Docker runtime.

- Added incremental migration `20261123041000_organizations_invitations.sql` for `viewer`, invitations and atomic organization-owner bootstrap.

## Phase 3 change log

- Added an independently installable Python backend under `apps/api` using FastAPI, Pydantic Settings, HTTPX and PyJWT.
- Added health/readiness endpoints and server-side JWT verification with JWKS cache, issuer, audience, expiration, subject and algorithm checks.
- Added `GET /api/v1/auth/me`, Dockerfile, `.env.example`, README and backend tests using generated keys and mocked JWKS responses.
- Added a server-only Supabase REST client with timeout, user-token/RLS mode, optional admin mode and explicit configuration errors.
- Added organization schemas, repository, service and protected list/create/get/update routes; ten backend tests pass including a negative cross-tenant case and mocked Supabase client checks.

## Phase 4 change log

- Added membership schemas, repository, RBAC service and protected routes for listing, adding, role changes, removal and ownership transfer.
- Added incremental migration `20261123042000_membership_rbac.sql`; direct membership write policy is removed and sensitive mutations are constrained by SECURITY DEFINER functions with explicit owner/admin checks.
- Added tests for member isolation, admin elevation prevention and owner-only transfer; the backend suite now has 14 passing tests.

## Phase 1 change log

- Added `.nvmrc` requesting Node `24.22.1` to match CI and `package.json` engines.
- Changed `npm run typecheck` to run `make-i18n` first, fixing clean-checkout missing generated i18n declarations.
- Ran `npm audit fix --package-lock-only --ignore-scripts`; runtime audit is now clean (`npm audit --omit=dev`: 0 vulnerabilities). The full audit still reports 18 development-tree vulnerabilities (17 moderate, 1 high); they are not forced because npm reports breaking upgrade paths.

## Verification policy

A phase is not complete until its listed checks have actually run and their results are recorded. Phase 1 is complete for the frontend baseline, with the environment limitations above recorded. No external Supabase, GitHub, payment or production deployment is claimed as connected until independently verified.

## Phase 5–10 change log (current pass)

Backend (`apps/api`):

- GitHub App: `app/github/{app_auth,webhooks}.py`, `app/repositories/github.py`,
  `app/services/github.py`, `app/schemas/github.py`, `app/api/v1/github.py`.
- AI gateway: `app/schemas/ai_gateway.py`, `app/services/ai_gateway.py`,
  `app/api/v1/ai_gateway.py`, metered `POST /api/v1/ai/generate`.
- Usage accounting: `supabase/migrations/20261123050000_usage_accounting.sql`
  (atomic, idempotent `record_usage_event`), `UsageRepository.record_event`.
- Worker: `app/worker/{queue,handlers,main}.py`, `apps/worker/` package and
  Dockerfile.
- Alignment fixes against the real migrations: `agent_runs` table, `billing_*`
  tables, invitation RPC token hash, file `deleted_at`.
- Routers registered: 14 total (health, auth, profile, organizations,
  memberships, invitations, models, agents, runs, usage, files, billing,
  github, ai-gateway).

Verification: `pytest -q` → 67 passed; `ruff check app tests` → clean.

Documentation added: `CORTEX_ARCHITECTURE.md`, `CORTEX_SECURITY.md`,
`CORTEX_DEPLOYMENT.md`, `SUPABASE_ACCESS_REQUIREMENTS.md`, `AI_GATEWAY.md`,
`AGENT_RUNNER.md`, `TESTING.md`, `CORTEX_DECISIONS.md`.

Still blocked on external access: hosted Supabase migrations/RLS, GitHub App
registration, AI provider credentials, Redis provisioning, Stripe. See
`docs/SUPABASE_ACCESS_REQUIREMENTS.md`.
