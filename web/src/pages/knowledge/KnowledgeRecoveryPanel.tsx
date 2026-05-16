import type { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, ClipboardList, Database, FileUp, FolderSync, RefreshCw, Search } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

import { KNOWLEDGE_ENTRY_ICON_CLASS, KNOWLEDGE_PANEL_CLASS } from "./styles";
import type { KnowledgeRecoveryActionId, KnowledgeRecoveryPlan } from "./recovery";

const actionIcon = {
  upload: <FileUp size={15} />,
  reindex: <RefreshCw size={15} />,
  diagnostics: <Database size={15} />,
  progress: <ClipboardList size={15} />,
  documents: <ClipboardList size={15} />,
  test: <Search size={15} />,
  folders: <FolderSync size={15} />,
} satisfies Record<KnowledgeRecoveryActionId, ReactNode>;

export function KnowledgeRecoveryPanel({
  visible,
  activeKb,
  plan,
  reindexing,
  diagnosing,
  onAction,
}: {
  visible: boolean;
  activeKb: string;
  plan: KnowledgeRecoveryPlan;
  reindexing: boolean;
  diagnosing: boolean;
  onAction: (action: KnowledgeRecoveryActionId) => void;
}) {
  if (!visible) return null;
  const isBusyAction =
    (plan.primaryAction.id === "reindex" && reindexing) ||
    (plan.primaryAction.id === "diagnostics" && diagnosing);

  return (
    <section className={`mt-4 ${KNOWLEDGE_PANEL_CLASS}`} data-testid="knowledge-recovery-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 gap-3">
          <div className={`${KNOWLEDGE_ENTRY_ICON_CLASS} ${plan.needsAttention ? "bg-tint-yellow" : "bg-tint-mint"}`}>
            {plan.needsAttention ? <AlertTriangle size={18} /> : <CheckCircle2 size={18} />}
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-semibold text-ink">修复向导</p>
              <Badge tone={plan.tone}>{plan.badge}</Badge>
            </div>
            <h2 className="mt-2 text-lg font-semibold text-ink">{plan.title}</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">{plan.summary}</p>
          </div>
        </div>
        <Badge tone={activeKb ? "brand" : "neutral"}>{activeKb || "未选择资料库"}</Badge>
      </div>

      <div className="mt-4 rounded-lg border border-line bg-canvas p-3">
        <p className="text-sm font-semibold text-ink">建议下一步</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button
            tone="primary"
            className="min-h-9 px-3 text-xs"
            disabled={!activeKb || isBusyAction}
            onClick={() => onAction(plan.primaryAction.id)}
            data-testid="knowledge-recovery-primary"
          >
            {isBusyAction ? <RefreshCw size={15} className="animate-spin" /> : actionIcon[plan.primaryAction.id]}
            {plan.primaryAction.label}
          </Button>
          {plan.secondaryActions.map((action) => {
            const busy = (action.id === "reindex" && reindexing) || (action.id === "diagnostics" && diagnosing);
            return (
              <Button
                key={action.id}
                tone="secondary"
                className="min-h-9 px-3 text-xs"
                disabled={!activeKb || busy}
                onClick={() => onAction(action.id)}
                data-testid={`knowledge-recovery-${action.id}`}
              >
                {busy ? <RefreshCw size={15} className="animate-spin" /> : actionIcon[action.id]}
                {action.label}
              </Button>
            );
          })}
        </div>
        <p className="mt-2 text-xs leading-5 text-slate-500">{plan.primaryAction.detail}</p>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        {plan.checks.map((check) => (
          <div key={check.label} className="rounded-lg border border-line bg-white p-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-semibold text-ink">{check.label}</p>
              <Badge tone={check.tone}>{check.tone === "success" ? "正常" : check.tone === "danger" ? "异常" : "查看"}</Badge>
            </div>
            <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-500">{check.detail}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
