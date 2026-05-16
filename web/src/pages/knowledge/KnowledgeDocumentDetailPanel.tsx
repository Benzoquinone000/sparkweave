import { Eye, FileText, Loader2, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import type { KnowledgeDocumentPreview, KnowledgeDocumentSummary, KnowledgeVectorChunk } from "@/lib/types";

import { DocumentPreviewPanel } from "./KnowledgeDocumentPreviewPanel";
import { DocumentVectorChunksPanel } from "./KnowledgeDocumentVectorChunksPanel";

export function KnowledgeDocumentDetailPanel({
  selectedDocument,
  selectedPreviewMatches,
  preview,
  previewLoading,
  vectorChunks,
  vectorTotal,
  vectorsAvailable,
  vectorsError,
  vectorsLoading,
  deletingDocument,
  deletingChunk,
  onPreview,
  onDeleteDocument,
  onDeleteChunk,
}: {
  selectedDocument: KnowledgeDocumentSummary | null;
  selectedPreviewMatches: boolean;
  preview: KnowledgeDocumentPreview | null;
  previewLoading: boolean;
  vectorChunks: KnowledgeVectorChunk[];
  vectorTotal: number;
  vectorsAvailable: boolean;
  vectorsError: string;
  vectorsLoading: boolean;
  deletingDocument: boolean;
  deletingChunk: boolean;
  onPreview: (documentId: string) => void;
  onDeleteDocument: (document: KnowledgeDocumentSummary) => void;
  onDeleteChunk: (chunk: KnowledgeVectorChunk) => void;
}) {
  return (
    <div className="min-w-0 rounded-lg border border-line bg-canvas p-3">
      {selectedDocument ? (
        <>
          <SelectedDocumentHeader
            document={selectedDocument}
            previewLoading={previewLoading}
            deletingDocument={deletingDocument}
            onPreview={onPreview}
            onDeleteDocument={onDeleteDocument}
          />

          <DocumentPreviewPanel
            selectedPreviewMatches={selectedPreviewMatches}
            preview={preview}
          />

          <DocumentVectorChunksPanel
            vectorChunks={vectorChunks}
            vectorTotal={vectorTotal}
            vectorsAvailable={vectorsAvailable}
            vectorsError={vectorsError}
            vectorsLoading={vectorsLoading}
            deletingChunk={deletingChunk}
            onDeleteChunk={onDeleteChunk}
          />
        </>
      ) : (
        <EmptyState icon={<FileText size={24} />} title="选择一个文档" description="左侧选择文档后，可以查看文本预览和引用片段。" />
      )}
    </div>
  );
}

function SelectedDocumentHeader({
  document,
  previewLoading,
  deletingDocument,
  onPreview,
  onDeleteDocument,
}: {
  document: KnowledgeDocumentSummary;
  previewLoading: boolean;
  deletingDocument: boolean;
  onPreview: (documentId: string) => void;
  onDeleteDocument: (document: KnowledgeDocumentSummary) => void;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold text-ink">{document.name}</p>
        <p className="mt-1 text-xs leading-5 text-slate-500">
          {document.relative_path || document.extension || "资料文档"}
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button
          tone="secondary"
          className="min-h-8 px-3 text-xs"
          onClick={() => onPreview(document.id)}
          disabled={document.content_available === false || previewLoading}
        >
          {previewLoading ? <Loader2 size={14} className="animate-spin" /> : <Eye size={14} />}
          查看文本
        </Button>
        <Button
          tone="danger"
          className="min-h-8 px-3 text-xs"
          onClick={() => onDeleteDocument(document)}
          disabled={deletingDocument}
        >
          {deletingDocument ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
          删除
        </Button>
      </div>
    </div>
  );
}
