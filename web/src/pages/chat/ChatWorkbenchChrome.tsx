import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Clock3, PanelRightOpen, X } from "lucide-react";
import { lazy, Suspense, type Dispatch, type SetStateAction } from "react";

import type {
  CapabilityId,
  ChatMessage,
  LearnerProfileSnapshot,
  NotebookReference,
  NotebookSummary,
  SessionSummary,
} from "@/lib/types";
import { formatRuntimeStatus } from "./chatPageUtils";
import { SessionHistoryPanel } from "./SessionHistoryPanel";

type RuntimeStatus = "idle" | "connecting" | "streaming" | "error";

const TaskSnapshot = lazy(() =>
  import("@/components/chat/TaskSnapshot").then((module) => ({ default: module.TaskSnapshot })),
);
const ContextPanel = lazy(() => import("./ContextPanel").then((module) => ({ default: module.ContextPanel })));

export function ChatTopBar({
  profileFocus,
  runtimeStatus,
  onToggleHistory,
  onToggleContext,
}: {
  profileFocus?: string;
  runtimeStatus: RuntimeStatus;
  onToggleHistory: () => void;
  onToggleContext: () => void;
}) {
  return (
    <div className="shrink-0 border-b border-line bg-white px-4 py-2.5 lg:px-5">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h1 className="truncate text-base font-semibold text-ink">问资料</h1>
          <p className="hidden truncate text-xs text-slate-500 md:block">直接输入问题，需要时再选择资料和回答方式。</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {profileFocus ? (
            <a
              href="/memory"
              className="hidden max-w-[220px] truncate rounded-lg border border-brand-purple-300 bg-tint-lavender px-2.5 py-1.5 text-xs font-medium text-brand-purple hover:border-brand-purple-300 md:inline-flex"
              title={`画像当前重点：${profileFocus}`}
            >
              画像：{profileFocus}
            </a>
          ) : null}
          <span className="hidden rounded-lg border border-line bg-canvas px-2.5 py-1.5 text-xs font-medium text-slate-600 sm:inline-flex">
            {formatRuntimeStatus(runtimeStatus)}
          </span>
          <button
            type="button"
            data-testid="chat-history-toggle"
            onClick={onToggleHistory}
            className="dt-interactive inline-flex h-9 items-center gap-2 rounded-lg border border-line bg-white px-3 text-sm text-slate-600 hover:border-brand-purple-300 hover:text-brand-purple lg:hidden"
            aria-label="历史会话"
          >
            <Clock3 size={16} />
            历史
          </button>
          <button
            type="button"
            data-testid="chat-context-toggle"
            onClick={onToggleContext}
            className="dt-interactive inline-flex h-9 items-center gap-2 rounded-lg border border-line bg-white px-3 text-sm text-slate-600 hover:border-brand-purple-300 hover:text-brand-purple"
            aria-label="上下文"
          >
            <PanelRightOpen size={16} />
            资料与偏好
          </button>
        </div>
      </div>
    </div>
  );
}

export function ChatHistoryDrawer({
  open,
  sessions,
  sessionId,
  loadingSessionId,
  sessionActionPending,
  onClose,
  onLoadSession,
  onRenameSession,
  onDeleteSession,
  onNewSession,
}: {
  open: boolean;
  sessions: SessionSummary[];
  sessionId: string | null;
  loadingSessionId: string | null;
  sessionActionPending: boolean;
  onClose: () => void;
  onLoadSession: (session: SessionSummary) => void;
  onRenameSession: (sessionId: string, title: string) => Promise<void>;
  onDeleteSession: (sessionId: string) => Promise<void>;
  onNewSession: () => void;
}) {
  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-40 bg-slate-950/25 lg:hidden"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
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
                onClick={onClose}
                className="dt-interactive inline-flex h-9 w-9 items-center justify-center rounded-lg border border-line text-slate-600 hover:border-brand-purple-300 hover:text-brand-purple"
                aria-label="关闭历史会话"
              >
                <X size={17} />
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-3">
              <SessionHistoryPanel
                sessions={sessions}
                sessionId={sessionId}
                onLoadSession={onLoadSession}
                onRenameSession={onRenameSession}
                onDeleteSession={onDeleteSession}
                onNewSession={onNewSession}
                loadingSessionId={loadingSessionId}
                sessionActionPending={sessionActionPending}
              />
            </div>
          </motion.aside>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

export function ChatContextDrawer({
  open,
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
  messages,
  runtimeStatus,
  historyReferences,
  setHistoryReferences,
  notebookReferences,
  setNotebookReferences,
  learnerProfile,
  learnerProfileLoading,
  onClose,
  onSaveMessage,
}: {
  open: boolean;
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
  messages: ChatMessage[];
  runtimeStatus: RuntimeStatus;
  historyReferences: string[];
  setHistoryReferences: Dispatch<SetStateAction<string[]>>;
  notebookReferences: NotebookReference[];
  setNotebookReferences: Dispatch<SetStateAction<NotebookReference[]>>;
  learnerProfile?: LearnerProfileSnapshot;
  learnerProfileLoading: boolean;
  onClose: () => void;
  onSaveMessage: (message: ChatMessage) => void;
}) {
  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-40 bg-slate-950/25"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
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
                onClick={onClose}
                className="dt-interactive inline-flex h-9 w-9 items-center justify-center rounded-lg border border-line text-slate-600 hover:border-brand-purple-300 hover:text-brand-purple"
                aria-label="关闭上下文"
              >
                <X size={17} />
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-3">
              <Suspense fallback={<DrawerPanelLoading label="正在准备任务状态" />}>
                <TaskSnapshot messages={messages} status={runtimeStatus} stageLabel={stageLabel} onSaveMessage={onSaveMessage} />
              </Suspense>
              <div className="mt-3">
                <Suspense fallback={<DrawerPanelLoading label="正在准备上下文配置" />}>
                <ContextPanel
                  capability={capability}
                  setCapability={setCapability}
                  tools={tools}
                  setTools={setTools}
                  knowledgeBases={knowledgeBases}
                  setKnowledgeBases={setKnowledgeBases}
                  language={language}
                  setLanguage={setLanguage}
                  capabilityConfig={capabilityConfig}
                  setCapabilityConfig={setCapabilityConfig}
                  stageLabel={stageLabel}
                  sessionId={sessionId}
                  turnId={turnId}
                  sessions={sessions}
                  notebooks={notebooks}
                  historyReferences={historyReferences}
                  setHistoryReferences={setHistoryReferences}
                  notebookReferences={notebookReferences}
                  setNotebookReferences={setNotebookReferences}
                  learnerProfile={learnerProfile}
                  learnerProfileLoading={learnerProfileLoading}
                />
                </Suspense>
              </div>
            </div>
          </motion.aside>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

function DrawerPanelLoading({ label }: { label: string }) {
  return (
    <div className="rounded-lg border border-line bg-canvas px-3 py-2 text-xs text-slate-500">
      <span className="font-medium text-ink">{label}</span>
    </div>
  );
}

export function SaveNoticeToast({ notice }: { notice: { title: string; notebookName: string } | null }) {
  if (!notice) return null;

  return (
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
            {notice.title} · {notice.notebookName}
          </p>
        </div>
      </div>
    </div>
  );
}
