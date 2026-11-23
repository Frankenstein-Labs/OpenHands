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

## Cortex-0 availability (probed 2026-11-23)

Verified with `scripts/verify-ai-provider.py` and a Frankenstein-Labs Hugging
Face token:

| Fact | Observed |
|---|---|
| Token identity | `Frankenstein-Labs` (user), accepted by the HF API |
| Repository `Frankenstein-Labs/Cortex.0` | `private=True`, `gated=False`, no `pipeline_tag` |
| Files | `Cortex.0-Q8_0.gguf`, `configs/cortex0.yaml`, `cortex0/` package |
| HF router chat call | `400 model_not_supported`: "not a chat model" |
| Other hosted model via the same token | `400 ... not supported by any provider you have enabled` |

Conclusion: **Cortex-0 is not served by Hugging Face Inference Providers.** The
catalogue entry stays `preview`, and the provider row stays `enabled=false`.
The token does read the private repository; it does not make the model callable.

To serve it, run the GGUF behind an OpenAI-compatible server (the model card
documents `llama-server -hf Frankenstein-Labs/Cortex.0 --hf-file
Cortex.0-Q8_0.gguf --port 8080`), then:

```bash
export CORTEX_VERIFY_PROVIDER_URL=http://<host>:8080/v1
export CORTEX_VERIFY_PROVIDER_KEY=<endpoint token, may be empty>
export CORTEX_VERIFY_MODEL=cortex-0
python scripts/verify-ai-provider.py --endpoint
```

Only after that probe returns `OK`:

1. `POST /api/v1/providers/frankenstein-cortex` with `enabled=true` and
   `base_url` set (platform admin).
2. `PATCH /api/v1/models/cortex-0` with `status="active"`.
3. Set `AI_PROVIDER_BASE_URLS` / `AI_PROVIDER_CREDENTIALS` in the API
   environment, keyed by `frankenstein-cortex`.

Do not download the GGUF onto the API host. A dedicated HF Inference Endpoint is
an option but is a paid resource and has not been created.

Never commit a provider key. Any token pasted into a chat should be rotated after
it is configured.

## Honest limitations

- No provider is configured in this environment, so live generation is not yet
  proven end to end.
- Streaming is implemented at the provider layer but not yet exposed over SSE.
- Cloudflare Workers AI needs a dedicated adapter before it can be enabled.
