-- Corrective migration: persisted agents, runs and run events.
-- Run execution itself stays with the OpenHands Agent Server; these tables are the
-- SaaS control plane (ownership, status, quota accounting, audit trail).

create table public.agents (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  created_by uuid not null references auth.users(id) on delete restrict,
  name text not null check (char_length(name) between 1 and 120),
  description text check (description is null or char_length(description) <= 2000),
  kind text not null default 'coding' check (kind in ('coding', 'general', 'research', 'custom')),
  model_id text references public.ai_models(id) on delete set null,
  system_prompt text check (system_prompt is null or char_length(system_prompt) <= 20000),
  tools jsonb not null default '[]'::jsonb,
  config jsonb not null default '{}'::jsonb,
  archived boolean not null default false,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index agents_org_idx on public.agents (organization_id, created_at desc);

create table public.agent_runs (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  agent_id uuid references public.agents(id) on delete set null,
  conversation_id text,
  created_by uuid not null references auth.users(id) on delete restrict,
  model_id text references public.ai_models(id) on delete set null,
  status text not null default 'queued'
    check (status in ('queued', 'provisioning', 'running', 'waiting', 'completed', 'failed', 'cancelled', 'expired')),
  prompt text check (prompt is null or char_length(prompt) <= 100000),
  budget_credits numeric(20, 6) not null default 0 check (budget_credits >= 0),
  credits_reserved numeric(20, 6) not null default 0 check (credits_reserved >= 0),
  credits_used numeric(20, 6) not null default 0 check (credits_used >= 0),
  error text,
  metadata jsonb not null default '{}'::jsonb,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index agent_runs_org_status_idx on public.agent_runs (organization_id, status, created_at desc);
create index agent_runs_org_created_idx on public.agent_runs (organization_id, created_at desc);

create table public.agent_run_events (
  id bigint generated always as identity primary key,
  run_id uuid not null references public.agent_runs(id) on delete cascade,
  organization_id uuid not null references public.organizations(id) on delete cascade,
  seq bigint not null check (seq >= 0),
  type text not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  unique (run_id, seq)
);

create index agent_run_events_run_idx on public.agent_run_events (run_id, seq);

alter table public.agents enable row level security;
alter table public.agent_runs enable row level security;
alter table public.agent_run_events enable row level security;

create policy agents_select_member on public.agents
  for select to authenticated using (public.is_org_member(organization_id));
create policy agents_insert_member on public.agents
  for insert to authenticated
  with check (public.is_org_member(organization_id) and created_by = (select auth.uid()));
create policy agents_update_admin on public.agents
  for update to authenticated
  using (public.has_org_role(organization_id, array['owner', 'admin']))
  with check (public.has_org_role(organization_id, array['owner', 'admin']));
create policy agents_delete_admin on public.agents
  for delete to authenticated
  using (public.has_org_role(organization_id, array['owner', 'admin']));

create policy agent_runs_select_member on public.agent_runs
  for select to authenticated using (public.is_org_member(organization_id));
create policy agent_runs_insert_member on public.agent_runs
  for insert to authenticated
  with check (public.is_org_member(organization_id) and created_by = (select auth.uid()));
-- Run status transitions and cancellation are written by the API with the user
-- token, but only for runs the user can see.
create policy agent_runs_update_member on public.agent_runs
  for update to authenticated
  using (public.is_org_member(organization_id))
  with check (public.is_org_member(organization_id));

create policy agent_run_events_select_member on public.agent_run_events
  for select to authenticated using (public.is_org_member(organization_id));
-- Events are server/runner-owned; no client write policies.
