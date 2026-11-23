# Supabase verification plan (development project only)

This plan proves that the SQL migrations, the RLS policies, and the multi-tenant
isolation actually work. A development project is now connected and its state has
been probed (section 7); migrations are not applied yet because no DDL credential
was provided. Do not treat any item as verified until its command has run and its
output is recorded.

Never run this plan against a production project.

## 1. What is already prepared

- Versioned migrations in `supabase/migrations/`.
- A runnable isolation harness: `scripts/verify-supabase-isolation.py`.
- Backend RLS/RBAC tests in `apps/api/tests/` (they mock Supabase, so they prove
  application logic, not database policies).
- Static SQL validation of the usage migration with `pglast`.

## 2. Prerequisites

| Requirement | Why |
|---|---|
| A dedicated Supabase **development** project | The harness creates and deletes users and organizations |
| `supabase` CLI, Docker | Local replay of migrations before touching any remote project |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` | Harness authentication |
| `CORTEX_VERIFY_ENV=development` | Hard guard: the harness refuses any other value |
| `CORTEX_VERIFY_ALLOW_REMOTE=1` | Only if the dev project is not on localhost |

The service-role key bypasses RLS. Keep it in the shell environment only, never in
a file, a commit, or a screenshot.

## 3. Step A — replay migrations locally (no remote project)

```bash
supabase start
supabase db reset          # applies every migration to an empty database
```

Expected: the reset finishes without error. Record the migration list and any
warning. Then repeat once more to prove the migrations replay from an empty base.

Rollback: `supabase stop --no-backup` destroys only the local containers.

## 4. Step B — apply migrations to the development project

```bash
supabase link --project-ref <dev-project-ref>
supabase db push --dry-run
supabase db push
```

`--dry-run` must list exactly the migrations that are not yet applied. If it
proposes rewriting an already-applied migration, stop: add a new corrective
migration instead.

Rollback: there is no automatic down migration. Restore the dev project from its
pre-run backup (Supabase dashboard → Database → Backups) or reset the project.
Record the backup timestamp before pushing.

## 5. Step C — prove tenant isolation

```bash
export CORTEX_VERIFY_ENV=development
export SUPABASE_URL=...
export SUPABASE_ANON_KEY=...
export SUPABASE_SERVICE_ROLE_KEY=...
python scripts/verify-supabase-isolation.py
```

The harness performs these checks and exits non-zero on the first failure:

1. Creates two confirmed users and signs both in.
2. Creates one organization per user through `create_organization_with_owner`.
3. Seeds an agent, a document and a document chunk in organization A.
4. As user B, reads `agents`, `agent_runs`, `documents`, `document_chunks`,
   `files`, `usage_events`, `organization_invitations`, `github_installations`
   filtered on organization A. Every read must return zero rows.
5. As user B, patches A's agent (must affect zero rows) and inserts an agent and
   a membership into organization A (both must be rejected).
6. Confirms organization A still reads its own rows.
7. Deletes the two test organizations and users.

The script prints no keys, and it deletes what it creates. If a step fails, the
test users and organizations may remain: delete them from the dev project before
rerunning.

## 6. Step D — Storage policies

Storage objects are not covered by the Python harness. Verify manually:

1. Create the `org-files`, `conversation-exports`, `run-artifacts` buckets as
   private.
2. With user A's JWT, upload `org-a/test.txt` through the presign flow.
3. With user B's JWT, request a signed URL for the same object. Expect 403.
4. Confirm an anonymous request cannot download the object.

Record the status codes.

## 7. Step E — record evidence

For each step, capture: command, timestamp, exit code, and a redacted excerpt of
the output. Store it under `docs/verification/` (do not include keys, JWTs, or
emails of real people). Only then may the corresponding checkbox in
`docs/IMPLEMENTATION_STATUS.md` be marked done.

## 8. What this plan does not cover

- Production data, billing providers, and AI provider calls.
- Load or concurrency testing.
- Backup/restore drills, which need a paid plan or a local dump/restore cycle.

Those remain separate, later phases.


## 7. Session evidence (2026-11-23)

Project `hmqbdhkufqvbjafyubxd` (`https://hmqbdhkufqvbjafyubxd.supabase.co`).

