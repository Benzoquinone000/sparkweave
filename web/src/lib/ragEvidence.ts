import type { StreamEvent } from "@/lib/types";

export type RagSubQuery = {
  index: number;
  query: string;
  purpose: string;
  status?: string;
  action?: string;
  error?: string;
  sourceCount?: number;
  contentChars?: number;
  success?: boolean;
  relevant?: boolean;
  relevanceScore?: number;
  matchedTerms: string[];
  repairAttempted?: boolean;
  repaired?: boolean;
};

export type RagQualityCheck = {
  code: string;
  status: string;
  observed?: number | string;
  threshold?: number | string;
  message: string;
};

export type RagSource = {
  title: string;
  source: string;
  content: string;
  chunkId?: string;
  page?: string;
  score?: string;
  evidenceReason?: string;
  matchedKeywords: string[];
  subquery?: string;
  subqueryIndex?: number;
  subqueryPurpose?: string;
};

export type RagEvidence = {
  query: string;
  kbName: string;
  provider: string;
  agentic: boolean;
  agenticFallback: boolean;
  agenticRepaired: boolean;
  explanationDecision: string;
  explanationSummary: string;
  explanationNextAction: string;
  planMode: string;
  planReason: string;
  activityRecommendation: string;
  qualityStatus: string;
  qualityScore?: number;
  coverageRatio?: number;
  relevantCoverageRatio?: number;
  qualityReasons: string[];
  contextChars?: number;
  contextMaxChars?: number;
  contextTruncated: boolean;
  repairStrategy: string;
  retrievalProfile: string;
  retrievalPolicyReason: string;
  retrievalMode: string;
  queryTransform: string;
  queryTransformApplied: boolean;
  qualityChecks: RagQualityCheck[];
  subqueries: RagSubQuery[];
  sources: RagSource[];
  sourceCount: number;
};

type RagCandidate = {
  metadata: Record<string, unknown>;
  sources: Record<string, unknown>[];
};

export function extractRagEvidence(events: StreamEvent[]): RagEvidence | null {
  const candidates: RagCandidate[] = [];

  for (const event of events) {
    const eventMetadata = event.metadata ?? {};

    if (event.type === "tool_result" && isRagLikeRecord(eventMetadata)) {
      candidates.push({
        metadata: asRecord(eventMetadata.result_metadata) ?? eventMetadata,
        sources: recordArray(eventMetadata.sources),
      });
    }

    if (event.type !== "result") continue;
    const traces = recordArray(eventMetadata.tool_traces);
    traces.forEach((trace) => {
      const metadata = asRecord(trace.metadata) ?? {};
      const sources = recordArray(trace.sources).length ? recordArray(trace.sources) : recordArray(metadata.sources);
      if (isRagTrace(trace, metadata, sources)) {
        candidates.push({ metadata, sources });
      }
    });
  }

  if (!candidates.length) return null;
  const best = candidates
    .map((candidate) => ({ candidate, score: candidateScore(candidate) }))
    .sort((left, right) => right.score - left.score)[0]?.candidate;
  if (!best) return null;

  return buildRagEvidenceFromCandidate(best);
}

export function buildRagEvidenceFromResult(result: Record<string, unknown>): RagEvidence | null {
  return buildRagEvidenceFromCandidate({
    metadata: result,
    sources: recordArray(result.sources),
  });
}

