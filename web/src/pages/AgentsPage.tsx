import { Bot, HelpCircle, Loader2, RefreshCw, Wand2 } from "lucide-react";
import { useLocation, useParams } from "@tanstack/react-router";
import { lazy, Suspense, useMemo, useState } from "react";
import { motion } from "framer-motion";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { NotionProductHero } from "@/components/ui/NotionProductHero";
import {
  useAgentConfigDetail,
  useAgentConfigs,
  useLearnerProfile,
  useLearningEffectMutations,
  useLearningEffectNextActions,
  useLearningEffectReport,
  useSparkBotChannelSchemas,
  useSparkBotDetail,
  useSparkBotFile,
  useSparkBotFiles,
  useSparkBotHistory,
  useSparkBotMutations,
  useSparkBotRecent,
  useSparkBotSouls,
  useSparkBots,
} from "@/hooks/useApiQueries";
import {
  AgentStatusStrip,
  AgentWorkspaceTabs,
  SparkBotRecentPanel,
} from "./agents/AgentWorkspaceChrome";
import type { AgentWorkspaceView } from "./agents/AgentWorkspaceChrome";
import { sortAssistantWorkspaceFiles } from "./agents/agentWorkspaceFiles";
import { ASSISTANT_QUICK_ACTIONS } from "./agents/assistantLearningFlow";
import {
  formatHistoryRole,
  isRecord,
  sparkBotHistoryChannel,
  sparkBotHistoryPieces,
  sparkBotHistoryTimestamp,
} from "./agents/assistantHistoryUtils";
import {
  ASSISTANT_COURSE_PRESETS,
  ASSISTANT_STYLE_PRESETS,
  assistantCoursePreset,
  assistantPersonaFromPreset,
  assistantStylePreset,
  DEFAULT_ASSISTANT_COURSE,
  DEFAULT_ASSISTANT_STYLE,
} from "./agents/assistantCreateWizardPresets";
import { TeachingAssistantWorkbench } from "./agents/TeachingAssistantWorkbench";

const AgentConfigCard = lazy(() =>
  import("./agents/AgentConfigPanels").then((module) => ({
    default: module.AgentConfigCard,
  })),
);
const AgentConfigDetail = lazy(() =>
  import("./agents/AgentConfigPanels").then((module) => ({
    default: module.AgentConfigDetail,
  })),
);
const BotProfileEditor = lazy(() =>
  import("./agents/BotSettingsPanels").then((module) => ({
    default: module.BotProfileEditor,
  })),
);
const BotRuntimeEditor = lazy(() =>
  import("./agents/BotSettingsPanels").then((module) => ({
    default: module.BotRuntimeEditor,
  })),
);
const BotToolsEditor = lazy(() =>
  import("./agents/BotSettingsPanels").then((module) => ({
    default: module.BotToolsEditor,
  })),
);
const BotCard = lazy(() =>
  import("./agents/SparkBotLibraryPanels").then((module) => ({
    default: module.BotCard,
  })),
);
const SoulLibrary = lazy(() =>
  import("./agents/SparkBotLibraryPanels").then((module) => ({
    default: module.SoulLibrary,
  })),
);
const SparkBotChat = lazy(() =>
  import("./agents/SparkBotChatPanel").then((module) => ({
    default: module.SparkBotChat,
  })),
);
const AssistantCreateWizard = lazy(() =>
  import("./agents/AssistantCreateWizard").then((module) => ({
    default: module.AssistantCreateWizard,
  })),
);
const AssistantDemoReadinessPanel = lazy(() =>
  import("./agents/AssistantDemoReadinessPanel").then((module) => ({
    default: module.AssistantDemoReadinessPanel,
  })),
);
const AssistantEvidenceAndArtifactsPanel = lazy(() =>
  import("./agents/AssistantEvidencePanels").then((module) => ({
    default: module.AssistantEvidenceAndArtifactsPanel,
  })),
);
const AssistantChannelPanel = lazy(() =>
  import("./agents/AssistantWorkspacePanels").then((module) => ({
    default: module.AssistantChannelPanel,
  })),
);
const AssistantWorkspaceFilesPanel = lazy(() =>
  import("./agents/AssistantWorkspacePanels").then((module) => ({
    default: module.AssistantWorkspaceFilesPanel,
  })),
);

