import { FileText, Loader2, Save, Settings2 } from "lucide-react";
import type { FormEvent } from "react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FieldShell, TextArea, TextInput } from "@/components/ui/Field";
import type { SparkBotFile, SparkBotSummary } from "@/lib/types";

type WorkspaceFilesPanelProps = {
  files: SparkBotFile[];
  activeBotId: string | null;
  activeFileName: string | null;
  activeFile?: SparkBotFile;
  fallbackContent?: string;
  newFileName: string;
  pending: boolean;
  loading: boolean;
  onNewFileNameChange: (value: string) => void;
  onCreateFile: (event: FormEvent<HTMLFormElement>) => void;
  onSelectFile: (filename: string) => void;
  onSaveFile: (content: string) => Promise<unknown>;
};

export function WorkspaceFilesPanel({
  files,
  activeBotId,
  activeFileName,
  activeFile,
  fallbackContent,
  newFileName,
  pending,
  loading,
  onNewFileNameChange,
  onCreateFile,
  onSelectFile,
  onSaveFile,
}: WorkspaceFilesPanelProps) {
  const editorContent = activeFile?.content ?? fallbackContent ?? "";

  return (
    <section className="rounded-lg border border-line bg-white p-3" data-testid="sparkbot-files-toggle">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <FileText size={18} className="text-brand-purple" />
          <h2 className="text-base font-semibold text-ink">课程资料文件</h2>
        </div>
        <Badge tone="neutral">{files.length}</Badge>
      </div>
      <form className="mt-4 grid gap-2 border-t border-line pt-4 sm:grid-cols-[minmax(0,1fr)_auto]" onSubmit={onCreateFile}>
        <TextInput value={newFileName} onChange={(event) => onNewFileNameChange(event.target.value)} placeholder="SOUL.md / TOOLS.md / HEARTBEAT.md" data-testid="sparkbot-new-file-name" />
        <Button tone="secondary" type="submit" disabled={!activeBotId || !newFileName.trim() || pending} data-testid="sparkbot-new-file-create">
          {pending ? <Loader2 size={16} className="animate-spin" /> : <FileText size={16} />}
          创建/打开
        </Button>
      </form>
      <div className="mt-4 grid gap-3 lg:grid-cols-[220px_minmax(0,1fr)]">
        <div className="max-h-96 space-y-2 overflow-y-auto pr-1">
          {files.map((file) => (
            <button
              key={file.filename}
              type="button"
              data-testid={`sparkbot-file-${file.filename}`}
              onClick={() => onSelectFile(file.filename)}
              className={`w-full rounded-lg border px-3 py-2 text-left text-sm transition ${
                activeFileName === file.filename ? "border-brand-purple-300 bg-tint-lavender text-brand-purple" : "border-line bg-white text-slate-600 hover:border-brand-purple-300"
              }`}
            >
              {file.filename}
            </button>
          ))}
        </div>
        {activeBotId && activeFileName ? (
          <WorkspaceFileEditor
            key={`${activeFileName}:${editorContent}`}
            filename={activeFileName}
            initialContent={editorContent}
            pending={pending}
            loading={loading}
            onSaveFile={onSaveFile}
          />
        ) : (
          <div className="rounded-lg border border-dashed border-line bg-canvas p-6 text-sm text-slate-500">选择一个文件后编辑。</div>
        )}
      </div>
    </section>
  );
}

type WorkspaceFileEditorProps = {
  filename: string;
  initialContent: string;
  pending: boolean;
  loading: boolean;
  onSaveFile: (content: string) => Promise<unknown>;
};

function WorkspaceFileEditor({ filename, initialContent, pending, loading, onSaveFile }: WorkspaceFileEditorProps) {
  const [draft, setDraft] = useState(initialContent);

  return (
    <form
      className="grid gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        void onSaveFile(draft);
      }}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-sm font-semibold text-ink">{filename}</p>
        <Button tone="primary" type="submit" disabled={pending || loading} data-testid="sparkbot-file-save">
          {pending || loading ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
          保存
        </Button>
      </div>
      <TextArea value={draft} onChange={(event) => setDraft(event.target.value)} className="min-h-60 font-mono text-xs" data-testid="sparkbot-file-content" />
    </form>
  );
}

type BotProfilePanelProps = {
  bot?: SparkBotSummary;
  pending: boolean;
  onSave: (payload: Partial<Pick<SparkBotSummary, "name" | "description" | "persona" | "model" | "auto_start">>) => Promise<unknown>;
};

