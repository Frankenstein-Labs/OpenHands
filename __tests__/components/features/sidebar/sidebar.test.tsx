import {
  act,
  render,
  screen,
  fireEvent,
  within,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Sidebar } from "#/components/features/sidebar/sidebar";
import { SidebarMobileNavProvider } from "#/components/features/sidebar/sidebar-mobile-nav-context";
import { SidebarMobileMenuBar } from "#/components/features/sidebar/sidebar-mobile-menu-bar";
import { useSidebarStore } from "#/stores/sidebar-store";
import {
  NavigationProvider,
  type NavigationContextValue,
} from "#/context/navigation-context";
import translations from "#/i18n/translation.json";

// Resolve labels through the source-of-truth translations for readable assertions.
vi.mock("react-i18next", async () => {
  const actual = await vi.importActual("react-i18next");
  return {
    ...(actual as object),
    useTranslation: () => ({
      t: (key: string) => {
        const entry = (translations as Record<string, Record<string, string>>)[
          key
        ];
        return entry?.en ?? key;
      },
      i18n: { language: "en", exists: () => false },
    }),
  };
});
vi.mock("#/hooks/query/use-config", () => ({
  useConfig: () => ({ data: { feature_flags: {} } }),
}));
vi.mock("#/hooks/query/use-settings", () => ({
  useSettings: () => ({
    data: { email_verified: true },
    error: null,
    isError: false,
    isFetching: false,
  }),
  getErrorStatus: () => undefined,
}));
vi.mock("#/contexts/active-backend-context", () => {
  const active = {
    backend: { id: "local", name: "Local", kind: "local" },
    orgId: null,
  };
  return {
    useActiveBackendContext: () => ({
      backends: [active.backend],
      active,
      setActive: vi.fn(),
    }),
    useActiveBackend: () => active,
  };
});
vi.mock("#/components/shared/buttons/styled-tooltip", () => ({
  StyledTooltip: ({ children }: { children: unknown }) => children,
}));
vi.mock("#/components/shared/buttons/openhands-logo-button", () => ({
  OpenHandsLogoButton: () => <div data-testid="logo-button" />,
}));
vi.mock("#/components/features/conversation-panel/conversation-panel", () => ({
  ConversationPanel: () => null,
}));
vi.mock(
  "#/components/features/conversation-panel/conversation-panel-wrapper",
  () => ({
    ConversationPanelWrapper: () => null,
  }),
);
vi.mock("#/components/features/command-menu/command-menu-trigger", () => ({
  CommandMenuTrigger: () => <div data-testid="command-menu-trigger" />,
}));
vi.mock(
  "#/components/features/canvas-extensions/canvas-extensions-runtime",
  () => ({
    useCanvasExtensionsRuntime: () => ({ pages: [] }),
  }),
);
vi.mock("#/components/features/sidebar/sidebar-conversation-list", () => ({
  SidebarConversationList: () => (
    <div data-testid="sidebar-conversation-list" />
  ),
}));
vi.mock("#/components/shared/modals/settings/settings-modal", () => ({
  SettingsModal: () => null,
}));

function getDesktopSidebar(collapsed?: boolean): HTMLElement {
  const selector =
    collapsed === undefined
      ? "aside[data-collapsed]"
      : `aside[data-collapsed="${collapsed ? "true" : "false"}"]`;
  const sidebar = document.querySelector(selector);
  if (!(sidebar instanceof HTMLElement)) {
    throw new Error(`Desktop sidebar not found: ${selector}`);
  }
  return sidebar;
}

function renderSidebar(currentPath: string) {
  const navigate = vi.fn();
  const value: NavigationContextValue = {
    currentPath,
    conversationId: null,
    isNavigating: false,
    navigate,
  };
  const rendered = render(
    <QueryClientProvider client={new QueryClient()}>
      <NavigationProvider value={value}>
        <SidebarMobileNavProvider>
          <Sidebar />
          <SidebarMobileMenuBar />
        </SidebarMobileNavProvider>
      </NavigationProvider>
    </QueryClientProvider>,
  );
  return { ...rendered, navigate };
}

