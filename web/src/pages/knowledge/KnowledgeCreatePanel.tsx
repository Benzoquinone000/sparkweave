import type { FormEvent } from "react";
import { ChevronLeft, Loader2, UploadCloud } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { FieldShell, FileInput, SelectInput, TextInput } from "@/components/ui/Field";
import type { RagProvider } from "@/lib/types";

import { FileList } from "./FileList";
import { formatErrorMessage } from "./format";
import { KNOWLEDGE_PANEL_LOOSE_CLASS } from "./styles";

export function KnowledgeCreatePanel({
  name,
  files,
  provider,
  providers,
  creating,
  error,
  onNameChange,
  onFilesChange,
  onProviderChange,
  onSubmit,
  onBack,
}: {
  name: string;
  files: File[];
  provider: string;
  providers: RagProvider[];
  creating: boolean;
  error?: unknown;
  onNameChange: (value: string) => void;
  onFilesChange: (files: File[]) => void;
  onProviderChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onBack: () => void;
}) {
  return (
    <section className={KNOWLEDGE_PANEL_LOOSE_CLASS} data-testid="knowledge-create-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold text-brand-purple">New Library</p>
          <h2 className="mt-2 text-xl font-semibold text-ink">新建资料库</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            这是一个全局动作，不依赖当前选中的资料库。创建完成后会自动切换到新资料库。
          </p>
        </div>
        <Button tone="secondary" className="min-h-9 px-3 text-xs" onClick={onBack}>
          <ChevronLeft size={15} />
          返回资料库
        </Button>
      </div>

      <form className="mt-5 grid gap-4" onSubmit={onSubmit}>
        <FieldShell label="资料库名称">
          <TextInput
            value={name}
            onChange={(event) => onNameChange(event.target.value)}
            placeholder="例如 calculus_notes"
            data-testid="knowledge-create-name"
          />
        </FieldShell>
        <FieldShell label="检索引擎">
          <SelectInput value={provider} onChange={(event) => onProviderChange(event.target.value)}>
            {providers.length ? (
              providers.map((item) => (
                <option key={item.name} value={item.name}>
                  {item.label || item.name}
                </option>
              ))
            ) : (
              <option value="">使用默认</option>
            )}
          </SelectInput>
        </FieldShell>
        <FieldShell label="初始资料" hint="支持 PDF、Markdown、文本、代码等资料">
          <FileInput
            multiple
            onChange={(event) => onFilesChange(Array.from(event.target.files ?? []))}
            data-testid="knowledge-create-files"
            buttonLabel="选择资料"
            emptyLabel="未选择资料"
          />
        </FieldShell>
        {files.length ? <FileList files={files} /> : null}
        {error ? (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm leading-6 text-red-700">
            创建没有完成：{formatErrorMessage(error)}
          </div>
        ) : null}
        <Button
          tone="primary"
          type="submit"
          className="min-h-11"
          disabled={!name.trim() || !files.length || creating}
          data-testid="knowledge-create-submit"
        >
          {creating ? <Loader2 size={16} className="animate-spin" /> : <UploadCloud size={16} />}
          创建并索引
        </Button>
      </form>
    </section>
  );
}
