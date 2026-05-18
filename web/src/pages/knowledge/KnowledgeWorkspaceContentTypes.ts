import type { KnowledgeRecoveryActionId, KnowledgeRecoveryPlan } from "./recovery";
import type { KnowledgeWorkspace } from "./types";
import type { WorkspaceOverviewProps } from "./KnowledgeWorkspaceOverviewTypes";
import type {
  WorkspaceDiagnosticsProps,
  WorkspaceQualityProps,
  WorkspaceRagTestProps,
} from "./KnowledgeWorkspaceRagTypes";
import type {
  WorkspaceDocumentsProps,
  WorkspaceFoldersProps,
  WorkspaceProgressProps,
  WorkspaceSettingsProps,
  WorkspaceUploadProps,
} from "./KnowledgeWorkspaceResourceTypes";

export type { KnowledgeSummaryItem, WorkspaceOverviewProps } from "./KnowledgeWorkspaceOverviewTypes";
export type {
  WorkspaceDiagnosticsProps,
  WorkspaceQualityProps,
  WorkspaceRagTestProps,
} from "./KnowledgeWorkspaceRagTypes";
export type {
  WorkspaceDocumentsProps,
  WorkspaceFoldersProps,
  WorkspaceProgressProps,
  WorkspaceSettingsProps,
  WorkspaceUploadProps,
} from "./KnowledgeWorkspaceResourceTypes";

export type KnowledgeWorkspaceContentProps = {
  activeKb: string;
  workspace: KnowledgeWorkspace;
  overview: WorkspaceOverviewProps;
  diagnostics: WorkspaceDiagnosticsProps;
  recoveryPlan: KnowledgeRecoveryPlan;
  quality: WorkspaceQualityProps;
  ragTest: WorkspaceRagTestProps;
  documents: WorkspaceDocumentsProps;
  upload: WorkspaceUploadProps;
  settings: WorkspaceSettingsProps;
  folders: WorkspaceFoldersProps;
  progress: WorkspaceProgressProps;
  onNavigate: (workspace: KnowledgeWorkspace) => void;
  onRecoveryAction: (action: KnowledgeRecoveryActionId) => void;
};

export type KnowledgeWorkspaceRoutePanelsProps = KnowledgeWorkspaceContentProps;
