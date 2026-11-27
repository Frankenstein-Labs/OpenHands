import {
  lazy,
  Suspense,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { FileText, MessageSquare } from "lucide-react";
import { useTranslation } from "react-i18next";
import { cn } from "#/utils/utils";
import { ChatActionTooltip } from "#/components/features/chat/chat-action-tooltip";
import BlockDrawerLeftIcon from "#/icons/block-drawer-left.svg?react";
import { mobileTopBarIconButtonClassName } from "#/utils/mobile-top-bar-icon-button-classes";
import { WorkspaceChrome } from "#/components/features/workspace/workspace-chrome";
import { AUTOMATION_SETUP_SHOW_AGENT_EVENT } from "#/components/features/automations/setup/automation-setup-agent-request";
import { LoadingSpinner } from "#/components/shared/loading-spinner";
import { consumeAutomationSetupHandoff } from "#/api/automation-setup-handoff-store";
import { getAutomationFormSession } from "#/api/automation-form-session";
import type { AutomationSetupDraft } from "#/api/automation-setup-types";
import { useConversationId } from "#/hooks/use-conversation-id";
import { useConversationStore } from "#/stores/conversation-store";
import { useConversationOverviewDrawerOptional } from "../conversation-overview-drawer-context";
import {
  useBreakpoint,
  SIDEBAR_RAIL_COLLAPSE_MAX_WIDTH,
} from "#/hooks/use-breakpoint";
import { SidebarMobileMenuToggle } from "#/components/features/sidebar/sidebar-mobile-menu-toggle";
import { ConversationOverviewDrawer } from "../conversation-overview-drawer";
import { useActiveConversation } from "#/hooks/query/use-active-conversation";
import { I18nKey } from "#/i18n/declaration";
import { hasAutomationSetupModeTag } from "#/utils/automation-draft-tags";

const AutomationSetupPanel = lazy(() =>
  import("#/components/features/automations/setup/automation-setup-panel").then(
    (module) => ({ default: module.AutomationSetupPanel }),
  ),
);

const BLANK_AUTOMATION_SETUP_DRAFT: AutomationSetupDraft = {
  prompt: "",
  kind: "prompt",
};

type MobileAutomationView = "form" | "conversation";

const MOBILE_AUTOMATION_VIEW_OPTIONS: {
  view: MobileAutomationView;
  labelKey: I18nKey;
  Icon: typeof FileText;
}[] = [
  {
    view: "form",
    labelKey: I18nKey.AUTOMATION_SETUP$VIEW_FORM,
    Icon: FileText,
  },
  {
    view: "conversation",
    labelKey: I18nKey.AUTOMATION_SETUP$VIEW_CONVERSATION,
    Icon: MessageSquare,
  },
];

function AutomationSetupDockedComposer({
  onTarget,
}: {
  onTarget: (element: HTMLDivElement | null) => void;
}) {
  return (
    <div className="automation-setup-scroll-gutter custom-scrollbar-always pointer-events-none absolute inset-0 z-20 overflow-y-scroll px-5 [&::-webkit-scrollbar-thumb]:bg-transparent">
      <div className="automation-setup-content relative mx-auto h-full w-full min-w-0">
        <div
          ref={onTarget}
          data-testid="automation-setup-docked-composer"
          className="automation-setup-composer-dock pointer-events-auto absolute inset-x-0 bottom-5 overflow-visible"
        />
      </div>
    </div>
  );
}

export function ConversationMain({ children }: { children?: ReactNode } = {}) {
  const { t } = useTranslation("openhands");
  const { conversationId } = useConversationId();
  const { data: conversation } = useActiveConversation();
  const isMobile = useBreakpoint();
  const isSidebarRailHidden = useBreakpoint(SIDEBAR_RAIL_COLLAPSE_MAX_WIDTH);
  const {
    isRightPanelShown,
    setHasRightPanelToggled,
    setIsRightPanelShown,
  } = useConversationStore();
  const isAutomationSetupModeHandoff = useMemo(
    () => consumeAutomationSetupHandoff(conversationId),
    [conversationId],
  );
  const [automationToolbarElement, setAutomationToolbarElement] =
    useState<HTMLDivElement | null>(null);
  const [isAutomationAgentHidden, setIsAutomationAgentHidden] = useState(false);
  const [mobileAutomationView, setMobileAutomationView] =
    useState<MobileAutomationView>("form");
  const [composerDockTarget, setComposerDockTarget] =
    useState<HTMLDivElement | null>(null);
  const overviewDrawer = useConversationOverviewDrawerOptional();
  const isSecondaryDrawerOpen = Boolean(overviewDrawer?.section);
  const hasTaggedAutomationSetupMode = hasAutomationSetupModeTag(
    conversation?.tags,
  );
  const isAutomationSetupMode =
    isAutomationSetupModeHandoff || hasTaggedAutomationSetupMode;
  const automationSetupDraft = useMemo(() => {
    if (!isAutomationSetupMode) return null;
    return (
      (conversationId ? getAutomationFormSession(conversationId) : null) ??
      BLANK_AUTOMATION_SETUP_DRAFT
    );
  }, [conversationId, isAutomationSetupMode]);
  const showMobileAutomationForm =
    isMobile && isAutomationSetupMode && mobileAutomationView === "form";

  useEffect(() => {
    if (!automationSetupDraft) return;
    setHasRightPanelToggled(true);
    setIsRightPanelShown(true);
  }, [automationSetupDraft, setHasRightPanelToggled, setIsRightPanelShown]);

  useEffect(() => {
    if (!automationSetupDraft) {
      setIsAutomationAgentHidden(false);
    }
  }, [automationSetupDraft]);

  useEffect(() => {
    const showAgent = () => {
      setIsAutomationAgentHidden(false);
      setMobileAutomationView("conversation");
    };
    window.addEventListener(AUTOMATION_SETUP_SHOW_AGENT_EVENT, showAgent);
    return () =>
      window.removeEventListener(AUTOMATION_SETUP_SHOW_AGENT_EVENT, showAgent);
  }, []);

  const showDockedComposer = isAutomationSetupMode && isAutomationAgentHidden;
  const agentToggleLabel = isAutomationAgentHidden
    ? t(I18nKey.AUTOMATION_SETUP$SHOW_AGENT)
    : t(I18nKey.AUTOMATION_SETUP$HIDE_AGENT);
  const setupTitle =
    automationSetupDraft?.form?.name?.trim() ||
    conversation?.title ||
    t(I18nKey.AUTOMATION_SETUP$TITLE);

  return (
    <div
      className={cn(
        isMobile
          ? "relative min-h-0 flex-1 flex flex-col"
          : "h-full flex flex-col overflow-hidden",
      )}
    >
      {isAutomationSetupMode ? (
        <header
          data-testid="automation-setup-topbar"
          className={cn(
            "flex shrink-0 border-b border-border bg-canvas-base",
            isMobile ? "flex-col" : "h-10 min-h-10 items-center justify-between gap-2 px-3",
          )}
        >
          <div
            className={cn(
              "flex min-w-0 items-center gap-2",
              isMobile && "h-10 justify-between px-3",
              isSidebarRailHidden && "h-12",
            )}
          >
            <div className="flex min-w-0 flex-1 items-center gap-2">
              {isSidebarRailHidden ? <SidebarMobileMenuToggle /> : null}
              <h2
                data-testid="automation-setup-conversation-title"
                className="min-w-0 truncate text-sm font-medium text-content"
              >
                {setupTitle}
              </h2>
            </div>
            {isMobile ? (
              <div
                role="group"
                aria-label={`${t(I18nKey.AUTOMATION_SETUP$VIEW_FORM)} / ${t(I18nKey.AUTOMATION_SETUP$VIEW_CONVERSATION)}`}
                className="flex shrink-0 overflow-hidden rounded-lg border border-border"
              >
                {MOBILE_AUTOMATION_VIEW_OPTIONS.map(
                  ({ view, labelKey, Icon }) => {
                    const label = t(labelKey);
                    return (
                      <button
                        key={view}
                        type="button"
                        data-testid={`automation-setup-mobile-view-${view}`}
                        aria-label={label}
                        aria-pressed={mobileAutomationView === view}
                        title={label}
                        onClick={() => setMobileAutomationView(view)}
                        className={cn(
                          "inline-flex size-7 items-center justify-center",
                          mobileAutomationView === view
                            ? "bg-tertiary text-content"
                            : "text-muted",
                        )}
                      >
                        <Icon className="size-4" aria-hidden />
                      </button>
                    );
                  },
                )}
              </div>
            ) : null}
          </div>
          <div
            className={cn(
              "flex min-w-0 items-center gap-1.5",
              isMobile ? "overflow-x-auto px-3 pb-2" : "shrink-0",
              isMobile && mobileAutomationView === "conversation" && "hidden",
            )}
          >
            <div
              ref={setAutomationToolbarElement}
              data-testid="automation-setup-toolbar"
              className="flex min-w-0 shrink-0 items-center gap-1.5"
            />
            {!isMobile ? (
              <ChatActionTooltip
                tooltip={agentToggleLabel}
                ariaLabel={agentToggleLabel}
              >
                <button
                  type="button"
                  data-testid="automation-setup-agent-toggle"
                  aria-label={agentToggleLabel}
                  aria-pressed={!isAutomationAgentHidden}
                  onClick={() =>
                    setIsAutomationAgentHidden((previous) => !previous)
                  }
                  className={cn(
                    mobileTopBarIconButtonClassName,
                    "size-7 self-center",
                  )}
                >
                  <BlockDrawerLeftIcon className="size-5 shrink-0" />
                </button>
              </ChatActionTooltip>
            ) : null}
          </div>
        </header>
      ) : null}

      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Main workspace: Chat / Preview / Artifacts */}
        {!isAutomationSetupMode ? <WorkspaceChrome /> : null}

        {/* Automation setup right panel (preserved backend capability). */}
        {isAutomationSetupMode && !isMobile && isRightPanelShown ? (
          <div
            className="transition-all duration-300 ease-in-out overflow-hidden w-[40%]"
          >
            <div className="flex h-full w-full flex-col bg-surface border-l border-border">
              {automationSetupDraft ? (
                <Suspense fallback={<LoadingSpinner size="small" />}>
                  <AutomationSetupPanel
                    draft={automationSetupDraft}
                    conversationId={conversationId}
                    conversationTags={conversation?.tags}
                    toolbarPortal={automationToolbarElement}
                    showInlineHeader={false}
                    reserveComposerSpace={showDockedComposer}
                  />
                </Suspense>
              ) : null}
              {showDockedComposer ? (
                <AutomationSetupDockedComposer
                  onTarget={setComposerDockTarget}
                />
              ) : null}
            </div>
          </div>
        ) : null}
      </div>

      {!isAutomationSetupMode && !children && (
        <ConversationOverviewDrawer isMobile={isMobile} />
      )}
    </div>
  );
}
