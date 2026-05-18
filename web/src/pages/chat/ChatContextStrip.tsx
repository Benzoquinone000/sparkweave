import { BookOpenCheck, Search } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { capabilityLabel } from "@/lib/capabilities";
import type { CapabilityId } from "@/lib/types";

export function ChatContextStrip({
  capability,
  tools,
  knowledgeBases,
  historyReferenceCount,
  notebookReferenceCount,
  onOpenContext,
}: {
  capability: CapabilityId;
  tools: string[];
  knowledgeBases: string[];
  historyReferenceCount: number;
  notebookReferenceCount: number;
  onOpenContext: () => void;
}) {
  const ragEnabled = tools.includes("rag");
  const referenceCount = historyReferenceCount + notebookReferenceCount;
  const shouldShow = ragEnabled || knowledgeBases.length || referenceCount > 0 || capability !== "chat";
  if (!shouldShow) return null;

  const primaryKb = knowledgeBases[0] || "";
  const kbLabel = primaryKb ? `${primaryKb}${knowledgeBases.length > 1 ? ` +${knowledgeBases.length - 1}` : ""}` : "未选择资料库";
  const title = primaryKb ? `资料库：${kbLabel}` : ragEnabled ? "当前未限定资料库" : capabilityLabel(capability);
  const description = primaryKb
    ? "助教会按问题自动判断如何查资料和组织依据。"
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
          {primaryKb && ragEnabled ? <Badge tone="neutral">自动引用</Badge> : null}
          {referenceCount ? <Badge tone="neutral">引用 {referenceCount} 条</Badge> : null}
          <Button tone="secondary" className="min-h-8 px-2.5 text-xs" type="button" onClick={onOpenContext}>
            <Search size={14} />
            资料
          </Button>
        </div>
      </div>
    </div>
  );
}
