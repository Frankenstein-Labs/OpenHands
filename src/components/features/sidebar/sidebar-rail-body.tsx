import { useTranslation } from "react-i18next";
import {
  ChevronLeft,
  ChevronRight,
  BookOpen,
  Filter,
  FolderPlus,
  Plus,
  Settings,
} from "lucide-react";
import { OpenHandsLogoButton } from "#/components/shared/buttons/openhands-logo-button";
import { NavigationLink } from "#/components/shared/navigation-link";
import { getLockedCloudHost } from "#/api/agent-server-config";
import { useActiveBackendContext } from "#/contexts/active-backend-context";
import { SidebarCollapsedIconSlot } from "./sidebar-collapsed-icon-slot";
import { SidebarNavLink } from "./sidebar-nav-link";
import { I18nKey } from "#/i18n/declaration";
import { cn } from "#/utils/utils";
import { StyledTooltip } from "#/components/shared/buttons/styled-tooltip";
import { CommandMenuTrigger } from "#/components/features/command-menu/command-menu-trigger";
import { SidebarConversationList } from "./sidebar-conversation-list";
import { SidebarUserProfile } from "./sidebar-user-profile";
import {
  SIDEBAR_COLLAPSE_TOGGLE_OVERLAY_CLASS,
  SIDEBAR_COLLAPSED_LOGO_WRAPPER_CLASS,
  SIDEBAR_ICON_BUTTON_CLASS,
  SIDEBAR_ICON_SLOT_CLASS,
  sidebarHeaderRowClassName,
  sidebarNavLabelClassName,
  sidebarNavListClassName,
  sidebarNavRowClassName,
} from "./sidebar-layout";
import { useCanvasExtensionsRuntime } from "#/components/features/canvas-extensions/canvas-extensions-runtime";
import { CanvasExtensionIcon } from "#/components/features/canvas-extensions/canvas-extension-icon";

const ICON_SIZE = 18;
const SIDEBAR_LOGO_WIDTH = 34;
const SIDEBAR_LOGO_HEIGHT = Math.round((SIDEBAR_LOGO_WIDTH * 30) / 46);

export interface SidebarRailBodyProps {
  collapsed: boolean;
  showCollapseToggle: boolean;
  showMobileCloseButton?: boolean;
  onCloseMobile?: () => void;
  collapseToggleLabel: string;
  onCollapse: () => void;
  onExpand: () => void;
  showCollapsedExpandButton: boolean;
  currentPath: string;
}

