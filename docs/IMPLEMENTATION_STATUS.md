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
| Phase 9 — Supabase Storage/RAG | Storage + RAG implemented (code + unit tests) | Private buckets, `files` presign/list/delete routes, and `documents`/`document_chunks` with `match_document_chunks`; `POST/GET/DELETE /api/v1/documents` and `GET /api/v1/documents/search` ingest text in-process and search by cosine distance. 6 unit tests. | Embeddings are generated only when a provider returns them; hosted Supabase (pgvector) is required to verify the SQL function. |
| Phase 10 — Billing/quotas | Billing abstraction + quotas implemented | Provider-neutral billing service, plans/subscription/checkout/invoices routes, signed idempotent webhook, server-side quota and credit enforcement. 6 unit tests. | No Stripe account configured; no real charge is possible or attempted. |
| Phase 11 — SaaS/admin UI | First slice implemented | `/cortex` workspace: Supabase Auth sign-in/up/out with refresh, profile, organization switch, members/invitations, model catalogue + metered playground, usage/limits, documents + search, GitHub installations/repositories. Backed by the real FastAPI routes; 5 new tests. | Cortex surfaces are English-only (file-scoped `i18next/no-literal-string` disable) until translations land. The verify-openhands feature map does not yet cover `/cortex`, so `map coverage` reports it as unmapped. |
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

## Run execution (branch `feat/cortex-run-execution`)

- Worker queue: Redis Streams consumer group with idempotent jobs, backoff,
  dead-letter handling and crash reclaim (tested against a real Redis container).
- Run admission and settlement: `enqueue_agent_run` and `settle_agent_run`
  decide under a row lock, so concurrent requests cannot overspend or exceed the
  concurrency limit. Migration
  `20261123060000_run_idempotency_before_limit.sql` makes a concurrent retry
  replay its own run instead of failing with `P0002`.
- Runner: `AgentServerRunner` starts, polls and cancels real Agent Server
  conversations. Three contract bugs were fixed after testing against a live
  server (missing `agent_settings`/`workspace`, wrong cancel route, no LLM
  credential forwarding). See `docs/AGENT_RUNNER.md`.
- Metering: `app/worker/metering.py` prices `stats.usage_to_metrics` with the
  catalogue rates and settles exactly once, capped by the reserved budget.

Evidence for this branch:

- `cd apps/api && pytest -q` → 100 passed, 1 skipped (the skip is the live Agent
  Server test, which runs when `CORTEX_AGENT_SERVER_URL` is set).
- `bash scripts/verify-supabase-local.sh` → 5/5 steps, "migrations apply and RLS
  isolates two tenants on a fresh database".
- `bash scripts/verify-run-admission-race.sh` → PASS (one admitted run, one row
  and one reservation for a replayed key).
- Live Agent Server run: conversation finished, 8395 prompt + 36 completion
  tokens, priced at 4.2515 credits, settled once, redelivery skipped.

## Tenant isolation and security (branch `feat/cortex-tenant-isolation`)

- Sandboxes: `app/sandbox/` defines a provider contract and a Docker provider.
  Every run gets its own container: own bind-mounted workspace
  (`SANDBOX_WORKSPACE_ROOT/<org>/<run>`), own `/tmp` tmpfs, non-root user,
  `--cap-drop ALL`, `no-new-privileges`, read-only root, and an internal-only
  network with no published ports. CPU, memory, PID, disk and wall-clock limits
  are enforced (`--cpus`, `--memory`, `--pids-limit`, a disk probe and a
  reaper).
- Runner: `SandboxedAgentServerRunner` provisions the container, waits for the
  Agent Server inside it, then creates the conversation with that container's
  URL. A failed start removes the container; a finished run stops it. Sandbox
  metadata is stored on the run so a restarted worker can still reach and stop
  it. `SANDBOX_PROVIDER=docker` enables it; `shared` keeps the previous
  behaviour.
- Tenant provider keys: `organization_ai_credentials` stores Fernet ciphertext
  with no client read policy at all; admins see metadata through a definer
  function and only the service role can read ciphertext. The gateway merges
  the organization's keys per request, and per-organization rate and monthly
  token ceilings are enforced before the provider is called.
- Security assertions: `scripts/supabase-local-tenant-security.sql` proves
  cross-tenant reads and writes fail for runs, run events, files, AI
  credentials and AI settings, that a `member` cannot manage credentials, and
  that ciphertext never leaves the service role.
- Load: `scripts/loadtest_admission.py` measures the admission path with
  10/50/100 concurrent users and a contended single-organization run. Results
  and limits are recorded in `docs/CORTEX_ISOLATION.md`.

Evidence for this branch:

- `cd apps/api && pytest -q` → 131 passed, 1 skipped, including 9 tests that
  run real `alpine:3.20` containers (workspace isolation, no host/container
  escape, non-root, resource limits, reaping, disk budget).
- `bash scripts/verify-supabase-local.sh` → 6/6 steps on a fresh database.
- `scripts/loadtest_admission.py`: 100 users × 20 admissions → 2000 requests,
  0 failures, p95 36 ms, p99 127 ms on one local Postgres.

Still open: remote Supabase verification (blocked until a development project
is authorized), a real Agent Server image in the sandbox tests, and a
Kubernetes sandbox provider for multi-host scale.
