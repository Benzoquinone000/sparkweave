import { RagEvidenceChain } from "@/components/results/RagEvidenceChain";
import type { RagEvidence } from "@/lib/ragEvidence";
import type { RagSearchSource, RagSearchTestResult } from "@/lib/types";

import { RagAgenticTrace } from "./RagAgenticTrace";
import { RagSearchContextView, RagSearchSourcesView, RagSearchSummaryView } from "./RagSearchResultViews";
import type { ResultStatus } from "./RagSearchResultPanels";
import type { RagTestPanelView } from "./ragTestConfig";
import type { RagSearchRecovery, RagSearchRecoveryAction } from "./ragSearchStatus";

export function RagSearchTestPanelRoutes({
  panelView,
  result,
  resultStatus,
  recovery,
  chatHandoffHref,
  activeKb,
  sources,
  content,
  ragEvidence,
  onAction,
  onOpenAgentic,
  onOpenContext,
  onOpenSources,
}: {
  panelView: RagTestPanelView;
  result: RagSearchTestResult | null;
  resultStatus: ResultStatus | null;
  recovery: RagSearchRecovery | null;
  chatHandoffHref: string;
  activeKb: string;
  sources: RagSearchSource[];
  content: string;
  ragEvidence: RagEvidence | null;
  onAction: (action: RagSearchRecoveryAction) => void;
  onOpenAgentic: () => void;
  onOpenContext: () => void;
  onOpenSources: () => void;
}) {
  if (!result) return null;

  if (panelView === "summary") {
    return (
      <RagSearchSummaryView
        result={result}
        resultStatus={resultStatus}
        recovery={recovery}
        chatHandoffHref={chatHandoffHref}
        activeKb={activeKb}
        sources={sources}
        content={content}
        onAction={onAction}
        onOpenAgentic={onOpenAgentic}
        onOpenContext={onOpenContext}
        onOpenSources={onOpenSources}
      />
    );
  }

  if (panelView === "agentic") {
    return (
      <div className="mt-4" data-testid="knowledge-rag-test-agentic-page">
        {ragEvidence ? (
          <RagEvidenceChain evidence={ragEvidence} showRecoveryLink={false} />
        ) : (
          <RagAgenticTrace result={result} contentChars={content.length} sourceCount={sources.length} />
        )}
      </div>
    );
  }

  if (panelView === "context") {
    return <RagSearchContextView result={result} content={content} />;
  }

  if (panelView === "sources") {
    return <RagSearchSourcesView sources={sources} onAction={onAction} />;
  }

  return null;
}
