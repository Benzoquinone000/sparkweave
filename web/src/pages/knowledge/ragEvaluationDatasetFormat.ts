import type { RagEvaluationReport } from "@/lib/types";

import {
  formatRagEvalChars,
  formatRagEvalMs,
  formatRagEvalNumber,
  formatRagEvalRate,
} from "./ragEvaluationBaseFormat";
import { readNumber } from "./ragUtils";

export function datasetProfileTone(value: string): "success" | "warning" | "neutral" | "brand" {
  if (value === "release_ready") return "success";
  if (value === "partial") return "brand";
  if (value === "smoke_check") return "neutral";
  return "warning";
}

export function datasetProfileClass(value: string) {
  if (value === "release_ready") return "border-emerald-200 bg-emerald-50";
  if (value === "partial") return "border-brand-purple-300 bg-tint-lavender";
  if (value === "smoke_check") return "border-line bg-canvas";
  return "border-amber-200 bg-amber-50";
}

export function formatDatasetProfileStatus(profile: Record<string, unknown>) {
  const status = String(profile.label_status || "");
  const labels: Record<string, string> = {
    empty: "缺少样本",
    partial: "部分标注",
    release_ready: "可做质量判断",
    smoke_check: "体检样本",
  };
  return labels[status] || String(profile.label_status_label || "待判断");
}

export function formatDatasetProfileHeadline(profile: Record<string, unknown>) {
  const status = String(profile.label_status || "");
  if (status === "release_ready") return "这批样本有足够的期望关键词和来源，可用于观察资料查找质量变化。";
  if (status === "partial") return "这批样本已有部分标注，指标可以参考，但还不适合直接决定默认策略。";
  if (status === "smoke_check") return "这批样本主要用于确认资料能否被问到，不代表正式质量结论。";
  return String(profile.headline || "先补充检查样本，再运行资料来源检查。");
}

export function formatDatasetProfileRecommendation(profile: Record<string, unknown>) {
  const status = String(profile.label_status || "");
  const minCases = readNumber(profile, "min_release_cases") ?? 30;
  if (status === "release_ready") return "后续改动查找方案时继续复用这批样本，质量变化会更可比。";
  if (status === "partial") return `建议把更多样本补上期望关键词和来源；正式质量判断建议至少 ${minCases} 个标注样本。`;
  if (status === "smoke_check") return "适合上传或重新整理资料后快速确认链路；要判断质量，请准备期望关键词和来源。";
  return String(profile.recommendation || "添加问题、期望关键词和期望来源后再运行完整对比。");
}

export function formatDatasetProfileCount(profile: Record<string, unknown>, key: string) {
  const value = readNumber(profile, key);
  const total = readNumber(profile, "case_count");
  if (typeof value !== "number") return "-";
  if (!total) return String(value);
  return `${value}/${total}`;
}

export function isReleaseDatasetProfile(profile: Record<string, unknown> | null) {
  return String(profile?.label_status || "") === "release_ready";
}

export function isSmokeDatasetProfile(profile: Record<string, unknown> | null) {
  const status = String(profile?.label_status || "");
  return status === "smoke_check" || status === "empty";
}

export function ragEvaluationMetricFacts(
  summary: NonNullable<RagEvaluationReport["summary"]>[number],
  datasetProfile: Record<string, unknown> | null,
) {
  if (isSmokeDatasetProfile(datasetProfile)) {
    return [
      { label: "查找成功", value: formatRagEvalRate(summary.success_rate) },
      { label: "平均来源", value: formatRagEvalNumber(summary.avg_source_count) },
      { label: "平均回答材料", value: formatRagEvalChars(summary.avg_context_chars) },
      { label: "来源说明", value: formatRagEvalNumber(summary.avg_evidence_reasons) },
      { label: "较慢请求", value: formatRagEvalMs(summary.p95_latency_ms) },
    ];
  }
  return [
    { label: "成功率", value: formatRagEvalRate(summary.success_rate) },
    { label: "关键词覆盖", value: formatRagEvalRate(summary.keyword_recall) },
    { label: "来源命中", value: formatRagEvalRate(summary.source_hit_rate) },
    { label: "来源排序", value: formatRagEvalRate(summary.avg_source_ndcg) },
    { label: "较慢请求", value: formatRagEvalMs(summary.p95_latency_ms) },
  ];
}
