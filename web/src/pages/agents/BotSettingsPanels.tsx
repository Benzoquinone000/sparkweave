import { Bot, Loader2, RefreshCw, Save, Wand2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FieldShell, TextArea, TextInput } from "@/components/ui/Field";
import type { SparkBotSummary } from "@/lib/types";

export function BotProfileEditor({
  bot,
  pending,
  onSave,
}: {
  bot?: SparkBotSummary;
  pending: boolean;
  onSave: (
    payload: Partial<Pick<SparkBotSummary, "name" | "description" | "persona" | "model" | "auto_start">>,
  ) => Promise<unknown>;
}) {
  return (
    <section className="rounded-lg border border-line bg-white p-3" data-testid="bot-profile-editor">
      <div className="flex flex-wrap items-start justify-between gap-3 rounded-lg bg-tint-lavender px-3 py-3" data-testid="bot-profile-toggle">
        <div>
          <div className="flex items-center gap-2">
            <Bot size={18} className="text-brand-purple" />
            <h2 className="text-base font-semibold text-ink">助教资料</h2>
          </div>
          <p className="mt-1 text-sm leading-6 text-slate-500">名称、模型和角色设定，按需编辑。</p>
        </div>
        <Badge tone={bot?.running ? "success" : "neutral"}>{bot?.running ? "运行中" : "停止"}</Badge>
      </div>
      <div className="mt-4 border-t border-line pt-4">
        {bot ? (
          <BotProfileForm key={bot.bot_id} bot={bot} pending={pending} onSave={onSave} />
        ) : (
          <p className="rounded-lg border border-dashed border-line bg-canvas p-4 text-sm text-slate-500">选择一个助教后可编辑资料。</p>
        )}
      </div>
    </section>
  );
}

function BotProfileForm({
  bot,
  pending,
  onSave,
}: {
  bot: SparkBotSummary;
  pending: boolean;
  onSave: (
    payload: Partial<Pick<SparkBotSummary, "name" | "description" | "persona" | "model" | "auto_start">>,
  ) => Promise<unknown>;
}) {
  const [name, setName] = useState(bot.name || "");
  const [description, setDescription] = useState(bot.description || "");
  const [model, setModel] = useState(bot.model || "");
  const [persona, setPersona] = useState(bot.persona || "");
  const [autoStart, setAutoStart] = useState(Boolean(bot.auto_start));
  const [saved, setSaved] = useState(false);

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await onSave({
      name: name.trim(),
      description: description.trim(),
      model: model.trim(),
      persona,
      auto_start: autoStart,
    });
    setSaved(true);
  };

  return (
    <form className="mt-4 grid gap-3 md:grid-cols-2" onSubmit={submit}>
      <FieldShell label="助教 ID">
        <TextInput value={bot.bot_id} readOnly />
      </FieldShell>
      <FieldShell label="名称">
        <TextInput value={name} onChange={(event) => setName(event.target.value)} data-testid="bot-profile-name" />
      </FieldShell>
      <FieldShell label="描述">
        <TextInput value={description} onChange={(event) => setDescription(event.target.value)} data-testid="bot-profile-description" />
      </FieldShell>
      <FieldShell label="模型">
        <TextInput value={model} onChange={(event) => setModel(event.target.value)} placeholder="继承全局模型" data-testid="bot-profile-model" />
      </FieldShell>
      <label className="dt-interactive flex items-start gap-3 rounded-lg border border-line bg-white p-3 text-sm text-slate-600 hover:border-brand-purple-300 md:col-span-2">
        <input
          type="checkbox"
          checked={autoStart}
          onChange={(event) => setAutoStart(event.target.checked)}
          className="mt-1"
          data-testid="bot-profile-auto-start"
        />
        <span>
          <span className="font-medium text-ink">自动启动</span>
          <span className="mt-1 block text-xs leading-5 text-slate-500">启动项目时自动拉起这个助教。</span>
        </span>
      </label>
      <div className="md:col-span-2">
        <FieldShell label="角色设定">
          <TextArea value={persona} onChange={(event) => setPersona(event.target.value)} data-testid="bot-profile-persona" />
        </FieldShell>
      </div>
      <div className="flex flex-wrap items-center gap-3 md:col-span-2">
        <Button tone="primary" type="submit" disabled={pending} data-testid="bot-profile-save">
          {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
          保存资料
        </Button>
        {saved ? <span className="text-sm text-emerald-700">资料已保存。</span> : null}
      </div>
    </form>
  );
}