function buildRagEvidenceFromCandidate(best: RagCandidate): RagEvidence | null {
  const plan = asRecord(best.metadata.query_plan) ?? asRecord(best.metadata.failed_query_plan);
  const explanation = asRecord(best.metadata.agentic_explanation);
  const userFacing = asRecord(explanation?.user_facing);
  const explanationPlan = asRecord(explanation?.plan);
  const explanationEvidence = asRecord(explanation?.evidence);
  const activityPlan = asRecord(best.metadata.agentic_activity_plan);
  const quality = asRecord(best.metadata.agentic_quality);
  const repair = asRecord(best.metadata.agentic_repair);
  const contextPack = asRecord(best.metadata.agentic_context_pack);
  const subqueries = extractSubqueries(plan, best.metadata, explanation);
  const sources = normalizeSources(best.sources.length ? best.sources : recordArray(best.metadata.sources));
  const explanationDecision = textValue(explanation?.decision);
  const agentic = best.metadata.agentic_rag === true || subqueries.length > 1;
  const query = textValue(best.metadata.query) || textValue(plan?.original_query) || textValue(plan?.query);
  const sourceCount = numberValue(explanationEvidence?.source_count) ?? numberValue(best.metadata.source_count) ?? sources.length;

  if (!query && !sources.length && !subqueries.length) return null;

  return {
    query,
    kbName: textValue(best.metadata.kb_name),
    provider: textValue(best.metadata.provider),
    agentic,
    agenticFallback: best.metadata.agentic_fallback === true || explanationDecision === "single_search_fallback",
    agenticRepaired: best.metadata.agentic_repaired === true || explanationDecision === "subquery_repair" || Boolean(repair),
    explanationDecision,
    explanationSummary: textValue(userFacing?.summary) || textValue(explanation?.summary),
    explanationNextAction: textValue(userFacing?.next_action) || textValue(explanation?.next_action),
    planMode: textValue(explanationPlan?.mode) || textValue(plan?.agentic_mode) || textValue(plan?.mode),
    planReason: textValue(userFacing?.trigger_reason) || textValue(explanationPlan?.reason) || textValue(plan?.agentic_reason) || textValue(plan?.reason),
    activityRecommendation: textValue(userFacing?.next_action) || textValue(explanation?.next_action) || textValue(activityPlan?.recommendation),
    qualityStatus: textValue(explanationEvidence?.quality_status) || textValue(quality?.status),
    qualityScore: numberValue(explanationEvidence?.quality_score) ?? numberValue(quality?.quality_score),
    coverageRatio: numberValue(explanationEvidence?.coverage_ratio) ?? numberValue(quality?.coverage_ratio),
    relevantCoverageRatio: numberValue(explanationEvidence?.relevant_coverage_ratio) ?? numberValue(quality?.relevant_coverage_ratio),
    qualityReasons: stringArray(explanationEvidence?.reasons).length ? stringArray(explanationEvidence?.reasons) : stringArray(quality?.reasons),
    contextChars: numberValue(contextPack?.context_chars) ?? numberValue(explanationEvidence?.context_chars),
    contextMaxChars: numberValue(contextPack?.max_context_chars),
    contextTruncated: contextPack?.truncated === true,
    repairStrategy: textValue(repair?.strategy),
    retrievalProfile: textValue(best.metadata.retrieval_profile),
    retrievalPolicyReason: textValue(best.metadata.retrieval_policy_reason),
    retrievalMode: textValue(best.metadata.retrieval_mode) || textValue(best.metadata.mode),
    queryTransform: textValue(best.metadata.query_transform),
    queryTransformApplied: best.metadata.query_transform_applied === true,
    qualityChecks: normalizeQualityChecks(recordArray(explanation?.quality_checks)),
    subqueries,
    sources,
    sourceCount,
  };
}

function isRagTrace(trace: Record<string, unknown>, metadata: Record<string, unknown>, sources: Record<string, unknown>[]) {
  const name = textValue(trace.name) || textValue(metadata.tool_name) || textValue(metadata.tool);
  if (name === "rag") return true;
  if ("query_plan" in metadata || "agentic_rag" in metadata || "context_pack" in metadata) return true;
  return sources.some((source) => textValue(source.type) === "rag" || Boolean(source.subquery));
}

function isRagLikeRecord(record: Record<string, unknown>) {
  const tool = textValue(record.tool_name) || textValue(record.tool);
  if (tool === "rag") return true;
  if ("query_plan" in record || "agentic_rag" in record) return true;
  return recordArray(record.sources).some((source) => textValue(source.type) === "rag" || Boolean(source.subquery));
}

function candidateScore(candidate: RagCandidate) {
  const metadata = candidate.metadata;
  const plan = asRecord(metadata.query_plan) ?? asRecord(metadata.failed_query_plan);
  return (
    (metadata.agentic_rag === true ? 50 : 0) +
    (metadata.agentic_repaired === true ? 12 : 0) +
    (metadata.agentic_fallback === true ? 8 : 0) +
    recordArray(plan?.subqueries).length * 10 +
    candidate.sources.length * 2 +
    ("agentic_explanation" in metadata ? 16 : 0) +
    ("context_pack" in metadata ? 5 : 0)
  );
}

