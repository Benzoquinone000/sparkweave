import {
  formatRagEvalMs,
  formatRagEvalRate,
  formatStrategyName,
} from "./ragEvaluationBaseFormat";
import { isRecord, readNumber } from "./ragUtils";

export function formatRagExperimentHeadline(summary: Record<string, unknown>) {
  const leader = String(summary.quality_leader || "strategy");
  const metrics = isRecord(summary.quality_leader_metrics) ? summary.quality_leader_metrics : {};
  return `当前领先方案：${formatStrategyName(leader)}，来源命中 ${formatRagEvalRate(readNumber(metrics, "source_hit_rate"))}，来源排序 ${formatRagEvalRate(readNumber(metrics, "avg_source_ndcg"))}，关键词覆盖 ${formatRagEvalRate(readNumber(metrics, "keyword_recall"))}，较慢请求 ${formatRagEvalMs(readNumber(metrics, "p95_latency_ms"))}。`;
}

export function formatRagExperimentRecommendation(summary: Record<string, unknown>) {
  const leader = String(summary.quality_leader || "");
  const baseline = String(summary.baseline_strategy || "baseline");
  const delta = isRecord(summary.quality_delta) ? summary.quality_delta : {};
  const sourceDelta = readNumber(delta, "source_hit_delta") ?? 0;
  const keywordDelta = readNumber(delta, "keyword_recall_delta") ?? 0;
  const latencyDelta = readNumber(delta, "p95_latency_delta_ms") ?? 0;
  if (!leader) return "先运行评测，再决定默认查找策略。";
  if (leader === baseline) return "当前基础策略仍然最稳，优先检查资料覆盖、切片和整理质量。";
  if (latencyDelta > 1000 && Math.max(sourceDelta, keywordDelta) < 0.05) {
    return "质量收益不大但耗时明显变高，建议作为复杂问题的可选方案，不要直接设为默认。";
  }
  if (Math.max(sourceDelta, keywordDelta) >= 0.05) {
    return "建议用于复杂问题、考试复盘和高风险问答；普通快速对话继续保留基础策略。";
  }
  return "领先幅度较小，建议扩大标注样本后再决定是否设为默认。";
}

export function ragExperimentDecisionTone(value: string): "success" | "warning" | "neutral" | "brand" {
  if (value === "promote_default") return "success";
  if (value === "use_for_complex_queries") return "brand";
  if (value === "keep_baseline") return "neutral";
  return "warning";
}

export function formatRagExperimentDecision(summary: Record<string, unknown>) {
  const decision = String(summary.decision || "");
  const labels: Record<string, string> = {
    keep_baseline: "继续使用基础策略",
    needs_evaluation: "需要先评测",
    needs_more_data: "需要更多样本",
    promote_default: "可作为默认候选",
    use_for_complex_queries: "用于复杂问题",
  };
  return labels[decision] || String(summary.decision_label || "待判断");
}
