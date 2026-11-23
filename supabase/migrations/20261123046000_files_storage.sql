-- Corrective migration: private file metadata for Supabase Storage.
-- Object paths must start with the owning organization id; this is enforced both
-- in the API and by the RLS check below.

create table public.files (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  created_by uuid not null references auth.users(id) on delete restrict,
  bucket text not null check (bucket in ('org-files', 'conversation-exports', 'run-artifacts')),
  object_path text not null check (char_length(object_path) between 3 and 1024),
  mime_type text,
  size_bytes bigint check (size_bytes is null or size_bytes >= 0),
  checksum text,
  status text not null default 'pending' check (status in ('pending', 'ready', 'deleted')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  deleted_at timestamptz,
  unique (bucket, object_path)
);

create index files_org_created_idx on public.files (organization_id, created_at desc);

alter table public.files enable row level security;

create policy files_select_member on public.files
  for select to authenticated
  using (
    public.is_org_member(organization_id)
    and object_path like organization_id::text || '/%'
  );
create policy files_insert_member on public.files
  for insert to authenticated
  with check (
    public.is_org_member(organization_id)
    and created_by = (select auth.uid())
    and object_path like organization_id::text || '/%'
  );
create policy files_update_admin on public.files
  for update to authenticated
  using (public.has_org_role(organization_id, array['owner', 'admin']))
  with check (object_path like organization_id::text || '/%');
create policy files_delete_admin on public.files
  for delete to authenticated
  using (public.has_org_role(organization_id, array['owner', 'admin']));
