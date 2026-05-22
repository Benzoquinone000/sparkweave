import { BarChart3, Loader2, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import type { RagEvaluationReport } from "@/lib/types";

import { ConfigFact } from "./ConfigFact";
import { isRecord, readNumber } from "./ragUtils";
import { KNOWLEDGE_PANEL_CLASS } from "./styles";
import {
  formatRagEvalTime,
  formatRagPresetName,
  ragEvaluationMetricFacts,
  ragEvaluationTone,
} from "./ragEvaluationFormat";
import {
  RagDatasetProfilePanel,
  RagDeltaRowsPanel,
  RagDiagnosticRowsPanel,
  RagDiagnosticSummaryPanel,
  RagEvaluationPresetPanel,
  RagExperimentSummaryPanel,
  RagQualityGatePanel,
  RagTypedRowsPanel,
} from "./RagEvaluationPanels";

export function RagEvaluationCard({
  report,
  available,
  loading,
  error,
  onRefresh,
  preset,
  onPresetChange,
  onRun,
  running,
}: {
  report?: RagEvaluationReport | null;
  available: boolean;
  loading: boolean;
  error: unknown;
  onRefresh: () => void;
  preset: string;
  onPresetChange: (preset: string) => void;
  onRun: () => void;
  running: boolean;
}) {
  const baselineName = String(report?.baseline_strategy || "baseline");
  const summary = report?.summary?.find((item) => item.strategy === baselineName) ?? report?.summary?.[0];
  const typedRows = (report?.summary_by_query_type ?? []).slice(0, 3);
  const deltaRows = (report?.deltas ?? []).filter(isRecord).slice(0, 4);
  const experimentSummary = isRecord(report?.experiment_summary) ? report.experiment_summary : null;
  const qualityGate = isRecord(report?.quality_gate) ? report.quality_gate : null;
  const datasetProfile = isRecord(report?.dataset_profile) ? report.dataset_profile : null;
  const diagnosticRows = (report?.case_diagnostics ?? []).filter(isRecord).slice(0, 4);
  const diagnosticSummary = isRecord(report?.diagnostic_summary) ? report.diagnostic_summary : null;
  const tone = ragEvaluationTone(summary?.success_rate, summary?.source_hit_rate);
  const reportPresetLabel = report?.preset ? formatRagPresetName(String(report.preset)) : "";

  return (
    <section className={`mt-4 ${KNOWLEDGE_PANEL_CLASS}`} data-testid="knowledge-rag-eval-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-line bg-canvas text-brand-purple">
            <BarChart3 size={18} />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-ink">资料来源检查</p>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              {loading
                ? "正在读取最近一次评测摘要..."
                : error
                  ? "评测摘要读取失败，稍后再试。"
                  : available && report
                    ? `最近评测：${formatRagEvalTime(report.created_at)}，${report.case_count ?? summary?.cases ?? 0} 个样本${reportPresetLabel ? ` · ${reportPresetLabel}` : ""}`
                    : "还没有评测记录。先跑一次快速体检，确认资料能被稳定问到。"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone={available && report ? tone : "neutral"}>{available && report ? "已评测" : "未评测"}</Badge>
          <Button tone="quiet" className="min-h-8 px-2 text-xs" onClick={onRefresh}>
            {loading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          </Button>
        </div>
      </div>

      <RagEvaluationPresetPanel
        preset={preset}
        running={running}
        onPresetChange={onPresetChange}
        onRun={onRun}
      />

      {datasetProfile ? <RagDatasetProfilePanel datasetProfile={datasetProfile} /> : null}

      {available && report && summary ? (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-5">
            {ragEvaluationMetricFacts(summary, datasetProfile).map((item) => (
              <ConfigFact key={item.label} label={item.label} value={item.value} />
            ))}
          </div>
          {experimentSummary ? (
            <RagExperimentSummaryPanel experimentSummary={experimentSummary} />
          ) : null}
          {qualityGate ? (
            <RagQualityGatePanel qualityGate={qualityGate} datasetProfile={datasetProfile} />
          ) : null}
          {deltaRows.length ? (
            <RagDeltaRowsPanel rows={deltaRows} baselineName={baselineName} />
          ) : null}
          {diagnosticSummary && readNumber(diagnosticSummary, "total_diagnostics") ? (
            <RagDiagnosticSummaryPanel diagnosticSummary={diagnosticSummary} />
          ) : null}
          {diagnosticRows.length ? (
            <RagDiagnosticRowsPanel rows={diagnosticRows} />
          ) : null}
          {typedRows.length ? (
            <RagTypedRowsPanel rows={typedRows} />
          ) : null}
        </>
      ) : (
        <div className="mt-4 rounded-lg border border-dashed border-line bg-canvas p-3 text-xs leading-5 text-slate-500">
          快速体检用于确认资料查找是否通畅；正式质量对比建议使用标注数据集，准备好问题、期望来源和关键词后再运行完整对比。
        </div>
      )}
    </section>
  );
}
