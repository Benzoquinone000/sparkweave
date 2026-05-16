import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, ChevronUp, Edit3, ExternalLink, Loader2, Save, Trash2, X } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FieldShell, TextArea, TextInput } from "@/components/ui/Field";
import type { NotebookDetail, NotebookRecord } from "@/lib/types";

import { RecordAssetPreview } from "./RecordAssetPreview";
import { getRecordAsset } from "./recordAssetUtils";

type NotebookMetaPayload = {
  name: string;
  description: string;
  color: string;
  icon: string;
};

type RecordPayload = {
  title: string;
  summary: string;
  user_query: string;
  output: string;
};

export function NotebookMetaEditor({
  notebook,
  pending,
  onSave,
}: {
  notebook: NotebookDetail;
  pending: boolean;
  onSave: (payload: NotebookMetaPayload) => Promise<unknown>;
}) {
  const [name, setName] = useState(notebook.name || "");
  const [description, setDescription] = useState(notebook.description || "");

  return (
    <form
      className="mt-4 border-t border-line pt-4"
      onSubmit={(event) => {
        event.preventDefault();
        void onSave({
          name: name.trim(),
          description: description.trim(),
          color: notebook.color || "#0F766E",
          icon: notebook.icon || "book",
        });
      }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-ink">笔记本信息</h3>
          <p className="mt-1 text-sm text-slate-500">更新名称和描述后，列表、详情和保存入口会同步使用新信息。</p>
        </div>
        <Button tone="primary" type="submit" disabled={!name.trim() || pending} data-testid="notebook-meta-save">
          {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
          保存信息
        </Button>
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-[240px_minmax(0,1fr)]">
        <FieldShell label="名称">
          <TextInput value={name} onChange={(event) => setName(event.target.value)} data-testid="notebook-meta-name" />
        </FieldShell>
        <FieldShell label="描述">
          <TextInput value={description} onChange={(event) => setDescription(event.target.value)} data-testid="notebook-meta-description" />
        </FieldShell>
      </div>
    </form>
  );
}

export function RecordCard({
  record,
  active,
  onEdit,
  onDelete,
}: {
  record: NotebookRecord;
  active: boolean;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const sessionTarget = sessionTargetForRecord(record);
  const asset = getRecordAsset(record);
  const [expanded, setExpanded] = useState(Boolean(active && asset.hasPreview));
  const recordKey = String(record.id || record.record_id || "");

  return (
    <article
      className={`dt-interactive rounded-lg border px-4 py-3 ${active ? "border-brand-purple-300 bg-tint-lavender" : "border-line bg-white hover:border-brand-purple-300"}`}
      data-testid={recordKey ? `notebook-record-${recordKey}` : undefined}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="brand">{record.record_type}</Badge>
        {asset.kind ? <Badge tone="neutral">{asset.kind}</Badge> : null}
        {record.kb_name ? <Badge tone="neutral">{record.kb_name}</Badge> : null}
        <div className="ml-auto flex gap-2">
          {sessionTarget ? (
            <Button tone="quiet" className="min-h-8 px-2 text-xs" onClick={() => window.location.assign(sessionTarget)}>
              <ExternalLink size={14} />
              打开会话
            </Button>
          ) : null}
          {asset.hasPreview ? (
            <Button tone="quiet" className="min-h-8 px-2 text-xs" onClick={() => setExpanded((value) => !value)}>
              {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              {expanded ? "收起资产" : "预览资产"}
            </Button>
          ) : null}
          <Button
            tone="quiet"
            className="min-h-8 px-2 text-xs"
            onClick={onEdit}
            data-testid={recordKey ? `notebook-record-edit-${recordKey}` : undefined}
          >
            <Edit3 size={14} />
            编辑
          </Button>
          <Button
            tone="danger"
            className="min-h-8 px-2 text-xs"
            onClick={onDelete}
            data-testid={recordKey ? `notebook-record-delete-${recordKey}` : undefined}
          >
            <Trash2 size={14} />
            删除
          </Button>
        </div>
      </div>
      <h3 className="mt-3 font-semibold text-ink">{record.title}</h3>
      <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-600">{record.summary || record.output || "暂无内容"}</p>
      <AnimatePresence initial={false}>
        {expanded && asset.hasPreview ? (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
          >
            <RecordAssetPreview record={record} asset={asset} />
          </motion.div>
        ) : null}
      </AnimatePresence>
    </article>
  );
}

export function RecordEditor({
  record,
  pending,
  onCancel,
  onSave,
}: {
  record: NotebookRecord;
  pending: boolean;
  onCancel: () => void;
  onSave: (payload: RecordPayload) => Promise<void>;
}) {
  const [title, setTitle] = useState(record.title);
  const [summary, setSummary] = useState(record.summary || "");
  const [userQuery, setUserQuery] = useState(record.user_query || "");
  const [output, setOutput] = useState(record.output || "");

  return (
    <section className="rounded-lg border border-line bg-white p-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-ink">编辑记录</h2>
        <Button tone="quiet" onClick={onCancel}>
          <X size={16} />
          关闭
        </Button>
      </div>
      <form
        className="mt-4 grid gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          void onSave({ title, summary, user_query: userQuery, output });
        }}
      >
        <FieldShell label="标题">
          <TextInput value={title} onChange={(event) => setTitle(event.target.value)} data-testid="record-editor-title" />
        </FieldShell>
        <FieldShell label="摘要">
          <TextArea value={summary} onChange={(event) => setSummary(event.target.value)} data-testid="record-editor-summary" />
        </FieldShell>
        <FieldShell label="用户问题">
          <TextArea value={userQuery} onChange={(event) => setUserQuery(event.target.value)} data-testid="record-editor-user-query" />
        </FieldShell>
        <FieldShell label="输出">
          <TextArea
            value={output}
            onChange={(event) => setOutput(event.target.value)}
            className="min-h-56"
            data-testid="record-editor-output"
          />
        </FieldShell>
        <Button tone="primary" type="submit" disabled={!title.trim() || pending} data-testid="record-editor-save">
          {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
          保存记录
        </Button>
      </form>
    </section>
  );
}

function sessionTargetForRecord(record: NotebookRecord) {
  const sessionId = typeof record.metadata?.session_id === "string" ? record.metadata.session_id : "";
  if (!sessionId) return null;
  const type = record.record_type || record.type;
  return type === "guided_learning" ? `/guide?session=${encodeURIComponent(sessionId)}` : `/chat/${encodeURIComponent(sessionId)}`;
}
