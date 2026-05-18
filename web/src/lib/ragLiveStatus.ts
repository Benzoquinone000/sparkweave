import type { StreamEvent } from "@/lib/types";

export type RagLivePhase =
  | "starting"
  | "planning"
  | "searching"
  | "multi_search"
  | "checking"
  | "repairing"
  | "fallback"
  | "complete"
  | "error";

export type RagLiveStatus = {
  phase: RagLivePhase;
  title: string;
  detail: string;
  query: string;
  kbName: string;
  sourceCount?: number;
  subqueryCount?: number;
  contextChars?: number;
  qualityStatus: string;
  qualityScore?: number;
  repaired: boolean;
  fallback: boolean;
  transformed: boolean;
  running: boolean;
};

type MutableRagLiveStatus = Omit<RagLiveStatus, "title" | "detail"> & {
  lastMessage: string;
};

export function extractRagLiveStatus(events: StreamEvent[]): RagLiveStatus | null {
  const state: MutableRagLiveStatus = {
    phase: "starting",
    query: "",
    kbName: "",
    qualityStatus: "",
    repaired: false,
    fallback: false,
    transformed: false,
    running: false,
    lastMessage: "",
  };
  let sawRag = false;

  for (const event of events) {
    if (!isRagEvent(event)) continue;
    sawRag = true;

    const metadata = event.metadata ?? {};
    const args = asRecord(metadata.args);
    const resultMetadata = asRecord(metadata.result_metadata);
    const quality = asRecord(resultMetadata?.agentic_quality) ?? asRecord(metadata.agentic_quality);
    const contextPack = asRecord(resultMetadata?.agentic_context_pack) ?? asRecord(metadata.agentic_context_pack);
    const queryPlan = asRecord(resultMetadata?.query_plan) ?? asRecord(metadata.query_plan);
    const sources = recordArray(metadata.sources).length ? recordArray(metadata.sources) : recordArray(resultMetadata?.sources);
    const content = String(event.content ?? "").trim();
    const lowerContent = content.toLowerCase();

    state.query =
      textValue(args?.query) ||
      textValue(metadata.query) ||
      textValue(resultMetadata?.query) ||
      textValue(queryPlan?.original_query) ||
      state.query;
    state.kbName = textValue(args?.kb_name) || textValue(metadata.kb_name) || textValue(resultMetadata?.kb_name) || state.kbName;
    state.qualityStatus = textValue(quality?.status) || state.qualityStatus;
    state.qualityScore = numberValue(quality?.quality_score) ?? state.qualityScore;
    state.contextChars = numberValue(contextPack?.context_chars) ?? numberValue(metadata.context_chars) ?? state.contextChars;
    state.sourceCount =
      numberValue(resultMetadata?.source_count) ??
      numberValue(metadata.source_count) ??
      (sources.length ? sources.length : undefined) ??
      state.sourceCount;
    state.subqueryCount =
      recordArray(queryPlan?.subqueries).length ||
      recordArray(resultMetadata?.subquery_results).length ||
      recordArray(metadata.subquery_results).length ||
      state.subqueryCount;

    if (event.type === "tool_call") {
      state.running = true;
      state.phase = "starting";
      state.lastMessage = "正在进入资料库检索。";
    }

    if (event.type === "progress") {
      state.running = true;
      state.lastMessage = readableProgressMessage(content) || state.lastMessage;
      if (lowerContent.includes("retrieval policy")) state.phase = "planning";
      if (lowerContent.startsWith("query:") || lowerContent.includes("retrieving from knowledge base")) state.phase = "searching";
      if (lowerContent.includes("planned") && lowerContent.includes("retrieval")) state.phase = "multi_search";
      if (lowerContent.includes("query transformed")) state.transformed = true;
      if (lowerContent.includes("repairing weak")) {
        state.phase = "repairing";
        state.repaired = true;
      }
      if (lowerContent.includes("repaired weak")) {
        state.phase = "checking";
        state.repaired = true;
      }
      if (lowerContent.includes("evidence was weak") || lowerContent.includes("baseline retrieval")) {
        state.phase = "fallback";
        state.fallback = true;
      }
      if (lowerContent.includes("merged") || lowerContent.includes("retrieved") || lowerContent.includes("retrieve complete")) {
        state.phase = state.phase === "fallback" ? "fallback" : "checking";
      }
    }

    if (event.type === "tool_result") {
      state.running = false;
      state.phase = metadata.success === false ? "error" : "complete";
      state.repaired = resultMetadata?.agentic_repaired === true || Boolean(resultMetadata?.agentic_repair) || state.repaired;
      state.fallback = resultMetadata?.agentic_fallback === true || state.fallback;
      state.transformed = resultMetadata?.query_transform_applied === true || state.transformed;
      state.lastMessage = metadata.success === false ? "资料检索没有顺利完成。" : "资料检索已完成。";
    }

    if (event.type === "error") {
      state.running = false;
      state.phase = "error";
      state.lastMessage = content || "资料检索没有顺利完成。";
    }
  }

  if (!sawRag) return null;
  return {
    ...state,
    ...describeStatus(state),
  };
}

