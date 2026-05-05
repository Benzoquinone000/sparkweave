import {
  BookOpen,
  Bot,
  Clock3,
  FileText,
  HelpCircle,
  Loader2,
  MessageSquareText,
  PenTool,
  Play,
  RefreshCw,
  Save,
  Search,
  SendHorizontal,
  Square,
  Trash2,
  Wand2,
  type LucideIcon,
} from "lucide-react";
import { useLocation, useParams } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FieldShell, SelectInput, TextArea, TextInput } from "@/components/ui/Field";
import { NotionProductHero } from "@/components/ui/NotionProductHero";
import { sparkBotSocketUrl } from "@/lib/api";
import type { AgentUiConfig, SparkBotChannelSchema, SparkBotFile, SparkBotRecentItem, SparkBotSoul, SparkBotSummary } from "@/lib/types";
import {
  useAgentConfigDetail,
  useAgentConfigs,
  useSparkBotChannelSchemas,
  useSparkBotDetail,
  useSparkBotFile,
  useSparkBotFiles,
  useSparkBotHistory,
  useSparkBotMutations,
  useSparkBotRecent,
  useSparkBotSoulDetail,
  useSparkBotSouls,
  useSparkBots,
} from "@/hooks/useApiQueries";

type AgentWorkspaceView = "assistants" | "capabilities" | "workspace" | "advanced";

