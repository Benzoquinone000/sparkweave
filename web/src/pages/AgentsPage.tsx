import { CalendarClock, MessageSquareText, PlugZap } from "lucide-react";
import { useLocation, useParams } from "@tanstack/react-router";
import type { FormEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";

import { Button } from "@/components/ui/Button";
import {
  useSparkBotChannelSchemas,
  useSparkBotCronJobs,
  useSparkBotDetail,
  useSparkBotFile,
  useSparkBotFiles,
  useSparkBotMutations,
  useSparkBotRecent,
  useSparkBots,
} from "@/hooks/useApiQueries";
import { AgentWorkspaceTabs, SparkBotRecentPanel, type AgentWorkspaceView } from "./agents/AgentWorkspaceChrome";
import { AssistantStats, BotRail, BotRoster, CreateBotPanel, NoBotCallout } from "./agents/SparkBotAssistantPanels";
import { ChannelMcpPanel } from "./agents/SparkBotChannelPanel";
import { SparkBotChatTest } from "./agents/SparkBotChatTest";
import { SparkBotCronPanel } from "./agents/SparkBotCronPanel";
import { BotProfilePanel, JsonEditor, WorkspaceFilesPanel } from "./agents/SparkBotWorkspacePanels";
import { orderWorkspaceFiles } from "./agents/workspaceFiles";

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
                新建提醒
              </Button>
              <Button tone="secondary" onClick={() => setView("workspace")}>
                <PlugZap size={16} />
                接入群聊
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
