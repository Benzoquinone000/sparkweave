import { Badge } from "@/components/ui/Badge";
import type { KnowledgeDocumentPreview } from "@/lib/types";

export function DocumentPreviewPanel({
  selectedPreviewMatches,
  preview,
}: {
  selectedPreviewMatches: boolean;
  preview: KnowledgeDocumentPreview | null;
}) {
  if (!selectedPreviewMatches) {
    return (
      <p className="mt-3 rounded-lg border border-dashed border-line bg-white p-3 text-xs leading-5 text-slate-500">
        点击“查看文本”后，会显示 OCR 或文本层提取后的 Markdown 结果，并缓存到资料库目录。
      </p>
    );
  }

  return (
    <div className="mt-3 rounded-lg border border-line bg-white p-3">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold text-ink">OCR / 文本预览</p>
        <Badge tone={preview?.truncated ? "warning" : "neutral"}>
          {preview?.truncated ? "已截断" : `${preview?.content_chars ?? 0} 字`}
        </Badge>
      </div>
      <pre className="max-h-[220px] overflow-auto whitespace-pre-wrap break-words rounded-lg bg-canvas p-3 text-xs leading-6 text-slate-700">
        {preview?.content || "没有可预览文本。"}
      </pre>
    </div>
  );
}
