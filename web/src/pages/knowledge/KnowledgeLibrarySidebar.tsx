import { FileUp, Loader2, RefreshCw, UploadCloud } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import type { KnowledgeBase } from "@/lib/types";

import { formatProgressStage } from "./format";
import { KNOWLEDGE_PANEL_CLASS } from "./styles";

export function KnowledgeLibrarySidebar({
  bases,
  activeKb,
  createActive,
  refreshing,
  onRefresh,
  onCreate,
  onSelect,
}: {
  bases: KnowledgeBase[];
  activeKb: string;
  createActive: boolean;
  refreshing: boolean;
  onRefresh: () => void;
  onCreate: () => void;
  onSelect: (kbName: string) => void;
}) {
  return (
    <section className={KNOWLEDGE_PANEL_CLASS}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-ink">我的资料库</h2>
          <p className="mt-1 text-sm leading-6 text-slate-500">选择一个资料库，后续问答和导学会优先引用它。</p>
        </div>
        <div className="flex gap-1">
          <Button tone="quiet" className="min-h-8 px-2 text-xs" onClick={onRefresh}>
            {refreshing ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          </Button>
          <Button
            tone={createActive ? "primary" : "secondary"}
            className="min-h-8 px-2 text-xs"
            onClick={onCreate}
            data-testid="knowledge-open-create"
          >
            <UploadCloud size={14} />
            新建
          </Button>
        </div>
      </div>

      <div className="mt-4 max-h-[520px] space-y-2 overflow-y-auto pr-1">
        {bases.map((kb) => {
          const active = kb.name === activeKb;
          return (
            <button
              key={kb.name}
              type="button"
              onClick={() => onSelect(kb.name)}
              className={`w-full rounded-lg border p-3 text-left transition ${
                active ? "border-brand-purple-300 bg-tint-lavender" : "border-line bg-white hover:border-brand-purple-300"
              }`}
              data-testid={`knowledge-kb-select-${kb.name}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-ink">{kb.name}</p>
                  <p className="mt-1 text-xs text-slate-500">{formatProgressStage(kb.status || "ready")}</p>
                </div>
                <Badge tone={kb.is_default ? "brand" : active ? "success" : "neutral"}>
                  {kb.is_default ? "默认" : active ? "当前" : "选择"}
                </Badge>
              </div>
            </button>
          );
        })}

        {!bases.length ? (
          <div className="rounded-lg border border-dashed border-line bg-canvas p-4">
            <EmptyState
              icon={<FileUp size={24} />}
              title="还没有资料库"
              description="先创建一个资料库并上传课程资料。"
            />
            <Button tone="primary" className="mt-3 w-full" onClick={onCreate}>
              <UploadCloud size={16} />
              新建资料库
            </Button>
          </div>
        ) : null}
      </div>
    </section>
  );
}
