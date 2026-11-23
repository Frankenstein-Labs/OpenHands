-- Corrective migration: multi-tenant GitHub App model.
-- Private keys and installation tokens never live here; only installation metadata.
-- Webhook payloads are stored server-side for idempotency and auditing.

create table public.github_installations (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  installation_id bigint not null unique,
  account_login text not null,
  account_type text,
  status text not null default 'active' check (status in ('active', 'suspended', 'revoked')),
  created_at timestamptz not null default timezone('utc', now()),
  revoked_at timestamptz
);

create index github_installations_org_idx on public.github_installations (organization_id, status);

create table public.github_repositories (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  installation_id uuid references public.github_installations(id) on delete cascade,
  github_repo_id bigint not null,
  full_name text not null,
  default_branch text,
  permissions jsonb not null default '{}'::jsonb,
  status text not null default 'active' check (status in ('active', 'archived', 'revoked')),
  created_at timestamptz not null default timezone('utc', now()),
  unique (organization_id, github_repo_id)
);

create table public.github_webhook_events (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid references public.organizations(id) on delete cascade,
  delivery_id text not null unique,
  event_name text not null,
  payload jsonb not null,
  status text not null default 'received'
    check (status in ('received', 'processed', 'failed', 'ignored')),
  processed_at timestamptz,
  created_at timestamptz not null default timezone('utc', now())
);

alter table public.github_installations enable row level security;
alter table public.github_repositories enable row level security;
alter table public.github_webhook_events enable row level security;

create policy github_installations_select_member on public.github_installations
  for select to authenticated using (public.is_org_member(organization_id));
create policy github_repositories_select_member on public.github_repositories
  for select to authenticated using (public.is_org_member(organization_id));

-- Installations, repositories and webhook events are server-owned (written by the
-- backend after verifying the GitHub signature and the organization permission).