export function BotProfilePanel({ bot, pending, onSave }: BotProfilePanelProps) {
  const formKey = bot ? [bot.bot_id, bot.name, bot.description, bot.model, bot.persona, String(Boolean(bot.auto_start))].join(":") : "empty";

  return (
    <section className="rounded-lg border border-line bg-white p-3" data-testid="bot-profile-editor">
      <div className="flex items-center gap-2" data-testid="bot-profile-toggle">
        <Settings2 size={18} className="text-brand-purple" />
        <h2 className="text-base font-semibold text-ink">助教基础设置</h2>
      </div>
      {bot ? (
        <BotProfileForm key={formKey} bot={bot} pending={pending} onSave={onSave} />
      ) : (
        <p className="mt-4 rounded-lg border border-dashed border-line bg-canvas p-4 text-sm text-slate-500">先选择一个助教。</p>
      )}
    </section>
  );
}

type BotProfileFormProps = {
  bot: SparkBotSummary;
  pending: boolean;
  onSave: (payload: Partial<Pick<SparkBotSummary, "name" | "description" | "persona" | "model" | "auto_start">>) => Promise<unknown>;
};

function BotProfileForm({ bot, pending, onSave }: BotProfileFormProps) {
  const [name, setName] = useState(bot?.name || "");
  const [description, setDescription] = useState(bot?.description || "");
  const [model, setModel] = useState(bot?.model || "");
  const [persona, setPersona] = useState(bot?.persona || "");
  const [autoStart, setAutoStart] = useState(Boolean(bot?.auto_start));

  return (
    <form
      className="mt-4 grid gap-3 border-t border-line pt-4"
      onSubmit={(event) => {
        event.preventDefault();
        void onSave({ name, description, model, persona, auto_start: autoStart });
      }}
    >
      <FieldShell label="名称">
        <TextInput value={name} onChange={(event) => setName(event.target.value)} data-testid="bot-profile-name" />
      </FieldShell>
      <FieldShell label="说明">
        <TextInput value={description} onChange={(event) => setDescription(event.target.value)} data-testid="bot-profile-description" />
      </FieldShell>
      <FieldShell label="使用模型">
        <TextInput value={model} onChange={(event) => setModel(event.target.value)} placeholder="继承全局模型" data-testid="bot-profile-model" />
      </FieldShell>
      <label className="flex items-start gap-2 rounded-lg border border-line bg-canvas p-3 text-sm text-slate-600">
        <input
          type="checkbox"
          checked={autoStart}
          onChange={(event) => setAutoStart(event.target.checked)}
          className="mt-1"
          data-testid="bot-profile-auto-start"
        />
        <span>项目启动时自动启动这个助教</span>
      </label>
      <FieldShell label="助教设定">
        <TextArea value={persona} onChange={(event) => setPersona(event.target.value)} className="min-h-32" data-testid="bot-profile-persona" />
      </FieldShell>
      <Button tone="primary" type="submit" disabled={pending} data-testid="bot-profile-save">
        {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
        保存
      </Button>
    </form>
  );
}

type JsonEditorProps = {
  title: string;
  value: Record<string, unknown>;
  pending: boolean;
  testId?: string;
  onSave: (value: Record<string, unknown>) => Promise<unknown>;
};

export function JsonEditor({ title, value, pending, testId, onSave }: JsonEditorProps) {
  const initialDraft = useMemo(() => JSON.stringify(value, null, 2), [value]);

  return <JsonEditorDraft key={initialDraft} title={title} initialDraft={initialDraft} pending={pending} testId={testId} onSave={onSave} />;
}

type JsonEditorDraftProps = {
  title: string;
  initialDraft: string;
  pending: boolean;
  testId?: string;
  onSave: (value: Record<string, unknown>) => Promise<unknown>;
};

function JsonEditorDraft({ title, initialDraft, pending, testId, onSave }: JsonEditorDraftProps) {
  const [draft, setDraft] = useState(initialDraft);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  return (
    <section className="rounded-lg border border-line bg-white p-3" data-testid={testId}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold text-ink">{title}</h2>
        <Button
          tone="primary"
          onClick={async () => {
            try {
              const parsed = JSON.parse(draft) as unknown;
              if (!isRecord(parsed)) throw new Error("内容必须是结构化对象。");
              setError("");
              setSaved(false);
              await onSave(parsed);
              setSaved(true);
            } catch (saveError) {
              setSaved(false);
              setError(
                saveError instanceof SyntaxError
                  ? "内容格式有误，请检查括号和逗号。"
                  : saveError instanceof Error
                    ? saveError.message
                    : "保存失败。",
              );
            }
          }}
          disabled={pending}
        >
          {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
          保存
        </Button>
      </div>
      <TextArea value={draft} onChange={(event) => setDraft(event.target.value)} className="mt-3 min-h-48 font-mono text-xs" />
      {error ? <p className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-brand-red">{error}</p> : null}
      {saved ? <p className="mt-3 text-sm text-emerald-700">已保存。</p> : null}
    </section>
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}
