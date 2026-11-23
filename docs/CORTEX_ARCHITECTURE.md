# Cortex.ai architecture

Cortex.ai is the SaaS layer built around the existing OpenHands Agent Canvas
frontend and the OpenHands agent engine. The Canvas UI, conversations, agent
server integration, ACP agents, terminal, Monaco editor, workspaces, MCP and
automations stay in place; Cortex adds identity, tenancy, metering and control
plane services around them.

## Components

| Layer | Location | Responsibility |
|---|---|---|
| Frontend | `src/` (Agent Canvas) | Chat, workspaces, files, terminal, settings, SaaS screens. Hosted on Vercel. No persistent agent runtime in Vercel functions. |
| SaaS API | `apps/api/app` | FastAPI control plane: auth/profile, organizations, memberships, invitations, agents, runs, usage, files, billing, GitHub App, AI gateway. |
| Worker | `apps/worker` + `apps/api/app/worker` | Redis-backed async jobs sharing the API's repositories and settings. |
| Database / identity | `supabase/migrations` | PostgreSQL schema, RLS policies, SQL functions, private Storage buckets. |
| Agent engine | OpenHands Agent Server | Executes agent turns in an isolated environment. Cortex owns lifecycle, quotas and metering, not the agent loop. |

## Data flow

1. The browser authenticates with Supabase Auth and holds a JWT.
2. Every API call forwards that JWT to PostgREST, so RLS evaluates the real
   user. The API never trusts a client-supplied organization or role.
3. `GET /api/v1/auth/me` plus the organization context dependency resolve the
   active organization and role server-side.
4. Creating a run checks entitlement, concurrent-run quota and reserved budget,
   writes an `agent_runs` row, and enqueues a job. Execution is delegated to the
   Agent Server; run events are persisted in `agent_run_events`.
5. Usage is written as `usage_events` rows with an idempotency key. PostgreSQL
   stays the durable source of truth; Redis is only a queue.

## Module layout (`apps/api/app`)

- `api/v1/*` — thin routes, one module per resource.
- `schemas/*` — Pydantic request/response contracts.
- `services/*` — business rules, quota and authorization decisions.
- `repositories/*` — PostgREST access, one table family per repository.
- `github/` — GitHub App JWT signing and webhook signature verification.
- `ai_gateway/` — provider-neutral model access and metering.
- `worker/` — job envelope, Redis queue, handlers.
- `database/` — Supabase REST and Storage clients.

## Ownership boundaries

- Frontend state owns presentation only. Tenancy, roles, quotas and costs are
  server decisions.
- The API owns business rules. Repositories never contain policy.
- PostgreSQL owns durable facts (memberships, runs, usage, files, billing).
- The agent engine owns execution. It receives scoped credentials, never
  host secrets.

## Non-goals in this phase

- No microservice split: the AI gateway and runner are modules, not separate
  deployables, until load requires it.
- No payment provider is wired live; billing is an abstraction with an explicit
  "not configured" state.
- No permanent GPU fleet. Users consume configured providers and runners.
