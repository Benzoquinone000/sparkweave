import { Badge } from "@/components/ui/Badge";
import type { RagSearchSource, RagSearchTestResult } from "@/lib/types";

import { knowledgeProviderLabel } from "./format";
import {
  RagSearchChatHandoffCard,
  RagSearchRecoveryCard,
  RagSearchResultNavigationCards,
  RagSearchResultSummaryCard,
  RagSearchSourcesList,
  type ResultStatus,
} from "./RagSearchResultPanels";
import type { RagSearchRecovery, RagSearchRecoveryAction } from "./ragSearchStatus";

export function RagSearchSummaryView({
  result,
  resultStatus,
  recovery,
  chatHandoffHref,
  activeKb,
  sources,
  content,
  onAction,
  onOpenAgentic,
  onOpenContext,
  onOpenSources,
}: {
  result: RagSearchTestResult;
  resultStatus: ResultStatus | null;
  recovery: RagSearchRecovery | null;
  chatHandoffHref: string;
  activeKb: string;
  sources: RagSearchSource[];
  content: string;
  onAction: (action: RagSearchRecoveryAction) => void;
  onOpenAgentic: () => void;
  onOpenContext: () => void;
  onOpenSources: () => void;
}) {
  return (
    <div className="mt-4 grid gap-4">
      <RagSearchResultSummaryCard
        result={result}
        resultStatus={resultStatus}
        sources={sources}
        content={content}
      />
      {recovery ? <RagSearchRecoveryCard recovery={recovery} onAction={onAction} /> : null}
      {chatHandoffHref ? (
        <RagSearchChatHandoffCard
          href={chatHandoffHref}
          weak={resultStatus?.tone === "warning"}
          sourceCount={sources.length}
          activeKb={activeKb}
        />
      ) : null}
      <RagSearchResultNavigationCards
        onOpenAgentic={onOpenAgentic}
        onOpenContext={onOpenContext}
        onOpenSources={onOpenSources}
      />
    </div>
  );
}

export function RagSearchContextView({
  result,
  content,
}: {
  result: RagSearchTestResult;
  content: string;
}) {
  return (
    <div className="mt-4 rounded-lg border border-line bg-canvas p-3" data-testid="knowledge-rag-test-context-page">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold text-ink">回答材料</p>
        <div className="flex flex-wrap gap-2">
          <Badge tone="neutral">{knowledgeProviderLabel(result.provider)}</Badge>
          <Badge tone="neutral">{String(result.retrieval_profile || "auto")}</Badge>
          <Badge tone={result.success === false ? "warning" : "success"}>
            {result.success === false ? "查找失败" : "已找到来源"}
          </Badge>
        </div>
      </div>
      <p className="mt-3 max-h-[520px] overflow-y-auto whitespace-pre-wrap rounded-lg bg-white p-3 text-sm leading-6 text-slate-700">
        {content || result.error || "没有可预览的回答材料。"}
      </p>
    </div>
  );
}

export function RagSearchSourcesView({
  sources,
  onAction,
}: {
  sources: RagSearchSource[];
  onAction: (action: RagSearchRecoveryAction) => void;
}) {
  return (
    <div className="mt-4 grid gap-3" data-testid="knowledge-rag-test-sources-page">
      <RagSearchSourcesList sources={sources} onAction={onAction} />
    </div>
  );
}
