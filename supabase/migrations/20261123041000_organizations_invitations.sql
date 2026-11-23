-- Incremental tenant-management migration. The previous foundation migration remains immutable.

alter table public.organization_memberships
  drop constraint if exists organization_memberships_role_check;
alter table public.organization_memberships
  add constraint organization_memberships_role_check
  check (role in ('owner', 'admin', 'member', 'viewer'));

create table public.organization_invitations (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  email text not null check (email = lower(email)),
  role text not null default 'member' check (role in ('admin', 'member', 'viewer')),
  token_hash text not null unique,
  invited_by uuid not null references auth.users(id) on delete restrict,
  status text not null default 'pending' check (status in ('pending', 'accepted', 'declined', 'revoked', 'expired')),
  expires_at timestamptz not null,
  accepted_by uuid references auth.users(id) on delete set null,
  accepted_at timestamptz,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index organization_invitations_org_status_idx
  on public.organization_invitations (organization_id, status, expires_at);
create index organization_invitations_email_idx
  on public.organization_invitations (email, status, expires_at);

alter table public.organization_invitations enable row level security;

create policy invitations_select_member on public.organization_invitations
  for select to authenticated
  using (public.is_org_member(organization_id));
create policy invitations_manage_admin on public.organization_invitations
  for all to authenticated
  using (public.has_org_role(organization_id, array['owner', 'admin']))
  with check (public.has_org_role(organization_id, array['owner', 'admin']));

create or replace function public.create_organization_with_owner(
  organization_slug text,
  organization_name text
)
returns public.organizations
language plpgsql
security definer
set search_path = public
as $$
declare
  created_organization public.organizations;
  current_user_id uuid := (select auth.uid());
begin
  if current_user_id is null then
    raise exception using errcode = '28000', message = 'Authentication required';
  end if;

  insert into public.organizations (slug, name, created_by)
  values (organization_slug, organization_name, current_user_id)
  returning * into created_organization;

  insert into public.organization_memberships (organization_id, user_id, role)
  values (created_organization.id, current_user_id, 'owner');

  insert into public.organization_entitlements (
    organization_id, plan_id, credits_limit, period_start, period_end
  )
  select created_organization.id, p.id, p.included_credits,
         timezone('utc', now()), timezone('utc', now()) + interval '1 month'
  from public.plans p
  where p.id = 'free';

  return created_organization;
end;
$$;

revoke all on function public.create_organization_with_owner(text, text) from public;
grant execute on function public.create_organization_with_owner(text, text) to authenticated;
