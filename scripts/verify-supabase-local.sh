#!/usr/bin/env bash
# Prove the migrations and RLS policies on a local Postgres with a Supabase-like
# auth schema. No remote project and no credential are involved.
#
#   scripts/verify-supabase-local.sh
#
# Requires Docker. Set CORTEX_KEEP_PG=1 to keep the container for inspection.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE=$(printenv CORTEX_PG_IMAGE || true)
if [ -z "$IMAGE" ]; then IMAGE=pgvector/pgvector:pg16; fi
NAME=$(printenv CORTEX_PG_CONTAINER || true)
if [ -z "$NAME" ]; then NAME=cortex-local-pg; fi
KEEP=$(printenv CORTEX_KEEP_PG || true)

cleanup() {
  if [ "$KEEP" != "1" ]; then
    docker rm -f "$NAME" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" -e POSTGRES_PASSWORD=postgres "$IMAGE" >/dev/null

for _ in $(seq 1 60); do
  if docker exec "$NAME" pg_isready -U postgres -q 2>/dev/null; then
    break
  fi
  sleep 1
done
docker exec "$NAME" pg_isready -U postgres -q

psql_run() { docker exec "$NAME" psql -U postgres -v ON_ERROR_STOP=1 -q "$@" < /dev/null; }
psql_file() { local file="$1"; shift; docker exec -i "$NAME" psql -U postgres -v ON_ERROR_STOP=1 -q "$@" -f - < "$file"; }

echo '1/6 bootstrapping Supabase-like auth and storage schemas'
psql_file "$ROOT/scripts/supabase-local-bootstrap.sql"

echo '2/6 applying migrations'
for file in "$ROOT"/supabase/migrations/*.sql; do
  echo "   $(basename "$file")"
  psql_file "$file"
done

# Supabase grants table privileges to the API roles by default; reproduce that so
# the assertions test policies, not missing grants.
psql_run -c "
  grant usage on schema public to anon, authenticated, service_role;
  grant select on all tables in schema public to anon;
  grant select, insert, update, delete on all tables in schema public to authenticated, service_role;
  grant usage, select on all sequences in schema public to authenticated, service_role;
"

echo '3/6 running isolation assertions'
docker exec -i "$NAME" psql -U postgres -v ON_ERROR_STOP=1 -tA -f - \
  < "$ROOT/scripts/supabase-local-rls.sql"

echo '4/6 running run-admission and settlement assertions'
docker exec -i "$NAME" psql -U postgres -v ON_ERROR_STOP=1 -tA -f - \
  < "$ROOT/scripts/supabase-local-run-controls.sql"

echo '5/6 running tenant security assertions'
docker exec -i "$NAME" psql -U postgres -v ON_ERROR_STOP=1 -tA -f - \
  < "$ROOT/scripts/supabase-local-tenant-security.sql"

echo '6/6 done'
echo 'PASS: migrations apply and RLS isolates two tenants on a fresh database'
