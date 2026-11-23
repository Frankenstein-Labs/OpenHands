# Supabase verification plan (development project only)

This plan proves that the SQL migrations, the RLS policies, and the multi-tenant
isolation actually work. Nothing here has been executed yet: no Supabase project
credentials are available in this environment. Do not treat any item as verified
until its command has run and its output is recorded.

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
