import { Badge } from "@/components/ui/Badge";

import { readNumber } from "./ragUtils";
import {
  formatRagCaseIssue,
  formatRagCaseRecommendation,
  formatRagDiagnosticHeadline,
  formatRagDiagnosticSeverity,
  formatRagDiagnosticSummaryAction,
  formatRagEvalRate,
  formatStrategyName,
  ragDiagnosticSeverityTone,
} from "./ragEvaluationFormat";

export function RagDiagnosticSummaryPanel({
  diagnosticSummary,
}: {
  diagnosticSummary: Record<string, unknown>;
}) {
  return (
    <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-xs font-semibold text-amber-900">诊断结论</p>
          <p className="mt-1 text-xs leading-5 text-amber-800">{formatRagDiagnosticHeadline(diagnosticSummary)}</p>
        </div>
        <Badge tone={ragDiagnosticSeverityTone(String(diagnosticSummary.primary_severity || ""))}>
          {formatRagDiagnosticSeverity(String(diagnosticSummary.primary_severity || ""))}
        </Badge>
      </div>
      <p className="mt-2 text-xs leading-5 text-amber-900">{formatRagDiagnosticSummaryAction(diagnosticSummary)}</p>
    </div>
  );
}

export function RagDiagnosticRowsPanel({
  rows,
}: {
  rows: Record<string, unknown>[];
}) {
  return (
    <div className="mt-4 rounded-lg border border-line bg-white p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-xs font-semibold text-ink">需要优先检查的样本</p>
          <p className="mt-1 text-xs text-slate-500">把异常结果翻译成可执行的资料优化动作。</p>
        </div>
        <Badge tone="warning">{rows.length} 条</Badge>
      </div>
      <div className="mt-3 grid gap-2">
        {rows.map((row, index) => {
          const severity = String(row.severity || "low");
          const strategy = String(row.strategy || "strategy");
          const caseId = String(row.case_id || `case-${index + 1}`);
          const issueCode = String(row.issue_code || "");
          return (
            <div key={`${strategy}-${caseId}-${index}`} className="rounded-lg border border-line bg-canvas p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-xs font-semibold text-ink">
                    {caseId} · {formatStrategyName(strategy)}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">{formatRagCaseIssue(issueCode, row.issue)}</p>
                </div>
                <Badge tone={ragDiagnosticSeverityTone(severity)}>{formatRagDiagnosticSeverity(severity)}</Badge>
              </div>
              <p className="mt-2 text-xs leading-5 text-slate-600">{formatRagCaseRecommendation(issueCode, row.recommendation)}</p>
              <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500">
                <span>来源 {String(row.source_count ?? "-")}</span>
                <span>关键词 {formatRagEvalRate(readNumber(row, "keyword_recall"))}</span>
                <span>回答材料 {String(row.context_chars ?? 0)} 字</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
