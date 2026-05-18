import { Badge } from "@/components/ui/Badge";
import type { RagSearchSource, RagSearchTestResult } from "@/lib/types";

import { ConfigFact } from "./ConfigFact";
import { knowledgeProviderLabel } from "./format";

export type ResultStatus = {
  tone?: "neutral" | "success" | "warning" | "danger" | "brand";
  label?: string;
};

export function RagSearchResultSummaryCard({
  result,
  resultStatus,
  sources,
  content,
}: {
  result: RagSearchTestResult;
  resultStatus: ResultStatus | null;
  sources: RagSearchSource[];
  content: string;
}) {
  return (
    <div className="rounded-lg border border-line bg-canvas p-3" data-testid="knowledge-rag-test-summary">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold text-ink">结果概览</p>
        <Badge tone={resultStatus?.tone ?? "neutral"}>{resultStatus?.label ?? "检索完成"}</Badge>
      </div>
      <div className="mt-3 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
        <ConfigFact label="检索引擎" value={knowledgeProviderLabel(result.provider)} />
        <ConfigFact label="检索画像" value={String(result.retrieval_profile || "auto")} />
        <ConfigFact label="证据来源" value={String(result.source_count ?? sources.length)} />
        <ConfigFact label="上下文长度" value={`${content.length} 字`} />
      </div>
      {result.error ? <p className="mt-3 text-xs leading-5 text-amber-700">{result.error}</p> : null}
    </div>
  );
}
