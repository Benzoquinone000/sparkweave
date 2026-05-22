import { BookOpenCheck, SlidersHorizontal } from "lucide-react";

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
  const shouldShow = knowledgeBases.length > 0 || referenceCount > 0 || capability !== "chat";
  if (!shouldShow) return null;

  const primaryKb = knowledgeBases[0] || "";
  const kbLabel = primaryKb ? `${primaryKb}${knowledgeBases.length > 1 ? ` +${knowledgeBases.length - 1}` : ""}` : "未选择资料库";
  const title = primaryKb ? `资料库：${kbLabel}` : referenceCount ? "已引用学习记录" : capabilityLabel(capability);
  const description = primaryKb
    ? "系统会按问题自动判断如何查资料和组织来源。"
    : referenceCount
      ? "系统会结合选中的历史会话和笔记，不需要手动切换设置。"
    : "本轮已固定处理流程；默认情况下建议交给自动导学判断。";

  return (
    <div
      className={`dt-rag-flow ${primaryKb ? "dt-rag-flow-active" : ""} mb-2 rounded-lg border border-line bg-white/90 px-2.5 py-2 shadow-[0_1px_2px_rgba(15,15,15,0.03)]`}
      data-testid="chat-context-strip"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-canvas text-charcoal">
            <BookOpenCheck size={16} />
          </span>
          <div className="min-w-0">
            <p className="truncate text-xs font-semibold text-ink">{title}</p>
            <p className="hidden truncate text-xs leading-5 text-slate-500 md:block">{description}</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={primaryKb ? "success" : "neutral"}>{primaryKb ? "已绑定资料" : "固定流程"}</Badge>
          {primaryKb && ragEnabled ? <Badge tone="neutral">自动引用</Badge> : null}
          {referenceCount ? <Badge tone="neutral">引用 {referenceCount} 条</Badge> : null}
          <Button tone="secondary" className="min-h-8 px-2.5 text-xs" type="button" onClick={onOpenContext}>
            <SlidersHorizontal size={14} />
            资料
          </Button>
        </div>
      </div>
    </div>
  );
}
