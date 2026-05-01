import { AnimatePresence, motion } from "framer-motion";
import { useLocation, useParams } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  BookOpenCheck,
  Check,
  CheckCircle2,
  Clock3,
  Edit3,
  FileQuestion,
  ImageIcon,
  Lightbulb,
  Loader2,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightOpen,
  PlayCircle,
  Plus,
  Route,
  Save,
  Sparkles,
  Trash2,
  X,
  type LucideIcon,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { CapabilityPicker } from "@/components/chat/CapabilityPicker";
import { Composer } from "@/components/chat/Composer";
import { ContextReferencesPanel } from "@/components/chat/ContextReferencesPanel";
import { KnowledgeSelector } from "@/components/chat/KnowledgeSelector";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { TaskSnapshot } from "@/components/chat/TaskSnapshot";
import { ToolSelector } from "@/components/chat/ToolSelector";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FieldShell, SelectInput, TextArea, TextInput } from "@/components/ui/Field";
import { defaultConfigForCapability, defaultToolsForCapability, getCapability } from "@/lib/capabilities";
import { getSession } from "@/lib/api";
import type {
  CapabilityId,
  ChatAttachment,
  ChatMessage,
  LearnerProfileSnapshot,
  NotebookReference,
  NotebookSummary,
  SessionDetail,
  SessionSummary,
  StreamEvent,
} from "@/lib/types";
import { buildNotebookAsset, type NotebookAsset } from "@/lib/notebookAssets";
import { useChatRuntime } from "@/hooks/useChatRuntime";
import { useLearnerProfile, useLearnerProfileMutations, useNotebookMutations, useNotebooks, useSessionMutations, useSessions } from "@/hooks/useApiQueries";

const CAPABILITY_IDS = new Set<CapabilityId>([
  "chat",
  "deep_solve",
  "deep_question",
  "deep_research",
  "visualize",
  "math_animator",
]);

function isCapabilityId(value: unknown): value is CapabilityId {
  return typeof value === "string" && CAPABILITY_IDS.has(value as CapabilityId);
}

function getInitialCapabilityFromLocation(): CapabilityId {
  if (typeof window === "undefined") return "chat";
  const value = new URLSearchParams(window.location.search).get("capability");
  return isCapabilityId(value) ? value : "chat";
}

function formatStageLabel(event: StreamEvent | null, assistantStatus?: ChatMessage["status"]) {
  if (assistantStatus === "done") return "已完成";
  if (assistantStatus === "error") return "异常";
  if (!event) return "等待任务";
  const stage = String(event.stage ?? "").toLowerCase();
  if (event.type === "result" || event.type === "done") return "已完成";
  if (event.type === "error") return "异常";
  if (event.type === "stage_start" && stage === "thinking") return "正在思考";
  if (event.type === "progress" && stage === "thinking") return "正在思考";
  if (event.type === "stage_end" && stage === "thinking") return "整理答案";
  if (event.type === "stage_start" && stage === "responding") return "正在回答";
  if (event.type === "stage_end" && stage === "responding") return "已完成";
  if (stage === "thinking") return "正在思考";
  if (stage === "responding") return "正在回答";
  return event.stage || event.type;
}

