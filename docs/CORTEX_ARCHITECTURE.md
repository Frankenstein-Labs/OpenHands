# CORTEX AI architecture and autonomy plan

This document is the Phase 2 technical audit for the CORTEX AI fork. It records
the real dependency graph of this repository, the target architecture, and the
concrete work needed to run CORTEX AI under its own identity with independent
infrastructure. It is descriptive: nothing here adds services the repo does not
need, and no functional integration was removed to write it.

The companion pages are `docs/BRANDING.md` (what is rebranded) and
`docs/SELF_HOSTING.md` (upstream self-hosting guide).

---

## 1. Current architecture (verified in code)

This repository is the **frontend/control plane**, `@openhands/agent-canvas`.
The agent engine runs in a separate process/container.

```
Browser
  └── CORTEX AI UI (this repo: React + Vite + React Router, Electron shell)
        ├── Backend registry (local | cloud)  ── src/api/backend-registry
        ├── @openhands/typescript-client       ── typed agent-server clients
        └── @openhands/extensions              ── automation catalog/skills
              │
              ├── LOCAL backend  ── agent-server over HTTP + WebSocket
              │      started by the launcher via `uvx` / Docker (`ghcr.io/openhands/agent-server`)
              │      also runs the automation service and file/bash services
              │
              └── CLOUD backend  ── OpenHands Cloud (app.all-hands.dev)
                     per-conversation runtime at *.prod-runtime.all-hands.dev
                     auth: OAuth device-flow -> session API key, or cookie
```

Key facts (with sources):

- The UI talks to the backend through `@openhands/typescript-client`
  (`src/api/**`; 95 source files import it) and reads the automation catalog
  from `@openhands/extensions` (36 files).
- The **local** backend is the agent-server (`config/defaults.json`:
  `openhands-agent-server`, `openhands-automation`, ports 18000/18001/8000).
- The **cloud** backend is the OpenHands Cloud app, proxied through
  `src/api/cloud/proxy.ts`, with per-conversation runtimes on
  `*.prod-runtime.all-hands.dev` (`src/api/runtime-service/...`,
  `src/api/git-service/...`).
- There is **no server-side user model in this repo**. The "backend" the UI
  configures _is_ the identity boundary; credentials live client-side in the
  backend registry.

## 2. OpenHands dependencies (categorized)

Legend: **Indispensable** = must exist for the app to work at all;
**Replaceable** = swappable with configuration or a small adapter;
**Optional** = can be disabled without losing core functionality.

### npm

| Dependency                     | Role                                                           | Category                                             |
| ------------------------------ | -------------------------------------------------------------- | ---------------------------------------------------- |
| `@openhands/typescript-client` | Typed agent-server + cloud clients, device-flow, ACP providers | **Indispensable** (or reimplement the wire protocol) |
| `@openhands/extensions`        | Automation catalog + skills metadata                           | **Replaceable** (vendored/bundled catalog)           |

### Network services

| Service                                                               | Role                                     | Category                                         |
| --------------------------------------------------------------------- | ---------------------------------------- | ------------------------------------------------ |
| Local agent-server over HTTP/WS                                       | Runs agents, tools, bash, file, git, MCP | **Indispensable**                                |
| OpenHands Cloud (`app.all-hands.dev`, `*.prod-runtime.all-hands.dev`) | Hosted agents + device-flow auth + orgs  | **Replaceable** by a self-hosted agent-server    |
| `docs.openhands.dev`                                                  | Help/onboarding links only               | **Optional**                                     |
| `openhands.dev/joinslack`                                             | Community link only                      | **Optional**                                     |
| `z.openhands.dev` → PostHog                                           | Telemetry proxy                          | **Optional** (disable via `VITE_DO_NOT_TRACK=1`) |

### Auth

| Mechanism                       | Role                                                                                                                     | Category                                     |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------- |
| Local session API key           | Authenticates the browser to the local agent-server (`VITE_SESSION_API_KEY` / `window.__AGENT_CANVAS_SESSION_API_KEY__`) | **Indispensable** for local                  |
| OAuth 2.0 device flow           | Exchanges a user code for an OpenHands Cloud session API key                                                             | **Replaceable** (any IdP with a device flow) |
| Cookie auth (`--lock-to-cloud`) | Same-origin cookie session on a locked host                                                                              | **Replaceable**                              |