describe("Sidebar", () => {
  beforeEach(() => {
    window.localStorage.clear();
    useSidebarStore.setState({ collapsed: false });
  });
  afterEach(() => {
    window.localStorage.clear();
    useSidebarStore.setState({ collapsed: false });
  });

  it("opens and closes the mobile navigation drawer from the menu button", async () => {
    renderSidebar("/conversations");
    expect(
      screen.queryByTestId("sidebar-mobile-drawer"),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("sidebar-mobile-menu-toggle"));
    const drawer = screen.getByTestId("sidebar-mobile-drawer");
    expect(drawer).toBeInTheDocument();
    expect(within(drawer).queryByTestId("logo-button")).not.toBeInTheDocument();
    expect(
      within(drawer).getByTestId("sidebar-conversation-list"),
    ).toBeInTheDocument();
    fireEvent.click(within(drawer).getByTestId("sidebar-mobile-drawer-close"));
    await waitFor(() => {
      expect(
        screen.queryByTestId("sidebar-mobile-drawer"),
      ).not.toBeInTheDocument();
    });
  });

  it("leaves the mobile drawer open when a menu inside it already handled Escape", () => {
    renderSidebar("/conversations");
    const toggle = screen.getByTestId("sidebar-mobile-menu-toggle");
    fireEvent.click(toggle);
    const handledEscape = new KeyboardEvent("keydown", {
      key: "Escape",
      bubbles: true,
      cancelable: true,
    });
    handledEscape.preventDefault();
    act(() => document.body.dispatchEvent(handledEscape));
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });

  it("toggles between expanded and collapsed states and persists the choice", () => {
    const { unmount } = renderSidebar("/conversations");
    expect(getDesktopSidebar(false).dataset.collapsed).toBe("false");
    fireEvent.click(screen.getByTestId("sidebar-collapse-toggle"));
    expect(getDesktopSidebar(true).dataset.collapsed).toBe("true");
    unmount();
    renderSidebar("/conversations");
    expect(getDesktopSidebar(true).dataset.collapsed).toBe("true");
  });

  it("expands the sidebar from the collapsed state", () => {
    useSidebarStore.setState({ collapsed: true });
    renderSidebar("/conversations");
    fireEvent.click(screen.getByTestId("sidebar-collapse-toggle"));
    expect(getDesktopSidebar(false).dataset.collapsed).toBe("false");
  });

  it("expands the sidebar when empty collapsed rail space is clicked", () => {
    useSidebarStore.setState({ collapsed: true });
    renderSidebar("/conversations");
    fireEvent.click(getDesktopSidebar(true));
    expect(getDesktopSidebar(false).dataset.collapsed).toBe("false");
  });

  it("places New Task and Library after conversations and removes the sidebar promos and workspace selector", () => {
    renderSidebar("/conversations");
    const conversationList = screen.getByTestId("sidebar-conversation-list");
    const bottomNav = screen.getByTestId("sidebar-bottom-navigation");
    expect(
      conversationList.compareDocumentPosition(bottomNav) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      within(bottomNav).getByTestId("sidebar-new-task-link"),
    ).toHaveTextContent("New Task");
    expect(
      within(bottomNav).getByTestId("sidebar-library-link"),
    ).toHaveTextContent("Library");
    expect(
      within(bottomNav).getByTestId("sidebar-settings-link"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("sidebar-onboarding-checklist"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("agent-canvas-version-tile"),
    ).not.toBeInTheDocument();
    expect(screen.queryByTestId("backend-selector")).not.toBeInTheDocument();
    expect(screen.queryByTestId("sidebar-skills-link")).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("sidebar-automations-link"),
    ).not.toBeInTheDocument();
  });

  it("keeps New Task, Library and Settings at the bottom of the collapsed rail", () => {
    useSidebarStore.setState({ collapsed: true });
    renderSidebar("/conversations");
    const bottomNav = screen.getByTestId("sidebar-bottom-navigation");
    expect(
      within(bottomNav).getByTestId("sidebar-new-task-link"),
    ).toBeInTheDocument();
    expect(
      within(bottomNav).getByTestId("sidebar-library-link"),
    ).toBeInTheDocument();
    expect(
      within(bottomNav).getByTestId("collapsed-settings-link"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("collapsed-backend-selector-link"),
    ).not.toBeInTheDocument();
  });

  it("navigates to settings when the collapsed Settings link is clicked", () => {
    useSidebarStore.setState({ collapsed: true });
    const { navigate } = renderSidebar("/conversations");
    fireEvent.click(screen.getByTestId("collapsed-settings-link"));
    expect(navigate).toHaveBeenCalledWith("/settings", { replace: false });
  });
});