export function BotToolsEditor({
  bot,
  pending,
  onSave,
}: {
  bot?: SparkBotSummary;
  pending: boolean;
  onSave: (tools: Record<string, unknown>) => Promise<unknown>;
}) {
  return (
    <section className="rounded-lg border border-line bg-white p-3" data-testid="bot-tools-editor">
      <div className="flex flex-wrap items-start justify-between gap-3 rounded-lg bg-tint-sky px-3 py-3" data-testid="bot-tools-toggle">
        <div>
          <div className="flex items-center gap-2">
            <Wand2 size={18} className="text-brand-blue" />
            <h2 className="text-base font-semibold text-ink">工具能力</h2>
          </div>
          <p className="mt-1 text-sm leading-6 text-slate-500">执行、检索和扩展工具，演示前再调。</p>
        </div>
        <Badge tone="brand">工具</Badge>
      </div>
      <div className="mt-4 border-t border-line pt-4">
        {bot ? (
          <BotToolsForm key={`${bot.bot_id}-${JSON.stringify(bot.tools ?? {})}`} tools={bot.tools} pending={pending} onSave={onSave} />
        ) : (
          <p className="rounded-lg border border-dashed border-line bg-canvas p-4 text-sm text-slate-500">选择一个助教后可编辑工具配置。</p>
        )}
      </div>
    </section>
  );
}

