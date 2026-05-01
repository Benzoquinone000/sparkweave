import { AnimatePresence, motion } from "framer-motion";
import {
  BarChart3,
  BookMarked,
  CheckCircle2,
  ChevronLeft,
  ChevronDown,
  ChevronUp,
  Edit3,
  ExternalLink,
  FileText,
  GraduationCap,
  ListChecks,
  Loader2,
  Plus,
  RefreshCw,
  Save,
  Star,
  Tag,
  Trash2,
  Video,
  X,
} from "lucide-react";
import { useLocation } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";

import { ExternalVideoViewer } from "@/components/results/ExternalVideoViewer";
import { MathAnimatorViewer } from "@/components/results/MathAnimatorViewer";
import { VisualizationViewer } from "@/components/results/VisualizationViewer";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { FieldShell, SelectInput, TextArea, TextInput } from "@/components/ui/Field";
import { MarkdownRenderer } from "@/components/ui/MarkdownRenderer";
import { Metric } from "@/components/ui/Metric";
import { questionDifficultyLabel } from "@/lib/learningLabels";
import type {
  ExternalVideoResult,
  MathAnimatorResult,
  NotebookDetail,
  NotebookRecord,
  QuestionCategory,
  QuestionNotebookEntry,
  QuizQuestion,
  VisualizeResult,
} from "@/lib/types";
import {
  useNotebookDetail,
  useNotebookHealth,
  useNotebookMutations,
  useNotebookStats,
  useNotebooks,
  useQuestionCategories,
  useQuestionEntries,
  useQuestionEntryDetail,
  useQuestionNotebookMutations,
} from "@/hooks/useApiQueries";

type NotebookView = "browse" | "create" | "record" | "questions";

