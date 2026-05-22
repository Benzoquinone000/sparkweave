import { Check, Clock3, Edit3, Loader2, PanelLeftClose, Plus, Trash2, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { TextInput } from "@/components/ui/Field";
import { capabilityLabel } from "@/lib/capabilities";
import { sessionDisplayTitle } from "@/lib/sessionDisplay";
import type { SessionSummary } from "@/lib/types";

export function SessionHistoryPanel({
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

  const startRename = (session: SessionSummary, index: number) => {
    setRenamingId(session.session_id);
    setTitleDraft(sessionDisplayTitle(session, index));
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
    <section className="dt-dynamic-card rounded-lg border border-line bg-white p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <Clock3 size={17} className="text-brand-blue" />
          <h2 className="truncate text-sm font-semibold text-ink">历史会话</h2>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {onCollapse ? (
            <button
              type="button"
              className="dt-interactive inline-flex h-8 w-8 items-center justify-center rounded-md text-slate-500 hover:bg-canvas hover:text-brand-purple"
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
        {sessions.slice(0, 8).map((session, index) => (
          <div
            key={session.session_id}
            data-testid={`${testIdPrefix}-session-card-${session.session_id}`}
            className={`dt-dynamic-result w-full rounded-lg border px-3 py-2 text-left transition ${
              sessionId === session.session_id
                ? "border-brand-purple-300 bg-tint-lavender"
                : "border-line bg-white hover:border-brand-purple-300"
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
                      {sessionDisplayTitle(session, index)}
                    </span>
                    {loadingSessionId === session.session_id ? (
                      <Loader2 size={14} className="animate-spin text-brand-purple" />
                    ) : null}
                  </span>
                  <span className="mt-1 block truncate text-xs text-slate-500">
                    {capabilityLabel(session.preferences?.capability)} · {session.message_count} 条消息
                  </span>
                </button>
                <div className="flex shrink-0 gap-1">
                  <button
                    type="button"
                    className="rounded-md p-1.5 text-slate-500 transition hover:bg-white hover:text-brand-purple"
                    onClick={() => startRename(session, index)}
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
        {!sessions.length ? <p className="dt-dynamic-empty rounded-lg bg-canvas p-3 text-sm text-slate-500">发送消息后会沉淀到这里。</p> : null}
      </div>
    </section>
  );
}
