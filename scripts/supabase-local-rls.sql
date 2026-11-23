\set ON_ERROR_STOP on

create function pg_temp.assert_true(ok boolean, msg text) returns void language plpgsql as $$
begin
  if not coalesce(ok, false) then
    raise exception 'ASSERT FAILED: %', msg;
  end if;
end $$;

insert into auth.users (id, email) values
  ('00000000-0000-4000-8000-00000000000a', 'tenant-a@local'),
  ('00000000-0000-4000-8000-00000000000b', 'tenant-b@local');

-- Tenant A creates its organization and private data.
set role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-4000-8000-00000000000a', false);
select set_config(
  'test.org_a',
  (select id::text from public.create_organization_with_owner('org-a', 'Org A')),
  false
);
insert into public.agents (organization_id, created_by, name)
values (current_setting('test.org_a')::uuid, auth.uid(), 'A agent');
insert into public.documents (organization_id, created_by, title, source, status)
values (current_setting('test.org_a')::uuid, auth.uid(), 'A private document', 'manual', 'ready');
insert into public.document_chunks (document_id, organization_id, chunk_index, content, token_count)
select id, current_setting('test.org_a')::uuid, 0, 'tenant a secret runbook', 5
from public.documents where organization_id = current_setting('test.org_a')::uuid;
select pg_temp.assert_true(
  (select count(*) from public.agents where organization_id = current_setting('test.org_a')::uuid) = 1,
  'owner cannot read its own agent'
);

-- Tenant B creates a separate organization.
reset role;
set role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-4000-8000-00000000000b', false);
select set_config(
  'test.org_b',
  (select id::text from public.create_organization_with_owner('org-b', 'Org B')),
  false
);
select pg_temp.assert_true(
  current_setting('test.org_a') <> current_setting('test.org_b'),
  'organizations share an id'
);

-- Cross-tenant reads return nothing.
select pg_temp.assert_true(
  (select count(*) from public.agents where organization_id = current_setting('test.org_a')::uuid) = 0,
  'B can read agents of A'
);
select pg_temp.assert_true(
  (select count(*) from public.documents where organization_id = current_setting('test.org_a')::uuid) = 0,
  'B can read documents of A'
);
select pg_temp.assert_true(
  (select count(*) from public.document_chunks where organization_id = current_setting('test.org_a')::uuid) = 0,
  'B can read document chunks of A'
);
select pg_temp.assert_true(
  (select count(*) from public.organizations where id = current_setting('test.org_a')::uuid) = 0,
  'B can read organization A'
);
select pg_temp.assert_true(
  (select count(*) from public.organization_memberships where organization_id = current_setting('test.org_a')::uuid) = 0,
  'B can read memberships of A'
);

-- Cross-tenant writes affect nothing.
with updated as (
  update public.agents set name = 'hijacked'
  where organization_id = current_setting('test.org_a')::uuid
  returning 1
)
select pg_temp.assert_true((select count(*) from updated) = 0, 'B updated an agent of A');

-- Cross-tenant insert and privilege escalation are rejected.
do $$
begin
  begin
    insert into public.agents (organization_id, created_by, name)
    values (current_setting('test.org_a')::uuid, auth.uid(), 'intruder');
    raise exception 'ASSERT FAILED: B inserted an agent into A';
  exception when insufficient_privilege then
    null;
  end;

  begin
    insert into public.organization_memberships (organization_id, user_id, role)
    values (current_setting('test.org_a')::uuid, auth.uid(), 'admin');
    raise exception 'ASSERT FAILED: B granted itself a role in A';
  exception when insufficient_privilege then
    null;
  end;

  begin
    perform public.add_organization_member(
      current_setting('test.org_a')::uuid,
      '00000000-0000-4000-8000-00000000000b'::uuid,
      'admin'
    );
    raise exception 'ASSERT FAILED: B added a member to A';
  exception when insufficient_privilege then
    null;
  end;
end $$;

-- Tenant A still sees its own data.
reset role;
set role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-4000-8000-00000000000a', false);
select pg_temp.assert_true(
  (select count(*) from public.agents where organization_id = current_setting('test.org_a')::uuid) = 1,
  'A lost access to its own agent'
);
select pg_temp.assert_true(
  (select count(*) from public.document_chunks where organization_id = current_setting('test.org_a')::uuid) = 1,
  'A lost access to its own chunks'
);

-- Signed-out requests see nothing.
reset role;
set role anon;
select set_config('request.jwt.claim.sub', '', false);
select pg_temp.assert_true(
  (select count(*) from public.agents) = 0,
  'signed-out request can read agents'
);
select pg_temp.assert_true(
  (select count(*) from public.organizations) = 0,
  'signed-out request can read organizations'
);

-- The server-side role sees both tenants.
reset role;
set role service_role;
select pg_temp.assert_true(
  (select count(distinct organization_id) from public.agents) = 1,
  'service role lost access to tenant data'
);
select pg_temp.assert_true(
  (select count(*) from public.organizations where id in (
    current_setting('test.org_a')::uuid, current_setting('test.org_b')::uuid
  )) = 2,
  'service role cannot see both organizations'
);

-- Private storage buckets exist and are not public.
reset role;
select pg_temp.assert_true(
  (select count(*) from storage.buckets where id in ('org-files', 'conversation-exports', 'run-artifacts')) = 3,
  'expected private buckets are missing'
);
select pg_temp.assert_true(
  (select count(*) from storage.buckets where id in ('org-files', 'conversation-exports', 'run-artifacts') and public) = 0,
  'a storage bucket is public'
);
