# Cortex isolation: one sandbox per run

This page describes how a Cortex run is isolated from other runs, from other
tenants, and from the host. It also records the measured limits, so a claim of
"supports N users" always has a number behind it.

## What a sandbox is

Each run gets one container. Nothing inside it is shared with another run:

| Resource | How it is separated |
|---|---|
| Workspace | Bind mount of `SANDBOX_WORKSPACE_ROOT/<org>/<run>`, created `0700` per run |
| `/tmp` | Private tmpfs, size-limited |
| Filesystem | Container root is read-only; the workspace is the only writable mount |
| Processes | Own PID namespace, `--pids-limit` |
| Network | Internal bridge network, no published ports, no host network |
| User | Never root; the container runs as the host uid (or 1000 when the API runs as root) |
| Capabilities | `--cap-drop ALL`, `--security-opt no-new-privileges` |
| CPU / RAM | `--cpus`, `--memory`, `--memory-swap` |
| Disk | Workspace usage is probed while the run is active; exceeding the budget fails the run |
| Time | `SANDBOX_TIMEOUT_SECONDS` plus a reaper that stops and deletes old sandboxes |

The Agent Server inside the container is reached through the container's
private address (`Sandbox.api_url`). The shared `AGENT_SERVER_URL` is not used
when a sandbox exists, so one tenant's conversation can never be served by
another tenant's process.

## Lifecycle

1. The worker calls `SandboxedAgentServerRunner.start()` with the run id and
   organization id.
2. The provider creates the workspace, starts the container and returns a
   `Sandbox` handle.
3. The runner waits until the Agent Server answers, then creates the
   conversation with `base_url=sandbox.api_url` and `working_dir=/workspace`.
4. The sandbox description (`id`, `workspace`, `api_url`, `image`, `run_id`,
   `organization_id`) is stored in `agent_runs.metadata.sandbox`, so a worker
   that restarts can still reach the container.
5. While the run is active, each reconcile pass calls `enforce_limits()`. An
   over-budget workspace fails the run instead of silently filling the disk.
6. On completion, failure or cancellation, the reconciler calls
   `stop_sandbox()`; a failed start removes the container immediately.

If the process crashes between steps 3 and 6, the reaper
(`provider.reap(older_than_seconds)`) removes containers past their TTL, and
their workspaces with them.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `SANDBOX_PROVIDER` | `shared` | `docker` gives every run its own container |
| `SANDBOX_IMAGE` | `ghcr.io/all-hands-ai/agent-server:latest` | Agent Server image |
| `SANDBOX_WORKSPACE_ROOT` | `/var/lib/cortex/sandboxes` | Host directory for run workspaces |
| `SANDBOX_NETWORK` | `cortex-sandboxes` | Internal bridge network |
| `SANDBOX_CPUS` | `1.0` | CPU limit per run |
| `SANDBOX_MEMORY_MB` | `2048` | Memory limit per run |
| `SANDBOX_PIDS` | `512` | Process limit per run |
| `SANDBOX_DISK_MB` | `4096` | Workspace budget per run |
| `SANDBOX_TIMEOUT_SECONDS` | `3600` | Maximum run duration |
| `SANDBOX_READY_TIMEOUT_SECONDS` | `120` | Time allowed for the Agent Server to answer |

`shared` remains the default so an existing deployment does not change
behaviour on upgrade. A deployment that enables `docker` must run the API and
worker on a host with a Docker socket, and must never expose that socket inside
a sandbox.

## What the tests prove

`apps/api/tests/test_sandbox_docker.py` runs real `alpine:3.20` containers:

- two runs of two tenants share no files (each sees only its own workspace);
- a sandbox cannot write outside its workspace, cannot reach the host
  filesystem, and cannot reach the Docker socket;
- the container user is not root;
- CPU, memory and PID limits are applied to the container;
- `reap()` stops and deletes sandboxes past the TTL;
- the disk budget rejects an over-quota workspace.

`apps/api/tests/test_sandboxed_runner.py` proves the wiring: the spec carries
the configured limits, the conversation is created against the sandbox URL,
a failed start removes the container, and a finished run stops it.

## Measured admission capacity

`scripts/loadtest_admission.py` measures `enqueue_agent_run`, the point where
concurrency, quota and budget reservation are decided. Latency is measured
inside Postgres, so it excludes HTTP and process overhead.

Local run (single Postgres container, one vCPU, 20 admissions per user):

| Users | Requests | Failures | p50 | p95 | p99 | Max |
|---|---|---|---|---|---|---|
| 10 | 200 | 0 | 0.12 ms | 4.96 ms | 18.61 ms | 26.25 ms |
| 50 | 1000 | 0 | 0.12 ms | 18.46 ms | 56.25 ms | 150.07 ms |
| 100 | 2000 | 0 | 0.13 ms | 36.33 ms | 126.71 ms | 275.05 ms |
| 50 (one shared org) | 1000 | 0 | 0.12 ms | 27.82 ms | 306.34 ms | 678.43 ms |

Reading:

- The admission path stays error-free at 100 concurrent users on one database.
- p99 grows roughly linearly with concurrency, which is what a single
  database instance looks like. It is not evidence of 1000 concurrent users.
- The shared-organization case is slower at p99 because every admission takes
  the same entitlement row lock. That serialization is intentional: it is what
  prevents overspending and exceeding the concurrency limit.

To claim 1000 users, the same script must run against a database with more
capacity (and a connection pooler), and the results recorded here. Until then,
100 concurrent admissions is the measured figure.

## Not covered yet

- The sandbox image in these tests is `alpine:3.20`; a real Agent Server image
  is heavier and its startup time must be measured separately.
- One host runs all containers. Multi-host scale needs a Kubernetes provider
  behind the same `SandboxProvider` contract.
- GPU workloads are not part of the sandbox contract; models are called through
  the AI Gateway, not inside the sandbox.
