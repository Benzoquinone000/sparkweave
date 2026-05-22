import { BarChart3, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

import { ConfigFact } from "./ConfigFact";
import { readNumber } from "./ragUtils";
import {
  RAG_EVAL_PRESETS,
  datasetProfileClass,
  datasetProfileTone,
  formatDatasetProfileCount,
  formatDatasetProfileHeadline,
  formatDatasetProfileRecommendation,
  formatDatasetProfileStatus,
} from "./ragEvaluationFormat";

export {
  RagDeltaRowsPanel,
  RagExperimentSummaryPanel,
  RagQualityGatePanel,
  RagTypedRowsPanel,
} from "./RagEvaluationResultPanels";
export {
  RagDiagnosticRowsPanel,
  RagDiagnosticSummaryPanel,
} from "./RagEvaluationDiagnosticPanels";

export function RagEvaluationPresetPanel({
  preset,
  running,
  onPresetChange,
  onRun,
}: {
  preset: string;
  running: boolean;
  onPresetChange: (preset: string) => void;
  onRun: () => void;
}) {
  const currentPreset = RAG_EVAL_PRESETS.find((item) => item.id === preset) ?? RAG_EVAL_PRESETS[0];

  return (
    <div className="mt-4 rounded-lg border border-line bg-canvas p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-ink">评测方案</p>
          <p className="mt-1 text-xs text-slate-500">{currentPreset.description}</p>
          <p className="mt-1 text-xs text-steel">{currentPreset.detail}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {RAG_EVAL_PRESETS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`min-h-8 rounded-lg border px-3 text-xs font-semibold transition ${
                preset === item.id
                  ? "border-brand-purple bg-tint-lavender text-brand-purple"
                  : "border-line bg-white text-slate-600 hover:border-slate-300 hover:text-ink"
              }`}
              onClick={() => onPresetChange(item.id)}
            >
              {item.label}
            </button>
          ))}
          <Button tone="primary" className="min-h-8 px-3 text-xs" onClick={onRun} disabled={running}>
            {running ? <Loader2 size={14} className="animate-spin" /> : <BarChart3 size={14} />}
            {running ? currentPreset.runningLabel : currentPreset.buttonLabel}
          </Button>
        </div>
      </div>
      {currentPreset.id === "rag_upgrade" ? (
        <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900">
          完整对比会逐个运行多种查找策略，适合有标注样本时使用；只想确认资料能不能被问到，建议先用快速体检。
        </div>
      ) : null}
    </div>
  );
}

export function RagDatasetProfilePanel({
  datasetProfile,
}: {
  datasetProfile: Record<string, unknown>;
}) {
  return (
    <div
      className={`mt-4 rounded-lg border p-3 ${datasetProfileClass(String(datasetProfile.label_status || ""))}`}
      data-testid="knowledge-rag-dataset-profile"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-ink">样本可信度</p>
          <p className="mt-1 text-xs leading-5 text-slate-600">{formatDatasetProfileHeadline(datasetProfile)}</p>
        </div>
        <Badge tone={datasetProfileTone(String(datasetProfile.label_status || ""))}>
          {formatDatasetProfileStatus(datasetProfile)}
        </Badge>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-4">
        <ConfigFact label="样本" value={String(readNumber(datasetProfile, "case_count") ?? "-")} />
        <ConfigFact label="关键词标注" value={formatDatasetProfileCount(datasetProfile, "keyword_labelled_cases")} />
        <ConfigFact label="来源标注" value={formatDatasetProfileCount(datasetProfile, "source_labelled_cases")} />
        <ConfigFact label="完整标注" value={formatDatasetProfileCount(datasetProfile, "fully_labelled_cases")} />
      </div>
      <p className="mt-3 text-xs leading-5 text-slate-600">{formatDatasetProfileRecommendation(datasetProfile)}</p>
    </div>
  );
}
