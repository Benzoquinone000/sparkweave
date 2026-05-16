import { useLocation, useParams } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Composer } from "@/components/chat/Composer";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { defaultConfigForCapability, defaultToolsForCapability, getCapability } from "@/lib/capabilities";
import type { CapabilityId, ChatAttachment, NotebookReference } from "@/lib/types";
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
} from "./chat/chatPageUtils";
import { useChatAutoPrompt } from "./chat/useChatAutoPrompt";
import { useChatNotebookSave } from "./chat/useChatNotebookSave";
import { ChatContextStrip } from "./chat/ChatContextStrip";
import {
  ChatContextDrawer,
  ChatHistoryDrawer,
  ChatHistorySidebar,
  ChatTopBar,
  SaveNoticeToast,
} from "./chat/ChatWorkbenchChrome";
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
  const activeCapability = getCapability(capability);
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
      setCapability(quickCapability);
      setTools(nextTools);
      setCapabilityConfig(nextConfig);
      setKnowledgeBases(nextKnowledgeBases);
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
      });
    },
    [historyReferences, knowledgeBases, language, notebookReferences, runtime],
  );

  useChatAutoPrompt({
    initialCapability,
    messageCount: runtime.messages.length,
    runtimeStatus: runtime.status,
    resetRuntimeSession,
    sendQuickAction,
  });

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <ChatTopBar
        profileFocus={profileFocus}
        activeCapabilityLabel={activeCapability.label}
        runtimeStatus={runtime.status}
        onToggleHistory={() => setHistoryOpen((value) => !value)}
        onToggleContext={() => setContextOpen((value) => !value)}
      />

      <div className="flex min-h-0 flex-1">
        <ChatHistorySidebar
          collapsed={historyCollapsed}
          sessions={sessions.data ?? []}
          sessionId={runtime.sessionId}
          onLoadSession={loadSession}
          onRenameSession={renameSession}
          onDeleteSession={deleteChatSession}
          onNewSession={newSession}
          loadingSessionId={loadingSessionId}
          sessionActionPending={sessionActionPending}
          onCollapse={() => setHistoryCollapsed(true)}
          onExpand={() => setHistoryCollapsed(false)}
        />
        <section className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-4 py-4 lg:px-5">
            <div className="mx-auto flex max-w-4xl flex-col gap-4">
              {runtime.messages.length ? (
                runtime.messages.map((message) => (
                  <MessageBubble key={message.id} message={message} onSave={setSaveMessage} sessionId={runtime.sessionId} />
                ))
              ) : (
                <Suspense fallback={<ChatProfileStarterLoading />}>
                  <ChatProfileStarter
                    activeCapability={activeCapability.label}
                    profile={learnerProfile.data}
                    learningEffectAction={learningEffectActions.data?.items?.[0] ?? null}
                    disabled={!canSend}
                    onQuickSend={sendQuickAction}
                  />
                </Suspense>
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
              <ChatContextStrip
                capability={capability}
                tools={tools}
                knowledgeBases={knowledgeBases}
                historyReferenceCount={historyReferences.length}
                notebookReferenceCount={notebookReferences.reduce((total, item) => total + item.record_ids.length, 0)}
                config={capabilityConfig}
                onOpenContext={() => setContextOpen(true)}
              />
              <Composer disabled={!canSend} onCancel={runtime.cancel} onSend={send} />
            </div>
          </div>
        </section>
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
        onSaveMessage={setSaveMessage}
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
  );
}
function ChatProfileStarterLoading() {
  return (
    <section className="mx-auto w-full max-w-5xl py-5 sm:py-7">
      <div className="rounded-lg border border-line bg-white p-5 sm:p-6 lg:p-8">
        <div className="mx-auto max-w-3xl text-center">
          <span className="mx-auto block h-12 w-12 rounded-lg bg-slate-100" />
          <span className="mx-auto mt-4 block h-3 w-32 max-w-full rounded bg-slate-100" />
          <span className="mx-auto mt-4 block h-8 w-[min(520px,90%)] rounded bg-slate-100/90" />
          <span className="mx-auto mt-3 block h-4 w-[min(620px,92%)] rounded bg-slate-100/75" />
          <div className="mt-6 flex flex-wrap justify-center gap-2">
            <span className="h-9 w-24 rounded-lg bg-slate-100" />
            <span className="h-9 w-28 rounded-lg bg-slate-100/80" />
          </div>
        </div>
        <div className="mt-7 grid gap-3 md:grid-cols-[210px_minmax(0,1fr)]">
          <div className="rounded-lg bg-canvas p-4">
            <span className="block h-4 w-28 rounded bg-slate-100" />
            <span className="mt-4 block h-3 w-36 rounded bg-slate-100/80" />
            <span className="mt-2 block h-3 w-24 rounded bg-slate-100/70" />
          </div>
          <div className="rounded-lg bg-canvas p-4">
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