export function NotebookPage() {
  const location = useLocation();
  const notebooks = useNotebooks();
  const stats = useNotebookStats();
  const notebookHealth = useNotebookHealth();
  const mutations = useNotebookMutations();
  const questionEntries = useQuestionEntries();
  const categories = useQuestionCategories();
  const questionMutations = useQuestionNotebookMutations();
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
    <div className="h-full overflow-y-auto px-4 py-4 pb-24 lg:px-5 lg:pb-5">
      <div className="mx-auto max-w-6xl space-y-4">
        <motion.section
          className="dt-page-header"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22, ease: "easeOut" }}
        >
          <p className="dt-page-eyebrow">笔记</p>
          <h1 className="mt-1 text-xl font-semibold text-ink">学习笔记</h1>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-600">
            保存回答、题目和复盘材料，需要时再引用回学习台。
          </p>
        </motion.section>

        <motion.div
          className="flex flex-wrap gap-x-4 gap-y-1.5"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22, delay: 0.04, ease: "easeOut" }}
        >
          <Metric label="笔记本" value={items.length} detail="已创建" icon={<BookMarked size={19} />} />
          <Metric label="记录总数" value={String(stats.data?.total_records ?? 0)} detail={stats.isLoading ? "读取中" : "学习记录"} />
          <Metric
            label="服务健康"
            value={notebookHealth.data?.status ?? (notebookHealth.isError ? "error" : "checking")}
            detail={notebookHealth.data?.service ? String(notebookHealth.data.service) : "笔记服务"}
            icon={<CheckCircle2 size={19} />}
          />
          <Metric label="题目收藏" value={questionEntries.data?.length ?? 0} detail="收藏题目" />
        </motion.div>

        <div ref={notebookSectionRef} className="grid gap-4 lg:grid-cols-[300px_minmax(0,1fr)]">
          <section className="rounded-lg border border-line bg-white p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-base font-semibold text-ink">我的笔记本</h2>
              <Button tone="quiet" className="min-h-8 px-2 text-xs" onClick={() => void notebooks.refetch()}>
                <RefreshCw size={14} />
                刷新
              </Button>
            </div>
            <Button
              tone={view === "create" ? "primary" : "secondary"}
              className="mt-3 w-full justify-center"
              data-testid="notebook-create-toggle"
              onClick={() => setView("create")}
            >
              <Plus size={16} />
              新建笔记本
            </Button>
            <div className="mt-4 space-y-1">
              {items.map((item) => (
                <motion.button
                  key={item.id}
                  type="button"
                  onClick={() => {
                    setSelectedId(item.id);
                    setView("browse");
                  }}
                  className={`dt-interactive w-full rounded-lg border px-3 py-3 text-left transition ${
                    activeNotebookId === item.id && view !== "questions" ? "border-teal-200 bg-teal-50" : "border-transparent bg-white hover:border-teal-200 hover:bg-canvas"
                  }`}
                  whileHover={{ y: -2 }}
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
                <EmptyState icon={<BookMarked size={24} />} title="还没有笔记本" description="先新建一个主题，再把聊天、导学和练习结果沉淀进来。" />
              </div>
            ) : null}
            <div className="mt-4 border-t border-line pt-3">
              <Button
                tone={view === "questions" ? "primary" : "quiet"}
                className="w-full justify-center"
                onClick={() => setView("questions")}
              >
                <ListChecks size={16} />
                题目本
              </Button>
            </div>
          </section>

          <AnimatePresence mode="wait" initial={false}>
            {view === "create" ? (
              <motion.section
                key="create-notebook"
                className="rounded-lg border border-line bg-white p-4"
                initial={{ opacity: 0, x: 14 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                transition={{ duration: 0.2, ease: "easeOut" }}
              >
                <Button tone="quiet" className="mb-4 min-h-8 px-2 text-xs" onClick={() => setView("browse")}>
                  <ChevronLeft size={14} />
                  返回笔记本
                </Button>
                <div>
                  <Badge tone="brand">新建</Badge>
                  <h2 className="mt-3 text-lg font-semibold text-ink">创建一个学习主题</h2>
                  <p className="mt-1 text-sm leading-6 text-slate-500">只需要填写名称。描述可以简单写清楚这本笔记准备用来沉淀什么。</p>
                </div>
                <form className="mt-5 grid gap-3" onSubmit={createNotebook}>
                  <FieldShell label="名称">
                    <TextInput
                      value={newName}
                      onChange={(event) => setNewName(event.target.value)}
                      placeholder="例如 高数错题复盘"
                      data-testid="notebook-create-name"
                    />
                  </FieldShell>
                  <FieldShell label="描述">
                    <TextArea
                      value={newDescription}
                      onChange={(event) => setNewDescription(event.target.value)}
                      placeholder="这本笔记打算沉淀什么？"
                      data-testid="notebook-create-description"
                    />
                  </FieldShell>
                  <Button
                    tone="primary"
                    type="submit"
                    disabled={!newName.trim() || mutations.create.isPending}
                    data-testid="notebook-create-submit"
                  >
                    {mutations.create.isPending ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
                    创建笔记本
                  </Button>
                </form>
              </motion.section>
            ) : null}

            {view === "record" ? (
              <motion.section
                key="manual-record"
                className="rounded-lg border border-line bg-white p-4"
                initial={{ opacity: 0, x: 14 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                transition={{ duration: 0.2, ease: "easeOut" }}
              >
                <Button tone="quiet" className="mb-4 min-h-8 px-2 text-xs" onClick={() => setView("browse")}>
                  <ChevronLeft size={14} />
                  返回笔记本
                </Button>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <Badge tone={activeNotebookId ? "brand" : "neutral"}>{detail.data?.name || "未选择笔记本"}</Badge>
                    <h2 className="mt-3 text-lg font-semibold text-ink">补充一条学习记录</h2>
                    <p className="mt-1 text-sm leading-6 text-slate-500">适合补课堂笔记、错因、复盘结论。写完后会进入当前笔记本。</p>
                  </div>
                </div>
                <form className="mt-5 grid gap-3" onSubmit={addManualRecord}>
                  <FieldShell label="标题">
                    <TextInput
                      value={manualTitle}
                      onChange={(event) => setManualTitle(event.target.value)}
                      placeholder="本次复盘主题"
                      data-testid="notebook-manual-title"
                    />
                  </FieldShell>
                  <FieldShell label="内容">
                    <TextArea
                      value={manualOutput}
                      onChange={(event) => setManualOutput(event.target.value)}
                      placeholder="关键推理、错因、小结..."
                      className="min-h-44"
                      data-testid="notebook-manual-output"
                    />
                  </FieldShell>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      tone="secondary"
                      type="submit"
                      disabled={!activeNotebookId || !manualTitle.trim() || !manualOutput.trim() || mutations.addRecord.isPending}
                      data-testid="notebook-manual-submit"
                    >
                      {mutations.addRecord.isPending ? <Loader2 size={16} className="animate-spin" /> : <FileText size={16} />}
                      直接写入
                    </Button>
                    <Button
                      tone="primary"
                      type="submit"
                      data-action="with-summary"
                      disabled={!activeNotebookId || !manualTitle.trim() || !manualOutput.trim() || mutations.addRecordWithSummary.isPending}
                      data-testid="notebook-manual-summary-submit"
                    >
                      {mutations.addRecordWithSummary.isPending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                      生成摘要并写入
                    </Button>
                  </div>
                  <AnimatePresence>
                    {manualSummaryPreview ? (
                      <motion.p
                        className="rounded-lg border border-teal-200 bg-teal-50 p-3 text-sm leading-6 text-slate-600"
                        data-testid="notebook-summary-preview"
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -8 }}
                        transition={{ duration: 0.18 }}
                      >
                        {manualSummaryPreview}
                      </motion.p>
                    ) : null}
                  </AnimatePresence>
                </form>
              </motion.section>
            ) : null}

            {view === "questions" ? (
              <motion.section
                key="question-notebook"
                ref={questionSectionRef}
                className="rounded-lg border border-line bg-white p-4"
                initial={{ opacity: 0, x: 14 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                transition={{ duration: 0.2, ease: "easeOut" }}
              >
                <Button tone="quiet" className="mb-4 min-h-8 px-2 text-xs" onClick={() => setView("browse")}>
                  <ChevronLeft size={14} />
                  返回笔记本
                </Button>
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <Badge tone="brand">题目本</Badge>
                    <h2 className="mt-3 text-lg font-semibold text-ink">收藏题目与错题复盘</h2>
                    <p className="mt-1 text-sm text-slate-500">集中查看题目、答案、解析和分类。</p>
                  </div>
                  <form className="flex gap-2" onSubmit={createCategory}>
                    <TextInput
                      value={categoryName}
                      onChange={(event) => setCategoryName(event.target.value)}
                      placeholder="新分类"
                      className="min-w-40"
                      data-testid="question-category-create-name"
                    />
                    <Button
                      tone="secondary"
                      type="submit"
                      disabled={!categoryName.trim() || questionMutations.createCategory.isPending}
                      data-testid="question-category-create-submit"
                    >
                      <Tag size={16} />
                      添加
                    </Button>
                  </form>
                </div>

                <CategoryManager
                  categories={categories.data ?? []}
                  renamingCategoryId={renamingCategoryId}
                  categoryDraft={categoryDraft}
                  pending={questionMutations.renameCategory.isPending || questionMutations.deleteCategory.isPending}
                  onStartRename={(category) => {
                    setRenamingCategoryId(category.id);
                    setCategoryDraft(category.name);
                  }}
                  onDraft={setCategoryDraft}
                  onRename={async (categoryId) => {
                    if (!categoryDraft.trim()) return;
                    await questionMutations.renameCategory.mutateAsync({ categoryId, name: categoryDraft.trim() });
                    setRenamingCategoryId(null);
                    setCategoryDraft("");
                  }}
                  onCancelRename={() => {
                    setRenamingCategoryId(null);
                    setCategoryDraft("");
                  }}
                  onDelete={(categoryId) => {
                    if (window.confirm("删除这个分类？")) void questionMutations.deleteCategory.mutateAsync(categoryId);
                  }}
                />

                <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
                  <div className="grid gap-3">
                    <AnimatePresence initial={false}>
                      {(questionEntries.data ?? []).slice(0, 12).map((entry) => (
                        <motion.div
                          key={entry.id}
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -8 }}
                          transition={{ duration: 0.18, ease: "easeOut" }}
                        >
                          <QuestionCard
                            entry={entry}
                            active={activeQuestion?.id === entry.id}
                            pending={questionMutations.updateEntry.isPending || questionMutations.deleteEntry.isPending}
                            onSelect={() => setSelectedQuestionId(entry.id)}
                            onToggleBookmark={() => questionMutations.updateEntry.mutateAsync({ entryId: entry.id, bookmarked: !entry.bookmarked })}
                            onDelete={() => {
                              if (window.confirm("删除这道题？")) void questionMutations.deleteEntry.mutateAsync(entry.id);
                            }}
                          />
                        </motion.div>
                      ))}
                    </AnimatePresence>
                    {!questionEntries.data?.length ? <p className="rounded-lg border border-dashed border-line bg-canvas p-4 text-sm text-slate-500">暂无题目记录。</p> : null}
                  </div>

                  <QuestionDetail
                    entry={activeQuestion}
                    categories={categories.data ?? []}
                    pending={questionMutations.addEntryToCategory.isPending || questionMutations.removeEntryFromCategory.isPending}
                    onAddCategory={(entryId, categoryId) => questionMutations.addEntryToCategory.mutateAsync({ entryId, categoryId })}
                    onRemoveCategory={(entryId, categoryId) => questionMutations.removeEntryFromCategory.mutateAsync({ entryId, categoryId })}
                  />
                </div>

                <section className="mt-5 rounded-lg border border-line bg-canvas p-3">
                  <QuickQuestionPanel
                    value={quickQuestion}
                    status={quickQuestionStatus}
                    pending={questionMutations.upsertEntry.isPending || questionMutations.lookupEntry.isPending}
                    onChange={setQuickQuestion}
                    onLookup={() => void lookupQuickQuestion()}
                    onSubmit={upsertQuickQuestion}
                  />
                </section>
              </motion.section>
            ) : null}

            {view === "browse" ? (
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
                    <Badge tone="brand">当前笔记本</Badge>
                    <h2 className="mt-3 text-lg font-semibold text-ink">{detail.data?.name || "笔记本详情"}</h2>
                    <p className="mt-1 text-sm text-slate-500">{detail.data?.description || "选择一个笔记本查看记录。"}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      tone="secondary"
                      data-testid="notebook-manual-toggle"
                      onClick={() => setView("record")}
                      disabled={!activeNotebookId}
                    >
                      <Edit3 size={16} />
                      手动记录
                    </Button>
                    <Button tone="secondary" onClick={() => setView("questions")}>
                      <ListChecks size={16} />
                      题目本
                    </Button>
                    {activeNotebookId ? (
                      <Button
                        tone="danger"
                        data-testid="notebook-delete"
                        onClick={() => {
                          if (window.confirm("删除这个笔记本？")) void mutations.remove.mutateAsync(activeNotebookId);
                        }}
                        disabled={mutations.remove.isPending}
                      >
                        <Trash2 size={16} />
                        删除
                      </Button>
                    ) : null}
                  </div>
                </div>
                {activeNotebookId && detail.data ? (
                  <NotebookMetaEditor
                    key={detail.data.id}
                    notebook={detail.data}
                    pending={mutations.update.isPending}
                    onSave={(payload) => mutations.update.mutateAsync({ notebookId: activeNotebookId, ...payload })}
                  />
                ) : null}
                <div className="mt-5 grid gap-3">
                  <AnimatePresence initial={false}>
                    {(detail.data?.records ?? []).slice(0, 12).map((record) => (
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
                          onEdit={() => setEditingRecord(record)}
                          onDelete={() => {
                            const recordId = String(record.id || record.record_id || "");
                            if (activeNotebookId && recordId && window.confirm("删除这条记录？")) {
                              void mutations.deleteRecord.mutateAsync({ notebookId: activeNotebookId, recordId });
                            }
                          }}
                        />
                      </motion.div>
                    ))}
                  </AnimatePresence>
                  {activeNotebookId && !detail.data?.records?.length ? (
                    <EmptyState icon={<FileText size={24} />} title="暂无记录" description="从聊天页保存，或点“手动记录”补充一条复盘。" />
                  ) : null}
                </div>
              </motion.section>
            ) : null}
          </AnimatePresence>
        </div>

        {editingRecord && activeNotebookId ? (
          <RecordEditor
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

function sessionTargetForRecord(record: NotebookRecord) {
  const sessionId = typeof record.metadata?.session_id === "string" ? record.metadata.session_id : "";
  if (!sessionId) return null;
  const type = record.record_type || record.type;
  return type === "guided_learning" ? `/guide?session=${encodeURIComponent(sessionId)}` : `/chat/${encodeURIComponent(sessionId)}`;
}

function NotebookMetaEditor({
  notebook,
  pending,
  onSave,
}: {
  notebook: NotebookDetail;
  pending: boolean;
  onSave: (payload: { name: string; description: string; color: string; icon: string }) => Promise<unknown>;
}) {
  const [name, setName] = useState(notebook.name || "");
  const [description, setDescription] = useState(notebook.description || "");
  return (
    <form
      className="mt-4 border-t border-line pt-4"
      onSubmit={(event) => {
        event.preventDefault();
        void onSave({
          name: name.trim(),
          description: description.trim(),
          color: notebook.color || "#0F766E",
          icon: notebook.icon || "book",
        });
      }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-ink">笔记本信息</h3>
          <p className="mt-1 text-sm text-slate-500">更新名称和描述后，列表、详情和保存入口会同步使用新信息。</p>
        </div>
        <Button tone="primary" type="submit" disabled={!name.trim() || pending} data-testid="notebook-meta-save">
          {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
          保存信息
        </Button>
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-[240px_minmax(0,1fr)]">
        <FieldShell label="名称">
          <TextInput value={name} onChange={(event) => setName(event.target.value)} data-testid="notebook-meta-name" />
        </FieldShell>
        <FieldShell label="描述">
          <TextInput value={description} onChange={(event) => setDescription(event.target.value)} data-testid="notebook-meta-description" />
        </FieldShell>
      </div>
    </form>
  );
}

function RecordCard({
  record,
  active,
  onEdit,
  onDelete,
}: {
  record: NotebookRecord;
  active: boolean;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const sessionTarget = sessionTargetForRecord(record);
  const asset = getRecordAsset(record);
  const [expanded, setExpanded] = useState(Boolean(active && asset.hasPreview));
  const recordKey = String(record.id || record.record_id || "");

  return (
    <article
      className={`dt-interactive rounded-lg border px-4 py-3 ${active ? "border-teal-200 bg-teal-50" : "border-line bg-white hover:border-teal-200"}`}
      data-testid={recordKey ? `notebook-record-${recordKey}` : undefined}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="brand">{record.record_type}</Badge>
        {asset.kind ? <Badge tone="neutral">{asset.kind}</Badge> : null}
        {record.kb_name ? <Badge tone="neutral">{record.kb_name}</Badge> : null}
        <div className="ml-auto flex gap-2">
          {sessionTarget ? (
            <Button tone="quiet" className="min-h-8 px-2 text-xs" onClick={() => window.location.assign(sessionTarget)}>
              <ExternalLink size={14} />
              打开会话
            </Button>
          ) : null}
          {asset.hasPreview ? (
            <Button tone="quiet" className="min-h-8 px-2 text-xs" onClick={() => setExpanded((value) => !value)}>
              {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              {expanded ? "收起资产" : "预览资产"}
            </Button>
          ) : null}
          <Button
            tone="quiet"
            className="min-h-8 px-2 text-xs"
            onClick={onEdit}
            data-testid={recordKey ? `notebook-record-edit-${recordKey}` : undefined}
          >
            <Edit3 size={14} />
            编辑
          </Button>
          <Button
            tone="danger"
            className="min-h-8 px-2 text-xs"
            onClick={onDelete}
            data-testid={recordKey ? `notebook-record-delete-${recordKey}` : undefined}
          >
            <Trash2 size={14} />
            删除
          </Button>
        </div>
      </div>
      <h3 className="mt-3 font-semibold text-ink">{record.title}</h3>
      <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-600">{record.summary || record.output || "暂无内容"}</p>
      <AnimatePresence initial={false}>
        {expanded && asset.hasPreview ? (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
          >
            <RecordAssetPreview record={record} asset={asset} />
          </motion.div>
        ) : null}
      </AnimatePresence>
    </article>
  );
}

function RecordAssetPreview({ record, asset }: { record: NotebookRecord; asset: ReturnType<typeof getRecordAsset> }) {
  if (asset.visualize) {
    return (
      <div className="mt-4 border-t border-line pt-4">
        <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
          <BarChart3 size={16} className="text-brand-blue" />
          可视化资产预览
        </h4>
        <VisualizationViewer result={asset.visualize} />
      </div>
    );
  }

  if (asset.quizQuestions.length) {
    return (
      <div className="mt-4 border-t border-line pt-4">
        <h4 className="flex items-center gap-2 text-sm font-semibold text-ink">
          <ListChecks size={16} className="text-brand-teal" />
          题目资产预览
        </h4>
        <div className="mt-3 grid gap-3">
          {asset.quizQuestions.map((question, index) => (
            <div key={`${question.question_id ?? index}-${question.question}`} className="rounded-lg bg-canvas p-3">
              <p className="text-sm font-semibold leading-6 text-ink">
                {index + 1}. {question.question}
              </p>
              {question.options && Object.keys(question.options).length ? (
                <div className="mt-2 grid gap-1">
                  {Object.entries(question.options).map(([key, value]) => (
                    <p key={key} className="text-sm leading-6 text-slate-600">
                      <span className="font-semibold text-brand-teal">{key}.</span> {value}
                    </p>
                  ))}
                </div>
              ) : null}
              <p className="mt-2 text-sm leading-6 text-slate-600">
                <span className="font-semibold text-ink">参考答案：</span>
                {question.correct_answer || "未提供"}
              </p>
              {question.explanation ? <p className="mt-1 text-sm leading-6 text-slate-500">{question.explanation}</p> : null}
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (asset.mathAnimator) {
    return (
      <div className="mt-4 border-t border-line pt-4">
        <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
          <Video size={16} className="text-brand-blue" />
          数学动画资产预览
        </h4>
        <MathAnimatorViewer result={asset.mathAnimator} />
      </div>
    );
  }

  if (asset.externalVideo) {
    return (
      <div className="mt-4 border-t border-line pt-4">
        <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
          <Video size={16} className="text-brand-blue" />
          精选视频资产预览
        </h4>
        <ExternalVideoViewer result={asset.externalVideo} />
      </div>
    );
  }

  if (asset.guideHtml) {
    return (
      <div className="mt-4 border-t border-line pt-4">
        <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
          <GraduationCap size={16} className="text-brand-teal" />
          导学页面预览
        </h4>
        <div className="h-96 overflow-hidden rounded-lg border border-line bg-canvas">
          <iframe
            title={`${record.title} 导学页面`}
            data-testid="guide-asset-preview"
            srcDoc={asset.guideHtml}
            sandbox=""
            className="h-full w-full bg-white"
          />
        </div>
      </div>
    );
  }

  if (record.output) {
    return (
      <div className="markdown-body mt-4 border-t border-line pt-4 text-sm leading-6 text-slate-700">
        <MarkdownRenderer>{record.output}</MarkdownRenderer>
      </div>
    );
  }

  return null;
}

function getRecordAsset(record: NotebookRecord) {
  const metadata = asRecord(record.metadata);
  const visualize = isVisualizeResult(metadata?.visualize) ? metadata.visualize : null;
  const mathAnimator = isMathAnimatorResult(metadata?.math_animator) ? metadata.math_animator : null;
  const externalVideo = isExternalVideoResult(metadata?.external_video) ? metadata.external_video : null;
  const quizQuestions = getQuizQuestions(metadata?.quiz);
  const guideHtml = getGuideHtml(record, metadata);
  const kind = typeof metadata?.asset_kind === "string" ? metadata.asset_kind : "";
  return {
    kind,
    visualize,
    mathAnimator,
    externalVideo,
    quizQuestions,
    guideHtml,
    hasPreview: Boolean(visualize || mathAnimator || externalVideo || quizQuestions.length || guideHtml || record.output),
  };
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function isVisualizeResult(value: unknown): value is VisualizeResult {
  const record = asRecord(value);
  const code = asRecord(record?.code);
  return Boolean(
    record &&
      (record.render_type === "svg" || record.render_type === "chartjs" || record.render_type === "mermaid") &&
      code &&
      typeof code.content === "string",
  );
}

function isMathAnimatorResult(value: unknown): value is MathAnimatorResult {
  const record = asRecord(value);
  if (!record) return false;
  return Array.isArray(record.artifacts) || Boolean(record.code) || typeof record.response === "string";
}

function isExternalVideoResult(value: unknown): value is ExternalVideoResult {
  const record = asRecord(value);
  return Boolean(record && Array.isArray(record.videos));
}

function getQuizQuestions(value: unknown): QuizQuestion[] {
  const quiz = asRecord(value);
  const questions = Array.isArray(quiz?.questions) ? quiz.questions : [];
  return questions.flatMap((item) => {
    const record = asRecord(item);
    if (!record || typeof record.question !== "string") return [];
    return [
      {
        question_id: typeof record.question_id === "string" ? record.question_id : undefined,
        question: record.question,
        question_type: typeof record.question_type === "string" ? record.question_type : "written",
        options: normalizeOptions(record.options),
        correct_answer: typeof record.correct_answer === "string" ? record.correct_answer : String(record.correct_answer ?? ""),
        explanation: typeof record.explanation === "string" ? record.explanation : "",
        difficulty: typeof record.difficulty === "string" ? record.difficulty : "",
        concentration: typeof record.concentration === "string" ? record.concentration : "",
        knowledge_context: typeof record.knowledge_context === "string" ? record.knowledge_context : "",
      },
    ];
  });
}

function normalizeOptions(value: unknown) {
  const record = asRecord(value);
  if (!record) return undefined;
  return Object.fromEntries(Object.entries(record).map(([key, option]) => [key, String(option)]));
}

function getGuideHtml(record: NotebookRecord, metadata: Record<string, unknown> | null) {
  if (record.record_type !== "guided_learning") return "";
  if (typeof metadata?.guide_html === "string" && metadata.guide_html.trim()) return metadata.guide_html;
  if (metadata?.output_type === "html" && record.output?.trim()) return record.output;
  const output = record.output?.trim() ?? "";
  return output.startsWith("<") && /<\/[a-z][\s\S]*>/i.test(output) ? output : "";
}

function RecordEditor({
  record,
  pending,
  onCancel,
  onSave,
}: {
  record: NotebookRecord;
  pending: boolean;
  onCancel: () => void;
  onSave: (payload: { title: string; summary: string; user_query: string; output: string }) => Promise<void>;
}) {
  const [title, setTitle] = useState(record.title);
  const [summary, setSummary] = useState(record.summary || "");
  const [userQuery, setUserQuery] = useState(record.user_query || "");
  const [output, setOutput] = useState(record.output || "");
  return (
    <section className="rounded-lg border border-line bg-white p-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-ink">编辑记录</h2>
        <Button tone="quiet" onClick={onCancel}>
          <X size={16} />
          关闭
        </Button>
      </div>
      <form
        className="mt-4 grid gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          void onSave({ title, summary, user_query: userQuery, output });
        }}
      >
        <FieldShell label="标题">
          <TextInput value={title} onChange={(event) => setTitle(event.target.value)} data-testid="record-editor-title" />
        </FieldShell>
        <FieldShell label="摘要">
          <TextArea value={summary} onChange={(event) => setSummary(event.target.value)} data-testid="record-editor-summary" />
        </FieldShell>
        <FieldShell label="用户问题">
          <TextArea value={userQuery} onChange={(event) => setUserQuery(event.target.value)} data-testid="record-editor-user-query" />
        </FieldShell>
        <FieldShell label="输出">
          <TextArea
            value={output}
            onChange={(event) => setOutput(event.target.value)}
            className="min-h-56"
            data-testid="record-editor-output"
          />
        </FieldShell>
        <Button tone="primary" type="submit" disabled={!title.trim() || pending} data-testid="record-editor-save">
          {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
          保存记录
        </Button>
      </form>
    </section>
  );
}

function CategoryManager({
  categories,
  renamingCategoryId,
  categoryDraft,
  pending,
  onStartRename,
  onDraft,
  onRename,
  onCancelRename,
  onDelete,
}: {
  categories: QuestionCategory[];
  renamingCategoryId: number | null;
  categoryDraft: string;
  pending: boolean;
  onStartRename: (category: QuestionCategory) => void;
  onDraft: (value: string) => void;
  onRename: (categoryId: number) => Promise<void>;
  onCancelRename: () => void;
  onDelete: (categoryId: number) => void;
}) {
  return (
    <div className="mt-5 flex flex-wrap gap-2">
      {categories.map((category) =>
        renamingCategoryId === category.id ? (
          <form
            key={category.id}
            className="dt-interactive flex items-center gap-2 rounded-lg border border-line bg-white p-2"
            onSubmit={(event) => {
              event.preventDefault();
              void onRename(category.id);
            }}
          >
            <TextInput
              value={categoryDraft}
              onChange={(event) => onDraft(event.target.value)}
              className="h-9 w-36"
              data-testid={`question-category-rename-input-${category.id}`}
            />
            <Button
              tone="primary"
              type="submit"
              className="min-h-9 px-2 text-xs"
              disabled={pending || !categoryDraft.trim()}
              data-testid={`question-category-rename-save-${category.id}`}
            >
              保存
            </Button>
            <Button tone="quiet" className="min-h-9 px-2 text-xs" onClick={onCancelRename}>
              取消
            </Button>
          </form>
        ) : (
          <div key={category.id} className="dt-interactive flex items-center gap-2 rounded-lg border border-line bg-white px-3 py-2 text-sm hover:border-teal-200">
            <span className="font-medium text-ink">{category.name}</span>
            <Badge tone="neutral">{category.entry_count ?? 0}</Badge>
            <button
              type="button"
              className="text-slate-500 hover:text-brand-teal"
              onClick={() => onStartRename(category)}
              data-testid={`question-category-rename-${category.id}`}
            >
              改名
            </button>
            <button
              type="button"
              className="text-slate-500 hover:text-brand-red"
              onClick={() => onDelete(category.id)}
              data-testid={`question-category-delete-${category.id}`}
            >
              删除
            </button>
          </div>
        ),
      )}
    </div>
  );
}

function QuickQuestionPanel({
  value,
  status,
  pending,
  onChange,
  onLookup,
  onSubmit,
}: {
  value: {
    sessionId: string;
    questionId: string;
    question: string;
    correctAnswer: string;
    explanation: string;
    difficulty: string;
  };
  status: string;
  pending: boolean;
  onChange: (value: {
    sessionId: string;
    questionId: string;
    question: string;
    correctAnswer: string;
    explanation: string;
    difficulty: string;
  }) => void;
  onLookup: () => void;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
}) {
  const patch = (next: Partial<typeof value>) => onChange({ ...value, ...next });
  return (
    <form className="mt-4 border-t border-line pt-4" onSubmit={onSubmit}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-ink">题目快录</h3>
          <p className="mt-1 text-sm leading-6 text-slate-500">
            如果你从聊天或题目生成结果里复制了记录编号，可以在这里找回或补录单题。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            tone="secondary"
            type="button"
            onClick={onLookup}
            disabled={pending || !value.sessionId.trim() || !value.questionId.trim()}
            data-testid="question-lookup-submit"
          >
            {pending ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
            查找
          </Button>
          <Button
            tone="primary"
            type="submit"
            disabled={pending || !value.sessionId.trim() || !value.questionId.trim() || !value.question.trim()}
            data-testid="question-upsert-submit"
          >
            {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            写入题目
          </Button>
        </div>
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-3">
        <FieldShell label="答题记录">
          <TextInput value={value.sessionId} onChange={(event) => patch({ sessionId: event.target.value })} data-testid="question-upsert-session" />
        </FieldShell>
        <FieldShell label="题目编号">
          <TextInput value={value.questionId} onChange={(event) => patch({ questionId: event.target.value })} data-testid="question-upsert-id" />
        </FieldShell>
        <FieldShell label="难度">
          <SelectInput value={value.difficulty} onChange={(event) => patch({ difficulty: event.target.value })} data-testid="question-upsert-difficulty">
            <option value="easy">基础</option>
            <option value="medium">中等</option>
            <option value="hard">挑战</option>
          </SelectInput>
        </FieldShell>
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <FieldShell label="题干">
          <TextArea value={value.question} onChange={(event) => patch({ question: event.target.value })} data-testid="question-upsert-question" />
        </FieldShell>
        <div className="grid gap-3">
          <FieldShell label="参考答案">
            <TextInput value={value.correctAnswer} onChange={(event) => patch({ correctAnswer: event.target.value })} data-testid="question-upsert-answer" />
          </FieldShell>
          <FieldShell label="解析">
            <TextArea value={value.explanation} onChange={(event) => patch({ explanation: event.target.value })} data-testid="question-upsert-explanation" />
          </FieldShell>
        </div>
      </div>
      {status ? <p className="mt-3 rounded-lg border border-line bg-white p-3 text-sm text-slate-600">{status}</p> : null}
    </form>
  );
}

function QuestionCard({
  entry,
  active,
  pending,
  onSelect,
  onToggleBookmark,
  onDelete,
}: {
  entry: QuestionNotebookEntry;
  active: boolean;
  pending: boolean;
  onSelect: () => void;
  onToggleBookmark: () => Promise<unknown>;
  onDelete: () => void;
}) {
  return (
    <article
      className={`dt-interactive rounded-lg border px-4 py-3 ${active ? "border-teal-200 bg-teal-50" : "border-line bg-white hover:border-teal-200"}`}
      data-testid={`question-entry-${entry.id}`}
    >
      <button type="button" className="w-full text-left" onClick={onSelect} data-testid={`question-entry-select-${entry.id}`}>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={entry.bookmarked ? "brand" : "neutral"}>{entry.bookmarked ? "已收藏" : "题目"}</Badge>
          <Badge tone={entry.is_correct ? "success" : "warning"}>{entry.is_correct ? "正确" : "待复盘"}</Badge>
          {entry.difficulty ? <Badge tone="neutral">{questionDifficultyLabel(entry.difficulty)}</Badge> : null}
        </div>
        <h3 className="mt-3 line-clamp-2 font-semibold text-ink">{entry.question}</h3>
        <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-600">{entry.explanation || entry.correct_answer || "暂无解析"}</p>
      </button>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button
          tone="secondary"
          className="min-h-9 text-xs"
          onClick={() => void onToggleBookmark()}
          disabled={pending}
          data-testid={`question-entry-bookmark-${entry.id}`}
        >
          <Star size={14} />
          {entry.bookmarked ? "取消收藏" : "收藏"}
        </Button>
        <Button
          tone="danger"
          className="min-h-9 text-xs"
          onClick={onDelete}
          disabled={pending}
          data-testid={`question-entry-delete-${entry.id}`}
        >
          <Trash2 size={14} />
          删除
        </Button>
      </div>
    </article>
  );
}

function QuestionDetail({
  entry,
  categories,
  pending,
  onAddCategory,
  onRemoveCategory,
}: {
  entry?: QuestionNotebookEntry;
  categories: QuestionCategory[];
  pending: boolean;
  onAddCategory: (entryId: number, categoryId: number) => Promise<unknown>;
  onRemoveCategory: (entryId: number, categoryId: number) => Promise<unknown>;
}) {
  const [categoryId, setCategoryId] = useState("");
  if (!entry) {
    return <div className="rounded-lg border border-dashed border-line bg-canvas p-4 text-sm text-slate-500">选择一道题查看详情。</div>;
  }
  const linkedIds = new Set((entry.categories ?? []).map((item) => item.id));
  return (
    <aside className="rounded-lg border border-line bg-white p-3">
      <Badge tone="brand">题目详情</Badge>
      <h3 className="mt-3 font-semibold text-ink">{entry.question}</h3>
      {entry.options && Object.keys(entry.options).length ? (
        <div className="mt-4 grid gap-2">
          {Object.entries(entry.options).map(([key, value]) => (
            <p key={key} className="rounded-lg bg-canvas p-3 text-sm">
              <span className="font-semibold text-brand-teal">{key}.</span> {value}
            </p>
          ))}
        </div>
      ) : null}
      <div className="mt-4 grid gap-3 text-sm leading-6 text-slate-700">
        <p><span className="font-semibold text-ink">正确答案：</span>{entry.correct_answer || "未记录"}</p>
        <p><span className="font-semibold text-ink">我的答案：</span>{entry.user_answer || "未记录"}</p>
        <p><span className="font-semibold text-ink">解析：</span>{entry.explanation || "暂无解析"}</p>
      </div>
      <div className="mt-5 flex flex-wrap gap-2">
        {entry.session_id ? (
          <Button tone="secondary" className="min-h-9 text-xs" onClick={() => window.location.assign(`/chat/${encodeURIComponent(entry.session_id)}`)}>
            <ExternalLink size={14} />
            原会话
          </Button>
        ) : null}
        {entry.followup_session_id ? (
          <Button
            tone="secondary"
            className="min-h-9 text-xs"
            onClick={() => window.location.assign(`/chat/${encodeURIComponent(entry.followup_session_id || "")}`)}
          >
            <ExternalLink size={14} />
            追问会话
          </Button>
        ) : null}
      </div>
      <div className="mt-5">
        <p className="text-sm font-semibold text-ink">分类</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {(entry.categories ?? []).map((category) => (
            <button
              key={category.id}
              type="button"
              onClick={() => void onRemoveCategory(entry.id, category.id)}
              disabled={pending}
              data-testid={`question-detail-category-remove-${category.id}`}
              className="rounded-md border border-line bg-white px-2 py-1 text-xs text-slate-600 hover:border-red-200 hover:text-brand-red"
            >
              {category.name} ×
            </button>
          ))}
          {!entry.categories?.length ? <span className="text-sm text-slate-500">未分类</span> : null}
        </div>
        <div className="mt-3 grid grid-cols-[1fr_auto] gap-2">
          <SelectInput
            value={categoryId}
            onChange={(event) => setCategoryId(event.target.value)}
            data-testid="question-detail-category-select"
          >
            <option value="">选择分类</option>
            {categories.filter((category) => !linkedIds.has(category.id)).map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </SelectInput>
          <Button
            tone="secondary"
            disabled={!categoryId || pending}
            data-testid="question-detail-category-add"
            onClick={async () => {
              await onAddCategory(entry.id, Number(categoryId));
              setCategoryId("");
            }}
          >
            添加
          </Button>
        </div>
      </div>
    </aside>
  );
}
