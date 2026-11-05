import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "test-utils";
import { HomeMobileChrome } from "#/components/features/home/home-mobile-chrome";
import { SidebarMobileNavProvider } from "#/components/features/sidebar/sidebar-mobile-nav-context";
import { I18nKey } from "#/i18n/declaration";

vi.mock("#/hooks/query/use-settings", () => ({
  useSettings: () => ({
    data: { git_user_name: "Coumbassa" },
    isFetching: false,
  }),
}));

describe("HomeMobileChrome", () => {
  it("shows account access and the three mobile destinations", () => {
    renderWithProviders(
      <SidebarMobileNavProvider>
        <HomeMobileChrome />
      </SidebarMobileNavProvider>,
      { navigation: { currentPath: "/conversations", conversationId: null } },
    );

    expect(screen.getByTestId("home-mobile-header")).toBeInTheDocument();
    expect(screen.getByTestId("home-mobile-account-link")).toHaveTextContent(
      "C",
    );
    expect(screen.getByTestId("home-mobile-home-link")).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByTestId("home-mobile-library-link")).toHaveAttribute(
      "href",
      "/settings/agents",
    );
    expect(
      screen.getByTestId("home-mobile-conversations-button"),
    ).toHaveAttribute("aria-label", I18nKey.SIDEBAR$CONVERSATIONS);
  });

  it("opens the conversation drawer from the bottom chat tab", () => {
    renderWithProviders(
      <SidebarMobileNavProvider>
        <HomeMobileChrome />
      </SidebarMobileNavProvider>,
    );

    const conversationsButton = screen.getByTestId(
      "home-mobile-conversations-button",
    );
    expect(conversationsButton).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(conversationsButton);

    expect(conversationsButton).toHaveAttribute("aria-pressed", "true");
  });
});
