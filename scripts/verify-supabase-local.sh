#!/usr/bin/env bash
# Prove the migrations and RLS policies on a local Postgres with a Supabase-like
# auth schema. No remote project and no credential are involved.
#
#   scripts/verify-supabase-local.sh
#
# Requires Docker. Set CORTEX_KEEP_PG=1 to keep the container for inspection.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE="${CORTEX_PG_IMAGE:-pgvector/pgvector:pg16}"
NAME="${CORTEX_PG_CONTAINER:-cortex-local-pg}"

cleanup() {
  if [ "${CORTEX_KEEP_PG:-0}" != "1" ]; then
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

psql_run() { docker exec -i "$NAME" psql -U postgres -v ON_ERROR_STOP=1 -q "$@"; }

echo '1/4 bootstrapping Supabase-like auth and storage schemas'
psql_run -f - < "$ROOT/scripts/supabase-local-bootstrap.sql"

echo '2/4 applying migrations'
for file in "$ROOT"/supabase/migrations/*.sql; do
  echo "   $(basename "$file")"
  psql_run -f - < "$file"
done

# Supabase grants table privileges to the API roles by default; reproduce that so
# the assertions test policies, not missing grants.
psql_run -c "
  grant usage on schema public to anon, authenticated, service_role;
  grant select on all tables in schema public to anon;
  grant select, insert, update, delete on all tables in schema public to authenticated, service_role;
  grant usage, select on all sequences in schema public to authenticated, service_role;
"

echo '3/4 running isolation assertions'
psql_run -tA -f - < "$ROOT/scripts/supabase-local-rls.sql"

echo '4/4 done'
echo 'PASS: migrations apply and RLS isolates two tenants on a fresh database'
