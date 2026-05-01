import { BookMarked, Check, Link2, MessageSquareText } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { SelectInput } from "@/components/ui/Field";
import { useNotebookDetail } from "@/hooks/useApiQueries";
import { capabilityLabel } from "@/lib/capabilities";
import { sessionDisplayTitle } from "@/lib/sessionDisplay";
import type { NotebookReference, NotebookRecord, NotebookSummary, SessionSummary } from "@/lib/types";

interface ContextReferencesPanelProps {
  sessions: SessionSummary[];
  currentSessionId: string | null;
  notebooks: NotebookSummary[];
  historyReferences: string[];
  notebookReferences: NotebookReference[];
  onHistoryReferencesChange: (references: string[]) => void;
  onNotebookReferencesChange: (references: NotebookReference[]) => void;
}

export function ContextReferencesPanel({
  sessions,
  currentSessionId,
  notebooks,
  historyReferences,
  notebookReferences,
  onHistoryReferencesChange,
  onNotebookReferencesChange,
}: ContextReferencesPanelProps) {
  const [selectedNotebookId, setSelectedNotebookId] = useState<string | null>(null);
  const activeNotebookId =
    selectedNotebookId && notebooks.some((notebook) => notebook.id === selectedNotebookId)
      ? selectedNotebookId
      : notebooks[0]?.id || "";
  const notebookDetail = useNotebookDetail(activeNotebookId || null);
  const selectableSessions = useMemo(
    () =>
      sessions
        .filter((session) => (session.session_id || session.id) !== currentSessionId)
        .slice(0, 8),
    [currentSessionId, sessions],
  );
  const selectedHistory = useMemo(() => new Set(historyReferences), [historyReferences]);
  const selectedRecordIds = useMemo(() => {
    const ref = notebookReferences.find((item) => item.notebook_id === activeNotebookId);
    return new Set(ref?.record_ids ?? []);
  }, [activeNotebookId, notebookReferences]);
  const notebookReferenceCount = notebookReferences.reduce((total, item) => total + item.record_ids.length, 0);

  const toggleHistory = (sessionId: string) => {
    if (!sessionId) return;
    onHistoryReferencesChange(
      selectedHistory.has(sessionId)
        ? historyReferences.filter((item) => item !== sessionId)
        : [...historyReferences, sessionId],
    );
  };

  const toggleNotebookRecord = (record: NotebookRecord) => {
    const recordId = String(record.id || record.record_id || "").trim();
    if (!activeNotebookId || !recordId) return;
    const next = [...notebookReferences];
    const index = next.findIndex((item) => item.notebook_id === activeNotebookId);
    if (index < 0) {
      onNotebookReferencesChange([...next, { notebook_id: activeNotebookId, record_ids: [recordId] }]);
      return;
    }
    const existing = next[index];
    const recordIds = existing.record_ids.includes(recordId)
      ? existing.record_ids.filter((item) => item !== recordId)
      : [...existing.record_ids, recordId];
    if (recordIds.length) {
      next[index] = { ...existing, record_ids: recordIds };
    } else {
      next.splice(index, 1);
    }
    onNotebookReferencesChange(next);
  };

  return (
    <section className="border-b border-line p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Link2 size={17} className="text-brand-blue" />
            <h2 className="text-sm font-semibold text-ink">引用上下文</h2>
          </div>
          <p className="mt-1 text-xs leading-5 text-slate-500">选择少量历史或笔记作为本轮素材。</p>
        </div>
        <Badge tone={historyReferences.length || notebookReferenceCount ? "brand" : "neutral"}>
          {historyReferences.length + notebookReferenceCount}
        </Badge>
      </div>

      <div className="mt-3 space-y-4">
        <div>
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="flex items-center gap-2 text-xs font-semibold uppercase text-slate-500">
              <MessageSquareText size={14} />
              历史会话
            </p>
            {historyReferences.length ? (
              <Button tone="quiet" className="min-h-7 px-2 text-xs" onClick={() => onHistoryReferencesChange([])}>
                清空
              </Button>
            ) : null}
          </div>
          <div className="max-h-44 space-y-1.5 overflow-y-auto pr-1">
            {selectableSessions.map((session, index) => {
              const sessionId = session.session_id || session.id;
              const active = selectedHistory.has(sessionId);
              return (
                <button
                  key={sessionId}
                  type="button"
                  aria-pressed={active}
                  data-testid={`context-history-${sessionId}`}
                  onClick={() => toggleHistory(sessionId)}
                  className={`flex w-full items-start gap-2 rounded-lg border px-3 py-2 text-left transition ${
                    active ? "border-teal-200 bg-teal-50" : "border-line bg-white hover:border-teal-200"
                  }`}
                >
                  <span
                    className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border ${
                      active ? "border-brand-teal bg-brand-teal text-white" : "border-line bg-white text-transparent"
                    }`}
                  >
                    <Check size={12} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-ink">{sessionDisplayTitle(session, index)}</span>
                    <span className="mt-1 block truncate text-xs text-slate-500">
                      {capabilityLabel(session.preferences?.capability)} · {session.message_count ?? 0} 条消息
                    </span>
                  </span>
                </button>
              );
            })}
            {!selectableSessions.length ? (
              <p className="rounded-lg border border-dashed border-line bg-white p-3 text-xs leading-5 text-slate-500">暂无可引用的历史会话。</p>
            ) : null}
          </div>
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="flex items-center gap-2 text-xs font-semibold uppercase text-slate-500">
              <BookMarked size={14} />
              笔记记录
            </p>
            {notebookReferenceCount ? (
              <Button tone="quiet" className="min-h-7 px-2 text-xs" onClick={() => onNotebookReferencesChange([])}>
                清空
              </Button>
            ) : null}
          </div>
          <SelectInput value={activeNotebookId} onChange={(event) => setSelectedNotebookId(event.target.value)}>
            <option value="">选择笔记本</option>
            {notebooks.map((notebook) => (
              <option key={notebook.id} value={notebook.id}>
                {notebook.name}
              </option>
            ))}
          </SelectInput>
          <div className="mt-3 max-h-48 space-y-1.5 overflow-y-auto pr-1">
            {(notebookDetail.data?.records ?? []).slice(0, 10).map((record) => {
              const recordId = String(record.id || record.record_id || "");
              const active = selectedRecordIds.has(recordId);
              const recordType = record.record_type || record.type || "record";
              return (
                <button
                  key={recordId}
                  type="button"
                  aria-pressed={active}
                  data-testid={`context-record-${activeNotebookId}-${recordId}`}
                  onClick={() => toggleNotebookRecord(record)}
                  className={`w-full rounded-lg border px-3 py-2 text-left transition ${
                    active ? "border-teal-200 bg-teal-50" : "border-line bg-white hover:border-teal-200"
                  }`}
                >
                  <span className="flex items-start gap-2">
                    <span
                      className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border ${
                        active ? "border-brand-teal bg-brand-teal text-white" : "border-line bg-white text-transparent"
                      }`}
                    >
                      <Check size={12} />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center gap-2">
                        <Badge tone="neutral">{recordType}</Badge>
                        <span className="min-w-0 flex-1 truncate text-sm font-medium text-ink">{record.title}</span>
                      </span>
                      <span className="mt-2 line-clamp-2 text-xs leading-5 text-slate-500">
                        {record.summary || record.output || "暂无摘要"}
                      </span>
                    </span>
                  </span>
                </button>
              );
            })}
            {activeNotebookId && notebookDetail.isLoading ? (
              <p className="rounded-lg bg-white p-3 text-xs text-slate-500">正在读取笔记记录...</p>
            ) : null}
            {activeNotebookId && !notebookDetail.isLoading && !notebookDetail.data?.records?.length ? (
              <p className="rounded-lg border border-dashed border-line bg-white p-3 text-xs leading-5 text-slate-500">这个笔记本还没有记录。</p>
            ) : null}
            {!notebooks.length ? (
              <p className="rounded-lg border border-dashed border-line bg-white p-3 text-xs leading-5 text-slate-500">暂无笔记本，先在笔记页面创建或保存一条结果。</p>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  );
}
