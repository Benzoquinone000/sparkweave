import {
  Bot,
  CalendarClock,
  FileText,
  Loader2,
  MessageSquareText,
  Play,
  PlugZap,
  Plus,
  RefreshCw,
  Save,
  SendHorizontal,
  Server,
  Settings2,
  Square,
  Trash2,
  Upload,
} from "lucide-react";
import { useLocation, useParams } from "@tanstack/react-router";
import type { FormEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FieldShell, SelectInput, TextArea, TextInput } from "@/components/ui/Field";
import {
  useSparkBotChannelSchemas,
  useSparkBotCronJobs,
  useSparkBotDetail,
  useSparkBotFile,
  useSparkBotFiles,
  useSparkBotMutations,
  useSparkBotRecent,
  useSparkBotSkill,
  useSparkBotSkills,
  useSparkBots,
} from "@/hooks/useApiQueries";
import { sparkBotSocketUrl } from "@/lib/api";
import type { SparkBotFile, SparkBotSchemas, SparkBotSkill, SparkBotSummary } from "@/lib/types";
import { AgentWorkspaceTabs, SparkBotRecentPanel, type AgentWorkspaceView } from "./agents/AgentWorkspaceChrome";
import { SparkBotCronPanel } from "./agents/SparkBotCronPanel";

const DEFAULT_BOT_ID = "sparkbot-assistant";
const DEFAULT_PERSONA = `# SparkBot 助教

你是长期运行的 SparkBot 助教。

工作重点：
- 通过 MCP 与 workspace skills 调用真实工具。
- 面向飞书、QQ、Slack、Discord 等通道处理消息。
- 通过定时任务主动巡检、日报、复盘和提醒。
- 默认给出可执行结果，只在必要时解释过程。`;

