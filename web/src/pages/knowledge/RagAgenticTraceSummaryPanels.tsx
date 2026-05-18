import { Badge } from "@/components/ui/Badge";
import type { RagSearchTestResult } from "@/lib/types";

import { ConfigFact } from "./ConfigFact";
import {
  agenticNextActionClass,
  formatAgenticQualityStatus,
  formatAgenticReason,
  formatAgenticRecommendation,
  formatPercentValue,
  readNumber,
  readString,
} from "./ragUtils";

type AgenticNextAction = {
  tone: "success" | "warning" | "neutral";
  text: string;
};

export function AgenticTraceHeader({
  result,
  quality,
  qualityStatus,
  qualityScore,
  isWeak,
  planReason,
}: {
  result: RagSearchTestResult;
  quality: Record<string, unknown> | null;
  qualityStatus: string;
  qualityScore: number | undefined;
  isWeak: boolean;
  planReason: string;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-2">
      <div>
        <p className="text-sm font-semibold text-ink">深度检索过程</p>
        <p className="mt-1 text-xs leading-5 text-slate-500">
          {planReason ? formatAgenticReason(planReason) : "展示问题拆分、质量检查、分支修复和最终上下文预算。"}
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Badge tone={result.agentic_fallback ? "warning" : result.agentic_rag ? "brand" : "neutral"}>
          {result.agentic_fallback ? "已回退" : result.agentic_rag ? "分解检索" : "快速检索"}
        </Badge>
        {quality ? <Badge tone={isWeak ? "warning" : "success"}>{formatAgenticQualityStatus(qualityStatus)}</Badge> : null}
        {typeof qualityScore === "number" ? <Badge tone="neutral">{formatPercentValue(qualityScore)}</Badge> : null}
      </div>
    </div>
  );
}

export function AgenticTraceMetricGrid({
  quality,
  contextPack,
  result,
  contentChars,
  sourceCount,
  subqueryCount,
  isWeak,
  reasons,
}: {
  quality: Record<string, unknown> | null;
  contextPack: Record<string, unknown> | null;
  result: RagSearchTestResult;
  contentChars: number;
  sourceCount: number;
  subqueryCount: number;
  isWeak: boolean;
  reasons: string[];
}) {
  const contextUsed = readNumber(contextPack, "context_chars") ?? readNumber(quality, "content_chars") ?? contentChars;
  const contextLimit = readNumber(contextPack, "max_context_chars");

  return (
    <div className="mt-3 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
      <ConfigFact
        label="子问题覆盖"
        value={`${readNumber(quality, "covered_subqueries") ?? "-"} / ${
          readNumber(quality, "total_subqueries") ?? (subqueryCount || "-")
        }`}
        tone={isWeak && reasons.includes("low_subquery_coverage") ? "warning" : undefined}
      />
      <ConfigFact
        label="相关覆盖"
        value={`${readNumber(quality, "relevant_subqueries") ?? "-"} / ${
          readNumber(quality, "total_subqueries") ?? (subqueryCount || "-")
        }`}
        tone={isWeak && reasons.includes("low_relevance_coverage") ? "warning" : undefined}
      />
      <ConfigFact label="证据来源" value={String(readNumber(quality, "source_count") ?? result.source_count ?? sourceCount)} />
      <ConfigFact
        label="上下文预算"
        value={contextLimit ? `${contextUsed} / ${contextLimit} 字` : `${contextUsed} 字`}
        tone={contextPack?.truncated ? "warning" : undefined}
      />
    </div>
  );
}

export function AgenticThresholdStrip({ thresholds }: { thresholds: Record<string, unknown> | null }) {
  if (!thresholds) return null;

  return (
    <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
      <span>质量标准：来源 ≥ {String(readNumber(thresholds, "min_sources") ?? "-")}</span>
      <span>覆盖 ≥ {formatPercentValue(readNumber(thresholds, "min_coverage_ratio"))}</span>
      <span>相关覆盖 ≥ {formatPercentValue(readNumber(thresholds, "min_relevant_coverage_ratio"))}</span>
      <span>上下文 ≥ {String(readNumber(thresholds, "min_context_chars") ?? "-")} 字</span>
    </div>
  );
}

export function AgenticReasonBadges({ reasons }: { reasons: string[] }) {
  if (!reasons.length) return null;

  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {reasons.map((reason) => (
        <Badge key={reason} tone="warning">
          {formatAgenticReason(reason)}
        </Badge>
      ))}
    </div>
  );
}

export function AgenticRecommendation({
  quality,
  nextAction,
}: {
  quality: Record<string, unknown> | null;
  nextAction: AgenticNextAction | null;
}) {
  const recommendation = readString(quality, "recommendation");

  return (
    <>
      {recommendation ? (
        <p className="mt-3 text-xs leading-5 text-slate-600">{formatAgenticRecommendation(recommendation)}</p>
      ) : null}

      {nextAction ? (
        <div className={`mt-3 rounded-md border px-3 py-2 text-xs leading-5 ${agenticNextActionClass(nextAction.tone)}`}>
          {nextAction.text}
        </div>
      ) : null}
    </>
  );
}