### Storage

| Store                                                               | Contents                                                                                                                                        | Category                                      |
| ------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------- |
| Backend registry (`openhands-backends`, `openhands-active-backend`) | Hosts + API keys (client-side)                                                                                                                  | **Indispensable** (local-first)               |
| Conversation state (`conversation-state-*`), drafts                 | UI state                                                                                                                                        | **Optional**                                  |
| Backend health, telemetry consent, onboarding checklist             | UI state                                                                                                                                        | **Optional**                                  |
| Server-side conversations/bash events                               | `config/defaults.json` `paths.*` (`agent-canvas/conversations`, `agent-canvas/bash_events`), automation SQLite DB (`automation/automations.db`) | **Indispensable** (owned by the agent-server) |

### Telemetry

| Item                                                             | Role                                               | Category     |
| ---------------------------------------------------------------- | -------------------------------------------------- | ------------ |
| `src/services/telemetry.ts` + `config/defaults.json` `telemetry` | Anonymous PostHog events through `z.openhands.dev` | **Optional** |

### GitHub

- Git is integrated through the **agent-server** (`src/api/git-service`), not a
  direct GitHub OAuth client in this repo. Provider support in the manifest
  validator: `github`, `gitlab`, `bitbucket`.

## 3. Target CORTEX architecture

Only two components need to exist for CORTEX AI to be functionally independent:

```
CORTEX AI UI (this repo, already present)
  └── CORTEX agent-server  ==  the existing OpenHands agent-server, run under
      CORTEX's own infrastructure (same image or a CORTEX-published one)
        ├── model providers  ── already provider-agnostic (see §4)
        ├── conversation/git/bash/MCP services ── unchanged
        └── storage ── the server's own state dirs / DB (already configurable)
```

What can be **kept as-is**: the UI, the agent engine, the tool/runtime layer,
the conversation and git services, the storage layout, the model-provider
abstraction. What must be **configured** (no new code): the backend host, the
session key, the model connections, telemetry. What would require **real
development**: a CORTEX account system (identity, orgs, billing) — but only if
CORTEX wants hosted multi-tenant accounts; a self-hosted agent-server already
gives a working single-tenant experience today.

## 4. Authentication and accounts

Today the app has **no first-party account system**. It authenticates _to a
backend_:

1. **Local**: a pre-generated session API key authenticates the browser to the
   local agent-server. No user accounts.
2. **Cloud**: OAuth 2.0 **device flow** against OpenHands Cloud yields a session
   API key; or cookie auth when the deployment is locked to the Cloud host
   (`VITE_LOCK_TO_CLOUD`).

To let a future CORTEX deployment use its **own** accounts, without faking an
OAuth provider or storing secrets in code:

- **Recommended (no new auth server):** deploy CORTEX's own agent-server and use
  the existing **session API key** path (generate the key at deploy time, inject
  it via `VITE_SESSION_API_KEY` or the launcher flag). This is exactly how the
  published desktop/npm binary works and needs no account model.
- **If CORTEX wants hosted multi-tenant accounts:** stand up an identity service
  that speaks the same **device-flow** contract the client already implements
  (`src/api/device-flow-client.ts`) and issues session API keys. The client
  change is then limited to the host used by `startDeviceFlow`, not new auth
  code.
- Note: a "Sign in with GitHub" is an _identity_ step, not a complete
  authorization model for agents; it does not replace per-conversation session
  keys or sandbox isolation.

There is no secret to add to source: keys stay in the deploy environment or the
client-side backend registry.

## 5. AI models

The model layer is already **provider-agnostic** and does not need to change for
CORTEX:

- Providers are enumerated in `src/utils/map-provider.ts` (~27 providers:
  OpenAI, Anthropic, Azure, Bedrock, Gemini, Ollama, OpenRouter, …).
- Settings expose **custom provider connections** with an arbitrary `base_url`
  and `api_key` (`src/api/provider-connections-service`, the "custom" provider in
  `provider-connection-modal.tsx`). This already covers:
  - **third-party hosted models** (a provider + key),
  - **self-hosted models** (e.g. Ollama/OpenAI-compatible `base_url`),
  - a future **CORTEX-hosted endpoint** (a custom connection pointing at it).
- The UI (model selector, profiles) is separate from inference: inference runs
  in the agent-server/LLM; the UI only stores connection metadata.

