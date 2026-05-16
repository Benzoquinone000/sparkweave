import { Loader2, Scissors } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import type { KnowledgeVectorChunk } from "@/lib/types";

export function DocumentVectorChunksPanel({
  vectorChunks,
  vectorTotal,
  vectorsAvailable,
  vectorsError,
  vectorsLoading,
  deletingChunk,
  onDeleteChunk,
}: {
  vectorChunks: KnowledgeVectorChunk[];
  vectorTotal: number;
  vectorsAvailable: boolean;
  vectorsError: string;
  vectorsLoading: boolean;
  deletingChunk: boolean;
  onDeleteChunk: (chunk: KnowledgeVectorChunk) => void;
}) {
  return (
    <div className="mt-3 rounded-lg border border-line bg-white p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-xs font-semibold text-ink">引用片段</p>
          <p className="mt-1 text-xs text-slate-500">
            {vectorsAvailable
              ? `${vectorTotal || vectorChunks.length} 个片段来自当前文档`
              : vectorsError || "当前引用索引暂不可读取"}
          </p>
        </div>
        <Badge tone={vectorsAvailable ? "neutral" : "warning"}>{vectorsAvailable ? "已入库" : "不可用"}</Badge>
      </div>
      {vectorsLoading ? (
        <p className="mt-3 flex items-center gap-2 text-xs text-slate-500">
          <Loader2 size={14} className="animate-spin" />
          正在读取引用片段...
        </p>
      ) : vectorChunks.length ? (
        <div className="mt-3 grid max-h-[260px] gap-2 overflow-y-auto pr-1">
          {vectorChunks.map((chunk, index) => (
            <div key={chunk.node_id || chunk.id || index} className="rounded-lg border border-line bg-canvas p-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-xs font-semibold text-ink">
                    {chunk.node_id || chunk.id || `片段-${index + 1}`}
                  </p>
                  <p className="mt-1 text-xs leading-5 text-slate-600">{chunk.text_preview || "空片段"}</p>
                </div>
                <Button
                  tone="quiet"
                  className="min-h-8 px-2 text-xs text-brand-red"
                  onClick={() => onDeleteChunk(chunk)}
                  disabled={deletingChunk}
                >
                  {deletingChunk ? <Loader2 size={13} className="animate-spin" /> : <Scissors size={13} />}
                  删除片段
                </Button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-3 rounded-lg border border-dashed border-line bg-canvas p-3 text-xs leading-5 text-slate-500">
          还没有读取到该文档对应的引用片段。若刚上传完成，请刷新或重建索引。
        </p>
      )}
    </div>
  );
}
