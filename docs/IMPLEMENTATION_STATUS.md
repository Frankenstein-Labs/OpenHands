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
| Phase 5 — GitHub App | Not started | Existing Git integrations are not a per-customer GitHub App implementation. | Requires GitHub App registration and server-side installation flow. |
| Phase 6 — AI Gateway | Not started | Existing model/provider services are client/backend adapters, not the SaaS cost authority. | Requires server-side provider credential and usage design. |
| Phase 7 — OpenHands runner | Not started | Existing Agent Server integrations remain the compatibility base. | Requires secure runner boundary and quota checks. |
| Phase 8 — Redis/workers | Not started | No SaaS worker service exists in this repository. | Requires FastAPI job contracts. |
| Phase 9 — Supabase Storage/RAG | Not started | No Supabase Storage buckets or ingestion pipeline exists. | Requires private bucket policy and file ACL design. |
| Phase 10 — Billing/quotas | Not started | No payment provider, plans or server entitlements exist. | Provider remains intentionally decoupled; implement after usage authority. |
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
