import type {
  RagDiagnostic,
  RagEvaluationReport,
  RagPreflight,
  RagSearchTestResult,
} from "@/lib/types";
import type { RagTestHandoff } from "@/lib/ragHandoff";

export type WorkspaceDiagnosticsProps = {
  report?: RagDiagnostic;
  error: unknown;
  fetching: boolean;
  preflight?: RagPreflight;
  preflightError: unknown;
  preflightFetching: boolean;
  reindexing: boolean;
  onRefresh: () => void;
  onOpenRecovery: () => void;
  onOpenTest: () => void;
  onReindex: () => void;
};

export type WorkspaceQualityProps = {
  report: RagEvaluationReport | null;
  available: boolean;
  loading: boolean;
  error: unknown;
  preset: string;
  running: boolean;
  onRefresh: () => void;
  onPresetChange: (preset: string) => void;
  onRun: () => void;
};

export type WorkspaceRagTestProps = {
  query: string;
  profile: string;
  mode: string;
  agentic: string;
  topK: number;
  agenticMaxContextChars: number;
  agenticMaxSources: number;
  agenticMinRelevantCoverage: number;
  presetId: string;
  result: RagSearchTestResult | null;
  error: unknown;
  running: boolean;
  handoff?: RagTestHandoff | null;
  onQueryChange: (value: string) => void;
  onProfileChange: (value: string) => void;
  onModeChange: (value: string) => void;
  onAgenticChange: (value: string) => void;
  onTopKChange: (value: number) => void;
  onAgenticMaxContextCharsChange: (value: number) => void;
  onAgenticMaxSourcesChange: (value: number) => void;
  onAgenticMinRelevantCoverageChange: (value: number) => void;
  onPresetApply: (presetId: string) => void;
  onRun: () => void;
  onHandoffDismiss: () => void;
  onOpenDiagnostics: () => void;
};