export function AgentsPage() {
  const params = useParams({ strict: false }) as { botId?: string };
  const location = useLocation();
  const bots = useSparkBots();
  const agentConfigs = useAgentConfigs();
  const schemas = useSparkBotChannelSchemas();
  const souls = useSparkBotSouls();
  const recentBots = useSparkBotRecent(5);
  const mutations = useSparkBotMutations();
  const items = bots.data ?? [];
  const running = items.filter((item) => item.running).length;
  const [botId, setBotId] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [persona, setPersona] = useState("你是一个耐心、擅长追问和归纳的学习助教。");
  const [selectedBotId, setSelectedBotId] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [newFileName, setNewFileName] = useState("");
  const [selectedChannel, setSelectedChannel] = useState<string>("");
  const [selectedAgentType, setSelectedAgentType] = useState<string | null>(null);
  const [agentsView, setAgentsView] = useState<AgentWorkspaceView>("assistants");
  const pathBotId = /^\/agents\/([^/?#]+)\/chat/.exec(location.pathname)?.[1];
  const routeBotId = params.botId ? decodeURIComponent(params.botId) : pathBotId ? decodeURIComponent(pathBotId) : null;
  const activeBotId =
    selectedBotId && items.some((item) => item.bot_id === selectedBotId)
      ? selectedBotId
      : routeBotId && items.some((item) => item.bot_id === routeBotId)
        ? routeBotId
        : items[0]?.bot_id || null;
  const activeBot = useSparkBotDetail(activeBotId);
  const files = useSparkBotFiles(activeBotId);
  const history = useSparkBotHistory(activeBotId);
  const fileItems = useMemo(() => files.data ?? [], [files.data]);
  const activeFileName = selectedFile && fileItems.some((item) => item.filename === selectedFile) ? selectedFile : fileItems[0]?.filename || null;
  const activeFile = useSparkBotFile(activeBotId, activeFileName);
  const channelKeys = Object.keys(schemas.data?.channels ?? {});
  const activeChannel = selectedChannel && channelKeys.includes(selectedChannel) ? selectedChannel : channelKeys[0] || "";
  const channelSchema = activeChannel ? schemas.data?.channels?.[activeChannel] : undefined;
  const runtimeAgents = Object.entries(agentConfigs.data ?? {});
  const activeAgentType =
    selectedAgentType && runtimeAgents.some(([agentType]) => agentType === selectedAgentType)
      ? selectedAgentType
      : runtimeAgents[0]?.[0] || null;
  const activeAgentConfig = activeAgentType ? (agentConfigs.data ?? {})[activeAgentType] : undefined;
  const agentDetail = useAgentConfigDetail(activeAgentType);

  const createBot = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!botId.trim()) return;
    await mutations.create.mutateAsync({
      bot_id: botId.trim(),
      name: name.trim() || botId.trim(),
      description: description.trim(),
      persona: persona.trim(),
      auto_start: true,
    });
    setSelectedBotId(botId.trim());
    setBotId("");
    setName("");
    setDescription("");
  };

  const updateChannel = async (config: Record<string, unknown>) => {
    if (!activeBotId || !activeChannel) return;
    await mutations.update.mutateAsync({
      botId: activeBotId,
      payload: {
        channels: {
          ...(isRecord(activeBot.data?.channels) ? activeBot.data?.channels : {}),
          [activeChannel]: config,
        },
      },
    });
  };

  const updateGlobalChannels = async (config: Record<string, unknown>) => {
    if (!activeBotId) return;
    await mutations.update.mutateAsync({
      botId: activeBotId,
      payload: {
        channels: {
          ...(isRecord(activeBot.data?.channels) ? activeBot.data?.channels : {}),
          ...config,
        },
      },
    });
  };

  const createWorkspaceFile = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!activeBotId || !newFileName.trim()) return;
    const filename = newFileName.trim();
    await mutations.writeFile.mutateAsync({ botId: activeBotId, filename, content: "" });
    setSelectedFile(filename);
    setNewFileName("");
  };

  return (
    <div className="h-full overflow-y-auto px-4 py-4 pb-24 lg:px-5 lg:pb-5">
      <div className="mx-auto max-w-[1040px] space-y-4">
        <NotionProductHero
          eyebrow="SparkBot 学习助教"
          title="把常用助教收成一个小团队"
          description="日常只需要选择助教和能力。复杂配置放到下方，需要调试时再打开。"
          accent="purple"
          imageSrc="/illustrations/notion-agent-flow.svg"
          imageAlt="多智能体协作预览"
          people="working_laptop"
          previewTitle="助教替你接住重复问题"
          previewDescription="常驻人格、工具能力和资料文件会一起参与学习任务。"
          tiles={[
            { label: "助教", helper: "长期人格技能", tone: "lavender" },
            { label: "文件", helper: "工作区资料", tone: "sky" },
            { label: "协作", helper: "多智能体路径", tone: "yellow" },
          ]}
          actions={
            <>
              <Button tone="primary" onClick={() => setAgentsView("assistants")}>
                <Bot size={16} />
                管理助教
              </Button>
              <Button tone="secondary" onClick={() => setAgentsView("capabilities")}>
                <Wand2 size={16} />
                查看能力
              </Button>
            </>
          }
        />

        <AgentStatusStrip
          bots={items.length}
          running={running}
          recent={recentBots.data?.length ?? 0}
          capabilities={runtimeAgents.length}
        />

        <SparkBotRecentPanel
          items={recentBots.data ?? []}
          activeBotId={activeBotId}
          loading={recentBots.isFetching}
          onRefresh={() => void recentBots.refetch()}
          onSelect={(nextBotId) => setSelectedBotId(nextBotId)}
        />

        <AgentWorkspaceTabs
          value={agentsView}
          bots={items.length}
          capabilities={runtimeAgents.length}
          files={fileItems.length}
          onChange={setAgentsView}
        />

        {agentsView === "capabilities" ? (
          <motion.section
            key="agent-capabilities"
            className="rounded-lg border border-line bg-white p-3"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            data-testid="agent-capabilities-toggle"
          >
            <div>
              <div className="flex items-center gap-2">
                <HelpCircle size={18} className="text-brand-purple" />
                <h2 className="text-base font-semibold text-ink" aria-label="运行时智能体矩阵">助教能力</h2>
              </div>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
                常用学习能力集中在这里，演示和使用时可以快速进入。
              </p>
            </div>
            <div className="mt-4 flex justify-end border-t border-line pt-4">
            <Button tone="secondary" onClick={() => void agentConfigs.refetch()} disabled={agentConfigs.isFetching}>
              {agentConfigs.isFetching ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
              同步
            </Button>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3" data-testid="agent-config-matrix">
            {runtimeAgents.map(([agentType, config]) => (
              <AgentConfigCard
                key={agentType}
                agentType={agentType}
                config={config}
                active={activeAgentType === agentType}
                onInspect={() => setSelectedAgentType(agentType)}
              />
            ))}
          </div>
          {!runtimeAgents.length ? (
            <p className="mt-4 rounded-lg border border-dashed border-line bg-canvas p-4 text-sm text-slate-500">
              暂未读取到能力配置。
            </p>
          ) : null}
          <AgentConfigDetail
            agentType={activeAgentType}
            config={agentDetail.data ?? activeAgentConfig}
            loading={agentDetail.isFetching}
            error={agentDetail.error}
          />
          </motion.section>
        ) : null}

        {agentsView === "assistants" ? (
          <motion.div
            key="agent-assistants"
            className="space-y-4"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
          >
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
          <section className="rounded-lg border border-line bg-white p-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-base font-semibold text-ink">助教列表</h2>
              <Button tone="secondary" onClick={() => void bots.refetch()}>
                <RefreshCw size={16} />
                刷新
              </Button>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {items.map((bot) => (
                <BotCard
                  key={bot.bot_id}
                  bot={bot}
                  active={activeBotId === bot.bot_id}
                  pending={mutations.create.isPending || mutations.stop.isPending || mutations.destroy.isPending}
                  onSelect={() => setSelectedBotId(bot.bot_id)}
                  onStart={() => void mutations.create.mutateAsync({ bot_id: bot.bot_id, auto_start: true })}
                  onStop={() => void mutations.stop.mutateAsync(bot.bot_id)}
                  onDestroy={() => {
                    if (window.confirm(`彻底删除助教 ${bot.bot_id}？`)) void mutations.destroy.mutateAsync(bot.bot_id);
                  }}
                />
              ))}
            </div>
            {!items.length ? (
            <p className="mt-4 rounded-lg border border-dashed border-line bg-canvas p-4 text-sm leading-6 text-slate-500">
                暂未配置助教。创建一个助教后，可继续配置渠道和工作区文件。
              </p>
            ) : null}
          </section>

          <section className="rounded-lg border border-line bg-white p-3" data-testid="sparkbot-create-toggle">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-ink">创建助教</h2>
                <p className="mt-1 text-sm text-slate-500">需要新的常驻助教时再创建。</p>
              </div>
              <Badge tone="neutral">新建</Badge>
            </div>
            <form className="mt-4 grid gap-3 border-t border-line pt-4" onSubmit={createBot}>
              <FieldShell label="助教标识">
                <TextInput value={botId} onChange={(event) => setBotId(event.target.value)} placeholder="math_tutor" />
              </FieldShell>
              <FieldShell label="名称">
                <TextInput value={name} onChange={(event) => setName(event.target.value)} placeholder="高数助教" />
              </FieldShell>
              <FieldShell label="描述">
                <TextInput value={description} onChange={(event) => setDescription(event.target.value)} placeholder="答疑、追问、复盘" />
              </FieldShell>
              <FieldShell label="角色设定">
                <TextArea value={persona} onChange={(event) => setPersona(event.target.value)} />
              </FieldShell>
              {souls.data?.length ? (
                <FieldShell label="套用模板">
                  <SelectInput
                    value=""
                    onChange={(event) => {
                      const soul = souls.data?.find((item) => item.id === event.target.value);
                      if (soul) {
                        setPersona(soul.content);
                        setName((current) => current || soul.name);
                      }
                    }}
                  >
                    <option value="">选择一个模板</option>
                    {souls.data.map((soul) => (
                      <option key={soul.id} value={soul.id}>
                        {soul.name}
                      </option>
                    ))}
                  </SelectInput>
                </FieldShell>
              ) : null}
              <Button tone="primary" type="submit" disabled={!botId.trim() || mutations.create.isPending}>
                {mutations.create.isPending ? <Loader2 size={16} className="animate-spin" /> : <Bot size={16} />}
                创建并启动
              </Button>
            </form>
          </section>
        </div>

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
          <SparkBotChat botId={activeBotId} running={Boolean(activeBot.data?.running)} />
          <SoulLibrary
            souls={souls.data ?? []}
            pending={mutations.createSoul.isPending || mutations.updateSoul.isPending || mutations.deleteSoul.isPending}
            onUse={(soul) => {
              setPersona(soul.content);
              setName((current) => current || soul.name);
            }}
            onCreate={(soul) => mutations.createSoul.mutateAsync(soul)}
            onUpdate={(soulId, payload) => mutations.updateSoul.mutateAsync({ soulId, payload })}
            onDelete={(soulId) => mutations.deleteSoul.mutateAsync(soulId)}
          />
        </div>

        <section className="rounded-lg border border-line bg-white p-3">
          <h2 className="text-base font-semibold text-ink">最近历史</h2>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {(history.data ?? []).slice(0, 8).map((item, index) => {
              const pieces = sparkBotHistoryPieces(item);
              const timestamp = sparkBotHistoryTimestamp(item);
              const channel = sparkBotHistoryChannel(item);
              return (
                <article
                  key={`${index}-${timestamp || JSON.stringify(item).slice(0, 24)}`}
                  className="dt-interactive rounded-lg border border-line bg-white p-3 hover:border-brand-purple-300"
                  data-testid={`sparkbot-history-item-${index}`}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="neutral">{timestamp || "历史"}</Badge>
                    {channel ? <Badge tone="brand">{channel}</Badge> : null}
                  </div>
                  <div className="mt-3 grid gap-3">
                    {pieces.map((piece, pieceIndex) => (
                      <div
                        key={`${piece.role}-${pieceIndex}`}
                        className="border-t border-line pt-3 first:border-t-0 first:pt-0"
                        data-testid={`sparkbot-history-piece-${index}-${pieceIndex}`}
                      >
                        <p className="text-xs font-semibold tracking-normal text-brand-purple">{formatHistoryRole(piece.role)}</p>
                        <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-600">{piece.content}</p>
                      </div>
                    ))}
                  </div>
                </article>
              );
            })}
          </div>
          {activeBotId && !history.data?.length ? (
            <p className="mt-4 rounded-lg border border-dashed border-line bg-canvas p-4 text-sm text-slate-500">暂无历史消息。</p>
          ) : null}
        </section>
          </motion.div>
        ) : null}

        {agentsView === "advanced" ? (
          <motion.div
            key="agent-advanced"
            className="space-y-4"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
          >
        <BotProfileEditor
          bot={activeBot.data}
          pending={mutations.update.isPending}
          onSave={(payload) => {
            if (!activeBotId) return Promise.resolve();
            return mutations.update.mutateAsync({ botId: activeBotId, payload });
          }}
        />

        <BotToolsEditor
          bot={activeBot.data}
          pending={mutations.update.isPending}
          onSave={(tools) => {
            if (!activeBotId) return Promise.resolve();
            return mutations.update.mutateAsync({ botId: activeBotId, payload: { tools } });
          }}
        />

        <BotRuntimeEditor
          bot={activeBot.data}
          pending={mutations.update.isPending}
          onSave={(payload) => {
            if (!activeBotId) return Promise.resolve();
            return mutations.update.mutateAsync({ botId: activeBotId, payload });
          }}
        />
          </motion.div>
        ) : null}

        {agentsView === "workspace" ? (
          <motion.div
            key="agent-workspace"
            className="grid gap-4 lg:grid-cols-[360px_minmax(0,1fr)]"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
          >
          <section className="rounded-lg border border-line bg-white p-3" data-testid="sparkbot-channel-toggle">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-ink">渠道配置</h2>
                <p className="mt-1 text-sm text-slate-500">需要连接外部渠道时再配置。</p>
              </div>
              <Badge tone={activeBot.data?.running ? "success" : "neutral"}>{activeBot.data?.running ? "运行中" : "停止"}</Badge>
            </div>
            <div className="mt-4 grid gap-3 border-t border-line pt-4">
              <p className="text-sm text-slate-500">{activeBotId || "选择一个助教。"}</p>
              {schemas.data?.global ? (
                <GlobalChannelEditor
                  key={`${activeBotId}-global-channels`}
                  schema={schemas.data.global}
                  currentChannels={isRecord(activeBot.data?.channels) ? activeBot.data?.channels : undefined}
                  pending={mutations.update.isPending}
                  onSave={updateGlobalChannels}
                />
              ) : null}
              <FieldShell label="渠道">
                <SelectInput value={activeChannel} onChange={(event) => setSelectedChannel(event.target.value)}>
                  {channelKeys.map((key) => (
                    <option key={key} value={key}>
                      {schemas.data?.channels[key]?.display_name || key}
                    </option>
                  ))}
                </SelectInput>
              </FieldShell>
              {channelSchema ? (
                <ChannelEditor
                  key={`${activeBotId}-${activeChannel}`}
                  schema={channelSchema}
                  currentConfig={isRecord(activeBot.data?.channels?.[activeChannel]) ? activeBot.data?.channels?.[activeChannel] : undefined}
                  pending={mutations.update.isPending}
                  onSave={updateChannel}
                />
              ) : (
                <p className="rounded-lg bg-canvas p-4 text-sm text-slate-500">暂无可用渠道字段。</p>
              )}
            </div>
          </section>

          <section className="rounded-lg border border-line bg-white p-3" data-testid="sparkbot-files-toggle">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-ink">工作区文件</h2>
                <p className="mt-1 text-sm text-slate-500">编辑提示词、笔记和助教工作文件。</p>
              </div>
              <Badge tone="neutral">{fileItems.length}</Badge>
            </div>
            <form className="mt-4 grid gap-2 border-t border-line pt-4 sm:grid-cols-[minmax(0,1fr)_auto]" onSubmit={createWorkspaceFile}>
              <TextInput
                value={newFileName}
                onChange={(event) => setNewFileName(event.target.value)}
                placeholder="NOTES.md"
                data-testid="sparkbot-new-file-name"
              />
              <Button
                tone="secondary"
                type="submit"
                disabled={!activeBotId || !newFileName.trim() || mutations.writeFile.isPending}
                data-testid="sparkbot-new-file-create"
              >
                {mutations.writeFile.isPending ? <Loader2 size={16} className="animate-spin" /> : <FileText size={16} />}
                创建/打开
              </Button>
            </form>
            <div className="mt-4 grid gap-3 lg:grid-cols-[240px_minmax(0,1fr)]">
              <div className="max-h-96 space-y-2 overflow-y-auto pr-1">
                {fileItems.map((file) => (
                  <button
                    key={file.filename}
                    type="button"
                    data-testid={`sparkbot-file-${file.filename}`}
                    onClick={() => setSelectedFile(file.filename)}
                    className={`w-full rounded-lg border px-3 py-2 text-left text-sm transition ${
                      activeFileName === file.filename ? "border-brand-purple-300 bg-tint-lavender text-brand-purple" : "border-line bg-white text-slate-600 hover:border-brand-purple-300"
                    }`}
                  >
                    <FileText size={15} className="mr-2 inline" />
                    {file.filename}
                  </button>
                ))}
                {!fileItems.length ? <p className="rounded-lg bg-canvas p-3 text-sm text-slate-500">暂无可编辑文件。</p> : null}
              </div>
              {activeBotId && activeFileName ? (
                <FileEditor
                  key={`${activeBotId}-${activeFileName}-${activeFile.data?.content?.length ?? 0}`}
                  botId={activeBotId}
                  filename={activeFileName}
                  file={activeFile.data}
                  fallbackContent={fileItems.find((item) => item.filename === activeFileName)?.content}
                  pending={mutations.writeFile.isPending || activeFile.isLoading}
                  onSave={(content) => mutations.writeFile.mutateAsync({ botId: activeBotId, filename: activeFileName, content })}
                />
              ) : (
                <div className="rounded-lg border border-dashed border-line bg-canvas p-6 text-sm text-slate-500">
                  选择文件后可以直接编辑并保存。
                </div>
              )}
            </div>
          </section>
        </motion.div>
        ) : null}
      </div>
    </div>
  );
}

