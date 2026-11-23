/* eslint-disable i18next/no-literal-string -- Cortex admin surface is English-only until translations land; Canvas UI stays localized. */
import { NavLink, Outlet } from "react-router";
import {
  getCortexConfig,
  signOut,
  useCortexSession,
} from "#/api/cortex/cortex-api";
import { CortexAuthScreen } from "#/components/features/cortex/cortex-auth-screen";
import {
  CortexWorkspaceProvider,
  useCortexWorkspace,
} from "#/components/features/cortex/cortex-workspace";
import { CortexButton } from "#/components/features/cortex/cortex-ui";

const NAV_ITEMS = [
  { to: "/cortex", end: true, label: "Overview" },
  { to: "/cortex/organization", label: "Organization" },
  { to: "/cortex/models", label: "Models" },
  { to: "/cortex/usage", label: "Usage" },
  { to: "/cortex/documents", label: "Documents" },
  { to: "/cortex/integrations", label: "Integrations" },
  { to: "/cortex/profile", label: "Profile" },
];

function CortexFrame() {
  const session = useCortexSession();
  const { organizations, activeOrgId, setActiveOrgId } = useCortexWorkspace();

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="border-b border-border px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-base font-semibold text-content">{"Title"}</h1>
            <p className="text-xs text-tertiary-light">
              {"AI workspace, models, usage and integrations"}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {organizations.length > 0 && (
              <label className="flex items-center gap-2 text-xs text-tertiary-light">
                {"Organization"}
                <select
                  className="rounded-lg border border-border bg-surface-raised px-2 py-1 text-sm text-content"
                  value={activeOrgId ?? ""}
                  onChange={(event) => setActiveOrgId(event.target.value)}
                >
                  {organizations.map((organization) => (
                    <option key={organization.id} value={organization.id}>
                      {organization.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <span className="text-xs text-tertiary-light">
              {session?.email}
            </span>
            <CortexButton variant="secondary" onClick={() => void signOut()}>
              {"Sign out"}
            </CortexButton>
          </div>
        </div>
        <nav className="mt-3 flex flex-wrap gap-1">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `rounded-lg px-3 py-1.5 text-sm ${
                  isActive
                    ? "bg-surface-raised font-medium text-content"
                    : "text-tertiary-light hover:text-content"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        <Outlet />
      </div>
    </div>
  );
}

export default function CortexRoute() {
  const config = getCortexConfig();
  const session = useCortexSession();

  if (!config) {
    return (
      <div className="p-6 text-sm text-tertiary-light">
        Cortex is not configured. Set VITE_CORTEX_API_URL, VITE_SUPABASE_URL and
        VITE_SUPABASE_ANON_KEY.
      </div>
    );
  }
  if (!session) return <CortexAuthScreen />;
  return (
    <CortexWorkspaceProvider>
      <CortexFrame />
    </CortexWorkspaceProvider>
  );
}
