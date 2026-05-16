import { Badge } from "@/components/ui/Badge";
import type { KnowledgeDocumentSummary } from "@/lib/types";

import { formatBytes, formatDocDate } from "./format";

export function KnowledgeDocumentListPanel({
  documents,
  selectedDocumentId,
  onSelectDocument,
}: {
  documents: KnowledgeDocumentSummary[];
  selectedDocumentId: string;
  onSelectDocument: (documentId: string) => void;
}) {
  return (
    <div className="min-w-0">
      <div className="grid max-h-[430px] gap-2 overflow-y-auto pr-1">
        {documents.map((document) => {
          const active = document.id === selectedDocumentId;
          return (
            <button
              key={document.id}
              type="button"
              onClick={() => onSelectDocument(document.id)}
              className={`dt-interactive w-full rounded-lg border p-3 text-left transition ${
                active ? "border-brand-purple bg-tint-lavender" : "border-line bg-white hover:border-brand-purple-300"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-ink">{document.name}</p>
                  <p className="mt-1 truncate text-xs text-slate-500">
                    {document.size_human || formatBytes(Number(document.size || 0))} · {formatDocDate(document.modified_at)}
                  </p>
                </div>
                <Badge tone={Number(document.vector_count || 0) > 0 ? "success" : "neutral"}>
                  {document.vectors_available === false ? "未读取" : `${document.vector_count || 0} 片段`}
                </Badge>
              </div>
              <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500">
                {document.extracted_cached ? <span>已缓存预览</span> : <span>待生成预览</span>}
                {document.content_available === false ? <span>不可预览</span> : null}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