New-style API keys are used, not legacy JWTs:

| Dashboard label | Environment variable |
|---|---|
| Publishable key (`sb_publishable_...`) | `SUPABASE_ANON_KEY` |
| Secret key (`sb_secret_...`) | `SUPABASE_SERVICE_ROLE_KEY` (server only) |

Observed:

| Probe | Result |
|---|---|
| `GET /auth/v1/health` | 200, GoTrue v2.198.0 |
| `GET /rest/v1/` with publishable key | 401 "Secret API key required" (expected) |
| `GET /rest/v1/` with secret key | 200, **0 tables** |
| `GET /rest/v1/organizations` | `PGRST205`, table does not exist |
| `GET /auth/v1/settings` | email signup enabled, `mailer_autoconfirm=false`, no `site_url`, no redirect allow list |
| Isolation harness | creates two users and signs them in, then stops at step 2 with `PGRST202` (`create_organization_with_owner` missing) and removes both users |

So: authentication works, the schema is empty, and nothing is at risk. Applying
the migrations is the next step.

## 8. Applying the migrations

Two supported paths.

### Management API (no database password)

Needs a Supabase personal access token (`sbp_...`) with access to the project:

```bash
export SUPABASE_ACCESS_TOKEN=sbp_...
export SUPABASE_PROJECT_REF=hmqbdhkufqvbjafyubxd
python scripts/apply-supabase-migrations.py --dry-run --confirm-project "$SUPABASE_PROJECT_REF"
python scripts/apply-supabase-migrations.py --confirm-project "$SUPABASE_PROJECT_REF"
```

The script applies `supabase/migrations/*.sql` in filename order inside one
transaction per file and records each version in `public.cortex_migrations`, so a
rerun only applies what is missing.

### Direct connection

```bash
supabase link --project-ref hmqbdhkufqvbjafyubxd --password '<db password>'
supabase db push
```

## 9. Auth configuration still required

- Set the site URL and redirect allow list (`http://localhost:5173`,
  `https://<vercel-domain>/cortex`) or confirmation links will not come back to
  the app.
- Decide whether email confirmation stays required. The harness creates users
  with `email_confirm: true`, so it does not depend on the mailer.
- Google and GitHub OAuth remain disabled until client ids are configured.

## 10. Harness cleanup guarantee

`scripts/verify-supabase-isolation.py` now deletes the users and organizations it
creates in a `finally` block, including when a step fails. Verified: a failing run
left zero users behind.


## 11. Local proof (executed 2026-11-23)

The hosted project still has no DDL credential, so the migrations and policies
were proven on a disposable Postgres that emulates the Supabase auth surface.

```bash
scripts/verify-supabase-local.sh
```

What it does:

1. starts `pgvector/pgvector:pg16` in Docker;
2. creates `auth.users`, `auth.uid()`, `storage.buckets`, `storage.objects` and
   the `anon` / `authenticated` / `service_role` roles
   (`scripts/supabase-local-bootstrap.sql`);
3. applies all 13 migrations with `ON_ERROR_STOP=1`;
4. grants table privileges the way Supabase does, so the assertions test
   policies rather than missing grants;
5. runs `scripts/supabase-local-rls.sql`.

Result: `PASS`, exit 0, zero assertion failures. Covered:

- two organizations created through `create_organization_with_owner`;
- tenant B reads 0 rows from tenant A's `agents`, `documents`,
  `document_chunks`, `organizations` and `organization_memberships`;
- tenant B's `UPDATE` of tenant A's agent affects 0 rows;
- tenant B's cross-tenant `INSERT` into `agents` is rejected;
- tenant B's self-escalation through `organization_memberships` and
  `add_organization_member` is rejected;
- tenant A still sees its own rows;
- signed-out `anon` sees 0 rows;
- `service_role` sees both organizations;
- the three private buckets exist and none is public.

This proves the SQL. It does not replace running the same harness against the
hosted development project, which needs a token that belongs to the account that
owns the project.
