import { FileText, Loader2, Plus, Save, Server, Trash2, Upload } from "lucide-react";
import type { FormEvent } from "react";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FieldShell, SelectInput, TextArea, TextInput } from "@/components/ui/Field";
import { useSparkBotSkill, useSparkBotSkills } from "@/hooks/api/sparkbot";
import type { SparkBotSkill } from "@/lib/types";

type SkillsManagerPanelProps = {
  botId: string;
  pending: boolean;
  onSave: (skillName: string, content: string) => Promise<unknown>;
  onUpload: (file: File, skillName?: string) => Promise<unknown>;
};

export function SkillsManagerPanel({ botId, pending, onSave, onUpload }: SkillsManagerPanelProps) {
  const skills = useSparkBotSkills(botId, { enabled: Boolean(botId) });
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const effectiveSelectedName = selectedName === null ? skills.data?.[0]?.name ?? "" : selectedName;
  const selectedSkill = useSparkBotSkill(botId, effectiveSelectedName || null, { enabled: Boolean(botId && effectiveSelectedName) });
  const [uploadName, setUploadName] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState("");
  const [uploadSaved, setUploadSaved] = useState(false);

  const submitUpload = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!uploadFile) {
      setUploadError("请选择一个技能 Markdown 文件或 zip 包。");
      return;
    }
    try {
      setUploadError("");
      setUploadSaved(false);
      const result = (await onUpload(uploadFile, uploadName.trim() || undefined)) as SparkBotSkill | undefined;
      setUploadFile(null);
      setUploadName("");
      if (result?.name) setSelectedName(result.name);
      setUploadSaved(true);
      void skills.refetch();
    } catch (uploadError) {
      setUploadError(uploadError instanceof Error ? uploadError.message : "上传技能文件失败。");
    }
  };

  return (
    <section className="rounded-lg border border-line bg-white p-3" data-testid="sparkbot-skills-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <FileText size={18} className="text-brand-purple" />
          <h2 className="text-base font-semibold text-ink">助教技能</h2>
        </div>
        <Badge tone="neutral">{skills.data?.length ?? 0}</Badge>
      </div>

      <form className="mt-4 grid gap-2 border-t border-line pt-4" onSubmit={submitUpload}>
        <FieldShell label="上传技能文件" hint="支持单个 Markdown 文件，或包含技能文件的 zip 包">
          <input
            type="file"
            accept=".md,.zip"
            onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
            className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border file:border-line file:bg-canvas file:px-3 file:py-2 file:text-sm file:font-medium file:text-ink"
            data-testid="sparkbot-skill-upload-file"
          />
        </FieldShell>
        <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
          <TextInput value={uploadName} onChange={(event) => setUploadName(event.target.value)} placeholder="可选：技能名称" data-testid="sparkbot-skill-upload-name" />
          <Button tone="secondary" type="submit" disabled={pending || !uploadFile} data-testid="sparkbot-skill-upload-submit">
            {pending ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
            上传
          </Button>
        </div>
        {uploadError ? <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-brand-red">{uploadError}</p> : null}
        {uploadSaved ? <p className="text-sm text-emerald-700">已上传。</p> : null}
      </form>

      <div className="mt-4 flex max-h-36 flex-wrap gap-2 overflow-y-auto">
        {(skills.data ?? []).map((skill) => (
          <button
            key={`${skill.source}-${skill.name}`}
            type="button"
            onClick={() => setSelectedName(skill.name)}
            className={`rounded-lg border px-3 py-2 text-left text-sm transition ${
              effectiveSelectedName === skill.name ? "border-brand-purple-300 bg-tint-lavender text-brand-purple" : "border-line bg-white text-slate-600 hover:border-brand-purple-300"
            }`}
            data-testid={`sparkbot-skill-${skill.name}`}
          >
            <span className="block font-medium">{skill.name}</span>
            <span className="mt-1 block max-w-52 truncate text-xs text-slate-500">{skill.description || "可被助教调用"}</span>
            <span className="mt-1 block text-xs text-slate-500">{formatSkillSource(skill.source)} · {skill.available === false ? "缺依赖" : "可用"}</span>
          </button>
        ))}
        {!skills.data?.length && !skills.isFetching ? (
          <p className="rounded-lg border border-dashed border-line bg-canvas p-3 text-sm text-slate-500">还没有助教技能。上传或新建一个，用来写明提醒、复盘和群聊回复能力。</p>
        ) : null}
      </div>

      <SkillEditor
        key={effectiveSelectedName || "__new_skill__"}
        selectedSkill={selectedSkill.data}
        isNew={!effectiveSelectedName}
        pending={pending}
        onNew={() => setSelectedName("")}
        onSave={async (skillName, content) => {
          await onSave(skillName, content);
          setSelectedName(skillName);
          void skills.refetch();
        }}
      />
    </section>
  );
}

type SkillEditorProps = {
  selectedSkill?: SparkBotSkill;
  isNew: boolean;
  pending: boolean;
  onNew: () => void;
  onSave: (skillName: string, content: string) => Promise<unknown>;
};

function SkillEditor({ selectedSkill, isNew, pending, onNew, onSave }: SkillEditorProps) {
  const initialName = isNew ? "daily-review" : selectedSkill?.name || "daily-review";
  const [skillName, setSkillName] = useState(initialName);
  const [content, setContent] = useState(selectedSkill?.content || defaultSkillContent(initialName));
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  const submitSave = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!skillName.trim() || !content.trim()) {
      setError("技能名称和内容不能为空。");
      return;
    }
    try {
      setError("");
      setSaved(false);
      await onSave(skillName.trim(), content);
      setSaved(true);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "保存技能失败。");
    }
  };

  return (
    <form className="mt-4 grid gap-3 border-t border-line pt-4" onSubmit={submitSave}>
      <FieldShell label="技能名称">
        <TextInput value={skillName} onChange={(event) => setSkillName(event.target.value)} data-testid="sparkbot-skill-name" />
      </FieldShell>
      <FieldShell label="技能内容">
        <TextArea value={content} onChange={(event) => setContent(event.target.value)} className="min-h-48 font-mono text-xs" data-testid="sparkbot-skill-content" />
      </FieldShell>
      {selectedSkill?.missing_requirements ? (
        <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-700">{selectedSkill.missing_requirements}</p>
      ) : null}
      {error ? <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-brand-red">{error}</p> : null}
      {saved ? <p className="text-sm text-emerald-700">已保存。</p> : null}
      <div className="flex flex-wrap gap-2">
        <Button
          tone="secondary"
          type="button"
          onClick={() => {
            onNew();
            setSkillName("daily-review");
            setContent(defaultSkillContent("daily-review"));
            setError("");
            setSaved(false);
          }}
        >
          <Plus size={16} />
          新建
        </Button>
        <Button tone="primary" type="submit" disabled={pending || !skillName.trim() || !content.trim()} data-testid="sparkbot-skill-save">
          {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
          保存技能
        </Button>
      </div>
    </form>
  );
}

type McpServersEditorProps = {
  tools: Record<string, unknown>;
  pending: boolean;
  onSave: (tools: Record<string, unknown>) => Promise<unknown>;
};

export function McpServersEditor({ tools, pending, onSave }: McpServersEditorProps) {
  const servers = getMcpServers(tools);
  const [draft, setDraft] = useState(defaultMcpDraft());
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      const name = draft.name.trim();
      if (!name) throw new Error("服务名称不能为空。");
      const config = buildMcpServerConfig(draft);
      setError("");
      setSaved(false);
      await onSave(withMcpServers(tools, { ...servers, [name]: config }));
      setSaved(true);
    } catch (submitError) {
      setSaved(false);
      setError(submitError instanceof Error ? submitError.message : "保存外部服务失败。");
    }
  };

  const remove = async (name: string) => {
    const next = { ...servers };
    delete next[name];
    setSaved(false);
    await onSave(withMcpServers(tools, next));
    setSaved(true);
    if (draft.name === name) setDraft(defaultMcpDraft());
  };

  return (
    <section className="rounded-lg border border-line bg-white p-3" data-testid="sparkbot-mcp-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <Server size={18} className="text-brand-purple" />
          <h2 className="text-base font-semibold text-ink">外部服务</h2>
        </div>
        <Badge tone="neutral">{Object.keys(servers).length}</Badge>
      </div>

      <div className="mt-4 grid gap-2 border-t border-line pt-4">
        {Object.entries(servers).map(([name, config]) => (
          <div key={name} className="rounded-lg border border-line bg-canvas p-3">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-ink">{name}</p>
                <p className="mt-1 text-xs leading-5 text-slate-500">{formatMcpServer(config)}</p>
              </div>
              <div className="flex gap-2">
                <Button tone="quiet" className="min-h-8 px-2 text-xs" onClick={() => setDraft(mcpDraftFromConfig(name, config))}>
                  编辑
                </Button>
                <Button tone="danger" className="min-h-8 px-2 text-xs" onClick={() => void remove(name)} disabled={pending}>
                  <Trash2 size={14} />
                </Button>
              </div>
            </div>
          </div>
        ))}
        {!Object.keys(servers).length ? (
          <p className="rounded-lg border border-dashed border-line bg-canvas p-3 text-sm text-slate-500">还没有外部服务。添加后助教可在提醒和群聊回复中调用。</p>
        ) : null}
      </div>

      <form className="mt-4 grid gap-3 border-t border-line pt-4" onSubmit={submit}>
        <div className="grid gap-3 sm:grid-cols-2">
          <FieldShell label="名称">
            <TextInput value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} data-testid="sparkbot-mcp-name" />
          </FieldShell>
          <FieldShell label="类型">
            <SelectInput value={draft.type} onChange={(event) => setDraft({ ...draft, type: event.target.value as McpServerDraft["type"] })} data-testid="sparkbot-mcp-type">
              <option value="stdio">本地命令</option>
              <option value="sse">实时连接</option>
              <option value="streamableHttp">HTTP 连接</option>
            </SelectInput>
          </FieldShell>
        </div>

        {draft.type === "stdio" ? (
          <>
            <FieldShell label="本地命令">
              <TextInput value={draft.command} onChange={(event) => setDraft({ ...draft, command: event.target.value })} placeholder="npx / uvx / python" data-testid="sparkbot-mcp-command" />
            </FieldShell>
            <FieldShell label="启动选项">
              <TextInput value={draft.args} onChange={(event) => setDraft({ ...draft, args: event.target.value })} placeholder="-y @modelcontextprotocol/server-filesystem ." data-testid="sparkbot-mcp-args" />
            </FieldShell>
          </>
        ) : (
          <FieldShell label="服务地址">
            <TextInput value={draft.url} onChange={(event) => setDraft({ ...draft, url: event.target.value })} placeholder="http://127.0.0.1:3000/mcp" data-testid="sparkbot-mcp-url" />
          </FieldShell>
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          <FieldShell label="本地运行信息">
            <TextArea value={draft.env} onChange={(event) => setDraft({ ...draft, env: event.target.value })} className="min-h-20 font-mono text-xs" />
          </FieldShell>
          <FieldShell label="连接请求信息">
            <TextArea value={draft.headers} onChange={(event) => setDraft({ ...draft, headers: event.target.value })} className="min-h-20 font-mono text-xs" />
          </FieldShell>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <FieldShell label="超时秒数">
            <TextInput value={draft.toolTimeout} onChange={(event) => setDraft({ ...draft, toolTimeout: event.target.value })} inputMode="numeric" />
          </FieldShell>
          <FieldShell label="允许使用">
            <TextInput value={draft.enabledTools} onChange={(event) => setDraft({ ...draft, enabledTools: event.target.value })} placeholder="* 或 tool_a,tool_b" />
          </FieldShell>
        </div>

        {error ? <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-brand-red">{error}</p> : null}
        {saved ? <p className="text-sm text-emerald-700">外部服务已保存。</p> : null}
        <div className="flex flex-wrap gap-2">
          <Button tone="secondary" type="button" onClick={() => setDraft(defaultMcpDraft())}>
            <Plus size={16} />
            新建
          </Button>
          <Button tone="primary" type="submit" disabled={pending} data-testid="sparkbot-mcp-save">
            {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            保存外部服务
          </Button>
        </div>
      </form>
    </section>
  );
}

function defaultSkillContent(name: string) {
  return `---
description: ${name}
always: false
---

# ${name}

课程助教需要这个技能时使用。

## 能力
- 触发场景：
- 可读取资料：
- 输出结果：`;
}

function formatSkillSource(value?: string) {
  const normalized = String(value || "").trim();
  if (!normalized || normalized === "workspace") return "工作区";
  if (normalized === "builtin") return "内置";
  if (normalized === "upload") return "上传";
  return normalized;
}

type McpServerDraft = {
  name: string;
  type: "stdio" | "sse" | "streamableHttp";
  command: string;
  args: string;
  url: string;
  env: string;
  headers: string;
  toolTimeout: string;
  enabledTools: string;
};

function defaultMcpDraft(): McpServerDraft {
  return {
    name: "filesystem",
    type: "stdio",
    command: "npx",
    args: "-y @modelcontextprotocol/server-filesystem .",
    url: "",
    env: "{}",
    headers: "{}",
    toolTimeout: "30",
    enabledTools: "*",
  };
}

function getMcpServers(tools: Record<string, unknown>) {
  const raw = tools.mcpServers ?? tools.mcp_servers;
  return isRecord(raw) ? (raw as Record<string, Record<string, unknown>>) : {};
}

function withMcpServers(tools: Record<string, unknown>, servers: Record<string, Record<string, unknown>>) {
  const next = { ...tools };
  delete next.mcp_servers;
  return { ...next, mcpServers: servers };
}

function mcpDraftFromConfig(name: string, config: Record<string, unknown>): McpServerDraft {
  return {
    name,
    type: config.type === "sse" || config.type === "streamableHttp" ? config.type : "stdio",
    command: String(config.command ?? ""),
    args: Array.isArray(config.args) ? config.args.map(String).join(" ") : "",
    url: String(config.url ?? ""),
    env: JSON.stringify(isRecord(config.env) ? config.env : {}, null, 2),
    headers: JSON.stringify(isRecord(config.headers) ? config.headers : {}, null, 2),
    toolTimeout: String(config.toolTimeout ?? config.tool_timeout ?? 30),
    enabledTools: Array.isArray(config.enabledTools)
      ? config.enabledTools.map(String).join(",")
      : Array.isArray(config.enabled_tools)
        ? config.enabled_tools.map(String).join(",")
        : "*",
  };
}

function buildMcpServerConfig(draft: McpServerDraft) {
  const env = parseJsonObject(draft.env, "本地运行信息");
  const headers = parseJsonObject(draft.headers, "连接请求信息");
  const toolTimeout = Number(draft.toolTimeout || 30);
  if (!Number.isFinite(toolTimeout) || toolTimeout <= 0) throw new Error("超时秒数必须大于 0。");
  const enabledTools = splitEnabledTools(draft.enabledTools);
  if (draft.type === "stdio") {
    if (!draft.command.trim()) throw new Error("本地命令服务必须填写命令。");
    return {
      type: "stdio",
      command: draft.command.trim(),
      args: splitArgs(draft.args),
      env,
      headers,
      toolTimeout,
      enabledTools,
    };
  }
  if (!draft.url.trim()) throw new Error("远程服务必须填写 URL。");
  return {
    type: draft.type,
    url: draft.url.trim(),
    command: "",
    args: [],
    env,
    headers,
    toolTimeout,
    enabledTools,
  };
}

function formatMcpServer(config: Record<string, unknown>) {
  const type = String(config.type || "stdio");
  if (type === "stdio") return `本地命令 · ${String(config.command || "")} ${Array.isArray(config.args) ? config.args.join(" ") : ""}`.trim();
  if (type === "sse") return `实时连接 · ${String(config.url || "")}`;
  return `HTTP 连接 · ${String(config.url || "")}`;
}

function parseJsonObject(value: string, label: string) {
  const trimmed = value.trim();
  if (!trimmed) return {};
  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmed) as unknown;
  } catch {
    throw new Error(`${label}格式有误，请检查括号和逗号。`);
  }
  if (!isRecord(parsed)) throw new Error(`${label}必须是结构化对象。`);
  return parsed;
}

function splitArgs(value: string) {
  return value.trim() ? value.trim().split(/\s+/).filter(Boolean) : [];
}

function splitEnabledTools(value: string) {
  const items = value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  return items.length ? items : ["*"];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}
