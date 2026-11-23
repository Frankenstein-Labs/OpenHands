-- Corrective migration: user profiles linked to auth.users.
-- New file; the three foundation migrations remain immutable.

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text check (full_name is null or char_length(full_name) <= 160),
  avatar_url text,
  locale text not null default 'en' check (char_length(locale) between 2 and 12),
  timezone text not null default 'UTC' check (char_length(timezone) between 1 and 64),
  preferences jsonb not null default '{}'::jsonb,
  status text not null default 'active' check (status in ('active', 'suspended', 'deleted')),
  active_organization_id uuid references public.organizations(id) on delete set null,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

alter table public.profiles enable row level security;

create policy profiles_select_self on public.profiles
  for select to authenticated using (id = (select auth.uid()));

create policy profiles_insert_self on public.profiles
  for insert to authenticated
  with check (
    id = (select auth.uid())
    and (active_organization_id is null or public.is_org_member(active_organization_id))
  );

create policy profiles_update_self on public.profiles
  for update to authenticated
  using (id = (select auth.uid()))
  with check (
    id = (select auth.uid())
    and (active_organization_id is null or public.is_org_member(active_organization_id))
  );

-- Auto-provision a profile row for every new auth user. Kept minimal; the API
-- fills the rest on first access.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, full_name, avatar_url)
  values (
    new.id,
    nullif(new.raw_user_meta_data ->> 'full_name', ''),
    nullif(new.raw_user_meta_data ->> 'avatar_url', '')
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();
