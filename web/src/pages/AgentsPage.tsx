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
import type { SparkBotChannelSchema, SparkBotFile, SparkBotSchemas, SparkBotSkill, SparkBotSummary } from "@/lib/types";
import { AgentWorkspaceTabs, SparkBotRecentPanel, type AgentWorkspaceView } from "./agents/AgentWorkspaceChrome";
import { SparkBotCronPanel } from "./agents/SparkBotCronPanel";

const DEFAULT_BOT_ID = "sparkbot-assistant";
const DEFAULT_PERSONA = `# 课程助教

你是长期运行的课程助教。

工作重点：
- 结合课程资料、最近学习记录和课程资料文件处理问题。
- 面向飞书、QQ、Slack、Discord 等消息入口处理消息。
- 通过定时任务主动巡检、日报、复盘和提醒。
- 默认给出可执行结果，只在必要时解释过程。`;

export function AgentsPage() {
  const params = useParams({ strict: false }) as { botId?: string };
  const location = useLocation();
  const pageRef = useRef<HTMLDivElement | null>(null);
  const [view, setView] = useState<AgentWorkspaceView>("schedule");
  const [selectedBotId, setSelectedBotId] = useState<string | null>(null);
  const [activeFileName, setActiveFileName] = useState<string | null>("SOUL.md");
  const [newFileName, setNewFileName] = useState("");
  const [chatDraft, setChatDraft] = useState<{ id: number; text: string } | null>(null);
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
  const defaultChannels = useMemo(() => defaultChannelsConfig(), []);
  const defaultTools = useMemo(() => defaultToolsConfig(), []);
  const defaultAgent = useMemo(() => defaultAgentConfig(), []);
  const defaultHeartbeat = useMemo(() => defaultHeartbeatConfig(), []);
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

  useEffect(() => {
    pageRef.current?.scrollTo({ top: 0, left: 0 });
  }, [activeBotId, view]);

  const createWorkspaceFile = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!activeBotId || !newFileName.trim()) return;
    const filename = newFileName.trim();
    await mutations.writeFile.mutateAsync({ botId: activeBotId, filename, content: "" });
    setActiveFileName(filename);
    setNewFileName("");
  };

  return (
    <div ref={pageRef} className="dt-dynamic-page h-full overflow-y-auto px-3.5 py-3.5 pb-20 lg:px-4 lg:pb-4">
      <div className="mx-auto max-w-[1080px] space-y-3.5">
        <motion.section
          className="dt-page-header dt-page-header-accent-purple p-3.5"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22 }}
        >
          <div className="flex flex-wrap items-start justify-between gap-3.5">
            <div className="min-w-0">
              <p className="text-xs font-semibold text-brand-purple">课程助教</p>
              <h1 className="mt-1 text-xl font-semibold leading-tight text-ink">让课程助教按时推进</h1>
              <p className="mt-2 max-w-2xl text-xs leading-5 text-slate-600">
                把定时提醒、群聊回复和资料同步收在这里；日常学习入口仍回到学习、资料和记录。
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button tone="primary" onClick={() => setView("schedule")}>
                <CalendarClock size={16} />
                定时提醒
              </Button>
              <Button tone="secondary" onClick={() => setView("workspace")}>
                <PlugZap size={16} />
                资料与群聊
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
              <SparkBotChatTest key={`${activeBotId ?? "none"}:${chatDraft?.id ?? 0}`} bot={activeBotSummary} initialInput={chatDraft?.text ?? ""} />
            </div>
          </div>
        ) : null}

        {view === "workspace" ? (
          activeBotId ? (
            <div className="grid min-w-0 gap-4">
              <div className="min-w-0">
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
              </div>
              <div className="min-w-0">
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
                title="回复策略"
                value={activeBot.data?.agent ?? defaultAgent}
                pending={mutations.update.isPending}
                onSave={(agent) => mutations.update.mutateAsync({ botId: activeBotId, payload: { agent } })}
              />
              <JsonEditor
                title="提醒策略"
                value={activeBot.data?.heartbeat ?? defaultHeartbeat}
                pending={mutations.update.isPending}
                onSave={(heartbeat) => mutations.update.mutateAsync({ botId: activeBotId, payload: { heartbeat } })}
              />
              <section className="rounded-lg border border-line bg-white p-3">
                <div className="flex items-center gap-2">
                  <MessageSquareText size={18} className="text-brand-purple" />
                  <h2 className="text-base font-semibold text-ink">快捷检查</h2>
                </div>
                <div className="mt-4 border-t border-line pt-4">
                  <Button
                    tone="secondary"
                    onClick={() => {
                      setView("assistants");
                      setChatDraft({ id: Date.now(), text: "列出当前提醒任务" });
                    }}
                  >
                    <MessageSquareText size={16} />
                    查看提醒列表
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
        <p className="text-sm font-semibold text-ink">当前助教</p>
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
            {loading ? "正在读取助教..." : "创建一个助教后开始配置定时提醒。"}
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
      <AssistantFact label="当前助教" value={bot?.name || bot?.bot_id || "未选择"} />
      <AssistantFact label="运行状态" value={running ? `${running} 个在线` : "未启动"} />
      <AssistantFact label="提醒任务" value={`${jobs} 个`} />
      <AssistantFact label="资料文件" value={`${files} 个`} />
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
          <h2 className="text-base font-semibold text-ink">还没有课程助教</h2>
          <p className="mt-1 text-sm leading-6 text-slate-500">先创建助教，再配置提醒、消息入口和资料工作区。</p>
        </div>
        <Button tone="primary" onClick={onCreate}>
          <Bot size={16} />
          创建助教
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
          <h2 className="text-base font-semibold text-ink">课程助教</h2>
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
              if (window.confirm(`彻底删除助教 ${bot.bot_id}？`)) void onDestroy(bot.bot_id);
            }}
          />
        ))}
      </div>
      {!bots.length ? (
        <p className="mt-4 rounded-lg border border-dashed border-line bg-canvas p-4 text-sm leading-6 text-slate-500">
          还没有课程助教。右侧创建一个后，就可以配置提醒、消息入口和资料工作区。
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
            <p className="mt-1 line-clamp-2 text-sm leading-6 text-slate-500">{bot.description || bot.model || "课程助教"}</p>
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
  const suggestedBotId = useMemo(() => nextAvailableBotId(existingBotIds), [existingBotIds]);
  const [customBotId, setCustomBotId] = useState("");
  const [botIdEdited, setBotIdEdited] = useState(false);
  const [name, setName] = useState("课程助教");
  const [description, setDescription] = useState("支持课程资料、群聊消息和定时提醒的长期助教。");
  const [persona, setPersona] = useState(DEFAULT_PERSONA);
  const [autoStart, setAutoStart] = useState(true);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const botId = botIdEdited ? customBotId : suggestedBotId;
  const trimmedBotId = botId.trim();
  const idExists = Boolean(trimmedBotId && existingBotIds.includes(trimmedBotId));

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!trimmedBotId) return;
    if (idExists) {
      setSaved("");
      setError(`助教标识 "${trimmedBotId}" 已存在。请选择左侧卡片启动它，或换一个新的助教标识。`);
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
      setCustomBotId("");
    } catch (createError) {
      setSaved("");
      setError(createError instanceof Error ? createError.message : "创建助教失败。");
    }
  };

  return (
    <section className="rounded-lg border border-line bg-white p-3" data-testid="sparkbot-create-toggle">
      <div className="flex items-center gap-2">
        <Bot size={18} className="text-brand-purple" />
        <h2 className="text-base font-semibold text-ink">创建课程助教</h2>
      </div>
      <form className="mt-4 grid gap-3 border-t border-line pt-4" onSubmit={submit}>
        <FieldShell label="助教标识">
          <TextInput
            value={botId}
            onChange={(event) => {
              setBotIdEdited(true);
              setCustomBotId(event.target.value);
              setError("");
              setSaved("");
            }}
            data-testid="assistant-create-bot-id"
          />
        </FieldShell>
        {idExists ? (
          <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-700">
            这个助教标识已经存在。创建新助教请换一个标识；已有助教请在左侧列表直接启动或配置。
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
          <span>创建后立即启用</span>
        </label>
        <FieldShell label="助教设定">
          <TextArea value={persona} onChange={(event) => setPersona(event.target.value)} className="min-h-28" data-testid="assistant-create-persona" />
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
            <h2 className="text-base font-semibold text-ink">资料与群聊</h2>
          </div>
          <Badge tone={bot?.running ? "success" : "neutral"}>{bot?.running ? "运行中" : "停止"}</Badge>
        </div>
        <div className="mt-4 grid gap-3 border-t border-line pt-4">
          <ChannelBadges title="已连接入口" values={configuredChannels} fallback="未启用" />
          <ChannelBadges title="可连接入口" values={availableChannels.length ? availableChannels : ["feishu", "qq", "slack", "discord"]} />
        </div>
      </section>

      <ChannelConfigPanel schemas={schemas} channels={channels} pending={pending} onSave={onSaveChannels} />
      <SkillsManagerPanel botId={botId} pending={pending} onSave={onSaveSkill} onUpload={onUploadSkill} />
      <McpServersEditor tools={tools} pending={pending} onSave={onSaveTools} />

      <JsonEditor
        title="高级消息入口 JSON"
        value={channels}
        pending={pending}
        testId="sparkbot-channel-json-editor"
        onSave={onSaveChannels}
      />
      <JsonEditor
        title="外部连接规则"
        value={tools}
        pending={pending}
        onSave={onSaveTools}
      />
    </div>
  );
}

function ChannelConfigPanel({
  schemas,
  channels,
  pending,
  onSave,
}: {
  schemas?: SparkBotSchemas;
  channels: Record<string, unknown>;
  pending: boolean;
  onSave: (channels: Record<string, unknown>) => Promise<unknown>;
}) {
  const schemaChannels = schemas?.channels ?? {};
  const channelNames = orderChannelNames(Object.keys(schemaChannels));
  const configuredNames = Object.entries(channels)
    .filter(([, value]) => isRecord(value) && value.enabled)
    .map(([name]) => name);
  const [selectedName, setSelectedName] = useState(() => configuredNames[0] || (channelNames.includes("qq") ? "qq" : channelNames[0] || ""));
  const effectiveName = selectedName && channelNames.includes(selectedName) ? selectedName : channelNames.includes("qq") ? "qq" : channelNames[0] || "";

  if (!schemas || !channelNames.length) {
    return (
      <section className="rounded-lg border border-line bg-white p-3">
        <div className="flex items-center gap-2">
          <PlugZap size={18} className="text-brand-purple" />
          <h2 className="text-base font-semibold text-ink">消息入口配置</h2>
        </div>
        <p className="mt-3 rounded-lg border border-dashed border-line bg-canvas p-3 text-sm text-slate-500">
          渠道配置清单正在加载。需要时可以先使用下方高级 JSON。
        </p>
      </section>
    );
  }

  const selectedSchema = schemaChannels[effectiveName];

  return (
    <section className="rounded-lg border border-line bg-white p-3" data-testid="sparkbot-channel-config-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <PlugZap size={18} className="text-brand-purple" />
          <h2 className="text-base font-semibold text-ink">消息入口配置</h2>
        </div>
        <Badge tone="neutral">{configuredNames.length ? `${configuredNames.length} 个已启用` : "未启用"}</Badge>
      </div>

      <ChannelGlobalEditor
        schema={schemas.global}
        channels={channels}
        pending={pending}
        onSave={onSave}
      />

      <div className="mt-4 border-t border-line pt-4">
        <div className="flex gap-2 overflow-x-auto pb-1">
          {channelNames.map((name) => {
            const schema = schemaChannels[name];
            const config = isRecord(channels[name]) ? channels[name] : schema.default_config;
            const enabled = isRecord(config) && config.enabled === true;
            return (
              <button
                key={name}
                type="button"
                onClick={() => setSelectedName(name)}
                className={`shrink-0 rounded-lg border px-3 py-2 text-left text-sm transition ${
                  effectiveName === name
                    ? "border-brand-purple-300 bg-tint-lavender text-brand-purple"
                    : "border-line bg-white text-slate-600 hover:border-brand-purple-300"
                }`}
                data-testid={`sparkbot-channel-card-${name}`}
              >
                <span className="block font-medium">{channelDisplayName(name, schema)}</span>
                <span className="mt-1 block text-xs text-slate-500">{enabled ? "已启用" : "未启用"}</span>
              </button>
            );
          })}
        </div>

        {selectedSchema ? (
          <ChannelDetailEditor
            key={effectiveName}
            name={effectiveName}
            schema={selectedSchema}
            channels={channels}
            pending={pending}
            onSave={onSave}
          />
        ) : null}
      </div>
    </section>
  );
}

function ChannelGlobalEditor({
  schema,
  channels,
  pending,
  onSave,
}: {
  schema?: SparkBotChannelSchema;
  channels: Record<string, unknown>;
  pending: boolean;
  onSave: (channels: Record<string, unknown>) => Promise<unknown>;
}) {
  const properties = schemaProperties(schema?.json_schema);
  const initialDraft = useMemo(() => {
    const draft: Record<string, unknown> = {};
    for (const [name, propSchema] of Object.entries(properties)) {
      draft[name] = channels[name] ?? schemaDefaultValue(propSchema);
    }
    return draft;
  }, [channels, properties]);

  return (
    <ChannelSchemaForm
      title="全局规则"
      submitLabel="保存全局"
      channelName="global"
      draftKey={JSON.stringify(initialDraft)}
      initialDraft={initialDraft}
      properties={properties}
      secretFields={schema?.secret_fields ?? []}
      pending={pending}
      testId="sparkbot-global-channel-editor"
      onSubmit={(draft) => onSave({ ...channels, ...normalizeSchemaDraft(draft, properties) })}
    />
  );
}

function ChannelDetailEditor({
  name,
  schema,
  channels,
  pending,
  onSave,
}: {
  name: string;
  schema: SparkBotChannelSchema;
  channels: Record<string, unknown>;
  pending: boolean;
  onSave: (channels: Record<string, unknown>) => Promise<unknown>;
}) {
  const properties = schemaProperties(schema.json_schema);
  const initialDraft = useMemo(
    () => ({ ...(schema.default_config ?? {}), ...(isRecord(channels[name]) ? channels[name] : {}) }),
    [channels, name, schema.default_config],
  );

  return (
    <ChannelSchemaForm
      title={channelDisplayName(name, schema)}
      submitLabel="保存渠道"
      channelName={name}
      draftKey={`${name}:${JSON.stringify(initialDraft)}`}
      initialDraft={initialDraft}
      properties={properties}
      secretFields={schema.secret_fields ?? []}
      pending={pending}
      testId={`sparkbot-channel-editor-${name}`}
      onSubmit={(draft) => {
        const nextConfig = normalizeChannelConfig(normalizeSchemaDraft(draft, properties), properties);
        return onSave({ ...channels, [name]: nextConfig });
      }}
    />
  );
}

function ChannelSchemaForm({
  title,
  submitLabel,
  channelName,
  draftKey,
  initialDraft,
  properties,
  secretFields,
  pending,
  testId,
  onSubmit,
}: {
  title: string;
  submitLabel: string;
  channelName: string;
  draftKey: string;
  initialDraft: Record<string, unknown>;
  properties: Record<string, Record<string, unknown>>;
  secretFields: string[];
  pending: boolean;
  testId?: string;
  onSubmit: (draft: Record<string, unknown>) => Promise<unknown>;
}) {
  return (
    <ChannelSchemaFormDraft
      key={draftKey}
      title={title}
      submitLabel={submitLabel}
      channelName={channelName}
      initialDraft={initialDraft}
      properties={properties}
      secretFields={secretFields}
      pending={pending}
      testId={testId}
      onSubmit={onSubmit}
    />
  );
}

function ChannelSchemaFormDraft({
  title,
  submitLabel,
  channelName,
  initialDraft,
  properties,
  secretFields,
  pending,
  testId,
  onSubmit,
}: {
  title: string;
  submitLabel: string;
  channelName: string;
  initialDraft: Record<string, unknown>;
  properties: Record<string, Record<string, unknown>>;
  secretFields: string[];
  pending: boolean;
  testId?: string;
  onSubmit: (draft: Record<string, unknown>) => Promise<unknown>;
}) {
  const [draft, setDraft] = useState(initialDraft);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const updateField = (name: string, value: unknown) => {
    setDraft((current) => ({ ...current, [name]: value }));
    setSaved(false);
  };

  return (
    <form
      className="mt-4 grid gap-3"
      data-testid={testId}
      onSubmit={async (event) => {
        event.preventDefault();
        try {
          setError("");
          setSaved(false);
          await onSubmit(draft);
          setSaved(true);
        } catch (submitError) {
          setError(submitError instanceof Error ? submitError.message : "保存渠道配置失败。");
        }
      }}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
        <Button tone="secondary" type="submit" disabled={pending}>
          {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
          {submitLabel}
        </Button>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {Object.entries(properties).map(([name, propSchema]) => (
          <ChannelField
            key={name}
            channelName={channelName}
            name={name}
            schema={propSchema}
            value={draft[name] ?? schemaDefaultValue(propSchema)}
            secret={secretFields.includes(name)}
            onChange={(value) => updateField(name, value)}
          />
        ))}
      </div>
      {error ? <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-brand-red">{error}</p> : null}
      {saved ? <p className="text-sm text-emerald-700">已保存。</p> : null}
    </form>
  );
}

function ChannelField({
  channelName,
  name,
  schema,
  value,
  secret,
  onChange,
}: {
  channelName: string;
  name: string;
  schema: Record<string, unknown>;
  value: unknown;
  secret: boolean;
  onChange: (value: unknown) => void;
}) {
  const label = channelFieldLabel(name, schema);
  const hint = channelFieldHint(channelName, name, schema);
  const enumValues = Array.isArray(schema.enum) ? schema.enum.map(String) : [];
  const type = schemaType(schema);
  const testId = `channel-field-${name.replaceAll(".", "-")}`;

  if (type === "boolean") {
    return (
      <label className="flex min-h-16 items-start gap-2 rounded-lg border border-line bg-canvas/70 p-3 text-sm text-slate-600">
        <input
          type="checkbox"
          checked={value === true}
          onChange={(event) => onChange(event.target.checked)}
          className="mt-1"
          data-testid={testId}
        />
        <span>
          <span className="block font-medium text-ink">{label}</span>
          {hint ? <span className="mt-1 block text-xs text-slate-500">{hint}</span> : null}
        </span>
      </label>
    );
  }

  if (enumValues.length) {
    return (
      <FieldShell label={label} hint={hint}>
        <SelectInput value={String(value ?? "")} onChange={(event) => onChange(event.target.value)} data-testid={testId}>
          {enumValues.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </SelectInput>
      </FieldShell>
    );
  }

  if (type === "array") {
    return (
      <FieldShell label={label} hint={hint || "多个值用逗号或换行分隔"}>
        <TextArea
          value={arrayFieldText(value)}
          onChange={(event) => onChange(event.target.value)}
          className="min-h-16"
          data-testid={testId}
        />
      </FieldShell>
    );
  }

  if (type === "object") {
    return (
      <FieldShell label={label} hint={hint || "结构化配置，保存时按 JSON 解析"}>
        <TextArea
          value={objectFieldText(value)}
          onChange={(event) => onChange(event.target.value)}
          className="min-h-24 font-mono text-xs sm:col-span-2"
          data-testid={testId}
        />
      </FieldShell>
    );
  }

  return (
    <FieldShell label={label} hint={hint}>
      <TextInput
        type={type === "number" || type === "integer" ? "number" : secret ? "password" : "text"}
        value={String(value ?? "")}
        onChange={(event) => onChange(event.target.value)}
        data-testid={testId}
      />
    </FieldShell>
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

function schemaProperties(schema?: Record<string, unknown>) {
  const properties = isRecord(schema?.properties) ? schema.properties : {};
  return Object.fromEntries(
    Object.entries(properties).filter((entry): entry is [string, Record<string, unknown>] => isRecord(entry[1])),
  );
}

function schemaType(schema: Record<string, unknown>): string {
  const rawType = schema.type;
  if (typeof rawType === "string") return rawType;
  if (Array.isArray(rawType)) {
    const first = rawType.find((item) => item !== "null");
    if (typeof first === "string") return first;
  }
  const variants = Array.isArray(schema.anyOf) ? schema.anyOf : Array.isArray(schema.oneOf) ? schema.oneOf : [];
  for (const variant of variants) {
    if (!isRecord(variant)) continue;
    const variantType: string = schemaType(variant);
    if (variantType && variantType !== "null") return variantType;
  }
  if (Array.isArray(schema.enum)) return "string";
  if (isRecord(schema.properties)) return "object";
  return "string";
}

function schemaDefaultValue(schema: Record<string, unknown>) {
  if ("default" in schema) return schema.default;
  const type = schemaType(schema);
  if (type === "boolean") return false;
  if (type === "array") return [];
  if (type === "object") return {};
  if (type === "number" || type === "integer") return "";
  const enumValues = Array.isArray(schema.enum) ? schema.enum : [];
  if (enumValues.length) return enumValues[0];
  return "";
}

function normalizeSchemaDraft(draft: Record<string, unknown>, properties: Record<string, Record<string, unknown>>) {
  const normalized: Record<string, unknown> = { ...draft };
  for (const [name, schema] of Object.entries(properties)) {
    normalized[name] = normalizeSchemaValue(name, draft[name] ?? schemaDefaultValue(schema), schema);
  }
  return normalized;
}

function normalizeSchemaValue(name: string, value: unknown, schema: Record<string, unknown>): unknown {
  const type = schemaType(schema);
  if (type === "boolean") return value === true;
  if (type === "integer") {
    const text = String(value ?? "").trim();
    if (!text && "default" in schema) return schema.default;
    const parsed = Number(text);
    if (!Number.isFinite(parsed)) throw new Error(`${channelFieldLabel(name, schema)} 必须是数字。`);
    return Math.trunc(parsed);
  }
  if (type === "number") {
    const text = String(value ?? "").trim();
    if (!text && "default" in schema) return schema.default;
    const parsed = Number(text);
    if (!Number.isFinite(parsed)) throw new Error(`${channelFieldLabel(name, schema)} 必须是数字。`);
    return parsed;
  }
  if (type === "array") {
    if (Array.isArray(value)) return value.map(String).map((item) => item.trim()).filter(Boolean);
    return String(value ?? "")
      .split(/[\n,]/)
      .map((item) => item.trim())
      .filter(Boolean);
  }
  if (type === "object") {
    if (isRecord(value)) return value;
    const text = String(value ?? "").trim();
    if (!text) return {};
    const parsed = JSON.parse(text) as unknown;
    if (!isRecord(parsed)) throw new Error(`${channelFieldLabel(name, schema)} 必须是 JSON 对象。`);
    return parsed;
  }
  return String(value ?? "");
}

function normalizeChannelConfig(config: Record<string, unknown>, properties: Record<string, Record<string, unknown>>) {
  const next = { ...config };
  if (next.enabled === true && properties.allow_from && (!Array.isArray(next.allow_from) || next.allow_from.length === 0)) {
    next.allow_from = ["*"];
  }
  return next;
}

function arrayFieldText(value: unknown) {
  return Array.isArray(value) ? value.map(String).join("\n") : String(value ?? "");
}

function objectFieldText(value: unknown) {
  if (!value) return "";
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

function channelDisplayName(name: string, schema?: SparkBotChannelSchema) {
  const labels: Record<string, string> = {
    dingtalk: "钉钉",
    discord: "Discord",
    email: "邮箱",
    feishu: "飞书",
    matrix: "Matrix",
    mochat: "Mochat",
    qq: "QQ",
    slack: "Slack",
    telegram: "Telegram",
    web: "网页",
    wecom: "企业微信",
    whatsapp: "WhatsApp",
  };
  return labels[name] || schema?.display_name || name;
}

function channelFieldLabel(name: string, schema: Record<string, unknown>) {
  const labels: Record<string, string> = {
    access_token: "访问令牌",
    allow_from: "允许来源",
    app_id: "App ID",
    app_secret: "App Secret",
    app_token: "App Token",
    base_url: "服务地址",
    bot_id: "机器人 ID",
    bot_token: "Bot Token",
    client_id: "Client ID",
    client_secret: "Client Secret",
    enabled: "启用",
    encrypt_key: "加密 Key",
    group_policy: "群聊规则",
    imap_host: "IMAP 主机",
    imap_password: "IMAP 密码",
    imap_username: "IMAP 用户名",
    msg_format: "消息格式",
    rate_limit: "频率限制",
    secret: "Secret",
    send_progress: "发送进度",
    send_tool_hints: "发送工具提示",
    smtp_host: "SMTP 主机",
    smtp_password: "SMTP 密码",
    smtp_username: "SMTP 用户名",
    token: "Token",
    transcription_api_key: "语音转写 Key",
    verification_token: "Verification Token",
    webhook_url: "Webhook URL",
    welcome_text: "欢迎语",
  };
  return labels[name] || String(schema.title || name);
}

function channelFieldHint(channelName: string, name: string, schema: Record<string, unknown>) {
  const contextualHints: Record<string, string> = {
    "discord.gateway_url": "默认使用 Discord Gateway v10；只有自建代理时才需要改。",
    "discord.guild_id": "可选：限制到指定服务器；不填则按机器人加入的服务器接收事件。",
    "discord.intents": "默认包含消息内容权限；还需要在 Discord Developer Portal 开启 Message Content Intent。",
    "discord.token": "Discord Developer Portal 的 Bot Token；保存后按敏感字段处理。",
    "dingtalk.client_id": "钉钉开放平台应用凭证，部分页面也叫 AppKey 或 Client ID；Stream 模式必填。",
    "dingtalk.client_secret": "钉钉开放平台应用密钥，部分页面也叫 AppSecret 或 Client Secret。",
    "email.consent_granted": "确认该邮箱允许 SparkBot 自动读取并回复；未确认时不要启用。",
    "email.from_address": "外发显示地址；通常与 SMTP 用户名一致。",
    "email.imap_host": "邮箱收件服务器，例如 imap.example.com；需要账号开启 IMAP。",
    "email.imap_password": "建议使用邮箱应用专用密码，不要填写网页登录密码。",
    "email.smtp_host": "邮箱发件服务器，例如 smtp.example.com。",
    "email.smtp_password": "建议使用邮箱应用专用密码，不要填写网页登录密码。",
    "feishu.app_id": "飞书开放平台应用的 App ID；长连接事件订阅和发消息共用。",
    "feishu.app_secret": "飞书开放平台应用的 App Secret；保存后按敏感字段处理。",
    "feishu.encrypt_key": "飞书事件订阅的 Encrypt Key；未开启事件加密时可留空。",
    "feishu.verification_token": "飞书事件订阅的 Verification Token；长连接事件校验使用。",
    "matrix.access_token": "Matrix 账号访问令牌；建议使用专用机器人账号生成。",
    "matrix.device_id": "可选：生成令牌时的设备 ID；启用加密房间时建议填写并保留 store。",
    "matrix.e2ee_enabled": "默认关闭以保证安装稳定；加密房间需要额外安装 matrix-nio[e2e] 和 python-olm。",
    "matrix.homeserver": "Matrix homeserver 地址，例如 https://matrix.org 或你的自建服务。",
    "matrix.user_id": "机器人 Matrix 用户 ID，例如 @bot:matrix.org。",
    "mochat.base_url": "Mochat/ClawHub HTTP 服务地址；不是通用聊天平台配置。",
    "mochat.claw_token": "Mochat/ClawHub 接入令牌；保存后按敏感字段处理。",
    "mochat.socket_url": "Mochat/ClawHub Socket.IO 地址；留空时使用服务默认地址。",
    "qq.app_id": "QQ 机器人开放平台的 AppID；需要开通对应消息事件权限。",
    "qq.msg_format": "plain 更稳；markdown 需要 QQ 平台侧模板/消息能力支持。",
    "qq.secret": "QQ 机器人开放平台 Secret；保存后按敏感字段处理。",
    "slack.app_token": "Slack Socket Mode 的 App-Level Token，通常以 xapp- 开头并包含 connections:write。",
    "slack.bot_token": "Slack Bot Token，通常以 xoxb- 开头；需要 chat:write、app_mentions:read、im/history 等权限。",
    "slack.mode": "当前实现支持 Socket Mode；需要在 Slack 应用中开启 Socket Mode 和事件订阅。",
    "slack.user_token_read_only": "预留只读用户令牌开关；当前核心收发仍以 Bot Token 为主。",
    "telegram.proxy": "可选 HTTP/SOCKS 代理；只在本机访问 Telegram 受限时填写。",
    "telegram.reply_to_message": "开启后外部回复更像原平台线程；部分群聊可保持关闭。",
    "telegram.token": "BotFather 创建机器人后给出的 Bot Token；保存后按敏感字段处理。",
    "web.rate_limit": "网页试问入口的每分钟限流；比赛演示保持 8 左右即可。",
    "web.welcome_text": "网页试问入口的默认欢迎语，建议写成学习下一步而不是功能介绍。",
    "wecom.bot_id": "企业微信智能机器人 Bot ID；用于 SDK WebSocket 鉴权。",
    "wecom.secret": "企业微信智能机器人 Secret；保存后按敏感字段处理。",
    "wecom.welcome_message": "进入会话事件触发的欢迎语，需要企业微信侧支持该事件。",
    "whatsapp.bridge_token": "本地或第三方 WhatsApp WebSocket 桥接服务的认证 Token。",
    "whatsapp.bridge_url": "当前实现连接 WebSocket 桥接服务，不是 Meta WhatsApp Cloud API 直连。",
  };
  const hints: Record<string, string> = {
    allow_from: "测试可填 *；上线建议填写指定用户或群 ID",
    app_id: "在对应开放平台创建机器人后获得",
    app_secret: "在对应开放平台创建机器人后获得；保存后按敏感字段处理",
    bot_token: "平台机器人 Token；保存后按敏感字段处理",
    client_id: "开放平台应用凭证；按渠道官方页面填写",
    client_secret: "开放平台应用密钥；保存后按敏感字段处理",
    secret: "保存后会按敏感字段处理",
    send_progress: "开启后会把助教执行过程同步到外部入口",
    send_tool_hints: "通常比赛演示关闭，调试时可开启",
    token: "平台机器人 Token；保存后按敏感字段处理",
    transcription_api_key: "用于外部语音消息转写；不填则使用环境变量或关闭语音转写",
  };
  const contextual = contextualHints[`${channelName}.${name}`];
  if (contextual) return contextual;
  return hints[name] || (typeof schema.description === "string" ? schema.description : undefined);
}

function orderChannelNames(names: string[]) {
  const priority = ["qq", "feishu", "wecom", "dingtalk", "telegram", "slack", "discord", "email", "whatsapp", "matrix", "mochat", "web"];
  return [...names].sort((a, b) => {
    const ai = priority.indexOf(a);
    const bi = priority.indexOf(b);
    if (ai !== -1 || bi !== -1) return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
    return a.localeCompare(b);
  });
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

function SkillEditor({
  selectedSkill,
  isNew,
  pending,
  onNew,
  onSave,
}: {
  selectedSkill?: SparkBotSkill;
  isNew: boolean;
  pending: boolean;
  onNew: () => void;
  onSave: (skillName: string, content: string) => Promise<unknown>;
}) {
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

function WorkspaceFileEditor({
  filename,
  initialContent,
  pending,
  loading,
  onSaveFile,
}: {
  filename: string;
  initialContent: string;
  pending: boolean;
  loading: boolean;
  onSaveFile: (content: string) => Promise<unknown>;
}) {
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

function BotProfilePanel({
  bot,
  pending,
  onSave,
}: {
  bot?: SparkBotSummary;
  pending: boolean;
  onSave: (payload: Partial<Pick<SparkBotSummary, "name" | "description" | "persona" | "model" | "auto_start">>) => Promise<unknown>;
}) {
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

function BotProfileForm({
  bot,
  pending,
  onSave,
}: {
  bot: SparkBotSummary;
  pending: boolean;
  onSave: (payload: Partial<Pick<SparkBotSummary, "name" | "description" | "persona" | "model" | "auto_start">>) => Promise<unknown>;
}) {
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

function SparkBotChatTest({
  bot,
  initialInput,
}: {
  bot?: SparkBotSummary;
  initialInput: string;
}) {
  const [input, setInput] = useState(initialInput);
  const [messages, setMessages] = useState<Array<{ role: "user" | "bot"; content: string }>>([]);
  const [busy, setBusy] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);
  const canSend = Boolean(bot?.bot_id && bot.running && !busy);

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
          setMessages((current) => replaceLastBotMessage(current, data.content || "助教回复失败。"));
          setBusy(false);
        }
      } catch {
        setMessages((current) => replaceLastBotMessage(current, "助教回复格式异常。"));
        setBusy(false);
      }
    };
    socket.onerror = () => {
      setMessages((current) => replaceLastBotMessage(current, "无法连接助教服务。"));
      setBusy(false);
    };
    socket.onclose = () => setBusy(false);
  };

  return (
    <section className="rounded-lg border border-line bg-white p-3" data-testid="sparkbot-chat">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <MessageSquareText size={18} className="text-brand-purple" />
          <h2 className="text-base font-semibold text-ink">试问助教</h2>
        </div>
        <Badge tone={bot?.running ? "success" : "neutral"}>{bot?.running ? "可测试" : "先启动助教"}</Badge>
      </div>
      <div className="mt-4 max-h-60 space-y-2 overflow-y-auto rounded-lg border border-line bg-canvas p-3">
        {messages.map((message, index) => (
          <div
            key={`${message.role}-${index}`}
            className={`rounded-lg border p-3 text-sm leading-6 ${
              message.role === "user" ? "ml-auto max-w-[82%] border-brand-purple-300 bg-tint-lavender" : "mr-auto max-w-[82%] border-line bg-white"
            }`}
          >
            <p className="text-xs font-semibold text-slate-500">{message.role === "user" ? "我" : "助教"}</p>
            <p className="mt-1 whitespace-pre-wrap text-slate-700">{message.content || "等待回复..."}</p>
          </div>
        ))}
        {!messages.length ? <p className="text-sm leading-6 text-slate-500">这里仅用于测试助教回复。正式任务优先通过群聊和定时提醒运行。</p> : null}
      </div>
      <form className="mt-3 flex gap-2" onSubmit={send}>
        <TextInput value={input} onChange={(event) => setInput(event.target.value)} placeholder="输入一句测试消息，例如：列出提醒" data-testid="sparkbot-chat-input" />
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
  const initialDraft = useMemo(() => JSON.stringify(value, null, 2), [value]);

  return <JsonEditorDraft key={initialDraft} title={title} initialDraft={initialDraft} pending={pending} testId={testId} onSave={onSave} />;
}

function JsonEditorDraft({
  title,
  initialDraft,
  pending,
  testId,
  onSave,
}: {
  title: string;
  initialDraft: string;
  pending: boolean;
  testId?: string;
  onSave: (value: Record<string, unknown>) => Promise<unknown>;
}) {
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
    web: {
      enabled: true,
      welcome_text: "我会先看学习画像和课程资料，再给出今天最应该完成的一步。",
      rate_limit: 8,
    },
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
