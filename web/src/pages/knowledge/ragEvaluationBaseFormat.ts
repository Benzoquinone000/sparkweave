export const RAG_EVAL_PRESETS = [
  {
    id: "quick_check",
    label: "快速体检",
    description: "最快确认资料能否被检索，适合上传或重建索引后立即检查。",
    detail: "2 个策略 · 3 个样本 · 通常几十秒内",
    buttonLabel: "运行快速体检",
    runningLabel: "体检中",
  },
  {
    id: "default",
    label: "标准体检",
    description: "覆盖基础、宽召回和严格召回，适合日常回归检查。",
    detail: "3 个策略 · 3 个样本 · 适合日常验证",
    buttonLabel: "运行标准体检",
    runningLabel: "评测中",
  },
  {
    id: "rag_upgrade",
    label: "完整对比",
    description: "加入混合重排、HyDE 和 Agentic 检索，适合正式调优或演示前。",
    detail: "6 个策略 · 会调用较重流程 · 可能持续数分钟",
    buttonLabel: "运行完整对比",
    runningLabel: "完整评测中",
  },
];

export function ragEvaluationTone(
  successRate: number | null | undefined,
  sourceHitRate: number | null | undefined,
): "success" | "warning" | "neutral" {
  const success = typeof successRate === "number" ? successRate : 0;
  const sourceHit = typeof sourceHitRate === "number" ? sourceHitRate : success;
  if (success >= 0.8 && sourceHit >= 0.7) return "success";
  if (success > 0 || sourceHit > 0) return "warning";
  return "neutral";
}

export function formatRagEvalRate(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  const normalized = value > 1 ? value : value * 100;
  return `${Math.round(normalized)}%`;
}

export function formatRagEvalMs(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  if (value >= 1000) return `${(value / 1000).toFixed(1)}s`;
  return `${Math.round(value)}ms`;
}

export function formatRagEvalNumber(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  if (Math.abs(value - Math.round(value)) < 0.05) return String(Math.round(value));
  return value.toFixed(1);
}

export function formatRagEvalChars(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  if (value >= 1000) return `${(value / 1000).toFixed(1)}k`;
  return String(Math.round(value));
}

export function formatRagEvalDeltaRate(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  const points = value > 1 || value < -1 ? value : value * 100;
  return `${points >= 0 ? "+" : ""}${points.toFixed(1)}pp`;
}

export function formatRagEvalDeltaMs(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  return `${value >= 0 ? "+" : ""}${Math.round(value)}ms`;
}

export function ragDeltaTone(value: number | null | undefined): "success" | "warning" | "neutral" {
  if (typeof value !== "number" || Number.isNaN(value)) return "neutral";
  if (value > 0) return "success";
  if (value < 0) return "warning";
  return "neutral";
}

export function formatStrategyName(value: string) {
  const labels: Record<string, string> = {
    adaptive_policy: "自适应策略",
    agentic_hyde: "深度改写检索",
    baseline: "基础策略",
    dense_strict: "精确语义检索",
    dense_wide: "宽松语义检索",
    hybrid_keyword_rerank: "混合检索重排",
    hyde_hybrid_rerank: "问题改写混合检索",
    wide_context: "宽上下文",
  };
  return labels[value] || value.replaceAll("_", " ");
}

export function formatRagPresetName(value: string) {
  const normalized = value.replaceAll("-", "_");
  const preset = RAG_EVAL_PRESETS.find((item) => item.id === normalized);
  if (preset) return preset.label;
  if (normalized === "custom") return "自定义评测";
  return value.replaceAll("_", " ");
}

export function formatRagEvalTime(value: unknown) {
  if (!value) return "刚刚";
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export function formatQueryType(value: unknown) {
  const labels: Record<string, string> = {
    code: "代码题",
    concept: "概念题",
    exact: "精确事实",
    fact: "事实题",
    formula: "公式推导",
    guide: "导学问题",
    untyped: "未分类",
  };
  const key = String(value || "untyped");
  return labels[key] || key;
}
