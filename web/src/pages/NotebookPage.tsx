import { AnimatePresence, motion } from "framer-motion";
import {
  BookMarked,
  FileText,
  ListChecks,
  Plus,
} from "lucide-react";
import { useLocation } from "@tanstack/react-router";
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Metric } from "@/components/ui/Metric";
import type { NotebookRecord } from "@/lib/types";
import {
  useNotebookDetail,
  useNotebookMutations,
  useNotebookStats,
  useNotebooks,
  useQuestionCategories,
  useQuestionEntries,
  useQuestionEntryDetail,
  useQuestionNotebookMutations,
} from "@/hooks/useApiQueries";
import { NotebookDetailPanel, NotebookListPanel } from "./notebook/NotebookBrowsePanels";
import { RecordEditor } from "./notebook/NotebookRecordPanels";

type NotebookView = "browse" | "create" | "record" | "questions";

const CreateNotebookPanel = lazy(() =>
  import("./notebook/NotebookEntryPanels").then((module) => ({ default: module.CreateNotebookPanel })),
);
const ManualRecordPanel = lazy(() =>
  import("./notebook/NotebookEntryPanels").then((module) => ({ default: module.ManualRecordPanel })),
);
const QuestionNotebookWorkspace = lazy(() =>
  import("./notebook/QuestionNotebookWorkspace").then((module) => ({ default: module.QuestionNotebookWorkspace })),
);

