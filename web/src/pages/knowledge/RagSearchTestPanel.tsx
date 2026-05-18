import { useState } from "react";

import { buildRagChatHandoffHref } from "@/lib/ragHandoff";
import { buildRagEvidenceFromResult } from "@/lib/ragEvidence";
import type { RagSearchTestResult } from "@/lib/types";

import { formatErrorMessage } from "./format";
import type { RagTestPanelView } from "./ragTestConfig";
import {
  buildRagSearchRecovery,
  describeRagSearchStatus,
  type RagSearchRecoveryAction,
} from "./ragSearchStatus";
import { RagSearchSetupForm } from "./RagSearchSetupForm";
import { RagSearchTestPanelHeader } from "./RagSearchTestPanelHeader";
import { RagSearchTestPanelRoutes } from "./RagSearchTestPanelRoutes";
import type { RagSearchTestPanelProps } from "./RagSearchTestPanelTypes";
import { KNOWLEDGE_PANEL_CLASS } from "./styles";

export function RagSearchTestPanel({
  activeKb,
  query,
  profile,
  mode,
  agentic,
  topK,
  agenticMaxContextChars,
  agenticMaxSources,
  agenticMinRelevantCoverage,
  presetId,
  result,
  error,
  running,
  handoff,
  onQueryChange,
  onProfileChange,
  onModeChange,
  onAgenticChange,
  onTopKChange,
  onAgenticMaxContextCharsChange,
  onAgenticMaxSourcesChange,
  onAgenticMinRelevantCoverageChange,
  onPresetApply,
  onRun,
  onHandoffDismiss,
  onOpenDiagnostics,
}: RagSearchTestPanelProps) {
  const sources = result?.sources ?? [];
  const content = result?.content || result?.answer || "";
  const ragEvidence = result ? buildRagEvidenceFromResult(result) : null;
  const [panelState, setPanelState] = useState<{ view: RagTestPanelView; result: RagSearchTestResult | null }>({
    view: "setup",
    result: null,
  });
  const panelView = result && panelState.result !== result ? "summary" : panelState.view;
  const setPanelView = (view: RagTestPanelView) => setPanelState({ view, result });
  const resultStatus = result ? describeRagSearchStatus(result, sources.length, content.length) : null;
  const recovery = result ? buildRagSearchRecovery(result, sources.length, content.length) : null;
  const chatHandoffHref =
    result && result.success !== false && activeKb && query.trim() && sources.length
      ? buildRagChatHandoffHref({
          activeKb,
          query,
          profile,
          mode,
          agentic,
          topK,
          agenticMaxContextChars,
          agenticMaxSources,
          agenticMinRelevantCoverage,
        })
      : "";
  const openSetup = () => setPanelView("setup");
  const applyDeepSearchPreset = () => {
    onPresetApply("deep");
    setPanelView("setup");
  };
  const runRecoveryAction = (action: RagSearchRecoveryAction) => {
    if (action === "deep") {
      applyDeepSearchPreset();
      return;
    }
    if (action === "setup") {
      openSetup();
      return;
    }
    if (action === "diagnostics") {
      onOpenDiagnostics?.();
      return;
    }
    setPanelView(action);
  };

  const showResultNavigation = Boolean(result) && panelView !== "setup";
  return (
    <section className={`mt-4 ${KNOWLEDGE_PANEL_CLASS}`} data-testid="knowledge-rag-test-panel">
      <RagSearchTestPanelHeader
        panelView={panelView}
        showResultNavigation={showResultNavigation}
        resultStatus={result ? resultStatus : null}
        sourceCount={sources.length}
        onBackToSummary={() => setPanelView("summary")}
        onOpenSetup={() => setPanelView("setup")}
      />
      {panelView === "setup" ? (
        <RagSearchSetupForm
          activeKb={activeKb}
          query={query}
          profile={profile}
          mode={mode}
          agentic={agentic}
          topK={topK}
          agenticMaxContextChars={agenticMaxContextChars}
          agenticMaxSources={agenticMaxSources}
          agenticMinRelevantCoverage={agenticMinRelevantCoverage}
          presetId={presetId}
          result={result}
          running={running}
          handoff={handoff}
          onQueryChange={onQueryChange}
          onProfileChange={onProfileChange}
          onModeChange={onModeChange}
          onAgenticChange={onAgenticChange}
          onTopKChange={onTopKChange}
          onAgenticMaxContextCharsChange={onAgenticMaxContextCharsChange}
          onAgenticMaxSourcesChange={onAgenticMaxSourcesChange}
          onAgenticMinRelevantCoverageChange={onAgenticMinRelevantCoverageChange}
          onPresetApply={onPresetApply}
          onRun={onRun}
          onHandoffDismiss={onHandoffDismiss}
          onShowLastResult={() => setPanelView("summary")}
        />
      ) : null}
      {error ? (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm leading-6 text-red-700">
          {formatErrorMessage(error)}
        </div>
      ) : null}
      <RagSearchTestPanelRoutes
        panelView={panelView}
        result={result}
        resultStatus={resultStatus}
        recovery={recovery}
        chatHandoffHref={chatHandoffHref}
        activeKb={activeKb}
        sources={sources}
        content={content}
        ragEvidence={ragEvidence}
        onAction={runRecoveryAction}
        onOpenAgentic={() => setPanelView("agentic")}
        onOpenContext={() => setPanelView("context")}
        onOpenSources={() => setPanelView("sources")}
      />
    </section>
  );
}
