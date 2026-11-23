-- SaaS foundation: organizations, memberships, entitlements, usage and audit.
-- This migration is intentionally local/versioned. It does not connect to a hosted project.

create extension if not exists pgcrypto;

create table public.organizations (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique check (slug ~ '^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$'),
  name text not null check (char_length(name) between 1 and 160),
  created_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table public.organization_memberships (
  organization_id uuid not null references public.organizations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('owner', 'admin', 'member')),
  created_at timestamptz not null default timezone('utc', now()),
  primary key (organization_id, user_id)
);

create index organization_memberships_user_idx
  on public.organization_memberships (user_id, organization_id);

create table public.plans (
  id text primary key check (id ~ '^[a-z0-9][a-z0-9_-]{1,63}$'),
  name text not null,
  included_credits numeric(20, 6) not null check (included_credits >= 0),
  limits jsonb not null default '{}'::jsonb,
  active boolean not null default true,
  created_at timestamptz not null default timezone('utc', now())
);

create table public.organization_entitlements (
  organization_id uuid primary key references public.organizations(id) on delete cascade,
  plan_id text not null references public.plans(id),
  status text not null default 'active' check (status in ('trialing', 'active', 'past_due', 'canceled')),
  credits_limit numeric(20, 6) not null check (credits_limit >= 0),
  credits_used numeric(20, 6) not null default 0 check (credits_used >= 0),
  period_start timestamptz not null,
  period_end timestamptz not null check (period_end > period_start),
  updated_at timestamptz not null default timezone('utc', now())
);

create table public.usage_events (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  actor_user_id uuid references auth.users(id) on delete set null,
  event_type text not null check (event_type in ('llm_tokens', 'llm_request', 'agent_run', 'storage_bytes')),
  quantity numeric(20, 6) not null check (quantity >= 0),
  idempotency_key text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  unique (organization_id, idempotency_key)
);

create index usage_events_org_created_idx
  on public.usage_events (organization_id, created_at desc);

create table public.audit_logs (
  id bigint generated always as identity primary key,
  organization_id uuid references public.organizations(id) on delete set null,
  actor_user_id uuid references auth.users(id) on delete set null,
  action text not null,
  resource_type text not null,
  resource_id text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now())
);

create index audit_logs_org_created_idx
  on public.audit_logs (organization_id, created_at desc);

insert into public.plans (id, name, included_credits, limits)
values
  ('free', 'Free', 100, '{"max_members": 1, "max_concurrent_runs": 1}'::jsonb),
  ('team', 'Team', 5000, '{"max_members": 25, "max_concurrent_runs": 5}'::jsonb)
on conflict (id) do nothing;

create or replace function public.is_org_member(target_organization_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.organization_memberships m
    where m.organization_id = target_organization_id
      and m.user_id = (select auth.uid())
  );
$$;

create or replace function public.has_org_role(
  target_organization_id uuid,
  allowed_roles text[]
)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.organization_memberships m
    where m.organization_id = target_organization_id
      and m.user_id = (select auth.uid())
      and m.role = any (allowed_roles)
  );
$$;

revoke all on function public.is_org_member(uuid) from public;
revoke all on function public.has_org_role(uuid, text[]) from public;
grant execute on function public.is_org_member(uuid) to authenticated;
grant execute on function public.has_org_role(uuid, text[]) to authenticated;

alter table public.organizations enable row level security;
alter table public.organization_memberships enable row level security;
alter table public.plans enable row level security;
alter table public.organization_entitlements enable row level security;
alter table public.usage_events enable row level security;
alter table public.audit_logs enable row level security;

create policy organizations_select_member on public.organizations
  for select to authenticated using (public.is_org_member(id));
create policy organizations_insert_self on public.organizations
  for insert to authenticated with check (created_by = (select auth.uid()));
create policy organizations_update_admin on public.organizations
  for update to authenticated using (public.has_org_role(id, array['owner', 'admin']))
  with check (public.has_org_role(id, array['owner', 'admin']));

create policy memberships_select_member on public.organization_memberships
  for select to authenticated using (public.is_org_member(organization_id));
create policy memberships_insert_owner_bootstrap on public.organization_memberships
  for insert to authenticated
  with check (
    user_id = (select auth.uid())
    and role = 'owner'
    and exists (
      select 1 from public.organizations o
      where o.id = organization_id and o.created_by = (select auth.uid())
    )
  );
create policy memberships_manage_admin on public.organization_memberships
  for all to authenticated
  using (public.has_org_role(organization_id, array['owner', 'admin']))
  with check (public.has_org_role(organization_id, array['owner', 'admin']));

create policy plans_select_authenticated on public.plans
  for select to authenticated using (active = true);
create policy entitlements_select_member on public.organization_entitlements
  for select to authenticated using (public.is_org_member(organization_id));
create policy usage_select_member on public.usage_events
  for select to authenticated using (public.is_org_member(organization_id));
create policy audit_select_member on public.audit_logs
  for select to authenticated using (public.is_org_member(organization_id));

-- Usage and audit writes are server-owned in the target architecture. No client insert/update
-- policies are created; the FastAPI service will use a constrained server-side key path.

insert into storage.buckets (id, name, public)
values
  ('org-files', 'org-files', false),
  ('conversation-exports', 'conversation-exports', false),
  ('run-artifacts', 'run-artifacts', false)
on conflict (id) do update set public = excluded.public;

create policy storage_org_member_read on storage.objects
  for select to authenticated
  using (
    bucket_id in ('org-files', 'conversation-exports', 'run-artifacts')
    and name ~ '^[0-9a-fA-F-]{36}/'
    and public.is_org_member(split_part(name, '/', 1)::uuid)
  );

create policy storage_org_member_upload on storage.objects
  for insert to authenticated
  with check (
    bucket_id in ('org-files', 'conversation-exports', 'run-artifacts')
    and name ~ '^[0-9a-fA-F-]{36}/'
    and public.is_org_member(split_part(name, '/', 1)::uuid)
  );

create policy storage_org_admin_delete on storage.objects
  for delete to authenticated
  using (
    bucket_id in ('org-files', 'conversation-exports', 'run-artifacts')
    and name ~ '^[0-9a-fA-F-]{36}/'
    and public.has_org_role(split_part(name, '/', 1)::uuid, array['owner', 'admin'])
  );