export function AgentsPage() {
  const params = useParams({ strict: false }) as { botId?: string };
  const location = useLocation();
  const [view, setView] = useState<AgentWorkspaceView>("schedule");
  const [selectedBotId, setSelectedBotId] = useState<string | null>(null);
  const [activeFileName, setActiveFileName] = useState<string | null>("SOUL.md");
  const [newFileName, setNewFileName] = useState("");
  const [chatDraft, setChatDraft] = useState("");
  const [removedBotIds, setRemovedBotIds] = useState<Set<string>>(() => new Set());

  const bots = useSparkBots();
  const recentBots = useSparkBotRecent(5);
  const channelSchemas = useSparkBotChannelSchemas({ enabled: view === "workspace" });
  const mutations = useSparkBotMutations();
  const items = useMemo(
    () => (bots.data ?? []).filter((item) => !removedBotIds.has(item.bot_id)),
    [bots.data, removedBotIds],
  );
  const routeBotId = resolveRouteBotId(location.pathname, params.botId);
  const activeBotId =
    selectedBotId && items.some((item) => item.bot_id === selectedBotId)
      ? selectedBotId
      : routeBotId && items.some((item) => item.bot_id === routeBotId)
        ? routeBotId
        : items[0]?.bot_id || null;

  const activeBot = useSparkBotDetail(activeBotId);
  const cron = useSparkBotCronJobs(activeBotId);
  const files = useSparkBotFiles(activeBotId);
  const fileItems = useMemo(() => orderWorkspaceFiles(files.data ?? []), [files.data]);
  const selectedFileName =
    activeFileName && fileItems.some((item) => item.filename === activeFileName)
      ? activeFileName
      : fileItems[0]?.filename || null;
  const activeFile = useSparkBotFile(activeBotId, selectedFileName, {
    enabled: view === "workspace",
  });
  const activeBotSummary = activeBot.data ?? items.find((item) => item.bot_id === activeBotId);
  const running = items.filter((item) => item.running).length;
  const defaultChannels = useMemo(defaultChannelsConfig, []);
  const defaultTools = useMemo(defaultToolsConfig, []);
  const defaultAgent = useMemo(defaultAgentConfig, []);
  const defaultHeartbeat = useMemo(defaultHeartbeatConfig, []);
  const pending =
    mutations.create.isPending ||
    mutations.update.isPending ||
    mutations.stop.isPending ||
    mutations.destroy.isPending ||
    mutations.createCronJob.isPending ||
    mutations.updateCronJob.isPending ||
    mutations.deleteCronJob.isPending ||
    mutations.runCronJob.isPending ||
    mutations.writeFile.isPending ||
    mutations.writeSkill.isPending ||
    mutations.uploadSkill.isPending;

  const createWorkspaceFile = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!activeBotId || !newFileName.trim()) return;
    const filename = newFileName.trim();
    await mutations.writeFile.mutateAsync({ botId: activeBotId, filename, content: "" });
    setActiveFileName(filename);
    setNewFileName("");
  };

  return (
    <div className="h-full overflow-y-auto bg-canvas/40 px-3.5 py-3.5 pb-20 lg:px-4 lg:pb-4">
      <div className="mx-auto max-w-[1080px] space-y-3.5">
        <motion.section
          className="rounded-lg border border-line bg-white p-3.5 shadow-[0_1px_2px_rgba(15,15,15,0.025)]"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22 }}
        >
          <div className="flex flex-wrap items-start justify-between gap-3.5">
            <div className="min-w-0">
              <p className="text-xs font-semibold text-brand-purple">SparkBot 助教</p>
              <h1 className="mt-1 text-xl font-semibold leading-tight text-ink">定时任务驱动的通道 Agent</h1>
              <p className="mt-2 max-w-2xl text-xs leading-5 text-slate-600">
                核心入口保留定时任务、MCP 与 skills、飞书 / QQ 等通道，以及必要的机器人运行管理。
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button tone="primary" onClick={() => setView("schedule")}>
                <CalendarClock size={16} />
                定时任务
              </Button>
              <Button tone="secondary" onClick={() => setView("workspace")}>
                <PlugZap size={16} />
                通道与技能
              </Button>
            </div>
          </div>

          <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_340px]">
            <BotRail
              bots={items}
              activeBotId={activeBotId}
              loading={bots.isFetching}
              onSelect={setSelectedBotId}
              onOpenBots={() => setView("assistants")}
            />
            <AssistantStats
              bot={activeBotSummary}
              running={running}
              jobs={cron.data?.jobs?.length ?? 0}
              files={fileItems.length}
            />
          </div>
        </motion.section>

        <AgentWorkspaceTabs
          value={view}
          bots={items.length}
          jobs={cron.data?.jobs?.length ?? 0}
          files={fileItems.length}
          onChange={setView}
        />

        {view === "schedule" ? (
          activeBotId ? (
            <SparkBotCronPanel
              bot={activeBotSummary}
              cron={cron.data}
              loading={cron.isFetching}
              pending={pending}
              onRefresh={() => void cron.refetch()}
              onCreate={(payload) => mutations.createCronJob.mutateAsync({ botId: activeBotId, payload })}
              onToggle={(job, enabled) => mutations.updateCronJob.mutateAsync({ botId: activeBotId, jobId: job.id, enabled })}
              onRun={(job) => mutations.runCronJob.mutateAsync({ botId: activeBotId, jobId: job.id })}
              onDelete={(job) => {
                if (!window.confirm(`删除定时任务「${job.name}」？`)) return Promise.resolve();
                return mutations.deleteCronJob.mutateAsync({ botId: activeBotId, jobId: job.id });
              }}
            />
          ) : (
            <NoBotCallout onCreate={() => setView("assistants")} />
          )
        ) : null}

        {view === "assistants" ? (
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
            <BotRoster
              bots={items}
              activeBotId={activeBotId}
              loading={bots.isFetching}
              pending={pending}
              onRefresh={() => void bots.refetch()}
              onSelect={setSelectedBotId}
              onStart={(botId) => mutations.create.mutateAsync({ bot_id: botId, auto_start: true })}
              onStop={(botId) => mutations.stop.mutateAsync(botId)}
              onDestroy={(botId) => {
                const previousSelected = selectedBotId;
                setRemovedBotIds((current) => new Set(current).add(botId));
                if (activeBotId === botId || selectedBotId === botId) setSelectedBotId(null);
                return mutations.destroy
                  .mutateAsync(botId)
                  .then((result) => {
                    void bots.refetch();
                    void recentBots.refetch();
                    return result;
                  })
                  .catch((error) => {
                    setRemovedBotIds((current) => {
                      const next = new Set(current);
                      next.delete(botId);
                      return next;
                    });
                    if (previousSelected === botId) setSelectedBotId(botId);
                    throw error;
                  });
              }}
            />
            <CreateBotPanel
              existingBotIds={items.map((item) => item.bot_id)}
              pending={mutations.create.isPending}
              onCreate={(payload) =>
                mutations.create.mutateAsync(payload).then((bot) => {
                  setRemovedBotIds((current) => {
                    if (!current.has(bot.bot_id)) return current;
                    const next = new Set(current);
                    next.delete(bot.bot_id);
                    return next;
                  });
                  setSelectedBotId(bot.bot_id);
                  void bots.refetch();
                  void recentBots.refetch();
                  return bot;
                })
              }
            />
            <div className="lg:col-span-2">
              <SparkBotRecentPanel
                items={recentBots.data ?? []}
                activeBotId={activeBotId}
                loading={recentBots.isFetching}
                onRefresh={() => void recentBots.refetch()}
                onSelect={setSelectedBotId}
              />
            </div>
            <div className="lg:col-span-2">
              <SparkBotChatTest bot={activeBotSummary} draft={chatDraft} onDraftConsumed={() => setChatDraft("")} />
            </div>
          </div>
        ) : null}

        {view === "workspace" ? (
          activeBotId ? (
            <div className="grid gap-4 lg:grid-cols-[400px_minmax(0,1fr)]">
              <ChannelMcpPanel
                botId={activeBotId}
                bot={activeBot.data ?? activeBotSummary}
                schemas={channelSchemas.data}
                defaultChannels={defaultChannels}
                defaultTools={defaultTools}
                pending={mutations.update.isPending || mutations.writeSkill.isPending || mutations.uploadSkill.isPending}
                onSaveChannels={(channels) => mutations.update.mutateAsync({ botId: activeBotId, payload: { channels } })}
                onSaveTools={(tools) => mutations.update.mutateAsync({ botId: activeBotId, payload: { tools } })}
                onSaveSkill={(skillName, content) => mutations.writeSkill.mutateAsync({ botId: activeBotId, skillName, content })}
                onUploadSkill={(file, skillName) => mutations.uploadSkill.mutateAsync({ botId: activeBotId, file, skillName })}
              />
              <WorkspaceFilesPanel
                files={fileItems}
                activeBotId={activeBotId}
                activeFileName={selectedFileName}
                activeFile={activeFile.data}
                fallbackContent={fileItems.find((item) => item.filename === selectedFileName)?.content}
                newFileName={newFileName}
                pending={mutations.writeFile.isPending}
                loading={activeFile.isLoading}
                onNewFileNameChange={setNewFileName}
                onCreateFile={createWorkspaceFile}
                onSelectFile={setActiveFileName}
                onSaveFile={(content) => {
                  if (!selectedFileName) return Promise.resolve();
                  return mutations.writeFile.mutateAsync({ botId: activeBotId, filename: selectedFileName, content });
                }}
              />
            </div>
          ) : (
            <NoBotCallout onCreate={() => setView("assistants")} />
          )
        ) : null}

        {view === "advanced" ? (
          activeBotId ? (
            <div className="grid gap-4 lg:grid-cols-2">
              <BotProfilePanel
                bot={activeBot.data ?? activeBotSummary}
                pending={mutations.update.isPending}
                onSave={(payload) => mutations.update.mutateAsync({ botId: activeBotId, payload })}
              />
              <JsonEditor
                title="Agent 运行参数"
                value={activeBot.data?.agent ?? defaultAgent}
                pending={mutations.update.isPending}
                onSave={(agent) => mutations.update.mutateAsync({ botId: activeBotId, payload: { agent } })}
              />
              <JsonEditor
                title="Heartbeat"
                value={activeBot.data?.heartbeat ?? defaultHeartbeat}
                pending={mutations.update.isPending}
                onSave={(heartbeat) => mutations.update.mutateAsync({ botId: activeBotId, payload: { heartbeat } })}
              />
              <section className="rounded-lg border border-line bg-white p-3">
                <div className="flex items-center gap-2">
                  <MessageSquareText size={18} className="text-brand-purple" />
                  <h2 className="text-base font-semibold text-ink">命令调试</h2>
                </div>
                <div className="mt-4 border-t border-line pt-4">
                  <Button
                    tone="secondary"
                    onClick={() => {
                      setView("assistants");
                      setChatDraft("/cron list");
                    }}
                  >
                    <MessageSquareText size={16} />
                    打开 /cron list
                  </Button>
                </div>
              </section>
            </div>
          ) : (
            <NoBotCallout onCreate={() => setView("assistants")} />
          )
        ) : null}
      </div>
    </div>
  );
}

