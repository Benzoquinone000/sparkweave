import { KnowledgeActiveOverviewPanel } from "./KnowledgeActiveOverviewPanel";
import type { KnowledgeWorkspaceContentProps } from "./KnowledgeWorkspaceContentTypes";
import { KnowledgeWorkspaceRoutePanels } from "./KnowledgeWorkspaceRoutePanels";

export function KnowledgeWorkspaceContent({
  activeKb,
  workspace,
  overview,
  diagnostics,
  recoveryPlan,
  quality,
  ragTest,
  documents,
  upload,
  settings,
  folders,
  progress,
  onNavigate,
  onRecoveryAction,
}: KnowledgeWorkspaceContentProps) {
  return (
    <>
      <KnowledgeActiveOverviewPanel
        activeKb={activeKb}
        activeStatus={overview.activeStatus}
        activeFileCount={overview.activeFileCount}
        activeDocumentCount={overview.activeDocumentCount}
        activeSearchLabel={overview.activeSearchLabel}
        activePath={overview.activePath}
        workspace={workspace}
        progressMessage={overview.progressMessage}
        progressPercent={overview.progressPercent}
        progressStage={overview.progressStage}
        wsStatus={overview.wsStatus}
        taskActive={overview.taskActive}
        documentCount={overview.documentCount}
        vectorCount={overview.vectorCount}
        diagnosticStatus={overview.diagnosticStatus}
        recoveryBadge={overview.recoveryBadge}
        recoveryNeedsAttention={overview.recoveryNeedsAttention}
        evaluationAvailable={overview.evaluationAvailable}
        testSourceCount={overview.testSourceCount}
        folderCount={overview.folderCount}
        summaryItems={overview.summaryItems}
        reindexing={overview.reindexing}
        diagnosing={overview.diagnosing}
        defaultActive={overview.defaultActive}
        settingDefault={overview.settingDefault}
        removing={overview.removing}
        onReindex={overview.onReindex}
        onDiagnose={overview.onDiagnose}
        onSetDefault={overview.onSetDefault}
        onDelete={overview.onDelete}
        onNavigate={onNavigate}
      />

      <KnowledgeWorkspaceRoutePanels
        activeKb={activeKb}
        workspace={workspace}
        overview={overview}
        diagnostics={diagnostics}
        recoveryPlan={recoveryPlan}
        quality={quality}
        ragTest={ragTest}
        documents={documents}
        upload={upload}
        settings={settings}
        folders={folders}
        progress={progress}
        onNavigate={onNavigate}
        onRecoveryAction={onRecoveryAction}
      />
    </>
  );
}
