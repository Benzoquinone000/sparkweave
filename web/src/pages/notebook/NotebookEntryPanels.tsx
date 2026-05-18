import { AnimatePresence, motion } from "framer-motion";
import { ChevronLeft, FileText, Loader2, Plus, Save } from "lucide-react";
import type { FormEvent } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FieldShell, TextArea, TextInput } from "@/components/ui/Field";
import { NOTEBOOK_LIMITS } from "@/lib/requestLimits";

export function CreateNotebookPanel({
  name,
  description,
  pending,
  onNameChange,
  onDescriptionChange,
  onBack,
  onSubmit,
}: {
  name: string;
  description: string;
  pending: boolean;
  onNameChange: (value: string) => void;
  onDescriptionChange: (value: string) => void;
  onBack: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void | Promise<void>;
}) {
  return (
    <motion.section
      key="create-notebook"
      className="rounded-lg border border-line bg-white p-4"
      initial={{ opacity: 0, x: 14 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -10 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
    >
      <Button tone="quiet" className="mb-4 min-h-8 px-2 text-xs" onClick={onBack}>
        <ChevronLeft size={14} />
        返回记录本
      </Button>
      <div>
        <Badge tone="brand">新建</Badge>
        <h2 className="mt-3 text-lg font-semibold text-ink">创建一个记录本</h2>
        <p className="mt-1 text-sm leading-6 text-slate-500">只需要填写名称。描述可以简单写清楚这里准备用来沉淀什么。</p>
      </div>
      <form className="mt-5 grid gap-3" onSubmit={onSubmit}>
        <FieldShell label="名称">
          <TextInput
            value={name}
            onChange={(event) => onNameChange(event.target.value)}
            maxLength={NOTEBOOK_LIMITS.name}
            placeholder="例如 高数错题复盘"
            data-testid="notebook-create-name"
          />
        </FieldShell>
        <FieldShell label="描述">
          <TextArea
            value={description}
            onChange={(event) => onDescriptionChange(event.target.value)}
            maxLength={NOTEBOOK_LIMITS.description}
          placeholder="这个记录本打算沉淀什么？"
            data-testid="notebook-create-description"
          />
        </FieldShell>
        <Button tone="primary" type="submit" disabled={!name.trim() || pending} data-testid="notebook-create-submit">
          {pending ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
          创建记录本
        </Button>
      </form>
    </motion.section>
  );
}

export function ManualRecordPanel({
  notebookName,
  hasNotebook,
  title,
  output,
  summaryPreview,
  addPending,
  summaryPending,
  onTitleChange,
  onOutputChange,
  onBack,
  onSubmit,
}: {
  notebookName: string;
  hasNotebook: boolean;
  title: string;
  output: string;
  summaryPreview: string;
  addPending: boolean;
  summaryPending: boolean;
  onTitleChange: (value: string) => void;
  onOutputChange: (value: string) => void;
  onBack: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void | Promise<void>;
}) {
  const disabled = !hasNotebook || !title.trim() || !output.trim();

  return (
    <motion.section
      key="manual-record"
      className="rounded-lg border border-line bg-white p-4"
      initial={{ opacity: 0, x: 14 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -10 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
    >
      <Button tone="quiet" className="mb-4 min-h-8 px-2 text-xs" onClick={onBack}>
        <ChevronLeft size={14} />
        返回记录本
      </Button>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Badge tone={hasNotebook ? "brand" : "neutral"}>{notebookName || "未选择记录本"}</Badge>
          <h2 className="mt-3 text-lg font-semibold text-ink">补充一条学习记录</h2>
          <p className="mt-1 text-sm leading-6 text-slate-500">适合补课堂笔记、错因、复盘结论。写完后会进入当前记录本。</p>
        </div>
      </div>
      <form className="mt-5 grid gap-3" onSubmit={onSubmit}>
        <FieldShell label="标题">
          <TextInput
            value={title}
            onChange={(event) => onTitleChange(event.target.value)}
            maxLength={NOTEBOOK_LIMITS.title}
            placeholder="本次复盘主题"
            data-testid="notebook-manual-title"
          />
        </FieldShell>
        <FieldShell label="内容">
          <TextArea
            value={output}
            onChange={(event) => onOutputChange(event.target.value)}
            maxLength={NOTEBOOK_LIMITS.output}
            placeholder="关键推理、错因、小结..."
            className="min-h-44"
            data-testid="notebook-manual-output"
          />
        </FieldShell>
        <div className="flex flex-wrap gap-2">
          <Button
            tone="secondary"
            type="submit"
            disabled={disabled || addPending}
            data-testid="notebook-manual-submit"
          >
            {addPending ? <Loader2 size={16} className="animate-spin" /> : <FileText size={16} />}
            直接写入
          </Button>
          <Button
            tone="primary"
            type="submit"
            data-action="with-summary"
            disabled={disabled || summaryPending}
            data-testid="notebook-manual-summary-submit"
          >
            {summaryPending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            生成摘要并写入
          </Button>
        </div>
        <AnimatePresence>
          {summaryPreview ? (
            <motion.p
              className="rounded-lg border border-brand-purple-300 bg-tint-lavender p-3 text-sm leading-6 text-slate-600"
              data-testid="notebook-summary-preview"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.18 }}
            >
              {summaryPreview}
            </motion.p>
          ) : null}
        </AnimatePresence>
      </form>
    </motion.section>
  );
}