const AGENT_ICON_MAP: Record<string, LucideIcon> = {
  BookOpen,
  FileText,
  HelpCircle,
  PenTool,
  Search,
};

const AGENT_TARGETS: Record<string, { href: string; title: string; description: string }> = {
  solve: {
    href: "/chat?capability=deep_solve",
    title: "深度解题",
    description: "复杂题目拆解、推理和校验",
  },
  question: {
    href: "/question",
    title: "题目工坊",
    description: "知识点出题和试卷仿题",
  },
  research: {
    href: "/chat?capability=deep_research",
    title: "深度研究",
    description: "资料检索、引用和报告生成",
  },
  co_writer: {
    href: "/co-writer",
    title: "协作写作",
    description: "润色、扩写、缩写和结构编辑",
  },
  guide: {
    href: "/guide",
    title: "导学空间",
    description: "生成学习路径和交互式页面",
  },
};

function AgentWorkspaceTabs({
  value,
  bots,
  capabilities,
  files,
  onChange,
}: {
  value: AgentWorkspaceView;
  bots: number;
  capabilities: number;
  files: number;
  onChange: (value: AgentWorkspaceView) => void;
}) {
  const tabs: Array<{ id: AgentWorkspaceView; title: string; detail: string; count: number; tint: string }> = [
    { id: "assistants", title: "助教", detail: "聊天与常驻助教", count: bots, tint: "bg-tint-lavender" },
    { id: "capabilities", title: "能力", detail: "多智能体入口", count: capabilities, tint: "bg-tint-yellow" },
    { id: "workspace", title: "工作区", detail: "渠道和文件", count: files, tint: "bg-tint-sky" },
    { id: "advanced", title: "调优", detail: "人格、工具、运行", count: 3, tint: "bg-tint-mint" },
  ];
  return (
    <section className="rounded-lg border border-line bg-white p-2">
      <div className="grid gap-2 md:grid-cols-4">
        {tabs.map((tab) => {
          const active = value === tab.id;
          return (
            <motion.button
              key={tab.id}
              type="button"
              className={`dt-interactive rounded-lg border p-3 text-left transition ${
                active ? "border-ink bg-ink text-white" : `border-transparent ${tab.tint} text-ink hover:border-brand-purple-300`
              }`}
              onClick={() => onChange(tab.id)}
              whileHover={{ y: -2 }}
              whileTap={{ scale: 0.99 }}
              data-testid={`agent-workspace-tab-${tab.id}`}
            >
              <span className="flex items-center justify-between gap-3">
                <span className="text-sm font-semibold">{tab.title}</span>
                <span className={`rounded-md px-2 py-0.5 text-xs ${active ? "bg-white/15 text-white" : "bg-white text-slate-600"}`}>
                  {tab.count}
                </span>
              </span>
              <span className={`mt-2 block text-xs leading-5 ${active ? "text-white/75" : "text-slate-600"}`}>{tab.detail}</span>
            </motion.button>
          );
        })}
      </div>
    </section>
  );
}

