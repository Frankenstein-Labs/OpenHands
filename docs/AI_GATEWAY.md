# Cortex AI Gateway

Provider-neutral model access for Cortex.ai. Code lives in
`apps/api/app/ai_gateway/` and is exposed by `POST /api/v1/ai/generate`.

## Provider support

| Kind | Implementation | Status |
|---|---|---|
| `openai_compatible` | `OpenAICompatibleProvider` | Implemented |
| `openrouter` | OpenAI-compatible protocol | Implemented |
| `together` | OpenAI-compatible protocol | Implemented |
| `huggingface` | OpenAI-compatible inference endpoint | Implemented |
| `vercel_ai_gateway` | OpenAI-compatible endpoint | Implemented |
| `frankenstein` | `FrankensteinProvider` (remote inference URL) | Implemented; needs a real endpoint |
| `cloudflare_workers_ai` | — | **Not implemented**; the registry skips it instead of mis-calling it |

No provider is "connected" until credentials exist and a real call succeeds.
Providers start disabled in the catalogue.

## Interface

`Provider` (abstract) declares:

- `generate(request) -> GenerationResult`
- `stream(request) -> AsyncIterator[str]`
- `embeddings(model, inputs)`
- `health() -> bool`
- `configured` property

`GenerationRequest` carries model, messages, temperature, max tokens, tools,
streaming and `idempotent`. The router never retries a non-idempotent request.

Capabilities are declared per model (`ModelSpec`): task, modalities, context
window, tools, streaming, vision, embeddings, pricing and status. Unsupported
capabilities raise `CapabilityNotSupported` rather than silently degrading.

## Catalogue

- `ai_providers`: id, kind, base_url, enabled, capabilities.
- `ai_models`: display name, task, modalities, context window, capabilities,
  pricing, status, limits.
- Both are read through `ModelsRepository` and exposed by `/api/v1/models` and
  `/api/v1/providers`.

Adding a model does not require a frontend change: it is a catalogue row.

## Routing

`ModelRouter` selects among active models whose provider is configured:

1. exact requested model,
2. same task,
3. general-purpose,
4. others.

Fallback happens only for retryable provider errors and only when the request is
idempotent. `NoAvailableModel` is raised when nothing matches.

## Keys and secrets

- Credentials come from server settings (`ai_provider_credentials`,
  `ai_provider_base_urls`) and are passed to providers at build time.
- Keys are never returned by the API, logged, or sent to the browser.
- Rotation is a settings change plus restart; no key is persisted in the
  database.

## Metering and budgets

`AIGatewayService.generate`:

1. Loads the organization entitlement; missing entitlement → 404.
2. Rejects the call when remaining credits are zero (402).
3. Caps `max_tokens` against remaining credits (402 when too large).
4. Requires the requested model to be active and configured (503 otherwise).
5. Calls the router and computes credits from total tokens using
   `AI_GATEWAY_CREDITS_PER_1K_TOKENS` (default 1 credit per 1k tokens).
6. Records `llm_tokens` usage with an idempotency key through the atomic
   `record_usage_event` SQL function, which inserts the event and increments
   `organization_entitlements.credits_used` in one transaction.

## Honest limitations

- No provider is configured in this environment, so live generation is not yet
  proven end to end.
- Streaming is implemented at the provider layer but not yet exposed over SSE.
- Cloudflare Workers AI needs a dedicated adapter before it can be enabled.
