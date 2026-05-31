import { FileText, FileUp, Loader2, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import type { KnowledgeDocumentPreview, KnowledgeDocumentSummary, KnowledgeVectorChunk } from "@/lib/types";

import { formatErrorMessage } from "./format";
import {
  KnowledgeDocumentDetailPanel,
  KnowledgeDocumentListPanel,
} from "./KnowledgeDocumentManagerPanels";
import { KNOWLEDGE_PANEL_CLASS } from "./styles";

export function KnowledgeDocumentManager({
  documents,
  documentsLoading,
  documentsError,
  selectedDocumentId,
  selectedDocument,
  onSelectDocument,
  onRefresh,
  onPreview,
  preview,
  previewLoading,
  vectorChunks,
  vectorTotal,
  vectorsAvailable,
  vectorsError,
  vectorsLoading,
  onDeleteDocument,
  onDeleteChunk,
  deletingDocument,
  deletingChunk,
}: {
  documents: KnowledgeDocumentSummary[];
  documentsLoading: boolean;
  documentsError: unknown;
  selectedDocumentId: string;
  selectedDocument: KnowledgeDocumentSummary | null;
  onSelectDocument: (documentId: string) => void;
  onRefresh: () => void;
  onPreview: (documentId: string) => void;
  preview: KnowledgeDocumentPreview | null;
  previewLoading: boolean;
  vectorChunks: KnowledgeVectorChunk[];
  vectorTotal: number;
  vectorsAvailable: boolean;
  vectorsError: string;
  vectorsLoading: boolean;
  onDeleteDocument: (document: KnowledgeDocumentSummary) => void;
  onDeleteChunk: (chunk: KnowledgeVectorChunk) => void;
  deletingDocument: boolean;
  deletingChunk: boolean;
}) {
  const selectedPreviewMatches = preview?.document?.id === selectedDocumentId;
  const vectorInspectionAvailable = documents.every((item) => item.vectors_available !== false);

  return (
    <section className={`mt-4 ${KNOWLEDGE_PANEL_CLASS}`} data-testid="knowledge-document-manager">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-line bg-canvas text-brand-purple">
            <FileText size={18} />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-ink">文档与引用片段</p>
            <p className="mt-1 text-xs leading-5 text-slate-500">查看文本结果，管理可被问答引用的片段。</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone={documents.length ? "brand" : "neutral"}>{documents.length} 个文档</Badge>
          {!vectorInspectionAvailable ? <Badge tone="warning">引用片段未读取</Badge> : null}
          <Button tone="quiet" className="min-h-8 px-2 text-xs" onClick={onRefresh}>
            {documentsLoading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          </Button>
        </div>
      </div>

      {documentsError ? (
        <p className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-xs leading-5 text-red-700">
          文档列表读取失败：{formatErrorMessage(documentsError)}
        </p>
      ) : null}

      {!documentsLoading && !documents.length ? (
        <div className="mt-4">
          <EmptyState
            align="left"
            tone="knowledge"
            icon={<FileUp size={22} />}
            eyebrow="等待资料"
            title="还没有可管理的文档"
            description="上传资料并完成整理后，可以在这里查看文档内容和引用片段。"
          />
        </div>
      ) : (
        <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
          <KnowledgeDocumentListPanel
            documents={documents}
            selectedDocumentId={selectedDocumentId}
            onSelectDocument={onSelectDocument}
          />
          <KnowledgeDocumentDetailPanel
            selectedDocument={selectedDocument}
            selectedPreviewMatches={selectedPreviewMatches}
            preview={preview}
            previewLoading={previewLoading}
            vectorChunks={vectorChunks}
            vectorTotal={vectorTotal}
            vectorsAvailable={vectorsAvailable}
            vectorsError={vectorsError}
            vectorsLoading={vectorsLoading}
            deletingDocument={deletingDocument}
            deletingChunk={deletingChunk}
            onPreview={onPreview}
            onDeleteDocument={onDeleteDocument}
            onDeleteChunk={onDeleteChunk}
          />
        </div>
      )}
    </section>
  );
}