function AgentStatusStrip({
  bots,
  running,
  recent,
  capabilities,
}: {
  bots: number;
  running: number;
  recent: number;
  capabilities: number;
}) {
  const items = [
    { label: "助教", value: String(bots), ok: bots > 0 },
    { label: "运行中", value: String(running), ok: running > 0 },
    { label: "最近", value: String(recent), ok: recent > 0 },
    { label: "能力", value: String(capabilities), ok: capabilities > 0 },
  ];
  return (
    <section className="px-1">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
        {items.map((item) => (
          <div key={item.label} className="flex min-w-0 items-center gap-1.5 text-xs">
            <span className={`h-1.5 w-1.5 shrink-0 ${item.ok ? "bg-emerald-500" : "bg-slate-300"}`} style={{ borderRadius: "50%" }} />
            <span className="shrink-0 text-slate-500">{item.label}</span>
            <span className="truncate font-medium text-ink">{item.value}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function SparkBotRecentPanel({
  items,
  activeBotId,
  loading,
  onRefresh,
  onSelect,
}: {
  items: SparkBotRecentItem[];
  activeBotId: string | null;
  loading: boolean;
  onRefresh: () => void;
  onSelect: (botId: string) => void;
}) {
  return (
    <section className="rounded-lg border border-line bg-white p-3 shadow-[0_1px_2px_rgba(15,15,15,0.025)]" data-testid="sparkbot-recent-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Clock3 size={18} className="text-brand-blue" />
            <h2 className="text-base font-semibold text-ink">最近联系</h2>
          </div>
          <p className="mt-1 text-sm leading-6 text-slate-500">像 Notion 最近页面一样，直接回到上次的助教上下文。</p>
        </div>
        <Button tone="secondary" onClick={onRefresh} disabled={loading} data-testid="sparkbot-recent-refresh">
          {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
          刷新
        </Button>
      </div>
      <div className="mt-4 grid gap-2 md:grid-cols-3">
        {items.map((item) => {
          const active = activeBotId === item.bot_id;
          const displayTime = formatSparkBotTime(item.updated_at);
          return (
            <motion.button
              key={item.bot_id}
              type="button"
              onClick={() => onSelect(item.bot_id)}
              aria-pressed={active}
              className={`dt-interactive min-h-28 rounded-lg border p-3 text-left transition ${
                active ? "border-brand-purple-300 bg-tint-lavender" : "border-line bg-white hover:border-brand-purple-300 hover:bg-canvas"
              }`}
              data-testid={`sparkbot-recent-${item.bot_id}`}
              whileHover={{ y: -2 }}
              whileTap={{ scale: 0.99 }}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="truncate text-sm font-semibold text-ink">{item.name || item.bot_id}</h3>
                  <p className="mt-1 truncate text-xs text-slate-500">{item.bot_id}</p>
                </div>
                <Badge tone={item.running ? "success" : "neutral"}>{item.running ? "运行中" : "停止"}</Badge>
              </div>
              <p className="mt-3 line-clamp-2 text-sm leading-6 text-slate-600">{item.last_message || "还没有留下对话摘要。"}</p>
              <p className="mt-3 text-xs text-slate-500">{displayTime}</p>
            </motion.button>
          );
        })}
      </div>
      {!items.length && !loading ? (
        <p className="mt-4 rounded-lg border border-dashed border-line bg-canvas p-4 text-sm text-slate-500">
          暂无活跃历史。助教产生会话后会自动出现在这里。
        </p>
      ) : null}
    </section>
  );
}

function formatSparkBotTime(value?: string | number | null) {
  const timestamp = normalizeSparkBotTimestamp(value);
  if (!timestamp) return "最近";
  const date = new Date(timestamp);
  const now = Date.now();
  const diff = now - timestamp;
  if (diff >= 0 && diff < 60_000) return "刚刚";
  if (diff >= 0 && diff < 60 * 60_000) return `${Math.max(1, Math.floor(diff / 60_000))} 分钟前`;
  const today = new Date();
  const sameDay =
    date.getFullYear() === today.getFullYear() && date.getMonth() === today.getMonth() && date.getDate() === today.getDate();
  if (sameDay) return `今天 ${date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false })}`;
  return date.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
}

function normalizeSparkBotTimestamp(value?: string | number | null) {
  if (value === null || value === undefined || value === "") return 0;
  const numericValue = typeof value === "number" ? value : Number(value);
  const timestamp = Number.isFinite(numericValue)
    ? numericValue < 1_000_000_000_000
      ? numericValue * 1000
      : numericValue
    : new Date(value).getTime();
  if (!Number.isFinite(timestamp) || timestamp <= 0) return 0;
  const date = new Date(timestamp);
  if (date.getFullYear() < 2023) return 0;
  return timestamp;
}

function AgentConfigCard({
  agentType,
  config,
  active,
  onInspect,
}: {
  agentType: string;
  config: AgentUiConfig;
  active: boolean;
  onInspect: () => void;
}) {
  const Icon = AGENT_ICON_MAP[config.icon || ""] ?? HelpCircle;
  const target = AGENT_TARGETS[agentType] ?? {
    href: "/chat",
    title: agentType,
    description: "可用的助教能力入口",
  };
  return (
    <motion.article
      className={`dt-interactive rounded-lg border p-4 transition ${active ? "border-brand-purple-300 bg-tint-lavender" : "border-line bg-white hover:border-brand-purple-300"}`}
      whileHover={{ y: -2 }}
      transition={{ duration: 0.18 }}
    >
      <div className="flex items-start justify-between gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-line bg-white text-brand-purple">
          <Icon size={18} />
        </span>
        <Badge tone="neutral">{config.color || "默认"}</Badge>
      </div>
      <h3 className="mt-4 text-sm font-semibold text-ink">{target.title}</h3>
      <p className="mt-2 min-h-10 text-xs leading-5 text-slate-500">{target.description}</p>
      <div className="mt-4 grid gap-2 border-t border-line pt-3">
        <div className="flex items-center justify-between gap-3 text-xs">
          <span className="shrink-0 text-slate-500">入口</span>
          <span className="min-w-0 truncate font-semibold text-ink">{target.title}</span>
        </div>
        <div className="flex items-center justify-between gap-3 text-xs">
          <span className="shrink-0 text-slate-500">说明</span>
          <span className="min-w-0 truncate text-slate-600">{target.description}</span>
        </div>
      </div>
      <div className="mt-4 grid gap-2">
        <Button tone={active ? "primary" : "secondary"} onClick={onInspect} data-testid={`agent-config-inspect-${agentType}`}>
          查看详情
        </Button>
        <a
          href={target.href}
          className="inline-flex min-h-9 w-full items-center justify-center rounded-lg border border-line bg-white px-3 text-sm font-medium text-slate-700 transition hover:border-brand-purple-300 hover:text-brand-purple"
        >
          打开入口
        </a>
      </div>
    </motion.article>
  );
}

function AgentConfigDetail({
  agentType,
  config,
  loading,
  error,
}: {
  agentType: string | null;
  config?: AgentUiConfig;
  loading: boolean;
  error: Error | null;
}) {
  if (!agentType) return null;
  const displayTitle = AGENT_TARGETS[agentType]?.title ?? agentType;
  const displayDescription = AGENT_TARGETS[agentType]?.description ?? "可用的学习能力入口";
  const resultLabel = typeof config?.label_key === "string" ? config.label_key : "学习结果";
  const iconLabel = typeof config?.icon === "string" ? config.icon : "默认";
  return (
    <div className="mt-4 border-t border-line pt-4" data-testid="agent-config-detail">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase text-slate-500">能力详情</p>
          <h3 className="mt-1 text-base font-semibold text-ink">{displayTitle}</h3>
          <p className="mt-1 text-sm leading-6 text-slate-500">{displayDescription}</p>
        </div>
        <Badge tone={error ? "danger" : loading ? "brand" : "success"}>{error ? "异常" : loading ? "同步中" : "可用"}</Badge>
      </div>
      {error ? <p className="mt-4 rounded-md border border-red-100 bg-red-50 p-3 text-sm text-red-700">{error.message}</p> : null}
      <div className="mt-4 grid gap-2 md:grid-cols-3">
        <div className="rounded-lg bg-canvas px-3 py-2">
          <p className="text-xs text-slate-500">输出类型</p>
          <p className="mt-1 truncate text-sm font-semibold text-ink">{resultLabel}</p>
        </div>
        <div className="rounded-lg bg-canvas px-3 py-2">
          <p className="text-xs text-slate-500">入口</p>
          <p className="mt-1 truncate text-sm font-semibold text-ink">{displayTitle}</p>
        </div>
        <div className="rounded-lg bg-canvas px-3 py-2">
          <p className="text-xs text-slate-500">图标</p>
          <p className="mt-1 truncate text-sm font-semibold text-ink">{iconLabel}</p>
        </div>
      </div>
    </div>
  );
}

type BotChatMessage = {
  id: string;
  role: "user" | "bot" | "system";
  content: string;
  thinking?: string;
  status?: "streaming" | "done" | "error";
};

type SparkBotWsEvent = {
  type?: string;
  content?: string;
  delta?: boolean;
  append?: boolean;
};

function SparkBotChat({ botId, running }: { botId: string | null; running: boolean }) {
  const [messages, setMessages] = useState<BotChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [status, setStatus] = useState<"idle" | "connecting" | "streaming" | "error">("idle");
  const wsRef = useRef<WebSocket | null>(null);
  const activeReplyIdRef = useRef<string | null>(null);

  useEffect(
    () => () => {
      wsRef.current?.close();
    },
    [],
  );

  const send = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!botId || !running || !input.trim() || status === "connecting" || status === "streaming") return;
    wsRef.current?.close();
    const content = input.trim();
    const replyId = `bot-${Date.now()}`;
    activeReplyIdRef.current = replyId;
    setMessages((current) => [
      ...current,
      { id: `user-${Date.now()}`, role: "user", content, status: "done" },
      { id: replyId, role: "bot", content: "", status: "streaming" },
    ]);
    setInput("");
    setStatus("connecting");

    const socket = new WebSocket(sparkBotSocketUrl(botId));
    wsRef.current = socket;
    const updateReply = (updater: (message: BotChatMessage) => BotChatMessage) => {
      setMessages((current) => current.map((item) => (item.id === replyId ? updater(item) : item)));
    };
    socket.onopen = () => {
      setStatus("streaming");
      socket.send(JSON.stringify({ content, chat_id: "web" }));
    };
    socket.onmessage = (message) => {
      try {
        const eventData = JSON.parse(message.data) as SparkBotWsEvent;
        if (eventData.type === "thinking") {
          updateReply((item) => ({ ...item, thinking: eventData.content || "正在思考", status: "streaming" }));
          return;
        }
        if (eventData.type === "content_delta" || eventData.type === "delta" || (eventData.type === "content" && (eventData.delta || eventData.append))) {
          updateReply((item) => ({
            ...item,
            content: `${item.content}${eventData.content || ""}`,
            status: "streaming",
          }));
          return;
        }
        if (eventData.type === "content") {
          updateReply((item) => ({ ...item, content: eventData.content || "", status: "streaming" }));
          return;
        }
        if (eventData.type === "proactive") {
          setMessages((current) => [
            ...current,
            { id: `proactive-${Date.now()}`, role: "bot", content: eventData.content || "主动提醒", status: "done" },
          ]);
          return;
        }
        if (eventData.type === "done") {
          updateReply((item) => ({ ...item, status: "done" }));
          activeReplyIdRef.current = null;
          setStatus("idle");
          socket.close();
          return;
        }
        if (eventData.type === "error") {
          setStatus("error");
          activeReplyIdRef.current = null;
          updateReply((item) => ({ ...item, content: eventData.content || "助教回复异常", status: "error" }));
        }
      } catch {
        setStatus("error");
        activeReplyIdRef.current = null;
      }
    };
    socket.onerror = () => {
      setStatus("error");
      activeReplyIdRef.current = null;
      updateReply((item) => ({ ...item, content: "无法连接助教实时通道", status: "error" }));
    };
    socket.onclose = () => {
      wsRef.current = null;
      setStatus((current) => (current === "connecting" || current === "streaming" ? "idle" : current));
    };
  };

  return (
    <section className="rounded-lg border border-line bg-white p-3" data-testid="sparkbot-chat">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <MessageSquareText size={18} className="text-brand-purple" />
            <h2 className="text-base font-semibold text-ink" aria-label="Bot 对话">助教对话</h2>
          </div>
          <p className="mt-1 text-sm text-slate-500">{botId ? `${botId} · ${running ? "运行中" : "未运行"}` : "选择一个运行中的助教。"}</p>
        </div>
        <Badge tone={status === "error" ? "danger" : status === "idle" ? "neutral" : "brand"}>{formatBotChatStatus(status)}</Badge>
      </div>
      <div className="mt-4 max-h-80 space-y-3 overflow-y-auto rounded-lg border border-line bg-white p-3">
        <AnimatePresence initial={false}>
          {messages.map((message) => (
            <motion.article
              key={message.id}
              className={`rounded-lg border p-3 text-sm leading-6 ${
                message.role === "user" ? "ml-auto max-w-[82%] border-brand-purple-300 bg-tint-lavender" : "mr-auto max-w-[82%] border-line bg-white"
              }`}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.18, ease: "easeOut" }}
            >
              <Badge tone={message.status === "error" ? "danger" : message.role === "user" ? "brand" : "neutral"}>
                {message.role === "user" ? "你" : "助教"}
              </Badge>
              {message.thinking && message.status !== "done" ? (
                <p className="mt-2 rounded-md border border-line bg-canvas px-2 py-1 text-xs leading-5 text-slate-500">
                  助教正在整理思路
                </p>
              ) : null}
              <p className="mt-2 whitespace-pre-wrap text-slate-700">{message.content || "等待回复..."}</p>
            </motion.article>
          ))}
        </AnimatePresence>
        {!messages.length ? <p className="text-sm text-slate-500">启动助教后，可以在这里直接对话。</p> : null}
      </div>
      <form className="mt-4 flex gap-2" onSubmit={send}>
        <TextInput value={input} onChange={(event) => setInput(event.target.value)} placeholder="向 SparkBot 提问..." />
        <Button tone="primary" type="submit" disabled={!botId || !running || !input.trim() || status === "connecting" || status === "streaming"}>
          {status === "connecting" || status === "streaming" ? <Loader2 size={16} className="animate-spin" /> : <SendHorizontal size={16} />}
          发送
        </Button>
      </form>
    </section>
  );
}

function formatBotChatStatus(status: "idle" | "connecting" | "streaming" | "error") {
  return {
    idle: "就绪",
    connecting: "连接中",
    streaming: "回复中",
    error: "异常",
  }[status];
}

function SoulLibrary({
  souls,
  pending,
  onUse,
  onCreate,
  onUpdate,
  onDelete,
}: {
  souls: SparkBotSoul[];
  pending: boolean;
  onUse: (soul: SparkBotSoul) => void;
  onCreate: (soul: SparkBotSoul) => Promise<unknown>;
  onUpdate: (soulId: string, payload: Partial<Pick<SparkBotSoul, "name" | "content">>) => Promise<unknown>;
  onDelete: (soulId: string) => Promise<unknown>;
}) {
  const [selectedSoulId, setSelectedSoulId] = useState("");
  const soulDetail = useSparkBotSoulDetail(selectedSoulId || null);
  const activeSoul = soulDetail.data ?? souls.find((soul) => soul.id === selectedSoulId);
  const [draftId, setDraftId] = useState("");
  const [draftName, setDraftName] = useState("");
  const [draftContent, setDraftContent] = useState("");
  const [draftEdited, setDraftEdited] = useState(false);

  const draftValues =
    !draftEdited && activeSoul
      ? { id: activeSoul.id, name: activeSoul.name, content: activeSoul.content }
      : { id: draftId, name: draftName, content: draftContent };

  const updateDraft = (patch: Partial<SparkBotSoul>) => {
    setDraftId(patch.id ?? draftValues.id);
    setDraftName(patch.name ?? draftValues.name);
    setDraftContent(patch.content ?? draftValues.content);
    setDraftEdited(true);
  };

  const loadSoul = (soul: SparkBotSoul) => {
    setSelectedSoulId(soul.id);
    setDraftId(soul.id);
    setDraftName(soul.name);
    setDraftContent(soul.content);
    setDraftEdited(false);
  };

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextId = draftValues.id.trim();
    const nextName = draftValues.name.trim();
    if (!nextId || !nextName || !draftValues.content.trim()) return;
    if (activeSoul && activeSoul.id === nextId) {
      await onUpdate(activeSoul.id, { name: nextName, content: draftValues.content });
    } else {
      await onCreate({ id: nextId, name: nextName, content: draftValues.content });
      setSelectedSoulId(nextId);
    }
    setDraftEdited(false);
  };

  return (
    <section className="rounded-lg border border-line bg-white p-3">
      <div
        className="flex flex-wrap items-start justify-between gap-3 rounded-lg bg-tint-yellow px-3 py-3"
        data-testid="sparkbot-soul-toggle"
      >
          <div>
            <div className="flex items-center gap-2">
              <Wand2 size={18} className="text-brand-blue" />
              <h2 className="text-base font-semibold text-ink" aria-label="Soul 模板库">助教模板库</h2>
            </div>
            <p className="mt-1 text-sm text-slate-500">按需管理助教人格和提示模板。</p>
          </div>
          <Badge tone="neutral">{souls.length}</Badge>
        </div>
        <div className="mt-4 border-t border-line pt-4">
          <p className="text-xs text-slate-500" data-testid="sparkbot-soul-detail-source">
            {activeSoul
              ? soulDetail.isFetching
                ? "正在读取模板..."
                : (
                    <>
                      已选择：{activeSoul.name}
                    </>
                  )
              : "选择一个模板后可查看内容。"}
          </p>
          <div className="mt-3">
            <Button
              tone="quiet"
              type="button"
              className="min-h-8 px-2 text-xs"
              data-testid="sparkbot-soul-new"
              onClick={() => {
                setSelectedSoulId("");
                setDraftId("");
                setDraftName("");
                setDraftContent("");
                setDraftEdited(true);
              }}
            >
              新建模板
            </Button>
          </div>
          <div className="mt-4 flex max-h-40 flex-wrap gap-2 overflow-y-auto">
            {souls.map((soul) => (
              <button
                key={soul.id}
                type="button"
                data-testid={`sparkbot-soul-${soul.id}`}
                onClick={() => loadSoul(soul)}
                className={`rounded-lg border px-3 py-2 text-left text-sm ${
                  selectedSoulId === soul.id ? "border-brand-purple-300 bg-tint-lavender text-brand-purple" : "border-line bg-white text-slate-600 hover:border-brand-purple-300"
                }`}
              >
                {soul.name}
              </button>
            ))}
          </div>
        </div>
      <form className="mt-4 grid gap-3 border-t border-line pt-4" onSubmit={submit}>
        <FieldShell label="模板标识">
          <TextInput
            value={draftValues.id}
            onChange={(event) => updateDraft({ id: event.target.value })}
            placeholder="physics-tutor"
            data-testid="sparkbot-soul-id"
          />
        </FieldShell>
        <FieldShell label="名称">
          <TextInput
            value={draftValues.name}
            onChange={(event) => updateDraft({ name: event.target.value })}
            placeholder="物理助教"
            data-testid="sparkbot-soul-name"
          />
        </FieldShell>
        <FieldShell label="内容">
          <TextArea
            value={draftValues.content}
            onChange={(event) => updateDraft({ content: event.target.value })}
            className="min-h-40"
            data-testid="sparkbot-soul-content"
          />
        </FieldShell>
        <div className="grid grid-cols-2 gap-2">
          <Button tone="secondary" type="button" onClick={() => activeSoul && onUse(activeSoul)} disabled={!activeSoul} data-testid="sparkbot-soul-use">
            套用
          </Button>
          <Button
            tone="primary"
            type="submit"
            disabled={pending || !draftValues.id.trim() || !draftValues.name.trim() || !draftValues.content.trim()}
            data-testid="sparkbot-soul-save"
          >
            {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            保存模板
          </Button>
        </div>
        <Button
          tone="danger"
          type="button"
          data-testid="sparkbot-soul-delete"
          disabled={pending || !activeSoul}
          onClick={() => {
            if (activeSoul && window.confirm(`删除模板 ${activeSoul.name}？`)) void onDelete(activeSoul.id);
          }}
        >
          <Trash2 size={16} />
          删除模板
        </Button>
      </form>
    </section>
  );
}

function BotProfileEditor({
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
          <p className="mt-1 text-sm leading-6 text-slate-500">
            名称、模型和角色设定，按需编辑。
          </p>
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

function BotToolsEditor({
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
          <p className="mt-1 text-sm leading-6 text-slate-500">
            执行、检索和扩展工具，演示前再调。
          </p>
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

function BotRuntimeEditor({
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
          <p className="mt-1 text-sm leading-6 text-slate-500">
            响应节奏、工具上限和在线提醒。
          </p>
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
        <TextArea
          value={agentValue}
          onChange={(event) => setAgentValue(event.target.value)}
          className="min-h-72 font-mono text-xs"
          data-testid="bot-agent-json"
        />
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
        {saved ? (
          <span className="text-sm text-emerald-700">
            运行设置已保存。
          </span>
        ) : null}
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

function BotCard({
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
    <motion.div
      className={`dt-interactive rounded-lg border p-4 ${active ? "border-brand-purple-300 bg-tint-lavender" : "border-line bg-white hover:border-brand-purple-300"}`}
      data-testid={`sparkbot-card-${bot.bot_id}`}
      whileHover={{ y: -2 }}
      transition={{ duration: 0.18 }}
    >
      <button type="button" className="w-full text-left" onClick={onSelect}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate font-semibold text-ink">{bot.name || bot.bot_id}</p>
            <p className="mt-1 line-clamp-2 text-sm leading-6 text-slate-500">{bot.description || bot.model || "常驻学习助手"}</p>
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
    </motion.div>
  );
}

function GlobalChannelEditor({
  schema,
  currentChannels,
  pending,
  onSave,
}: {
  schema: Partial<SparkBotChannelSchema>;
  currentChannels?: Record<string, unknown>;
  pending: boolean;
  onSave: (config: Record<string, unknown>) => Promise<void>;
}) {
  const globalSchema: SparkBotChannelSchema = {
    name: "global",
    display_name: "全局渠道行为",
    default_config: defaultsFromSchema(schema.json_schema),
    secret_fields: schema.secret_fields ?? [],
    json_schema: schema.json_schema ?? { type: "object", properties: {} },
  };
  const currentConfig = pickSchemaConfig(currentChannels, globalSchema);
  return (
    <div className="border-t border-line pt-3" data-testid="sparkbot-global-channel-editor">
      <ChannelEditor schema={globalSchema} currentConfig={currentConfig} pending={pending} onSave={onSave} submitLabel="保存全局" />
    </div>
  );
}

function ChannelEditor({
  schema,
  currentConfig,
  pending,
  onSave,
  submitLabel = "保存渠道",
}: {
  schema: SparkBotChannelSchema;
  currentConfig?: Record<string, unknown>;
  pending: boolean;
  onSave: (config: Record<string, unknown>) => Promise<void>;
  submitLabel?: string;
}) {
  const initialConfig = useMemo(() => ({ ...(schema.default_config ?? {}), ...(currentConfig ?? {}) }), [currentConfig, schema.default_config]);
  const schemaProperties = useMemo(() => getSchemaProperties(schema), [schema]);
  const [formValues, setFormValues] = useState<Record<string, unknown>>(initialConfig);
  const [advancedMode, setAdvancedMode] = useState(false);
  const [value, setValue] = useState(JSON.stringify(initialConfig, null, 2));
  const [error, setError] = useState("");
  const updateValue = (key: string, nextValue: unknown) => {
    setFormValues((current) => ({ ...current, [key]: nextValue }));
  };
  const parsedConfig = () => {
    if (advancedMode || !schemaProperties.length) return JSON.parse(value) as Record<string, unknown>;
    const next = { ...initialConfig };
    for (const property of schemaProperties) {
      next[property.key] = normalizeChannelValue(formValues[property.key], property);
    }
    return next;
  };

  return (
    <form
      className="grid gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        try {
          const parsed = parsedConfig();
          setError("");
          void onSave(parsed);
        } catch (parseError) {
          setError(parseError instanceof Error ? parseError.message : "JSON 解析失败");
        }
      }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-ink">{schema.display_name || schema.name}</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            {schemaProperties.length ? "根据渠道字段生成表单。" : "这个渠道没有公开字段，使用高级配置。"}
          </p>
        </div>
        <Button
          tone="quiet"
          className="min-h-8 px-2 text-xs"
          type="button"
          onClick={() => {
            if (!advancedMode) setValue(JSON.stringify({ ...initialConfig, ...formValues }, null, 2));
            setAdvancedMode((current) => !current);
          }}
        >
          {advancedMode ? "表单模式" : "高级模式"}
        </Button>
      </div>
      {!advancedMode && schemaProperties.length ? (
        <div className="grid gap-3 border-t border-line pt-3">
          {schemaProperties.map((property) => (
            <ChannelSchemaField
              key={property.key}
              property={property}
              secret={schema.secret_fields?.includes(property.key)}
              value={formValues[property.key]}
              onChange={(nextValue) => updateValue(property.key, nextValue)}
            />
          ))}
        </div>
      ) : (
        <FieldShell label={schema.display_name || schema.name} hint={schema.secret_fields?.length ? `敏感字段：${schema.secret_fields.join(", ")}` : undefined}>
          <TextArea value={value} onChange={(event) => setValue(event.target.value)} className="min-h-64 font-mono text-xs" />
        </FieldShell>
      )}
      {error ? <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-brand-red">{error}</p> : null}
      <Button tone="secondary" type="submit" disabled={pending}>
        {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
        {submitLabel}
      </Button>
    </form>
  );
}

type ChannelSchemaProperty = {
  key: string;
  label: string;
  description?: string;
  type?: string;
  enum?: string[];
  default?: unknown;
};

function ChannelSchemaField({
  property,
  secret,
  value,
  onChange,
}: {
  property: ChannelSchemaProperty;
  secret?: boolean;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  const label = property.label || property.key;
  const valueString = value == null ? "" : typeof value === "object" ? JSON.stringify(value, null, 2) : String(value);
  if (property.type === "boolean") {
    return (
      <label className="flex items-start gap-3 rounded-lg border border-line bg-white p-3">
        <input
          type="checkbox"
          checked={Boolean(value)}
          onChange={(event) => onChange(event.target.checked)}
          className="mt-1 size-4 rounded border-line text-brand-purple focus:ring-brand-purple"
          data-testid={`channel-field-${property.key}`}
        />
        <span>
          <span className="block text-sm font-medium text-ink">{label}</span>
          {property.description ? <span className="mt-1 block text-xs leading-5 text-slate-500">{property.description}</span> : null}
        </span>
      </label>
    );
  }
  if (property.enum?.length) {
    return (
      <FieldShell label={label} hint={property.description}>
        <SelectInput value={valueString} onChange={(event) => onChange(event.target.value)} data-testid={`channel-field-${property.key}`}>
          {property.enum.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </SelectInput>
      </FieldShell>
    );
  }
  if (property.type === "object" || property.type === "array") {
    return (
      <FieldShell label={label} hint={property.description}>
        <TextArea
          value={valueString}
          onChange={(event) => onChange(event.target.value)}
          className="min-h-24 font-mono text-xs"
          data-testid={`channel-field-${property.key}`}
        />
      </FieldShell>
    );
  }
  return (
    <FieldShell label={label} hint={secret ? `${property.description || ""} secret`.trim() : property.description}>
      <TextInput
        type={secret ? "password" : property.type === "number" || property.type === "integer" ? "number" : "text"}
        value={valueString}
        onChange={(event) => onChange(event.target.value)}
        data-testid={`channel-field-${property.key}`}
      />
    </FieldShell>
  );
}

function FileEditor({
  filename,
  file,
  fallbackContent,
  pending,
  onSave,
}: {
  botId: string;
  filename: string;
  file?: SparkBotFile;
  fallbackContent?: string;
  pending: boolean;
  onSave: (content: string) => Promise<unknown>;
}) {
  const [content, setContent] = useState(file?.content ?? fallbackContent ?? "");
  return (
    <form
      className="grid gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        void onSave(content);
      }}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Badge tone="brand">{filename}</Badge>
        <Button tone="primary" type="submit" disabled={pending} data-testid="sparkbot-file-save">
          {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
          保存文件
        </Button>
      </div>
      <TextArea
        value={content}
        onChange={(event) => setContent(event.target.value)}
        className="min-h-96 font-mono text-xs"
        data-testid="sparkbot-file-content"
      />
    </form>
  );
}

type SparkBotHistoryPiece = {
  role: string;
  content: string;
};

function sparkBotHistoryPieces(item: Record<string, unknown>): SparkBotHistoryPiece[] {
  const user = unknownText(item.user);
  const assistant = unknownText(item.assistant);
  const paired = [
    user ? { role: "user", content: user } : null,
    assistant ? { role: "assistant", content: assistant } : null,
  ].filter(Boolean) as SparkBotHistoryPiece[];
  if (paired.length) return paired;

  return [
    {
      role: unknownText(item.role) || unknownText(item.type) || "message",
      content: unknownText(item.content) || unknownText(item.message) || unknownText(item.text) || safeJson(item),
    },
  ];
}

function sparkBotHistoryTimestamp(item: Record<string, unknown>) {
  return unknownText(item.timestamp) || unknownText(item.created_at) || unknownText(item.updated_at);
}

function sparkBotHistoryChannel(item: Record<string, unknown>) {
  const channel = unknownText(item.channel);
  const chatId = unknownText(item.chat_id);
  if (channel && chatId && channel !== chatId) return `${channel} / ${chatId}`;
  return channel || chatId;
}

function formatHistoryRole(role: string) {
  return (
    {
      user: "你",
      human: "你",
      assistant: "助教",
      bot: "助教",
      system: "系统",
    }[role] || role
  );
}

function unknownText(value: unknown) {
  if (typeof value === "string") return value.trim();
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return "";
}

function safeJson(value: unknown) {
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function getSchemaProperties(schema: SparkBotChannelSchema): ChannelSchemaProperty[] {
  const jsonSchema = isRecord(schema.json_schema) ? schema.json_schema : {};
  const properties = isRecord(jsonSchema.properties) ? jsonSchema.properties : {};
  return Object.entries(properties).map(([key, raw]) => {
    const property = isRecord(raw) ? raw : {};
    const enumValues = Array.isArray(property.enum) ? property.enum.map(String) : undefined;
    return {
      key,
      label: String(property.title || key),
      description: typeof property.description === "string" ? property.description : undefined,
      type: typeof property.type === "string" ? property.type : undefined,
      enum: enumValues,
      default: property.default,
    };
  });
}

function defaultsFromSchema(schema: unknown) {
  const jsonSchema = isRecord(schema) ? schema : {};
  const properties = isRecord(jsonSchema.properties) ? jsonSchema.properties : {};
  return Object.fromEntries(
    Object.entries(properties).map(([key, raw]) => {
      const property = isRecord(raw) ? raw : {};
      return [key, property.default ?? defaultValueForSchemaType(property.type)];
    }),
  );
}

function defaultValueForSchemaType(type: unknown) {
  if (type === "boolean") return false;
  if (type === "integer" || type === "number") return 0;
  if (type === "array") return [];
  if (type === "object") return {};
  return "";
}

function pickSchemaConfig(source: Record<string, unknown> | undefined, schema: SparkBotChannelSchema) {
  if (!source) return undefined;
  const keys = new Set(getSchemaProperties(schema).map((property) => property.key));
  return Object.fromEntries(Object.entries(source).filter(([key]) => keys.has(key)));
}

function normalizeChannelValue(value: unknown, property: ChannelSchemaProperty) {
  if (property.type === "boolean") return Boolean(value);
  if (property.type === "number") {
    if (value === "" || value == null) return undefined;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : value;
  }
  if (property.type === "integer") {
    if (value === "" || value == null) return undefined;
    const parsed = Number.parseInt(String(value), 10);
    return Number.isFinite(parsed) ? parsed : value;
  }
  if (property.type === "object" || property.type === "array") {
    if (typeof value !== "string") return value;
    const trimmed = value.trim();
    if (!trimmed) return property.type === "array" ? [] : {};
    return JSON.parse(trimmed) as unknown;
  }
  return value ?? "";
}
