# Sidebar navigation

This document records the sidebar changes introduced by `feat(sidebar): reorganize navigation and add user profile` (`d16668e`).

## Navigation

The sidebar now follows the requested task-oriented hierarchy while preserving the existing CORTEX branding and application shell:

- **New Task** opens the existing `/conversations` entry point.
- **Library** opens the existing agent-profile library at `/settings/agents`.
- **Projects** and **New Project** are shown as reserved navigation slots. They remain disabled because this repository does not currently expose a Projects backend or route; no fake project data is created.
- **Tasks** continues to use the existing conversation history and task list components.
- Existing `Customize`, `Automations`, settings, and backend-management access remain available so the reorganization does not remove application capabilities.

## User profile

The bottom profile control uses values already returned by the settings service. It displays the configured user name or the local part of the configured e-mail, and falls back to `Unknown User` when no identity data is available. The account menu exposes the existing account-settings route. No personal information, provider identity, avatar URL, or logout endpoint is fabricated: the current frontend does not expose a complete Google/GitHub/GitLab identity contract.

## Responsive behavior

The existing desktop collapsed rail and mobile drawer/overlay behavior are preserved. The new rows use the same sidebar layout primitives and responsive classes as the existing navigation.

## Verification

The following checks passed for the implementation commit:

- `npm run make-i18n`
- `npm run check-translation-completeness`
- staged TypeScript check (`react-router typegen && npx tsc --noEmit --skipLibCheck`)
- ESLint and Prettier through the pre-commit hook
- targeted Vitest tests for the sidebar and avatar: **28/28 passed**
