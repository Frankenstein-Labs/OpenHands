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

## Status in this phase

- Control plane (quota checks, run rows, events, cancellation, cleanup) is
  implemented and unit-tested.
- Sandbox provisioning itself is delegated to the OpenHands Agent Server and is
  not yet executed against a hosted runner in this environment.
- Real isolation limits must be verified on the target container platform before
  beta.
