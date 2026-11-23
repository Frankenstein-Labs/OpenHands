import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";
import {
  getActiveOrganizationId,
  setActiveOrganizationId,
  useCortexSession,
  type Organization,
} from "#/api/cortex/cortex-api";
import { useMembers, useOrganizations } from "#/api/cortex/cortex-hooks";

export interface CortexWorkspaceValue {
  organizations: Organization[];
  activeOrganization: Organization | null;
  activeOrgId: string | null;
  setActiveOrgId: (organizationId: string) => void;
  role: string | null;
  isLoading: boolean;
}

const CortexWorkspaceContext = createContext<CortexWorkspaceValue | null>(null);

export function CortexWorkspaceProvider({ children }: PropsWithChildren) {
  const session = useCortexSession();
  const organizationsQuery = useOrganizations();
  const [activeOrgId, setActive] = useState<string | null>(() =>
    getActiveOrganizationId(),
  );
  const organizations = useMemo(
    () => organizationsQuery.data ?? [],
    [organizationsQuery.data],
  );

  useEffect(() => {
    if (organizations.length === 0) return;
    const stillExists = organizations.some((org) => org.id === activeOrgId);
    if (!stillExists) {
      const next = organizations[0].id;
      setActive(next);
      setActiveOrganizationId(next);
    }
  }, [organizations, activeOrgId]);

  const membersQuery = useMembers(activeOrgId);
  const role =
    membersQuery.data?.find((member) => member.user_id === session?.userId)
      ?.role ?? null;

  const value = useMemo<CortexWorkspaceValue>(
    () => ({
      organizations,
      activeOrganization:
        organizations.find((org) => org.id === activeOrgId) ?? null,
      activeOrgId,
      setActiveOrgId: (organizationId: string) => {
        setActive(organizationId);
        setActiveOrganizationId(organizationId);
      },
      role,
      isLoading: organizationsQuery.isLoading,
    }),
    [organizations, activeOrgId, role, organizationsQuery.isLoading],
  );

  return (
    <CortexWorkspaceContext.Provider value={value}>
      {children}
    </CortexWorkspaceContext.Provider>
  );
}

export function useCortexWorkspace(): CortexWorkspaceValue {
  const value = useContext(CortexWorkspaceContext);
  if (!value) {
    throw new Error(
      "useCortexWorkspace must be used inside CortexWorkspaceProvider",
    );
  }
  return value;
}
