import type { FormEvent } from "react";
import { ChevronLeft, FileUp, Loader2, UploadCloud } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { FieldShell, FileInput, SelectInput } from "@/components/ui/Field";
import type { KnowledgeBase } from "@/lib/types";

import { FileList } from "./FileList";
import { formatErrorMessage } from "./format";
import { KNOWLEDGE_PANEL_CLASS } from "./styles";

export function KnowledgeUploadPanel({
  activeKb,
  bases,
  files,
  uploading,
  error,
  onKbChange,
  onFilesChange,
  onSubmit,
  onBack,
  onRecover,
}: {
  activeKb: string;
  bases: KnowledgeBase[];
  files: File[];
  uploading: boolean;
  error?: unknown;
  onKbChange: (kbName: string) => void;
  onFilesChange: (files: File[]) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onBack?: () => void;
  onRecover: () => void;
}) {
  return (
    <section className={KNOWLEDGE_PANEL_CLASS} data-testid="knowledge-upload-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <UploadCloud size={18} className="text-brand-purple" />
          <h2 className="text-base font-semibold text-ink">追加资料</h2>
        </div>
        {onBack ? (
          <Button
            tone="secondary"
            className="min-h-9 px-3 text-xs"
            type="button"
            onClick={onBack}
            data-testid="knowledge-upload-back"
          >
            <ChevronLeft size={14} />
            返回概览
          </Button>
        ) : null}
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-500">
        把新的课件、笔记或代码加入资料库，系统会自动建立可检索索引。
      </p>

      <form className="mt-4 grid gap-3" onSubmit={onSubmit}>
        <FieldShell label="目标资料库">
          <SelectInput value={activeKb} onChange={(event) => onKbChange(event.target.value)} data-testid="knowledge-upload-target">
            {bases.map((kb) => (
              <option key={kb.name} value={kb.name}>
                {kb.name}
              </option>
            ))}
          </SelectInput>
        </FieldShell>
        <FieldShell label="上传文件">
          <FileInput
            multiple
            onChange={(event) => onFilesChange(Array.from(event.target.files ?? []))}
            data-testid="knowledge-upload-files"
            buttonLabel="选择文件"
            emptyLabel="未选择文件"
          />
        </FieldShell>
        {files.length ? <FileList files={files} /> : null}
        {error ? (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3">
            <p className="text-sm font-semibold text-red-700">上传没有完成</p>
            <p className="mt-1 text-sm leading-6 text-red-700">{formatErrorMessage(error)}</p>
            <Button tone="secondary" className="mt-3 min-h-9 px-3 text-xs" type="button" onClick={onRecover}>
              查看修复向导
            </Button>
          </div>
        ) : null}
        <Button tone="primary" type="submit" disabled={!activeKb || !files.length || uploading} data-testid="knowledge-upload-submit">
          {uploading ? <Loader2 size={16} className="animate-spin" /> : <FileUp size={16} />}
          上传并索引
        </Button>
      </form>
    </section>
  );
}
