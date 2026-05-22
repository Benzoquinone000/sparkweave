import { ChevronLeft, MessageSquareText, MoreHorizontal } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

import { formatProgressStage } from "./format";
import type { KnowledgeWorkspaceContentProps } from "./KnowledgeWorkspaceContentTypes";
import { buildKnowledgeWorkspaceNavItems, type KnowledgeWorkspaceNavItem } from "./KnowledgeWorkspaceNavItems";
import { KNOWLEDGE_ENTRY_ICON_CLASS, KNOWLEDGE_PANEL_COMPACT_CLASS } from "./styles";
import type { KnowledgeWorkspace } from "./types";

export function KnowledgeWorkspaceTaskHeader({
  activeKb,
  workspace,
  overview,
  onNavigate,
}: Pick<KnowledgeWorkspaceContentProps, "activeKb" | "workspace" | "overview" | "onNavigate">) {
  const items = buildKnowledgeWorkspaceNavItems({
    documentCount: overview.documentCount,
    vectorCount: overview.vectorCount,
    diagnosticStatus: overview.diagnosticStatus,
    recoveryBadge: overview.recoveryBadge,
    recoveryNeedsAttention: overview.recoveryNeedsAttention,
    evaluationAvailable: overview.evaluationAvailable,
    testSourceCount: overview.testSourceCount,
    folderCount: overview.folderCount,
    taskActive: overview.taskActive,
  });
  const activeItem = items.find((item) => item.id === workspace) ?? items[0];
  const shortcutItems = buildShortcutItems(items, workspace, overview.taskActive, overview.recoveryNeedsAttention);
  const advancedItems = items.filter(
    (item) => item.id !== "overview" && !shortcutItems.some((shortcut) => shortcut.id === item.id),
  );
  const statusTone = overview.recoveryNeedsAttention
    ? "warning"
    : overview.progressPercent >= 100
      ? "success"
      : overview.taskActive
        ? "brand"
        : "neutral";
  const documents = toFiniteNumber(overview.documentCount);
  const vectors = toFiniteNumber(overview.vectorCount);
  const canAsk =
    Boolean(activeKb) &&
    documents !== null &&
    documents > 0 &&
    (vectors === null || vectors > 0) &&
    !overview.taskActive &&
    !overview.recoveryNeedsAttention;

  return (
    <section className={KNOWLEDGE_PANEL_COMPACT_CLASS} data-testid="knowledge-workspace-task-header">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 gap-3">
          <span className={`${KNOWLEDGE_ENTRY_ICON_CLASS} ${activeItem.accent} shrink-0`}>{activeItem.icon}</span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={activeKb ? "brand" : "neutral"}>{activeKb || "未选择资料库"}</Badge>
              <Badge tone={statusTone}>{formatProgressStage(overview.progressStage)}</Badge>
            </div>
            <h2 className="mt-2 text-base font-semibold text-ink">{activeItem.title}</h2>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-500">{activeItem.description}</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            tone="secondary"
            className="min-h-9 px-3 text-xs"
            onClick={() => onNavigate("overview")}
            data-testid="knowledge-workspace-back"
          >
            <ChevronLeft size={15} />
            资料首页
          </Button>
          {canAsk ? (
            <a
              href={buildKnowledgeChatHref(activeKb)}
              className="dt-interactive inline-flex min-h-9 items-center justify-center gap-2 rounded-lg border border-brand-purple bg-brand-purple px-3 text-xs font-medium text-white hover:bg-brand-purple-800"
              data-testid="knowledge-workspace-ask"
            >
              <MessageSquareText size={15} />
              问资料
            </a>
          ) : (
            <button
              type="button"
              disabled
              className="inline-flex min-h-9 items-center justify-center gap-2 rounded-lg border border-line bg-white px-3 text-xs font-medium text-slate-400"
              data-testid="knowledge-workspace-ask"
              title={activeKb ? "资料整理完成后可用" : "先选择资料库"}
            >
              <MessageSquareText size={15} />
              问资料
            </button>
          )}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {shortcutItems.map((item) => (
          <WorkspaceShortcut key={item.id} item={item} active={workspace} onNavigate={onNavigate} />
        ))}

        {advancedItems.length ? (
          <details className="relative rounded-lg border border-line bg-white px-3 py-2 [&>summary::-webkit-details-marker]:hidden">
            <summary className="dt-interactive flex cursor-pointer items-center gap-2 text-xs font-medium text-slate-600">
              <MoreHorizontal size={15} />
              更多入口
            </summary>
            <div className="mt-2 flex min-w-[220px] flex-col gap-2">
              {advancedItems.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`dt-interactive flex min-h-9 items-center justify-between gap-3 rounded-lg border px-3 text-left text-xs transition ${
                    item.id === workspace
                      ? "border-brand-purple-300 bg-tint-lavender text-brand-purple"
                      : "border-line bg-white text-slate-600 hover:border-brand-purple-300"
                  }`}
                  onClick={() => onNavigate(item.id)}
                  data-testid={`knowledge-workspace-more-${item.id}`}
                >
                  <span className="min-w-0 truncate font-medium">{item.title}</span>
                  <Badge tone={item.id === workspace ? "brand" : item.tone}>{item.badge}</Badge>
                </button>
              ))}
            </div>
          </details>
        ) : null}
      </div>

      {overview.progressMessage ? (
        <p className="mt-3 line-clamp-2 text-xs leading-5 text-slate-500">{overview.progressMessage}</p>
      ) : null}
    </section>
  );
}

function WorkspaceShortcut({
  item,
  active,
  onNavigate,
}: {
  item: KnowledgeWorkspaceNavItem;
  active: KnowledgeWorkspace;
  onNavigate: (workspace: KnowledgeWorkspace) => void;
}) {
  const selected = item.id === active;
  return (
    <button
      type="button"
      className={`dt-interactive inline-flex min-h-9 items-center gap-2 rounded-lg border px-3 text-xs transition ${
        selected
          ? "border-brand-purple-300 bg-tint-lavender text-brand-purple"
          : "border-line bg-white text-slate-600 hover:border-brand-purple-300 hover:bg-canvas"
      }`}
      onClick={() => onNavigate(item.id)}
      data-testid={`knowledge-workspace-shortcut-${item.id}`}
    >
      <span className={selected ? "text-brand-purple" : "text-slate-500"}>{item.icon}</span>
      <span className="font-medium">{item.title}</span>
      <Badge tone={selected ? "brand" : item.tone}>{item.badge}</Badge>
    </button>
  );
}

function buildShortcutItems(
  items: KnowledgeWorkspaceNavItem[],
  workspace: KnowledgeWorkspace,
  taskActive: boolean,
  recoveryNeedsAttention: boolean,
) {
  const shortcutIds = new Set<KnowledgeWorkspace>(["upload", "documents", "test"]);
  if (taskActive || workspace === "progress") shortcutIds.add("progress");
  if (recoveryNeedsAttention || workspace === "recovery") shortcutIds.add("recovery");
  if (!shortcutIds.has(workspace) && workspace !== "overview") shortcutIds.add(workspace);
  return items.filter((item) => shortcutIds.has(item.id));
}

function buildKnowledgeChatHref(activeKb: string) {
  const params = new URLSearchParams({ capability: "chat", kb: activeKb });
  return `/chat?${params.toString()}`;
}

function toFiniteNumber(value: number | string | null | undefined) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}
