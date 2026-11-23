# Cortex.ai decision log (ADR)

## ADR-001 — Keep Agent Canvas and the OpenHands engine

Status: accepted.

We build SaaS services around the existing React/TypeScript Canvas and the
OpenHands Agent Server. Rewriting chat, terminal, workspaces or MCP would
duplicate working behavior and break compatibility.

## ADR-002 — Supabase as identity, database and storage

Status: accepted.

Supabase Auth is the only identity provider; PostgreSQL with RLS is the tenant
authority; Storage holds private files. This avoids a second password store and
gives database-enforced isolation.

## ADR-003 — FastAPI control plane, not a second agent runtime

Status: accepted.

`apps/api` owns authorization, quotas, metering and lifecycle. Agent execution
stays in the Agent Server. FastAPI never executes user commands.

## ADR-004 — AI gateway as a module, not a microservice

Status: accepted.

A provider-neutral package inside the API keeps deployment simple while
remaining independently testable. It can be extracted later if load requires it.

## ADR-005 — Redis is a queue, PostgreSQL is the ledger

Status: accepted.

Jobs may be retried or lost and re-enqueued; usage and billing facts are written
transactionally to PostgreSQL. `record_usage_event` inserts the event and
increments consumed credits atomically and idempotently.

## ADR-006 — Additive, corrective migrations only

Status: accepted.

Applied migrations are never edited. Fixes ship as new timestamped files (for
example `20261123050000_usage_accounting.sql`).

## ADR-007 — No provider or payment is claimed without a real call

Status: accepted.

Providers start disabled; billing has an explicit `none` provider. The API
returns 503/404/402 honestly instead of simulating success.
