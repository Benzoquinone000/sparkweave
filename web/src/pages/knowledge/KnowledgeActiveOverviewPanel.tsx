import {
  KnowledgeIndexStatusCard,
  KnowledgeOverviewFacts,
  KnowledgeOverviewHeader,
  KnowledgeOverviewSummaryPanel,
  KnowledgeStartPanel,
  type KnowledgeSummaryItem,
} from "./KnowledgeActiveOverviewPanels";
import { buildKnowledgeNextStep } from "./KnowledgeNextStepModel";
import { KnowledgeWorkspaceNav } from "./KnowledgeWorkspaceNav";
import type { KnowledgeWsStatus } from "./progressFormat";
import { KNOWLEDGE_PANEL_LOOSE_CLASS } from "./styles";
import type { KnowledgeWorkspace } from "./types";

export function KnowledgeActiveOverviewPanel({
  activeKb,
  activeStatus,
  activeFileCount,
  activeDocumentCount,
  activeSearchLabel,
  activePath,
  workspace,
  progressMessage,
  progressPercent,
  progressStage,
  wsStatus,
  taskActive,
  documentCount,
  vectorCount,
  diagnosticStatus,
  recoveryBadge,
  recoveryNeedsAttention,
  evaluationAvailable,
  testSourceCount,
  folderCount,
  summaryItems,
  reindexing,
  diagnosing,
  defaultActive,
  settingDefault,
  removing,
  onReindex,
  onDiagnose,
  onSetDefault,
  onDelete,
  onNavigate,
}: {
  activeKb: string;
  activeStatus: string;
  activeFileCount?: number;
  activeDocumentCount?: number;
  activeSearchLabel: string;
  activePath: string;
  workspace: KnowledgeWorkspace;
  progressMessage: string;
  progressPercent: number;
  progressStage: string;
  wsStatus: KnowledgeWsStatus;
  taskActive: boolean;
  documentCount: number | string | null | undefined;
  vectorCount: number | string | null | undefined;
  diagnosticStatus: string;
  recoveryBadge: string;
  recoveryNeedsAttention: boolean;
  evaluationAvailable: boolean;
  testSourceCount?: number | string | null;
  folderCount: number;
  summaryItems: KnowledgeSummaryItem[];
  reindexing: boolean;
  diagnosing: boolean;
  defaultActive: boolean;
  settingDefault: boolean;
  removing: boolean;
  onReindex: () => void;
  onDiagnose: () => void;
  onSetDefault: () => void;
  onDelete: () => void;
  onNavigate: (workspace: KnowledgeWorkspace) => void;
}) {
  const nextStep = activeKb
    ? buildKnowledgeNextStep({
        documentCount: documentCount ?? activeDocumentCount,
        vectorCount,
        progressPercent,
        progressStage,
        taskActive,
        recoveryNeedsAttention,
        testSourceCount,
      })
    : null;

  return (
    <section className={KNOWLEDGE_PANEL_LOOSE_CLASS}>
      <KnowledgeOverviewHeader
        activeKb={activeKb}
        reindexing={reindexing}
        diagnosing={diagnosing}
        defaultActive={defaultActive}
        settingDefault={settingDefault}
        removing={removing}
        onReindex={onReindex}
        onDiagnose={onDiagnose}
        onSetDefault={onSetDefault}
        onDelete={onDelete}
      />

      {workspace === "overview" ? (
        <KnowledgeStartPanel
          activeKb={activeKb}
          nextStep={nextStep}
          documentCount={documentCount ?? activeDocumentCount}
          vectorCount={vectorCount}
          progressMessage={progressMessage}
          progressPercent={progressPercent}
          taskActive={taskActive}
          recoveryNeedsAttention={recoveryNeedsAttention}
          onNavigate={onNavigate}
        />
      ) : (
        <>
          <KnowledgeOverviewFacts
            activeStatus={activeStatus}
            activeFileCount={activeFileCount}
            activeDocumentCount={activeDocumentCount}
            activeSearchLabel={activeSearchLabel}
          />

          <KnowledgeIndexStatusCard
            progressMessage={progressMessage}
            progressPercent={progressPercent}
            progressStage={progressStage}
            wsStatus={wsStatus}
            taskActive={taskActive}
          />
        </>
      )}

      {activeKb ? <p className="mt-4 truncate text-xs text-slate-500">路径：{activePath}</p> : null}

      {activeKb ? (
        <KnowledgeWorkspaceNav
          active={workspace}
          documentCount={documentCount}
          vectorCount={vectorCount}
          diagnosticStatus={diagnosticStatus}
          recoveryBadge={recoveryBadge}
          recoveryNeedsAttention={recoveryNeedsAttention}
          evaluationAvailable={evaluationAvailable}
          testSourceCount={testSourceCount}
          folderCount={folderCount}
          taskActive={taskActive}
          onNavigate={onNavigate}
        />
      ) : null}

      <KnowledgeOverviewSummaryPanel summaryItems={summaryItems} workspace={workspace} />
    </section>
  );
}
