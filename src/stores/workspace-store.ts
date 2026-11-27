import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { WorkspaceTab, PreviewServerInfo, ArtifactFile } from "#/types/workspace";

interface WorkspaceStore {
  // Active tab
  activeTab: WorkspaceTab;
  setActiveTab: (tab: WorkspaceTab) => void;

  // Preview server info
  previewServer: PreviewServerInfo;
  setPreviewServer: (server: Partial<PreviewServerInfo> | ((prev: PreviewServerInfo) => Partial<PreviewServerInfo>)) => void;
  resetPreviewServer: () => void;

  // Artifacts (file tree)
  artifacts: ArtifactFile[];
  setArtifacts: (artifacts: ArtifactFile[]) => void;
  isLoadingArtifacts: boolean;
  setIsLoadingArtifacts: (loading: boolean) => void;
  artifactsError?: string;
  setArtifactsError: (error?: string) => void;

  // Panel visibility (for desktop)
  isRightPanelShown: boolean;
  setIsRightPanelShown: (shown: boolean) => void;
  toggleRightPanel: () => void;
}

const DEFAULT_PREVIEW_SERVER: PreviewServerInfo = {
  url: null,
  port: null,
  status: "none",
};

export const useWorkspaceStore = create<WorkspaceStore>()(
  persist(
    (set, get) => ({
      // Active tab
      activeTab: "chat",
      setActiveTab: (tab) => set({ activeTab: tab }),

      // Preview server
      previewServer: DEFAULT_PREVIEW_SERVER,
      setPreviewServer: (server) =>
        set((state) => ({
          previewServer: {
            ...state.previewServer,
            ...(typeof server === "function" ? server(state.previewServer) : server),
          },
        })),
      resetPreviewServer: () => set({ previewServer: DEFAULT_PREVIEW_SERVER }),

      // Artifacts
      artifacts: [],
      setArtifacts: (artifacts) => set({ artifacts }),
      isLoadingArtifacts: false,
      setIsLoadingArtifacts: (isLoadingArtifacts) => set({ isLoadingArtifacts }),
      artifactsError: undefined,
      setArtifactsError: (artifactsError) => set({ artifactsError }),

      // Panel visibility
      isRightPanelShown: true,
      setIsRightPanelShown: (isRightPanelShown) => set({ isRightPanelShown }),
      toggleRightPanel: () =>
        set((state) => ({ isRightPanelShown: !state.isRightPanelShown })),
    }),
    {
      name: "workspace-store",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        activeTab: state.activeTab,
        isRightPanelShown: state.isRightPanelShown,
      }),
    }
  )
);