export function NotebookPage() {
  const location = useLocation();
  const notebooks = useNotebooks();
  const stats = useNotebookStats();
  const mutations = useNotebookMutations();
  const items = useMemo(() => notebooks.data ?? [], [notebooks.data]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [manualTitle, setManualTitle] = useState("");
  const [manualOutput, setManualOutput] = useState("");
  const [manualSummaryPreview, setManualSummaryPreview] = useState("");
  const [categoryName, setCategoryName] = useState("");
  const [editingRecord, setEditingRecord] = useState<NotebookRecord | null>(null);
  const [selectedQuestionId, setSelectedQuestionId] = useState<number | null>(null);
  const [renamingCategoryId, setRenamingCategoryId] = useState<number | null>(null);
  const [categoryDraft, setCategoryDraft] = useState("");
  const [quickQuestion, setQuickQuestion] = useState({
    sessionId: "manual-session",
    questionId: "",
    question: "",
    correctAnswer: "",
    explanation: "",
    difficulty: "medium",
  });
  const [quickQuestionStatus, setQuickQuestionStatus] = useState("");
  const [view, setView] = useState<NotebookView>("browse");
  const notebookSectionRef = useRef<HTMLDivElement | null>(null);
  const questionSectionRef = useRef<HTMLElement | null>(null);
  const searchParams = useMemo(() => getSearchParams(location.search), [location.search]);
  const routeTab = searchParams.get("tab");
  const routeNotebookId = searchParams.get("notebook") || searchParams.get("notebook_id");
  const routeRecordId = searchParams.get("record") || searchParams.get("record_id");
  const routeQuestionKey = searchParams.get("entry") || searchParams.get("entry_id") || searchParams.get("question") || searchParams.get("question_id");
  const shouldLoadQuestions = view === "questions" || routeTab === "questions" || Boolean(routeQuestionKey);
  const questionEntries = useQuestionEntries({ enabled: shouldLoadQuestions });
  const categories = useQuestionCategories({ enabled: shouldLoadQuestions });
  const questionMutations = useQuestionNotebookMutations();
  const activeNotebookId =
    selectedId && items.some((item) => item.id === selectedId)
      ? selectedId
      : routeNotebookId && (!items.length || items.some((item) => item.id === routeNotebookId))
        ? routeNotebookId
        : items[0]?.id || null;
  const detail = useNotebookDetail(activeNotebookId);
  const routeQuestionId = routeQuestionKey && /^\d+$/.test(routeQuestionKey) ? Number(routeQuestionKey) : null;
  const routeQuestion = useQuestionEntryDetail(routeQuestionId);
  const activeQuestion =
    selectedQuestionId && questionEntries.data?.some((entry) => entry.id === selectedQuestionId)
      ? questionEntries.data.find((entry) => entry.id === selectedQuestionId)
      : routeQuestionId && questionEntries.data?.some((entry) => entry.id === routeQuestionId)
        ? questionEntries.data.find((entry) => entry.id === routeQuestionId)
        : routeQuestionId && routeQuestion.data
          ? routeQuestion.data
        : routeQuestionKey && questionEntries.data?.some((entry) => entry.question_id === routeQuestionKey)
          ? questionEntries.data.find((entry) => entry.question_id === routeQuestionKey)
      : questionEntries.data?.[0];

  useEffect(() => {
    const timer = window.setTimeout(() => {
    if (routeTab === "questions" || routeQuestionKey) {
      setView("questions");
      questionSectionRef.current?.scrollIntoView({ block: "start" });
      return;
    }
    if (routeTab === "notebooks" || routeNotebookId || routeRecordId) {
      setView("browse");
      notebookSectionRef.current?.scrollIntoView({ block: "start" });
    }
    }, 0);
    return () => window.clearTimeout(timer);
  }, [routeNotebookId, routeQuestionKey, routeRecordId, routeTab]);

  const createNotebook = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!newName.trim()) return;
    const result = await mutations.create.mutateAsync({
      name: newName.trim(),
      description: newDescription.trim(),
      color: "#0F766E",
      icon: "book",
    });
    setSelectedId(result.notebook.id);
    setNewName("");
    setNewDescription("");
    setView("browse");
  };

  const addManualRecord = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!activeNotebookId || !manualTitle.trim() || !manualOutput.trim()) return;
    const submitter = (event.nativeEvent as SubmitEvent).submitter as HTMLElement | null;
    const useStreamSummary = submitter?.dataset.action === "with-summary";
    const payload = {
      notebook_ids: [activeNotebookId],
      record_type: "chat" as const,
      title: manualTitle.trim(),
      summary: useStreamSummary ? "" : manualOutput.slice(0, 160),
      user_query: manualTitle.trim(),
      output: manualOutput,
      metadata: { source: "web_manual", ui_language: "zh" },
    };
    if (useStreamSummary) {
      setManualSummaryPreview("");
      await mutations.addRecordWithSummary.mutateAsync({
        ...payload,
        onEvent: (_event, data) => {
          if (data.type === "summary_chunk" && typeof data.content === "string") {
            setManualSummaryPreview((current) => `${current}${data.content}`);
          }
          if (data.type === "result" && typeof data.summary === "string") {
            setManualSummaryPreview(data.summary);
          }
        },
      });
    } else {
      await mutations.addRecord.mutateAsync(payload);
    }
    setManualTitle("");
    setManualOutput("");
    if (!useStreamSummary) setView("browse");
  };

  const createCategory = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!categoryName.trim()) return;
    await questionMutations.createCategory.mutateAsync(categoryName.trim());
    setCategoryName("");
  };

  const lookupQuickQuestion = async () => {
    if (!quickQuestion.sessionId.trim() || !quickQuestion.questionId.trim()) return;
    setQuickQuestionStatus("");
    try {
      const entry = await questionMutations.lookupEntry.mutateAsync({
        sessionId: quickQuestion.sessionId.trim(),
        questionId: quickQuestion.questionId.trim(),
      });
      setSelectedQuestionId(entry.id);
      setQuickQuestion((current) => ({
        ...current,
        question: entry.question || current.question,
        correctAnswer: entry.correct_answer || current.correctAnswer,
        explanation: entry.explanation || current.explanation,
        difficulty: entry.difficulty || current.difficulty,
      }));
      setQuickQuestionStatus(`已找到：${entry.question || "这道题"}`);
    } catch (error) {
      setQuickQuestionStatus(error instanceof Error ? `未找到：${error.message}` : "未找到这道题。");
    }
  };

  const upsertQuickQuestion = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!quickQuestion.sessionId.trim() || !quickQuestion.questionId.trim() || !quickQuestion.question.trim()) return;
    const entry = await questionMutations.upsertEntry.mutateAsync({
      session_id: quickQuestion.sessionId.trim(),
      question_id: quickQuestion.questionId.trim(),
      question: quickQuestion.question.trim(),
      question_type: "written",
      options: {},
      correct_answer: quickQuestion.correctAnswer.trim(),
      explanation: quickQuestion.explanation.trim(),
      difficulty: quickQuestion.difficulty.trim(),
    });
    setSelectedQuestionId(entry.id);
    setQuickQuestionStatus(`已写入：${entry.question || quickQuestion.question.trim()}`);
  };

  return (
    <div className="h-full overflow-y-auto px-3.5 py-3.5 pb-20 lg:px-4 lg:pb-4">
      <div className="mx-auto max-w-[1080px] space-y-3.5">
        <NotebookHomeHeader
          hasNotebook={Boolean(activeNotebookId)}
          onCreate={() => setView("create")}
          onQuestions={() => setView("questions")}
          onRecord={() => setView("record")}
        />

        <motion.div
          className="flex flex-wrap gap-x-4 gap-y-1.5"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22, delay: 0.04, ease: "easeOut" }}
        >
          <Metric label="记录本" value={items.length} detail="已创建" icon={<BookMarked size={19} />} />
          <Metric label="学习记录" value={String(stats.data?.total_records ?? 0)} detail={stats.isLoading ? "读取中" : "已保存"} icon={<FileText size={19} />} />
          <Metric
            label="错题收藏"
            value={shouldLoadQuestions ? questionEntries.data?.length ?? 0 : "-"}
            detail={shouldLoadQuestions ? "已加载" : "进入错题本加载"}
            icon={<ListChecks size={19} />}
          />
        </motion.div>

        <div ref={notebookSectionRef} className="grid gap-3.5 lg:grid-cols-[276px_minmax(0,1fr)]">
          <NotebookListPanel
            items={items}
            activeNotebookId={activeNotebookId}
            createActive={view === "create"}
            questionsActive={view === "questions"}
            onRefresh={() => void notebooks.refetch()}
            onCreate={() => setView("create")}
            onQuestions={() => setView("questions")}
            onSelect={(notebookId) => {
              setSelectedId(notebookId);
              setView("browse");
            }}
          />

          <AnimatePresence mode="wait" initial={false}>
            {view === "create" ? (
              <Suspense fallback={<NotebookViewLoading label="正在准备新建记录本" />}>
                <CreateNotebookPanel
                  name={newName}
                  description={newDescription}
                  pending={mutations.create.isPending}
                  onNameChange={setNewName}
                  onDescriptionChange={setNewDescription}
                  onBack={() => setView("browse")}
                  onSubmit={createNotebook}
                />
              </Suspense>
            ) : null}

            {view === "record" ? (
              <Suspense fallback={<NotebookViewLoading label="正在准备学习记录" />}>
                <ManualRecordPanel
                  notebookName={detail.data?.name || ""}
                  hasNotebook={Boolean(activeNotebookId)}
                  title={manualTitle}
                  output={manualOutput}
                  summaryPreview={manualSummaryPreview}
                  addPending={mutations.addRecord.isPending}
                  summaryPending={mutations.addRecordWithSummary.isPending}
                  onTitleChange={setManualTitle}
                  onOutputChange={setManualOutput}
                  onBack={() => setView("browse")}
                  onSubmit={addManualRecord}
                />
              </Suspense>
            ) : null}

            {view === "questions" ? (
              <Suspense fallback={<NotebookViewLoading label="正在准备题目本" />}>
                <QuestionNotebookWorkspace
                  sectionRef={questionSectionRef}
                  categories={categories.data ?? []}
                  entries={questionEntries.data ?? []}
                  activeQuestion={activeQuestion}
                  categoryName={categoryName}
                  renamingCategoryId={renamingCategoryId}
                  categoryDraft={categoryDraft}
                  quickQuestion={quickQuestion}
                  quickQuestionStatus={quickQuestionStatus}
                  createCategoryPending={questionMutations.createCategory.isPending}
                  manageCategoryPending={questionMutations.renameCategory.isPending || questionMutations.deleteCategory.isPending}
                  entryActionPending={questionMutations.updateEntry.isPending || questionMutations.deleteEntry.isPending}
                  categoryLinkPending={questionMutations.addEntryToCategory.isPending || questionMutations.removeEntryFromCategory.isPending}
                  quickQuestionPending={questionMutations.upsertEntry.isPending || questionMutations.lookupEntry.isPending}
                  onBack={() => setView("browse")}
                  onCategoryNameChange={setCategoryName}
                  onCreateCategory={createCategory}
                  onStartRename={(category) => {
                    setRenamingCategoryId(category.id);
                    setCategoryDraft(category.name);
                  }}
                  onCategoryDraft={setCategoryDraft}
                  onRenameCategory={async (categoryId) => {
                    if (!categoryDraft.trim()) return;
                    await questionMutations.renameCategory.mutateAsync({ categoryId, name: categoryDraft.trim() });
                    setRenamingCategoryId(null);
                    setCategoryDraft("");
                  }}
                  onCancelRename={() => {
                    setRenamingCategoryId(null);
                    setCategoryDraft("");
                  }}
                  onDeleteCategory={(categoryId) => questionMutations.deleteCategory.mutateAsync(categoryId)}
                  onSelectQuestion={setSelectedQuestionId}
                  onToggleBookmark={(entry) => questionMutations.updateEntry.mutateAsync({ entryId: entry.id, bookmarked: !entry.bookmarked })}
                  onDeleteQuestion={(entryId) => questionMutations.deleteEntry.mutateAsync(entryId)}
                  onAddCategory={(entryId, categoryId) => questionMutations.addEntryToCategory.mutateAsync({ entryId, categoryId })}
                  onRemoveCategory={(entryId, categoryId) => questionMutations.removeEntryFromCategory.mutateAsync({ entryId, categoryId })}
                  onQuickQuestionChange={setQuickQuestion}
                  onQuickQuestionLookup={() => void lookupQuickQuestion()}
                  onQuickQuestionSubmit={upsertQuickQuestion}
                />
              </Suspense>
            ) : null}

            {view === "browse" ? (
              <NotebookDetailPanel
                detail={detail.data}
                activeNotebookId={activeNotebookId}
                routeRecordId={routeRecordId}
                updatePending={mutations.update.isPending}
                removePending={mutations.remove.isPending}
                onManualRecord={() => setView("record")}
                onQuestions={() => setView("questions")}
                onDeleteNotebook={() => {
                  if (activeNotebookId && window.confirm("删除这个记录本？")) void mutations.remove.mutateAsync(activeNotebookId);
                }}
                onSaveNotebook={(payload) => activeNotebookId ? mutations.update.mutateAsync({ notebookId: activeNotebookId, ...payload }) : Promise.resolve()}
                onEditRecord={setEditingRecord}
                onDeleteRecord={(record) => {
                  const recordId = String(record.id || record.record_id || "");
                  if (activeNotebookId && recordId && window.confirm("删除这条记录？")) {
                    void mutations.deleteRecord.mutateAsync({ notebookId: activeNotebookId, recordId });
                  }
                }}
              />
            ) : null}
          </AnimatePresence>
        </div>

        {editingRecord && activeNotebookId ? (
          <RecordEditor
            key={editingRecord.id || editingRecord.record_id}
            record={editingRecord}
            pending={mutations.updateRecord.isPending}
            onCancel={() => setEditingRecord(null)}
            onSave={async (payload) => {
              const recordId = String(editingRecord.id || editingRecord.record_id || "");
              if (!recordId) return;
              await mutations.updateRecord.mutateAsync({ notebookId: activeNotebookId, recordId, ...payload });
              setEditingRecord(null);
            }}
          />
        ) : null}
      </div>
    </div>
  );
}

