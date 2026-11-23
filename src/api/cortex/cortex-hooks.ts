import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  cortexFetch,
  getSessionSnapshot,
  type DocumentSummary,
  type GenerateResult,
  type GitHubRepository,
  type Installation,
  type Invitation,
  type Membership,
  type Model,
  type Organization,
  type Profile,
  type Provider,
  type SearchHit,
  type UsageLimits,
  type UsageSummary,
} from "./cortex-api";

const hasSession = () => getSessionSnapshot() !== null;

export const cortexKeys = {
  profile: ["cortex", "profile"] as const,
  organizations: ["cortex", "organizations"] as const,
  members: (orgId: string | null) => ["cortex", "members", orgId] as const,
  invitations: (orgId: string | null) =>
    ["cortex", "invitations", orgId] as const,
  providers: ["cortex", "providers"] as const,
  models: ["cortex", "models"] as const,
  usage: (orgId: string | null) => ["cortex", "usage", orgId] as const,
  limits: (orgId: string | null) => ["cortex", "limits", orgId] as const,
  documents: (orgId: string | null) => ["cortex", "documents", orgId] as const,
  search: (orgId: string | null, query: string) =>
    ["cortex", "documents", orgId, "search", query] as const,
  installations: (orgId: string | null) =>
    ["cortex", "installations", orgId] as const,
  repositories: (orgId: string | null) =>
    ["cortex", "repositories", orgId] as const,
};

export function useCortexProfile() {
  return useQuery({
    queryKey: cortexKeys.profile,
    queryFn: () => cortexFetch<Profile>("/api/v1/profile"),
    enabled: hasSession(),
  });
}

export function useOrganizations() {
  return useQuery({
    queryKey: cortexKeys.organizations,
    queryFn: () => cortexFetch<Organization[]>("/api/v1/organizations"),
    enabled: hasSession(),
  });
}

export function useMembers(orgId: string | null) {
  return useQuery({
    queryKey: cortexKeys.members(orgId),
    queryFn: () =>
      cortexFetch<Membership[]>(`/api/v1/organizations/${orgId}/members`, {
        orgId,
      }),
    enabled: Boolean(orgId),
  });
}

export function useInvitations(orgId: string | null) {
  return useQuery({
    queryKey: cortexKeys.invitations(orgId),
    queryFn: () =>
      cortexFetch<Invitation[]>(`/api/v1/organizations/${orgId}/invitations`),
    enabled: Boolean(orgId),
  });
}

export function useProviders() {
  return useQuery({
    queryKey: cortexKeys.providers,
    queryFn: () => cortexFetch<Provider[]>("/api/v1/providers"),
    enabled: hasSession(),
  });
}

export function useModels() {
  return useQuery({
    queryKey: cortexKeys.models,
    queryFn: () => cortexFetch<Model[]>("/api/v1/models"),
    enabled: hasSession(),
  });
}

export function useUsage(orgId: string | null) {
  return useQuery({
    queryKey: cortexKeys.usage(orgId),
    queryFn: () => cortexFetch<UsageSummary>("/api/v1/usage", { orgId }),
    enabled: Boolean(orgId),
  });
}

export function useLimits(orgId: string | null) {
  return useQuery({
    queryKey: cortexKeys.limits(orgId),
    queryFn: () => cortexFetch<UsageLimits>("/api/v1/usage/limits", { orgId }),
    enabled: Boolean(orgId),
  });
}

export function useDocuments(orgId: string | null) {
  return useQuery({
    queryKey: cortexKeys.documents(orgId),
    queryFn: () =>
      cortexFetch<DocumentSummary[]>("/api/v1/documents", { orgId }),
    enabled: Boolean(orgId),
  });
}

export function useSearchDocuments(orgId: string | null, query: string) {
  return useQuery({
    queryKey: cortexKeys.search(orgId, query),
    queryFn: () =>
      cortexFetch<{ query: string; hits: SearchHit[] }>(
        "/api/v1/documents/search",
        { orgId, query: { q: query, limit: 20 } },
      ),
    enabled: Boolean(orgId) && query.trim().length > 1,
  });
}

export function useInstallations(orgId: string | null) {
  return useQuery({
    queryKey: cortexKeys.installations(orgId),
    queryFn: () =>
      cortexFetch<Installation[]>("/api/v1/integrations/github/installations", {
        orgId,
      }),
    enabled: Boolean(orgId),
  });
}

export function useRepositories(orgId: string | null, enabled = false) {
  return useQuery({
    queryKey: cortexKeys.repositories(orgId),
    queryFn: () =>
      cortexFetch<GitHubRepository[]>(
        "/api/v1/integrations/github/repositories",
        { orgId },
      ),
    enabled: Boolean(orgId) && enabled,
  });
}

export function useCreateOrganization() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { slug: string; name: string }) =>
      cortexFetch<Organization>("/api/v1/organizations", {
        method: "POST",
        body,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: cortexKeys.organizations,
      });
    },
  });
}

export function useInviteMember(orgId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; role: string }) =>
      cortexFetch<Invitation>(`/api/v1/organizations/${orgId}/invitations`, {
        method: "POST",
        body,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: cortexKeys.invitations(orgId),
      });
    },
  });
}

export function useUpdateMemberRole(orgId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { userId: string; role: string }) =>
      cortexFetch<Membership>(
        `/api/v1/organizations/${orgId}/members/${body.userId}`,
        { method: "PATCH", body: { role: body.role } },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: cortexKeys.members(orgId),
      });
    },
  });
}

export function useRemoveMember(orgId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) =>
      cortexFetch<void>(`/api/v1/organizations/${orgId}/members/${userId}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: cortexKeys.members(orgId),
      });
    },
  });
}

export function useGenerate(orgId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      model_id: string;
      messages: { role: "user"; content: string }[];
      max_tokens?: number;
    }) =>
      cortexFetch<GenerateResult>("/api/v1/ai/generate", {
        method: "POST",
        orgId,
        body,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: cortexKeys.usage(orgId) });
    },
  });
}

export function useCreateDocument(orgId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { title: string; content: string }) =>
      cortexFetch<{ document: DocumentSummary; chunk_count: number }>(
        "/api/v1/documents",
        { method: "POST", orgId, body },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: cortexKeys.documents(orgId),
      });
    },
  });
}

export function useDeleteDocument(orgId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (documentId: string) =>
      cortexFetch<void>(`/api/v1/documents/${documentId}`, {
        method: "DELETE",
        orgId,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: cortexKeys.documents(orgId),
      });
    },
  });
}

export function useLinkInstallation(orgId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (installationId: number) =>
      cortexFetch<Installation>("/api/v1/integrations/github/installations", {
        method: "POST",
        orgId,
        body: { installation_id: installationId },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: cortexKeys.installations(orgId),
      });
    },
  });
}

export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (
      body: Partial<Pick<Profile, "full_name" | "locale" | "timezone">>,
    ) => cortexFetch<Profile>("/api/v1/profile", { method: "PATCH", body }),
    onSuccess: (profile) => {
      queryClient.setQueryData(cortexKeys.profile, profile);
    },
  });
}