export function SidebarRailBody({
  collapsed,
  showCollapseToggle,
  showMobileCloseButton = false,
  onCloseMobile,
  collapseToggleLabel,
  onCollapse,
  onExpand,
  showCollapsedExpandButton,
  currentPath,
}: SidebarRailBodyProps) {
  const { t } = useTranslation("openhands");
  const { active } = useActiveBackendContext();
  const { pages: canvasExtensionPages } = useCanvasExtensionsRuntime();
  const isCloudBackend = active.backend.kind === "cloud";
  const cloudSettingsOrgQuery = active.orgId
    ? `?org=${encodeURIComponent(active.orgId)}`
    : "";
  const cloudSettingsUrl = isCloudBackend
    ? `${active.backend.host.replace(/\/+$/, "")}/settings${cloudSettingsOrgQuery}`
    : null;
  const isLockedToCloud = getLockedCloudHost() !== null;
  const settingsLabel = t(I18nKey.SIDEBAR$SETTINGS);
  const settingsTestId = collapsed
    ? "collapsed-settings-link"
    : "sidebar-settings-link";
  const settingsLinkClassName = cn(
    sidebarNavRowClassName({ collapsed }),
    !collapsed &&
      currentPath.startsWith("/settings") &&
      "bg-tertiary text-contrast",
  );
  const settingsLinkContent = (
    <>
      {collapsed ? (
        <SidebarCollapsedIconSlot active={currentPath.startsWith("/settings")}>
          <Settings width={ICON_SIZE} height={ICON_SIZE} />
        </SidebarCollapsedIconSlot>
      ) : (
        <span className={SIDEBAR_ICON_SLOT_CLASS}>
          <Settings width={ICON_SIZE} height={ICON_SIZE} />
        </span>
      )}
      <span className={sidebarNavLabelClassName(collapsed)}>
        {settingsLabel}
      </span>
    </>
  );
  const settingsLink =
    isCloudBackend && cloudSettingsUrl ? (
      <a
        href={cloudSettingsUrl}
        target={isLockedToCloud ? undefined : "_blank"}
        rel={isLockedToCloud ? undefined : "noopener noreferrer"}
        data-testid={settingsTestId}
        aria-label={settingsLabel}
        className={settingsLinkClassName}
      >
        {settingsLinkContent}
      </a>
    ) : (
      <NavigationLink
        to="/settings"
        data-testid={settingsTestId}
        aria-label={settingsLabel}
        className={settingsLinkClassName}
      >
        {settingsLinkContent}
      </NavigationLink>
    );

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className={sidebarHeaderRowClassName(collapsed)}>
        <div
          className={cn(
            collapsed && showCollapseToggle
              ? SIDEBAR_COLLAPSED_LOGO_WRAPPER_CLASS
              : "flex min-w-0 shrink-0 items-center",
          )}
        >
          {!showMobileCloseButton ? (
            <div
              className={cn(
                collapsed &&
                  showCollapseToggle &&
                  "flex h-full w-full items-center justify-start pl-2.5 transition-opacity duration-150",
                collapsed && showCollapsedExpandButton && "opacity-0",
              )}
            >
              <OpenHandsLogoButton
                logoWidth={SIDEBAR_LOGO_WIDTH}
                logoHeight={SIDEBAR_LOGO_HEIGHT}
                logoClassName="max-w-none"
                className={cn(SIDEBAR_ICON_SLOT_CLASS, "overflow-visible")}
              />
            </div>
          ) : null}
          {collapsed && showCollapseToggle ? (
            <button
              type="button"
              data-testid="sidebar-collapse-toggle"
              aria-pressed={collapsed}
              aria-label={collapseToggleLabel}
              onClick={onExpand}
              className={cn(
                SIDEBAR_COLLAPSE_TOGGLE_OVERLAY_CLASS,
                showCollapsedExpandButton
                  ? "opacity-100 pointer-events-auto"
                  : "opacity-0 pointer-events-none",
              )}
            >
              <ChevronRight width={14} height={14} />
            </button>
          ) : null}
        </div>
        {!collapsed && showCollapseToggle ? (
          <button
            type="button"
            data-testid="sidebar-collapse-toggle"
            aria-pressed={collapsed}
            aria-label={collapseToggleLabel}
            onClick={onCollapse}
            className={cn(
              "hidden md:inline-flex ml-auto",
              SIDEBAR_ICON_BUTTON_CLASS,
              "text-muted hover:text-contrast hover:bg-surface-raised",
            )}
          >
            <ChevronLeft width={14} height={14} />
          </button>
        ) : null}
        {!collapsed && showMobileCloseButton ? (
          <button
            type="button"
            data-testid="sidebar-mobile-drawer-close"
            onClick={onCloseMobile}
            aria-label={t(I18nKey.SIDEBAR$CLOSE_MENU)}
            className={cn(
              "inline-flex ml-auto",
              SIDEBAR_ICON_BUTTON_CLASS,
              "text-muted hover:text-contrast hover:bg-surface-raised",
            )}
          >
            <ChevronLeft width={14} height={14} />
          </button>
        ) : null}
      </div>

      <nav className={sidebarNavListClassName(collapsed)}>
        <CommandMenuTrigger collapsed={collapsed} />
        {!collapsed ? (
          <div className="mt-5 flex h-9 items-center justify-between px-2.5 text-sm font-medium text-muted">
            <span>{t(I18nKey.SIDEBAR$PROJECTS)}</span>
            <button
              type="button"
              aria-label={t(I18nKey.SIDEBAR$NEW_PROJECT)}
              data-testid="sidebar-new-project-button"
              disabled
              className="rounded-md p-1 text-muted opacity-60"
              title={t(I18nKey.SIDEBAR$PROJECTS_UNAVAILABLE)}
            >
              <Plus className="size-5" aria-hidden="true" />
            </button>
          </div>
        ) : null}
        <button
          type="button"
          data-testid="sidebar-new-project-link"
          disabled
          className={cn(
            sidebarNavRowClassName({ collapsed }),
            "text-muted opacity-60",
          )}
          title={t(I18nKey.SIDEBAR$PROJECTS_UNAVAILABLE)}
        >
          <span className={SIDEBAR_ICON_SLOT_CLASS}>
            <FolderPlus width={ICON_SIZE} height={ICON_SIZE} />
          </span>
          <span className={sidebarNavLabelClassName(collapsed)}>
            {t(I18nKey.SIDEBAR$NEW_PROJECT)}
          </span>
        </button>
        {!collapsed ? (
          <div className="mt-5 flex h-9 items-center justify-between px-2.5 text-sm font-medium text-muted">
            <span>{t(I18nKey.COMMON$TASKS)}</span>
            <Filter className="size-5" aria-hidden="true" />
          </div>
        ) : null}
        {canvasExtensionPages.map((page) => (
          <SidebarNavLink
            key={`${page.extension.name}:${page.contribution.id}`}
            to={page.href}
            label={page.contribution.nav_label || page.contribution.title}
            testId={`sidebar-canvas-extension-${page.extension.name}-${page.contribution.id}`}
            collapsed={collapsed}
            icon={
              <CanvasExtensionIcon
                extension={page.extension}
                size={ICON_SIZE}
              />
            }
          />
        ))}
      </nav>

      <SidebarConversationList collapsed={collapsed} />
      {!collapsed ? <SidebarUserProfile collapsed={false} /> : null}

      <nav
        aria-label={t(I18nKey.SIDEBAR$NAVIGATION_LABEL)}
        data-testid="sidebar-bottom-navigation"
        className={cn(
          sidebarNavListClassName(collapsed),
          "mt-auto shrink-0 border-t border-border pt-2 pb-2",
        )}
      >
        <SidebarNavLink
          to="/conversations"
          end
          label={t(I18nKey.SIDEBAR$NEW_TASK)}
          testId="sidebar-new-task-link"
          collapsed={collapsed}
          icon={<Plus width={ICON_SIZE} height={ICON_SIZE} />}
        />
        <SidebarNavLink
          to="/settings/agents"
          label={t(I18nKey.SIDEBAR$LIBRARY)}
          testId="sidebar-library-link"
          collapsed={collapsed}
          icon={<BookOpen width={ICON_SIZE} height={ICON_SIZE} />}
        />
        {collapsed ? (
          <StyledTooltip content={settingsLabel} placement="right">
            {settingsLink}
          </StyledTooltip>
        ) : (
          settingsLink
        )}
      </nav>
    </div>
  );
}
