\set ON_ERROR_STOP on

create function pg_temp.assert_true(ok boolean, msg text) returns void language plpgsql as $$
begin
  if not coalesce(ok, false) then
    raise exception 'ASSERT FAILED: %', msg;
  end if;
end $$;

create function pg_temp.expect_sqlstate(expected text, stmt text) returns void language plpgsql as $$
begin
  begin
    execute stmt;
    raise exception 'ASSERT FAILED: statement should have failed: %', stmt;
  exception
    when others then
      if sqlstate <> expected then
        raise exception 'ASSERT FAILED: expected % for %, got % (%)', expected, stmt, sqlstate, sqlerrm;
      end if;
  end;
end $$;

create function pg_temp.expect_enqueue_error(
  expected text, org uuid, label text, idem_key text, budget numeric
) returns void language plpgsql as $$
begin
  perform pg_temp.expect_sqlstate(
    expected,
    format(
      'select public.enqueue_agent_run(%L::uuid, null, null, null, %L, %s, %L)',
      org, label, budget, idem_key
    )
  );
end $$;

create function pg_temp.expect_settle_error(expected text, run_id uuid) returns void language plpgsql as $$
begin
  perform pg_temp.expect_sqlstate(
    expected,
    format('select public.settle_agent_run(%L::uuid, %L, 0)', run_id, 'running')
  );
end $$;

insert into auth.users (id, email) values
  ('00000000-0000-4000-8000-00000000000c', 'runs-a@local'),
  ('00000000-0000-4000-8000-00000000000d', 'runs-b@local');

set role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-4000-8000-00000000000c', false);
select set_config(
  'test.org_a',
  (select id::text from public.create_organization_with_owner('runs-a', 'Runs A')),
  false
);
select set_config('test.org_b', '', false);

-- A first run reserves its budget.
select set_config(
  'test.run_1',
  (select id::text from public.enqueue_agent_run(
    current_setting('test.org_a')::uuid, null, null, null, 'first', 60, 'key-1'
  )),
  false
);
select pg_temp.assert_true(
  (select credits_reserved from public.organization_entitlements
    where organization_id = current_setting('test.org_a')::uuid) = 60,
  'budget was not reserved'
);

-- Replaying the same idempotency key returns the same run and reserves nothing.
select pg_temp.assert_true(
  (select id::text from public.enqueue_agent_run(
    current_setting('test.org_a')::uuid, null, null, null, 'first', 60, 'key-1'
  )) = current_setting('test.run_1'),
  'idempotent replay created a second run'
);
select pg_temp.assert_true(
  (select credits_reserved from public.organization_entitlements
    where organization_id = current_setting('test.org_a')::uuid) = 60,
  'idempotent replay reserved credits twice'
);

-- The free plan allows one concurrent run.
select pg_temp.expect_enqueue_error(
  'P0002', current_setting('test.org_a')::uuid, 'second', 'key-2', 1
);

-- Another tenant cannot enqueue into this organization.
reset role;
set role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-4000-8000-00000000000d', false);
select pg_temp.expect_enqueue_error(
  '42501', current_setting('test.org_a')::uuid, 'intruder', 'key-3', 1
);

-- Settlement releases the reservation and books the real usage.
reset role;
set role service_role;
select set_config(
  'test.settled_1',
  (select status from public.settle_agent_run(current_setting('test.run_1')::uuid, 'completed', 25)),
  false
);
select pg_temp.assert_true(current_setting('test.settled_1') = 'completed', 'run was not settled');
select pg_temp.assert_true(
  (select credits_reserved = 0 and credits_used = 25
     from public.organization_entitlements
    where organization_id = current_setting('test.org_a')::uuid),
  'settlement did not release the reservation or book usage'
);

-- Settling twice must not double-charge.
select public.settle_agent_run(current_setting('test.run_1')::uuid, 'completed', 25);
select pg_temp.assert_true(
  (select credits_used from public.organization_entitlements
    where organization_id = current_setting('test.org_a')::uuid) = 25,
  'second settlement charged the tenant twice'
);

-- A budget above the remaining credits is refused even under the concurrency cap.
reset role;
update public.organization_entitlements
set credits_limit = 30
where organization_id = current_setting('test.org_a')::uuid;

set role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-4000-8000-00000000000c', false);
select pg_temp.expect_enqueue_error(
  'P0003', current_setting('test.org_a')::uuid, 'too-big', 'key-4', 10
);

-- A budget inside the remaining credits is accepted.
select set_config(
  'test.run_2',
  (select id::text from public.enqueue_agent_run(
    current_setting('test.org_a')::uuid, null, null, null, 'fits', 4, 'key-5'
  )),
  false
);
select pg_temp.assert_true(
  (select credits_reserved from public.organization_entitlements
    where organization_id = current_setting('test.org_a')::uuid) = 4,
  'accepted run did not reserve its budget'
);

-- Cancelling through settlement refunds the reservation.
reset role;
set role service_role;
select public.settle_agent_run(current_setting('test.run_2')::uuid, 'cancelled', 0);
select pg_temp.assert_true(
  (select credits_reserved = 0 and credits_used = 25
     from public.organization_entitlements
    where organization_id = current_setting('test.org_a')::uuid),
  'cancellation did not refund the reservation'
);

-- Terminal runs cannot be settled with an invalid status.
select pg_temp.expect_settle_error('22023', current_setting('test.run_1')::uuid);
