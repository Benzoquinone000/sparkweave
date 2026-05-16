import { Loader2, Search, X } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import type { RagTestHandoff } from "@/lib/ragHandoff";

export function RagSearchHandoffCard({
  handoff,
  activeKb,
  running,
  onRun,
  onDismiss,
}: {
  handoff: RagTestHandoff;
  activeKb: string;
  running: boolean;
  onRun: () => void;
  onDismiss?: () => void;
}) {
  const fromChat = handoff.source === "chat";

  return (
    <div className="rounded-lg border border-brand-purple-300 bg-tint-lavender p-3" data-testid="knowledge-rag-test-handoff">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-ink">{fromChat ? "从聊天带来的证据复测" : "已带入待测问题"}</p>
            {handoff.status ? <Badge tone={handoff.status === "无证据" ? "neutral" : "warning"}>{handoff.status}</Badge> : null}
          </div>
          <p className="mt-1 max-w-2xl text-xs leading-5 text-slate-600">
            {fromChat
              ? `已带入刚才的聊天问题和资料库「${activeKb || "当前资料库"}」。先运行预检，确认资料片段能否被稳定召回。`
              : `已按链接填入问题和资料库「${activeKb || "当前资料库"}」，可以直接运行一次预检。`}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {onDismiss ? (
            <Button tone="secondary" className="min-h-9 px-3 text-xs" type="button" onClick={onDismiss}>
              <X size={15} />
              收起
            </Button>
          ) : null}
          <Button tone="primary" className="min-h-9 px-3 text-xs" type="button" onClick={onRun} disabled={running}>
            {running ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
            开始复测
          </Button>
        </div>
      </div>
    </div>
  );
}
