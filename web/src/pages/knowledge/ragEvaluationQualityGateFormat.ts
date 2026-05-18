import {
  formatRagEvalMs,
  formatRagEvalNumber,
  formatRagEvalRate,
  formatStrategyName,
} from "./ragEvaluationBaseFormat";
import {
  isReleaseDatasetProfile,
  isSmokeDatasetProfile,
} from "./ragEvaluationDatasetFormat";
import { isRecord, readNumber } from "./ragUtils";

export function qualityGateTone(
  value: string,
  datasetProfile: Record<string, unknown> | null = null,
): "success" | "warning" | "neutral" {
  if (!isReleaseDatasetProfile(datasetProfile)) return "neutral";
  if (value === "pass") return "success";
  if (value === "warn" || value === "fail") return "warning";
  return "neutral";
}

export function qualityGateClass(value: string, datasetProfile: Record<string, unknown> | null = null) {
  if (!isReleaseDatasetProfile(datasetProfile)) return "border-line bg-canvas";
  if (value === "pass") return "border-emerald-200 bg-emerald-50";
  if (value === "fail") return "border-red-200 bg-red-50";
  if (value === "warn") return "border-amber-200 bg-amber-50";
  return "border-line bg-canvas";
}

export function formatQualityGateStatus(
  gate: Record<string, unknown>,
  datasetProfile: Record<string, unknown> | null = null,
) {
  const datasetStatus = String(datasetProfile?.label_status || "");
  if (datasetStatus === "smoke_check") return "需标注";
  if (datasetStatus === "partial") return "补标注";
  if (datasetStatus === "empty") return "缺少样本";
  const status = String(gate.status || "");
  const labels: Record<string, string> = {
    fail: "暂不通过",
    pass: "可发布",
    warn: "需观察",
  };
  return labels[status] || String(gate.status_label || "待判断");
}

export function formatQualityGateHeadline(
  gate: Record<string, unknown>,
  datasetProfile: Record<string, unknown> | null = null,
) {
  const datasetStatus = String(datasetProfile?.label_status || "");
  if (datasetStatus === "smoke_check") {
    return "这次结果先用于确认检索链路；质量门需要带期望关键词和来源的样本。";
  }
  if (datasetStatus === "partial") {
    return "已有部分标注，质量门可以参考，但还不适合决定默认检索策略。";
  }
  if (datasetStatus === "empty") {
    return "还没有可评测样本，先添加问题再运行检索质量评估。";
  }
  const headline = String(gate.headline || "").trim();
  if (headline) return translateQualityGateText(headline);
  const strategy = String(gate.strategy || "当前策略");
  return `${formatStrategyName(strategy)} 的检索质量已完成评估。`;
}

export function formatQualityGateRecommendation(
  gate: Record<string, unknown>,
  datasetProfile: Record<string, unknown> | null = null,
) {
  const datasetStatus = String(datasetProfile?.label_status || "");
  const minCases = readNumber(datasetProfile, "min_release_cases") ?? 30;
  if (datasetStatus === "smoke_check") {
    return "如果只是确认资料能否被问到，这次体检已经足够；如果要调默认策略，请先准备标注样本。";
  }
  if (datasetStatus === "partial") {
    return `继续补齐期望关键词和期望来源；正式质量门建议至少 ${minCases} 个完整标注样本。`;
  }
  return translateQualityGateText(String(gate.recommendation || "先处理质量门提示，再把策略设为默认。"));
}

export function qualityGateReasons(gate: Record<string, unknown>) {
  return Array.isArray(gate.reasons) ? gate.reasons.map((item) => String(item || "").trim()).filter(Boolean) : [];
}

