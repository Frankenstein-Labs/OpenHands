import { useTranslation } from "react-i18next";
import { Settings } from "lucide-react";
import AutomationsIcon from "#/icons/automations.svg?react";
import { BackendSelector } from "#/components/features/backends/backend-selector";
import { SidebarNavLink } from "#/components/features/sidebar/sidebar-nav-link";
import {
  automationListPath,
  getInterfaceCopy,
  hasAutomationInterface,
} from "#/manifests/automation-interface";
import { CUSTOMIZE_PATH } from "#/hooks/use-pinned-home-route";
import { I18nKey } from "#/i18n/declaration";

/** Settings-only home for the workspace selector and the former task shortcuts. */
export function SettingsWorkspaceTools({
  onNavigate,
}: {
  onNavigate?: () => void;
}) {
  const { t } = useTranslation("openhands");

  return (
    <section
      data-testid="settings-workspace-tools"
      className="flex flex-col gap-1 border-t border-border px-2 pt-3"
    >
      <BackendSelector onSelectOption={onNavigate} />
      <SidebarNavLink
        to={CUSTOMIZE_PATH}
        label={t(I18nKey.NAV$CUSTOMIZE)}
        testId="settings-tools-customize-link"
        onClick={onNavigate}
        icon={<Settings className="size-4" aria-hidden />}
      />
      {hasAutomationInterface() ? (
        <SidebarNavLink
          to={automationListPath()}
          label={getInterfaceCopy().sidebarLabel}
          testId="settings-tools-automations-link"
          onClick={onNavigate}
          icon={<AutomationsIcon className="size-4" aria-hidden />}
        />
      ) : null}
    </section>
  );
}
