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
    auto: "自动编排",
    force: "强制分解",
    forced: "强制分解",
    on: "强制分解",
    off: "关闭",
    false: "关闭",
  };
  return labels[key] || String(value || "关闭");
}

export function formatAgenticQualityStatus(value: string) {
  const labels: Record<string, string> = {
    sufficient: "证据充足",
    weak: "证据偏弱",
    checked: "已检查",
  };
  return labels[value] || value || "已检查";
}

export function formatAgenticRepairStrategy(value: string) {
  const labels: Record<string, string> = {
    single_search_fallback: "回退原问题",
    subquery_repair: "修复子查询",
  };
  return labels[value] || value || "未触发";
}

export function formatAgenticReason(value: string) {
  const labels: Record<string, string> = {
    agentic_rag_disabled: "深度检索已关闭",
    all_subqueries_failed: "所有子查询失败",
    empty_query: "问题为空",
    forced_by_caller: "手动强制启用",
    low_context_chars: "上下文过少",
    low_relevance_coverage: "相关覆盖不足",
    low_score: "相似度偏低",
    low_source_count: "来源数量不足",
    low_subquery_coverage: "子问题覆盖不足",
    multiple_questions: "包含多个问题",
    no_sources: "没有召回来源",
    simple_query_fast_path: "简单问题使用快速检索",
  };
  if (value.startsWith("multi_intent_terms")) return "识别到多意图问题";
  if (value.includes("fallback_rule_split")) return "问题拆分失败，已使用规则拆分";
  return labels[value] || value.replaceAll("_", " ");
}

export function formatAgenticRecommendation(value: string) {
  const labels: Record<string, string> = {
    "Agentic evidence is sufficient for grounded synthesis.": "当前证据链可以支撑回答。",
    "Evidence is weak; use a fallback retrieval path before answering.": "证据偏弱，回答前应先回退到基础检索。",
    "No evidence was found. Check indexing coverage or widen candidate_top_k.": "没有召回证据，请检查索引覆盖或扩大候选证据数量。",
    "Relevant coverage is low; repair weak branches or retry with broader retrieval.": "相关覆盖不足，请修复薄弱分支或使用更宽的检索策略。",
    "Some branches returned weakly related chunks; retry the original query with broader retrieval.": "部分分支证据相关性偏弱，系统已尝试用更宽的检索路径修复。",
    "Subquery coverage is low; repair weak branches or retry with broader retrieval.": "子问题覆盖不足，请修复薄弱分支或使用更宽的检索策略。",
    "Use the merged evidence as grounded context, then answer with citations.": "可使用合并证据作为回答上下文，并附带引用。",
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
    return { tone: "warning", text: "下一步：先检查资料是否已完成索引，再扩大证据数量或候选召回。" };
  }
  if (reasons.includes("low_relevance_coverage")) {
    return { tone: "warning", text: "下一步：使用“深度追问”方案复测，或检查对应文档分块是否包含问题关键词。" };
  }
  if (reasons.includes("low_subquery_coverage")) {
    return { tone: "warning", text: "下一步：提高来源上限或上下文预算，确认每个子问题都能召回到证据。" };
  }
  if (reasons.includes("low_context_chars") || truncated) {
    return { tone: "warning", text: "下一步：适当提高上下文预算，避免关键证据在打包阶段被截断。" };
  }
  if (fallback) {
    return { tone: "warning", text: "下一步：查看回退原因；若原问题召回更好，可以保留快速检索作为默认路径。" };
  }
  return { tone: "success", text: "当前证据链稳定，可以进入聊天问答验证最终回答质量。" };
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
