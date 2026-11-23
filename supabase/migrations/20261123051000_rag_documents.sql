-- Corrective migration: private document library with tenant-scoped search.
-- Uses PostgreSQL full-text search so retrieval works without any external
-- embedding provider. Chunks keep an organization id for RLS.

create extension if not exists pg_trgm;

create table public.documents (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  created_by uuid not null references auth.users(id) on delete restrict,
  title text not null check (char_length(title) between 1 and 300),
  source text not null default 'manual' check (source in ('manual', 'upload', 'github', 'conversation')),
  mime_type text,
  size_bytes bigint check (size_bytes is null or size_bytes >= 0),
  status text not null default 'ready' check (status in ('pending', 'processing', 'ready', 'failed')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index documents_org_created_idx on public.documents (organization_id, created_at desc);

create table public.document_chunks (
  id bigint generated always as identity primary key,
  document_id uuid not null references public.documents(id) on delete cascade,
  organization_id uuid not null references public.organizations(id) on delete cascade,
  chunk_index integer not null check (chunk_index >= 0),
  content text not null check (char_length(content) between 1 and 8000),
  token_count integer check (token_count is null or token_count >= 0),
  search tsvector generated always as (to_tsvector('english', content)) stored,
  created_at timestamptz not null default timezone('utc', now()),
  unique (document_id, chunk_index)
);

create index document_chunks_org_idx on public.document_chunks (organization_id);
create index document_chunks_search_idx on public.document_chunks using gin (search);
create index document_chunks_trgm_idx on public.document_chunks using gin (content gin_trgm_ops);

alter table public.documents enable row level security;
alter table public.document_chunks enable row level security;

create policy documents_select_member on public.documents
  for select to authenticated
  using (public.is_org_member(organization_id));

create policy documents_insert_member on public.documents
  for insert to authenticated
  with check (
    public.is_org_member(organization_id)
    and created_by = (select auth.uid())
  );

create policy documents_delete_admin on public.documents
  for delete to authenticated
  using (public.has_org_role(organization_id, array['owner', 'admin']));

create policy document_chunks_select_member on public.document_chunks
  for select to authenticated
  using (public.is_org_member(organization_id));

create policy document_chunks_insert_member on public.document_chunks
  for insert to authenticated
  with check (public.is_org_member(organization_id));

create policy document_chunks_delete_admin on public.document_chunks
  for delete to authenticated
  using (public.has_org_role(organization_id, array['owner', 'admin']));

-- Tenant-scoped search. SECURITY INVOKER so RLS still applies to the caller.
create or replace function public.search_document_chunks(
  target_organization_id uuid,
  query_text text,
  match_limit integer default 10
)
returns table (
  document_id uuid,
  document_title text,
  chunk_index integer,
  content text,
  rank real
)
language sql
stable
security invoker
set search_path = public
as $$
  select
    c.document_id,
    d.title as document_title,
    c.chunk_index,
    c.content,
    ts_rank(c.search, websearch_to_tsquery('english', query_text)) as rank
  from public.document_chunks c
  join public.documents d on d.id = c.document_id
  where c.organization_id = target_organization_id
    and query_text is not null
    and char_length(btrim(query_text)) > 0
    and c.search @@ websearch_to_tsquery('english', query_text)
  order by rank desc, c.document_id, c.chunk_index
  limit least(greatest(coalesce(match_limit, 10), 1), 50);
$$;

revoke all on function public.search_document_chunks(uuid, text, integer) from public;
grant execute on function public.search_document_chunks(uuid, text, integer) to authenticated;
