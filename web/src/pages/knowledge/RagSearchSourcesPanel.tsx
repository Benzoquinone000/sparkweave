import { GitBranch, Search, SlidersHorizontal } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import type { RagSearchSource } from "@/lib/types";

import type { RagSearchRecoveryAction } from "./ragSearchStatus";

export function RagSearchSourcesList({
  sources,
  onAction,
}: {
  sources: RagSearchSource[];
  onAction: (action: RagSearchRecoveryAction) => void;
}) {
  return (
    <div className="grid gap-3">
      {sources.map((source, index) => (
        <RagSearchSourceArticle key={`${source.chunk_id || source.source || index}`} source={source} index={index} />
      ))}
      {!sources.length ? (
        <EmptyState
          icon={<Search size={24} />}
          title="没有召回证据"
          description="尝试扩大证据数量、切换检索画像，或先检查知识库是否已经完成索引。"
          action={
            <div className="flex flex-wrap justify-center gap-2">
              <Button tone="primary" className="min-h-9 px-3 text-xs" type="button" onClick={() => onAction("deep")}>
                <GitBranch size={15} />
                套用深度追问
              </Button>
              <Button tone="secondary" className="min-h-9 px-3 text-xs" type="button" onClick={() => onAction("setup")}>
                <SlidersHorizontal size={15} />
                调整检索
              </Button>
            </div>
          }
        />
      ) : null}
    </div>
  );
}

function RagSearchSourceArticle({
  source,
  index,
}: {
  source: RagSearchSource;
  index: number;
}) {
  return (
    <article className="rounded-lg border border-line bg-white p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-ink">{source.title || source.source || `证据 ${index + 1}`}</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">{source.evidence_reason || "来自知识库检索结果。"}</p>
        </div>
        <Badge tone="neutral">{source.score === "" || source.score == null ? "相关度 -" : `相关度 ${source.score}`}</Badge>
      </div>
      <p className="mt-3 whitespace-pre-wrap rounded-lg bg-canvas p-3 text-sm leading-6 text-slate-700">
        {source.content || "这个证据没有可预览文本。"}
      </p>
      {source.matched_keywords?.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {source.matched_keywords.slice(0, 8).map((keyword) => (
            <Badge key={keyword} tone="brand">
              {keyword}
            </Badge>
          ))}
        </div>
      ) : null}
    </article>
  );
}
