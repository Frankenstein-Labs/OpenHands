# Cortex identity

Cortex is the public name of the agent and of the platform in this repository.
It is built by Frankenstein-Labs. OpenHands is the open-source engine and the
Agent Canvas frontend underneath, kept as a technical foundation and credited
in `LICENSE` and `NOTICE`.

## What the agent says about itself

Every new conversation receives an identity block in its system prompt
(`src/constants/cortex-identity.ts`), appended by
`buildStartConversationRequest` and by the local planner builder in
`src/api/agent-server-adapter.ts`.

The block states, in English:

- the agent's name is Cortex and it is built by Frankenstein-Labs;
- it helps with real software work: exploring a codebase, writing and reviewing
  code, running commands and tests in a terminal, editing files, fixing
  failures, using Git;
- it must say when a tool is unavailable instead of pretending it used one;
- OpenHands is its technical foundation, not its name: the agent mentions
  OpenHands only for questions about lineage, licensing or the underlying
  engine;
- it answers "who are you", "who created you", "what is your mission" and "what
  can you do" naturally, without reciting the block on every turn.

The block is injected for the native Cortex/OpenHands harness and for the
planner. ACP profiles (Claude Code, Codex, Gemini, Pi, OpenCode) run another
vendor's CLI and keep their own identity, so they do not receive it.

## Surfaces rebranded

| Surface | File | Value |
|---|---|---|
| App title | `src/root.tsx` | `Cortex` |
| App description | `src/root.tsx` | `Cortex — the AI engineering agent by Frankenstein-Labs.` |
| PWA manifest | `public/site.webmanifest` | `Cortex` |
| Desktop loading screen | `electron/loading.html` | `Cortex` |
| Sidebar mark, agent chip, shared conversation header | `src/assets/branding/cortex-logo.svg` | Cortex orbit mark |
| Product name, onboarding, chat, browser, automation and telemetry copy | `src/i18n/translation.json` | 25 keys, all 16 locales |
| Backend service name and OpenAPI title | `apps/api/app/core/config.py`, `apps/api/app/main.py` | `Cortex SaaS API` |

The i18n rewrite is key-scoped, not a global replacement: each selected key had
its `OpenHands` token replaced by `Cortex` in every locale, so the surrounding
sentences stay correct.

## Surfaces that keep the OpenHands name

These are real third-party products or legal notices. Renaming them would be
false:

- `BACKEND$CLOUD_*`, `SETTINGS$NEED_OPENHANDS_ACCOUNT`,
  `SETTINGS$OPENHANDS_API_KEY_*`, `RESPONDER_DEPLOYMENT$OPENHANDS_CLOUD_*` —
  the hosted OpenHands Cloud service.
- `SCHEMA$VERIFICATION$*`, `SETTINGS$META_PROFILE_TEMPLATE_ROUTER_*`,
  `SETTINGS$OPENHANDS_FREE_MODELS_NOTE` — the OpenHands model provider.
- `LICENSE$*` — OpenHands Enterprise licence notices.
- `LICENSE`, `NOTICE`, dependency names, package names and imports.

## Tests

```bash
npx vitest run src/constants/cortex-identity.test.ts \
  __tests__/i18n/cortex-branding.test.ts \
  src/api/agent-server-adapter.test.ts
```

- `cortex-identity.test.ts` checks the name, the creator, the mission, the real
  capability list, the honesty rules and the OpenHands lineage wording.
- `cortex-branding.test.ts` checks every product key says Cortex in every
  locale and that external service names and licence notices still say
  OpenHands.
- `agent-server-adapter.test.ts` checks the identity block reaches both the
  managed-agent launch payload and the planner payload, and is absent for ACP.

## Extending the persona

The identity block is a plain exported string, so a later per-organisation or
per-plan persona can be composed by appending to it, without touching the
conversation builder. Keep capability claims limited to tools the agent
actually receives; the honesty rules exist so the agent does not promise
features that are not implemented.
