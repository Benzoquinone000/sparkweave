import { ChevronLeft } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

import { KNOWLEDGE_ENTRY_ICON_CLASS, KNOWLEDGE_PANEL_COMPACT_CLASS } from "./styles";
import type { KnowledgeWorkspace } from "./types";
import { buildKnowledgeWorkspaceNavItems } from "./KnowledgeWorkspaceNavItems";

export function KnowledgeWorkspaceNav({
  active,
  documentCount,
  vectorCount,
  diagnosticStatus,
  recoveryBadge,
  recoveryNeedsAttention,
  evaluationAvailable,
  testSourceCount,
  folderCount,
  taskActive,
  onNavigate,
}: {
  active: KnowledgeWorkspace;
  documentCount: number | string | null | undefined;
  vectorCount: number | string | null | undefined;
  diagnosticStatus: string;
  recoveryBadge: string;
  recoveryNeedsAttention: boolean;
  evaluationAvailable: boolean;
  testSourceCount?: number | string | null;
  folderCount: number;
  taskActive: boolean;
  onNavigate: (workspace: KnowledgeWorkspace) => void;
}) {
  const items = buildKnowledgeWorkspaceNavItems({
    documentCount,
    vectorCount,
    diagnosticStatus,
    recoveryBadge,
    recoveryNeedsAttention,
    evaluationAvailable,
    testSourceCount,
    folderCount,
    taskActive,
  });

  const activeItem = items.find((item) => item.id === active) ?? items[0];

  return (
    <section className={`mt-4 ${KNOWLEDGE_PANEL_COMPACT_CLASS}`} data-testid="knowledge-workspace-nav">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-ink">{activeItem.title}</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">{activeItem.description}</p>
        </div>
        {active !== "overview" ? (
          <Button
            tone="secondary"
            className="min-h-9 px-3 text-xs"
            onClick={() => onNavigate("overview")}
            data-testid="knowledge-workspace-back"
          >
            <ChevronLeft size={15} />
            返回概览
          </Button>
        ) : null}
      </div>
      <div className={active === "overview" ? "mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4" : "mt-3 flex flex-wrap gap-2"}>
        {items.map((item) => {
          const selected = item.id === active;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onNavigate(item.id)}
              className={
                active === "overview"
                  ? `rounded-lg border p-3 text-left transition ${
                      selected ? "border-brand-purple-300 bg-tint-lavender" : "border-line bg-surface hover:border-brand-purple-300 hover:bg-white"
                    }`
                  : `inline-flex min-h-9 items-center gap-2 rounded-lg border px-3 text-xs transition ${
                      selected ? "border-brand-purple-300 bg-tint-lavender text-brand-purple" : "border-line bg-white text-slate-600 hover:border-brand-purple-300"
                    }`
              }
              data-testid={`knowledge-workspace-${item.id}`}
            >
              <span className={active === "overview" ? `${KNOWLEDGE_ENTRY_ICON_CLASS} ${item.accent}` : "text-brand-purple"}>
                {item.icon}
              </span>
              <span className="min-w-0">
                <span className="block truncate font-semibold text-ink">{item.title}</span>
                {active === "overview" ? <span className="mt-1 block text-xs leading-5 text-slate-500">{item.description}</span> : null}
              </span>
              <Badge tone={selected ? "brand" : item.tone}>{item.badge}</Badge>
            </button>
          );
        })}
      </div>
      {active === "overview" && typeof vectorCount !== "undefined" && vectorCount !== null ? (
        <p className="mt-3 text-xs leading-5 text-slate-500">当前引用索引可见 {String(vectorCount)} 条片段；进入“连接检查”可查看检索连接和模型详情。</p>
      ) : null}
    </section>
  );
}
