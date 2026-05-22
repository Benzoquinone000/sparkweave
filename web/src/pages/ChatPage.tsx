import { useLocation, useNavigate, useParams } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, FilePenLine } from "lucide-react";
import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Composer } from "@/components/chat/Composer";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { SparkWeaveLightField } from "@/components/visual/SparkWeaveLightField";
import { defaultConfigForCapability, defaultToolsForCapability, getCapability } from "@/lib/capabilities";
import {
  getCanvasContextFromDocument,
  getCanvasDocumentFromMessage,
  type ChatCanvasDocument,
} from "@/lib/chatCanvas";
import type { CapabilityId, ChatAttachment, ChatMessage, NotebookReference } from "@/lib/types";
import { useChatRuntime } from "@/hooks/useChatRuntime";
import {
  useLearnerProfile,
  useLearnerProfileMutations,
  useLearningEffectNextActions,
  useNotebookMutations,
  useNotebooks,
  useSessionMutations,
  useSessions,
} from "@/hooks/useApiQueries";
import {
  formatStageLabel,
  getInitialCapabilityFromLocation,
  knowledgeBasesFromSearchParams,
} from "./chat/chatPageUtils";
import { useChatAutoPrompt } from "./chat/useChatAutoPrompt";
import { useChatNotebookSave } from "./chat/useChatNotebookSave";
import { ChatContextStrip } from "./chat/ChatContextStrip";
import {
  ChatContextDrawer,
  ChatHistoryDrawer,
  ChatTopBar,
  SaveNoticeToast,
} from "./chat/ChatWorkbenchChrome";
import { ChatCanvasPanel } from "./chat/ChatCanvasPanel";
import { useChatSessionActions } from "./chat/useChatSessionActions";

const SaveMessageModal = lazy(() =>
  import("./chat/SaveMessageModal").then((module) => ({ default: module.SaveMessageModal })),
);
const ChatProfileStarter = lazy(() =>
  import("./chat/ChatProfileStarter").then((module) => ({ default: module.ChatProfileStarter })),
);

