import { lazy, Suspense } from "react";

import type { KnowledgeWorkspaceRoutePanelsProps } from "./KnowledgeWorkspaceContentTypes";

const KnowledgeDiagnosticsPanel = lazy(() =>
  import("./KnowledgeDiagnosticsPanel").then((module) => ({ default: module.KnowledgeDiagnosticsPanel })),
);
const KnowledgeRecoveryPanel = lazy(() =>
  import("./KnowledgeRecoveryPanel").then((module) => ({ default: module.KnowledgeRecoveryPanel })),
);
const RagEvaluationCard = lazy(() =>
  import("./RagEvaluationCard").then((module) => ({ default: module.RagEvaluationCard })),
);
const RagSearchTestPanel = lazy(() =>
  import("./RagSearchTestPanel").then((module) => ({ default: module.RagSearchTestPanel })),
);

export function KnowledgeWorkspaceRagRoutePanels({
  activeKb,
  workspace,
  overview,
  diagnostics,
  recoveryPlan,
  quality,
  ragTest,
  onRecoveryAction,
}: KnowledgeWorkspaceRoutePanelsProps) {
  return (
    <>
      {workspace === "diagnostics" ? (
        <Suspense fallback={<RagRouteLoading label="正在准备连接检查" />}>
          <KnowledgeDiagnosticsPanel
            activeKb={activeKb}
            report={diagnostics.report}
            error={diagnostics.error}
            fetching={diagnostics.fetching}
            visible={Boolean(
              (diagnostics.report ||
                diagnostics.error ||
                diagnostics.fetching ||
                diagnostics.preflight ||
                diagnostics.preflightError ||
                diagnostics.preflightFetching) &&
                activeKb,
            )}
            preflight={diagnostics.preflight}
            preflightError={diagnostics.preflightError}
            preflightFetching={diagnostics.preflightFetching}
            reindexing={diagnostics.reindexing}
            onRefresh={diagnostics.onRefresh}
            onOpenRecovery={diagnostics.onOpenRecovery}
            onOpenTest={diagnostics.onOpenTest}
            onReindex={diagnostics.onReindex}
          />
        </Suspense>
      ) : null}

      {activeKb && workspace === "recovery" ? (
        <Suspense fallback={<RagRouteLoading label="正在准备整理向导" />}>
          <KnowledgeRecoveryPanel
            visible
            activeKb={activeKb}
            plan={recoveryPlan}
            reindexing={overview.reindexing}
            diagnosing={overview.diagnosing}
            onAction={onRecoveryAction}
          />
        </Suspense>
      ) : null}

      {activeKb && workspace === "quality" ? (
        <Suspense fallback={<RagRouteLoading label="正在准备来源检查" />}>
          <RagEvaluationCard
            report={quality.report}
            available={quality.available}
            loading={quality.loading}
            error={quality.error}
            onRefresh={quality.onRefresh}
            preset={quality.preset}
            onPresetChange={quality.onPresetChange}
            onRun={quality.onRun}
            running={quality.running}
          />
        </Suspense>
      ) : null}

      {activeKb && workspace === "test" ? (
        <Suspense fallback={<RagRouteLoading label="正在准备资料试问" />}>
          <RagSearchTestPanel
            activeKb={activeKb}
            query={ragTest.query}
            profile={ragTest.profile}
            mode={ragTest.mode}
            agentic={ragTest.agentic}
            topK={ragTest.topK}
            agenticMaxContextChars={ragTest.agenticMaxContextChars}
            agenticMaxSources={ragTest.agenticMaxSources}
            agenticMinRelevantCoverage={ragTest.agenticMinRelevantCoverage}
            presetId={ragTest.presetId}
            result={ragTest.result}
            error={ragTest.error}
            running={ragTest.running}
            handoff={ragTest.handoff}
            onQueryChange={ragTest.onQueryChange}
            onProfileChange={ragTest.onProfileChange}
            onModeChange={ragTest.onModeChange}
            onAgenticChange={ragTest.onAgenticChange}
            onTopKChange={ragTest.onTopKChange}
            onAgenticMaxContextCharsChange={ragTest.onAgenticMaxContextCharsChange}
            onAgenticMaxSourcesChange={ragTest.onAgenticMaxSourcesChange}
            onAgenticMinRelevantCoverageChange={ragTest.onAgenticMinRelevantCoverageChange}
            onPresetApply={ragTest.onPresetApply}
            onRun={ragTest.onRun}
            onHandoffDismiss={ragTest.onHandoffDismiss}
            onOpenDiagnostics={ragTest.onOpenDiagnostics}
          />
        </Suspense>
      ) : null}
    </>
  );
}

function RagRouteLoading({ label }: { label: string }) {
  return (
    <section className="rounded-lg border border-line bg-white/90 p-4">
      <p className="text-sm font-semibold text-ink">{label}</p>
      <div className="mt-3 space-y-2">
        <span className="block h-3 w-44 max-w-full rounded bg-slate-100" />
        <span className="block h-14 rounded bg-slate-100/80" />
      </div>
    </section>
  );
}
