#!/usr/bin/env bash
# Concurrent run admission on a real Postgres.
#
# Proves two invariants that only appear under real concurrency:
#   1. two different idempotency keys racing for the last concurrency slot
#      admit exactly one run;
#   2. two deliveries of the same idempotency key return the same run, create
#      one row and reserve the budget once.
#
# Usage: DATABASE_URL=postgresql://... bash scripts/verify-run-admission-race.sh
#   or:  bash scripts/verify-run-admission-race.sh "docker exec <container> psql -U postgres"
set -uo pipefail

DB_URL=$(printenv DATABASE_URL || true)
if [ $# -ge 1 ]; then
  PSQL="$*"
elif [ -n "$DB_URL" ]; then
  PSQL="psql $DB_URL"
else
  echo "Set DATABASE_URL or pass the psql command, e.g. 'docker exec pg psql -U postgres'" >&2
  exit 2
fi

run_user="$(python3 -c 'import uuid; print(uuid.uuid4())')"
run_suffix="$(date +%s)-$RANDOM"
failures=0

sql() { $PSQL -qtA -v ON_ERROR_STOP=1 -c "$1"; }

as_user() {
  $PSQL -qtA -c "set role authenticated;
    set request.jwt.claim.sub = '$run_user';
    $1" 2>&1 | tail -1
}

enqueue() { as_user "select id from public.enqueue_agent_run('$1'::uuid,null,null,null,'race','1','$2');"; }

echo "== fixtures (user $run_user)"
sql "insert into auth.users (id, email) values ('$run_user','race-$run_suffix@local');" > /dev/null
org="$(as_user "select id from public.create_organization_with_owner('race-$run_suffix','Race $run_suffix');")"
echo "org=$org"

echo '== two different keys racing for one slot'
enqueue "$org" "a-$run_suffix" > /tmp/race-a.$$ &
enqueue "$org" "b-$run_suffix" > /tmp/race-b.$$ &
wait
admitted=0
for f in /tmp/race-a.$$ /tmp/race-b.$$; do
  if grep -qE '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' "$f"; then
    admitted=$((admitted + 1))
  else
    echo "  rejected: $(tail -1 "$f")"
  fi
done
echo "admitted=$admitted (expected 1)"
[ "$admitted" -eq 1 ] || failures=$((failures + 1))

active="$(sql "select count(*) from public.agent_runs
  where organization_id='$org'::uuid and status in ('queued','provisioning','running','waiting');")"
echo "active runs=$active (expected 1)"
[ "$active" = "1" ] || failures=$((failures + 1))

sql "select public.settle_agent_run(id, 'cancelled', 0) from public.agent_runs
  where organization_id='$org'::uuid and status in ('queued','provisioning','running','waiting');" > /dev/null

echo '== the same key racing with itself'
key="same-$run_suffix"
enqueue "$org" "$key" > /tmp/race-s1.$$ &
enqueue "$org" "$key" > /tmp/race-s2.$$ &
wait
first="$(tail -1 /tmp/race-s1.$$)"
second="$(tail -1 /tmp/race-s2.$$)"
echo "delivery 1: $first"
echo "delivery 2: $second"
[ "$first" = "$second" ] || { echo "FAIL: a retry did not replay the first run"; failures=$((failures + 1)); }
rows="$(sql "select count(*) from public.agent_runs where idempotency_key='$key';")"
echo "runs stored for that key=$rows (expected 1)"
[ "$rows" = "1" ] || { echo "FAIL: the retry created a second run"; failures=$((failures + 1)); }

echo '== reservation and cleanup'
echo "reserved before settlement=$(sql "select credits_reserved from public.organization_entitlements where organization_id='$org'::uuid;")"
sql "select public.settle_agent_run(id, 'cancelled', 0) from public.agent_runs
  where organization_id='$org'::uuid and status in ('queued','provisioning','running','waiting');" > /dev/null
reserved="$(sql "select credits_reserved from public.organization_entitlements where organization_id='$org'::uuid;")"
echo "reserved after settlement=$reserved (expected 0.000000)"
[ "$reserved" = "0.000000" ] || failures=$((failures + 1))

rm -f /tmp/race-a.$$ /tmp/race-b.$$ /tmp/race-s1.$$ /tmp/race-s2.$$
if [ "$failures" -eq 0 ]; then
  echo 'PASS: concurrent admission is serialized and idempotent'
  exit 0
fi
echo "FAIL: $failures assertion(s) failed"
exit 1