function NotebookViewLoading({ label }: { label: string }) {
  return (
    <section className="rounded-lg border border-line bg-white p-4">
      <p className="text-sm font-semibold text-ink">{label}</p>
      <div className="mt-4 space-y-3">
        <span className="block h-3 w-40 max-w-full rounded bg-slate-100" />
        <span className="block h-16 rounded bg-slate-100/80" />
        <span className="block h-16 rounded bg-slate-100/60" />
      </div>
    </section>
  );
}

function NotebookHomeHeader({
  hasNotebook,
  onCreate,
  onQuestions,
  onRecord,
}: {
  hasNotebook: boolean;
  onCreate: () => void;
  onQuestions: () => void;
  onRecord: () => void;
}) {
  return (
    <section className="rounded-lg border border-line bg-white p-3.5 shadow-[0_8px_24px_rgba(15,15,15,0.03)]">
      <div className="flex flex-wrap items-start justify-between gap-3.5">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-steel">记录</p>
          <h1 className="mt-1 text-xl font-semibold leading-tight text-ink">把学过的内容留下来</h1>
          <p className="mt-2 max-w-2xl text-xs leading-5 text-slate-600">
            聊天答案、错题和复盘都可以回到这里。先看最近记录，需要时再新建记录本或整理错题。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {hasNotebook ? (
            <Button tone="primary" onClick={onRecord}>
              <FileText size={16} />
              写一条记录
            </Button>
          ) : (
            <Button tone="primary" onClick={onCreate}>
              <Plus size={16} />
              新建记录本
            </Button>
          )}
          <Button tone="secondary" onClick={onQuestions}>
            <ListChecks size={16} />
            错题本
          </Button>
          {hasNotebook ? (
            <Button tone="secondary" onClick={onCreate}>
              <Plus size={16} />
              新建记录本
            </Button>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function getSearchParams(search: unknown) {
  if (search && typeof search === "object") {
    const params = new URLSearchParams();
    Object.entries(search as Record<string, unknown>).forEach(([key, value]) => {
      if (value != null) params.set(key, String(value));
    });
    return params;
  }
  if (typeof window === "undefined") return new URLSearchParams();
  return new URLSearchParams(window.location.search);
}
