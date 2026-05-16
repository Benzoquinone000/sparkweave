import type { KnowledgeWsStatus } from "./progressFormat";

export type KnowledgeSummaryItem = {
  key: string;
  label: string;
  value: string;
};

export type WorkspaceOverviewProps = {
  activeStatus: string;
  activeFileCount?: number;
  activeDocumentCount?: number;
  activeSearchLabel: string;
  activePath: string;
  progressMessage: string;
  progressPercent: number;
  progressStage: string;
  wsStatus: KnowledgeWsStatus;
  taskActive: boolean;
  documentCount: number | string | null | undefined;
  vectorCount: number | string | null | undefined;
  diagnosticStatus: string;
  recoveryBadge: string;
  recoveryNeedsAttention: boolean;
  evaluationAvailable: boolean;
  testSourceCount?: number | string | null;
  folderCount: number;
  summaryItems: KnowledgeSummaryItem[];
  reindexing: boolean;
  diagnosing: boolean;
  defaultActive: boolean;
  settingDefault: boolean;
  removing: boolean;
  onReindex: () => void;
  onDiagnose: () => void;
  onSetDefault: () => void;
  onDelete: () => void;
};
