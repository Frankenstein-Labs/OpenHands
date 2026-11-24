\set ON_ERROR_STOP on

-- Multi-tenant security assertions for the tables added by the isolation phase:
-- run events, files, per-organization AI credentials and AI settings.
--
-- Everything runs through the `authenticated` role, exactly like a browser
-- session, so these assertions fail if RLS or a definer function is wrong.

create function pg_temp.assert_true(ok boolean, msg text) returns void language plpgsql as $$
begin
  if not coalesce(ok, false) then
    raise exception 'ASSERT FAILED: %', msg;
  end if;
end $$;

create function pg_temp.assert_raises(stmt text, msg text) returns void language plpgsql as $$
begin
  begin
    execute stmt;
  exception when others then
    return;
  end;
  raise exception 'ASSERT FAILED (expected a rejection): %', msg;
end $$;

insert into auth.users (id, email) values
  ('00000000-0000-4000-8000-0000000000c1', 'sec-a@local'),
  ('00000000-0000-4000-8000-0000000000c2', 'sec-b@local'),
  ('00000000-0000-4000-8000-0000000000c3', 'sec-a-member@local');

-- A catalogue provider must exist for the credential foreign key.
insert into public.ai_providers (id, name, kind, enabled)
values ('sec-provider', 'Security provider', 'openai_compatible', false)
on conflict (id) do nothing;

-- Tenant A (owner) creates its organization and private data.
set role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-4000-8000-0000000000c1', false);
select set_config(
  'test.org_a',
  (select id::text from public.create_organization_with_owner('sec-a', 'Security A')),
  false
);
select set_config('test.user_a', '00000000-0000-4000-8000-0000000000c1', false);

insert into public.agents (organization_id, created_by, name)
values (current_setting('test.org_a')::uuid, auth.uid(), 'A agent');

insert into public.agent_runs (organization_id, created_by, prompt, status)
values (current_setting('test.org_a')::uuid, auth.uid(), 'secret prompt', 'queued');

insert into public.files (organization_id, created_by, bucket, object_path)
values (
  current_setting('test.org_a')::uuid, auth.uid(), 'org-files',
  current_setting('test.org_a') || '/private.txt'
);

select public.set_organization_ai_credential(
  current_setting('test.org_a')::uuid, 'sec-provider', 'gAAAAA-ciphertext-for-tenant-a', 'aaaa'
);
select public.set_organization_ai_settings(current_setting('test.org_a')::uuid, null, 5000, 1.5);
select public.add_organization_member(
  current_setting('test.org_a')::uuid, '00000000-0000-4000-8000-0000000000c3', 'member'
);

-- Run events are written by the runner, never by a browser session.
reset role;
insert into public.agent_run_events (run_id, organization_id, seq, type, payload)
select id, organization_id, 0, 'started', '{"note":"a secret"}'::jsonb
from public.agent_runs where organization_id = current_setting('test.org_a')::uuid;

-- Tenant B creates its own organization.
set role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-4000-8000-0000000000c2', false);
select set_config(
  'test.org_b',
  (select id::text from public.create_organization_with_owner('sec-b', 'Security B')),
  false
);

-- ---------------------------------------------------------------------------
-- Cross-tenant reads
-- ---------------------------------------------------------------------------
select pg_temp.assert_true(
  (select count(*) from public.agent_runs
    where organization_id = current_setting('test.org_a')::uuid) = 0,
  'tenant B can read tenant A runs'
);
select pg_temp.assert_true(
  (select count(*) from public.agent_run_events
    where organization_id = current_setting('test.org_a')::uuid) = 0,
  'tenant B can read tenant A run events'
);
select pg_temp.assert_true(
  (select count(*) from public.files
    where organization_id = current_setting('test.org_a')::uuid) = 0,
  'tenant B can read tenant A files'
);
select pg_temp.assert_true(
  (select count(*) from public.organization_ai_credentials
    where organization_id = current_setting('test.org_a')::uuid) = 0,
  'tenant B can read tenant A encrypted provider keys'
);
select pg_temp.assert_true(
  (select count(*) from public.organization_ai_settings
    where organization_id = current_setting('test.org_a')::uuid) = 0,
  'tenant B can read tenant A AI settings'
);

-- ---------------------------------------------------------------------------
-- Cross-tenant writes and privilege escalation
-- ---------------------------------------------------------------------------
select pg_temp.assert_raises(
  format(
    'select public.set_organization_ai_credential(%L::uuid, %L, %L, %L)',
    current_setting('test.org_a'), 'sec-provider', 'gAAAAA-intruder', 'zzzz'
  ),
  'tenant B wrote a credential for tenant A'
);
select pg_temp.assert_raises(
  format(
    'select public.set_organization_ai_settings(%L::uuid, null, 1, 1)',
    current_setting('test.org_a')
  ),
  'tenant B changed the AI settings of tenant A'
);
select pg_temp.assert_raises(
  format(
    'select public.revoke_organization_ai_credential(%L::uuid, %L)',
    current_setting('test.org_a'), 'sec-provider'
  ),
  'tenant B revoked a credential of tenant A'
);

-- A plain member of tenant A must not be able to manage its AI credentials.
reset role;
set role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-4000-8000-0000000000c3', false);
select pg_temp.assert_raises(
  format(
    'select public.set_organization_ai_credential(%L::uuid, %L, %L, %L)',
    current_setting('test.org_a'), 'sec-provider', 'gAAAAA-member-write', 'mmmm'
  ),
  'a member escalated to manage provider credentials'
);
select pg_temp.assert_true(
  (select count(*) from public.list_organization_ai_credentials(
    current_setting('test.org_a')::uuid)) = 0,
  'a member can read provider key metadata'
);
-- Members still see the (secret-free) AI settings of their organization.
select pg_temp.assert_true(
  (select count(*) from public.organization_ai_settings
    where organization_id = current_setting('test.org_a')::uuid) = 1,
  'a member cannot read its own organization AI settings'
);

-- ---------------------------------------------------------------------------
-- The owner still sees metadata, never ciphertext
-- ---------------------------------------------------------------------------
reset role;
set role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-4000-8000-0000000000c1', false);
select pg_temp.assert_true(
  (select count(*) from public.list_organization_ai_credentials(
    current_setting('test.org_a')::uuid)) = 1,
  'the owner cannot see its own credential metadata'
);
select pg_temp.assert_true(
  (select key_last4 from public.list_organization_ai_credentials(
    current_setting('test.org_a')::uuid)) = 'aaaa',
  'credential metadata does not report the stored last4'
);
select pg_temp.assert_true(
  (select count(*) from public.organization_ai_credentials
    where organization_id = current_setting('test.org_a')::uuid) = 0,
  'an authenticated session can read ciphertext directly'
);

-- The gateway path (service role) is the only reader of ciphertext.
reset role;
set role service_role;
select pg_temp.assert_true(
  (select count(*) from public.organization_ai_credential_secrets(
    current_setting('test.org_a')::uuid)) = 1,
  'the service role cannot read the credential ciphertext'
);
select pg_temp.assert_true(
  (select count(*) from public.organization_ai_credential_secrets(
    current_setting('test.org_b')::uuid)) = 0,
  'the service role sees credentials of an organization that has none'
);
reset role;

-- Ciphertext of one tenant is never returned for another tenant's id.
select pg_temp.assert_true(
  (select count(*) from public.organization_ai_credential_secrets(
    current_setting('test.org_b')::uuid)) = 0,
  'tenant B id resolves to tenant A credentials'
);

select 'tenant security assertions passed' as result;
