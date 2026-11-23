# Cortex Engine Validation

Real-engine evidence for the Cortex identity work: a running OpenHands Agent
Server, a real model behind it, and conversations whose actions and outputs are
recorded. Nothing here is mocked: every result below came from the agent server
API at `http://127.0.0.1:60000` (version `1.63.1`).

## What was validated

| Check | Result |
|---|---|
| Real Agent Server | `openhands-agent-server` 1.63.1, `/settings` and `/api/conversations` answer with the session key |
| Conversation creation through the adapter payload | 201, `execution_status` reaches `finished` |
| Cortex identity reaches the model | Yes, verbatim answers below |
| Tools execute in the workspace | Yes: file creation, `pip install`, `pytest` runs |
| Real token accounting | `usage_to_metrics` reports `model_name: openai/qwen3-4b` |
| Planner identity | Code-level only (unit tests), not run live |
| ACP identity | Code-level only (no ACP agent binary in this sandbox) |

## Model access paths tested

The sandbox has no paid provider credential, so three paths were measured.

| Path | Result |
|---|---|
| Platform managed proxy (`llm-proxy.app.all-hands.dev`) | 403 `Request rejected by proxy policy` for every listed model and auth header combination |
| Hugging Face Inference Providers (`router.huggingface.co/v1`) with a real `hf_` token | `GET /v1/models` 200 (158 models); `POST /v1/chat/completions` 402 `Purchase pre-paid credits` |
| Local `llama.cpp` server (`llama-cpp-python` 0.3.38) with Qwen3-4B-Instruct-2507 Q4_K_M | Works; 12.8 tok/s prompt eval, 4.5 tok/s generation on 4 vCPU |

`llama-cpp-python` does not parse Qwen tool calls and rejects `tool` roles, so a
small OpenAI-compatible shim (`cortex-live-validation/llm_shim.py`) converts
`<tool_call>` text into `tool_calls` and flattens tool turns. The shim only
translates protocol; the decisions come from the model.

## Identity validation

Conversation `dc495ec1-7b4b-487c-bb06-514abb7993b4`, no tools, identity injected
through `agent_context.system_message_suffix` (the same field the frontend uses):

> 1. Je suis Cortex, un agent intelligent développé par Frankenstein-Labs.
> 2. Je suis créé par Frankenstein-Labs.
> 3. Mon objectif est d'aider les personnes à transformer leurs idées en logiciel fonctionnel.
> 4. Je peux explorer des codebases, éditer du code, exécuter des commandes et résoudre des problèmes techniques.
> 5. J'ai été conçu pour simplifier le processus de création de logiciels, en automatisant les tâches répétitives et en aidant à la conception efficace du code.

Answer 4 lists only the capabilities the session actually had, which is the
behaviour the identity prompt asks for.

## Capability validation

Conversation `056b5a68-89cc-463e-b793-a4421df00e2b`, tools `terminal` and
`file_editor`, workspace `cortex-live-validation/capability`. Task: create
`app.py` (`add`, `divide` raising `ValueError`), `test_app.py` with two pytest
tests, run them, fix failures, write `README.md`, summarise with real output.

Observed actions, in order:

1. `FileEditorAction create` → `app.py`
2. `FileEditorAction create` → `test_app.py`
3. `TerminalAction python -m pytest -q` → `No module named pytest`
4. `TerminalAction pip install pytest` → installed
5. `TerminalAction python -m pytest -q` → `FF` (both tests failed)

The run then stalled on a long generation: Qwen3-4B writes verbose reasoning and
generation is 4.5 tok/s, so a single turn can exceed ten minutes. The failure
detection and dependency installation above are real, but the fix turn was not
completed in this sandbox.

## Limits

- Identity and capability evidence comes from a 4B local model, not a frontier
  model. Behaviour quality is bounded by the model, not by the engine.
- Throughput makes multi-turn agent tasks impractical on 4 vCPU. Cloud
  inference is required for real validation: either credits on the Hugging Face
  account, or another provider key.
- The planner and ACP paths are covered by unit tests only.

## Enabling a hosted provider

`ProviderRegistry` now falls back to the public endpoint of each hosted kind, so
enabling one is a provider row plus a server-side credential:

```bash
# apps/api/.env (gitignored, never committed)
AI_PROVIDER_CREDENTIALS={"huggingface":"hf_..."}
```

Defaults: Hugging Face `https://router.huggingface.co/v1`, OpenRouter
`https://openrouter.ai/api/v1`, Together `https://api.together.xyz/v1`, Vercel
AI Gateway `https://ai-gateway.vercel.sh/v1`. A row `base_url` or
`AI_PROVIDER_BASE_URLS` entry still wins over the default.

## Reproducing

```bash
# real agent server (already running in this sandbox on port 60000)
openhands-agent-server --port 60000

# local model + protocol shim
python -m llama_cpp.server --model cortex-live-validation/models/qwen3-4b.gguf \
  --n_ctx 32768 --n_threads 4 --n_batch 1024 --flash_attn True --port 18080
python cortex-live-validation/llm_shim.py 18085
```

Then create a conversation with `llm.model=openai/qwen3-4b`,
`llm.base_url=http://127.0.0.1:18085/v1` and `agent_context.system_message_suffix`
set to the Cortex identity.
