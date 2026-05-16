export const KNOWLEDGE_WORKSPACES = [
  "overview",
  "documents",
  "test",
  "diagnostics",
  "recovery",
  "quality",
  "upload",
  "settings",
  "progress",
  "folders",
] as const;

export type KnowledgeWorkspaceId = (typeof KNOWLEDGE_WORKSPACES)[number];

export type RagTestHandoff = {
  source: "chat" | "link";
  status?: string;
};

export type KnowledgeHandoffIntent = {
  cacheKey: string;
  workspace?: KnowledgeWorkspaceId;
  kbName: string;
  query: string;
  presetId: string;
  profile: string;
  mode: string;
  agentic: string;
  topK?: number;
  agenticMaxContextChars?: number;
  agenticMaxSources?: number;
  agenticMinRelevantCoverage?: number;
  handoff?: RagTestHandoff;
};

export type KnowledgePreflightLinkInput = {
  query?: string;
  kbName?: string;
  retrievalProfile?: string;
  retrievalMode?: string;
  agentic?: boolean;
};

export type EvidenceRecoveryStatus = {
  tone: "success" | "warning" | "neutral" | string;
  badge: string;
};

export type RagChatHandoffInput = {
  activeKb: string;
  query: string;
  profile: string;
  mode: string;
  agentic: string;
  topK: number;
  agenticMaxContextChars: number;
  agenticMaxSources: number;
  agenticMinRelevantCoverage: number;
};

export function buildKnowledgePreflightHref(input: KnowledgePreflightLinkInput, status: EvidenceRecoveryStatus) {
  if (status.tone === "success") return "";
  if (!input.query && !input.kbName) return "";
  const params = new URLSearchParams({
    from: "chat_evidence",
    evidence_status: status.badge,
    workspace: "test",
    preset: "deep",
    retrieval_profile: input.retrievalProfile || "broad",
    retrieval_mode: input.retrievalMode || "hybrid",
    agentic_rag: input.agentic ? "force" : "auto",
  });
  if (input.query) params.set("query", input.query);
  if (input.kbName) params.set("kb", input.kbName);
  return `/knowledge?${params.toString()}`;
}

export function buildRagChatHandoffHref({
  activeKb,
  query,
  profile,
  mode,
  agentic,
  topK,
  agenticMaxContextChars,
  agenticMaxSources,
  agenticMinRelevantCoverage,
}: RagChatHandoffInput) {
  const params = new URLSearchParams({
    new: "1",
    capability: "chat",
    prompt: query.trim(),
    kb: activeKb,
    prefetch_rag: "1",
    retrieval_profile: profile || "auto",
    retrieval_mode: mode || "hybrid",
    agentic_rag: agentic || "auto",
    top_k: String(topK),
    candidate_top_k: String(Math.max(topK * 3, topK)),
    agentic_max_context_chars: String(agenticMaxContextChars),
    agentic_max_sources: String(agenticMaxSources),
    agentic_min_relevant_coverage_ratio: String(agenticMinRelevantCoverage),
    max_context_chars: String(agenticMaxContextChars),
  });
  return `/chat?${params.toString()}`;
}

export function parseKnowledgeHandoffSearch(input: string | URLSearchParams): KnowledgeHandoffIntent | null {
  const params = typeof input === "string" ? new URLSearchParams(input.startsWith("?") ? input.slice(1) : input) : input;
  const cacheKey = params.toString();
  if (!cacheKey) return null;

  const requestedWorkspace = cleanSearchParam(params.get("workspace"));
  const kbName = cleanSearchParam(params.get("kb")) || cleanSearchParam(params.get("knowledge_base"));
  const query = cleanSearchParam(params.get("query")) || cleanSearchParam(params.get("prompt"));
  const presetId = cleanSearchParam(params.get("preset"));
  const from = cleanSearchParam(params.get("from"));
  const evidenceStatus = cleanSearchParam(params.get("evidence_status"));
  const hasHandoff =
    Boolean(requestedWorkspace || kbName || query || presetId || from || evidenceStatus) ||
    params.has("retrieval_profile") ||
    params.has("retrieval_mode") ||
    params.has("agentic_rag");

  if (!hasHandoff) return null;

  const topK = readIntegerSearchParam(params, "top_k", 1, 30);
  const agenticMaxContextChars = readIntegerSearchParam(params, "agentic_max_context_chars", 500, 50000);
  const agenticMaxSources = readIntegerSearchParam(params, "agentic_max_sources", 1, 40);
  const agenticMinRelevantCoverage = readRatioSearchParam(params, "agentic_min_relevant_coverage_ratio");
  const handoff =
    from || query
      ? {
          source: from === "chat_evidence" ? ("chat" as const) : ("link" as const),
          ...(evidenceStatus ? { status: evidenceStatus } : {}),
        }
      : undefined;

  return {
    cacheKey,
    ...(isKnowledgeWorkspaceId(requestedWorkspace) ? { workspace: requestedWorkspace } : {}),
    kbName,
    query,
    presetId,
    profile: cleanSearchParam(params.get("retrieval_profile")),
    mode: cleanSearchParam(params.get("retrieval_mode")),
    agentic: cleanSearchParam(params.get("agentic_rag")),
    ...(typeof topK === "number" ? { topK } : {}),
    ...(typeof agenticMaxContextChars === "number" ? { agenticMaxContextChars } : {}),
    ...(typeof agenticMaxSources === "number" ? { agenticMaxSources } : {}),
    ...(typeof agenticMinRelevantCoverage === "number" ? { agenticMinRelevantCoverage } : {}),
    ...(handoff ? { handoff } : {}),
  };
}

export function isKnowledgeWorkspaceId(value: string): value is KnowledgeWorkspaceId {
  return KNOWLEDGE_WORKSPACES.includes(value as KnowledgeWorkspaceId);
}

function cleanSearchParam(value: string | null) {
  return typeof value === "string" ? value.trim() : "";
}

function readIntegerSearchParam(params: URLSearchParams, key: string, min: number, max: number) {
  const raw = cleanSearchParam(params.get(key));
  if (!raw) return undefined;
  const parsed = Number(raw);
  if (!Number.isFinite(parsed)) return undefined;
  return Math.min(max, Math.max(min, Math.round(parsed)));
}

function readRatioSearchParam(params: URLSearchParams, key: string) {
  const raw = cleanSearchParam(params.get(key));
  if (!raw) return undefined;
  const parsed = Number(raw);
  if (!Number.isFinite(parsed)) return undefined;
  const normalized = parsed > 1 ? parsed / 100 : parsed;
  return Math.min(1, Math.max(0, normalized));
}