export function qualityGateMetrics(gate: Record<string, unknown>, datasetProfile: Record<string, unknown> | null = null) {
  const metrics = isRecord(gate.metrics) ? gate.metrics : {};
  if (isSmokeDatasetProfile(datasetProfile)) {
    return [
      { label: "样本", value: String(readNumber(metrics, "cases") ?? "-") },
      { label: "检索成功", value: formatRagEvalRate(readNumber(metrics, "success_rate")) },
      { label: "平均来源", value: formatRagEvalNumber(readNumber(metrics, "avg_source_count")) },
      { label: "较慢请求", value: formatRagEvalMs(readNumber(metrics, "p95_latency_ms")) },
    ];
  }
  return [
    { label: "样本", value: String(readNumber(metrics, "cases") ?? "-") },
    { label: "来源命中", value: formatRagEvalRate(readNumber(metrics, "source_hit_rate")) },
    { label: "证据排序", value: formatRagEvalRate(readNumber(metrics, "avg_source_ndcg")) },
    { label: "质量分", value: formatRagEvalRate(readNumber(metrics, "quality_score")) },
  ];
}

export function translateQualityGateReason(value: string) {
  const text = translateQualityGateText(value);
  return text.endsWith("。") ? text : `${text}。`;
}

function translateQualityGateText(value: string) {
  return value
    .replace("No strategy summary rows were produced.", "没有生成任何策略评测摘要")
    .replace("All tracked retrieval quality gates passed.", "所有已跟踪的检索质量门都已通过")
    .replace("Run a labelled RAG evaluation before trusting this knowledge base.", "先运行带标注的 RAG 评测，再信任这个资料库")
    .replace("Create at least one labelled dataset, then rerun the RAG quality experiment.", "先准备带标注的数据集，再重新运行 RAG 质量评测")
    .replace("Keep this retrieval setup as the current release baseline and monitor future regressions.", "可以把这套检索配置作为当前发布基线，并持续监控后续回归")
    .replace("Keep the strategy gated for normal use, review the highlighted cases, then rerun the same dataset.", "普通使用先保持策略受控，检查高亮样本后用同一数据集复测")
    .replace("Fix retrieval execution errors before tuning ranking or prompt behavior.", "先修复检索执行错误，再调整排序或提示词")
    .replace("Do not promote this retrieval setup until the failed quality checks are addressed and re-evaluated.", "失败项处理并复测前，不要把这套检索配置提升为默认")
    .replace(/Only (\d+) cases were evaluated; at least (\d+) are required for a basic gate\./, "只评测了 $1 个样本，基础质量门至少需要 $2 个。")
    .replace(/Only (\d+) cases were evaluated; target baseline is (\d+)\./, "只评测了 $1 个样本，目标基线是 $2 个。")
    .replace(/(\d+) critical retrieval diagnostics were found\./, "发现 $1 个严重检索诊断项。")
    .replace(/(\d+) high-severity diagnostics need review\./, "$1 个高严重度诊断项需要复核。")
    .replace(/(\d+) cases produced diagnostics\./, "$1 个样本产生了诊断提示。")
    .replace("Retrieval success rate is below 95%.", "检索成功率低于 95%。")
    .replace("Expected-source hit rate is below 75%.", "期望来源命中率低于 75%。")
    .replace("Expected-source hit rate is below the 85% release target.", "期望来源命中率低于 85% 发布目标。")
    .replace("Evidence ranking nDCG is below 70%.", "证据排序 nDCG 低于 70%。")
    .replace("Evidence ranking nDCG is below the 80% release target.", "证据排序 nDCG 低于 80% 发布目标。")
    .replace("Keyword recall is below 55%.", "关键词召回低于 55%。")
    .replace("Keyword recall is below the 65% release target.", "关键词召回低于 65% 发布目标。")
    .replace("Evidence reasons are sparse; explanations may feel thin.", "证据理由偏少，解释可能显得单薄。")
    .replace("The strategy comparison still needs more evidence before changing defaults.", "更改默认策略前，还需要更多评测证据。")
    .replace("is ready:", "已达到发布标准：")
    .replace("is usable but needs review:", "可用但需要复核：")
    .replace("is blocked by quality issues:", "被质量问题阻断：")
    .replace("source hit", "来源命中")
    .replace("keyword recall", "关键词召回");
}
