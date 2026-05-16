import type {
  CapabilityId,
  ChatMessage,
  LearningEffectNextAction,
  LearnerProfileSnapshot,
  StreamEvent,
} from "@/lib/types";

const CAPABILITY_IDS = new Set<CapabilityId>([
  "chat",
  "deep_solve",
  "deep_question",
  "deep_research",
  "external_video_search",
  "visualize",
  "math_animator",
]);

export function isCapabilityId(value: unknown): value is CapabilityId {
  return typeof value === "string" && CAPABILITY_IDS.has(value as CapabilityId);
}

export function getInitialCapabilityFromLocation(): CapabilityId {
  if (typeof window === "undefined") return "chat";
  const value = new URLSearchParams(window.location.search).get("capability");
  return isCapabilityId(value) ? value : "chat";
}

export function formatStageLabel(event: StreamEvent | null, assistantStatus?: ChatMessage["status"]) {
  if (assistantStatus === "done") return "已完成";
  if (assistantStatus === "error") return "异常";
  if (!event) return "等待任务";
  const stage = String(event.stage ?? "").toLowerCase();
  if (event.type === "result" || event.type === "done") return "已完成";
  if (event.type === "error") return "异常";
  if (event.type === "stage_start" && stage === "thinking") return "正在思考";
  if (event.type === "progress" && stage === "thinking") return "正在思考";
  if (event.type === "stage_end" && stage === "thinking") return "整理答案";
  if (event.type === "stage_start" && stage === "responding") return "正在回答";
  if (event.type === "stage_end" && stage === "responding") return "已完成";
  if (stage === "thinking") return "正在思考";
  if (stage === "responding") return "正在回答";
  return event.stage || event.type;
}

export function cleanText(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

export function profileTopic(profile?: LearnerProfileSnapshot) {
  const focus = cleanText(profile?.overview.current_focus);
  if (focus) return focus;
  const weakPoint = cleanText(profile?.learning_state.weak_points?.[0]?.label);
  if (weakPoint) return weakPoint;
  return "当前学习任务";
}

export function guideHref(profile?: LearnerProfileSnapshot) {
  const action = profile?.next_action;
  if (cleanText(action?.href)) return cleanText(action?.href);
  const prompt = cleanText(action?.suggested_prompt) || cleanText(action?.title) || profileTopic(profile);
  const params = new URLSearchParams({ new: "1", prompt });
  const title = cleanText(action?.title);
  if (title) params.set("action_title", title);
  const actionKind = cleanText(action?.kind);
  const sourceType = cleanText(action?.source_type);
  const sourceLabel = cleanText(action?.source_label);
  if (actionKind) params.set("action_kind", actionKind);
  if (sourceType) params.set("source_type", sourceType);
  if (sourceLabel) params.set("source_label", sourceLabel);
  if (action?.estimated_minutes) params.set("estimated_minutes", String(action.estimated_minutes));
  if (action?.confidence) params.set("confidence", String(action.confidence));
  return `/guide?${params.toString()}`;
}

export function promptFromLearningEffectAction(action?: LearningEffectNextAction | null) {
  if (!action) return "";
  const directPrompt = cleanText(action.prompt);
  if (directPrompt) return directPrompt;
  const href = cleanText(action.href);
  if (href) {
    try {
      const url = new URL(href, "http://sparkweave.local");
      const prompt = cleanText(url.searchParams.get("prompt"));
      if (prompt) return prompt;
    } catch {
      // Fall back to the action text below.
    }
  }
  const concepts = (action.target_concepts ?? []).filter(Boolean).join("、");
  const title = cleanText(action.title);
  const reason = cleanText(action.reason);
  if (title && concepts) return `${title}。请重点围绕：${concepts}。${reason}`;
  if (title && reason) return `${title}。${reason}`;
  return title || reason;
}

export function capabilityFromLearningEffectAction(action?: LearningEffectNextAction | null): CapabilityId | undefined {
  return isCapabilityId(action?.capability) ? action.capability : undefined;
}

export function configFromLearningEffectAction(action?: LearningEffectNextAction | null): Record<string, unknown> | undefined {
  return action?.config && typeof action.config === "object" ? action.config : undefined;
}

export function knowledgeBasesFromLearningEffectAction(action?: LearningEffectNextAction | null) {
  const direct = uniqueStrings(action?.knowledge_bases ?? []);
  if (direct.length) return direct;
  const href = cleanText(action?.href);
  if (!href) return [];
  try {
    const url = new URL(href, "http://sparkweave.local");
    return knowledgeBasesFromSearchParams(url.searchParams);
  } catch {
    return [];
  }
}

export function knowledgeBasesFromSearchParams(params: URLSearchParams) {
  const values = [
    ...params.getAll("kb"),
    ...params.getAll("knowledge_base"),
    ...params.getAll("knowledge_bases"),
  ].flatMap((value) => value.split(","));
  return uniqueStrings(values);
}

export function ragConfigFromSearchParams(params: URLSearchParams): Record<string, unknown> | undefined {
  const config: Record<string, unknown> = {};
  [
    "retrieval_profile",
    "retrieval_mode",
    "agentic_rag",
    "query_transform",
    "reranker",
  ].forEach((key) => {
    const value = cleanText(params.get(key));
    if (value) config[key] = value;
  });

  [
    ["top_k", 1, 30],
    ["candidate_top_k", 1, 100],
    ["max_context_chars", 500, 30000],
    ["agentic_max_context_chars", 500, 30000],
    ["agentic_max_sources", 1, 50],
    ["agentic_min_sources", 0, 20],
    ["agentic_max_subqueries", 1, 8],
    ["agentic_min_relevant_coverage_ratio", 0, 1],
    ["agentic_min_coverage_ratio", 0, 1],
  ].forEach(([key, min, max]) => {
    const parsed = Number(params.get(String(key)));
    if (!Number.isFinite(parsed)) return;
    config[String(key)] = Math.max(Number(min), Math.min(Number(max), parsed));
  });

  const prefetchRag = cleanText(params.get("prefetch_rag"));
  if (prefetchRag) config.prefetch_rag = prefetchRag;

  return Object.keys(config).length ? config : undefined;
}

export function isTruthyConfigFlag(value: unknown) {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value !== 0;
  if (typeof value === "string") return !["", "0", "false", "off", "no"].includes(value.trim().toLowerCase());
  return Boolean(value);
}

export function formatRagModeLabel(value: unknown) {
  const key = String(value || "").trim().toLowerCase();
  const labels: Record<string, string> = {
    auto: "自动分解",
    force: "强制多路",
    forced: "强制多路",
    off: "快速检索",
    false: "快速检索",
  };
  return labels[key] || "知识库检索";
}

export function formatRetrievalProfileLabel(value: unknown) {
  const key = String(value || "").trim().toLowerCase();
  const labels: Record<string, string> = {
    auto: "自动画像",
    concept: "概念解释",
    exact: "精确事实",
    broad: "综合问题",
    formula: "公式推导",
  };
  return labels[key] || "";
}

export function formatRuntimeStatus(status: "idle" | "connecting" | "streaming" | "error") {
  return {
    idle: "就绪",
    connecting: "连接中",
    streaming: "生成中",
    error: "异常",
  }[status];
}

function uniqueStrings(values: unknown[]) {
  const seen = new Set<string>();
  const result: string[] = [];
  values.forEach((value) => {
    const text = cleanText(value);
    if (!text || seen.has(text)) return;
    seen.add(text);
    result.push(text);
  });
  return result;
}
