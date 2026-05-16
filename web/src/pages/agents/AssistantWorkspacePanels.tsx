import { FileText, Loader2 } from "lucide-react";
import type { FormEventHandler } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FieldShell, SelectInput, TextInput } from "@/components/ui/Field";
import type { SparkBotChannelSchema, SparkBotFile } from "@/lib/types";
import {
  ChannelEditor,
  FileEditor,
  GlobalChannelEditor,
} from "./AgentWorkspaceEditors";
import { assistantWorkspaceFileMeta } from "./agentWorkspaceFiles";
import { isRecord } from "./assistantHistoryUtils";

export function AssistantChannelPanel({
  activeBotId,
  running,
  globalSchema,
  channelSchemas,
  channelKeys,
  activeChannel,
  channels,
  loading = false,
  pending,
  onChannelSelect,
  onSaveGlobal,
  onSaveChannel,
}: {
  activeBotId: string | null;
  running: boolean;
  globalSchema?: Partial<SparkBotChannelSchema>;
  channelSchemas: Record<string, SparkBotChannelSchema>;
  channelKeys: string[];
  activeChannel: string;
  channels?: Record<string, unknown>;
  loading?: boolean;
  pending: boolean;
  onChannelSelect: (channel: string) => void;
  onSaveGlobal: (config: Record<string, unknown>) => Promise<void>;
  onSaveChannel: (config: Record<string, unknown>) => Promise<void>;
}) {
  const channelSchema = channelSchemas[activeChannel];
  const currentChannelConfig = channels && isRecord(channels[activeChannel]) ? channels[activeChannel] : undefined;
  return (
    <section className="rounded-lg border border-line bg-white p-3" data-testid="sparkbot-channel-toggle">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-ink">渠道与多模态</h2>
          <p className="mt-1 text-sm text-slate-500">连接 Web、语音转写、外部消息渠道和后续多模态入口。</p>
        </div>
        <Badge tone={running ? "success" : "neutral"}>{running ? "运行中" : "停止"}</Badge>
      </div>
      <div className="mt-4 grid gap-3 border-t border-line pt-4">
        <p className="text-sm text-slate-500">{activeBotId || "选择一个助教。"}</p>
        {globalSchema ? (
          <GlobalChannelEditor
            key={`${activeBotId}-global-channels`}
            schema={globalSchema}
            currentChannels={channels}
            pending={pending}
            onSave={onSaveGlobal}
          />
        ) : null}
        <FieldShell label="渠道">
          <SelectInput value={activeChannel} onChange={(event) => onChannelSelect(event.target.value)}>
            {channelKeys.map((key) => (
              <option key={key} value={key}>
                {channelSchemas[key]?.display_name || key}
              </option>
            ))}
          </SelectInput>
        </FieldShell>
        {loading ? (
          <p className="rounded-lg bg-canvas p-4 text-sm text-slate-500">正在读取渠道配置...</p>
        ) : channelSchema ? (
          <ChannelEditor
            key={`${activeBotId}-${activeChannel}`}
            schema={channelSchema}
            currentConfig={currentChannelConfig}
            pending={pending}
            onSave={onSaveChannel}
          />
        ) : (
          <p className="rounded-lg bg-canvas p-4 text-sm text-slate-500">暂无可用渠道字段。</p>
        )}
      </div>
    </section>
  );
}

export function AssistantWorkspaceFilesPanel({
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
}: {
  files: SparkBotFile[];
  activeBotId: string | null;
  activeFileName: string | null;
  activeFile?: SparkBotFile;
  fallbackContent?: string;
  newFileName: string;
  pending: boolean;
  loading: boolean;
  onNewFileNameChange: (value: string) => void;
  onCreateFile: FormEventHandler<HTMLFormElement>;
  onSelectFile: (filename: string) => void;
  onSaveFile: (content: string) => Promise<unknown>;
}) {
  const courseFileCount = files.filter((file) => assistantWorkspaceFileMeta(file.filename).label === "课程资料").length;
  return (
    <section className="rounded-lg border border-line bg-white p-3" data-testid="sparkbot-files-toggle">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-ink">资料与助教笔记</h2>
          <p className="mt-1 text-sm text-slate-500">编辑课程设定、学习笔记和助教会长期参考的工作文件。</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="success">{courseFileCount} 个课程资料</Badge>
          <Badge tone="neutral">{files.length}</Badge>
        </div>
      </div>
      <form className="mt-4 grid gap-2 border-t border-line pt-4 sm:grid-cols-[minmax(0,1fr)_auto]" onSubmit={onCreateFile}>
        <TextInput
          value={newFileName}
          onChange={(event) => onNewFileNameChange(event.target.value)}
          placeholder="COURSE.md / NOTES.md"
          data-testid="sparkbot-new-file-name"
        />
        <Button
          tone="secondary"
          type="submit"
          disabled={!activeBotId || !newFileName.trim() || pending}
          data-testid="sparkbot-new-file-create"
        >
          {pending ? <Loader2 size={16} className="animate-spin" /> : <FileText size={16} />}
          创建/打开
        </Button>
      </form>
      <div className="mt-4 grid gap-3 lg:grid-cols-[240px_minmax(0,1fr)]">
        <div className="max-h-96 space-y-2 overflow-y-auto pr-1">
          {files.map((file) => {
            const meta = assistantWorkspaceFileMeta(file.filename);
            return (
              <button
                key={file.filename}
                type="button"
                data-testid={`sparkbot-file-${file.filename}`}
                onClick={() => onSelectFile(file.filename)}
                className={`w-full rounded-lg border px-3 py-2 text-left text-sm transition ${
                  activeFileName === file.filename ? "border-brand-purple-300 bg-tint-lavender text-brand-purple" : "border-line bg-white text-slate-600 hover:border-brand-purple-300"
                }`}
              >
                <span className="flex items-start gap-2">
                  <FileText size={15} className="mt-0.5 shrink-0" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{file.filename}</span>
                    <span className="mt-1 block line-clamp-2 text-xs leading-5 text-slate-500">{meta.detail}</span>
                  </span>
                </span>
                <span className="mt-2 inline-flex">
                  <Badge tone={meta.tone}>{meta.label}</Badge>
                </span>
              </button>
            );
          })}
          {!files.length ? <p className="rounded-lg bg-canvas p-3 text-sm text-slate-500">暂无可编辑文件。</p> : null}
        </div>
        {activeBotId && activeFileName ? (
          <FileEditor
            key={`${activeBotId}-${activeFileName}-${activeFile?.content?.length ?? 0}`}
            botId={activeBotId}
            filename={activeFileName}
            file={activeFile}
            fallbackContent={fallbackContent}
            pending={pending || loading}
            onSave={onSaveFile}
          />
        ) : (
          <div className="rounded-lg border border-dashed border-line bg-canvas p-6 text-sm text-slate-500">
            选择文件后可以直接编辑并保存。
          </div>
        )}
      </div>
    </section>
  );
}
