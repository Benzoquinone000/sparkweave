import { Database, GitBranch, ListChecks, MessageSquareText, SlidersHorizontal } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

import type { RagSearchRecovery, RagSearchRecoveryAction } from "./ragSearchStatus";

export function RagSearchRecoveryCard({
  recovery,
  onAction,
}: {
  recovery: RagSearchRecovery;
  onAction: (action: RagSearchRecoveryAction) => void;
}) {
  return (
    <div className="rounded-lg border border-line bg-white p-3" data-testid="knowledge-rag-test-recovery">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-ink">{recovery.title}</p>
            <Badge tone={recovery.tone}>{recovery.badge}</Badge>
          </div>
          <p className="mt-1 max-w-2xl text-xs leading-5 text-slate-500">{recovery.description}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button tone="primary" className="min-h-9 px-3 text-xs" type="button" onClick={() => onAction(recovery.primary.action)}>
            <RecoveryActionIcon action={recovery.primary.action} />
            {recovery.primary.label}
          </Button>
          {recovery.secondary ? (
            <Button tone="secondary" className="min-h-9 px-3 text-xs" type="button" onClick={() => onAction(recovery.secondary!.action)}>
              <RecoveryActionIcon action={recovery.secondary.action} />
              {recovery.secondary.label}
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export function RagSearchChatHandoffCard({
  href,
  weak,
  sourceCount,
  activeKb,
}: {
  href: string;
  weak: boolean;
  sourceCount: number;
  activeKb: string;
}) {
  return (
    <div className="rounded-lg border border-line bg-tint-sky p-3" data-testid="knowledge-rag-test-chat-handoff">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-ink">{weak ? "可以试问，但建议先复测证据" : "证据可用，可以进入问答"}</p>
            <Badge tone={weak ? "warning" : "success"}>{sourceCount} 条证据</Badge>
          </div>
          <p className="mt-1 max-w-2xl text-xs leading-5 text-slate-600">
            系统会带上当前问题、资料库「{activeKb}」和这组检索设置，在聊天页先取资料再回答。
          </p>
        </div>
        <a
          href={href}
          className="dt-interactive inline-flex min-h-9 items-center justify-center gap-2 rounded-lg border border-brand-purple bg-brand-purple px-3 text-xs font-medium text-white shadow-[rgba(86,69,212,0.16)_0_1px_2px] hover:bg-brand-purple-800"
        >
          <MessageSquareText size={15} />
          带证据开始问答
        </a>
      </div>
    </div>
  );
}

export function RagSearchResultNavigationCards({
  onOpenAgentic,
  onOpenContext,
  onOpenSources,
}: {
  onOpenAgentic: () => void;
  onOpenContext: () => void;
  onOpenSources: () => void;
}) {
  return (
    <div className="grid gap-2 md:grid-cols-3">
      <button
        type="button"
        className="rounded-lg border border-line bg-white p-3 text-left transition hover:border-brand-purple-300"
        onClick={onOpenAgentic}
        data-testid="knowledge-rag-test-open-agentic"
      >
        <span className="block text-sm font-semibold text-ink">深度检索过程</span>
        <span className="mt-1 block text-xs leading-5 text-slate-500">查看拆分、质量检查和修复情况。</span>
      </button>
      <button
        type="button"
        className="rounded-lg border border-line bg-white p-3 text-left transition hover:border-brand-purple-300"
        onClick={onOpenContext}
        data-testid="knowledge-rag-test-open-context"
      >
        <span className="block text-sm font-semibold text-ink">召回上下文</span>
        <span className="mt-1 block text-xs leading-5 text-slate-500">查看最终送入回答生成的参考文本。</span>
      </button>
      <button
        type="button"
        className="rounded-lg border border-line bg-white p-3 text-left transition hover:border-brand-purple-300"
        onClick={onOpenSources}
        data-testid="knowledge-rag-test-open-sources"
      >
        <span className="block text-sm font-semibold text-ink">证据列表</span>
        <span className="mt-1 block text-xs leading-5 text-slate-500">逐条查看来源片段和命中词。</span>
      </button>
    </div>
  );
}

function RecoveryActionIcon({ action }: { action: RagSearchRecoveryAction }) {
  if (action === "diagnostics") return <Database size={15} />;
  if (action === "sources") return <ListChecks size={15} />;
  if (action === "agentic" || action === "deep") return <GitBranch size={15} />;
  return <SlidersHorizontal size={15} />;
}