export function ChatPage() {
  const params = useParams({ strict: false }) as { sessionId?: string };
  const location = useLocation();
  const initialCapability = useMemo(() => getInitialCapabilityFromLocation(), []);
  const [capability, setCapability] = useState<CapabilityId>(initialCapability);
  const [tools, setTools] = useState<string[]>(() => defaultToolsForCapability(initialCapability));
  const [capabilityConfig, setCapabilityConfig] = useState<Record<string, unknown>>(() => ({ ...getCapability(initialCapability).config }));
  const [knowledgeBases, setKnowledgeBases] = useState<string[]>([]);
  const [historyReferences, setHistoryReferences] = useState<string[]>([]);
  const [notebookReferences, setNotebookReferences] = useState<NotebookReference[]>([]);
  const [language, setLanguage] = useState<"zh" | "en">("zh");
  const [contextOpen, setContextOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyCollapsed, setHistoryCollapsed] = useState(false);
  const [loadingSessionId, setLoadingSessionId] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<ChatMessage | null>(null);
  const [saveNotice, setSaveNotice] = useState<{ title: string; notebookName: string } | null>(null);
  const runtime = useChatRuntime();
  const sessions = useSessions();
  const sessionMutations = useSessionMutations();
  const notebooks = useNotebooks();
  const notebookMutations = useNotebookMutations();
  const learnerProfile = useLearnerProfile();
  const learnerProfileMutations = useLearnerProfileMutations();
  const queryClient = useQueryClient();
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const refreshedProfileTurnRef = useRef<string | null>(null);
  const activeCapability = getCapability(capability);
  const profileFocus = learnerProfile.data?.overview.current_focus?.trim();
  const saveAsset = useMemo(
    () =>
      saveMessage
        ? buildNotebookAsset({
            message: saveMessage,
            messages: runtime.messages,
            sessionId: runtime.sessionId,
            turnId: runtime.turnId,
            language,
            knowledgeBase: knowledgeBases[0] ?? null,
          })
        : null,
    [knowledgeBases, language, runtime.messages, runtime.sessionId, runtime.turnId, saveMessage],
  );
  const pathSessionId = /^\/chat\/([^/?#]+)/.exec(location.pathname)?.[1];
  const routeSessionId = params.sessionId
    ? decodeURIComponent(params.sessionId)
    : pathSessionId
      ? decodeURIComponent(pathSessionId)
      : null;
  const { hydrateSession } = runtime;

  useEffect(() => {
    if (!runtime.messages.length) return;
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [runtime.messages.length, runtime.lastEvent]);

  useEffect(() => {
    if (!saveNotice) return;
    const timer = window.setTimeout(() => setSaveNotice(null), 3000);
    return () => window.clearTimeout(timer);
  }, [saveNotice]);

  const canSend = runtime.status === "idle" || runtime.status === "error";
  const latestAssistant = useMemo(
    () => [...runtime.messages].reverse().find((message) => message.role === "assistant") ?? null,
    [runtime.messages],
  );
  const stageLabel = useMemo(() => {
    return formatStageLabel(runtime.lastEvent, latestAssistant?.status);
  }, [latestAssistant?.status, runtime.lastEvent]);

  useEffect(() => {
    if (!latestAssistant || latestAssistant.status !== "done") return;
    if (!runtime.turnId || refreshedProfileTurnRef.current === runtime.turnId) return;
    refreshedProfileTurnRef.current = runtime.turnId;
    void learnerProfileMutations.refresh
      .mutateAsync({ force: true })
      .catch(() => {
        void queryClient.invalidateQueries({ queryKey: ["learner-profile"] });
      });
  }, [latestAssistant, learnerProfileMutations.refresh, queryClient, runtime.turnId]);

  const send = (content: string, attachments: ChatAttachment[]) => {
    runtime.send({
      content,
      capability,
      tools,
      knowledgeBases,
      historyReferences,
      notebookReferences,
      attachments,
      language,
      config: capabilityConfig,
    });
  };

  const sendQuickAction = useCallback(
    (content: string, quickCapability: CapabilityId = "chat", quickConfig?: Record<string, unknown>) => {
      const nextTools = defaultToolsForCapability(quickCapability);
      const nextConfig = {
        ...defaultConfigForCapability(quickCapability, content),
        ...(quickConfig ?? {}),
      };
      setCapability(quickCapability);
      setTools(nextTools);
      setCapabilityConfig(nextConfig);
      runtime.send({
        content,
        capability: quickCapability,
        tools: nextTools,
        knowledgeBases,
        historyReferences,
        notebookReferences,
        attachments: [],
        language,
        config: nextConfig,
      });
    },
    [historyReferences, knowledgeBases, language, notebookReferences, runtime],
  );

  const newSession = () => {
    runtime.newSession();
    setHistoryReferences([]);
    setNotebookReferences([]);
  };

  const handleCapabilityChange = useCallback((next: CapabilityId) => {
    setCapability(next);
    setTools(defaultToolsForCapability(next));
    setCapabilityConfig({ ...getCapability(next).config });
  }, []);

  const applySessionDetail = useCallback((detail: SessionDetail) => {
    hydrateSession(detail);
    const pref = detail.preferences;
    if (isCapabilityId(pref?.capability)) handleCapabilityChange(pref.capability);
    if (pref?.tools) setTools(pref.tools);
    if (pref?.knowledge_bases) setKnowledgeBases(pref.knowledge_bases);
    if (pref?.language === "zh" || pref?.language === "en") setLanguage(pref.language);
    setContextOpen(false);
  }, [handleCapabilityChange, hydrateSession]);

  const loadSessionById = async (targetSessionId: string) => {
    setLoadingSessionId(targetSessionId);
    try {
      const detail = await getSession(targetSessionId);
      applySessionDetail(detail);
    } finally {
      setLoadingSessionId(null);
    }
  };

  const loadSession = async (session: SessionSummary) => {
    await loadSessionById(session.session_id);
  };

  const renameSession = async (sessionId: string, title: string) => {
    await sessionMutations.rename.mutateAsync({ sessionId, title });
  };

  const deleteChatSession = async (sessionId: string) => {
    await sessionMutations.remove.mutateAsync(sessionId);
    if (runtime.sessionId === sessionId) runtime.newSession();
  };

  useEffect(() => {
    if (!routeSessionId || routeSessionId === runtime.sessionId) return;
    let cancelled = false;
    getSession(routeSessionId)
      .then((detail) => {
        if (!cancelled) applySessionDetail(detail);
      });
    return () => {
      cancelled = true;
    };
  }, [applySessionDetail, routeSessionId, runtime.sessionId]);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="shrink-0 border-b border-line bg-white px-4 py-2.5 lg:px-5">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <h1 className="truncate text-base font-semibold text-ink">AI 学习工作台</h1>
            <p className="hidden truncate text-xs text-slate-500 md:block">先输入问题，需要时再添加资料、工具或学习方式。</p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {profileFocus ? (
              <a
                href="/memory"
                className="hidden max-w-[220px] truncate rounded-lg border border-teal-100 bg-teal-50 px-2.5 py-1.5 text-xs font-medium text-brand-teal hover:border-teal-200 md:inline-flex"
                title={`画像当前重点：${profileFocus}`}
              >
                画像：{profileFocus}
              </a>
            ) : null}
            <span className="hidden rounded-lg border border-line bg-canvas px-2.5 py-1.5 text-xs font-medium text-slate-600 sm:inline-flex">
              {activeCapability.label} · {formatRuntimeStatus(runtime.status)}
            </span>
            <button
              type="button"
              data-testid="chat-history-toggle"
              onClick={() => setHistoryOpen((value) => !value)}
              className="dt-interactive inline-flex h-9 items-center gap-2 rounded-lg border border-line bg-white px-3 text-sm text-slate-600 hover:border-teal-200 hover:text-brand-teal lg:hidden"
              aria-label="历史会话"
            >
              <Clock3 size={16} />
              历史
            </button>
            <button
              type="button"
              data-testid="chat-context-toggle"
              onClick={() => setContextOpen((value) => !value)}
              className="dt-interactive inline-flex h-9 items-center gap-2 rounded-lg border border-line bg-white px-3 text-sm text-slate-600 hover:border-teal-200 hover:text-brand-teal"
              aria-label="上下文"
            >
              <PanelRightOpen size={16} />
              资料与工具
            </button>
          </div>
        </div>
      </div>

      <div className="flex min-h-0 flex-1">
        <aside
          className={`hidden shrink-0 border-r border-line bg-white/80 transition-[width] duration-200 lg:block ${
            historyCollapsed ? "w-14 p-2" : "w-72 p-3"
          }`}
          data-testid="chat-history-sidebar"
          data-collapsed={historyCollapsed ? "true" : "false"}
        >
          {historyCollapsed ? (
            <div className="flex h-full flex-col items-center gap-3">
              <button
                type="button"
                className="dt-interactive inline-flex h-10 w-10 items-center justify-center rounded-lg border border-line bg-white text-slate-600 hover:border-teal-200 hover:text-brand-teal"
                onClick={() => setHistoryCollapsed(false)}
                aria-label="展开历史会话"
                data-testid="chat-history-expand"
                title="展开历史会话"
              >
                <PanelLeftOpen size={17} />
              </button>
              <div className="flex min-h-0 flex-1 flex-col items-center gap-2 rounded-lg border border-line bg-white px-2 py-3 text-slate-500">
                <Clock3 size={16} className="text-brand-blue" />
                <span className="text-xs font-medium [writing-mode:vertical-rl]">历史</span>
                <span className="rounded-md bg-canvas px-1.5 py-1 text-xs">{sessions.data?.length ?? 0}</span>
              </div>
            </div>
          ) : (
            <SessionHistoryPanel
              sessions={sessions.data ?? []}
              sessionId={runtime.sessionId}
              onLoadSession={loadSession}
              onRenameSession={renameSession}
              onDeleteSession={deleteChatSession}
              onNewSession={newSession}
              loadingSessionId={loadingSessionId}
              sessionActionPending={sessionMutations.rename.isPending || sessionMutations.remove.isPending}
              testIdPrefix="chat-sidebar"
              onCollapse={() => setHistoryCollapsed(true)}
            />
          )}
        </aside>
        <section className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-4 py-4 lg:px-5">
            <div className="mx-auto flex max-w-4xl flex-col gap-4">
              {runtime.messages.length ? (
                runtime.messages.map((message) => (
                  <MessageBubble key={message.id} message={message} onSave={setSaveMessage} sessionId={runtime.sessionId} />
                ))
              ) : (
                <EmptyState
                  activeCapability={activeCapability.label}
                  profile={learnerProfile.data}
                  disabled={!canSend}
                  onQuickSend={sendQuickAction}
                />
              )}
            </div>
          </div>

          <div className="shrink-0 border-t border-line bg-canvas px-4 py-3 pb-24 lg:px-5 lg:pb-4">
            {runtime.error ? (
              <div className="mx-auto mb-3 flex max-w-4xl items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-brand-red">
                <AlertTriangle size={16} />
                {runtime.error}
              </div>
            ) : null}
            <div className="mx-auto max-w-4xl">
              <Composer disabled={!canSend} onCancel={runtime.cancel} onSend={send} />
            </div>
          </div>
        </section>
      </div>

      <AnimatePresence>
        {historyOpen ? (
          <motion.div
            className="fixed inset-0 z-40 bg-slate-950/25 lg:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setHistoryOpen(false)}
          >
            <motion.aside
              className="ml-auto flex h-full w-[min(360px,92vw)] flex-col border-l border-line bg-white shadow-panel"
              data-testid="chat-history-drawer"
              initial={{ x: 360 }}
              animate={{ x: 0 }}
              exit={{ x: 360 }}
              onClick={(event) => event.stopPropagation()}
            >
              <div className="flex h-14 shrink-0 items-center justify-between border-b border-line px-4">
                <div>
                  <p className="text-sm font-semibold text-ink">历史会话</p>
                  <p className="mt-0.5 text-xs text-slate-500">继续之前的学习线索。</p>
                </div>
                <button
                  type="button"
                  onClick={() => setHistoryOpen(false)}
                  className="dt-interactive inline-flex h-9 w-9 items-center justify-center rounded-lg border border-line text-slate-600 hover:border-teal-200 hover:text-brand-teal"
                  aria-label="关闭历史会话"
                >
                  <X size={17} />
                </button>
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto p-3">
                <SessionHistoryPanel
                  sessions={sessions.data ?? []}
                  sessionId={runtime.sessionId}
                  onLoadSession={(session) => {
                    void loadSession(session);
                    setHistoryOpen(false);
                  }}
                  onRenameSession={renameSession}
                  onDeleteSession={deleteChatSession}
                  onNewSession={() => {
                    newSession();
                    setHistoryOpen(false);
                  }}
                  loadingSessionId={loadingSessionId}
                  sessionActionPending={sessionMutations.rename.isPending || sessionMutations.remove.isPending}
                />
              </div>
            </motion.aside>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <AnimatePresence>
        {contextOpen ? (
          <motion.div
            className="fixed inset-0 z-40 bg-slate-950/25"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setContextOpen(false)}
          >
            <motion.aside
              className="ml-auto flex h-full w-[min(420px,92vw)] flex-col border-l border-line bg-white shadow-panel"
              data-testid="chat-mobile-context-drawer"
              initial={{ x: 420 }}
              animate={{ x: 0 }}
              exit={{ x: 420 }}
              onClick={(event) => event.stopPropagation()}
            >
              <div className="flex h-14 shrink-0 items-center justify-between border-b border-line px-4">
                <div>
                  <p className="text-sm font-semibold text-ink">资料与工具</p>
                  <p className="mt-0.5 text-xs text-slate-500">按需补充学习上下文</p>
                </div>
                <button
                  type="button"
                  onClick={() => setContextOpen(false)}
                  className="dt-interactive inline-flex h-9 w-9 items-center justify-center rounded-lg border border-line text-slate-600 hover:border-teal-200 hover:text-brand-teal"
                  aria-label="关闭上下文"
                >
                  <X size={17} />
                </button>
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto p-3">
                <TaskSnapshot
                  messages={runtime.messages}
                  status={runtime.status}
                  stageLabel={stageLabel}
                  sessionId={runtime.sessionId}
                  turnId={runtime.turnId}
                  onSaveMessage={setSaveMessage}
                />
                <div className="mt-3">
                  <ContextPanel
                    capability={capability}
                    setCapability={handleCapabilityChange}
                    tools={tools}
                    setTools={setTools}
                    knowledgeBases={knowledgeBases}
                    setKnowledgeBases={setKnowledgeBases}
                    language={language}
                    setLanguage={setLanguage}
                    capabilityConfig={capabilityConfig}
                    setCapabilityConfig={setCapabilityConfig}
                    stageLabel={stageLabel}
                    sessionId={runtime.sessionId}
                    turnId={runtime.turnId}
                    sessions={sessions.data ?? []}
                    notebooks={notebooks.data ?? []}
                    historyReferences={historyReferences}
                    setHistoryReferences={setHistoryReferences}
                    notebookReferences={notebookReferences}
                    setNotebookReferences={setNotebookReferences}
                    learnerProfile={learnerProfile.data}
                    learnerProfileLoading={learnerProfile.isLoading}
                  />
                </div>
              </div>
            </motion.aside>
          </motion.div>
        ) : null}
      </AnimatePresence>

      {saveNotice ? (
        <div
          role="status"
          className="fixed bottom-5 right-5 z-50 max-w-sm rounded-lg border border-emerald-200 bg-white p-4 text-sm"
        >
          <div className="flex items-start gap-3">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">
              <CheckCircle2 size={17} />
            </span>
            <div className="min-w-0">
              <p className="font-semibold text-ink">已保存为学习资产</p>
              <p className="mt-1 truncate text-slate-500">
                {saveNotice.title} · {saveNotice.notebookName}
              </p>
            </div>
          </div>
        </div>
      ) : null}

      {saveMessage && saveAsset ? (
        <SaveMessageModal
          key={saveMessage.id}
          asset={saveAsset}
          notebooks={notebooks.data ?? []}
          pending={notebookMutations.addRecord.isPending}
          onClose={() => setSaveMessage(null)}
          onSave={async ({ notebookId, title, summary }) => {
            await notebookMutations.addRecord.mutateAsync({
              notebook_ids: [notebookId],
              record_type: saveAsset.recordType,
              title,
              summary,
              user_query: saveAsset.userQuery,
              output: saveAsset.output,
              metadata: {
                ...saveAsset.metadata,
                edited_title: title,
                edited_summary: summary,
              },
              kb_name: knowledgeBases[0] ?? null,
            });
            const notebookName = (notebooks.data ?? []).find((item) => item.id === notebookId)?.name || notebookId;
            setSaveNotice({ title, notebookName });
            setSaveMessage(null);
          }}
        />
      ) : null}
    </div>
  );
}

function cleanText(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function profileTopic(profile?: LearnerProfileSnapshot) {
  const focus = cleanText(profile?.overview.current_focus);
  if (focus) return focus;
  const weakPoint = cleanText(profile?.learning_state.weak_points?.[0]?.label);
  if (weakPoint) return weakPoint;
  return "当前学习任务";
}

function guideHref(profile?: LearnerProfileSnapshot) {
  const action = profile?.next_action;
  if (cleanText(action?.href)) return cleanText(action?.href);
  const prompt = cleanText(action?.suggested_prompt) || cleanText(action?.title) || profileTopic(profile);
  const params = new URLSearchParams({ new: "1", prompt });
  const title = cleanText(action?.title);
  if (title) params.set("action_title", title);
  return `/guide?${params.toString()}`;
}

function quickActionsForProfile(profile?: LearnerProfileSnapshot) {
  const topic = profileTopic(profile);
  return [
    {
      id: "explain",
      label: "讲清卡点",
      description: "用直觉、例子和一个自测题解释。",
      icon: Lightbulb,
      capability: "chat" as const,
      prompt: `请结合我的学习画像，用 5 分钟能读完的方式讲清楚：${topic}。先解释直觉，再给一个例子，最后给我一个自测问题。`,
    },
    {
      id: "practice",
      label: "生成练习",
      description: "选择、判断、填空和简答混合。",
      icon: FileQuestion,
      capability: "deep_question" as const,
      prompt: `围绕「${topic}」生成 5 道交互式练习题，包含选择题、判断题、填空题和简答题，并给出答案解析。`,
      config: {
        mode: "custom",
        topic,
        num_questions: 5,
        difficulty: "auto",
        question_type: "mixed",
      },
    },
    {
      id: "video",
      label: "找公开视频",
      description: "筛 3 个适合当前水平的视频。",
      icon: PlayCircle,
      capability: "chat" as const,
      prompt: `请从网络上帮我推荐适合当前水平的公开视频，主题是「${topic}」。只给 3 个最适合的，并说明为什么适合我。`,
    },
    {
      id: "visual",
      label: "画图解",
      description: "把概念关系画成一张图。",
      icon: ImageIcon,
      capability: "visualize" as const,
      prompt: `请为「${topic}」生成一张简洁的学习图解，突出概念关系、关键步骤和最容易混淆的点。`,
      config: { render_mode: "auto" },
    },
  ];
}

function EmptyState({
  activeCapability,
  profile,
  disabled,
  onQuickSend,
}: {
  activeCapability: string;
  profile?: LearnerProfileSnapshot;
  disabled: boolean;
  onQuickSend: (content: string, capability?: CapabilityId, config?: Record<string, unknown>) => void;
}) {
  const action = profile?.next_action;
  const title = cleanText(action?.title) || `${profileTopic(profile)}：先迈出一步`;
  const summary =
    cleanText(action?.summary) ||
    cleanText(profile?.overview.summary) ||
    "我会根据你的画像和当前问题，自动选择答疑、练习、图解、视频或导学路径。你只需要点一下，或者直接输入问题。";
  const minutes = Number(action?.estimated_minutes || profile?.overview.preferred_time_budget_minutes || 10);
  const actions = quickActionsForProfile(profile);

  return (
    <motion.div
      className="mx-auto w-full max-w-3xl py-10"
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, ease: "easeOut" }}
      data-testid="chat-profile-starter"
    >
      <div className="rounded-lg border border-line bg-white p-4 text-left shadow-sm sm:p-5">
        <div className="flex items-start gap-3">
          <motion.div
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-teal-200 bg-teal-50 text-brand-teal"
            animate={{ y: [0, -2, 0] }}
            transition={{ duration: 3.2, repeat: Infinity, ease: "easeInOut" }}
          >
            <Sparkles size={22} />
          </motion.div>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold uppercase tracking-wide text-brand-teal">今天先做这一步</p>
            <h2 className="mt-1 text-lg font-semibold leading-7 text-ink">{title}</h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">{summary}</p>
            <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
              <span className="rounded-md border border-line bg-canvas px-2 py-1">{Math.max(3, minutes)} 分钟</span>
              <span className="rounded-md border border-line bg-canvas px-2 py-1">默认：{activeCapability}</span>
              {profile?.confidence ? (
                <span className="rounded-md border border-line bg-canvas px-2 py-1">
                  画像可信度 {Math.round(profile.confidence * 100)}%
                </span>
              ) : null}
            </div>
          </div>
        </div>

        <div className="mt-5 flex flex-col gap-2 sm:flex-row">
          <motion.a
            href={guideHref(profile)}
            data-testid="chat-profile-guide"
            className="dt-interactive inline-flex min-h-10 flex-1 items-center justify-center gap-2 rounded-lg bg-brand-teal px-4 text-sm font-semibold text-white hover:bg-teal-700"
            whileHover={{ y: -1 }}
            whileTap={{ scale: 0.99 }}
          >
            <Route size={16} />
            进入导学
          </motion.a>
          <motion.button
            type="button"
            data-testid="chat-profile-start"
            disabled={disabled}
            className="dt-interactive inline-flex min-h-10 flex-1 items-center justify-center gap-2 rounded-lg border border-red-200 bg-white px-4 text-sm font-semibold text-brand-red hover:border-red-300 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
            onClick={() => onQuickSend(cleanText(action?.suggested_prompt) || `请根据我的学习画像，安排我下一步学习：${profileTopic(profile)}`)}
            whileHover={disabled ? undefined : { y: -1 }}
            whileTap={disabled ? undefined : { scale: 0.99 }}
          >
            <BookOpenCheck size={16} />
            直接开始
          </motion.button>
        </div>

        <div className="mt-5 grid gap-2 sm:grid-cols-2">
          {actions.map((item) => (
            <QuickActionButton key={item.id} action={item} disabled={disabled} onQuickSend={onQuickSend} />
          ))}
        </div>
      </div>
    </motion.div>
  );
}

function QuickActionButton({
  action,
  disabled,
  onQuickSend,
}: {
  action: ReturnType<typeof quickActionsForProfile>[number];
  disabled: boolean;
  onQuickSend: (content: string, capability?: CapabilityId, config?: Record<string, unknown>) => void;
}) {
  const Icon = action.icon as LucideIcon;
  return (
    <motion.button
      type="button"
      disabled={disabled}
      data-testid={`chat-profile-action-${action.id}`}
      className="dt-interactive flex min-h-[74px] items-start gap-3 rounded-lg border border-line bg-white p-3 text-left hover:border-teal-200 hover:bg-teal-50/40 disabled:cursor-not-allowed disabled:opacity-50"
      onClick={() => onQuickSend(action.prompt, action.capability, action.config)}
      whileHover={disabled ? undefined : { y: -1 }}
      whileTap={disabled ? undefined : { scale: 0.99 }}
    >
      <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-canvas text-brand-blue">
        <Icon size={16} />
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-semibold text-ink">{action.label}</span>
        <span className="mt-1 block text-xs leading-5 text-slate-500">{action.description}</span>
      </span>
    </motion.button>
  );
}

function formatRuntimeStatus(status: "idle" | "connecting" | "streaming" | "error") {
  return {
    idle: "就绪",
    connecting: "连接中",
    streaming: "生成中",
    error: "异常",
  }[status];
}

function SessionHistoryPanel({
  sessions,
  sessionId,
  onLoadSession,
  onRenameSession,
  onDeleteSession,
  onNewSession,
  onCollapse,
  loadingSessionId,
  sessionActionPending,
  testIdPrefix = "chat",
}: {
  sessions: SessionSummary[];
  sessionId: string | null;
  onLoadSession: (session: SessionSummary) => void;
  onRenameSession: (sessionId: string, title: string) => Promise<void>;
  onDeleteSession: (sessionId: string) => Promise<void>;
  onNewSession: () => void;
  onCollapse?: () => void;
  loadingSessionId: string | null;
  sessionActionPending: boolean;
  testIdPrefix?: string;
}) {
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [titleDraft, setTitleDraft] = useState("");

  const startRename = (session: SessionSummary) => {
    setRenamingId(session.session_id);
    setTitleDraft(session.title || "未命名会话");
  };

  const submitRename = async (targetSessionId: string) => {
    const nextTitle = titleDraft.trim();
    if (!nextTitle) return;
    await onRenameSession(targetSessionId, nextTitle);
    setRenamingId(null);
    setTitleDraft("");
  };

  const removeSession = async (targetSessionId: string) => {
    if (!window.confirm("删除这个历史会话？")) return;
    await onDeleteSession(targetSessionId);
    if (renamingId === targetSessionId) {
      setRenamingId(null);
      setTitleDraft("");
    }
  };

  return (
    <section className="rounded-lg border border-line bg-white p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <Clock3 size={17} className="text-brand-blue" />
          <h2 className="truncate text-sm font-semibold text-ink">历史会话</h2>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {onCollapse ? (
            <button
              type="button"
              className="dt-interactive inline-flex h-8 w-8 items-center justify-center rounded-md text-slate-500 hover:bg-canvas hover:text-brand-teal"
              onClick={onCollapse}
              aria-label="收起历史会话"
              data-testid={`${testIdPrefix}-history-collapse`}
              title="收起历史会话"
            >
              <PanelLeftClose size={15} />
            </button>
          ) : null}
          <Button tone="quiet" className="min-h-8 px-2 text-xs" onClick={onNewSession} data-testid={`${testIdPrefix}-new-session`}>
            <Plus size={14} />
            新建
          </Button>
        </div>
      </div>
      <div className="mt-3 max-h-[calc(100vh-190px)] space-y-1.5 overflow-y-auto pr-1">
        {sessions.slice(0, 8).map((session) => (
          <div
            key={session.session_id}
            data-testid={`${testIdPrefix}-session-card-${session.session_id}`}
            className={`w-full rounded-lg border px-3 py-2 text-left transition ${
              sessionId === session.session_id
                ? "border-teal-200 bg-teal-50"
                : "border-line bg-white hover:border-teal-200"
            }`}
          >
            {renamingId === session.session_id ? (
              <div className="grid gap-2">
                <TextInput
                  value={titleDraft}
                  onChange={(event) => setTitleDraft(event.target.value)}
                  className="h-9"
                  data-testid={`${testIdPrefix}-session-title-${session.session_id}`}
                  aria-label="会话标题"
                />
                <div className="flex gap-2">
                  <Button
                    tone="primary"
                    className="min-h-8 flex-1 px-2 text-xs"
                    onClick={() => void submitRename(session.session_id)}
                    disabled={!titleDraft.trim() || sessionActionPending}
                    data-testid={`${testIdPrefix}-session-rename-save-${session.session_id}`}
                  >
                    {sessionActionPending ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}
                    保存
                  </Button>
                  <Button
                    tone="quiet"
                    className="min-h-8 px-2 text-xs"
                    onClick={() => {
                      setRenamingId(null);
                      setTitleDraft("");
                    }}
                    data-testid={`${testIdPrefix}-session-rename-cancel-${session.session_id}`}
                  >
                    <X size={13} />
                    取消
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex items-start gap-2">
                <button
                  type="button"
                  className="min-w-0 flex-1 text-left"
                  onClick={() => onLoadSession(session)}
                  data-testid={`${testIdPrefix}-session-load-${session.session_id}`}
                >
                  <span className="flex items-center gap-2">
                    <span className="min-w-0 flex-1 truncate text-sm font-medium text-ink">
                      {session.title || "未命名会话"}
                    </span>
                    {loadingSessionId === session.session_id ? (
                      <Loader2 size={14} className="animate-spin text-brand-teal" />
                    ) : null}
                  </span>
                  <span className="mt-1 block truncate text-xs text-slate-500">
                    {session.preferences?.capability || "聊天"} · {session.message_count} 条消息
                  </span>
                </button>
                <div className="flex shrink-0 gap-1">
                  <button
                    type="button"
                    className="rounded-md p-1.5 text-slate-500 transition hover:bg-white hover:text-brand-teal"
                    onClick={() => startRename(session)}
                    data-testid={`${testIdPrefix}-session-rename-${session.session_id}`}
                    aria-label="重命名会话"
                  >
                    <Edit3 size={14} />
                  </button>
                  <button
                    type="button"
                    className="rounded-md p-1.5 text-slate-500 transition hover:bg-white hover:text-brand-red disabled:opacity-50"
                    onClick={() => void removeSession(session.session_id)}
                    disabled={sessionActionPending}
                    data-testid={`${testIdPrefix}-session-delete-${session.session_id}`}
                    aria-label="删除会话"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
        {!sessions.length ? <p className="rounded-lg bg-canvas p-3 text-sm text-slate-500">发送消息后会沉淀到这里。</p> : null}
      </div>
    </section>
  );
}

function ContextPanel({
  capability,
  setCapability,
  tools,
  setTools,
  knowledgeBases,
  setKnowledgeBases,
  language,
  setLanguage,
  capabilityConfig,
  setCapabilityConfig,
  stageLabel,
  sessionId,
  turnId,
  sessions,
  notebooks,
  historyReferences,
  setHistoryReferences,
  notebookReferences,
  setNotebookReferences,
  learnerProfile,
  learnerProfileLoading,
}: {
  capability: CapabilityId;
  setCapability: (value: CapabilityId) => void;
  tools: string[];
  setTools: (value: string[]) => void;
  knowledgeBases: string[];
  setKnowledgeBases: (value: string[]) => void;
  language: "zh" | "en";
  setLanguage: (value: "zh" | "en") => void;
  capabilityConfig: Record<string, unknown>;
  setCapabilityConfig: (value: Record<string, unknown>) => void;
  stageLabel: string;
  sessionId: string | null;
  turnId: string | null;
  sessions: SessionSummary[];
  notebooks: NotebookSummary[];
  historyReferences: string[];
  setHistoryReferences: (value: string[]) => void;
  notebookReferences: NotebookReference[];
  setNotebookReferences: (value: NotebookReference[]) => void;
  learnerProfile?: LearnerProfileSnapshot;
  learnerProfileLoading: boolean;
}) {
  return (
    <div className="overflow-hidden rounded-lg border border-line bg-white">
      <ProfileMiniCard profile={learnerProfile} loading={learnerProfileLoading} />

      <section className="border-b border-line p-3">
        <div className="flex items-center gap-2">
          <Route size={17} className="text-brand-blue" />
          <h2 className="text-sm font-semibold text-ink">学习方式</h2>
        </div>
        <div className="mt-3">
          <CapabilityPicker value={capability} onChange={setCapability} />
        </div>
      </section>

      <CapabilityConfigPanel capability={capability} config={capabilityConfig} onChange={setCapabilityConfig} />

      <section className="border-b border-line p-3">
        <h2 className="text-sm font-semibold text-ink">辅助工具</h2>
        <div className="mt-3">
          <ToolSelector selected={tools} onChange={setTools} />
        </div>
      </section>

      <section className="border-b border-line p-3">
        <div className="flex items-center gap-2">
          <BookOpenCheck size={17} className="text-brand-teal" />
          <h2 className="text-sm font-semibold text-ink">资料范围</h2>
        </div>
        <div className="mt-3">
          <KnowledgeSelector selected={knowledgeBases} onChange={setKnowledgeBases} />
        </div>
      </section>

      <ContextReferencesPanel
        sessions={sessions}
        currentSessionId={sessionId}
        notebooks={notebooks}
        historyReferences={historyReferences}
        notebookReferences={notebookReferences}
        onHistoryReferencesChange={setHistoryReferences}
        onNotebookReferencesChange={setNotebookReferences}
      />

      <section className="p-3">
        <h2 className="text-sm font-semibold text-ink">回答偏好</h2>
        <div className="mt-3 grid gap-2">
          <div className="flex items-center justify-between rounded-lg bg-canvas px-3 py-2 text-sm">
            <span className="text-slate-500">语言</span>
            <select
              value={language}
              onChange={(event) => setLanguage(event.target.value as "zh" | "en")}
              className="rounded-lg border border-line bg-white px-2 py-1 text-sm"
            >
              <option value="zh">中文</option>
              <option value="en">English</option>
            </select>
          </div>
          <details className="rounded-lg bg-canvas px-3 py-2 text-sm text-slate-500">
            <summary className="cursor-pointer select-none text-slate-600">查看当前状态</summary>
            <div className="mt-2 grid gap-2">
              <InfoRow label="进度" value={stageLabel} />
              <InfoRow label="会话" value={sessionId || "待创建"} />
              <InfoRow label="轮次" value={turnId || "待创建"} />
            </div>
          </details>
        </div>
      </section>
    </div>
  );
}

function ProfileMiniCard({ profile, loading }: { profile?: LearnerProfileSnapshot; loading: boolean }) {
  const weakPoints = profile?.learning_state.weak_points?.slice(0, 2) ?? [];
  const nextAction = profile?.next_action?.title?.trim();

  return (
    <section className="border-b border-line bg-teal-50/70 p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-sm font-semibold text-brand-teal">
            <Sparkles size={16} />
            学习画像
          </div>
          {loading ? (
            <p className="mt-2 text-sm text-teal-900">正在读取画像...</p>
          ) : profile ? (
            <>
              <p className="mt-2 line-clamp-2 text-sm leading-6 text-teal-950">
                {profile.overview.current_focus || "继续学习后，系统会整理你的当前重点。"}
              </p>
              {nextAction ? <p className="mt-1 text-xs text-teal-800">下一步：{nextAction}</p> : null}
              {weakPoints.length ? (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {weakPoints.map((item) => (
                    <span key={`${item.label}-${item.source_ids.join("-")}`} className="rounded-md bg-white px-2 py-1 text-xs text-teal-800">
                      {item.label}
                    </span>
                  ))}
                </div>
              ) : null}
            </>
          ) : (
            <p className="mt-2 text-sm leading-6 text-teal-900">完成一次导学或练习后，系统会自动形成画像。</p>
          )}
        </div>
        <a
          href="/memory"
          className="dt-interactive shrink-0 rounded-lg border border-teal-200 bg-white px-2.5 py-1.5 text-xs font-medium text-brand-teal hover:border-brand-teal"
        >
          修正
        </a>
      </div>
    </section>
  );
}

function SaveMessageModal({
  asset,
  notebooks,
  pending,
  onClose,
  onSave,
}: {
  asset: NotebookAsset;
  notebooks: Array<{ id: string; name: string }>;
  pending: boolean;
  onClose: () => void;
  onSave: (input: { notebookId: string; title: string; summary: string }) => Promise<void>;
}) {
  const [notebookId, setNotebookId] = useState(notebooks[0]?.id ?? "");
  const [title, setTitle] = useState(asset.title);
  const [summary, setSummary] = useState(asset.summary);

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/30 px-4"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        <motion.form
          className="w-full max-w-xl rounded-lg border border-line bg-white p-3"
          initial={{ y: 24, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 24, opacity: 0 }}
          onSubmit={(event) => {
            event.preventDefault();
            if (notebookId) void onSave({ notebookId, title, summary });
          }}
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <Badge tone="brand">笔记本</Badge>
              <h2 className="mt-3 text-lg font-semibold text-ink">保存生成结果</h2>
              <p className="mt-1 text-sm leading-6 text-slate-500">把这次回答、图表或题目沉淀到笔记本，后续可用于导学和复盘。</p>
            </div>
            <Button tone="quiet" onClick={onClose}>
              关闭
            </Button>
          </div>
          <div className="mt-5 rounded-lg border border-line bg-canvas p-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="neutral">{asset.assetKind}</Badge>
              <Badge tone="neutral">{asset.recordType}</Badge>
            </div>
            <p className="mt-3 line-clamp-4 text-sm leading-6 text-slate-600">{asset.output}</p>
          </div>
          <div className="mt-5 grid gap-4">
            <FieldShell label="目标笔记本">
              <SelectInput value={notebookId} onChange={(event) => setNotebookId(event.target.value)} required>
                <option value="">请选择</option>
                {notebooks.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </SelectInput>
            </FieldShell>
            <FieldShell label="标题">
              <TextInput value={title} onChange={(event) => setTitle(event.target.value)} required />
            </FieldShell>
            <FieldShell label="摘要">
              <TextArea value={summary} onChange={(event) => setSummary(event.target.value)} />
            </FieldShell>
          </div>
          <div className="mt-5 flex justify-end gap-3">
            <Button tone="secondary" onClick={onClose}>
              取消
            </Button>
            <Button tone="primary" type="submit" disabled={!notebookId || pending}>
              {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
              保存
            </Button>
          </div>
        </motion.form>
      </motion.div>
    </AnimatePresence>
  );
}

function CapabilityConfigPanel({
  capability,
  config,
  onChange,
}: {
  capability: CapabilityId;
  config: Record<string, unknown>;
  onChange: (value: Record<string, unknown>) => void;
}) {
  const patch = (next: Record<string, unknown>) => onChange({ ...config, ...next });
  const toggleSource = (source: string) => {
    const current = Array.isArray(config.sources) ? config.sources.map(String) : [];
    patch({ sources: current.includes(source) ? current.filter((item) => item !== source) : [...current, source] });
  };

  if (capability === "chat") {
    return (
      <section className="border-b border-line p-3">
        <h2 className="text-sm font-semibold text-ink">能力参数</h2>
        <p className="mt-2 text-sm leading-6 text-slate-500">即时答疑无需额外参数。</p>
      </section>
    );
  }

  return (
    <section className="border-b border-line p-3">
      <h2 className="text-sm font-semibold text-ink">能力参数</h2>
      <div className="mt-3 grid gap-3">
        {capability === "deep_question" ? (
          <>
            <div className="grid grid-cols-2 gap-3">
              <FieldShell label="题目数量">
                <TextInput
                  type="number"
                  min={1}
                  max={50}
                  value={Number(config.num_questions ?? 5)}
                  onChange={(event) => patch({ num_questions: Math.max(1, Number(event.target.value) || 1) })}
                />
              </FieldShell>
              <FieldShell label="难度">
                <SelectInput value={String(config.difficulty ?? "medium")} onChange={(event) => patch({ difficulty: event.target.value })}>
                  <option value="auto">自动</option>
                  <option value="easy">简单</option>
                  <option value="medium">中等</option>
                  <option value="hard">困难</option>
                </SelectInput>
              </FieldShell>
            </div>
            <FieldShell label="题型">
              <SelectInput value={String(config.question_type ?? "mixed")} onChange={(event) => patch({ question_type: event.target.value })}>
                <option value="mixed">混合</option>
                <option value="choice">选择题</option>
                <option value="true_false">判断题</option>
                <option value="fill_blank">填空题</option>
                <option value="written">主观题</option>
                <option value="coding">编程题</option>
              </SelectInput>
            </FieldShell>
            <FieldShell label="偏好">
              <TextArea
                value={String(config.preference ?? "")}
                onChange={(event) => patch({ preference: event.target.value })}
                placeholder="例如：偏重概念辨析，答案要有详细解析。"
                className="min-h-20"
              />
            </FieldShell>
          </>
        ) : null}

        {capability === "deep_research" ? (
          <>
            <div className="grid grid-cols-2 gap-3">
              <FieldShell label="模式">
                <SelectInput value={String(config.mode ?? "report")} onChange={(event) => patch({ mode: event.target.value })}>
                  <option value="report">报告</option>
                  <option value="notes">笔记</option>
                  <option value="brief">简报</option>
                </SelectInput>
              </FieldShell>
              <FieldShell label="深度">
                <SelectInput value={String(config.depth ?? "standard")} onChange={(event) => patch({ depth: event.target.value })}>
                  <option value="light">轻量</option>
                  <option value="standard">标准</option>
                  <option value="deep">深入</option>
                </SelectInput>
              </FieldShell>
            </div>
            <div>
              <p className="text-sm font-medium text-ink">研究来源</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {[
                  ["web", "联网"],
                  ["kb", "知识库"],
                  ["papers", "论文"],
                ].map(([value, label]) => {
                  const active = Array.isArray(config.sources) && config.sources.map(String).includes(value);
                  return (
                    <button
                      key={value}
                      type="button"
                      onClick={() => toggleSource(value)}
                      className={`rounded-md border px-2 py-1 text-xs transition ${
                        active ? "border-teal-200 bg-teal-50 text-brand-teal" : "border-line bg-canvas text-slate-600 hover:border-teal-200"
                      }`}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            </div>
          </>
        ) : null}

        {capability === "visualize" ? (
          <FieldShell label="渲染模式">
            <SelectInput value={String(config.render_mode ?? "auto")} onChange={(event) => patch({ render_mode: event.target.value })}>
              <option value="auto">自动</option>
              <option value="svg">SVG</option>
              <option value="mermaid">Mermaid</option>
              <option value="chartjs">Chart.js</option>
            </SelectInput>
          </FieldShell>
        ) : null}

        {capability === "math_animator" ? (
          <>
            <div className="grid grid-cols-2 gap-3">
              <FieldShell label="输出">
                <SelectInput value={String(config.output_mode ?? "video")} onChange={(event) => patch({ output_mode: event.target.value })}>
                  <option value="video">视频</option>
                  <option value="image">图片</option>
                </SelectInput>
              </FieldShell>
              <FieldShell label="质量">
                <SelectInput value={String(config.quality ?? "medium")} onChange={(event) => patch({ quality: event.target.value })}>
                  <option value="low">低</option>
                  <option value="medium">中</option>
                  <option value="high">高</option>
                </SelectInput>
              </FieldShell>
            </div>
            <FieldShell label="风格提示">
              <TextArea
                value={String(config.style_hint ?? "")}
                onChange={(event) => patch({ style_hint: event.target.value })}
                placeholder="例如：干净课堂风，突出公式变形过程。"
                className="min-h-20"
              />
            </FieldShell>
          </>
        ) : null}

        {capability === "deep_solve" ? (
          <label className="flex items-center justify-between gap-3 rounded-lg border border-line bg-canvas px-3 py-2 text-sm">
            <span className="text-slate-600">输出详细解答</span>
            <input
              type="checkbox"
              checked={Boolean(config.detailed_answer ?? true)}
              onChange={(event) => patch({ detailed_answer: event.target.checked })}
            />
          </label>
        ) : null}
      </div>
    </section>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg bg-canvas px-3 py-2 text-sm">
      <span className="text-slate-500">{label}</span>
      <span className="min-w-0 truncate font-medium text-ink">{value}</span>
    </div>
  );
}