function isRagEvent(event: StreamEvent) {
  const metadata = event.metadata ?? {};
  const args = asRecord(metadata.args);
  const resultMetadata = asRecord(metadata.result_metadata);
  const toolName = textValue(metadata.tool_name) || textValue(metadata.tool) || textValue(metadata.name) || textValue(event.content);
  if (toolName.toLowerCase() === "rag") return true;
  if (textValue(args?.kb_name) || textValue(metadata.kb_name) || textValue(resultMetadata?.kb_name)) return true;
  if ("query_plan" in metadata || "agentic_rag" in metadata || "agentic_quality" in metadata) return true;
  if (resultMetadata && ("query_plan" in resultMetadata || "agentic_rag" in resultMetadata || "agentic_quality" in resultMetadata)) return true;
  return recordArray(metadata.sources).some(isRagSource) || recordArray(resultMetadata?.sources).some(isRagSource);
}

function describeStatus(status: MutableRagLiveStatus) {
  const sourceText = typeof status.sourceCount === "number" ? `已找到 ${status.sourceCount} 条依据` : "";
  const kbText = status.kbName ? `资料库：${status.kbName}` : "";
  const detailParts = [status.lastMessage, sourceText, kbText].filter(Boolean);

  if (status.phase === "error") {
    return {
      title: "资料检索遇到问题",
      detail: detailParts.join(" · ") || "系统没有拿到可用的资料结果。",
    };
  }
  if (status.phase === "complete") {
    return {
      title: status.sourceCount ? "已从资料库找到依据" : "资料检索已结束",
      detail: detailParts.join(" · ") || "系统会基于可用资料组织回答。",
    };
  }
  if (status.phase === "fallback") {
    return {
      title: "证据偏弱，正在改用稳妥检索",
      detail: detailParts.join(" · ") || "系统正在扩大依据，避免只依赖薄弱片段。",
    };
  }
  if (status.phase === "repairing") {
    return {
      title: "正在补强薄弱证据",
      detail: detailParts.join(" · ") || "部分检索分支证据不足，系统正在补查。",
    };
  }
  if (status.phase === "checking") {
    return {
      title: "正在检查资料依据",
      detail: detailParts.join(" · ") || "系统正在判断找到的片段是否足够回答。",
    };
  }
  if (status.phase === "multi_search") {
    return {
      title: "正在多路查资料",
      detail:
        detailParts.join(" · ") ||
        (status.subqueryCount ? `系统已拆成 ${status.subqueryCount} 个角度检索。` : "系统正在从多个角度补充依据。"),
    };
  }
  if (status.phase === "planning") {
    return {
      title: "正在判断如何查资料",
      detail: detailParts.join(" · ") || "系统会根据问题自动选择检索方式。",
    };
  }
  return {
    title: "正在查资料",
    detail: detailParts.join(" · ") || "系统正在从当前资料库取回可引用内容。",
  };
}

function readableProgressMessage(content: string) {
  const trimmed = content.trim();
  const lower = trimmed.toLowerCase();
  if (!trimmed) return "";
  if (lower.startsWith("query:")) return "正在按问题查找相关片段。";
  if (lower.includes("retrieval policy")) return "正在为这个问题选择检索方式。";
  if (lower.includes("query transformed")) return "已补充检索关键词。";
  if (lower.includes("planned") && lower.includes("retrieval")) return "系统已拆分问题并开始多路检索。";
  if (lower.includes("retrieving from knowledge base")) return "正在访问资料库。";
  if (lower.includes("repairing weak")) return "部分依据偏弱，正在补查。";
  if (lower.includes("repaired weak")) return "薄弱分支已补强，继续检查证据。";
  if (lower.includes("evidence was weak")) return "证据偏弱，正在改用更稳的检索。";
  if (lower.includes("merged")) return "已合并多路检索结果。";
  if (lower.includes("retrieved")) return "已取回资料片段。";
  if (lower.includes("retrieve complete")) return "资料检索已完成。";
  return trimmed.length > 120 ? `${trimmed.slice(0, 120).trim()}...` : trimmed;
}

function isRagSource(source: Record<string, unknown>) {
  return textValue(source.type) === "rag" || Boolean(source.subquery) || Boolean(source.chunk_id);
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function recordArray(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object" && !Array.isArray(item));
}

function textValue(value: unknown) {
  if (typeof value === "string") return value.trim();
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return "";
}

function numberValue(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value !== "string") return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}
