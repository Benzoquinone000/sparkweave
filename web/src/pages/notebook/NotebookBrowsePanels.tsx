import { AnimatePresence, motion } from "framer-motion";
import { BookMarked, Edit3, FileText, ListChecks, MoreHorizontal, Plus, RefreshCw, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import type { NotebookDetail, NotebookRecord, NotebookSummary } from "@/lib/types";

import { NotebookMetaEditor, RecordCard } from "./NotebookRecordPanels";

type NotebookMetaPayload = {
  name: string;
  description: string;
  color: string;
  icon: string;
};

export function NotebookListPanel({
  items,
  activeNotebookId,
  createActive,
  questionsActive,
  onRefresh,
  onCreate,
  onQuestions,
  onSelect,
}: {
  items: NotebookSummary[];
  activeNotebookId: string | null;
  createActive: boolean;
  questionsActive: boolean;
  onRefresh: () => void;
  onCreate: () => void;
  onQuestions: () => void;
  onSelect: (notebookId: string) => void;
}) {
  return (
    <section className="rounded-lg border border-line bg-white p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold text-ink">我的记录本</h2>
        <Button tone="quiet" className="min-h-8 px-2 text-xs" onClick={onRefresh}>
          <RefreshCw size={14} />
          刷新
        </Button>
      </div>
      <Button
        tone={createActive ? "primary" : "secondary"}
        className="mt-3 w-full justify-center"
        data-testid="notebook-create-toggle"
        onClick={onCreate}
      >
        <Plus size={16} />
        新建记录本
      </Button>
      <div className="mt-4 space-y-1">
        {items.map((item) => (
          <motion.button
            key={item.id}
            type="button"
            onClick={() => onSelect(item.id)}
            className={`dt-interactive w-full rounded-lg border px-3 py-3 text-left transition ${
              activeNotebookId === item.id && !questionsActive
                ? "border-brand-purple-300 bg-tint-lavender"
                : "border-transparent bg-white hover:border-brand-purple-300 hover:bg-canvas"
            }`}
            whileHover={{ y: -0.5 }}
            whileTap={{ scale: 0.99 }}
          >
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white text-brand-blue">
                <FileText size={18} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold text-ink">{item.name}</p>
                <p className="mt-1 line-clamp-2 text-sm leading-6 text-slate-500">{item.description || "暂无描述"}</p>
              </div>
              <Badge tone="neutral">{item.record_count ?? 0}</Badge>
            </div>
          </motion.button>
        ))}
      </div>
      {!items.length ? (
        <div className="mt-5">
          <EmptyState icon={<BookMarked size={24} />} title="先创建一个记录本" description="建好后可以写复盘、存错题，也可以把聊天和导学结果沉淀进来。" />
        </div>
      ) : null}
      <div className="mt-4 border-t border-line pt-3">
        <Button tone={questionsActive ? "primary" : "quiet"} className="w-full justify-center" onClick={onQuestions}>
          <ListChecks size={16} />
          错题本
        </Button>
      </div>
    </section>
  );
}

export function NotebookDetailPanel({
  detail,
  activeNotebookId,
  routeRecordId,
  updatePending,
  removePending,
  onManualRecord,
  onQuestions,
  onDeleteNotebook,
  onSaveNotebook,
  onEditRecord,
  onDeleteRecord,
}: {
  detail?: NotebookDetail;
  activeNotebookId: string | null;
  routeRecordId: string | null;
  updatePending: boolean;
  removePending: boolean;
  onManualRecord: () => void;
  onQuestions: () => void;
  onDeleteNotebook: () => void;
  onSaveNotebook: (payload: NotebookMetaPayload) => Promise<unknown>;
  onEditRecord: (record: NotebookRecord) => void;
  onDeleteRecord: (record: NotebookRecord) => void;
}) {
  return (
    <motion.section
      key="notebook-detail"
      className="rounded-lg border border-line bg-white p-4"
      initial={{ opacity: 0, x: 14 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -10 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Badge tone="brand">当前记录本</Badge>
          <h2 className="mt-3 text-lg font-semibold text-ink">{detail?.name || "记录本详情"}</h2>
          <p className="mt-1 text-sm text-slate-500">{detail?.description || "选择一个记录本查看学习记录。"}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button tone="secondary" data-testid="notebook-manual-toggle" onClick={onManualRecord} disabled={!activeNotebookId}>
            <Edit3 size={16} />
            写一条记录
          </Button>
          <Button tone="secondary" onClick={onQuestions}>
            <ListChecks size={16} />
            错题本
          </Button>
          {activeNotebookId ? (
            <details className="rounded-lg border border-line bg-white px-3 py-2 [&>summary::-webkit-details-marker]:hidden">
              <summary
                className="dt-interactive flex cursor-pointer items-center gap-2 text-xs font-medium text-slate-600"
                data-testid="notebook-management-toggle"
              >
                <MoreHorizontal size={15} />
                管理
              </summary>
              <div className="mt-2 flex flex-col gap-2 sm:w-32">
                <Button
                  tone="danger"
                  className="min-h-8 justify-start px-2 text-xs"
                  data-testid="notebook-delete"
                  onClick={onDeleteNotebook}
                  disabled={removePending}
                >
                  <Trash2 size={14} />
                  删除记录本
                </Button>
              </div>
            </details>
          ) : null}
        </div>
      </div>
      {activeNotebookId && detail ? (
        <NotebookMetaEditor key={detail.id} notebook={detail} pending={updatePending} onSave={onSaveNotebook} />
      ) : null}
      <div className="mt-5 grid gap-3">
        <AnimatePresence initial={false}>
          {(detail?.records ?? []).slice(0, 12).map((record) => (
            <motion.div
              key={record.id || record.record_id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.18, ease: "easeOut" }}
            >
              <RecordCard
                record={record}
                active={Boolean(routeRecordId && routeRecordId === String(record.id || record.record_id || ""))}
                onEdit={() => onEditRecord(record)}
                onDelete={() => onDeleteRecord(record)}
              />
            </motion.div>
          ))}
        </AnimatePresence>
        {activeNotebookId && !detail?.records?.length ? (
          <EmptyState icon={<FileText size={24} />} title="暂无记录" description="点“写一条记录”补充复盘，或从聊天、导学结果里保存关键内容。" />
        ) : null}
      </div>
    </motion.section>
  );
}
