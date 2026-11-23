-- Corrective migration: Cortex-0 (Frankenstein-Labs) catalogue entry.
-- The provider is created disabled and without an endpoint: it becomes selectable
-- only after an operator configures a real inference URL and a server-side key.

insert into public.ai_providers (id, name, kind, base_url, enabled, capabilities)
values (
  'frankenstein-cortex',
  'Frankenstein-Labs Cortex',
  'frankenstein',
  null,
  false,
  '{"supports_streaming": true, "remote_endpoint_required": true}'::jsonb
)
on conflict (id) do nothing;

insert into public.ai_models (
  id, provider_id, display_name, description, task, modalities,
  context_window, supports_streaming, supports_tools, supports_vision,
  supports_embeddings, status, limits, capabilities
)
values (
  'cortex-0',
  'frankenstein-cortex',
  'Cortex-0',
  'Frankenstein-Labs Cortex-0 served from a configured remote endpoint (no weights are downloaded by Cortex).',
  'general',
  '{text}',
  4096,
  true,
  false,
  false,
  false,
  'preview',
  '{"requires_remote_endpoint": true}'::jsonb,
  '{"note": "Enable only after a real endpoint answers /health"}'::jsonb
)
on conflict (id) do nothing;
