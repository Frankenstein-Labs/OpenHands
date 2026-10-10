# CORTEX AI branding and customization

This repository is the frontend for **CORTEX AI** (Frankenstein Labs), built on
the open-source OpenHands agent engine. This document records what was rebranded,
what was intentionally left untouched, and where the remaining external
dependencies are configured.

## What is branded

| Surface | Source of truth |
| --- | --- |
| Web app product name (document title, meta) | `src/constants/branding.ts` (`BRANDING`) |
| Browser tab / conversation title | `src/hooks/use-app-title.ts` (reads `BRANDING.productName`) |
| In-app shell strings (welcome, hero copy, first chat message) | `src/i18n/translation.json` (`BRANDING$*`, `ONBOARDING$TITLE`, `HOME$OPENHANDS_DESCRIPTION`, `LANDING$SUBTITLE`, `CHAT_INTERFACE$INITIAL_MESSAGE`) |
| PWA manifest name | `public/site.webmanifest` |
| Desktop product name + installer artifacts | `electron-builder.config.mjs`, `electron/package.json`, `electron/loading.html`, `electron/main.mjs` |
| App wordmark (sidebar, shared conversation) | `src/assets/branding/cortex-logo.svg` |

## What is intentionally NOT rebranded

Renaming any of the following would break a functional integration, a wire
contract, or a license/attribution obligation. They keep the OpenHands name:

- **Agent engine identity** — the built-in agent is OpenHands
  (`src/utils/map-provider.ts` provider id `openhands`,
  `src/constants/acp-providers.ts`, `SETTINGS$AGENT_TYPE_OPENHANDS`). The engine
  is a distinct product from this UI.
- **LLM provider IDs** — the `openhands` provider and its models.
- **npm package name** (`@openhands/agent-canvas`) and **imports**
  (`@openhands/typescript-client`, `@openhands/extensions`).
- **Container images** — `ghcr.io/openhands/agent-server`, `ghcr.io/openhands/agent-canvas`.
- **Python package names** — `openhands-agent-server`, `openhands-tools`, `openhands-workspace`.
- **`OH_*` environment variables** consumed by the agent server.
- **Source repositories** — `github.com/OpenHands/*` references in docs.
- **License and attribution** — `LICENSE`, copyright headers.

## External service dependencies (customization points)

These are functional today and are the knobs to turn when CORTEX AI gets its own
infrastructure. None of them is replaced with an invented domain.

| Dependency | Where | Notes |
| --- | --- | --- |
| OpenHands Cloud host (`app.all-hands.dev`, `app.openhands.dev`) | `src/utils/constants.ts`, `src/api/agent-server-config.ts`, `src/components/features/backends/backend-form-modal.tsx` | Default hosted backend. Configurable at runtime; a self-hosted backend can be used instead. |
| Locked Cloud host | `VITE_LOCK_TO_CLOUD` (see `.env.sample`) | Pins the app to a specific Cloud/self-hosted host. |
| Telemetry proxy (`z.openhands.dev` → PostHog) | `src/services/telemetry.ts`, `config/defaults.json` | Disable with `VITE_DO_NOT_TRACK=1` or override `VITE_POSTHOG_HOST`. |
| Documentation links (`docs.openhands.dev`) | onboarding checklist, settings help, manifests | Upstream docs. Replace only when CORTEX AI documentation exists. |
| Community links (`openhands.dev/joinslack`, `go.openhands.dev/slack`) | `src/components/features/sidebar/sidebar-onboarding-checklist.constants.ts`, `README.md` | Replace when CORTEX AI community channels exist. |
| Asset CDN (`assets.openhands.dev`) | `README.md` | Documentation images only. |
| Agent server + automation (uvx / PyPI) | `config/defaults.json`, `scripts/*` | `OH_AGENT_SERVER_*` select the engine version. |

## Planned next steps toward independence

1. Stand up CORTEX AI documentation and community URLs, then swap the
   `docs.openhands.dev` / `openhands.dev` links.
2. Decide the CORTEX AI Cloud / self-hosted host and set `VITE_LOCK_TO_CLOUD`
   (or replace `PRODUCT_URL.PRODUCTION`).
3. Point telemetry at CORTEX AI's own PostHog project (`VITE_POSTHOG_API_KEY`,
   `VITE_POSTHOG_HOST`) or disable it.
