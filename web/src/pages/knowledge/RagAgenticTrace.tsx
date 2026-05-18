import type { RagSearchTestResult } from "@/lib/types";

import {
  AgenticContextPackSummary,
  AgenticReasonBadges,
  AgenticRecommendation,
  AgenticRepairPanel,
  AgenticSubqueriesPanel,
  AgenticThresholdStrip,
  AgenticTraceHeader,
  AgenticTraceMetricGrid,
} from "./RagAgenticTracePanels";
import {
  buildAgenticNextAction,
  isRecord,
  readNumber,
  readString,
  toRecordArray,
  toStringArray,
} from "./ragUtils";
import { KNOWLEDGE_NOTE_CLASS } from "./styles";

export function RagAgenticTrace({
  result,
  contentChars,
  sourceCount,
}: {
  result: RagSearchTestResult;
  contentChars: number;
  sourceCount: number;
}) {
  const quality = isRecord(result.agentic_quality) ? result.agentic_quality : null;
  const contextPack = isRecord(result.agentic_context_pack) ? result.agentic_context_pack : null;
  const repair = isRecord(result.agentic_repair) ? result.agentic_repair : null;
  const activityPlan = isRecord(result.agentic_activity_plan) ? result.agentic_activity_plan : null;
  const queryPlan = isRecord(result.query_plan) ? result.query_plan : isRecord(result.failed_query_plan) ? result.failed_query_plan : null;
  const subqueries = toRecordArray(result.subquery_results);
  const branches = toRecordArray(contextPack?.branches);
  const reasons = toStringArray(quality?.reasons ?? result.agentic_fallback_reason);
  const thresholds = isRecord(quality?.thresholds) ? quality.thresholds : null;
  const planReason = readString(queryPlan, "agentic_reason") || readString(activityPlan, "reason");

  if (!quality && !contextPack && !repair && !activityPlan && !queryPlan && !subqueries.length) {
    return null;
  }

  const qualityStatus = readString(quality, "status");
  const qualityScore = readNumber(quality, "quality_score");
  const isWeak = Boolean(result.agentic_fallback) || qualityStatus === "weak";
  const nextAction = buildAgenticNextAction({
    reasons,
    fallback: Boolean(result.agentic_fallback),
    sourceCount: readNumber(quality, "source_count") ?? result.source_count ?? sourceCount,
    truncated: Boolean(contextPack?.truncated),
  });

  return (
    <div className={KNOWLEDGE_NOTE_CLASS}>
      <AgenticTraceHeader
        result={result}
        quality={quality}
        qualityStatus={qualityStatus}
        qualityScore={qualityScore}
        isWeak={isWeak}
        planReason={planReason}
      />

      <AgenticTraceMetricGrid
        quality={quality}
        contextPack={contextPack}
        result={result}
        contentChars={contentChars}
        sourceCount={sourceCount}
        subqueryCount={subqueries.length}
        isWeak={isWeak}
        reasons={reasons}
      />

      <AgenticThresholdStrip thresholds={thresholds} />
      <AgenticReasonBadges reasons={reasons} />
      <AgenticRecommendation quality={quality} nextAction={nextAction} />
      <AgenticRepairPanel repair={repair} />
      <AgenticSubqueriesPanel subqueries={subqueries} />
      <AgenticContextPackSummary contextPack={contextPack} branchCount={branches.length} />
    </div>
  );
}
