import React from "react";
import { ChevronUp, Settings } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useSettings } from "#/hooks/query/use-settings";
import { I18nKey } from "#/i18n/declaration";
import { NavigationLink } from "#/components/shared/navigation-link";
import { UserAvatar } from "./user-avatar";
import { cn } from "#/utils/utils";

interface SidebarUserProfileProps {
  collapsed: boolean;
}

function getDisplayName(name?: string, email?: string): string {
  const normalizedName = name?.trim();
  if (normalizedName) return normalizedName;

  const normalizedEmail = email?.trim();
  if (normalizedEmail) return normalizedEmail.split("@")[0] || normalizedEmail;

  return "Unknown User";
}

export function SidebarUserProfile({ collapsed }: SidebarUserProfileProps) {
  const { t } = useTranslation("openhands");
  const { data: settings, isFetching } = useSettings();
  const [isOpen, setIsOpen] = React.useState(false);

  const displayName = getDisplayName(
    settings?.git_user_name,
    settings?.email || settings?.git_user_email,
  );
  const email = settings?.email || settings?.git_user_email || "";

  if (collapsed) {
    return <UserAvatar isLoading={isFetching} />;
  }

  return (
    <div
      className="relative shrink-0 px-2.5 pb-1"
      data-testid="sidebar-user-profile"
    >
      {isOpen ? (
        <div
          className="absolute bottom-full left-2.5 right-2.5 z-50 mb-2 rounded-lg border border-border bg-surface-raised p-1 shadow-lg"
          role="menu"
          data-testid="sidebar-user-profile-menu"
        >
          <div className="px-2.5 py-2">
            <div className="truncate text-sm text-contrast">{displayName}</div>
            {email ? (
              <div className="truncate text-xs text-muted">{email}</div>
            ) : null}
          </div>
          <div className="my-1 border-t border-border" />
          <NavigationLink
            to="/settings/app"
            role="menuitem"
            onClick={() => setIsOpen(false)}
            className="flex h-9 items-center gap-2 rounded-md px-2.5 text-sm text-muted hover:bg-surface hover:text-contrast"
          >
            <Settings className="size-4" aria-hidden="true" />
            <span>{t(I18nKey.USER$ACCOUNT_SETTINGS)}</span>
          </NavigationLink>
        </div>
      ) : null}

      <button
        type="button"
        aria-expanded={isOpen}
        aria-haspopup="menu"
        data-testid="sidebar-user-profile-trigger"
        onClick={() => setIsOpen((open) => !open)}
        className={cn(
          "flex h-12 w-full items-center gap-3 rounded-lg px-2.5 text-left",
          "text-muted hover:bg-surface-raised hover:text-contrast",
        )}
      >
        <span className="flex size-8 shrink-0 items-center justify-center overflow-hidden rounded-full bg-blue-500 text-sm font-medium text-white">
          {displayName.slice(0, 1).toUpperCase()}
        </span>
        <span className="min-w-0 flex-1 truncate text-sm font-medium">
          {displayName}
        </span>
        <ChevronUp
          className={cn(
            "size-4 shrink-0 transition-transform",
            isOpen && "rotate-180",
          )}
          aria-hidden="true"
        />
      </button>
    </div>
  );
}
