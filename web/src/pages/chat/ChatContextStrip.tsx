import { BookOpenCheck, Search } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { capabilityLabel } from "@/lib/capabilities";
import type { CapabilityId } from "@/lib/types";
import { formatRagModeLabel, formatRetrievalProfileLabel, isTruthyConfigFlag } from "./chatPageUtils";

export function ChatContextStrip({
  capability,
  tools,
  knowledgeBases,
  historyReferenceCount,
  notebookReferenceCount,
  config,
  onOpenContext,
}: {
  capability: CapabilityId;
  tools: string[];
  knowledgeBases: string[];
  historyReferenceCount: number;
  notebookReferenceCount: number;
  config: Record<string, unknown>;
  onOpenContext: () => void;
}) {
  const ragEnabled = tools.includes("rag");
  const referenceCount = historyReferenceCount + notebookReferenceCount;
  const shouldShow = ragEnabled || knowledgeBases.length || referenceCount > 0 || capability !== "chat";
  if (!shouldShow) return null;

  const primaryKb = knowledgeBases[0] || "";
  const kbLabel = primaryKb ? `${primaryKb}${knowledgeBases.length > 1 ? ` +${knowledgeBases.length - 1}` : ""}` : "未选择资料库";
  const prefetchEnabled = isTruthyConfigFlag(config.prefetch_rag);
  const retrievalProfile = formatRetrievalProfileLabel(config.retrieval_profile);
  const ragMode = formatRagModeLabel(config.agentic_rag);
  const title = primaryKb ? `资料库：${kbLabel}` : ragEnabled ? "当前未限定资料库" : capabilityLabel(capability);
  const description = primaryKb
    ? prefetchEnabled
      ? "发送后会先从资料库取证据，再组织回答。"
      : "回答会优先使用已选择资料库；复杂问题可在资料与工具里打开自动分解。"
    : "本轮可以先普通问答；需要基于课程资料时，先选择一个资料库。";

  return (
    <div className="mb-2 rounded-lg border border-line bg-white px-3 py-2" data-testid="chat-context-strip">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-tint-lavender text-brand-purple">
            <BookOpenCheck size={16} />
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-ink">{title}</p>
            <p className="hidden truncate text-xs leading-5 text-slate-500 sm:block">{description}</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={primaryKb ? "success" : "neutral"}>{primaryKb ? "已绑定资料" : "普通问答"}</Badge>
          {prefetchEnabled ? <Badge tone="brand">先取证据</Badge> : null}
          {primaryKb && ragEnabled ? <Badge tone="neutral">{ragMode}</Badge> : null}
          {retrievalProfile ? <Badge tone="neutral">{retrievalProfile}</Badge> : null}
          {referenceCount ? <Badge tone="neutral">引用 {referenceCount} 条</Badge> : null}
          <Button tone="secondary" className="min-h-8 px-2.5 text-xs" type="button" onClick={onOpenContext}>
            <Search size={14} />
            调整
          </Button>
        </div>
      </div>
    </div>
  );
}