function extractSubqueries(
  plan: Record<string, unknown> | null,
  metadata: Record<string, unknown>,
  explanation: Record<string, unknown> | null,
) {
  const explanationSteps = recordArray(explanation?.steps);
  if (explanationSteps.length) {
    return explanationSteps
      .map((item, index): RagSubQuery | null => {
        const query = textValue(item.query);
        if (!query) return null;
        return normalizeSubquery({
          index: numberValue(item.index) ?? index + 1,
          query,
          purpose: textValue(item.purpose) || "补充查找视角",
          result: item,
        });
      })
      .filter((item): item is RagSubQuery => Boolean(item));
  }

  const planned = recordArray(plan?.subqueries);
  const results = recordArray(metadata.subquery_results);
  const resultByQuery = new Map(results.map((item) => [textValue(item.query), item]));

  const subqueries = planned
    .map((item, index): RagSubQuery | null => {
      const query = textValue(item.query);
      if (!query) return null;
      const result = resultByQuery.get(query) ?? results[index] ?? {};
      return normalizeSubquery({
        index: numberValue(item.index) ?? index + 1,
        query,
        purpose: textValue(item.purpose) || "补充查找视角",
        result,
      });
    })
    .filter((item): item is RagSubQuery => Boolean(item));

  if (subqueries.length) return subqueries;

  return results
    .map((item, index): RagSubQuery | null => {
      const query = textValue(item.query);
      if (!query) return null;
      return normalizeSubquery({
        index: index + 1,
        query,
        purpose: textValue(item.purpose) || "分路查找",
        result: item,
      });
    })
    .filter((item): item is RagSubQuery => Boolean(item));
}

function normalizeSubquery({
  index,
  query,
  purpose,
  result,
}: {
  index: number;
  query: string;
  purpose: string;
  result: Record<string, unknown>;
}): RagSubQuery {
  return {
    index,
    query,
    purpose,
    status: textValue(result.status),
    action: textValue(result.action),
    error: textValue(result.error),
    sourceCount: numberValue(result.source_count),
    contentChars: numberValue(result.content_chars),
    success: typeof result.success === "boolean" ? result.success : undefined,
    relevant: typeof result.relevant === "boolean" ? result.relevant : undefined,
    relevanceScore: numberValue(result.relevance_score),
    matchedTerms: stringArray(result.matched_terms),
    repairAttempted: result.repair_attempted === true,
    repaired: result.repaired === true,
  };
}

function normalizeQualityChecks(checks: Record<string, unknown>[]): RagQualityCheck[] {
  return checks
    .map((check): RagQualityCheck | null => {
      const code = textValue(check.code);
      if (!code) return null;
      return {
        code,
        status: textValue(check.status),
        observed: scalarValue(check.observed),
        threshold: scalarValue(check.threshold),
        message: textValue(check.message),
      };
    })
    .filter((item): item is RagQualityCheck => Boolean(item));
}

function normalizeSources(rawSources: Record<string, unknown>[]) {
  return rawSources
    .map((source): RagSource => {
      const matchedKeywords = stringArray(source.matched_keywords);
      return {
        title: textValue(source.title) || textValue(source.file_name) || "资料片段",
        source: textValue(source.source) || textValue(source.file_path) || textValue(source.url),
        content: textValue(source.content) || textValue(source.text) || textValue(source.snippet),
        chunkId: textValue(source.chunk_id) || textValue(source.id),
        page: textValue(source.page),
        score: textValue(source.score),
        evidenceReason: textValue(source.evidence_reason),
        matchedKeywords,
        subquery: textValue(source.subquery),
        subqueryIndex: numberValue(source.subquery_index),
        subqueryPurpose: textValue(source.subquery_purpose),
      };
    })
    .filter((source) => source.title || source.source || source.content)
    .filter(dedupeSource);
}

function dedupeSource(source: RagSource, index: number, sources: RagSource[]) {
  const key = sourceDedupKey(source);
  if (!key) return true;
  return sources.findIndex((item) => sourceDedupKey(item) === key) === index;
}

function sourceDedupKey(source: RagSource) {
  return [source.chunkId, source.source, source.page, source.title, source.content.slice(0, 120)]
    .filter(Boolean)
    .join("|");
}

function recordArray(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object" && !Array.isArray(item));
}

function stringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item).trim()).filter(Boolean);
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function textValue(value: unknown) {
  if (typeof value === "string") return value.trim();
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return "";
}

function numberValue(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value !== "string") return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function scalarValue(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) return value.trim();
  return undefined;
}
