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

## Admission, reservation and settlement

Admission is a single database function, `public.enqueue_agent_run`, not a
read-then-write sequence in Python:

1. it replays `(organization_id, idempotency_key)` when the caller retries;
2. it locks the organization's entitlement row;
3. it counts active runs and compares them with `limits.max_concurrent_runs`;
4. it refuses the run when `credits_used + credits_reserved + budget` exceeds
   `credits_limit`;
5. it reserves the budget and inserts the run in the same transaction.

`public.settle_agent_run` releases the reservation, books real usage and returns
the run unchanged when it is already terminal, so a cancel, a retry or a
redelivered job cannot refund twice. `POST /api/v1/runs` forwards the
`Idempotency-Key` header to the function.

## Queue and worker

- Jobs live in a Redis Stream consumer group (`cortex:jobs`, group
  `cortex-workers`). Unacknowledged entries stay in the pending list, so a worker
  crash does not lose the job.
- A consumer reclaims pending entries idle for 60 s. Entries delivered more than
  `max_attempts` times go to `cortex:jobs:dead`.
- Failures are retried with exponential backoff (2 s, 4 s, … capped at 300 s)
  through a sorted set promoted when due.
- A per-job lock (`cortex:jobs:lock:{job_id}`, 900 s) prevents a redelivered job
  from running twice while the original consumer still holds it.
- The worker stops cleanly on SIGTERM/SIGINT, and a job that exhausts its retries
  settles its run as `failed` so credits are never left reserved.

Handlers:

| Job | Effect |
|---|---|
| `execute_agent_run` | `queued` → `provisioning` → `running`, starts an Agent Server conversation, schedules reconciliation |
| `reconcile_agent_run` | Polls the conversation, settles `completed`/`failed`, reschedules while running |
| `reap_stale_runs` | Marks active runs older than `older_than_minutes` (default 120) as `expired` |

## Environment

| Variable | Purpose |
|---|---|
| `REDIS_URL` | Queue and coordination |
| `AGENT_SERVER_URL` | OpenHands Agent Server base URL |
| `AGENT_SERVER_API_KEY` | Session key sent as `X-Session-API-Key` |
| `AGENT_SERVER_WORKSPACE_ROOT` | Parent directory for per-run workspaces |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | Durable state and settlement |

## Status in this phase

Proven with real infrastructure:

- 10 integration tests against a real `redis:7-alpine` container: idempotent
  enqueue, ack, retry with backoff, dead letter, crash reclaim, lock
  exclusivity, duplicate-delivery skip, delayed promotion.
- Local Postgres suite and the hosted development project prove atomic
  reservation, idempotent replay, concurrency limit, cross-tenant rejection,
  settlement and refund.
- 7 tests cover the runner client and the execute/reconcile handlers with a
  stubbed Agent Server transport.
- `scripts/verify-worker-hosted.py` runs the real worker against the hosted
  development project and a real Redis container. It proves both paths:
  no Agent Server configured → job dead-lettered, run `failed`, reservation
  released; stub Agent Server → conversation started, run `completed`,
  reservation released. Test data is deleted afterwards.

Not proven:

- No Agent Server is configured here, so no conversation has actually run; the
  runner raises `RunnerUnavailable` until `AGENT_SERVER_URL` is set.
- `credits_used` is settled from the run row (currently 0) because no token
  metering is wired to the Agent Server yet.
- Sandbox isolation limits (CPU, RAM, disk, network, host secrets) must be
  verified on the target container platform before beta.
