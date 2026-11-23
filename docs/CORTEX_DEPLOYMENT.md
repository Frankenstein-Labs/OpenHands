# Cortex.ai deployment

## Topology

| Service | Platform | Notes |
|---|---|---|
| Frontend | Vercel | Static/SSR build of Agent Canvas. No persistent agent runtime in serverless functions. |
| SaaS API | Container host (Fly.io, Cloud Run, ECS, K8s) | `apps/api/Dockerfile`, port 8000, `/health` and `/readiness`. |
| Worker | Container host | `apps/worker/Dockerfile`, runs `python -m worker.main`, needs `REDIS_URL`. |
| Database/Auth/Storage | Supabase | Migrations in `supabase/migrations`, applied with the Supabase CLI. |
| Redis | Managed Redis | Queue and coordination only; never the billing source of truth. |
| Agent Server | OpenHands deployment | Must run on a container-capable platform, not Vercel. |
| AI providers | External | Server-side keys only. |

Do not use Render for this stack.

## Required environment

API and worker share these server-only variables (see `apps/api/.env.example`):

```
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_JWT_ISSUER=
SUPABASE_JWT_AUDIENCE=authenticated
REDIS_URL=
GITHUB_APP_ID=
GITHUB_APP_SLUG=
GITHUB_APP_PRIVATE_KEY=
GITHUB_WEBHOOK_SECRET=
GITHUB_API_BASE_URL=https://api.github.com
AI_GATEWAY_* / provider keys
BILLING_PROVIDER=none
```

Frontend variables are limited to the Supabase URL/anon key and the API base
URL. No secret ever uses a `NEXT_PUBLIC_`/`VITE_` prefix.

## Health checks

- `GET /health` — process is up.
- `GET /readiness` — configuration is complete (Supabase settings present).
- Worker: container restart policy plus Redis connectivity; jobs are idempotent
  and retried, so a restart is safe.

## Deploy order

1. Apply migrations to a Supabase **development** project and run the RLS
   verification script.
2. Deploy the API container with the anon key + service-role key.
3. Deploy the worker container with the same settings and `REDIS_URL`.
4. Point the frontend at the API base URL and Supabase project.
5. Configure the GitHub App callback/webhook URLs.
6. Run the smoke checklist in `docs/TESTING.md`.

## Rollback

- Application: redeploy the previous image tag; no database change is needed.
- Database: migrations are additive. Corrective migrations are new files, never
  edits to applied ones. For a bad deploy, roll back code first; only revert SQL
  with a reviewed, backed-up corrective migration.
- Worker: scale to zero safely; queued jobs remain in Redis and durable state
  stays in PostgreSQL.

## Cost policy

No paid resource is created automatically. Redis, container hosts and any
provider plan require explicit approval before provisioning.
