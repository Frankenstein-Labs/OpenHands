/**
 * Workspace types for the new three-pane workspace (Chat, Preview, Artifacts)
 */

export type WorkspaceTab = "chat" | "preview" | "artifacts";

export interface WorkspaceTabConfig {
  id: WorkspaceTab;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  disabled?: boolean;
}

export interface PreviewServerInfo {
  url: string | null;
  port: number | null;
  status: "starting" | "ready" | "building" | "error" | "stopped" | "none";
  error?: string;
  framework?: string;
  devCommand?: string;
}

export interface ArtifactFile {
  path: string;
  name: string;
  type: "file" | "directory";
  size?: number;
  mimeType?: string;
  children?: ArtifactFile[];
}

export interface WorkspaceState {
  activeTab: WorkspaceTab;
  previewServer: PreviewServerInfo;
  artifacts: ArtifactFile[];
  isLoadingArtifacts: boolean;
  artifactsError?: string;
}