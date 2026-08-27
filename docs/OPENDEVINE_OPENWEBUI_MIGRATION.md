# OpenDevine UI migration contract

## Objective

OpenDevine adopts the real Open WebUI interaction model and visual language while keeping OpenHands/OpenDevine as the execution engine. This document defines the boundary for incremental migration.

## Non-negotiable boundaries

The UI may change layout, navigation, styling, labels and presentation components. It must not replace or bypass the Agent Server adapter, the WebSocket/event path, MCP services, native client tools, child conversation launch, worktree isolation, mono-writer, runtime services, Live Preview URL handling or CI/CD policy.

A capability is visible as an active action only when its backend contract is available and tested. Test fixtures and mock API handlers remain test-only and must never be selected by the real development or production entrypoint.

## Stable flow

```text
OpenHands / Agent Server
  ↓
TypeScript API adapters and service hooks
  ↓
Normalized OpenHands event types
  ↓
Zustand stores and conversation state
  ↓
OpenDevine presentation components
  ↓
Open WebUI interaction shell
```

The presentation layer consumes application data and callbacks from existing hooks and stores. It does not call Agent Server endpoints directly. New presentation components should receive view data and intent callbacks, while API side effects remain in the existing services/hooks.

## Mapping from Open WebUI to OpenDevine

| Open WebUI surface | OpenDevine implementation boundary                                                        | Migration rule                                                           |
| ------------------ | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| Sidebar            | Existing `Sidebar`, conversation list, navigation context and sidebar store               | Re-theme and reorganize incrementally; keep existing navigation behavior |
| New Chat / Search  | Existing route links, command menu and conversation creation hooks                        | Preserve real creation and search services                               |
| Chat               | Existing `ConversationMain`, `ChatInterfaceWrapper`, event handler and WebSocket provider | Change presentation only; preserve event ordering and streaming          |
| Model selector     | Existing active profile and LLM/profile hooks                                             | Never infer a model from visual state alone                              |
| Attachments        | Existing conversation upload/file APIs and input handlers                                 | Keep real upload and error paths                                         |
| Tools/MCP          | Existing MCP APIs, settings and tool contracts                                            | Do not add a visual-only integration card                                |
| Workbench panels   | Existing files, terminal, browser, commits, planner, tasks and Preview routes             | Compose existing surfaces before creating replacement implementations    |
| Live Preview       | Existing forwarded URL, preview store and refresh hook                                    | No iframe/mock replacement; keep real server/URL lifecycle               |
| Agent/sub-agents   | Existing native client tools and child conversation service                               | Keep limits, worktree isolation and mono-writer enforcement              |

## First UI slice

The first implementation slice is the global shell: OpenDevine branding, Open WebUI-style sidebar hierarchy, conversation list navigation and a visually consistent conversation frame. It must not alter conversation creation, event transport, agent settings, MCP behavior or Preview routes. Acceptance requires lint, typecheck, focused UI tests, build and a real browser smoke check against the existing local backend.

## License and attribution

The Open WebUI repository and documentation must be reviewed before copying code or assets. The current official license page contains attribution and branding requirements for current releases. OpenDevine should prefer a clean React/TypeScript implementation of the verified interaction patterns and retain clear attribution where required; it must not imply official endorsement by Open WebUI.
