-- Per-organization AI provider credentials and settings.
--
-- Provider keys are tenant data, not platform data: one organization's key must
-- never be usable by another. The ciphertext is produced by the API with
-- Fernet before it reaches Postgres, so the database never sees a plaintext
-- key and a database dump alone does not expose one.
--
-- Read access is deliberately narrow:
--   * `organization_ai_credentials` has RLS enabled and **no policy at all**, so
--     `authenticated` and `anon` cannot read it even with a valid JWT. Admins
--     see metadata (`key_last4`, provider, timestamps) through a definer
--     function; only the service role can read ciphertext.
--   * `organization_ai_settings` is readable by members because it holds no
--     secret, and writable only through a definer function with a role check.

create table public.organization_ai_credentials (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  provider_id text not null references public.ai_providers(id) on delete cascade,
  ciphertext text not null check (char_length(ciphertext) between 16 and 8192),
  key_last4 text not null check (char_length(key_last4) between 1 and 8),
  created_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  revoked_at timestamptz
);

create unique index organization_ai_credentials_active_idx
  on public.organization_ai_credentials (organization_id, provider_id)
  where revoked_at is null;

create index organization_ai_credentials_org_idx
  on public.organization_ai_credentials (organization_id);

alter table public.organization_ai_credentials enable row level security;
-- Intentionally no policy: secrets are reachable only through the definer
-- functions below (metadata) or with the service role (ciphertext).

create table public.organization_ai_settings (
  organization_id uuid primary key references public.organizations(id) on delete cascade,
  default_model_id text references public.ai_models(id) on delete set null,
  monthly_token_limit bigint check (monthly_token_limit is null or monthly_token_limit >= 0),
  credits_per_1k_tokens numeric(12, 4)
    check (credits_per_1k_tokens is null or credits_per_1k_tokens >= 0),
  updated_by uuid references auth.users(id) on delete set null,
  updated_at timestamptz not null default timezone('utc', now())
);

alter table public.organization_ai_settings enable row level security;

create policy organization_ai_settings_select_member on public.organization_ai_settings
  for select to authenticated using (public.is_org_member(organization_id));
-- Writes go through set_organization_ai_settings(); no direct write policy.

-- ---------------------------------------------------------------------------
-- Credential metadata (no secret) for organization admins
-- ---------------------------------------------------------------------------
create or replace function public.list_organization_ai_credentials(target_organization_id uuid)
returns table (
  provider_id text,
  key_last4 text,
  created_at timestamptz,
  updated_at timestamptz
)
language sql
stable
security definer
set search_path = public
as $$
  select c.provider_id, c.key_last4, c.created_at, c.updated_at
  from public.organization_ai_credentials c
  where c.organization_id = target_organization_id
    and c.revoked_at is null
    and public.has_org_role(target_organization_id, array['owner', 'admin'])
  order by c.provider_id;
$$;

revoke all on function public.list_organization_ai_credentials(uuid) from public;
grant execute on function public.list_organization_ai_credentials(uuid) to authenticated;

