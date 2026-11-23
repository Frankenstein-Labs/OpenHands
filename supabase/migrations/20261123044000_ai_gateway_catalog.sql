-- Corrective migration: provider-neutral AI catalogue.
-- Providers/models are declared, but every provider starts disabled until real
-- credentials and a working endpoint are verified server-side.

create table public.ai_providers (
  id text primary key check (id ~ '^[a-z0-9][a-z0-9_-]{1,63}$'),
  name text not null,
  kind text not null check (kind in (
    'openai_compatible',
    'vercel_ai_gateway',
    'huggingface',
    'openrouter',
    'together',
    'cloudflare_workers_ai',
    'frankenstein'
  )),
  base_url text,
  enabled boolean not null default false,
  capabilities jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table public.ai_models (
  id text primary key check (id ~ '^[a-z0-9][a-z0-9._:/-]{1,127}$'),
  provider_id text not null references public.ai_providers(id) on delete cascade,
  display_name text not null,
  description text,
  task text not null default 'general'
    check (task in ('general', 'coding', 'reasoning', 'light', 'vision', 'embedding')),
  modalities text[] not null default '{text}',
  context_window integer check (context_window is null or context_window > 0),
  max_output_tokens integer check (max_output_tokens is null or max_output_tokens > 0),
  supports_tools boolean not null default false,
  supports_streaming boolean not null default true,
  supports_vision boolean not null default false,
  supports_embeddings boolean not null default false,
  input_cost_per_1k numeric(20, 8) check (input_cost_per_1k is null or input_cost_per_1k >= 0),
  output_cost_per_1k numeric(20, 8) check (output_cost_per_1k is null or output_cost_per_1k >= 0),
  currency text not null default 'USD',
  status text not null default 'active'
    check (status in ('active', 'preview', 'disabled', 'retired')),
  limits jsonb not null default '{}'::jsonb,
  capabilities jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index ai_models_provider_idx on public.ai_models (provider_id, status);

alter table public.ai_providers enable row level security;
alter table public.ai_models enable row level security;

create policy ai_providers_select_authenticated on public.ai_providers
  for select to authenticated using (true);
create policy ai_models_select_authenticated on public.ai_models
  for select to authenticated using (true);

-- Catalogue is server-managed; no client write policies.

insert into public.ai_providers (id, name, kind, base_url, enabled)
values
  ('openai-compatible', 'OpenAI-compatible endpoint', 'openai_compatible', null, false),
  ('openrouter', 'OpenRouter', 'openrouter', 'https://openrouter.ai/api/v1', false),
  ('together', 'Together AI', 'together', 'https://api.together.xyz/v1', false),
  ('huggingface', 'Hugging Face Inference Providers', 'huggingface', 'https://router.huggingface.co/v1', false),
  ('vercel-ai-gateway', 'Vercel AI Gateway', 'vercel_ai_gateway', null, false),
  ('cloudflare-workers-ai', 'Cloudflare Workers AI', 'cloudflare_workers_ai', null, false),
  ('frankenstein', 'Frankenstein-Labs', 'frankenstein', null, false)
on conflict (id) do nothing;

-- Cortex-0 is declared but NOT available until a real remote endpoint is set.
insert into public.ai_models (
  id, provider_id, display_name, description, task, modalities, context_window,
  supports_tools, supports_streaming, status, limits
)
values (
  'frankenstein/cortex-0', 'frankenstein', 'Cortex-0',
  'Frankenstein-Labs Cortex-0 (remote endpoint required).',
  'general', '{text}', 4096, true, true, 'preview',
  '{"requires_endpoint": true}'::jsonb
)
on conflict (id) do nothing;
