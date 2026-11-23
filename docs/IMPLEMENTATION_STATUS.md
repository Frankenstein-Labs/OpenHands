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
| Phase 7 — OpenHands runner | Control plane verified | `agent_runs`/`agent_run_events`, create/get/cancel/events routes. Admission is atomic in `enqueue_agent_run` (idempotency key, concurrency, reservation); cancel settles through `settle_agent_run`. `AgentServerRunner` starts a conversation and `execute_agent_run`/`reconcile_agent_run` drive the lifecycle. Proven locally and on the hosted development project. | No `AGENT_SERVER_URL`, so no conversation has run; token metering not wired, settled usage is 0. |
| Phase 8 — Redis/workers | Implemented and tested | Redis Streams consumer group with pending-list reclaim, exponential-backoff retries, dead-letter stream, per-job lock, graceful shutdown and dead-letter settlement. 10 integration tests against a real `redis:7-alpine` container; `apps/worker/` package and Dockerfile. | No managed Redis in production yet; single-host Redis only. |
| Phase 9 — Supabase Storage/RAG | Storage + RAG implemented (code + unit tests) | Private buckets, `files` presign/list/delete routes, and `documents`/`document_chunks` with `match_document_chunks`; `POST/GET/DELETE /api/v1/documents` and `GET /api/v1/documents/search` ingest text in-process and search by cosine distance. 6 unit tests. | Embeddings are generated only when a provider returns them; hosted Supabase (pgvector) is required to verify the SQL function. |
| Phase 10 — Billing/quotas | Billing abstraction + quotas implemented | Provider-neutral billing service, plans/subscription/checkout/invoices routes, signed idempotent webhook, server-side quota and credit enforcement. 6 unit tests. | No Stripe account configured; no real charge is possible or attempted. |
| Phase 11 — SaaS/admin UI | First slice implemented | `/cortex` workspace: Supabase Auth sign-in/up/out with refresh, profile, organization switch, members/invitations, model catalogue + metered playground, usage/limits, documents + search, GitHub installations/repositories. Backed by the real FastAPI routes; 5 new tests. | Cortex surfaces are English-only (file-scoped `i18next/no-literal-string` disable) until translations land. The verify-openhands feature map does not yet cover `/cortex`, so `map coverage` reports it as unmapped. |
| Phase 11b — Cortex identity | Implemented and tested | `src/constants/cortex-identity.ts` injected into every native conversation and the planner; product keys rebranded in all 16 locales; app title, PWA manifest, desktop loading screen, backend service name and OpenAPI title say Cortex; Cortex mark replaces the wordmark; `NOTICE` records the OpenHands attribution. | Persona is global, not per-organization; real conversation behaviour still needs an Agent Server. |
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


## Phase 9 RAG + Phase 11 Cortex UI change log (current pass)

Backend:

- `supabase/migrations/20261123051000_rag_documents.sql`: `documents`,
  `document_chunks`, org-scoped RLS, `match_document_chunks` (security invoker).
- `supabase/migrations/20261123052000_cortex0_catalog.sql`: Cortex-0 catalogue
  row as `preview` so it is listed but never marked available.
- `app/schemas/documents.py`, `app/repositories/documents.py`,
  `app/services/documents.py`, `app/api/v1/documents.py` (ingest, list, get,
  delete, semantic search).
- Platform-admin catalogue writes: `POST/PATCH /api/v1/providers` and
  `POST/PATCH /api/v1/models`, guarded by `CORTEX_PLATFORM_ADMIN_USER_IDS`
  (empty by default, so no one is an admin until configured). Writes use the
  service role; reads stay on the user JWT.
- Verification harness: `scripts/verify-supabase-isolation.py` and
  `docs/SUPABASE_VERIFICATION_PLAN.md`. The harness refuses production and
  remote URLs by default, creates two users/organizations, and asserts that
  tenant B cannot read or write tenant A's rows.

Frontend:

- `src/api/cortex/` — Supabase Auth REST (no new dependency), session refresh,
  typed `cortexFetch`, React Query hooks for every SaaS route.
- `/cortex` route tree with Overview, Organization, Models, Usage, Documents,
  Integrations and Profile pages; sidebar entry `Cortex`.
- Agent Canvas routes, components, i18n and settings are untouched except for
  the added sidebar link (the brand string is exempted from the literal-string rule).

Verification:

- Backend: `pytest -q` → 78 passed; `ruff check app tests` → clean.
- Frontend: `npm run typecheck` → 0 errors; `npm run lint` → 0 errors;
  `npm run build` → success; new Vitest files → 5 passed.
- `python scripts/verify-supabase-isolation.py` without credentials exits 1 with
  a clear message; production and remote guards were exercised.
- Known gap: the `verify-openhands` feature map does not list `/cortex`, so the
  skill's `map coverage` test fails. Per `AGENTS.md`, verification-skill maps are
  not edited by implementors; the follow-up belongs in a separate PR.

## Supabase development project: migrations and isolation verified (2026-11-23)

Project `hmqbdhkufqvbjafyubxd`. All 13 migrations applied through the Management
API (`scripts/apply-supabase-migrations.py`), recorded in `public.cortex_migrations`.

| Check | Result |
|---|---|
| Migrations applied | 13/13, ledger has 13 rows |
| Public tables | 22 |
| Storage buckets | `org-files`, `conversation-exports`, `run-artifacts`, all private |
| `scripts/verify-supabase-isolation.py` | PASS: two users, two organizations, cross-tenant reads/writes denied, role escalation denied, cleanup leaves zero users |
| Auth config | `site_url=http://localhost:5173`, redirects allow localhost:3000/5173 and `https://*.vercel.app/**` |
| API smoke (`uvicorn` + real JWT) | `/health` 200, `/models` 200, `/providers` 200, `/organizations` 200 then `POST` 201, `/profile` 200, `/usage` 200, `/models/available` 200 |

Local replay without credentials also passes: `scripts/verify-supabase-local.sh`.

Operational note: deleting a user who still owns an organization is blocked by
the `created_by` foreign keys. Transfer ownership or delete the organization
first; this is the intended safety behaviour, not a bug.

Still required: real AI provider credentials (the catalogue seeds every provider
disabled and both Cortex-0 entries as `preview`), GitHub App private key and
webhook secret, Redis for the worker, and Vercel environment variables
(`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_CORTEX_API_URL`).