-- ---------------------------------------------------------------------------
-- Upsert a credential (ciphertext only) as owner/admin of the organization
-- ---------------------------------------------------------------------------
create or replace function public.set_organization_ai_credential(
  target_organization_id uuid,
  target_provider_id text,
  target_ciphertext text,
  target_key_last4 text
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  credential_id uuid;
begin
  if not public.has_org_role(target_organization_id, array['owner', 'admin']) then
    raise exception 'not allowed to manage AI credentials for this organization'
      using errcode = '42501';
  end if;

  if not exists (select 1 from public.ai_providers p where p.id = target_provider_id) then
    raise exception 'unknown AI provider %', target_provider_id using errcode = '23503';
  end if;

  update public.organization_ai_credentials
  set ciphertext = target_ciphertext,
      key_last4 = target_key_last4,
      updated_at = timezone('utc', now())
  where organization_id = target_organization_id
    and provider_id = target_provider_id
    and revoked_at is null
  returning id into credential_id;

  if credential_id is null then
    insert into public.organization_ai_credentials
      (organization_id, provider_id, ciphertext, key_last4, created_by)
    values
      (target_organization_id, target_provider_id, target_ciphertext, target_key_last4,
       (select auth.uid()))
    returning id into credential_id;
  end if;

  return credential_id;
end;
$$;

revoke all on function public.set_organization_ai_credential(uuid, text, text, text) from public;
grant execute on function public.set_organization_ai_credential(uuid, text, text, text)
  to authenticated;

-- ---------------------------------------------------------------------------
-- Revoke a credential (soft delete, keeps the audit trail)
-- ---------------------------------------------------------------------------
create or replace function public.revoke_organization_ai_credential(
  target_organization_id uuid,
  target_provider_id text
)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
begin
  if not public.has_org_role(target_organization_id, array['owner', 'admin']) then
    raise exception 'not allowed to manage AI credentials for this organization'
      using errcode = '42501';
  end if;

  update public.organization_ai_credentials
  set revoked_at = timezone('utc', now()),
      updated_at = timezone('utc', now())
  where organization_id = target_organization_id
    and provider_id = target_provider_id
    and revoked_at is null;

  return found;
end;
$$;

revoke all on function public.revoke_organization_ai_credential(uuid, text) from public;
grant execute on function public.revoke_organization_ai_credential(uuid, text) to authenticated;

-- ---------------------------------------------------------------------------
-- Ciphertext read path for the gateway (service role only)
-- ---------------------------------------------------------------------------
create or replace function public.organization_ai_credential_secrets(target_organization_id uuid)
returns table (provider_id text, ciphertext text)
language sql
stable
security definer
set search_path = public
as $$
  select c.provider_id, c.ciphertext
  from public.organization_ai_credentials c
  where c.organization_id = target_organization_id
    and c.revoked_at is null;
$$;

revoke all on function public.organization_ai_credential_secrets(uuid) from public;
-- `authenticated` must never decrypt a tenant key, even for its own tenant:
-- only the server-side gateway uses this function.
grant execute on function public.organization_ai_credential_secrets(uuid) to service_role;

-- ---------------------------------------------------------------------------
-- Per-organization AI settings (default model, token ceiling, rate)
-- ---------------------------------------------------------------------------
create or replace function public.set_organization_ai_settings(
  target_organization_id uuid,
  target_default_model_id text,
  target_monthly_token_limit bigint,
  target_credits_per_1k_tokens numeric
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  if not public.has_org_role(target_organization_id, array['owner', 'admin']) then
    raise exception 'not allowed to change AI settings for this organization'
      using errcode = '42501';
  end if;

  if target_default_model_id is not null
     and not exists (select 1 from public.ai_models m where m.id = target_default_model_id) then
    raise exception 'unknown AI model %', target_default_model_id using errcode = '23503';
  end if;

  insert into public.organization_ai_settings
    (organization_id, default_model_id, monthly_token_limit, credits_per_1k_tokens, updated_by)
  values
    (target_organization_id, target_default_model_id, target_monthly_token_limit,
     target_credits_per_1k_tokens, (select auth.uid()))
  on conflict (organization_id) do update
    set default_model_id = excluded.default_model_id,
        monthly_token_limit = excluded.monthly_token_limit,
        credits_per_1k_tokens = excluded.credits_per_1k_tokens,
        updated_by = excluded.updated_by,
        updated_at = timezone('utc', now());
end;
$$;

revoke all on function public.set_organization_ai_settings(uuid, text, bigint, numeric)
  from public;
grant execute on function public.set_organization_ai_settings(uuid, text, bigint, numeric)
  to authenticated;

comment on table public.organization_ai_credentials is
  'Encrypted provider keys, one active row per organization and provider. No client policy: ciphertext is service-role only.';
