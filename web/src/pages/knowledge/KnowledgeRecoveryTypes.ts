export type KnowledgeRecoveryActionId =
  | "upload"
  | "reindex"
  | "diagnostics"
  | "progress"
  | "documents"
  | "test"
  | "folders";

export type KnowledgeRecoveryTone = "brand" | "success" | "warning" | "danger" | "neutral";

export type KnowledgeRecoveryCheck = {
  label: string;
  detail: string;
  tone: KnowledgeRecoveryTone;
};

export type KnowledgeRecoveryAction = {
  id: KnowledgeRecoveryActionId;
  label: string;
  detail: string;
};

export type KnowledgeRecoveryPlan = {
  state: "empty" | "running" | "failed" | "connection" | "needs_index" | "ready";
  title: string;
  summary: string;
  badge: string;
  tone: KnowledgeRecoveryTone;
  needsAttention: boolean;
  primaryAction: KnowledgeRecoveryAction;
  secondaryActions: KnowledgeRecoveryAction[];
  checks: KnowledgeRecoveryCheck[];
};

export type KnowledgeRecoveryInput = {
  activeKb: string;
  documentCount?: number | string | null;
  vectorCount?: number | string | null;
  progressStage?: string;
  progressMessage?: string;
  taskActive?: boolean;
  readinessState?: string;
  readinessLabel?: string;
  readinessSummary?: string;
  readinessAction?: string;
  diagnosticStatus?: string;
  latestError?: string;
};