export function ChatPage() {
  const params = useParams({ strict: false }) as { sessionId?: string };
  const location = useLocation();
  const navigate = useNavigate();
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
  const [canvasOpen, setCanvasOpen] = useState(false);
  const [canvasDocument, setCanvasDocument] = useState<ChatCanvasDocument | null>(null);
  const [dismissedAutoCanvasId, setDismissedAutoCanvasId] = useState<string | null>(null);
  const [visualPulseKey, setVisualPulseKey] = useState(0);
  const [completeVisualActive, setCompleteVisualActive] = useState(false);
  const runtime = useChatRuntime();
  const sessions = useSessions();
  const sessionMutations = useSessionMutations();
  const notebooks = useNotebooks();
  const notebookMutations = useNotebookMutations();
  const learnerProfile = useLearnerProfile();
  const learnerProfileMutations = useLearnerProfileMutations();
  const learningEffectActions = useLearningEffectNextActions({ limit: 1, window: "14d" });
  const queryClient = useQueryClient();
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const refreshedProfileTurnRef = useRef<string | null>(null);
  const sessionInvalidationRef = useRef<string>("");
  const routeSyncedSessionRef = useRef<string | null>(null);
  const completeVisualMessageRef = useRef<string | null>(null);
  const completeVisualTimerRef = useRef<number | null>(null);
  const profileFocus = learnerProfile.data?.overview.current_focus?.trim();
  const { saveMessage, saveAsset, saveNotice, savePending, setSaveMessage, closeSaveModal, saveToNotebook } = useChatNotebookSave({
    messages: runtime.messages,
    sessionId: runtime.sessionId,
    turnId: runtime.turnId,
    language,
    knowledgeBases,
    notebooks: notebooks.data ?? [],
    addRecord: notebookMutations.addRecord,
  });
  const pathSessionId = /^\/chat\/([^/?#]+)/.exec(location.pathname)?.[1];
  const routeSessionId = params.sessionId
    ? decodeURIComponent(params.sessionId)
    : pathSessionId
      ? decodeURIComponent(pathSessionId)
      : null;
  const navigateToNewChat = useCallback(() => {
    routeSyncedSessionRef.current = null;
    void navigate({ to: "/chat", replace: true });
  }, [navigate]);
  const navigateToSession = useCallback(
    (nextSessionId: string) => {
      if (!nextSessionId || routeSessionId === nextSessionId) return;
      routeSyncedSessionRef.current = nextSessionId;
      void navigate({
        to: "/chat/$sessionId",
        params: { sessionId: nextSessionId },
        replace: true,
      });
    },
    [navigate, routeSessionId],
  );
  const resetRuntimeSession = runtime.newSession;
  const {
    loadingSessionId,
    newSession,
    handleCapabilityChange,
    loadSession,
    renameSession,
    deleteChatSession,
    sessionActionPending,
  } = useChatSessionActions({
    routeSessionId,
    runtimeSessionId: runtime.sessionId,
    hydrateSession: runtime.hydrateSession,
    resetRuntimeSession,
    sessionMutations,
    setCapability,
    setTools,
    setCapabilityConfig,
    setKnowledgeBases,
    setLanguage,
    setContextOpen,
    setHistoryReferences,
    setNotebookReferences,
    onNewSessionRoute: navigateToNewChat,
    onSessionRoute: navigateToSession,
  });

  useEffect(() => {
    if (!runtime.messages.length) return;
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [runtime.messages.length, runtime.lastEvent]);

  const canSend = runtime.status === "idle" || runtime.status === "error";
  const latestAssistant = useMemo(
    () => [...runtime.messages].reverse().find((message) => message.role === "assistant") ?? null,
    [runtime.messages],
  );
  const stageLabel = useMemo(() => {
    return formatStageLabel(runtime.lastEvent, latestAssistant?.status);
  }, [latestAssistant?.status, runtime.lastEvent]);

  const handleSaveMessage = useCallback((message: ChatMessage) => {
    setSaveMessage(message);
  }, [setSaveMessage]);

  useEffect(() => {
    const handleCanvasSave = (event: Event) => {
      const detail = (event as CustomEvent<ChatMessage>).detail;
      if (!detail || detail.role !== "assistant" || typeof detail.content !== "string") return;
      handleSaveMessage(detail);
    };
    window.addEventListener("sparkweave:canvas-save-message", handleCanvasSave);
    return () => window.removeEventListener("sparkweave:canvas-save-message", handleCanvasSave);
  }, [handleSaveMessage]);

  const openCanvas = useCallback((document: ChatCanvasDocument) => {
    setCanvasDocument(document);
    setDismissedAutoCanvasId(null);
    setCanvasOpen(true);
  }, []);

  const latestCanvasToolDocument = useMemo(
    () => (latestAssistant ? getCanvasDocumentFromMessage(latestAssistant, { mode: "tool" }) : null),
    [latestAssistant],
  );
  const canAutoOpenCanvas =
    Boolean(latestCanvasToolDocument) &&
    (!routeSessionId || !runtime.sessionId || routeSessionId === runtime.sessionId) &&
    latestCanvasToolDocument?.id !== dismissedAutoCanvasId;
  const latestToolCanvasIsNew =
    Boolean(latestCanvasToolDocument) && latestCanvasToolDocument?.messageId !== canvasDocument?.messageId;
  const activeCanvasDocument = runtime.messages.length
    ? canAutoOpenCanvas && latestToolCanvasIsNew
      ? latestCanvasToolDocument
      : canvasDocument ?? (canAutoOpenCanvas ? latestCanvasToolDocument : null)
    : null;
  const activeCanvasOpen = Boolean(activeCanvasDocument && (canvasOpen || canAutoOpenCanvas));

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

  useEffect(() => {
    if (!runtime.sessionId) return;
    const phase = latestAssistant?.status === "done" || runtime.status === "idle" ? "done" : "created";
    const invalidationKey = `${runtime.sessionId}:${phase}`;
    if (sessionInvalidationRef.current === invalidationKey) return;
    sessionInvalidationRef.current = invalidationKey;
    void queryClient.invalidateQueries({ queryKey: ["sessions"] });
    void queryClient.invalidateQueries({ queryKey: ["session", runtime.sessionId] });
  }, [latestAssistant?.status, queryClient, runtime.sessionId, runtime.status]);

  useEffect(() => {
    if (!runtime.sessionId) {
      routeSyncedSessionRef.current = null;
      return;
    }
    if (!routeSessionId) return;
    if (routeSessionId === runtime.sessionId || routeSyncedSessionRef.current === runtime.sessionId) return;
    navigateToSession(runtime.sessionId);
  }, [navigateToSession, routeSessionId, runtime.sessionId]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const requestedKnowledgeBases = knowledgeBasesFromSearchParams(params);
    if (!requestedKnowledgeBases.length) return;
    const timer = window.setTimeout(() => {
      setKnowledgeBases((current) => {
        if (current.length === requestedKnowledgeBases.length && current.every((item, index) => item === requestedKnowledgeBases[index])) {
          return current;
        }
        return requestedKnowledgeBases;
      });
    }, 0);
    return () => window.clearTimeout(timer);
  }, [location.search]);

  const triggerVisualPulse = useCallback(() => {
    setVisualPulseKey((value) => value + 1);
  }, []);

  const latestDoneMessageId = latestAssistant?.status === "done" ? latestAssistant.id : null;

  useEffect(() => {
    if (!latestDoneMessageId) return;
    if (completeVisualMessageRef.current === latestDoneMessageId) return;
    completeVisualMessageRef.current = latestDoneMessageId;
    const startTimer = window.setTimeout(() => {
      setCompleteVisualActive(true);
      triggerVisualPulse();
      if (completeVisualTimerRef.current) {
        window.clearTimeout(completeVisualTimerRef.current);
      }
      completeVisualTimerRef.current = window.setTimeout(() => {
        setCompleteVisualActive(false);
        completeVisualTimerRef.current = null;
      }, 1650);
    }, 0);
    return () => window.clearTimeout(startTimer);
  }, [latestDoneMessageId, triggerVisualPulse]);

  useEffect(() => {
    return () => {
      if (completeVisualTimerRef.current) {
        window.clearTimeout(completeVisualTimerRef.current);
      }
    };
  }, []);

  const send = (content: string, attachments: ChatAttachment[]) => {
    const canvasContext = activeCanvasOpen ? getCanvasContextFromDocument(activeCanvasDocument) : null;
    triggerVisualPulse();
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
      canvasContext,
    });
  };

  const sendQuickAction = useCallback(
    (
      content: string,
      quickCapability: CapabilityId = "chat",
      quickConfig?: Record<string, unknown>,
      options?: { knowledgeBases?: string[] },
    ) => {
      const nextTools = defaultToolsForCapability(quickCapability);
      const nextKnowledgeBases = options?.knowledgeBases ?? knowledgeBases;
      const nextConfig = {
        ...defaultConfigForCapability(quickCapability, content),
        ...(quickConfig ?? {}),
      };
      const canvasContext = activeCanvasOpen ? getCanvasContextFromDocument(activeCanvasDocument) : null;
      setCapability(quickCapability);
      setTools(nextTools);
      setCapabilityConfig(nextConfig);
      setKnowledgeBases(nextKnowledgeBases);
      triggerVisualPulse();
      runtime.send({
        content,
        capability: quickCapability,
        tools: nextTools,
        knowledgeBases: nextKnowledgeBases,
        historyReferences,
        notebookReferences,
        attachments: [],
        language,
        config: nextConfig,
        canvasContext,
      });
    },
    [activeCanvasDocument, activeCanvasOpen, historyReferences, knowledgeBases, language, notebookReferences, runtime, triggerVisualPulse],
  );

  useChatAutoPrompt({
    initialCapability,
    messageCount: runtime.messages.length,
    runtimeStatus: runtime.status,
    resetRuntimeSession,
    sendQuickAction,
  });

  const chatWidthClass = activeCanvasOpen ? "max-w-[820px]" : "max-w-[880px]";
  const hasConversation = runtime.messages.length > 0;
  const isGenerating = runtime.status !== "idle" && runtime.status !== "error";
  const lightFieldMode = isGenerating
    ? "thinking"
    : completeVisualActive
      ? "complete"
      : "idle";
  const lightFieldActive = isGenerating || completeVisualActive;

  return (
    <div
      className={`dt-ai-workspace dt-ai-workspace-has-field dt-ai-workspace-mode-${lightFieldMode} ${
        hasConversation ? "dt-ai-workspace-in-session" : ""
      } flex h-full flex-col overflow-hidden`}
    >
      <SparkWeaveLightField active={lightFieldActive} mode={lightFieldMode} pulseKey={visualPulseKey} />
      <div className="relative z-10 flex h-full min-h-0 flex-col">
        <ChatTopBar
          profileFocus={profileFocus}
          runtimeStatus={runtime.status}
          onToggleHistory={() => setHistoryOpen((value) => !value)}
          onToggleContext={() => setContextOpen((value) => !value)}
        />

        <div className="flex min-h-0 flex-1 overflow-hidden">
          <section className="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
            <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-3.5 pb-4 pt-3 sm:px-5 lg:px-6">
              <div
                className={`mx-auto flex w-full ${chatWidthClass} flex-col ${
                  hasConversation ? "gap-3 py-2.5" : "min-h-full justify-center gap-3 py-4"
                }`}
              >
                {hasConversation ? (
                  runtime.messages.map((message) => (
                    <MessageBubble
                      key={message.id}
                      message={message}
                      onOpenCanvas={openCanvas}
                      onSave={handleSaveMessage}
                      sessionId={runtime.sessionId}
                    />
                  ))
                ) : (
                  <Suspense fallback={<ChatProfileStarterLoading />}>
                    <ChatProfileStarter
                      profile={learnerProfile.data}
                      learningEffectAction={learningEffectActions.data?.items?.[0] ?? null}
                      knowledgeBases={knowledgeBases}
                      disabled={!canSend}
                      onQuickSend={sendQuickAction}
                    />
                  </Suspense>
                )}
              </div>
            </div>

            <div className="dt-composer-dock shrink-0 px-3.5 pb-20 pt-2.5 lg:px-6 lg:pb-4">
              {runtime.error ? (
                <div className={`mx-auto mb-2.5 flex w-full ${chatWidthClass} items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-brand-red`}>
                  <AlertTriangle size={16} />
                  {runtime.error}
                </div>
              ) : null}
              <div className={`mx-auto w-full ${chatWidthClass}`}>
                <ChatContextStrip
                  capability={capability}
                  tools={tools}
                  knowledgeBases={knowledgeBases}
                  historyReferenceCount={historyReferences.length}
                  notebookReferenceCount={notebookReferences.reduce((total, item) => total + item.record_ids.length, 0)}
                  onOpenContext={() => setContextOpen(true)}
                />
                {activeCanvasOpen && activeCanvasDocument ? (
                  <div
                    data-testid="chat-canvas-context-indicator"
                    className="mb-2 flex items-center gap-2 rounded-lg border border-line bg-white/90 px-3 py-2 text-xs text-steel shadow-[0_1px_2px_rgba(15,15,15,0.03)]"
                  >
                    <FilePenLine size={14} className="shrink-0 text-brand-purple" />
                    <span className="min-w-0 truncate">
                      已带入画布：<span className="font-medium text-ink">{activeCanvasDocument.title}</span>
                    </span>
                  </div>
                ) : null}
                <Composer disabled={!canSend} onCancel={runtime.cancel} onSend={send} />
              </div>
            </div>
          </section>
          <ChatCanvasPanel
            key={activeCanvasDocument?.id ?? "empty-canvas"}
            document={activeCanvasDocument}
            open={activeCanvasOpen}
            onClose={() => {
              const closingCanvasId = activeCanvasDocument?.id;
              if (closingCanvasId && closingCanvasId === latestCanvasToolDocument?.id) {
                setDismissedAutoCanvasId(closingCanvasId);
              }
              setCanvasOpen(false);
            }}
            onDocumentChange={(nextDocument) => {
              setCanvasDocument(nextDocument);
              setCanvasOpen(true);
            }}
            onSaveMessage={handleSaveMessage}
          />
        </div>

        <ChatHistoryDrawer
          open={historyOpen}
          sessions={sessions.data ?? []}
          sessionId={runtime.sessionId}
          onClose={() => setHistoryOpen(false)}
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
          sessionActionPending={sessionActionPending}
        />

        <ChatContextDrawer
          open={contextOpen}
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
          messages={runtime.messages}
          runtimeStatus={runtime.status}
          historyReferences={historyReferences}
          setHistoryReferences={setHistoryReferences}
          notebookReferences={notebookReferences}
          setNotebookReferences={setNotebookReferences}
          learnerProfile={learnerProfile.data}
          learnerProfileLoading={learnerProfile.isLoading}
          onClose={() => setContextOpen(false)}
          onSaveMessage={handleSaveMessage}
        />

        <SaveNoticeToast notice={saveNotice} />

        {saveMessage && saveAsset ? (
          <Suspense fallback={null}>
            <SaveMessageModal
              key={saveMessage.id}
              asset={saveAsset}
              notebooks={notebooks.data ?? []}
              pending={savePending}
              onClose={closeSaveModal}
              onSave={saveToNotebook}
            />
          </Suspense>
        ) : null}
      </div>
    </div>
  );
}
function ChatProfileStarterLoading() {
  return (
    <section className="mx-auto w-full max-w-[820px] py-2 sm:py-3">
      <div className="p-3 sm:p-4">
        <div className="mx-auto max-w-3xl text-center">
          <span className="mx-auto block h-8 w-8 rounded-lg bg-slate-100" />
          <span className="mx-auto mt-3 block h-3 w-28 max-w-full rounded bg-slate-100" />
          <span className="mx-auto mt-3 block h-7 w-[min(480px,88%)] rounded bg-slate-100/90" />
          <span className="mx-auto mt-2.5 block h-4 w-[min(560px,90%)] rounded bg-slate-100/75" />
          <div className="mt-5 flex flex-wrap justify-center gap-2">
            <span className="h-8 w-[88px] rounded-lg bg-slate-100" />
            <span className="h-8 w-24 rounded-lg bg-slate-100/80" />
          </div>
        </div>
        <div className="mt-5 grid gap-3 md:grid-cols-[184px_minmax(0,1fr)]">
          <div className="rounded-lg bg-canvas p-3">
            <span className="block h-4 w-28 rounded bg-slate-100" />
            <span className="mt-4 block h-3 w-36 rounded bg-slate-100/80" />
            <span className="mt-2 block h-3 w-24 rounded bg-slate-100/70" />
          </div>
          <div className="rounded-lg bg-canvas p-3">
            <span className="block h-14 rounded bg-slate-100/80" />
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <span className="block h-16 rounded bg-slate-100/70" />
              <span className="block h-16 rounded bg-slate-100/60" />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
