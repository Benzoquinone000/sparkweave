export function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

export function readNumber(record: unknown, key: string) {
  if (!isRecord(record)) return undefined;
  const value = record[key];
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

export function readString(record: unknown, key: string) {
  if (!isRecord(record)) return "";
  const value = record[key];
  return typeof value === "string" ? value : "";
}

export function toRecordArray(value: unknown) {
  return Array.isArray(value) ? value.filter(isRecord) : [];
}

export function toStringArray(value: unknown) {
  if (Array.isArray(value)) return value.map((item) => String(item)).filter(Boolean);
  if (typeof value === "string" && value.trim()) return value.split(",").map((item) => item.trim()).filter(Boolean);
  return [];
}

export function formatOptionalCount(value: number | undefined) {
  return typeof value === "number" ? String(value) : "-";
}

export function formatAgenticMode(value: unknown) {
  const key = String(value || "off").toLowerCase();
  const labels: Record<string, string> = {
    auto: "自动多路",
    force: "总是拆分",
    forced: "总是拆分",
    on: "总是拆分",
    off: "轻量查找",
    false: "轻量查找",
  };
  return labels[key] || String(value || "轻量查找");
}

export function formatAgenticQualityStatus(value: string) {
  const labels: Record<string, string> = {
    sufficient: "来源充足",
    weak: "来源偏弱",
    checked: "已检查",
  };
  return labels[value] || value || "已检查";
}

export function formatAgenticRepairStrategy(value: string) {
  const labels: Record<string, string> = {
    single_search_fallback: "改用原问题",
    subquery_repair: "补强拆分问题",
  };
  return labels[value] || value || "未触发";
}

export function formatAgenticReason(value: string) {
  const labels: Record<string, string> = {
    agentic_rag_disabled: "多路来源未开启",
    all_subqueries_failed: "拆分问题均未找到来源",
    empty_query: "问题为空",
    forced_by_caller: "已选择总是拆分",
    low_context_chars: "回答材料过少",
    low_relevance_coverage: "相关来源不足",
    low_score: "相似度偏低",
    low_source_count: "来源数量不足",
    low_subquery_coverage: "拆分覆盖不足",
    multiple_questions: "包含多个问题",
    no_sources: "没有找到来源",
    simple_query_fast_path: "简单问题使用快速查找",
  };
  if (value.startsWith("multi_intent_terms")) return "识别到多意图问题";
  if (value.includes("fallback_rule_split")) return "问题拆分失败，已使用规则拆分";
  return labels[value] || value.replaceAll("_", " ");
}

export function formatAgenticRecommendation(value: string) {
  const labels: Record<string, string> = {
    "Agentic evidence is sufficient for grounded synthesis.": "当前来源可以支撑回答。",
    "Evidence is weak; use a fallback retrieval path before answering.": "来源偏弱，回答前建议先改用轻量查找复测。",
    "No evidence was found. Check indexing coverage or widen candidate_top_k.": "没有找到来源，请检查资料覆盖或扩大候选范围。",
    "Relevant coverage is low; repair weak branches or retry with broader retrieval.": "相关来源不足，请补强薄弱部分或扩大查找范围。",
    "Some branches returned weakly related chunks; retry the original query with broader retrieval.": "部分查找视角的来源相关性偏弱，系统已尝试用更宽的范围补强。",
    "Subquery coverage is low; repair weak branches or retry with broader retrieval.": "拆分覆盖不足，请补强薄弱部分或扩大查找范围。",
    "Use the merged evidence as grounded context, then answer with citations.": "可使用合并来源作为回答材料，并附带引用。",
  };
  return labels[value] || value;
}

export function buildAgenticNextAction({
  reasons,
  fallback,
  sourceCount,
  truncated,
}: {
  reasons: string[];
  fallback: boolean;
  sourceCount: number | undefined;
  truncated: boolean;
}): { tone: "success" | "warning" | "neutral"; text: string } | null {
  if ((sourceCount ?? 0) <= 0 || reasons.includes("no_sources")) {
    return { tone: "warning", text: "下一步：先检查资料是否已整理完成，再扩大来源数量或候选范围。" };
  }
  if (reasons.includes("low_relevance_coverage")) {
    return { tone: "warning", text: "下一步：使用“复杂问题”方案复测，或检查对应资料片段是否包含问题关键词。" };
  }
  if (reasons.includes("low_subquery_coverage")) {
    return { tone: "warning", text: "下一步：提高来源上限或回答材料上限，确认每个拆分问题都能找到资料。" };
  }
  if (reasons.includes("low_context_chars") || truncated) {
    return { tone: "warning", text: "下一步：适当提高回答材料上限，避免关键来源在整理阶段被截断。" };
  }
  if (fallback) {
    return { tone: "warning", text: "下一步：查看回退原因；若原问题查找效果更好，可以保留快速查找作为默认路径。" };
  }
  return { tone: "success", text: "当前来源稳定，可以进入聊天问答验证最终回答质量。" };
}

export function agenticNextActionClass(tone: "success" | "warning" | "neutral") {
  if (tone === "success") return "border-emerald-200 bg-emerald-50 text-emerald-800";
  if (tone === "warning") return "border-amber-200 bg-amber-50 text-amber-800";
  return "border-line bg-white text-slate-600";
}

export function formatPercentValue(value: number | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  return `${Math.round((value > 1 ? value : value * 100))}%`;
}