So "CORTEX models" today means _CORTEX-configured connections to existing
providers or CORTEX's own OpenAI-compatible endpoint_. There is **no proprietary
CORTEX model** in this repository, and none is claimed.

## 6. Legacy OpenHands services — keep / remove plan

| Service                                                   | Role                                                        | Depends on it                                   | If removed                                                 | Replacement                                 | Migration                                                                                                               |
| --------------------------------------------------------- | ----------------------------------------------------------- | ----------------------------------------------- | ---------------------------------------------------------- | ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| OpenHands Cloud app host (`app.all-hands.dev`)            | Optional hosted backend + device-flow + settings deep-links | Cloud onboarding, device flow, "API keys" links | Cloud onboarding stops working; local self-host unaffected | CORTEX-hosted app/agent-server              | Keep default; override with `VITE_LOCK_TO_CLOUD` / backend registry; central default now in `EXTERNAL_ORIGINS.cloudApp` |
| Per-conversation runtime (`*.prod-runtime.all-hands.dev`) | Runs cloud conversations                                    | Cloud conversations/terminal/git                | Cloud conversations unavailable                            | Self-hosted agent-server runtime URL        | No change needed for local; cloud path follows the cloud host                                                           |
| `docs.openhands.dev`                                      | Help links                                                  | Onboarding/settings tooltips                    | Links 404 if replaced wrongly                              | CORTEX docs site                            | Centralized in `EXTERNAL_ORIGINS.docs` + `docsUrl()`; swap one constant                                                 |
| `openhands.dev/joinslack`                                 | Community link                                              | Sidebar checklist                               | Dangling invite                                            | CORTEX community URL                        | Centralized in `EXTERNAL_ORIGINS.slackCommunity`                                                                        |
| `z.openhands.dev` telemetry proxy                         | PostHog ad-blocker bypass                                   | Telemetry delivery                              | Telemetry silently drops                                   | CORTEX PostHog project or disable           | `VITE_POSTHOG_HOST` / `VITE_DO_NOT_TRACK=1`                                                                             |
| `ghcr.io/openhands/*` images                              | Agent-server + canvas images                                | Docker/desktop runtimes                         | Runtimes can't pull                                        | Publish CORTEX images from the same sources | Change `config/defaults.json` `images.*`                                                                                |
| `openhands-*` PyPI packages                               | Agent-server via `uvx`                                      | npm/desktop launchers                           | Launchers can't start the engine                           | Mirror/publish under CORTEX                 | Change `config/defaults.json` `packages.*` / `versions.*`                                                               |

No integration was deleted in this phase.

## 7. Security posture (checked, unchanged)

- **API keys**: never hardcoded in source; supplied by env/runtime injection
  (`VITE_SESSION_API_KEY`, `window.__AGENT_CANVAS_SESSION_API_KEY__`) or stored
  client-side in the backend registry. Telemetry's PostHog key in
  `config/defaults.json` is a public, write-only ingestion key.
- **User sessions**: session API keys are per-backend/per-conversation;
  `remote` runtimes use the conversation's `X-Session-API-Key`.
- **Agent permissions / command execution / isolation**: enforced by the
  agent-server sandbox and runtime, not weakened here.
- **Private GitHub repos**: git flows through the agent-server with the user's
  credentials; this repo holds no GitHub token.
- **Conversation data**: stored by the agent-server under its state dirs (local)
  or by the cloud backend; the UI persists only per-conversation UI state.
- No security mechanism was disabled for this work.

## 8. Priority execution plan

1. **Publish CORTEX agent-server + canvas images/packages** and point
   `config/defaults.json` (`images.*`, `packages.*`) and the desktop/npm
   launchers at them, so CORTEX runs its own engine binaries.
2. **Choose the CORTEX backend + auth**: either deploy the self-hosted
   agent-server with a session key (fastest, no accounts) or stand up an
   identity service speaking the existing device-flow contract; set
   `VITE_LOCK_TO_CLOUD` / `EXTERNAL_ORIGINS.cloudApp` accordingly.
3. **Swap docs/community/telemetry**: replace `EXTERNAL_ORIGINS.docs` and
   `.slackCommunity` with CORTEX URLs once they exist, and point telemetry at a
   CORTEX PostHog project or disable it (`VITE_DO_NOT_TRACK=1`).
