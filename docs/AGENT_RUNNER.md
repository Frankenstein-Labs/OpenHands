# OpenHands Agent Runner (Cortex control plane)

Cortex does not reimplement the agent. The OpenHands Agent Server executes
turns; Cortex owns identity, quotas, lifecycle, metering and cleanup.

## Run lifecycle

Statuses (enforced by `agent_runs.status`): `queued`, `provisioning`, `running`,
`waiting`, `completed`, `failed`, `cancelled`, `expired`.

1. Authenticate the user and resolve the organization and role.
2. Check entitlement and concurrent-run quota.
3. Reserve budget (`credits_reserved`) and insert an `agent_runs` row.
4. Enqueue a worker job for provisioning.
5. Connect to the Agent Server with scoped, temporary credentials.
6. Stream progress as `agent_run_events` rows.
7. Record usage, settle reserved credits, and release the environment.
8. On timeout or failure, mark `expired`/`failed` and clean up.

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/runs` | Create a run after quota and budget checks |
| `GET` | `/api/v1/runs/{id}` | Run status |
| `POST` | `/api/v1/runs/{id}/cancel` | Cancel an active run |
| `GET` | `/api/v1/runs/{id}/events` | Ordered run events |

## Quotas and budget

- Concurrent runs are limited by `limits.max_concurrent_runs` from the plan.
- `budget_credits` is reserved at creation and cannot exceed remaining credits.
- A run that is cancelled or fails before consuming resources is moved to a
  terminal state; reserved credits are released according to the settlement
  rules in the runs service.

## Isolation (target design)

- One sandbox per run: separate filesystem, process namespace, CPU, RAM, disk
  and network policy.
- No host Docker socket, no host secrets, no access to cloud metadata endpoints.
- Commands run in the sandbox, never in the FastAPI process.
- Hard timeout and automatic teardown; idle environments are reaped by the
  worker (`reap_stale_runs`).

## Worker cleanup

`apps/api/app/worker/handlers.py::reap_stale_runs` marks active runs older than
`older_than_minutes` (default 120) as `expired`, so abandoned runs cannot hold
quotas forever. The job is idempotent.

## Agent Server contract (verified against a live server)

`apps/api/app/runner/agent_server.py` talks to the OpenHands Agent Server over
its REST API. Driving it against a real server (1.63.1) corrected three
assumptions that a fake runner cannot expose:

| Call | Endpoint | Notes |
|---|---|---|
| Start | `POST /api/conversations` | The body **must** carry `agent_settings` (even `{}`) and `workspace`; without them the server answers `422`. |
| Status | `GET /api/conversations/{id}` | `execution_status` is the field to read; token usage lives in `stats.usage_to_metrics`. |
| Cancel | `POST /api/conversations/{id}/interrupt` | There is no `/stop` route (`404`). |

The server never inherits its own settings into a conversation: a conversation
created without credentials fails with `LLMAuthenticationError`. The runner
therefore forwards the deployment's LLM configuration:

| Variable | Purpose |
|---|---|
| `AGENT_SERVER_URL` | Base URL of the Agent Server |
| `AGENT_SERVER_API_KEY` | Session key sent as `X-Session-API-Key` |
| `AGENT_SERVER_WORKSPACE_ROOT` | Default `working_dir` when the run does not set one |
| `AGENT_SERVER_LLM_MODEL` | Model id, with its provider prefix (`openai/gpt-5.6`) |
| `AGENT_SERVER_LLM_BASE_URL` | OpenAI-compatible endpoint |
| `AGENT_SERVER_LLM_API_KEY` | Server-only credential; never sent to the browser |

Per-organization model selection will come from the AI Gateway; until then a run
uses the deployment-level LLM above.

## Metering

`apps/api/app/worker/metering.py` prices what the agent actually consumed:

1. `accumulated_usage()` sums `prompt_tokens` and `completion_tokens` over every
   profile in `stats.usage_to_metrics` (the main agent and the condenser each
   report their own counters).
2. `credits_for_usage()` applies `models.input_cost_per_1k` and
   `models.output_cost_per_1k` of the run's model.
3. The charge is capped at `agent_runs.budget_credits`, so one run can never push
   an organization past the limit it was admitted under. A model without a
   published price books `0` instead of inventing a cost.

`reconcile_agent_run` passes the computed amount to `settle_agent_run`, which
releases the reservation and books `credits_used` in one transaction. Settlement
is idempotent, so a redelivered reconciliation cannot charge twice.

## Admission under concurrency

`enqueue_agent_run` (migration `20261123060000_run_idempotency_before_limit.sql`)
re-checks the idempotency key *after* taking the entitlement row lock. Before
that, two concurrent deliveries of one request both passed the pre-check, and
the loser failed with `P0002 concurrent run limit reached` instead of replaying
the run it had already created.

`scripts/verify-run-admission-race.sh` proves both invariants against a real
Postgres: two different keys racing for the last slot admit exactly one run, and
two deliveries of the same key return the same run with one row and one
reservation.

## Verification commands

```bash
# Unit and contract tests (no external service needed)
cd apps/api && pytest -q

# Real Agent Server (creates and cancels a conversation)
CORTEX_AGENT_SERVER_URL=http://127.0.0.1:60000 \
CORTEX_AGENT_SERVER_API_KEY=... \
CORTEX_AGENT_SERVER_LLM_MODEL=openai/gpt-5.6 \
CORTEX_AGENT_SERVER_LLM_BASE_URL=... \
CORTEX_AGENT_SERVER_LLM_API_KEY=... \
pytest -q tests/test_runner_handlers.py -k real_conversation

# Schema, RLS and run controls on a throwaway Postgres
bash scripts/verify-supabase-local.sh

# Concurrent admission on a real Postgres
DATABASE_URL=postgresql://... bash scripts/verify-run-admission-race.sh
```

## Status in this phase

- Control plane (quota checks, run rows, events, cancellation, cleanup) is
  implemented and unit-tested.
- Start, status and cancel were exercised against a live Agent Server, including
  a completed run whose token usage was priced and settled exactly once.
- Sandbox provisioning is delegated to the OpenHands Agent Server. Container
  isolation limits (CPU, RAM, disk, network, egress) still have to be verified on
  the target platform before beta, and each tenant does not yet get its own
  container.