function resolveRouteBotId(pathname: string, paramBotId?: string) {
  if (paramBotId) return decodeURIComponent(paramBotId);
  const match = /^\/agents\/([^/?#]+)\/chat/.exec(pathname);
  return match ? decodeURIComponent(match[1]) : null;
}

function BotRail({
  bots,
  activeBotId,
  loading,
  onSelect,
  onOpenBots,
}: {
  bots: SparkBotSummary[];
  activeBotId: string | null;
  loading: boolean;
  onSelect: (botId: string) => void;
  onOpenBots: () => void;
}) {
  return (
    <div className="rounded-lg border border-line bg-canvas p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold text-ink">当前机器人</p>
        <Button tone="quiet" className="min-h-8 px-2 text-xs" onClick={onOpenBots}>
          管理
        </Button>
      </div>
      <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
        {bots.map((bot) => {
          const active = activeBotId === bot.bot_id;
          return (
            <button
              key={bot.bot_id}
              type="button"
              onClick={() => onSelect(bot.bot_id)}
              className={`min-w-[180px] rounded-lg border px-3 py-2 text-left transition ${
                active ? "border-brand-purple-300 bg-white" : "border-line bg-white/70 hover:border-brand-purple-300"
              }`}
              data-testid={`sparkbot-rail-${bot.bot_id}`}
            >
              <span className="flex items-start justify-between gap-2">
                <span className="min-w-0">
                  <span className="block truncate text-sm font-semibold text-ink">{bot.name || bot.bot_id}</span>
                  <span className="mt-1 block truncate text-xs text-slate-500">{bot.bot_id}</span>
                </span>
                <Badge tone={bot.running ? "success" : "neutral"}>{bot.running ? "在线" : "停止"}</Badge>
              </span>
            </button>
          );
        })}
        {!bots.length ? (
          <button
            type="button"
            onClick={onOpenBots}
            className="min-w-[220px] rounded-lg border border-dashed border-line bg-white px-3 py-2 text-left text-sm text-slate-500"
          >
            {loading ? "正在读取 SparkBot..." : "创建一个 SparkBot 后开始配置定时任务。"}
          </button>
        ) : null}
      </div>
    </div>
  );
}

function AssistantStats({
  bot,
  running,
  jobs,
  files,
}: {
  bot?: SparkBotSummary;
  running: number;
  jobs: number;
  files: number;
}) {
  return (
    <div className="grid gap-2 text-sm">
      <AssistantFact label="当前 Bot" value={bot?.name || bot?.bot_id || "未选择"} />
      <AssistantFact label="运行状态" value={running ? `${running} 个在线` : "未启动"} />
      <AssistantFact label="定时任务" value={`${jobs} 个`} />
      <AssistantFact label="工作区文件" value={`${files} 个`} />
    </div>
  );
}

function AssistantFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-line bg-white px-3 py-2">
      <span className="block text-xs font-medium text-slate-500">{label}</span>
      <span className="mt-1 block truncate font-semibold text-ink">{value}</span>
    </div>
  );
}

function NoBotCallout({ onCreate }: { onCreate: () => void }) {
  return (
    <section className="rounded-lg border border-dashed border-line bg-white p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-ink">还没有可用的 SparkBot</h2>
          <p className="mt-1 text-sm leading-6 text-slate-500">先创建机器人，再配置通道、MCP、skills 和定时任务。</p>
        </div>
        <Button tone="primary" onClick={onCreate}>
          <Bot size={16} />
          打开创建表单
        </Button>
      </div>
    </section>
  );
}