export function AgentsPage() {
  const params = useParams({ strict: false }) as { botId?: string };
  const location = useLocation();
  const [agentsView, setAgentsView] =
    useState<AgentWorkspaceView>("assistants");
  const shouldLoadAssistantView = agentsView === "assistants";
  const shouldLoadCapabilitiesView = agentsView === "capabilities";
  const shouldLoadWorkspaceView = agentsView === "workspace";
  const shouldLoadAdvancedView = agentsView === "advanced";
  const shouldLoadActiveBot =
    shouldLoadAssistantView ||
    shouldLoadWorkspaceView ||
    shouldLoadAdvancedView;
  const bots = useSparkBots();
  const agentConfigs = useAgentConfigs();
  const schemas = useSparkBotChannelSchemas({
    enabled: shouldLoadWorkspaceView,
  });
  const souls = useSparkBotSouls({ enabled: shouldLoadAssistantView });
  const recentBots = useSparkBotRecent(5);
  const mutations = useSparkBotMutations();
  const learnerProfile = useLearnerProfile();
  const learningReport = useLearningEffectReport({
    courseId: "",
    window: "14d",
  });
  const learningNextActions = useLearningEffectNextActions({
    courseId: "",
    window: "14d",
    limit: 3,
  });
  const learningMutations = useLearningEffectMutations();
  const items = bots.data ?? [];
  const running = items.filter((item) => item.running).length;
  const [botId, setBotId] = useState(DEFAULT_ASSISTANT_COURSE.botId);
  const [name, setName] = useState(DEFAULT_ASSISTANT_COURSE.name);
  const [description, setDescription] = useState(
    DEFAULT_ASSISTANT_COURSE.description,
  );
  const [persona, setPersona] = useState(() =>
    assistantPersonaFromPreset(
      DEFAULT_ASSISTANT_COURSE,
      DEFAULT_ASSISTANT_STYLE,
    ),
  );
  const [selectedBotId, setSelectedBotId] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [newFileName, setNewFileName] = useState("");
  const [selectedChannel, setSelectedChannel] = useState<string>("");
  const [selectedAgentType, setSelectedAgentType] = useState<string | null>(
    null,
  );
  const [createStep, setCreateStep] = useState(0);
  const [selectedCoursePreset, setSelectedCoursePreset] = useState(
    ASSISTANT_COURSE_PRESETS[0].id,
  );
  const [selectedStylePreset, setSelectedStylePreset] = useState(
    ASSISTANT_STYLE_PRESETS[0].id,
  );
  const [chatDraft, setChatDraft] = useState("");
  const pathBotId = /^\/agents\/([^/?#]+)\/chat/.exec(location.pathname)?.[1];
  const routeBotId = params.botId
    ? decodeURIComponent(params.botId)
    : pathBotId
      ? decodeURIComponent(pathBotId)
      : null;
  const activeBotId =
    selectedBotId && items.some((item) => item.bot_id === selectedBotId)
      ? selectedBotId
      : routeBotId && items.some((item) => item.bot_id === routeBotId)
        ? routeBotId
        : items[0]?.bot_id || null;
  const activeBot = useSparkBotDetail(activeBotId, {
    enabled: shouldLoadActiveBot,
  });
  const files = useSparkBotFiles(activeBotId);
  const history = useSparkBotHistory(activeBotId);
  const fileItems = useMemo(() => files.data ?? [], [files.data]);
  const sortedFileItems = useMemo(
    () => sortAssistantWorkspaceFiles(fileItems),
    [fileItems],
  );
  const activeFileName =
    selectedFile &&
    sortedFileItems.some((item) => item.filename === selectedFile)
      ? selectedFile
      : sortedFileItems[0]?.filename || null;
  const activeFile = useSparkBotFile(activeBotId, activeFileName, {
    enabled: shouldLoadWorkspaceView,
  });
  const channelKeys = Object.keys(schemas.data?.channels ?? {});
  const activeChannel =
    selectedChannel && channelKeys.includes(selectedChannel)
      ? selectedChannel
      : channelKeys[0] || "";
  const runtimeAgents = Object.entries(agentConfigs.data ?? {});
  const activeAgentType =
    selectedAgentType &&
    runtimeAgents.some(([agentType]) => agentType === selectedAgentType)
      ? selectedAgentType
      : runtimeAgents[0]?.[0] || null;
  const activeAgentConfig = activeAgentType
    ? (agentConfigs.data ?? {})[activeAgentType]
    : undefined;
  const agentDetail = useAgentConfigDetail(activeAgentType, {
    enabled: shouldLoadCapabilitiesView,
  });
  const activeBotSummary =
    activeBot.data ?? items.find((item) => item.bot_id === activeBotId);
  const recommendedActions = learningNextActions.data?.items?.length
    ? learningNextActions.data.items
    : (learningReport.data?.next_actions?.slice(0, 3) ?? []);

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
    setBotId(DEFAULT_ASSISTANT_COURSE.botId);
    setName(DEFAULT_ASSISTANT_COURSE.name);
    setDescription(DEFAULT_ASSISTANT_COURSE.description);
    setPersona(
      assistantPersonaFromPreset(
        DEFAULT_ASSISTANT_COURSE,
        DEFAULT_ASSISTANT_STYLE,
      ),
    );
    setSelectedCoursePreset(DEFAULT_ASSISTANT_COURSE.id);
    setSelectedStylePreset(DEFAULT_ASSISTANT_STYLE.id);
    setCreateStep(0);
  };

  const applyCreatePreset = (
    courseId = selectedCoursePreset,
    styleId = selectedStylePreset,
  ) => {
    const preset = assistantCoursePreset(courseId);
    const style = assistantStylePreset(styleId);
    setBotId(preset.botId);
    setName(preset.name);
    setDescription(preset.description);
    setPersona(assistantPersonaFromPreset(preset, style));
  };

  const updateChannel = async (config: Record<string, unknown>) => {
    if (!activeBotId || !activeChannel) return;
    await mutations.update.mutateAsync({
      botId: activeBotId,
      payload: {
        channels: {
          ...(isRecord(activeBot.data?.channels)
            ? activeBot.data?.channels
            : {}),
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
          ...(isRecord(activeBot.data?.channels)
            ? activeBot.data?.channels
            : {}),
          ...config,
        },
      },
    });
  };

  const createWorkspaceFile = async (
    event: React.FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault();
    if (!activeBotId || !newFileName.trim()) return;
    const filename = newFileName.trim();
    await mutations.writeFile.mutateAsync({
      botId: activeBotId,
      filename,
      content: "",
    });
    setSelectedFile(filename);
    setNewFileName("");
  };

  return (
    <div className="h-full overflow-y-auto px-4 py-4 pb-24 lg:px-5 lg:pb-5">
      <div className="mx-auto max-w-[1040px] space-y-4">
        <NotionProductHero
          eyebrow="AI 助教中心"
          title="今天先学什么，助教会给出答案"
          description="围绕课程资料、学习画像和最近练习组织答疑、图解、练习与复盘。高级配置仍在，但默认先服务学习任务。"
          accent="purple"
          imageSrc="/illustrations/sparkweave-assistant-studio.svg"
          imageAlt="AI 助教工作台预览"
          previewTitle="课程助教工作台"
          previewDescription="把画像、课程资料、讲解、练习和评估回写放进同一条学习路径。"
          tiles={[
            { label: "画像驱动", helper: "知道薄弱点", tone: "lavender" },
            { label: "资料可追溯", helper: "回答有来源", tone: "sky" },
            { label: "评估闭环", helper: "学完能回写", tone: "yellow" },
          ]}
          actions={
            <>
              <Button
                tone="primary"
                onClick={() => setAgentsView("assistants")}
              >
                <Bot size={16} />
                进入我的助教
              </Button>
              <Button
                tone="secondary"
                onClick={() => setAgentsView("capabilities")}
              >
                <Wand2 size={16} />
                查看助教能力
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

        <TeachingAssistantWorkbench
          bot={activeBotSummary}
          activeBotId={activeBotId}
          fileCount={fileItems.length}
          historyCount={history.data?.length ?? 0}
          recentCount={recentBots.data?.length ?? 0}
          profile={learnerProfile.data}
          report={learningReport.data}
          nextActions={recommendedActions}
          learningLoading={
            learnerProfile.isLoading ||
            learningReport.isLoading ||
            learningNextActions.isLoading
          }
          pending={mutations.create.isPending}
          completePending={learningMutations.completeAction.isPending}
          onStart={() => {
            if (activeBotId)
              void mutations.create.mutateAsync({
                bot_id: activeBotId,
                auto_start: true,
              });
          }}
          onUseAction={(prompt) => {
            setAgentsView("assistants");
            setChatDraft(prompt);
          }}
          onOpenCapabilities={() => setAgentsView("capabilities")}
          onOpenWorkspace={() => setAgentsView("workspace")}
          onCompleteAction={(action) =>
            learningMutations.completeAction.mutateAsync({
              actionId: action.id,
              note: "Learner marked the assistant recommendation as completed from AI 助教中心.",
              courseId: learningReport.data?.course_id || "",
              conceptIds: action.target_concepts,
            })
          }
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
          files={sortedFileItems.length}
          onChange={setAgentsView}
        />

        {agentsView === "capabilities" ? (
          <Suspense
            fallback={<AgentsWorkspaceLoading label="正在准备助教能力" />}
          >
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
                  <h2
                    className="text-base font-semibold text-ink"
                    aria-label="运行时智能体矩阵"
                  >
                    助教能力
                  </h2>
                </div>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
                  把底层多智能体能力包装成学习任务：讲懂概念、分步解题、生成练习、组织资料和制定路径。
                </p>
              </div>
              <div className="mt-4 flex justify-end border-t border-line pt-4">
                <Button
                  tone="secondary"
                  onClick={() => void agentConfigs.refetch()}
                  disabled={agentConfigs.isFetching}
                >
                  {agentConfigs.isFetching ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <RefreshCw size={16} />
                  )}
                  同步
                </Button>
              </div>
              <div
                className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3"
                data-testid="agent-config-matrix"
              >
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
          </Suspense>
        ) : null}

        {agentsView === "assistants" ? (
          <Suspense
            fallback={<AgentsWorkspaceLoading label="正在准备我的助教" />}
          >
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
                    <h2 className="text-base font-semibold text-ink">
                      我的课程助教
                    </h2>
                    <Button
                      tone="secondary"
                      onClick={() => void bots.refetch()}
                    >
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
                        pending={
                          mutations.create.isPending ||
                          mutations.stop.isPending ||
                          mutations.destroy.isPending
                        }
                        onSelect={() => setSelectedBotId(bot.bot_id)}
                        onStart={() =>
                          void mutations.create.mutateAsync({
                            bot_id: bot.bot_id,
                            auto_start: true,
                          })
                        }
                        onStop={() =>
                          void mutations.stop.mutateAsync(bot.bot_id)
                        }
                        onDestroy={() => {
                          if (window.confirm(`彻底删除助教 ${bot.bot_id}？`))
                            void mutations.destroy.mutateAsync(bot.bot_id);
                        }}
                      />
                    ))}
                  </div>
                  {!items.length ? (
                    <p className="mt-4 rounded-lg border border-dashed border-line bg-canvas p-4 text-sm leading-6 text-slate-500">
                      暂未配置课程助教。创建后即可绑定资料、对话答疑，并持续沉淀学习记录。
                    </p>
                  ) : null}
                </section>

                <section
                  className="rounded-lg border border-line bg-white p-3"
                  data-testid="sparkbot-create-toggle"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h2
                        className="text-base font-semibold text-ink"
                        aria-label="创建助教"
                      >
                        创建课程助教
                      </h2>
                      <p className="mt-1 text-sm text-slate-500">
                        三步创建长期助教：课程、风格、确认。
                      </p>
                    </div>
                    <Badge tone="neutral">第 {createStep + 1} 步</Badge>
                  </div>
                  <AssistantCreateWizard
                    step={createStep}
                    courseId={selectedCoursePreset}
                    styleId={selectedStylePreset}
                    botId={botId}
                    name={name}
                    description={description}
                    persona={persona}
                    souls={souls.data ?? []}
                    pending={mutations.create.isPending}
                    onStepChange={setCreateStep}
                    onCourseSelect={(courseId) => {
                      setSelectedCoursePreset(courseId);
                      const preset = assistantCoursePreset(courseId);
                      const style = assistantStylePreset(selectedStylePreset);
                      setBotId(preset.botId);
                      setName(preset.name);
                      setDescription(preset.description);
                      setPersona(assistantPersonaFromPreset(preset, style));
                    }}
                    onStyleSelect={(styleId) => {
                      setSelectedStylePreset(styleId);
                      setPersona(
                        assistantPersonaFromPreset(
                          assistantCoursePreset(selectedCoursePreset),
                          assistantStylePreset(styleId),
                        ),
                      );
                    }}
                    onBotIdChange={setBotId}
                    onNameChange={setName}
                    onDescriptionChange={setDescription}
                    onPersonaChange={setPersona}
                    onApplyPreset={() => applyCreatePreset()}
                    onUseSoul={(soul) => {
                      setPersona(soul.content);
                      setName((current) => current || soul.name);
                    }}
                    onSubmit={createBot}
                  />
                </section>
              </div>

              <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
                <SparkBotChat
                  botId={activeBotId}
                  bot={activeBotSummary}
                  running={Boolean(activeBot.data?.running)}
                  draftPrompt={chatDraft}
                  feedbackPending={learningMutations.appendEvent.isPending}
                  quickActions={ASSISTANT_QUICK_ACTIONS}
                  onFeedback={(feedback, response) =>
                    learningMutations.appendEvent.mutateAsync({
                      source: "sparkbot",
                      source_id: activeBotId || "",
                      actor: "learner",
                      verb: "rated",
                      object_type: "assistant_response",
                      object_id: `sparkbot:${activeBotId || "unknown"}`,
                      title: `助教回答反馈：${feedback}`,
                      summary: `学生对助教回答反馈：${feedback}`,
                      course_id: learningReport.data?.course_id || "",
                      resource_type: "chat",
                      confidence: 0.74,
                      metadata: {
                        bot_id: activeBotId,
                        feedback,
                        helpful: feedback === "有帮助",
                        response_preview: response.slice(0, 240),
                      },
                    })
                  }
                />
                <SoulLibrary
                  souls={souls.data ?? []}
                  pending={
                    mutations.createSoul.isPending ||
                    mutations.updateSoul.isPending ||
                    mutations.deleteSoul.isPending
                  }
                  onUse={(soul) => {
                    setPersona(soul.content);
                    setName((current) => current || soul.name);
                  }}
                  onCreate={(soul) => mutations.createSoul.mutateAsync(soul)}
                  onUpdate={(soulId, payload) =>
                    mutations.updateSoul.mutateAsync({ soulId, payload })
                  }
                  onDelete={(soulId) =>
                    mutations.deleteSoul.mutateAsync(soulId)
                  }
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
                          {channel ? (
                            <Badge tone="brand">{channel}</Badge>
                          ) : null}
                        </div>
                        <div className="mt-3 grid gap-3">
                          {pieces.map((piece, pieceIndex) => (
                            <div
                              key={`${piece.role}-${pieceIndex}`}
                              className="border-t border-line pt-3 first:border-t-0 first:pt-0"
                              data-testid={`sparkbot-history-piece-${index}-${pieceIndex}`}
                            >
                              <p className="text-xs font-semibold tracking-normal text-brand-purple">
                                {formatHistoryRole(piece.role)}
                              </p>
                              <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-600">
                                {piece.content}
                              </p>
                            </div>
                          ))}
                        </div>
                      </article>
                    );
                  })}
                </div>
                {activeBotId && !history.data?.length ? (
                  <p className="mt-4 rounded-lg border border-dashed border-line bg-canvas p-4 text-sm text-slate-500">
                    暂无历史消息。
                  </p>
                ) : null}
              </section>
            </motion.div>
          </Suspense>
        ) : null}

        {agentsView === "advanced" ? (
          <Suspense
            fallback={<AgentsWorkspaceLoading label="正在准备高级配置" />}
          >
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
                  return mutations.update.mutateAsync({
                    botId: activeBotId,
                    payload,
                  });
                }}
              />

              <BotToolsEditor
                bot={activeBot.data}
                pending={mutations.update.isPending}
                onSave={(tools) => {
                  if (!activeBotId) return Promise.resolve();
                  return mutations.update.mutateAsync({
                    botId: activeBotId,
                    payload: { tools },
                  });
                }}
              />

              <BotRuntimeEditor
                bot={activeBot.data}
                pending={mutations.update.isPending}
                onSave={(payload) => {
                  if (!activeBotId) return Promise.resolve();
                  return mutations.update.mutateAsync({
                    botId: activeBotId,
                    payload,
                  });
                }}
              />
            </motion.div>
          </Suspense>
        ) : null}

        {agentsView === "workspace" ? (
          <Suspense
            fallback={<AgentsWorkspaceLoading label="正在准备助教工作区" />}
          >
            <motion.div
              key="agent-workspace"
              className="space-y-4"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2, ease: "easeOut" }}
            >
              <AssistantEvidenceAndArtifactsPanel
                report={learningReport.data}
                profile={learnerProfile.data}
                files={sortedFileItems}
                history={history.data ?? []}
                nextActions={recommendedActions}
                onUsePrompt={(prompt) => {
                  setAgentsView("assistants");
                  setChatDraft(prompt);
                }}
              />
              <AssistantDemoReadinessPanel
                report={learningReport.data}
                profile={learnerProfile.data}
                files={sortedFileItems}
                history={history.data ?? []}
                nextActions={recommendedActions}
              />
              <div className="grid gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
                <AssistantChannelPanel
                  activeBotId={activeBotId}
                  running={Boolean(activeBot.data?.running)}
                  globalSchema={schemas.data?.global}
                  channelSchemas={schemas.data?.channels ?? {}}
                  channelKeys={channelKeys}
                  activeChannel={activeChannel}
                  channels={
                    isRecord(activeBot.data?.channels)
                      ? activeBot.data?.channels
                      : undefined
                  }
                  loading={schemas.isLoading || schemas.isFetching}
                  pending={mutations.update.isPending}
                  onChannelSelect={setSelectedChannel}
                  onSaveGlobal={updateGlobalChannels}
                  onSaveChannel={updateChannel}
                />
                <AssistantWorkspaceFilesPanel
                  files={sortedFileItems}
                  activeBotId={activeBotId}
                  activeFileName={activeFileName}
                  activeFile={activeFile.data}
                  fallbackContent={
                    sortedFileItems.find(
                      (item) => item.filename === activeFileName,
                    )?.content
                  }
                  newFileName={newFileName}
                  pending={mutations.writeFile.isPending}
                  loading={activeFile.isLoading}
                  onNewFileNameChange={setNewFileName}
                  onCreateFile={createWorkspaceFile}
                  onSelectFile={setSelectedFile}
                  onSaveFile={(content) => {
                    if (!activeBotId || !activeFileName)
                      return Promise.resolve();
                    return mutations.writeFile.mutateAsync({
                      botId: activeBotId,
                      filename: activeFileName,
                      content,
                    });
                  }}
                />
              </div>
            </motion.div>
          </Suspense>
        ) : null}
      </div>
    </div>
  );
}
function AgentsWorkspaceLoading({ label }: { label: string }) {
  return (
    <section className="rounded-lg border border-line bg-white/82 p-4">
      <p className="text-sm font-semibold text-ink">{label}</p>
      <div className="mt-3 space-y-2">
        <span className="block h-3 w-44 max-w-full rounded bg-slate-100" />
        <span className="block h-16 rounded bg-slate-100/80" />
        <span className="block h-16 rounded bg-slate-100/60" />
      </div>
    </section>
  );
}