function BotToolsForm({
  tools,
  pending,
  onSave,
}: {
  tools?: Record<string, unknown>;
  pending: boolean;
  onSave: (tools: Record<string, unknown>) => Promise<unknown>;
}) {
  const [value, setValue] = useState(JSON.stringify(tools ?? defaultSparkBotToolsConfig(), null, 2));
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      const parsed = JSON.parse(value) as unknown;
      if (!isRecord(parsed)) throw new Error("工具配置必须是 JSON 对象");
      setError("");
      await onSave(parsed);
      setSaved(true);
    } catch (submitError) {
      setSaved(false);
      setError(submitError instanceof Error ? submitError.message : "JSON 解析失败");
    }
  };

  return (
    <form className="mt-4 grid gap-3" onSubmit={submit}>
      <TextArea value={value} onChange={(event) => setValue(event.target.value)} className="min-h-72 font-mono text-xs" data-testid="bot-tools-json" />
      {error ? <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-brand-red">{error}</p> : null}
      <div className="flex flex-wrap items-center gap-3">
        <Button tone="secondary" type="button" onClick={() => setValue(JSON.stringify(defaultSparkBotToolsConfig(), null, 2))}>
          恢复默认模板
        </Button>
        <Button tone="primary" type="submit" disabled={pending} data-testid="bot-tools-save">
          {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
          保存工具配置
        </Button>
        {saved ? <span className="text-sm text-emerald-700">工具配置已保存。</span> : null}
      </div>
    </form>
  );
}

function defaultSparkBotToolsConfig() {
  return {
    exec: { timeout: 60, pathAppend: "" },
    web: {
      proxy: null,
      fetchMaxChars: 50000,
      search: { provider: "brave", apiKey: "", baseUrl: "", maxResults: 5 },
    },
    restrictToWorkspace: true,
    mcpServers: {},
  };
}

export function BotRuntimeEditor({
  bot,
  pending,
  onSave,
}: {
  bot?: SparkBotSummary;
  pending: boolean;
  onSave: (payload: { agent: Record<string, unknown>; heartbeat: Record<string, unknown> }) => Promise<unknown>;
}) {
  return (
    <section className="rounded-lg border border-line bg-white p-3" data-testid="bot-runtime-editor">
      <div className="flex flex-wrap items-start justify-between gap-3 rounded-lg bg-tint-mint px-3 py-3" data-testid="bot-runtime-toggle">
        <div>
          <div className="flex items-center gap-2">
            <RefreshCw size={18} className="text-brand-purple" />
            <h2 className="text-base font-semibold text-ink">运行习惯</h2>
          </div>
          <p className="mt-1 text-sm leading-6 text-slate-500">响应节奏、工具上限和在线提醒。</p>
        </div>
        <Badge tone="brand">运行设置</Badge>
      </div>
      <div className="mt-4 border-t border-line pt-4">
        {bot ? (
          <BotRuntimeForm
            key={`${bot.bot_id}-${JSON.stringify(bot.agent ?? {})}-${JSON.stringify(bot.heartbeat ?? {})}`}
            agent={bot.agent}
            heartbeat={bot.heartbeat}
            pending={pending}
            onSave={onSave}
          />
        ) : (
          <p className="rounded-lg border border-dashed border-line bg-canvas p-4 text-sm text-slate-500">选择一个助教后可编辑运行设置。</p>
        )}
      </div>
    </section>
  );
}

function BotRuntimeForm({
  agent,
  heartbeat,
  pending,
  onSave,
}: {
  agent?: Record<string, unknown>;
  heartbeat?: Record<string, unknown>;
  pending: boolean;
  onSave: (payload: { agent: Record<string, unknown>; heartbeat: Record<string, unknown> }) => Promise<unknown>;
}) {
  const [agentValue, setAgentValue] = useState(JSON.stringify(agent ?? defaultSparkBotAgentConfig(), null, 2));
  const [heartbeatValue, setHeartbeatValue] = useState(JSON.stringify(heartbeat ?? defaultSparkBotHeartbeatConfig(), null, 2));
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      const parsedAgent = JSON.parse(agentValue) as unknown;
      const parsedHeartbeat = JSON.parse(heartbeatValue) as unknown;
      if (!isRecord(parsedAgent)) throw new Error("助教行为必须是 JSON 对象");
      if (!isRecord(parsedHeartbeat)) throw new Error("在线状态必须是 JSON 对象");
      setError("");
      await onSave({ agent: parsedAgent, heartbeat: parsedHeartbeat });
      setSaved(true);
    } catch (submitError) {
      setSaved(false);
      setError(submitError instanceof Error ? submitError.message : "JSON 解析失败");
    }
  };

  return (
    <form className="mt-4 grid gap-3 lg:grid-cols-2" onSubmit={submit}>
      <FieldShell label="行为参数">
        <TextArea value={agentValue} onChange={(event) => setAgentValue(event.target.value)} className="min-h-72 font-mono text-xs" data-testid="bot-agent-json" />
      </FieldShell>
      <FieldShell label="在线节奏">
        <TextArea
          value={heartbeatValue}
          onChange={(event) => setHeartbeatValue(event.target.value)}
          className="min-h-72 font-mono text-xs"
          data-testid="bot-heartbeat-json"
        />
      </FieldShell>
      {error ? <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-brand-red lg:col-span-2">{error}</p> : null}
      <div className="flex flex-wrap items-center gap-3 lg:col-span-2">
        <Button
          tone="secondary"
          type="button"
          onClick={() => {
            setAgentValue(JSON.stringify(defaultSparkBotAgentConfig(), null, 2));
            setHeartbeatValue(JSON.stringify(defaultSparkBotHeartbeatConfig(), null, 2));
          }}
        >
          恢复默认模板
        </Button>
        <Button tone="primary" type="submit" disabled={pending} data-testid="bot-runtime-save">
          {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
          保存运行设置
        </Button>
        {saved ? <span className="text-sm text-emerald-700">运行设置已保存。</span> : null}
      </div>
    </form>
  );
}

function defaultSparkBotAgentConfig() {
  return {
    maxToolIterations: 4,
    toolCallLimit: 5,
    maxTokens: 8192,
    contextWindowTokens: 65536,
    temperature: 0.1,
    reasoningEffort: null,
    teamMaxWorkers: 5,
    teamWorkerMaxIterations: 25,
  };
}

function defaultSparkBotHeartbeatConfig() {
  return {
    enabled: true,
    intervalS: 1800,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}