function BotRoster({
  bots,
  activeBotId,
  loading,
  pending,
  onRefresh,
  onSelect,
  onStart,
  onStop,
  onDestroy,
}: {
  bots: SparkBotSummary[];
  activeBotId: string | null;
  loading: boolean;
  pending: boolean;
  onRefresh: () => void;
  onSelect: (botId: string) => void;
  onStart: (botId: string) => Promise<unknown>;
  onStop: (botId: string) => Promise<unknown>;
  onDestroy: (botId: string) => Promise<unknown>;
}) {
  return (
    <section className="rounded-lg border border-line bg-white p-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Bot size={18} className="text-brand-purple" />
          <h2 className="text-base font-semibold text-ink">机器人</h2>
        </div>
        <Button tone="secondary" onClick={onRefresh} disabled={loading}>
          {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
          刷新
        </Button>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {bots.map((bot) => (
          <SparkBotCard
            key={bot.bot_id}
            bot={bot}
            active={activeBotId === bot.bot_id}
            pending={pending}
            onSelect={() => onSelect(bot.bot_id)}
            onStart={() => void onStart(bot.bot_id)}
            onStop={() => void onStop(bot.bot_id)}
            onDestroy={() => {
              if (window.confirm(`彻底删除 SparkBot ${bot.bot_id}？`)) void onDestroy(bot.bot_id);
            }}
          />
        ))}
      </div>
      {!bots.length ? (
        <p className="mt-4 rounded-lg border border-dashed border-line bg-canvas p-4 text-sm leading-6 text-slate-500">
          还没有 SparkBot。右侧创建一个后，就可以配置 MCP、skills、通道和定时任务。
        </p>
      ) : null}
    </section>
  );
}

function SparkBotCard({
  bot,
  active,
  pending,
  onSelect,
  onStart,
  onStop,
  onDestroy,
}: {
  bot: SparkBotSummary;
  active: boolean;
  pending: boolean;
  onSelect: () => void;
  onStart: () => void;
  onStop: () => void;
  onDestroy: () => void;
}) {
  return (
    <article className={`rounded-lg border p-3 ${active ? "border-brand-purple-300 bg-tint-lavender" : "border-line bg-white"}`} data-testid={`sparkbot-card-${bot.bot_id}`}>
      <button type="button" className="w-full text-left" onClick={onSelect}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate font-semibold text-ink">{bot.name || bot.bot_id}</p>
            <p className="mt-1 line-clamp-2 text-sm leading-6 text-slate-500">{bot.description || bot.model || "SparkBot 通道助教"}</p>
          </div>
          <Badge tone={bot.running ? "success" : "neutral"}>{bot.running ? "运行中" : "停止"}</Badge>
        </div>
      </button>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button tone="secondary" className="min-h-9 text-xs" onClick={onStart} disabled={bot.running || pending} data-testid={`sparkbot-start-${bot.bot_id}`}>
          <Play size={14} />
          启动
        </Button>
        <Button tone="secondary" className="min-h-9 text-xs" onClick={onStop} disabled={!bot.running || pending} data-testid={`sparkbot-stop-${bot.bot_id}`}>
          <Square size={14} />
          停止
        </Button>
        <Button tone="danger" className="min-h-9 text-xs" onClick={onDestroy} disabled={pending} data-testid={`sparkbot-destroy-${bot.bot_id}`}>
          <Trash2 size={14} />
          删除
        </Button>
      </div>
    </article>
  );
}

function CreateBotPanel({
  existingBotIds,
  pending,
  onCreate,
}: {
  existingBotIds: string[];
  pending: boolean;
  onCreate: (payload: { bot_id: string; name?: string; description?: string; persona?: string; auto_start?: boolean }) => Promise<SparkBotSummary>;
}) {
  const [botId, setBotId] = useState(DEFAULT_BOT_ID);
  const [botIdEdited, setBotIdEdited] = useState(false);
  const [name, setName] = useState("SparkBot 助教");
  const [description, setDescription] = useState("支持 MCP、skills、通道消息和定时任务的长期助教。");
  const [persona, setPersona] = useState(DEFAULT_PERSONA);
  const [autoStart, setAutoStart] = useState(true);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const trimmedBotId = botId.trim();
  const idExists = Boolean(trimmedBotId && existingBotIds.includes(trimmedBotId));

  useEffect(() => {
    if (botIdEdited) return;
    if (trimmedBotId && !existingBotIds.includes(trimmedBotId)) return;
    setBotId(nextAvailableBotId(existingBotIds));
  }, [botIdEdited, existingBotIds, trimmedBotId]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!trimmedBotId) return;
    if (idExists) {
      setSaved("");
      setError(`Bot ID "${trimmedBotId}" 已存在。请选择左侧卡片启动它，或换一个新的 Bot ID。`);
      return;
    }
    try {
      setError("");
      setSaved("");
      const created = await onCreate({
        bot_id: trimmedBotId,
        name: name.trim() || trimmedBotId,
        description: description.trim(),
        persona,
        auto_start: autoStart,
      });
      setSaved(`已创建 ${created.bot_id}。`);
      setBotIdEdited(false);
      setBotId(nextAvailableBotId([...existingBotIds, created.bot_id]));
    } catch (createError) {
      setSaved("");
      setError(createError instanceof Error ? createError.message : "创建 SparkBot 失败。");
    }
  };

  return (
    <section className="rounded-lg border border-line bg-white p-3" data-testid="sparkbot-create-toggle">
      <div className="flex items-center gap-2">
        <Bot size={18} className="text-brand-purple" />
        <h2 className="text-base font-semibold text-ink">创建 SparkBot</h2>
      </div>
      <form className="mt-4 grid gap-3 border-t border-line pt-4" onSubmit={submit}>
        <FieldShell label="Bot ID">
          <TextInput
            value={botId}
            onChange={(event) => {
              setBotIdEdited(true);
              setBotId(event.target.value);
              setError("");
              setSaved("");
            }}
            data-testid="assistant-create-bot-id"
          />
        </FieldShell>
        {idExists ? (
          <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-700">
            这个 Bot ID 已经存在。创建新机器人请换一个 ID；已有机器人请在左侧列表直接启动或配置。
          </p>
        ) : null}
        <FieldShell label="名称">
          <TextInput value={name} onChange={(event) => setName(event.target.value)} data-testid="assistant-create-name" />
        </FieldShell>
        <FieldShell label="说明">
          <TextInput value={description} onChange={(event) => setDescription(event.target.value)} />
        </FieldShell>
        <label className="flex items-start gap-2 rounded-lg border border-line bg-canvas p-3 text-sm text-slate-600">
          <input type="checkbox" checked={autoStart} onChange={(event) => setAutoStart(event.target.checked)} className="mt-1" />
          <span>创建后启动</span>
        </label>
        <FieldShell label="人设">
          <TextArea value={persona} onChange={(event) => setPersona(event.target.value)} className="min-h-44" data-testid="assistant-create-persona" />
        </FieldShell>
        {error ? <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-brand-red">{error}</p> : null}
        {saved ? <p className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">{saved}</p> : null}
        <Button tone="primary" type="submit" disabled={pending || !trimmedBotId || idExists} data-testid="assistant-create-submit">
          {pending ? <Loader2 size={16} className="animate-spin" /> : <Bot size={16} />}
          创建
        </Button>
      </form>
    </section>
  );
}

function ChannelMcpPanel({
  botId,
  bot,
  schemas,
  defaultChannels,
  defaultTools,
  pending,
  onSaveChannels,
  onSaveTools,
  onSaveSkill,
  onUploadSkill,
}: {
  botId: string;
  bot?: SparkBotSummary;
  schemas?: SparkBotSchemas;
  defaultChannels: Record<string, unknown>;
  defaultTools: Record<string, unknown>;
  pending: boolean;
  onSaveChannels: (channels: Record<string, unknown>) => Promise<unknown>;
  onSaveTools: (tools: Record<string, unknown>) => Promise<unknown>;
  onSaveSkill: (skillName: string, content: string) => Promise<unknown>;
  onUploadSkill: (file: File, skillName?: string) => Promise<unknown>;
}) {
  const channels = bot?.channels ?? defaultChannels;
  const tools = bot?.tools ?? defaultTools;
  const configuredChannels = Object.entries(channels)
    .filter(([, value]) => isRecord(value) && value.enabled)
    .map(([key]) => key);
  const availableChannels = Object.keys(schemas?.channels ?? {}).sort();
  return (
    <div className="grid gap-4" data-testid="sparkbot-channel-toggle">
      <section className="rounded-lg border border-line bg-white p-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <PlugZap size={18} className="text-brand-purple" />
            <h2 className="text-base font-semibold text-ink">通道、MCP 与 Skills</h2>
          </div>
          <Badge tone={bot?.running ? "success" : "neutral"}>{bot?.running ? "运行中" : "停止"}</Badge>
        </div>
        <div className="mt-4 grid gap-3 border-t border-line pt-4">
          <ChannelBadges title="已启用通道" values={configuredChannels} fallback="未启用" />
          <ChannelBadges title="可用通道" values={availableChannels.length ? availableChannels : ["feishu", "qq", "slack", "discord"]} />
        </div>
      </section>

      <SkillsManagerPanel botId={botId} pending={pending} onSave={onSaveSkill} onUpload={onUploadSkill} />
      <McpServersEditor tools={tools} pending={pending} onSave={onSaveTools} />

      <JsonEditor
        title="通道配置"
        value={channels}
        pending={pending}
        testId="sparkbot-global-channel-editor"
        onSave={onSaveChannels}
      />
      <JsonEditor
        title="工具高级 JSON"
        value={tools}
        pending={pending}
        onSave={onSaveTools}
      />
    </div>
  );
}

function ChannelBadges({ title, values, fallback }: { title: string; values: string[]; fallback?: string }) {
  return (
    <div>
      <p className="text-xs font-medium text-slate-500">{title}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {values.length ? values.map((value) => <Badge key={value} tone="neutral">{value}</Badge>) : <Badge tone="neutral">{fallback || "暂无"}</Badge>}
      </div>
    </div>
  );
}

function SkillsManagerPanel({
  botId,
  pending,
  onSave,
  onUpload,
}: {
  botId: string;
  pending: boolean;
  onSave: (skillName: string, content: string) => Promise<unknown>;
  onUpload: (file: File, skillName?: string) => Promise<unknown>;
}) {
  const skills = useSparkBotSkills(botId, { enabled: Boolean(botId) });
  const [selectedName, setSelectedName] = useState("");
  const selectedSkill = useSparkBotSkill(botId, selectedName || null, { enabled: Boolean(botId && selectedName) });
  const [skillName, setSkillName] = useState("daily-review");
  const [content, setContent] = useState(defaultSkillContent("daily-review"));
  const [uploadName, setUploadName] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!selectedName && skills.data?.length) {
      setSelectedName(skills.data[0].name);
    }
  }, [selectedName, skills.data]);

  useEffect(() => {
    if (!selectedSkill.data) return;
    setSkillName(selectedSkill.data.name);
    setContent(selectedSkill.data.content || defaultSkillContent(selectedSkill.data.name));
    setError("");
    setSaved(false);
  }, [selectedSkill.data]);

  const submitUpload = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!uploadFile) {
      setError("请选择一个 SKILL.md 或 zip 文件。");
      return;
    }
    try {
      setError("");
      setSaved(false);
      const result = (await onUpload(uploadFile, uploadName.trim() || undefined)) as SparkBotSkill | undefined;
      setUploadFile(null);
      setUploadName("");
      if (result?.name) setSelectedName(result.name);
      setSaved(true);
      void skills.refetch();
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "上传 skill 失败。");
    }
  };

  const submitSave = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!skillName.trim() || !content.trim()) {
      setError("Skill 名称和内容不能为空。");
      return;
    }
    try {
      setError("");
      setSaved(false);
      await onSave(skillName.trim(), content);
      setSelectedName(skillName.trim());
      setSaved(true);
      void skills.refetch();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "保存 skill 失败。");
    }
  };

  return (
    <section className="rounded-lg border border-line bg-white p-3" data-testid="sparkbot-skills-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <FileText size={18} className="text-brand-purple" />
          <h2 className="text-base font-semibold text-ink">Skills</h2>
        </div>
        <Badge tone="neutral">{skills.data?.length ?? 0}</Badge>
      </div>

      <form className="mt-4 grid gap-2 border-t border-line pt-4" onSubmit={submitUpload}>
        <FieldShell label="上传 skill" hint="支持单个 SKILL.md 或包含 SKILL.md 的 zip">
          <input
            type="file"
            accept=".md,.zip"
            onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
            className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border file:border-line file:bg-canvas file:px-3 file:py-2 file:text-sm file:font-medium file:text-ink"
            data-testid="sparkbot-skill-upload-file"
          />
        </FieldShell>
        <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
          <TextInput value={uploadName} onChange={(event) => setUploadName(event.target.value)} placeholder="可选：skill 名称" data-testid="sparkbot-skill-upload-name" />
          <Button tone="secondary" type="submit" disabled={pending || !uploadFile} data-testid="sparkbot-skill-upload-submit">
            {pending ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
            上传
          </Button>
        </div>
      </form>

      <div className="mt-4 flex max-h-36 flex-wrap gap-2 overflow-y-auto">
        {(skills.data ?? []).map((skill) => (
          <button
            key={`${skill.source}-${skill.name}`}
            type="button"
            onClick={() => setSelectedName(skill.name)}
            className={`rounded-lg border px-3 py-2 text-left text-sm transition ${
              selectedName === skill.name ? "border-brand-purple-300 bg-tint-lavender text-brand-purple" : "border-line bg-white text-slate-600 hover:border-brand-purple-300"
            }`}
            data-testid={`sparkbot-skill-${skill.name}`}
          >
            <span className="block font-medium">{skill.name}</span>
            <span className="mt-1 block text-xs text-slate-500">{skill.source || "workspace"} · {skill.available === false ? "缺依赖" : "可用"}</span>
          </button>
        ))}
        {!skills.data?.length && !skills.isFetching ? (
          <p className="rounded-lg border border-dashed border-line bg-canvas p-3 text-sm text-slate-500">暂无 skills，可以上传一个 SKILL.md。</p>
        ) : null}
      </div>

      <form className="mt-4 grid gap-3 border-t border-line pt-4" onSubmit={submitSave}>
        <FieldShell label="Skill 名称">
          <TextInput value={skillName} onChange={(event) => setSkillName(event.target.value)} data-testid="sparkbot-skill-name" />
        </FieldShell>
        <FieldShell label="SKILL.md">
          <TextArea value={content} onChange={(event) => setContent(event.target.value)} className="min-h-72 font-mono text-xs" data-testid="sparkbot-skill-content" />
        </FieldShell>
        {selectedSkill.data?.missing_requirements ? (
          <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-700">{selectedSkill.data.missing_requirements}</p>
        ) : null}
        {error ? <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-brand-red">{error}</p> : null}
        {saved ? <p className="text-sm text-emerald-700">已保存。</p> : null}
        <div className="flex flex-wrap gap-2">
          <Button tone="secondary" type="button" onClick={() => { setSkillName("new-skill"); setContent(defaultSkillContent("new-skill")); setSelectedName(""); }}>
            <Plus size={16} />
            新建
          </Button>
          <Button tone="primary" type="submit" disabled={pending || !skillName.trim() || !content.trim()} data-testid="sparkbot-skill-save">
            {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            保存到工作区
          </Button>
        </div>
      </form>
    </section>
  );
}

function McpServersEditor({
  tools,
  pending,
  onSave,
}: {
  tools: Record<string, unknown>;
  pending: boolean;
  onSave: (tools: Record<string, unknown>) => Promise<unknown>;
}) {
  const servers = getMcpServers(tools);
  const [draft, setDraft] = useState(defaultMcpDraft());
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      const name = draft.name.trim();
      if (!name) throw new Error("MCP 名称不能为空。");
      const config = buildMcpServerConfig(draft);
      setError("");
      setSaved(false);
      await onSave(withMcpServers(tools, { ...servers, [name]: config }));
      setSaved(true);
    } catch (submitError) {
      setSaved(false);
      setError(submitError instanceof Error ? submitError.message : "保存 MCP 失败。");
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
          <h2 className="text-base font-semibold text-ink">MCP 服务器</h2>
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
          <p className="rounded-lg border border-dashed border-line bg-canvas p-3 text-sm text-slate-500">还没有 MCP 服务器。添加后 SparkBot 可在任务和通道对话中调用。</p>
        ) : null}
      </div>

      <form className="mt-4 grid gap-3 border-t border-line pt-4" onSubmit={submit}>
        <div className="grid gap-3 sm:grid-cols-2">
          <FieldShell label="名称">
            <TextInput value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} data-testid="sparkbot-mcp-name" />
          </FieldShell>
          <FieldShell label="类型">
            <SelectInput value={draft.type} onChange={(event) => setDraft({ ...draft, type: event.target.value as McpServerDraft["type"] })} data-testid="sparkbot-mcp-type">
              <option value="stdio">stdio</option>
              <option value="sse">sse</option>
              <option value="streamableHttp">streamableHttp</option>
            </SelectInput>
          </FieldShell>
        </div>

        {draft.type === "stdio" ? (
          <>
            <FieldShell label="命令">
              <TextInput value={draft.command} onChange={(event) => setDraft({ ...draft, command: event.target.value })} placeholder="npx / uvx / python" data-testid="sparkbot-mcp-command" />
            </FieldShell>
            <FieldShell label="参数">
              <TextInput value={draft.args} onChange={(event) => setDraft({ ...draft, args: event.target.value })} placeholder="-y @modelcontextprotocol/server-filesystem ." data-testid="sparkbot-mcp-args" />
            </FieldShell>
          </>
        ) : (
          <FieldShell label="URL">
            <TextInput value={draft.url} onChange={(event) => setDraft({ ...draft, url: event.target.value })} placeholder="http://127.0.0.1:3000/mcp" data-testid="sparkbot-mcp-url" />
          </FieldShell>
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          <FieldShell label="环境变量 JSON">
            <TextArea value={draft.env} onChange={(event) => setDraft({ ...draft, env: event.target.value })} className="min-h-24 font-mono text-xs" />
          </FieldShell>
          <FieldShell label="Headers JSON">
            <TextArea value={draft.headers} onChange={(event) => setDraft({ ...draft, headers: event.target.value })} className="min-h-24 font-mono text-xs" />
          </FieldShell>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <FieldShell label="超时秒数">
            <TextInput value={draft.toolTimeout} onChange={(event) => setDraft({ ...draft, toolTimeout: event.target.value })} inputMode="numeric" />
          </FieldShell>
          <FieldShell label="允许工具">
            <TextInput value={draft.enabledTools} onChange={(event) => setDraft({ ...draft, enabledTools: event.target.value })} placeholder="* 或 tool_a,tool_b" />
          </FieldShell>
        </div>

        {error ? <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-brand-red">{error}</p> : null}
        {saved ? <p className="text-sm text-emerald-700">MCP 配置已保存。</p> : null}
        <div className="flex flex-wrap gap-2">
          <Button tone="secondary" type="button" onClick={() => setDraft(defaultMcpDraft())}>
            <Plus size={16} />
            新建
          </Button>
          <Button tone="primary" type="submit" disabled={pending} data-testid="sparkbot-mcp-save">
            {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            保存 MCP
          </Button>
        </div>
      </form>
    </section>
  );
}

function WorkspaceFilesPanel({
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
  onCreateFile: (event: FormEvent<HTMLFormElement>) => void;
  onSelectFile: (filename: string) => void;
  onSaveFile: (content: string) => Promise<unknown>;
}) {
  const [draft, setDraft] = useState(activeFile?.content ?? fallbackContent ?? "");

  useEffect(() => {
    setDraft(activeFile?.content ?? fallbackContent ?? "");
  }, [activeFile?.content, fallbackContent, activeFileName]);

  return (
    <section className="rounded-lg border border-line bg-white p-3" data-testid="sparkbot-files-toggle">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <FileText size={18} className="text-brand-purple" />
          <h2 className="text-base font-semibold text-ink">工作区文件</h2>
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
          <form
            className="grid gap-3"
            onSubmit={(event) => {
              event.preventDefault();
              void onSaveFile(draft);
            }}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-mono text-sm font-semibold text-ink">{activeFileName}</p>
              <Button tone="primary" type="submit" disabled={pending || loading} data-testid="sparkbot-file-save">
                {pending || loading ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                保存
              </Button>
            </div>
            <TextArea value={draft} onChange={(event) => setDraft(event.target.value)} className="min-h-96 font-mono text-xs" data-testid="sparkbot-file-content" />
          </form>
        ) : (
          <div className="rounded-lg border border-dashed border-line bg-canvas p-6 text-sm text-slate-500">选择一个文件后编辑。</div>
        )}
      </div>
    </section>
  );
}

function BotProfilePanel({
  bot,
  pending,
  onSave,
}: {
  bot?: SparkBotSummary;
  pending: boolean;
  onSave: (payload: Partial<Pick<SparkBotSummary, "name" | "description" | "persona" | "model" | "auto_start">>) => Promise<unknown>;
}) {
  const [name, setName] = useState(bot?.name || "");
  const [description, setDescription] = useState(bot?.description || "");
  const [model, setModel] = useState(bot?.model || "");
  const [persona, setPersona] = useState(bot?.persona || "");
  const [autoStart, setAutoStart] = useState(Boolean(bot?.auto_start));

  useEffect(() => {
    setName(bot?.name || "");
    setDescription(bot?.description || "");
    setModel(bot?.model || "");
    setPersona(bot?.persona || "");
    setAutoStart(Boolean(bot?.auto_start));
  }, [bot?.bot_id, bot?.name, bot?.description, bot?.model, bot?.persona, bot?.auto_start]);

  return (
    <section className="rounded-lg border border-line bg-white p-3" data-testid="bot-profile-editor">
      <div className="flex items-center gap-2" data-testid="bot-profile-toggle">
        <Settings2 size={18} className="text-brand-purple" />
        <h2 className="text-base font-semibold text-ink">Bot 基础设置</h2>
      </div>
      {bot ? (
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
          <FieldShell label="模型">
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
            <span>项目启动时自动启动这个 SparkBot</span>
          </label>
          <FieldShell label="人设">
            <TextArea value={persona} onChange={(event) => setPersona(event.target.value)} className="min-h-56" data-testid="bot-profile-persona" />
          </FieldShell>
          <Button tone="primary" type="submit" disabled={pending} data-testid="bot-profile-save">
            {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            保存
          </Button>
        </form>
      ) : (
        <p className="mt-4 rounded-lg border border-dashed border-line bg-canvas p-4 text-sm text-slate-500">先选择一个 SparkBot。</p>
      )}
    </section>
  );
}

function SparkBotChatTest({
  bot,
  draft,
  onDraftConsumed,
}: {
  bot?: SparkBotSummary;
  draft: string;
  onDraftConsumed: () => void;
}) {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Array<{ role: "user" | "bot"; content: string }>>([]);
  const [busy, setBusy] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);
  const canSend = Boolean(bot?.bot_id && bot.running && !busy);

  useEffect(() => {
    if (draft) {
      setInput(draft);
      onDraftConsumed();
    }
  }, [draft, onDraftConsumed]);

  useEffect(
    () => () => {
      socketRef.current?.close();
    },
    [],
  );

  const send = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!bot?.bot_id || !input.trim() || !canSend) return;
    const content = input.trim();
    setInput("");
    setBusy(true);
    setMessages((current) => [...current, { role: "user", content }, { role: "bot", content: "" }]);
    socketRef.current?.close();
    const socket = new WebSocket(sparkBotSocketUrl(bot.bot_id));
    socketRef.current = socket;
    socket.onopen = () => socket.send(JSON.stringify({ content, chat_id: "web" }));
    socket.onmessage = (message) => {
      try {
        const data = JSON.parse(message.data) as { type?: string; content?: string; delta?: boolean; append?: boolean };
        if (data.type === "content_delta" || data.type === "delta" || data.delta || data.append) {
          setMessages((current) => appendLastBotMessage(current, data.content || ""));
        } else if (data.type === "content" || data.type === "proactive") {
          setMessages((current) => replaceLastBotMessage(current, data.content || ""));
        } else if (data.type === "done") {
          setBusy(false);
          socket.close();
        } else if (data.type === "error") {
          setMessages((current) => replaceLastBotMessage(current, data.content || "SparkBot 返回错误。"));
          setBusy(false);
        }
      } catch {
        setMessages((current) => replaceLastBotMessage(current, "无法解析 SparkBot 响应。"));
        setBusy(false);
      }
    };
    socket.onerror = () => {
      setMessages((current) => replaceLastBotMessage(current, "无法连接 SparkBot WebSocket。"));
      setBusy(false);
    };
    socket.onclose = () => setBusy(false);
  };

  return (
    <section className="rounded-lg border border-line bg-white p-3" data-testid="sparkbot-chat">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <MessageSquareText size={18} className="text-brand-purple" />
          <h2 className="text-base font-semibold text-ink">通道调试</h2>
        </div>
        <Badge tone={bot?.running ? "success" : "neutral"}>{bot?.running ? "可测试" : "先启动 Bot"}</Badge>
      </div>
      <div className="mt-4 max-h-72 space-y-2 overflow-y-auto rounded-lg border border-line bg-canvas p-3">
        {messages.map((message, index) => (
          <div
            key={`${message.role}-${index}`}
            className={`rounded-lg border p-3 text-sm leading-6 ${
              message.role === "user" ? "ml-auto max-w-[82%] border-brand-purple-300 bg-tint-lavender" : "mr-auto max-w-[82%] border-line bg-white"
            }`}
          >
            <p className="text-xs font-semibold text-slate-500">{message.role === "user" ? "我" : "SparkBot"}</p>
            <p className="mt-1 whitespace-pre-wrap text-slate-700">{message.content || "等待回复..."}</p>
          </div>
        ))}
        {!messages.length ? <p className="text-sm leading-6 text-slate-500">这里仅用于测试 Bot 回复。正式任务优先通过通道、MCP、skills 和定时任务运行。</p> : null}
      </div>
      <form className="mt-3 flex gap-2" onSubmit={send}>
        <TextInput value={input} onChange={(event) => setInput(event.target.value)} placeholder="/cron list 或测试一句通道消息" data-testid="sparkbot-chat-input" />
        <Button tone="primary" type="submit" disabled={!canSend || !input.trim()}>
          {busy ? <Loader2 size={16} className="animate-spin" /> : <SendHorizontal size={16} />}
          发送
        </Button>
      </form>
    </section>
  );
}

