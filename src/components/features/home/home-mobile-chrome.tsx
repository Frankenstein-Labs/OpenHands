import { useTranslation } from "react-i18next";
import { Grid2X2, House, MessageCircle } from "lucide-react";
import { useSettings } from "#/hooks/query/use-settings";
import { useNavigation } from "#/context/navigation-context";
import { useSidebarMobileNav } from "#/components/features/sidebar/sidebar-mobile-nav-context";
import { NavigationLink } from "#/components/shared/navigation-link";
import { I18nKey } from "#/i18n/declaration";
import { cn } from "#/utils/utils";

function getAvatarInitial(name?: string, email?: string): string {
  const normalizedName = name?.trim();
  if (normalizedName) return normalizedName.slice(0, 1).toUpperCase();
  const normalizedEmail = email?.trim();
  return normalizedEmail ? normalizedEmail.slice(0, 1).toUpperCase() : "?";
}

export function HomeMobileChrome() {
  const { t } = useTranslation("openhands");
  const { data: settings } = useSettings();
  const { currentPath } = useNavigation();
  const { isOpen, toggle } = useSidebarMobileNav();
  const isHomeActive = currentPath === "/" || currentPath === "/conversations";
  const accountLabel = t(I18nKey.USER$ACCOUNT_SETTINGS);
  const accountInitial = getAvatarInitial(
    settings?.git_user_name,
    settings?.email || settings?.git_user_email,
  );

  const navItemClassName = (active: boolean) =>
    cn(
      "flex size-14 items-center justify-center rounded-full transition-colors",
      active
        ? "bg-white/10 text-white"
        : "text-white/80 hover:bg-white/10 hover:text-white",
    );

  return (
    <>
      <header
        data-testid="home-mobile-header"
        className="absolute inset-x-0 top-0 z-30 flex h-16 items-center justify-between gap-3 px-4 md:hidden"
        style={{ paddingTop: "env(safe-area-inset-top)" }}
      >
        <div className="min-w-0 flex-1" aria-hidden="true" />
        <NavigationLink
          to="/settings/app"
          aria-label={accountLabel}
          title={accountLabel}
          data-testid="home-mobile-account-link"
          className="flex size-10 shrink-0 items-center justify-center rounded-full border border-white/20 bg-accent text-sm font-semibold text-white shadow-lg"
        >
          {accountInitial}
        </NavigationLink>
      </header>

      <nav
        data-testid="home-mobile-bottom-nav"
        aria-label={t(I18nKey.SIDEBAR$NAVIGATION_LABEL)}
        className="absolute inset-x-0 bottom-0 z-30 flex justify-center px-4 pb-3 md:hidden"
        style={{ paddingBottom: "max(0.75rem, env(safe-area-inset-bottom))" }}
      >
        <div className="flex h-16 w-full max-w-lg items-center justify-around rounded-full border border-white/10 bg-surface/90 px-2 shadow-2xl backdrop-blur-xl">
          <NavigationLink
            to="/conversations"
            end
            aria-label={t(I18nKey.SIDEBAR$NEW_TASK)}
            aria-current={isHomeActive ? "page" : undefined}
            className={navItemClassName(isHomeActive)}
            data-testid="home-mobile-home-link"
          >
            <House className="size-6" aria-hidden="true" />
          </NavigationLink>
          <NavigationLink
            to="/settings/agents"
            aria-label={t(I18nKey.SIDEBAR$LIBRARY)}
            className={({ isActive }) => navItemClassName(isActive)}
            data-testid="home-mobile-library-link"
          >
            <Grid2X2 className="size-6" aria-hidden="true" />
          </NavigationLink>
          <button
            type="button"
            aria-label={t(I18nKey.SIDEBAR$CONVERSATIONS)}
            aria-pressed={isOpen}
            onClick={toggle}
            className={navItemClassName(isOpen)}
            data-testid="home-mobile-conversations-button"
          >
            <MessageCircle className="size-6" aria-hidden="true" />
          </button>
        </div>
      </nav>
    </>
  );
}
