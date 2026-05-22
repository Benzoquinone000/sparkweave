import { Badge } from "@/components/ui/Badge";
import type { RagEvaluationSummaryRow } from "@/lib/types";

import { ConfigFact } from "./ConfigFact";
import { readNumber } from "./ragUtils";
import {
  formatQueryType,
  formatQualityGateHeadline,
  formatQualityGateRecommendation,
  formatQualityGateStatus,
  formatRagEvalDeltaMs,
  formatRagEvalDeltaRate,
  formatRagEvalRate,
  formatRagExperimentDecision,
  formatRagExperimentHeadline,
  formatRagExperimentRecommendation,
  formatStrategyName,
  isReleaseDatasetProfile,
  qualityGateClass,
  qualityGateMetrics,
  qualityGateReasons,
  qualityGateTone,
  ragDeltaTone,
  ragEvaluationTone,
  ragExperimentDecisionTone,
  translateQualityGateReason,
} from "./ragEvaluationFormat";

export function RagExperimentSummaryPanel({
  experimentSummary,
}: {
  experimentSummary: Record<string, unknown>;
}) {
  const experimentQualityScore = readNumber(experimentSummary, "quality_score");
  const experimentLatencyTradeoffMs = readNumber(experimentSummary, "latency_tradeoff_ms");

  return (
    <div className="mt-4 rounded-lg border border-line bg-canvas p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-ink">实验结论</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">{formatRagExperimentHeadline(experimentSummary)}</p>
        </div>
        <Badge tone="brand">{formatStrategyName(String(experimentSummary.quality_leader || "strategy"))}</Badge>
      </div>
      <div className="mt-2 flex flex-wrap gap-2">
        <Badge tone={ragExperimentDecisionTone(String(experimentSummary.decision || ""))}>
          {formatRagExperimentDecision(experimentSummary)}
        </Badge>
        {typeof experimentQualityScore === "number" ? <Badge tone="neutral">质量分 {Math.round(experimentQualityScore * 100)}%</Badge> : null}
        {typeof experimentLatencyTradeoffMs === "number" ? (
          <Badge tone="neutral">延迟 {formatRagEvalDeltaMs(experimentLatencyTradeoffMs)}</Badge>
        ) : null}
      </div>
      <p className="mt-2 text-xs leading-5 text-slate-600">{formatRagExperimentRecommendation(experimentSummary)}</p>
    </div>
  );
}

export function RagQualityGatePanel({
  qualityGate,
  datasetProfile,
}: {
  qualityGate: Record<string, unknown>;
  datasetProfile: Record<string, unknown> | null;
}) {
  const releaseDataset = isReleaseDatasetProfile(datasetProfile);
  const qualityGateReasonRows = qualityGateReasons(qualityGate).slice(0, 3);

  return (
    <div
      className={`mt-4 rounded-lg border p-3 ${qualityGateClass(String(qualityGate.status || ""), datasetProfile)}`}
      data-testid="knowledge-rag-quality-gate"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-ink">{releaseDataset ? "质量判断" : "质量判断准备度"}</p>
          <p className="mt-1 text-xs leading-5 text-slate-600">{formatQualityGateHeadline(qualityGate, datasetProfile)}</p>
        </div>
        <Badge tone={qualityGateTone(String(qualityGate.status || ""), datasetProfile)}>
          {formatQualityGateStatus(qualityGate, datasetProfile)}
        </Badge>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-4">
        {qualityGateMetrics(qualityGate, datasetProfile).map((item) => (
          <ConfigFact key={item.label} label={item.label} value={item.value} />
        ))}
      </div>
      <p className="mt-3 text-xs leading-5 text-slate-600">{formatQualityGateRecommendation(qualityGate, datasetProfile)}</p>
      {qualityGateReasonRows.length ? (
        <div className="mt-2 grid gap-1.5">
          {qualityGateReasonRows.map((reason) => (
            <p key={reason} className="text-xs leading-5 text-charcoal">
              - {translateQualityGateReason(reason)}
            </p>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function RagDeltaRowsPanel({
  rows,
  baselineName,
}: {
  rows: Record<string, unknown>[];
  baselineName: string;
}) {
  return (
    <div className="mt-4 rounded-lg border border-line bg-canvas p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-xs font-semibold text-ink">相对基础策略收益</p>
          <p className="mt-1 text-xs text-slate-500">以 {formatStrategyName(baselineName)} 为参照，看升级策略带来的来源变化。</p>
        </div>
        <Badge tone="neutral">{rows.length} 个策略</Badge>
      </div>
      <div className="mt-3 grid gap-2 lg:grid-cols-2">
        {rows.map((row) => {
          const strategy = String(row.strategy || "strategy");
          const sourceDelta = readNumber(row, "source_hit_delta");
          const sourceNdcgDelta = readNumber(row, "source_ndcg_delta");
          const keywordDelta = readNumber(row, "keyword_recall_delta");
          const latencyDelta = readNumber(row, "p95_latency_delta_ms");
          return (
            <div key={strategy} className="rounded-lg border border-line bg-white p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="truncate text-xs font-semibold text-ink">{formatStrategyName(strategy)}</p>
                <Badge tone={ragDeltaTone(sourceDelta)}>{formatRagEvalDeltaRate(sourceDelta)}</Badge>
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-500">
                <span>排序 {formatRagEvalDeltaRate(sourceNdcgDelta)}</span>
                <span>关键词 {formatRagEvalDeltaRate(keywordDelta)}</span>
                <span>延迟 {formatRagEvalDeltaMs(latencyDelta)}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function RagTypedRowsPanel({
  rows,
}: {
  rows: RagEvaluationSummaryRow[];
}) {
  return (
    <div className="mt-4 grid gap-2 sm:grid-cols-3">
      {rows.map((row, index) => (
        <div key={`${row.strategy || "strategy"}-${row.query_type || index}`} className="rounded-lg border border-line bg-canvas p-3">
          <div className="flex items-center justify-between gap-2">
            <p className="truncate text-xs font-semibold text-ink">{formatQueryType(row.query_type)}</p>
            <Badge tone={ragEvaluationTone(row.success_rate, row.source_hit_rate)}>{formatRagEvalRate(row.source_hit_rate)}</Badge>
          </div>
          <p className="mt-2 text-xs leading-5 text-slate-500">
            {row.cases ?? 0} 题 · 关键词 {formatRagEvalRate(row.keyword_recall)}
          </p>
        </div>
      ))}
    </div>
  );
}
