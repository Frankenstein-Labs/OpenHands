# Third-party notices

## LibreChat

This interface adaptation incorporates interaction and visual patterns from the LibreChat project, including the landing-page composition and SplitText-style animated greeting from `client/src/components/Chat/Landing.tsx`, plus its surface-role approach from `client/src/style.css`.

LibreChat is Copyright (c) 2026 LibreChat AI and contributors and is distributed under the MIT License. The source repository is available at <https://github.com/LibreChat-AI/LibreChat>.

The OpenHands adaptation lives in:

- `src/components/features/home/home-header/librechat-landing-title.tsx`
- `src/index.css` under the `LibreChat visual skin` section

The OpenHands-specific hooks and components remain responsible for conversation creation, Agent Canvas/Cortex state, workspaces, repositories, files, plugins, automations and model selection.

The complete LibreChat license text is retained in the source repository at `https://github.com/LibreChat-AI/LibreChat/blob/main/LICENSE`.