function JsonEditor({
  title,
  value,
  pending,
  testId,
  onSave,
}: {
  title: string;
  value: Record<string, unknown>;
  pending: boolean;
  testId?: string;
  onSave: (value: Record<string, unknown>) => Promise<unknown>;
}) {
  const [draft, setDraft] = useState(JSON.stringify(value, null, 2));
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setDraft(JSON.stringify(value, null, 2));
    setError("");
    setSaved(false);
  }, [value]);

  return (
    <section className="rounded-lg border border-line bg-white p-3" data-testid={testId}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold text-ink">{title}</h2>
        <Button
          tone="primary"
          onClick={async () => {
            try {
              const parsed = JSON.parse(draft) as unknown;
              if (!isRecord(parsed)) throw new Error("必须是 JSON 对象。");
              setError("");
              setSaved(false);
              await onSave(parsed);
              setSaved(true);
            } catch (saveError) {
              setSaved(false);
              setError(saveError instanceof Error ? saveError.message : "JSON 解析失败。");
            }
          }}
          disabled={pending}
        >
          {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
          保存
        </Button>
      </div>
      <TextArea value={draft} onChange={(event) => setDraft(event.target.value)} className="mt-3 min-h-72 font-mono text-xs" />
      {error ? <p className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-brand-red">{error}</p> : null}
      {saved ? <p className="mt-3 text-sm text-emerald-700">已保存。</p> : null}
    </section>
  );
}

function appendLastBotMessage(messages: Array<{ role: "user" | "bot"; content: string }>, delta: string) {
  return messages.map((message, index) =>
    index === messages.length - 1 && message.role === "bot" ? { ...message, content: `${message.content}${delta}` } : message,
  );
}

function replaceLastBotMessage(messages: Array<{ role: "user" | "bot"; content: string }>, content: string) {
  return messages.map((message, index) => (index === messages.length - 1 && message.role === "bot" ? { ...message, content } : message));
}

function nextAvailableBotId(existingBotIds: string[]) {
  const existing = new Set(existingBotIds);
  if (!existing.has(DEFAULT_BOT_ID)) return DEFAULT_BOT_ID;
  let index = 2;
  while (existing.has(`${DEFAULT_BOT_ID}-${index}`)) index += 1;
  return `${DEFAULT_BOT_ID}-${index}`;
}

function defaultSkillContent(name: string) {
  return `---
description: ${name}
always: false
---

# ${name}

Use this skill when SparkBot needs this workflow.

## Steps
- Clarify the trigger.
- Use MCP or workspace tools when needed.
- Return a concise action result.`;
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
  const env = parseJsonObject(draft.env, "环境变量");
  const headers = parseJsonObject(draft.headers, "Headers");
  const toolTimeout = Number(draft.toolTimeout || 30);
  if (!Number.isFinite(toolTimeout) || toolTimeout <= 0) throw new Error("超时秒数必须大于 0。");
  const enabledTools = splitEnabledTools(draft.enabledTools);
  if (draft.type === "stdio") {
    if (!draft.command.trim()) throw new Error("stdio MCP 必须填写命令。");
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
  if (!draft.url.trim()) throw new Error("远程 MCP 必须填写 URL。");
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
  if (type === "stdio") return `${type} · ${String(config.command || "")} ${Array.isArray(config.args) ? config.args.join(" ") : ""}`.trim();
  return `${type} · ${String(config.url || "")}`;
}

function parseJsonObject(value: string, label: string) {
  const trimmed = value.trim();
  if (!trimmed) return {};
  const parsed = JSON.parse(trimmed) as unknown;
  if (!isRecord(parsed)) throw new Error(`${label} 必须是 JSON 对象。`);
  return parsed;
}

function splitArgs(value: string) {
  return value.trim() ? value.trim().split(/\s+/).filter(Boolean) : [];
}

function splitEnabledTools(value: string) {
  const items = value.split(",").map((item) => item.trim()).filter(Boolean);
  return items.length ? items : ["*"];
}

function orderWorkspaceFiles(files: SparkBotFile[]) {
  const priority = ["SOUL.md", "TOOLS.md", "AGENTS.md", "HEARTBEAT.md", "USER.md", "NOTES.md", "COURSE.md"];
  return [...files].sort((a, b) => {
    const ai = priority.indexOf(a.filename);
    const bi = priority.indexOf(b.filename);
    if (ai !== -1 || bi !== -1) return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
    return a.filename.localeCompare(b.filename);
  });
}

function defaultChannelsConfig() {
  return {
    send_progress: true,
    send_tool_hints: false,
    feishu: {
      enabled: false,
      app_id: "",
      app_secret: "",
      encrypt_key: "",
      verification_token: "",
      group_policy: "mention",
      allow_from: [],
    },
    qq: {
      enabled: false,
      app_id: "",
      secret: "",
      msg_format: "plain",
      allow_from: [],
    },
  };
}

function defaultToolsConfig() {
  return {
    restrictToWorkspace: true,
    mcpServers: {},
    exec: { timeout: 300, pathAppend: "" },
    web: {
      search: { provider: "brave", apiKey: "", baseUrl: "", maxResults: 5 },
      fetchMaxChars: 50000,
    },
  };
}

function defaultAgentConfig() {
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

function defaultHeartbeatConfig() {
  return {
    enabled: true,
    intervalS: 1800,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}
