import {
  BookOpen,
  Brain,
  BarChart3,
  CalendarDays,
  ChevronLeft,
  CheckCircle2,
  Clock3,
  Compass,
  GraduationCap,
  ListChecks,
  Lightbulb,
  Loader2,
  Map,
  MessageCircle,
  PlayCircle,
  RefreshCw,
  Sparkles,
  Target,
  Trash2,
  Video,
  X,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import type { FormEvent, ReactNode } from "react";

import { MathAnimatorViewer } from "@/components/results/MathAnimatorViewer";
import { VisualizationViewer } from "@/components/results/VisualizationViewer";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FieldShell, SelectInput, TextArea, TextInput } from "@/components/ui/Field";
import { MarkdownRenderer } from "@/components/ui/MarkdownRenderer";
import { openGuideV2ResourceJobEvents } from "@/lib/api";
import {
  useGuideV2Evaluation,
  useGuideV2CoachBriefing,
  useGuideV2CoursePackage,
  useGuideV2Diagnostic,
  useGuideV2Health,
  useGuideV2LearnerMemory,
  useGuideV2LearningTimeline,
  useGuideV2LearningReport,
  useGuideV2MistakeReview,
  useGuideV2Mutations,
  useGuideV2ProfileDialogue,
  useGuideV2ResourceRecommendations,
  useGuideV2SessionDetail,
  useGuideV2Sessions,
  useGuideV2StudyPlan,
  useGuideV2Templates,
  useNotebookDetail,
  useNotebooks,
} from "@/hooks/useApiQueries";
import type {
  GuideV2Artifact,
  GuideV2CoachBriefing,
  GuideV2CoursePackage,
  GuideV2Diagnostic,
  GuideV2DiagnosticAnswer,
  GuideV2DiagnosticQuestion,
  GuideV2DiagnosticValue,
  GuideV2CourseTemplate,
  GuideV2Evaluation,
  GuideV2LearnerMemory,
  GuideV2LearningFeedback,
  GuideV2LearningReport,
  GuideV2LearningTimeline,
  GuideV2MistakeReview,
  GuideV2PlanEvent,
  GuideV2ProfileDialogue,
  GuideV2ResourceRecommendation,
  GuideV2ResourceType,
  GuideV2StudyPlan,
  GuideV2Task,
  MathAnimatorResult,
  NotebookRecord,
  NotebookReference,
  QuizResultItem,
  VisualizeResult,
} from "@/lib/types";

type GuideSubPage = "main" | "setup" | "habits" | "completeTask" | "routeMap";

const preferenceOptions = [
  { id: "visual", label: "图解" },
  { id: "video", label: "短视频" },
  { id: "practice", label: "练习" },
  { id: "example", label: "例题" },
];

const mistakeTypeOptions = [
  { id: "概念边界不清", label: "概念边界" },
  { id: "公式或步骤断裂", label: "公式步骤" },
  { id: "计算细节错误", label: "计算细节" },
  { id: "不会迁移应用", label: "迁移应用" },
  { id: "题意理解偏差", label: "题意偏差" },
  { id: "表达不完整", label: "表达不完整" },
];

const levelOptions = [
  { value: "", label: "自动判断" },
  { value: "beginner", label: "刚入门" },
  { value: "intermediate", label: "学过但不稳" },
  { value: "advanced", label: "想深入提升" },
];

const horizonOptions = [
  { value: "", label: "自动安排" },
  { value: "today", label: "今天完成" },
  { value: "week", label: "一周计划" },
  { value: "short", label: "短期补强" },
];

export function GuidePage() {
  const sessions = useGuideV2Sessions();
  const health = useGuideV2Health();
  const templates = useGuideV2Templates();
  const learnerMemory = useGuideV2LearnerMemory();
  const mutations = useGuideV2Mutations();
  const notebooks = useNotebooks();

  const [goal, setGoal] = useState("我想用 30 分钟理解梯度下降的直观意义，并做几道练习确认掌握。");
  const [courseTemplateId, setCourseTemplateId] = useState("");
  const [level, setLevel] = useState("");
  const [horizon, setHorizon] = useState("");
  const [timeBudget, setTimeBudget] = useState("30");
  const [preferences, setPreferences] = useState<string[]>(["visual", "practice"]);
  const [weakPoints, setWeakPoints] = useState("");
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [referenceNotebookId, setReferenceNotebookId] = useState("");
  const [selectedRecordIds, setSelectedRecordIds] = useState<string[]>([]);
  const [reflection, setReflection] = useState("");
  const [score, setScore] = useState("0.85");
  const [mistakeTypes, setMistakeTypes] = useState<string[]>([]);
  const [resourcePrompt, setResourcePrompt] = useState("");
  const [generatingType, setGeneratingType] = useState<GuideV2ResourceType | null>(null);
  const [resourceJobId, setResourceJobId] = useState<string | null>(null);
  const [saveNotebookId, setSaveNotebookId] = useState("");
  const [saveMessage, setSaveMessage] = useState("");
  const [focusMode, setFocusMode] = useState(false);
  const [supportOpen, setSupportOpen] = useState(false);
  const [learningFeedback, setLearningFeedback] = useState<GuideV2LearningFeedback | null>(null);
  const [guideSubPage, setGuideSubPage] = useState<GuideSubPage>("main");

  const referenceNotebook = useNotebookDetail(referenceNotebookId || null);
  const courseTemplates = templates.data ?? [];
  const selectedTemplate = courseTemplates.find((item) => item.id === courseTemplateId) ?? null;
  const activeSessionId = selectedSessionId || sessions.data?.[0]?.session_id || null;
  const detail = useGuideV2SessionDetail(activeSessionId);
  const evaluation = useGuideV2Evaluation(activeSessionId);
  const studyPlan = useGuideV2StudyPlan(activeSessionId);
  const learningTimeline = useGuideV2LearningTimeline(activeSessionId);
  const coachBriefing = useGuideV2CoachBriefing(activeSessionId);
  const mistakeReview = useGuideV2MistakeReview(activeSessionId);
  const diagnostic = useGuideV2Diagnostic(activeSessionId);
  const profileDialogue = useGuideV2ProfileDialogue(activeSessionId);
  const learningReport = useGuideV2LearningReport(activeSessionId);
  const coursePackage = useGuideV2CoursePackage(activeSessionId);
  const resourceRecommendations = useGuideV2ResourceRecommendations(activeSessionId);
  const session = detail.data ?? null;
  const nodes = useMemo(() => session?.course_map?.nodes ?? [], [session?.course_map?.nodes]);
  const tasks = useMemo(() => session?.tasks ?? [], [session?.tasks]);
  const courseMetadata = asRecord(session?.course_map?.metadata) ?? {};
  const currentTask = session?.current_task ?? tasks.find((task) => task.status !== "completed" && task.status !== "skipped") ?? null;
  const profile = session?.profile ?? {};
  const recommendations = session?.recommendations ?? [];
  const planEvents = session?.plan_events ?? [];
  const referenceRecords = useMemo(
    () => (referenceNotebook.data?.records ?? []).slice(0, 6),
    [referenceNotebook.data?.records],
  );
  const currentArtifacts = useMemo(
    () => (currentTask?.artifact_refs ?? []).filter((artifact) => !isResearchResourceType(String(artifact.type))),
    [currentTask?.artifact_refs],
  );
  const diagnosticDone = diagnostic.data?.status === "completed";
  const guideStage = !session ? "create" : !diagnosticDone ? "diagnostic" : learningFeedback ? "feedback" : currentTask ? "learn" : "complete";
  const journeySteps = [
    { id: "create", label: "定目标", helper: "告诉系统你要学什么" },
    { id: "diagnostic", label: "校准起点", helper: "用前测确定先从哪里开始" },
    { id: "learn", label: "专注当前步", helper: "看资源、做练习、交证据" },
    { id: "feedback", label: "反馈调整", helper: "根据表现进入下一步" },
  ];
  const activeStepIndex = Math.max(
    0,
    journeySteps.findIndex((item) => item.id === (guideStage === "complete" ? "feedback" : guideStage)),
  );
  const primaryActionLabel =
    guideStage === "create"
      ? "先创建一条路线"
      : guideStage === "diagnostic"
        ? "先完成前测"
        : guideStage === "feedback"
          ? "看反馈并继续下一步"
          : guideStage === "complete"
            ? "这条路线已经完成"
            : "完成当前任务";
  const stageMessage =
    guideStage === "create"
      ? "先不用看复杂面板，只要写下目标和时间，我会把它拆成能执行的学习路线。"
      : guideStage === "diagnostic"
        ? "路线已经有了，先用几道问题校准起点，后面的任务才不会太难或太浅。"
        : guideStage === "feedback"
          ? "刚刚的学习证据已经记录，先看反馈，再决定继续、补救还是复测。"
          : guideStage === "complete"
            ? "这条路线已经走完，可以查看报告、导出课程包，或者开启新的目标。"
            : "现在只需要盯住这一件事：完成当前任务，并留下能被系统判断的学习证据。";

  useEffect(() => {
    if (!activeSessionId && focusMode) {
      setFocusMode(false);
    }
  }, [activeSessionId, focusMode]);

  useEffect(() => {
    setGuideSubPage("main");
  }, [activeSessionId, guideStage]);

  const selectCourseTemplate = (templateId: string) => {
    setCourseTemplateId(templateId);
    const template = courseTemplates.find((item) => item.id === templateId);
    if (!template) return;
    if (template.default_goal) setGoal(template.default_goal);
    if (template.default_time_budget_minutes) setTimeBudget(String(template.default_time_budget_minutes));
    if (template.default_preferences?.length) setPreferences(template.default_preferences);
    if (!level && template.level) setLevel(template.level);
    if (!horizon && template.suggested_weeks && template.suggested_weeks > 1) setHorizon("week");
  };

  const busy =
    mutations.create.isPending ||
    mutations.completeTask.isPending ||
    mutations.submitDiagnostic.isPending ||
    mutations.submitProfileDialogue.isPending ||
    mutations.refreshRecommendations.isPending ||
    mutations.startResourceJob.isPending ||
    mutations.remove.isPending;

  const notebookReferences = useMemo<NotebookReference[]>(() => {
    if (!referenceNotebookId || !selectedRecordIds.length) return [];
    return [{ notebook_id: referenceNotebookId, record_ids: selectedRecordIds }];
  }, [referenceNotebookId, selectedRecordIds]);

  useEffect(() => {
    if (!saveNotebookId && notebooks.data?.[0]?.id) {
      setSaveNotebookId(notebooks.data[0].id);
    }
  }, [notebooks.data, saveNotebookId]);

  useEffect(() => {
    setMistakeTypes([]);
  }, [currentTask?.task_id]);

  const createSession = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!goal.trim()) return;
    const created = await mutations.create.mutateAsync({
      goal: goal.trim(),
      level,
      horizon,
      timeBudgetMinutes: Number(timeBudget) || null,
      courseTemplateId,
      preferences,
      weakPoints: splitLines(weakPoints),
      notebookReferences,
    });
    if (created.session?.session_id) {
      setSelectedSessionId(created.session.session_id);
      setReflection("");
      setResourcePrompt("");
      setSaveMessage("");
      setLearningFeedback(null);
    }
  };

  const completeCurrentTask = async () => {
    if (!activeSessionId || !currentTask) return;
    const result = await mutations.completeTask.mutateAsync({
      sessionId: activeSessionId,
      taskId: currentTask.task_id,
      score: Number(score),
      reflection: reflection.trim(),
      mistakeTypes,
    });
    setLearningFeedback(result.learning_feedback ?? null);
    setSaveMessage(result.learning_feedback?.summary || "学习证据已记录。");
    setReflection("");
    setMistakeTypes([]);
  };

  const generateResource = async (
    type: GuideV2ResourceType,
    targetTaskId = currentTask?.task_id || "",
    promptOverride = resourcePrompt.trim(),
  ) => {
    if (!activeSessionId || !targetTaskId) return;
    setGeneratingType(type);
    try {
      const job = await mutations.startResourceJob.mutateAsync({
        sessionId: activeSessionId,
        taskId: targetTaskId,
        resourceType: type,
        prompt: promptOverride,
        quality: type === "video" ? "low" : "medium",
      });
      setResourceJobId(job.task_id);
    } catch (error) {
      setGeneratingType(null);
      setSaveMessage(error instanceof Error ? error.message : "资源生成任务启动失败。");
    }
  };

  useEffect(() => {
    if (!resourceJobId) return;
    const source = openGuideV2ResourceJobEvents(resourceJobId);
    const handle = (type: string) => () => {
      if (type === "result") {
        void detail.refetch();
        void evaluation.refetch();
        void coachBriefing.refetch();
        void mistakeReview.refetch();
        void learningTimeline.refetch();
        void studyPlan.refetch();
        void resourceRecommendations.refetch();
        void sessions.refetch();
      }
      if (type === "complete" || type === "failed") {
        if (type === "complete") {
          void detail.refetch();
          void evaluation.refetch();
          void coachBriefing.refetch();
          void mistakeReview.refetch();
          void learningTimeline.refetch();
          void studyPlan.refetch();
          void learningReport.refetch();
          void coursePackage.refetch();
          void resourceRecommendations.refetch();
          void sessions.refetch();
        }
        setGeneratingType(null);
        setResourceJobId(null);
        source.close();
      }
    };
    source.addEventListener("status", handle("status"));
    source.addEventListener("trace", handle("trace"));
    source.addEventListener("result", handle("result"));
    source.addEventListener("complete", handle("complete"));
    source.addEventListener("failed", handle("failed"));
    source.onerror = () => {
      setSaveMessage("资源生成连接暂时不可用，请稍后刷新页面查看结果。");
      setGeneratingType(null);
      setResourceJobId(null);
      source.close();
    };
    return () => source.close();
  }, [coachBriefing.refetch, coursePackage.refetch, detail.refetch, evaluation.refetch, learningReport.refetch, learningTimeline.refetch, mistakeReview.refetch, resourceJobId, resourceRecommendations.refetch, sessions.refetch, studyPlan.refetch]);

  const deleteActiveSession = async () => {
    if (!activeSessionId || !window.confirm("删除这条学习路径？")) return;
    await mutations.remove.mutateAsync(activeSessionId);
    setSelectedSessionId(null);
  };

  const saveArtifact = async (artifact: GuideV2Artifact) => {
    if (!activeSessionId || !currentTask) return;
    setSaveMessage("");
    const result = await mutations.saveArtifact.mutateAsync({
      sessionId: activeSessionId,
      taskId: currentTask.task_id,
      artifactId: artifact.id,
      notebookIds: saveNotebookId ? [saveNotebookId] : [],
      saveQuestions: true,
    });
    const notebookText = result.notebook?.added_to_notebooks?.length ? "已保存到 Notebook" : "";
    const questionText = result.question_notebook?.saved
      ? `已同步 ${result.question_notebook.count ?? 0} 道题到题目本`
      : "";
    setSaveMessage([notebookText, questionText].filter(Boolean).join("，") || "保存完成");
  };

  const saveLearningReport = async () => {
    if (!activeSessionId || !saveNotebookId) return;
    setSaveMessage("");
    const result = await mutations.saveReport.mutateAsync({
      sessionId: activeSessionId,
      notebookIds: [saveNotebookId],
      title: learningReport.data?.title,
      summary: learningReport.data?.summary,
    });
    const added = result.notebook?.added_to_notebooks?.length ?? 0;
    setSaveMessage(`学习效果报告已保存到 ${added || 0} 个 Notebook。`);
  };

  const saveCoursePackage = async () => {
    if (!activeSessionId || !saveNotebookId) return;
    setSaveMessage("");
    const result = await mutations.saveCoursePackage.mutateAsync({
      sessionId: activeSessionId,
      notebookIds: [saveNotebookId],
      title: coursePackage.data?.title,
      summary: coursePackage.data?.summary,
    });
    const added = result.notebook?.added_to_notebooks?.length ?? 0;
    setSaveMessage(`课程产出包已保存到 ${added || 0} 个 Notebook。`);
  };

  const submitQuizArtifact = async (artifact: GuideV2Artifact, answers: QuizResultItem[]) => {
    if (!activeSessionId || !currentTask) return;
    setSaveMessage("");
    const result = await mutations.submitQuiz.mutateAsync({
      sessionId: activeSessionId,
      taskId: currentTask.task_id,
      artifactId: artifact.id,
      answers,
      saveQuestions: true,
    });
    const attempt = result.attempt ?? {};
    const scoreValue = Number(attempt.score ?? 0);
    const savedCount = result.question_notebook?.count ?? 0;
    setLearningFeedback(result.learning_feedback ?? null);
    setSaveMessage(`练习已回写：得分 ${Math.round(scoreValue * 100)}%，同步 ${savedCount} 道题到题目本。`);
  };

  const submitDiagnostic = async (answers: GuideV2DiagnosticAnswer[]) => {
    if (!activeSessionId) return;
    setSaveMessage("");
    const result = await mutations.submitDiagnostic.mutateAsync({
      sessionId: activeSessionId,
      answers,
    });
    const scoreValue = Number(result.diagnosis?.readiness_score ?? 0);
    const weak = result.diagnosis?.weak_points?.[0];
    setSaveMessage(`前测已更新画像：准备度 ${Math.round(scoreValue * 100)}%${weak ? `，优先照顾「${weak}」` : ""}。`);
  };

  const submitProfileDialogue = async (message: string) => {
    if (!activeSessionId || !message.trim()) return;
    setSaveMessage("");
    const result = await mutations.submitProfileDialogue.mutateAsync({
      sessionId: activeSessionId,
      message: message.trim(),
    });
    setSaveMessage(result.assistant_reply || "学习画像已根据对话更新。");
  };

  const togglePreference = (id: string) => {
    setPreferences((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  };

  const toggleMistakeType = (id: string) => {
    setMistakeTypes((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  };

  const toggleReferenceRecord = (record: NotebookRecord) => {
    const recordId = record.record_id || record.id;
    setSelectedRecordIds((current) => (current.includes(recordId) ? current.filter((id) => id !== recordId) : [...current, recordId]));
  };

  return (
    <div className="h-full overflow-y-auto bg-canvas px-4 py-4 pb-24 lg:px-5 lg:pb-6">
      <div className="mx-auto max-w-3xl space-y-4">
        <motion.section
          className="rounded-lg border border-line bg-white p-6 shadow-sm"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22, ease: "easeOut" }}
        >
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-teal">懒人导学</p>
              <h1 className="mt-2 text-2xl font-semibold text-ink">{primaryActionLabel}</h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{stageMessage}</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                tone={focusMode ? "primary" : "secondary"}
                className="min-h-9 px-3 text-xs"
                disabled={!activeSessionId}
                onClick={() => setFocusMode((value) => !value)}
              >
                {focusMode ? "普通模式" : "专注模式"}
              </Button>
              <Button tone="quiet" className="min-h-9 px-3 text-xs" onClick={() => setSupportOpen(true)}>
                <BookOpen size={15} />
                更多
              </Button>
              <Badge tone={health.data?.status === "healthy" ? "success" : "neutral"}>
                {health.data?.status || "checking"}
              </Badge>
            </div>
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
            {journeySteps.map((step, index) => {
              const reached = index <= activeStepIndex;
              const current = index === activeStepIndex;
              return (
                <motion.div
                  key={step.id}
                  className={`rounded-lg border px-3 py-2 transition ${
                    current
                      ? "border-teal-200 bg-teal-50"
                      : reached
                        ? "border-line bg-white"
                        : "border-line bg-canvas"
                  }`}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.18, delay: index * 0.04 }}
                >
                  <div className="flex items-center gap-2">
                    {reached ? <CheckCircle2 size={14} className={current ? "text-brand-teal" : "text-emerald-600"} /> : <span className="size-2 rounded-full bg-slate-300" />}
                    <span className={`text-xs font-semibold ${current ? "text-brand-teal" : "text-slate-500"}`}>{step.label}</span>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </motion.section>

        {saveMessage ? (
          <motion.div
            className="rounded-lg border border-teal-200 bg-teal-50 px-4 py-3 text-sm leading-6 text-teal-800"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.16 }}
          >
            {saveMessage}
          </motion.div>
        ) : null}

        <div className="grid gap-4">
          <main className="space-y-4">
            {guideSubPage === "setup" ? (
              <GuideSubPageFrame
                eyebrow="目标设置"
                title="把路线参数调清楚"
                description="这里放高级设置。改完后回到主页面，继续一键创建路线。"
                onBack={() => setGuideSubPage("main")}
              >
                <form className="space-y-4" onSubmit={createSession}>
                  <FieldShell label="你想学什么">
                    <TextArea
                      value={goal}
                      onChange={(event) => setGoal(event.target.value)}
                      className="min-h-32 text-base leading-7"
                      placeholder="例如：我想在 30 分钟内理解梯度下降，并做几道题确认掌握。"
                    />
                  </FieldShell>
                  <div className="grid gap-3 md:grid-cols-2">
                    <FieldShell label="课程模板">
                      <SelectInput value={courseTemplateId} onChange={(event) => selectCourseTemplate(event.target.value)}>
                        <option value="">自定义学习目标</option>
                        {courseTemplates.map((template) => (
                          <option key={template.id} value={template.id}>
                            {template.title}
                          </option>
                        ))}
                      </SelectInput>
                    </FieldShell>
                    <FieldShell label="水平">
                      <SelectInput value={level} onChange={(event) => setLevel(event.target.value)}>
                        {levelOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </SelectInput>
                    </FieldShell>
                  </div>
                  <CourseTemplatePreview template={selectedTemplate} loading={templates.isFetching} />
                  <div className="grid gap-3 md:grid-cols-2">
                    <FieldShell label="时间">
                      <TextInput value={timeBudget} onChange={(event) => setTimeBudget(event.target.value)} inputMode="numeric" />
                    </FieldShell>
                    <FieldShell label="周期">
                      <SelectInput value={horizon} onChange={(event) => setHorizon(event.target.value)}>
                        {horizonOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </SelectInput>
                    </FieldShell>
                  </div>
                  <FieldShell label="薄弱点" hint="可选">
                    <TextInput value={weakPoints} onChange={(event) => setWeakPoints(event.target.value)} placeholder="公式推导、代码实现、概念直觉" />
                  </FieldShell>
                  <ReferencePicker
                    notebooks={notebooks.data ?? []}
                    notebookId={referenceNotebookId}
                    records={referenceRecords}
                    selectedRecordIds={selectedRecordIds}
                    loading={referenceNotebook.isFetching}
                    onNotebookChange={(value) => {
                      setReferenceNotebookId(value);
                      setSelectedRecordIds([]);
                    }}
                    onToggleRecord={toggleReferenceRecord}
                  />
                  <Button tone="primary" type="submit" className="min-h-12 w-full text-base" disabled={!goal.trim() || mutations.create.isPending}>
                    {mutations.create.isPending ? <Loader2 size={18} className="animate-spin" /> : <Sparkles size={18} />}
                    保存设置并创建路线
                  </Button>
                </form>
              </GuideSubPageFrame>
            ) : null}

            {guideSubPage === "habits" ? (
              <GuideSubPageFrame
                eyebrow="学习画像"
                title="补充你的学习习惯"
                description="告诉系统你的基础、偏好和卡点。导学路线会根据这些信息自动调整。"
                onBack={() => setGuideSubPage("main")}
              >
                <ProfileDialoguePanel
                  dialogue={profileDialogue.data ?? null}
                  loading={profileDialogue.isFetching}
                  submitting={mutations.submitProfileDialogue.isPending}
                  disabled={!activeSessionId || busy}
                  onSubmit={(message) => void submitProfileDialogue(message)}
                />
              </GuideSubPageFrame>
            ) : null}

            {guideSubPage === "completeTask" && currentTask ? (
              <GuideSubPageFrame
                eyebrow="提交学习证据"
                title="完成当前任务"
                description="写下掌握评分和一句话反思，系统会据此给出下一步反馈。"
                onBack={() => setGuideSubPage("main")}
              >
                <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
                  <div className="rounded-lg border border-line bg-canvas p-4">
                    <h3 className="text-sm font-semibold text-ink">做到这些就算完成</h3>
                    <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-600">
                      {(currentTask.success_criteria?.length ? currentTask.success_criteria : ["完成任务并写下一句话总结"]).map((item) => (
                        <li key={item} className="flex gap-2">
                          <CheckCircle2 size={16} className="mt-1 shrink-0 text-brand-teal" />
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="rounded-lg border border-line bg-white p-4">
                    <FieldShell label="掌握评分" hint="0-1">
                      <TextInput value={score} onChange={(event) => setScore(event.target.value)} inputMode="decimal" />
                    </FieldShell>
                    <FieldShell label="一句话反思">
                      <TextArea
                        value={reflection}
                        onChange={(event) => setReflection(event.target.value)}
                        className="min-h-28"
                        placeholder="我已经理解了……还不确定的是……"
                      />
                    </FieldShell>
                    <Button tone="primary" className="mt-3 w-full" onClick={() => void completeCurrentTask()} disabled={busy || !activeSessionId}>
                      {mutations.completeTask.isPending ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
                      完成并获得反馈
                    </Button>
                  </div>
                </div>
              </GuideSubPageFrame>
            ) : null}

            {guideSubPage === "routeMap" && session ? (
              <GuideSubPageFrame
                eyebrow="完整路线"
                title="学习路线与任务队列"
                description="这里集中查看路径、知识地图和所有任务。主页面只保留当前动作。"
                onBack={() => setGuideSubPage("main")}
              >
                <StudyPlanPanel plan={studyPlan.data ?? null} loading={studyPlan.isFetching} />
                <CourseSyllabusPanel metadata={courseMetadata} />
                <section className="rounded-lg border border-line bg-white p-5">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <h2 className="text-base font-semibold text-ink">知识地图</h2>
                      <p className="mt-1 text-sm text-slate-500">按学习顺序展示知识点、当前所在位置和每个节点的任务。</p>
                    </div>
                    <Badge tone="neutral">{nodes.length} 节点</Badge>
                  </div>
                  <KnowledgeMapVisualization
                    nodes={nodes}
                    mastery={session?.mastery ?? {}}
                    tasks={tasks}
                    currentTask={currentTask}
                  />
                </section>
                <section className="rounded-lg border border-line bg-white p-5">
                  <h2 className="text-base font-semibold text-ink">任务队列</h2>
                  <div className="mt-4 space-y-2">
                    {tasks.map((task) => (
                      <TaskRow key={task.task_id} task={task} active={task.task_id === currentTask?.task_id} />
                    ))}
                    {!tasks.length ? <p className="rounded-lg bg-canvas p-4 text-sm text-slate-500">暂无任务。</p> : null}
                  </div>
                </section>
              </GuideSubPageFrame>
            ) : null}

            {guideSubPage === "main" ? (
              <>
            {!session ? (
              <section className="rounded-lg border border-line bg-white p-5 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <Badge tone="brand">先做这一件事</Badge>
                    <h2 className="mt-3 text-xl font-semibold text-ink">{primaryActionLabel}</h2>
                    <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
                      写下目标、时间和偏好即可。路线、前测、资源和反馈都会在后面自动接上，不需要你自己找入口。
                    </p>
                  </div>
                  <Badge tone="neutral">{sessions.data?.length ?? 0} 条历史路线</Badge>
                </div>
                <form className="mt-6 space-y-4" onSubmit={createSession}>
                  <FieldShell label="你想学什么">
                    <TextArea
                      value={goal}
                      onChange={(event) => setGoal(event.target.value)}
                      className="min-h-36 text-base leading-7"
                      placeholder="例如：我想在 30 分钟内理解梯度下降，并做几道题确认掌握。"
                    />
                  </FieldShell>
                  <Button tone="primary" type="submit" className="min-h-12 w-full text-base" disabled={!goal.trim() || mutations.create.isPending}>
                    {mutations.create.isPending ? <Loader2 size={18} className="animate-spin" /> : <Sparkles size={18} />}
                    帮我安排学习
                  </Button>

                  <button
                    type="button"
                    className="w-full rounded-lg border border-line bg-canvas p-4 text-left transition hover:border-teal-200 hover:bg-teal-50"
                    onClick={() => setGuideSubPage("setup")}
                  >
                    <span className="text-sm font-semibold text-ink">进入高级设置页</span>
                    <span className="mt-1 block text-xs leading-5 text-slate-500">课程模板、水平、时间、薄弱点和 Notebook 引用都放在单独页面里。</span>
                  </button>
                </form>
              </section>
            ) : null}

            {session && guideStage === "diagnostic" ? (
              <>
                <section className="rounded-lg border border-teal-200 bg-white p-5 shadow-sm">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <Badge tone="brand">先做这一件事</Badge>
                      <h2 className="mt-3 text-xl font-semibold text-ink">先校准起点，再开始学习</h2>
                      <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                        这一步会判断你是概念不稳、公式断裂，还是缺练习。后面的路线会因此变得更贴身。
                      </p>
                    </div>
                    <Badge tone="warning">约 2 分钟</Badge>
                  </div>
                </section>
                <DiagnosticPanel
                  diagnostic={diagnostic.data ?? null}
                  loading={diagnostic.isFetching}
                  submitting={mutations.submitDiagnostic.isPending}
                  disabled={!activeSessionId || busy}
                  onSubmit={(answers) => void submitDiagnostic(answers)}
                />
                <button
                  type="button"
                  className="w-full rounded-lg border border-line bg-white p-4 text-left transition hover:border-teal-200 hover:bg-teal-50"
                  onClick={() => setGuideSubPage("habits")}
                >
                  <span className="text-sm font-semibold text-ink">进入学习画像页</span>
                  <span className="mt-1 block text-xs leading-5 text-slate-500">补充学习习惯、基础和卡点，用单独页面完成。</span>
                </button>
              </>
            ) : null}

            {session && guideStage === "feedback" ? (
              <LearningFeedbackCard feedback={learningFeedback} />
            ) : null}

            {session && (guideStage === "learn" || guideStage === "feedback") ? (
              <>
                <section className="rounded-lg border border-line bg-white p-5 shadow-sm">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <Badge tone="brand">{guideStage === "feedback" ? "接着做这一步" : "先做这一件事"}</Badge>
                      <h2 className="mt-3 text-xl font-semibold text-ink">{currentTask?.title || "路线正在整理下一步"}</h2>
                      <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                        {currentTask?.instruction || "系统会把目标拆成可执行任务，并根据完成情况更新掌握度与下一步建议。"}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge tone={currentTask?.status === "completed" ? "success" : "neutral"}>{currentTask?.status || "pending"}</Badge>
                      {currentTask ? (
                        <Badge tone="neutral">
                          <Clock3 size={13} className="mr-1" />
                          {currentTask.estimated_minutes ?? 8} 分钟
                        </Badge>
                      ) : null}
                    </div>
                  </div>

                  {currentTask ? (
                    <div className="mt-5 space-y-4">
                      <FieldShell label="补充要求" hint="可选">
                        <TextInput
                          value={resourcePrompt}
                          onChange={(event) => setResourcePrompt(event.target.value)}
                          placeholder="例如：更适合零基础、重点解释公式含义、用 C++ 例子说明"
                          disabled={!currentTask || Boolean(generatingType)}
                        />
                      </FieldShell>
                      <div className="grid gap-3 sm:grid-cols-3">
                        <Button
                          tone="secondary"
                          className="min-h-14 justify-center"
                          disabled={!activeSessionId || busy || Boolean(generatingType)}
                          onClick={() => void generateResource("visual")}
                        >
                          {generatingType === "visual" ? <Loader2 size={16} className="animate-spin" /> : <Map size={16} />}
                          看图解
                        </Button>
                        <Button
                          tone="secondary"
                          className="min-h-14 justify-center"
                          disabled={!activeSessionId || busy || Boolean(generatingType)}
                          onClick={() => void generateResource("quiz")}
                        >
                          {generatingType === "quiz" ? <Loader2 size={16} className="animate-spin" /> : <ListChecks size={16} />}
                          做练习
                        </Button>
                        <Button
                          tone="primary"
                          className="min-h-14 justify-center"
                          disabled={!activeSessionId || busy || Boolean(generatingType)}
                          onClick={() => void generateResource("video")}
                        >
                          {generatingType === "video" ? <Loader2 size={16} className="animate-spin" /> : <Video size={16} />}
                          看短视频
                        </Button>
                      </div>

                      <button
                        type="button"
                        className="w-full rounded-lg border border-line bg-canvas p-4 text-left transition hover:border-teal-200 hover:bg-teal-50"
                        onClick={() => setGuideSubPage("completeTask")}
                      >
                        <span className="text-sm font-semibold text-ink">进入提交页</span>
                        <span className="mt-1 block text-xs leading-5 text-slate-500">学完后到单独页面提交评分和反思，系统再给反馈。</span>
                      </button>
                    </div>
                  ) : null}
                </section>

                {currentArtifacts.length || generatingType ? (
                <section className="rounded-lg border border-line bg-white p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h2 className="text-base font-semibold text-ink">生成结果</h2>
                      <p className="mt-1 text-sm leading-6 text-slate-500">
                        图解、短视频和练习统一放在这里，用分页切换查看。
                      </p>
                    </div>
                    <Badge tone={generatingType ? "brand" : currentArtifacts.length ? "brand" : "neutral"}>
                      {generatingType ? "生成中" : `${currentArtifacts.length} 个资源`}
                    </Badge>
                  </div>
                  <div className="mt-5 space-y-3">
                    {generatingType ? (
                      <div className="flex items-center gap-2 rounded-lg border border-teal-200 bg-teal-50 p-3 text-sm text-teal-800">
                        <Loader2 size={16} className="animate-spin" />
                        正在生成{resourceLabel(generatingType)}，完成后会自动出现在结果页。
                      </div>
                    ) : null}
                    {currentArtifacts.length ? (
                      <ResourceArtifactPager
                        artifacts={currentArtifacts}
                        saveNotebookId={saveNotebookId}
                        saving={mutations.saveArtifact.isPending}
                        quizSubmitting={mutations.submitQuiz.isPending}
                        onSave={(artifact) => void saveArtifact(artifact)}
                        onSubmitQuiz={(artifact, answers) => void submitQuizArtifact(artifact, answers)}
                      />
                    ) : null}
                    {currentTask && !currentArtifacts.length ? (
                      <p className="rounded-lg border border-dashed border-line bg-canvas p-4 text-sm text-slate-500">
                        还没有资源。建议先点“生成图解”，看懂后再点“生成练习”。
                      </p>
                    ) : null}
                  </div>
                </section>
                ) : null}
              </>
            ) : null}

            {session && guideStage === "complete" ? (
              <section className="rounded-lg border border-line bg-white p-5 shadow-sm">
                <Badge tone="success">路线完成</Badge>
                <h2 className="mt-3 text-xl font-semibold text-ink">你已经走完这条学习路线</h2>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                  现在适合查看学习报告、导出课程包，或者在学习背包里开启新的目标。
                </p>
                <div className="mt-4 grid gap-4 lg:grid-cols-2">
                  <LearningReportPanel
                    report={learningReport.data ?? null}
                    loading={learningReport.isFetching}
                    canSave={Boolean(activeSessionId && saveNotebookId)}
                    saving={mutations.saveReport.isPending}
                    onSave={() => void saveLearningReport()}
                  />
                  <CoursePackagePanel
                    coursePackage={coursePackage.data ?? null}
                    loading={coursePackage.isFetching}
                    canSave={Boolean(activeSessionId && saveNotebookId)}
                    saving={mutations.saveCoursePackage.isPending}
                    onSave={() => void saveCoursePackage()}
                  />
                </div>
              </section>
            ) : null}

            {session ? (
              <button
                type="button"
                className="w-full rounded-lg border border-line bg-white p-4 text-left transition hover:border-teal-200 hover:bg-teal-50"
                onClick={() => setGuideSubPage("routeMap")}
              >
                <span className="text-sm font-semibold text-ink">进入完整路线页</span>
                <span className="mt-1 block text-xs leading-5 text-slate-500">知识地图、学习计划和任务队列放到独立页面查看。</span>
              </button>
            ) : null}
              </>
            ) : null}
          </main>

          {false ? (
            <aside className="space-y-4">
              <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
                <div className="flex items-center gap-2">
                  <Target size={18} className="text-brand-teal" />
                  <h2 className="text-base font-semibold text-ink">现在只看这里</h2>
                </div>
                <p className="mt-3 text-sm leading-6 text-slate-600">{primaryActionLabel}</p>
                <div className="mt-4 grid grid-cols-2 gap-2">
                  <EvalMini label="进度" value={`${session?.progress ?? 0}%`} />
                  <EvalMini label="任务" value={tasks.length || 0} />
                </div>
                <Button tone="secondary" className="mt-4 w-full" onClick={() => setSupportOpen(true)}>
                  <BookOpen size={16} />
                  打开学习背包
                </Button>
              </section>

              <CoachNudgeCard
                briefing={coachBriefing.data ?? null}
                loading={coachBriefing.isFetching}
                onOpen={() => setSupportOpen(true)}
              />
            </aside>
          ) : null}
        </div>

        <AnimatePresence>
          {supportOpen ? (
            <motion.div
              className="fixed inset-0 z-50 bg-slate-900/25"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <button
                type="button"
                className="absolute inset-0 cursor-default"
                aria-label="关闭学习背包"
                onClick={() => setSupportOpen(false)}
              />
              <motion.aside
                className="absolute right-0 top-0 h-full w-full max-w-[430px] overflow-y-auto bg-canvas p-4 shadow-2xl"
                initial={{ x: 440 }}
                animate={{ x: 0 }}
                exit={{ x: 440 }}
                transition={{ type: "spring", stiffness: 280, damping: 30 }}
              >
                <div className="mb-4 flex items-center justify-between gap-3 rounded-lg border border-line bg-white p-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-brand-teal">学习背包</p>
                    <h2 className="mt-1 text-lg font-semibold text-ink">只保留关键入口</h2>
                  </div>
                  <Button tone="quiet" className="min-h-8 px-2" onClick={() => setSupportOpen(false)}>
                    <X size={16} />
                  </Button>
                </div>

                <div className="space-y-4">
                  <section className="rounded-lg border border-line bg-white p-4">
                    <h2 className="text-base font-semibold text-ink">路线</h2>
                    <p className="mt-1 text-xs leading-5 text-slate-500">切换路线，或直接创建一个新目标。</p>
                    <div className="mt-4 space-y-3">
                      <form className="space-y-3" onSubmit={createSession}>
                        <FieldShell label="新学习目标">
                          <TextArea value={goal} onChange={(event) => setGoal(event.target.value)} className="min-h-20" />
                        </FieldShell>
                        <Button tone="primary" type="submit" className="w-full" disabled={!goal.trim() || mutations.create.isPending}>
                          {mutations.create.isPending ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
                          创建新路线
                        </Button>
                      </form>
                      <div className="max-h-52 space-y-2 overflow-y-auto pr-1">
                        {(sessions.data ?? []).slice(0, 5).map((item) => (
                          <button
                            key={item.session_id}
                            type="button"
                            onClick={() => {
                              setSelectedSessionId(item.session_id);
                              setSupportOpen(false);
                            }}
                            className={`w-full rounded-lg border p-3 text-left transition ${
                              activeSessionId === item.session_id ? "border-teal-200 bg-teal-50" : "border-line bg-white hover:border-teal-200"
                            }`}
                          >
                            <p className="line-clamp-2 text-sm font-semibold text-ink">{item.goal}</p>
                            <p className="mt-1 text-xs text-slate-500">
                              {item.progress ?? 0}% · {item.task_count ?? 0} 个任务
                            </p>
                          </button>
                        ))}
                        {!sessions.data?.length ? <p className="rounded-lg bg-canvas p-3 text-sm text-slate-500">还没有学习路线。</p> : null}
                      </div>
                    </div>
                  </section>

                  <section className="rounded-lg border border-line bg-white p-4">
                    <div className="flex items-center gap-2">
                      <Brain size={18} className="text-brand-teal" />
                      <h2 className="text-base font-semibold text-ink">画像摘要</h2>
                    </div>
                    <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
                      <Fact label="水平" value={String(profile.level || "-")} />
                      <Fact label="时间" value={profile.time_budget_minutes ? `${profile.time_budget_minutes} 分钟` : "-"} />
                      <Fact label="偏好" value={arrayText(profile.preferences)} />
                      <Fact label="薄弱点" value={arrayText(profile.weak_points)} />
                    </div>
                  </section>

                  <section className="rounded-lg border border-line bg-white p-4">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <GraduationCap size={18} className="text-brand-teal" />
                        <h2 className="text-base font-semibold text-ink">下一步建议</h2>
                      </div>
                      <Button tone="quiet" className="min-h-8 px-2 text-xs" disabled={!activeSessionId || busy} onClick={() => activeSessionId && mutations.refreshRecommendations.mutate(activeSessionId)}>
                        <RefreshCw size={14} />
                      </Button>
                    </div>
                    {currentTask ? (
                      <div className="mt-3 rounded-lg border border-line bg-canvas p-3">
                        <p className="text-sm font-semibold text-ink">{currentTask.title}</p>
                        <p className="mt-1 line-clamp-3 text-xs leading-5 text-slate-600">{currentTask.instruction || "继续完成当前任务。"}</p>
                      </div>
                    ) : null}
                    <div className="mt-3 space-y-2">
                      {recommendations.slice(0, 2).map((item) => (
                        <p key={item} className="rounded-lg border border-line bg-canvas p-3 text-sm leading-6 text-slate-600">
                          {item}
                        </p>
                      ))}
                      {!recommendations.length ? <p className="rounded-lg bg-canvas p-3 text-sm text-slate-500">完成任务后会更新建议。</p> : null}
                    </div>
                  </section>

                  <section className="rounded-lg border border-line bg-white p-4">
                    <h2 className="text-base font-semibold text-ink">操作</h2>
                    <div className="mt-3 grid gap-2">
                      <Button tone="secondary" disabled={!activeSessionId || busy} onClick={() => activeSessionId && mutations.refreshRecommendations.mutate(activeSessionId)}>
                        <RefreshCw size={16} />
                        刷新建议
                      </Button>
                      <Button tone="danger" disabled={!activeSessionId || busy} onClick={() => void deleteActiveSession()}>
                        <Trash2 size={16} />
                        删除路线
                      </Button>
                    </div>
                  </section>
                </div>
              </motion.aside>
            </motion.div>
          ) : null}
        </AnimatePresence>
      </div>
    </div>
  );
}

function GuideSubPageFrame({
  eyebrow,
  title,
  description,
  children,
  onBack,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
  onBack: () => void;
}) {
  return (
    <motion.section
      className="rounded-lg border border-line bg-white p-5 shadow-sm"
      initial={{ opacity: 0, x: 18 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -18 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
    >
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3 border-b border-line pb-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-brand-teal">{eyebrow}</p>
          <h2 className="mt-2 text-xl font-semibold text-ink">{title}</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">{description}</p>
        </div>
        <Button tone="secondary" className="min-h-9 px-3 text-xs" onClick={onBack}>
          <ChevronLeft size={15} />
          返回主流程
        </Button>
      </div>
      <div className="space-y-4">{children}</div>
    </motion.section>
  );
}

function ReferencePicker({
  notebooks,
  notebookId,
  records,
  selectedRecordIds,
  loading,
  onNotebookChange,
  onToggleRecord,
}: {
  notebooks: Array<{ id: string; name?: string }>;
  notebookId: string;
  records: NotebookRecord[];
  selectedRecordIds: string[];
  loading: boolean;
  onNotebookChange: (value: string) => void;
  onToggleRecord: (record: NotebookRecord) => void;
}) {
  return (
    <div className="rounded-lg border border-line bg-canvas p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-medium text-ink">引用学习记录</p>
        <Badge tone={selectedRecordIds.length ? "brand" : "neutral"}>{selectedRecordIds.length} 条</Badge>
      </div>
      <SelectInput className="mt-3" value={notebookId} onChange={(event) => onNotebookChange(event.target.value)}>
        <option value="">不引用 Notebook</option>
        {notebooks.map((item) => (
          <option key={item.id} value={item.id}>
            {item.name || item.id}
          </option>
        ))}
      </SelectInput>
      {notebookId ? (
        <div className="mt-3 space-y-2">
          {records.map((record) => {
            const recordId = record.record_id || record.id;
            const selected = selectedRecordIds.includes(recordId);
            return (
              <button
                key={recordId}
                type="button"
                onClick={() => onToggleRecord(record)}
                className={`w-full rounded-lg border p-3 text-left transition ${
                  selected ? "border-teal-200 bg-teal-50" : "border-line bg-white hover:border-teal-200"
                }`}
              >
                <p className="truncate text-sm font-semibold text-ink">{record.title || recordId}</p>
                <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{record.summary || record.user_query || "学习记录"}</p>
              </button>
            );
          })}
          {loading ? <p className="text-xs text-slate-500">正在读取记录...</p> : null}
          {!loading && !records.length ? <p className="text-xs text-slate-500">这个 Notebook 暂无可引用记录。</p> : null}
        </div>
      ) : null}
    </div>
  );
}

function CourseTemplatePreview({
  template,
  loading,
}: {
  template: GuideV2CourseTemplate | null;
  loading: boolean;
}) {
  if (loading && !template) {
    return (
      <div className="rounded-lg border border-line bg-canvas p-3 text-sm text-slate-500">
        正在读取课程模板...
      </div>
    );
  }
  if (!template) {
    return (
      <div className="rounded-lg border border-line bg-canvas p-3 text-sm leading-6 text-slate-500">
        选择内置课程会自动填入学习目标、时间预算和偏好；自定义目标适合临时补课或短期专项学习。
      </div>
    );
  }
  return (
    <motion.div
      className="rounded-lg border border-teal-200 bg-teal-50 p-3"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.16 }}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-ink">{template.course_name || template.title}</p>
          <p className="mt-1 text-xs leading-5 text-slate-600">{template.description}</p>
        </div>
        <Badge tone="brand">{template.course_id || template.id}</Badge>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2">
        <EvalMini label="周期" value={Number(template.suggested_weeks ?? 0)} suffix="周" />
        <EvalMini label="学分" value={Number(template.credits ?? 0)} />
        <EvalMini label="课时" value={Number(template.estimated_minutes ?? 0)} suffix="m" />
      </div>
      {template.learning_outcomes?.length ? (
        <p className="mt-3 line-clamp-2 text-xs leading-5 text-slate-600">
          {template.learning_outcomes[0]}
        </p>
      ) : null}
      {template.tags?.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {template.tags.slice(0, 4).map((tag) => (
            <Badge key={tag} tone="neutral">{tag}</Badge>
          ))}
        </div>
      ) : null}
    </motion.div>
  );
}

function LongTermMemoryPanel({
  memory,
  loading,
}: {
  memory: GuideV2LearnerMemory | null;
  loading: boolean;
}) {
  const weakPoints = memory?.persistent_weak_points ?? [];
  const preferences = memory?.top_preferences ?? [];
  const mistakes = memory?.common_mistakes ?? [];
  const strengths = memory?.strengths ?? [];
  const evidenceCount = Number(memory?.evidence_count ?? 0);
  return (
    <section className="rounded-lg border border-line bg-white p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Brain size={18} className="text-brand-teal" />
          <h2 className="text-base font-semibold text-ink">长期学习画像</h2>
        </div>
        {loading ? (
          <Loader2 size={16} className="animate-spin text-brand-teal" />
        ) : (
          <Badge tone={evidenceCount ? "brand" : "neutral"}>{evidenceCount} 证据</Badge>
        )}
      </div>
      <p className="mt-3 text-xs leading-5 text-slate-600">
        {memory?.summary || "完成更多导学任务后，系统会沉淀跨课程的偏好、薄弱点和常见错因。"}
      </p>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <EvalMini label="路线" value={Number(memory?.session_count ?? 0)} />
        <EvalMini
          label="均分"
          value={memory?.average_score == null ? "-" : Math.round(Number(memory.average_score) * 100)}
          suffix={memory?.average_score == null ? "" : "%"}
        />
      </div>
      {preferences.length ? <MemoryChipGroup title="偏好" items={preferences.slice(0, 4)} tone="brand" /> : null}
      {weakPoints.length ? <MemoryChipGroup title="薄弱点" items={weakPoints.slice(0, 4)} tone="warning" /> : null}
      {mistakes.length ? <MemoryChipGroup title="常见错因" items={mistakes.slice(0, 3)} tone="danger" /> : null}
      {strengths.length ? <MemoryChipGroup title="优势" items={strengths.slice(0, 3)} tone="success" /> : null}
      {memory?.next_guidance?.length ? (
        <div className="mt-3 space-y-2">
          {memory.next_guidance.slice(0, 2).map((item) => (
            <p key={item} className="rounded-lg border border-teal-100 bg-teal-50 p-2 text-xs leading-5 text-teal-800">
              {item}
            </p>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function MemoryChipGroup({
  title,
  items,
  tone,
}: {
  title: string;
  items: Array<{ label?: string; count?: number }>;
  tone: "success" | "warning" | "brand" | "danger";
}) {
  return (
    <div className="mt-3">
      <p className="text-xs font-semibold text-slate-500">{title}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {items.map((item) => (
          <Badge key={`${title}-${item.label}`} tone={tone}>
            {item.label || "-"} {item.count ? `×${item.count}` : ""}
          </Badge>
        ))}
      </div>
    </div>
  );
}

function CoachNudgeCard({
  briefing,
  loading,
  onOpen,
}: {
  briefing: GuideV2CoachBriefing | null;
  loading: boolean;
  onOpen: () => void;
}) {
  const focus = briefing?.focus ?? {};
  const firstAction = briefing?.next_actions?.[0] || briefing?.coach_actions?.[0]?.label || "完成当前一步后，我会继续调整路线。";
  const blocker = briefing?.blockers?.[0];
  return (
    <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Sparkles size={18} className="text-brand-teal" />
          <h2 className="text-base font-semibold text-ink">学习助手</h2>
        </div>
        {loading ? <Loader2 size={16} className="animate-spin text-brand-teal" /> : <Badge tone="brand">在线</Badge>}
      </div>
      <p className="mt-3 text-sm font-semibold leading-6 text-ink">
        {briefing?.headline || focus.task_title || "先从当前这一步开始。"}
      </p>
      <p className="mt-2 text-sm leading-6 text-slate-600">{firstAction}</p>
      {blocker ? (
        <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-800">
          可能卡点：{blocker}
        </p>
      ) : null}
      <Button tone="secondary" className="mt-4 w-full" onClick={onOpen}>
        <BookOpen size={16} />
        查看依据
      </Button>
    </section>
  );
}

function CoachBriefingPanel({
  briefing,
  loading,
  disabled,
  onGenerate,
  onGenerateResource,
}: {
  briefing: GuideV2CoachBriefing | null;
  loading: boolean;
  disabled: boolean;
  onGenerate: (item: GuideV2ResourceRecommendation) => void;
  onGenerateResource: (type: GuideV2ResourceType, taskId: string, prompt: string) => void;
}) {
  const focus = briefing?.focus ?? {};
  const microPlan = briefing?.micro_plan ?? [];
  const shortcuts = (briefing?.resource_shortcuts ?? []).filter((item) => !isResearchResourceType(item.resource_type));
  const coachMode = briefing?.coach_mode || "normal";
  const mistakeSummary = briefing?.mistake_summary;
  const priorityMistake = briefing?.priority_mistake;
  const effectAssessment = briefing?.effect_assessment;
  const focusTaskId = focus.task_id || "";
  const fallbackCoachActions = coachModeActions(
    coachMode,
    focusTaskId,
    priorityMistake?.label || focus.task_title || "当前任务",
    priorityMistake?.suggested_action || "",
  );
  const coachActions = (briefing?.coach_actions?.length ? briefing.coach_actions : fallbackCoachActions).filter(
    (item) => !isResearchResourceType(item.resource_type || item.type || ""),
  );
  return (
    <section className="rounded-lg border border-teal-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Sparkles size={18} className="text-brand-teal" />
            <p className="text-sm font-semibold text-brand-teal">今日导学简报</p>
            <Badge tone={coachModeTone(coachMode)}>{coachModeLabel(coachMode)}</Badge>
          </div>
          <h2 className="mt-3 text-xl font-semibold text-ink">
            {briefing?.headline || "创建学习路线后，我会给出今天最该做的一步。"}
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            {briefing?.summary || "简报会综合学习画像、任务状态、资源生成和练习证据，把下一步变成可执行的小动作。"}
          </p>
          {briefing?.priority_reason ? (
            <p className="mt-2 max-w-3xl text-xs leading-5 text-brand-teal">{briefing.priority_reason}</p>
          ) : null}
        </div>
        {loading ? <Loader2 size={18} className="animate-spin text-brand-teal" /> : <Badge tone={focus.mastery_status === "mastered" ? "success" : "brand"}>{Math.round(Number(focus.mastery_score ?? 0) * 100)}%</Badge>}
      </div>
      {effectAssessment ? (
        <div className="mt-4 rounded-lg border border-line bg-canvas p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={effectStatusTone(effectAssessment.score)}>{effectAssessment.label || "效果评估"}</Badge>
              <span className="text-sm font-semibold text-ink">{Number(effectAssessment.score ?? 0)} 分</span>
            </div>
            <span className="text-xs text-slate-400">学习效果雷达</span>
          </div>
          <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-600">{effectAssessment.summary || "正在根据学习证据更新判断。"}</p>
        </div>
      ) : null}

      <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_260px]">
        <div className="rounded-lg border border-line bg-canvas p-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">{focus.task_type ? taskTypeLabel(focus.task_type) : "任务"}</Badge>
            {focus.estimated_minutes ? <Badge tone="neutral">{focus.estimated_minutes} 分钟</Badge> : null}
            {focus.node_title ? <Badge tone="neutral">{focus.node_title}</Badge> : null}
          </div>
          <p className="mt-3 text-sm font-semibold text-ink">{focus.task_title || "等待当前任务"}</p>
          <div className="mt-3 grid gap-2 sm:grid-cols-3">
            {microPlan.slice(0, 3).map((item) => (
              <div key={`${item.step}-${item.title}`} className="rounded-lg border border-line bg-white p-3">
                <div className="flex items-center justify-between gap-2">
                  <Badge tone="neutral">Step {item.step ?? "-"}</Badge>
                  <span className="text-xs text-slate-400">{item.duration_minutes ?? "-"}m</span>
                </div>
                <p className="mt-2 line-clamp-3 text-xs font-medium leading-5 text-slate-700">{item.title || "行动"}</p>
              </div>
            ))}
            {!microPlan.length ? <p className="rounded-lg bg-white p-3 text-xs text-slate-500">完成第一条路线后生成行动计划。</p> : null}
          </div>
        </div>

        <div className="rounded-lg border border-line bg-white p-3">
          <p className="text-sm font-semibold text-ink">快速调用</p>
          {priorityMistake ? (
            <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3">
              <div className="flex flex-wrap gap-2">
                <Badge tone={mistakeLoopStatusTone(priorityMistake.loop_status)}>
                  {mistakeLoopStatusLabel(priorityMistake.loop_status)}
                </Badge>
                <Badge tone={mistakeSeverityTone(priorityMistake.severity)}>
                  {mistakeSeverityLabel(priorityMistake.severity)}
                </Badge>
              </div>
              <p className="mt-2 line-clamp-2 text-xs font-semibold text-ink">{priorityMistake.label || "当前错因"}</p>
              {priorityMistake.suggested_action ? (
                <p className="mt-1 line-clamp-3 text-xs leading-5 text-slate-600">{priorityMistake.suggested_action}</p>
              ) : null}
            </div>
          ) : null}
          <div className="mt-3 space-y-2">
            {coachActions.map((item) => {
              const resourceType = normalizeResourceType(item.resource_type || item.type || "visual");
              const targetTaskId = item.target_task_id || focusTaskId;
              const prompt = item.prompt || `围绕「${focus.task_title || "当前任务"}」生成学习资源。`;
              const label = item.label || item.title || resourceLabel(resourceType);
              return (
                <Button
                  key={item.id || `${resourceType}-${label}`}
                  tone={item.primary ? "primary" : "secondary"}
                  className="w-full justify-start text-left text-xs"
                  disabled={disabled || !targetTaskId}
                  onClick={() => onGenerateResource(resourceType, targetTaskId, prompt)}
                >
                  <Lightbulb size={14} />
                  {label}
                </Button>
              );
            })}
            {shortcuts.slice(0, 2).map((item) => (
              <Button
                key={item.id}
                tone="secondary"
                className="w-full justify-start text-left text-xs"
                disabled={disabled}
                onClick={() => onGenerate(item)}
              >
                <Lightbulb size={14} />
                {resourceLabel(normalizeResourceType(item.resource_type))}
              </Button>
            ))}
            {!shortcuts.length && !coachActions.length ? <p className="text-xs leading-5 text-slate-500">完成或提交证据后会给出更精确的资源入口。</p> : null}
          </div>
          {mistakeSummary?.cluster_count ? (
            <div className="mt-3 grid grid-cols-3 gap-2">
              <EvalMini label="待处理" value={Number(mistakeSummary.open_cluster_count ?? 0)} />
              <EvalMini label="已闭环" value={Number(mistakeSummary.closed_cluster_count ?? 0)} />
              <EvalMini label="复测" value={Number(mistakeSummary.pending_retest_count ?? 0)} />
            </div>
          ) : null}
        </div>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <EvalList title="为什么这样安排" items={briefing?.evidence_reasons ?? []} empty="先创建路线并完成第一项任务。" tone="brand" />
        <EvalList title="当前卡点" items={briefing?.blockers ?? []} empty="暂未发现明显卡点。" tone="warning" />
      </div>
    </section>
  );
}

function LearningFeedbackCard({ feedback }: { feedback: GuideV2LearningFeedback | null }) {
  if (!feedback) return null;
  const actions = feedback.actions ?? [];
  const quality = feedback.evidence_quality;
  return (
    <motion.section
      className="rounded-lg border border-teal-200 bg-white p-5 shadow-sm"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <CheckCircle2 size={18} className="text-brand-teal" />
            <p className="text-sm font-semibold text-brand-teal">即时学习反馈</p>
            <Badge tone={feedbackTone(feedback.tone)}>{feedback.score_percent == null ? "已记录" : `${feedback.score_percent}%`}</Badge>
          </div>
          <h2 className="mt-3 text-lg font-semibold text-ink">{feedback.title || "学习证据已记录"}</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            {feedback.summary || "系统已经根据这次学习证据更新路线。"}
          </p>
        </div>
        {feedback.next_task_title ? <Badge tone="brand">下一步</Badge> : <Badge tone="success">完成</Badge>}
      </div>
      {actions.length ? (
        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          {actions.slice(0, 4).map((item) => (
            <p key={item} className="rounded-lg border border-line bg-canvas px-3 py-2 text-xs leading-5 text-slate-600">
              {item}
            </p>
          ))}
        </div>
      ) : null}
      {quality ? (
        <div className="mt-4 rounded-lg border border-line bg-canvas p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-semibold text-ink">证据质量</p>
            <Badge tone={effectStatusTone(quality.score)}>{quality.label || `${quality.score ?? 0} 分`}</Badge>
          </div>
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            {(quality.strengths ?? []).slice(0, 2).map((item) => (
              <p key={item} className="text-xs leading-5 text-slate-600">• {item}</p>
            ))}
            {(quality.gaps ?? []).slice(0, 2).map((item) => (
              <p key={item} className="text-xs leading-5 text-amber-700">• {item}</p>
            ))}
          </div>
        </div>
      ) : null}
    </motion.section>
  );
}

function ProfileDialoguePanel({
  dialogue,
  loading,
  submitting,
  disabled,
  onSubmit,
}: {
  dialogue: GuideV2ProfileDialogue | null;
  loading: boolean;
  submitting: boolean;
  disabled: boolean;
  onSubmit: (message: string) => void;
}) {
  const [message, setMessage] = useState("");
  const prompts = dialogue?.suggested_prompts ?? [];
  const lastSignals = asRecord(dialogue?.last_signals) ?? {};
  const weakPoints = Array.isArray(lastSignals.weak_points) ? lastSignals.weak_points.map(String) : [];
  const preferences = Array.isArray(lastSignals.preferences) ? lastSignals.preferences.map(String) : [];

  const submit = () => {
    const cleaned = message.trim();
    if (!cleaned || disabled || submitting) return;
    onSubmit(cleaned);
    setMessage("");
  };

  return (
    <section className="rounded-lg border border-line bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="grid size-10 place-items-center rounded-lg border border-teal-200 bg-teal-50 text-brand-teal">
            <MessageCircle size={20} />
          </div>
          <div>
            <h2 className="text-base font-semibold text-ink">对话式学习画像</h2>
            <p className="mt-1 text-sm leading-6 text-slate-500">
              {dialogue?.summary || "用一句话告诉系统你的基础、时间、偏好或卡点，路线会立刻调整。"}
            </p>
          </div>
        </div>
        {loading ? (
          <Loader2 size={16} className="animate-spin text-brand-teal" />
        ) : (
          <Badge tone={dialogue?.status === "updated" ? "success" : "brand"}>
            {dialogue?.status === "updated" ? "已更新" : "可对话"}
          </Badge>
        )}
      </div>

      <div className="mt-4 rounded-lg border border-line bg-canvas p-3">
        <TextArea
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          className="min-h-20 bg-white"
          disabled={disabled || submitting}
          placeholder="例如：我今天只有20分钟，公式推导不太会，希望先看图解再做题。"
        />
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-slate-500">自然语言会被解析为画像信号、薄弱点和资源偏好。</p>
          <Button tone="primary" disabled={!message.trim() || disabled || submitting} onClick={submit}>
            {submitting ? <Loader2 size={16} className="animate-spin" /> : <MessageCircle size={16} />}
            更新画像
          </Button>
        </div>
      </div>

      {prompts.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {prompts.slice(0, 4).map((prompt) => (
            <button
              key={prompt}
              type="button"
              disabled={disabled || submitting}
              onClick={() => setMessage(prompt)}
              className="rounded-lg border border-line bg-white px-3 py-2 text-left text-xs leading-5 text-slate-600 transition hover:border-teal-200 hover:text-brand-teal disabled:cursor-not-allowed"
            >
              {prompt}
            </button>
          ))}
        </div>
      ) : null}

      {(weakPoints.length || preferences.length) ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {weakPoints.slice(0, 3).map((item) => (
            <Badge key={`weak-${item}`} tone="warning">薄弱：{item}</Badge>
          ))}
          {preferences.filter((item) => !isResearchResourceType(item)).slice(0, 3).map((item) => (
            <Badge key={`pref-${item}`} tone="brand">偏好：{resourceOrPreferenceLabel(item)}</Badge>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function DiagnosticPanel({
  diagnostic,
  loading,
  submitting,
  disabled,
  onSubmit,
}: {
  diagnostic: GuideV2Diagnostic | null;
  loading: boolean;
  submitting: boolean;
  disabled: boolean;
  onSubmit: (answers: GuideV2DiagnosticAnswer[]) => void;
}) {
  const [answers, setAnswers] = useState<Record<string, GuideV2DiagnosticValue>>({});
  const questions = diagnostic?.questions ?? [];
  const requiredAnswered = questions
    .filter((question) => question.type !== "multi_select")
    .every((question) => answers[question.question_id] !== undefined && String(answers[question.question_id]).length > 0);
  const answerCount = questions.filter((question) => {
    const value = answers[question.question_id];
    return Array.isArray(value) ? value.length > 0 : value !== undefined && String(value).length > 0;
  }).length;

  const setAnswer = (questionId: string, value: GuideV2DiagnosticValue) => {
    setAnswers((current) => ({ ...current, [questionId]: value }));
  };

  const toggleMulti = (questionId: string, value: string) => {
    setAnswers((current) => {
      const existing = Array.isArray(current[questionId]) ? current[questionId] as string[] : [];
      return {
        ...current,
        [questionId]: existing.includes(value) ? existing.filter((item) => item !== value) : [...existing, value],
      };
    });
  };

  const submit = () => {
    const payload = questions
      .map((question) => ({
        question_id: question.question_id,
        value: answers[question.question_id],
      }))
      .filter((item): item is GuideV2DiagnosticAnswer => item.value !== undefined);
    if (!payload.length || !requiredAnswered || submitting || disabled) return;
    onSubmit(payload);
  };

  return (
    <section className="rounded-lg border border-line bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="grid size-10 place-items-center rounded-lg border border-red-100 bg-red-50 text-brand-red">
            <Brain size={20} />
          </div>
          <div>
            <h2 className="text-base font-semibold text-ink">学习画像前测</h2>
            <p className="mt-1 text-sm leading-6 text-slate-500">
              {diagnostic?.summary || "创建路线后，用几个问题校准基础、偏好和薄弱点。"}
            </p>
          </div>
        </div>
        {loading ? (
          <Loader2 size={16} className="animate-spin text-brand-teal" />
        ) : (
          <Badge tone={diagnostic?.status === "completed" ? "success" : "warning"}>
            {diagnosticStatusLabel(diagnostic?.status || "pending")}
          </Badge>
        )}
      </div>

      {diagnostic?.last_result?.recommendations?.length ? (
        <div className="mt-4 rounded-lg border border-line bg-canvas p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-semibold text-ink">最近诊断建议</p>
            {diagnostic.last_result.readiness_score !== undefined ? (
              <Badge tone={effectStatusTone(Number(diagnostic.last_result.readiness_score) * 100)}>
                {Math.round(Number(diagnostic.last_result.readiness_score) * 100)}%
              </Badge>
            ) : null}
          </div>
          {diagnostic.last_result.bottleneck_label ? (
            <p className="mt-2 text-xs leading-5 text-brand-teal">
              当前卡点：{diagnostic.last_result.bottleneck_label}
            </p>
          ) : null}
          <div className="mt-2 space-y-1">
            {diagnostic.last_result.recommendations.slice(0, 3).map((item) => (
              <p key={item} className="text-xs leading-5 text-slate-600">• {item}</p>
            ))}
          </div>
          {diagnostic.last_result.learning_strategy?.length ? (
            <div className="mt-3 grid gap-2 sm:grid-cols-3">
              {diagnostic.last_result.learning_strategy.slice(0, 3).map((item) => (
                <div key={`${item.phase}-${item.action}`} className="rounded-lg border border-line bg-white p-3">
                  <Badge tone="neutral">{item.phase || "策略"}</Badge>
                  <p className="mt-2 line-clamp-3 text-xs font-medium leading-5 text-ink">{item.action}</p>
                  {item.success_check ? (
                    <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-500">{item.success_check}</p>
                  ) : null}
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="mt-4 space-y-3">
        {questions.slice(0, 7).map((question) => (
          <div key={question.question_id} className="rounded-lg border border-line bg-canvas p-3">
            <p className="text-sm font-medium leading-6 text-ink">{question.prompt}</p>
            {question.type === "scale" ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {Array.from({ length: Number(question.max ?? 5) - Number(question.min ?? 1) + 1 }, (_item, index) => Number(question.min ?? 1) + index).map((value) => (
                  <button
                    key={value}
                    type="button"
                    disabled={disabled || submitting}
                    onClick={() => setAnswer(question.question_id, value)}
                    className={`min-h-9 min-w-9 rounded-lg border px-3 text-sm font-semibold transition disabled:cursor-not-allowed ${
                      answers[question.question_id] === value ? "border-teal-200 bg-teal-50 text-brand-teal" : "border-line bg-white text-slate-600 hover:border-teal-200"
                    }`}
                    title={question.labels?.[String(value)]}
                  >
                    {value}
                  </button>
                ))}
              </div>
            ) : question.type === "multi_select" ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {(question.options ?? []).map((option) => {
                  const current = answers[question.question_id];
                  const selected = Array.isArray(current) && current.includes(option.value);
                  return (
                    <button
                      key={option.value}
                      type="button"
                      disabled={disabled || submitting}
                      onClick={() => toggleMulti(question.question_id, option.value)}
                      className={`rounded-lg border px-3 py-2 text-sm transition disabled:cursor-not-allowed ${
                        selected ? "border-teal-200 bg-teal-50 text-brand-teal" : "border-line bg-white text-slate-600 hover:border-teal-200"
                      }`}
                    >
                      {option.label}
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="mt-3 grid gap-2 sm:grid-cols-3">
                {(question.options ?? []).map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    disabled={disabled || submitting}
                    onClick={() => setAnswer(question.question_id, option.value)}
                    className={`rounded-lg border px-3 py-2 text-left text-sm transition disabled:cursor-not-allowed ${
                      answers[question.question_id] === option.value ? "border-teal-200 bg-teal-50 text-brand-teal" : "border-line bg-white text-slate-600 hover:border-teal-200"
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-slate-500">已回答 {answerCount}/{questions.length} 项，多选题可留空。</p>
        <Button tone="primary" disabled={!questions.length || !requiredAnswered || disabled || submitting} onClick={submit}>
          {submitting ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
          提交前测并调整路线
        </Button>
      </div>
    </section>
  );
}

function KnowledgeMapVisualization({
  nodes,
  mastery,
  tasks,
  currentTask,
}: {
  nodes: Array<Record<string, unknown>>;
  mastery: Record<string, Record<string, unknown>>;
  tasks: GuideV2Task[];
  currentTask: GuideV2Task | null;
}) {
  const currentNodeId = currentTask?.node_id || "";
  const [selectedNodeId, setSelectedNodeId] = useState("");

  const items = useMemo(
    () =>
      nodes.map((node, index) => {
        const nodeId = readString(node, "node_id") || `N${index + 1}`;
        const nodeMastery = mastery[nodeId] ?? {};
        const nodeTasks = tasks.filter((task) => task.node_id === nodeId);
        const completedTasks = nodeTasks.filter((task) => task.status === "completed").length;
        const status = readString(nodeMastery, "status") || readString(node, "status") || "not_started";
        return {
          node,
          nodeId,
          index,
          title: readString(node, "title") || nodeId,
          description: readString(node, "description") || "等待路线生成。",
          difficulty: readString(node, "difficulty") || "medium",
          target: readString(node, "mastery_target"),
          prerequisites: extractStringArray(node.prerequisites),
          strategies: extractStringArray(node.resource_strategy),
          tags: extractStringArray(node.tags),
          mastery: nodeMastery,
          status,
          score: scorePercent(nodeMastery.mastery_score ?? nodeMastery.score ?? node.mastery_score),
          tasks: nodeTasks,
          completedTasks,
          isCurrent: currentNodeId === nodeId,
        };
      }),
    [currentNodeId, mastery, nodes, tasks],
  );

  useEffect(() => {
    if (!items.length) {
      setSelectedNodeId("");
      return;
    }
    setSelectedNodeId((current) => {
      if (current && items.some((item) => item.nodeId === current)) return current;
      return currentNodeId || items[0].nodeId;
    });
  }, [currentNodeId, items]);

  if (!items.length) {
    return <p className="mt-4 rounded-lg border border-dashed border-line bg-canvas p-4 text-sm text-slate-500">生成路线后展示知识地图。</p>;
  }

  const selected = items.find((item) => item.nodeId === selectedNodeId) ?? items[0];
  const masteredCount = items.filter((item) => item.status === "mastered").length;
  const completedTaskCount = tasks.filter((task) => task.status === "completed").length;
  const currentIndex = Math.max(0, items.findIndex((item) => item.isCurrent));
  const averageMastery = Math.round(items.reduce((sum, item) => sum + item.score, 0) / items.length);
  const selectedDone = selected.status === "mastered" || (selected.tasks.length > 0 && selected.completedTasks === selected.tasks.length);

  return (
    <div className="mt-4 space-y-4">
      <div className="rounded-lg border border-teal-200 bg-teal-50 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-brand-teal">Learning Map</p>
            <h3 className="mt-1 text-lg font-semibold text-ink">从起点到掌握的路线</h3>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-teal-800">
              当前在第 {currentIndex + 1} 步。点击任意知识点，可以查看它的目标、掌握度和对应任务。
            </p>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="rounded-lg border border-teal-200 bg-white px-3 py-2">
              <p className="text-lg font-semibold text-ink">{items.length}</p>
              <p className="text-xs text-slate-500">知识点</p>
            </div>
            <div className="rounded-lg border border-teal-200 bg-white px-3 py-2">
              <p className="text-lg font-semibold text-ink">{masteredCount}</p>
              <p className="text-xs text-slate-500">已掌握</p>
            </div>
            <div className="rounded-lg border border-teal-200 bg-white px-3 py-2">
              <p className="text-lg font-semibold text-ink">{averageMastery}%</p>
              <p className="text-xs text-slate-500">平均</p>
            </div>
          </div>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-line bg-white p-4 shadow-sm">
        <div className="flex min-w-max items-stretch">
          {items.map((item, index) => {
            const active = item.nodeId === selected.nodeId;
            const done = item.status === "mastered" || (item.tasks.length > 0 && item.completedTasks === item.tasks.length);
            const style = knowledgeNodeStyle(item.status, active, item.isCurrent, done);
            return (
              <div key={item.nodeId} className="flex items-center">
                <button
                  type="button"
                  onClick={() => setSelectedNodeId(item.nodeId)}
                  className={`min-h-40 w-40 rounded-lg border p-3 text-left transition hover:-translate-y-0.5 hover:shadow-sm ${style.card}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className={`flex size-9 items-center justify-center rounded-full border text-sm font-semibold ${style.dot}`}>
                      {done ? <CheckCircle2 size={17} /> : index + 1}
                    </span>
                    <Badge tone={item.isCurrent ? "brand" : masteryTone(item.status)}>{item.isCurrent ? "当前" : masteryStatusLabel(item.status)}</Badge>
                  </div>
                  <span className="mt-3 block line-clamp-2 min-h-10 text-sm font-semibold leading-5 text-ink">{item.title}</span>
                  <span className="mt-2 block line-clamp-2 text-xs leading-5 text-slate-500">{item.description}</span>
                  <div className="mt-3">
                    <div className="flex items-center justify-between text-xs text-slate-500">
                      <span>掌握</span>
                      <span>{item.score}%</span>
                    </div>
                    <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100">
                      <div className={`h-full rounded-full ${style.bar}`} style={{ width: `${item.score}%` }} />
                    </div>
                  </div>
                  <span className="mt-3 block text-xs text-slate-500">{item.completedTasks}/{item.tasks.length || 0} 个任务完成</span>
                </button>
                {index < items.length - 1 ? (
                  <div className="flex h-full items-center px-2">
                    <div className={`h-0.5 w-8 ${done ? "bg-emerald-300" : "bg-slate-200"}`} />
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      </div>

      <motion.div
        key={selected.nodeId}
        className="grid gap-4 rounded-lg border border-line bg-white p-4 shadow-sm lg:grid-cols-[minmax(0,1fr)_280px]"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.18 }}
      >
        <div className="rounded-lg border border-line bg-canvas p-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={selected.isCurrent ? "brand" : masteryTone(selected.status)}>
              {selected.isCurrent ? "当前" : masteryStatusLabel(selected.status)}
            </Badge>
            <Badge tone="neutral">Step {selected.index + 1}</Badge>
            <Badge tone="neutral">{selected.difficulty}</Badge>
          </div>
          <h3 className="mt-3 text-lg font-semibold text-ink">{selected.title}</h3>
          <p className="mt-2 text-sm leading-6 text-slate-600">{selected.description}</p>
          {selected.target ? (
            <div className="mt-4 rounded-lg border border-teal-200 bg-white p-3">
              <p className="text-xs font-semibold text-brand-teal">掌握目标</p>
              <p className="mt-1 text-sm leading-6 text-teal-800">{selected.target}</p>
            </div>
          ) : null}
          <div className="mt-4 flex flex-wrap gap-2">
            {selected.prerequisites.slice(0, 4).map((item) => (
              <Badge key={`pre-${item}`} tone="neutral">前置：{item}</Badge>
            ))}
            {selected.strategies.slice(0, 4).map((item) => (
              <Badge key={`strategy-${item}`} tone="brand">{item}</Badge>
            ))}
            {!selected.prerequisites.length && !selected.strategies.length && selected.tags.slice(0, 4).map((item) => (
              <Badge key={`tag-${item}`} tone="neutral">{item}</Badge>
            ))}
          </div>
        </div>
        <div className="rounded-lg border border-line bg-white p-4">
          <div className="grid place-items-center">
            <div className="relative grid size-28 place-items-center rounded-full border border-line bg-canvas">
              <div
                className="absolute inset-2 rounded-full"
                style={{ background: `conic-gradient(#0F766E ${selected.score * 3.6}deg, #E2E8F0 0deg)` }}
              />
              <div className="relative grid size-20 place-items-center rounded-full border border-line bg-white">
                <div className="text-center">
                  <p className="text-2xl font-semibold text-ink">{selected.score}%</p>
                  <p className="text-xs text-slate-500">掌握</p>
                </div>
              </div>
            </div>
            <Badge tone={selectedDone ? "success" : masteryTone(selected.status)}>{selectedDone ? "节点完成" : masteryStatusLabel(selected.status)}</Badge>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <EvalMini label="任务" value={selected.tasks.length} />
            <EvalMini label="完成" value={selected.completedTasks} />
          </div>
          <p className="mt-3 rounded-lg border border-line bg-canvas p-2 text-xs leading-5 text-slate-600">
            建议：先完成当前节点任务，再进入下一步，路线会根据练习反馈自动调整。
          </p>
        </div>
      </motion.div>

      <div className="rounded-lg border border-line bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold text-ink">行动清单</h3>
            <p className="mt-1 text-xs text-slate-500">只展示当前选中知识点的任务。</p>
          </div>
          <Badge tone="neutral">{selected.tasks.length} 个</Badge>
        </div>
        <div className="mt-3 space-y-2">
          {selected.tasks.map((task) => (
            <TaskRow key={task.task_id} task={task} active={task.task_id === currentTask?.task_id} />
          ))}
          {!selected.tasks.length ? (
            <p className="rounded-lg bg-canvas p-3 text-sm text-slate-500">这个知识点暂时没有单独任务。</p>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function StudyPlanPanel({
  plan,
  loading,
}: {
  plan: GuideV2StudyPlan | null;
  loading: boolean;
}) {
  const blocks = plan?.blocks ?? [];
  const checkpoints = plan?.checkpoints ?? [];
  const remainingMinutes = Number(plan?.remaining_minutes ?? 0);
  const effectAssessment = plan?.effect_assessment;
  return (
    <section className="rounded-lg border border-line bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="grid size-10 place-items-center rounded-lg border border-teal-200 bg-teal-50 text-brand-teal">
            <CalendarDays size={20} />
          </div>
          <div>
            <h2 className="text-base font-semibold text-ink">学习日程与检查点</h2>
            <p className="mt-1 text-sm leading-6 text-slate-500">
              {plan?.summary || "创建路线后，这里会把任务拆成每次学习可执行的安排。"}
            </p>
          </div>
        </div>
        {loading ? (
          <Loader2 size={16} className="animate-spin text-brand-teal" />
        ) : (
          <Badge tone={blocks.length ? "brand" : "neutral"}>{blocks.length || 0} 次学习</Badge>
        )}
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <EvalMini label="单次预算" value={Number(plan?.daily_time_budget ?? 0)} suffix="m" />
        <EvalMini label="剩余时间" value={remainingMinutes} suffix="m" />
        <EvalMini label="检查点" value={checkpoints.length} />
      </div>
      {effectAssessment ? (
        <div className="mt-4 rounded-lg border border-line bg-canvas p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-semibold text-ink">路径调度依据</p>
            <Badge tone={effectStatusTone(effectAssessment.score)}>{effectAssessment.label || Number(effectAssessment.score ?? 0)}</Badge>
          </div>
          <p className="mt-2 text-xs leading-5 text-slate-600">
            {effectAssessment.summary || "学习日程会根据效果评估动态调整优先级。"}
          </p>
        </div>
      ) : null}

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        {blocks.slice(0, 4).map((block) => {
          const completed = Number(block.completed_tasks ?? 0);
          const total = Number(block.total_tasks ?? 0);
          const progress = total ? Math.round((completed / total) * 100) : 0;
          return (
            <motion.div
              key={block.id}
              className="rounded-lg border border-line bg-canvas p-4"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.16 }}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h3 className="text-sm font-semibold text-ink">{block.title}</h3>
                  <p className="mt-1 line-clamp-1 text-xs text-slate-500">{block.focus || "学习块"}</p>
                </div>
                <Badge tone={planStatusTone(block.status || "")}>{planStatusLabel(block.status || "")}</Badge>
              </div>
              <ProgressBar value={progress} className="mt-3" />
              <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
                <Badge tone="neutral">{block.estimated_minutes ?? 0} 分钟</Badge>
                <Badge tone="neutral">{completed}/{total} 任务</Badge>
              </div>
              <div className="mt-3 space-y-2">
                {(block.tasks ?? []).slice(0, 2).map((task) => (
                  <p key={task.task_id || task.title} className="line-clamp-1 rounded-lg bg-white px-3 py-2 text-xs text-slate-600">
                    {task.title || task.task_id}
                  </p>
                ))}
              </div>
              {(block.recommended_actions ?? []).length ? (
                <p className="mt-3 text-xs leading-5 text-slate-600">{block.recommended_actions?.[0]}</p>
              ) : null}
            </motion.div>
          );
        })}
        {!blocks.length ? (
          <p className="rounded-lg border border-dashed border-line bg-canvas p-4 text-sm text-slate-500">
            暂无日程。先创建一条导学路线。
          </p>
        ) : null}
      </div>

      {checkpoints.length ? (
        <div className="mt-4 rounded-lg border border-line bg-canvas p-4">
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm font-semibold text-ink">下一次检查</p>
            <Badge tone={planStatusTone(String(plan?.next_checkpoint?.status || checkpoints[0]?.status || ""))}>
              {planStatusLabel(String(plan?.next_checkpoint?.status || checkpoints[0]?.status || ""))}
            </Badge>
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            {String(plan?.next_checkpoint?.title || checkpoints[0]?.title || "学习复盘")}
          </p>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            {String(plan?.next_checkpoint?.trigger || checkpoints[0]?.trigger || "完成当前学习块后检查。")}
          </p>
        </div>
      ) : null}

      {plan?.rules?.length ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {plan.rules.slice(0, 3).map((rule) => (
            <Badge key={rule} tone="neutral">{rule}</Badge>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function CourseSyllabusPanel({ metadata }: { metadata: Record<string, unknown> }) {
  const outcomes = Array.isArray(metadata.learning_outcomes) ? metadata.learning_outcomes.map(String) : [];
  const weeklySchedule = Array.isArray(metadata.weekly_schedule) ? metadata.weekly_schedule : [];
  const assessment = Array.isArray(metadata.assessment) ? metadata.assessment : [];
  const milestones = Array.isArray(metadata.project_milestones) ? metadata.project_milestones : [];
  if (!Object.keys(metadata).length) return null;
  return (
    <section className="rounded-lg border border-line bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-ink">课程大纲</h2>
          <p className="mt-1 text-sm leading-6 text-slate-500">
            {String(metadata.course_name || "完整课程")} · {String(metadata.suggested_weeks || "-")} 周 · {String(metadata.credits || "-")} 学分建议
          </p>
        </div>
        <Badge tone="brand">{String(metadata.course_id || "COURSE")}</Badge>
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-[1fr_1.2fr]">
        <div className="space-y-3">
          <div className="rounded-lg border border-line bg-canvas p-3">
            <p className="text-sm font-semibold text-ink">学习目标</p>
            <div className="mt-2 space-y-2">
              {outcomes.slice(0, 4).map((item) => (
                <p key={item} className="text-xs leading-5 text-slate-600">• {item}</p>
              ))}
            </div>
          </div>
          <div className="rounded-lg border border-line bg-canvas p-3">
            <p className="text-sm font-semibold text-ink">考核构成</p>
            <div className="mt-2 grid grid-cols-2 gap-2">
              {assessment.slice(0, 4).map((raw) => {
                const item = asRecord(raw) ?? {};
                return (
                  <div key={String(item.name)} className="rounded-lg bg-white p-2">
                    <p className="line-clamp-1 text-xs text-slate-500">{String(item.name || "考核")}</p>
                    <p className="mt-1 text-sm font-semibold text-ink">{String(item.weight || 0)}%</p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
        <div className="rounded-lg border border-line bg-canvas p-3">
          <p className="text-sm font-semibold text-ink">周次安排</p>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {weeklySchedule.slice(0, 8).map((raw, index) => {
              const item = asRecord(raw) ?? {};
              return (
                <div key={`${item.week || index}`} className="rounded-lg border border-line bg-white p-3">
                  <Badge tone="neutral">第 {String(item.week || index + 1)} 周</Badge>
                  <p className="mt-2 line-clamp-2 text-sm font-medium text-ink">{String(item.topic || "学习主题")}</p>
                  <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{String(item.deliverable || "阶段产出")}</p>
                </div>
              );
            })}
          </div>
        </div>
      </div>
      {milestones.length ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {milestones.slice(0, 4).map((raw) => {
            const item = asRecord(raw) ?? {};
            return <Badge key={String(item.stage)} tone="neutral">{String(item.stage || "里程碑")}</Badge>;
          })}
        </div>
      ) : null}
    </section>
  );
}

function LearningReportPanel({
  report,
  loading,
  canSave,
  saving,
  onSave,
}: {
  report: GuideV2LearningReport | null;
  loading: boolean;
  canSave: boolean;
  saving: boolean;
  onSave: () => void;
}) {
  const overview = report?.overview ?? {};
  const nodes = report?.node_cards ?? [];
  const score = Number(overview.overall_score ?? 0);
  const progress = Number(overview.progress ?? 0);
  const behavior = report?.behavior_summary ?? {};
  const behaviorTags = report?.behavior_tags ?? [];
  const feedbackDigest = report?.feedback_digest;
  const latestFeedback = feedbackDigest?.latest;
  const effectAssessment = report?.effect_assessment;
  const effectDimensions = effectAssessment?.dimensions ?? [];
  const timelineEvents = report?.timeline_events ?? [];
  const mistakeReview = report?.mistake_review;
  const mistakeSummary = mistakeReview?.summary ?? {};
  const mistakeClusters = mistakeReview?.clusters ?? [];
  return (
    <section className="rounded-lg border border-line bg-white p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <BarChart3 size={18} className="text-brand-teal" />
          <h2 className="text-base font-semibold text-ink">学习效果报告</h2>
        </div>
        {loading ? <Loader2 size={16} className="animate-spin text-brand-teal" /> : <Badge tone={score >= 80 ? "success" : score >= 60 ? "brand" : "warning"}>{score || 0}</Badge>}
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-600">
        {report?.summary || "完成任务后，这里会汇总学习画像、薄弱点、路径调整和下一步计划。"}
      </p>
      <div className="mt-4 grid grid-cols-2 gap-2">
        <EvalMini label="进度" value={progress} suffix="%" />
        <EvalMini label="调整" value={Number(overview.path_adjustment_count ?? 0)} suffix="次" />
      </div>
      <div className="mt-4 rounded-lg border border-line bg-white p-3">
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm font-semibold text-ink">效果评估</p>
          <Badge tone={effectStatusTone(effectAssessment?.score)}>{effectAssessment?.label || "待评估"}</Badge>
        </div>
        <div className="mt-3 grid grid-cols-[72px_1fr] items-center gap-3">
          <div className="flex h-[72px] w-[72px] items-center justify-center rounded-lg border border-line bg-canvas">
            <span className="text-xl font-semibold text-brand-teal">{Number(effectAssessment?.score ?? 0)}</span>
          </div>
          <p className="text-xs leading-5 text-slate-600">
            {effectAssessment?.summary || "系统会结合任务进度、掌握程度、行为证据、错因闭环和反馈质量，给出可执行的学习效果判断。"}
          </p>
        </div>
        {effectDimensions.length ? (
          <div className="mt-3 space-y-2">
            {effectDimensions.slice(0, 5).map((dimension) => (
              <div key={dimension.id || dimension.label} className="rounded-lg border border-line bg-canvas p-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-ink">{dimension.label || dimension.id || "维度"}</span>
                  <Badge tone={effectStatusTone(dimension.score)}>{Number(dimension.score ?? 0)}</Badge>
                </div>
                <ProgressBar value={Number(dimension.score ?? 0)} className="mt-2" />
                <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-500">{dimension.evidence || "暂无证据。"}</p>
              </div>
            ))}
          </div>
        ) : null}
        {effectAssessment?.strategy_adjustments?.length ? (
          <div className="mt-3 space-y-2">
            {effectAssessment.strategy_adjustments.slice(0, 3).map((item) => (
              <p key={item} className="rounded-lg border border-teal-100 bg-teal-50 p-2 text-xs leading-5 text-teal-800">
                {item}
              </p>
            ))}
          </div>
        ) : null}
      </div>
      <div className="mt-4 rounded-lg border border-line bg-canvas p-3">
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm font-semibold text-ink">行为证据</p>
          <Badge tone="neutral">{Number(behavior.event_count ?? 0)} 条</Badge>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <EvalMini label="资源" value={Number(behavior.resource_count ?? 0)} suffix="个" />
          <EvalMini label="练习" value={Number(behavior.quiz_attempt_count ?? 0)} suffix="次" />
          <EvalMini label="证据" value={Number(behavior.evidence_count ?? 0)} suffix="条" />
          <EvalMini label="画像" value={Number(behavior.profile_update_count ?? 0)} suffix="次" />
        </div>
        {behaviorTags.length ? (
          <div className="mt-3 flex flex-wrap gap-2">
            {behaviorTags.slice(0, 5).map((tag) => (
              <Badge key={tag} tone="brand">{tag}</Badge>
            ))}
          </div>
        ) : null}
        {timelineEvents.length ? (
          <div className="mt-3 space-y-2">
            {timelineEvents.slice(0, 3).map((event) => (
              <div key={event.id} className="rounded-lg border border-line bg-white p-2">
                <div className="flex items-center justify-between gap-2">
                  <Badge tone={timelineEventTone(event.type)}>{event.label || timelineEventLabel(event.type)}</Badge>
                  <span className="text-[11px] text-slate-400">{formatTime(event.created_at)}</span>
                </div>
                <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-600">{event.title || event.description}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-3 text-xs leading-5 text-slate-500">完成诊断、练习或资源生成后，会自动形成可追溯轨迹。</p>
        )}
      </div>
      <div className="mt-4 rounded-lg border border-line bg-white p-3">
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm font-semibold text-ink">反馈摘要</p>
          <Badge tone={Number(feedbackDigest?.warning_count ?? 0) ? "warning" : Number(feedbackDigest?.count ?? 0) ? "success" : "neutral"}>
            {Number(feedbackDigest?.count ?? 0)} 次
          </Badge>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <EvalMini label="稳定" value={Number(feedbackDigest?.success_count ?? 0)} suffix="次" />
          <EvalMini label="需干预" value={Number(feedbackDigest?.warning_count ?? 0)} suffix="次" />
        </div>
        {latestFeedback ? (
          <div className="mt-3 rounded-lg border border-line bg-canvas p-2">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={feedbackTone(latestFeedback.tone)}>{latestFeedback.score_percent == null ? "反馈" : `${latestFeedback.score_percent}%`}</Badge>
              {latestFeedback.task_title ? <span className="text-[11px] text-slate-400">{latestFeedback.task_title}</span> : null}
            </div>
            <p className="mt-2 line-clamp-1 text-xs font-semibold text-ink">{latestFeedback.title || "学习反馈"}</p>
            <p className="mt-1 line-clamp-3 text-xs leading-5 text-slate-600">{latestFeedback.summary || "系统已根据学习证据更新路线。"}</p>
          </div>
        ) : (
          <p className="mt-3 text-xs leading-5 text-slate-500">完成任务后会沉淀即时反馈，辅助复盘学习效果。</p>
        )}
      </div>
      <div className="mt-4 rounded-lg border border-line bg-white p-3">
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm font-semibold text-ink">错因复测</p>
          <Badge tone={Number(mistakeSummary.pending_retest_count ?? 0) ? "warning" : "neutral"}>
            {Number(mistakeSummary.cluster_count ?? 0)} 类
          </Badge>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <EvalMini label="低分" value={Number(mistakeSummary.low_score_evidence_count ?? 0)} suffix="条" />
          <EvalMini label="待复测" value={Number(mistakeSummary.pending_retest_count ?? 0)} suffix="个" />
        </div>
        {mistakeClusters.length ? (
          <div className="mt-3 space-y-2">
            {mistakeClusters.slice(0, 2).map((cluster) => (
              <p key={cluster.label} className="rounded-lg border border-line bg-canvas p-2 text-xs leading-5 text-slate-600">
                <span className="font-semibold text-ink">{cluster.label}</span>：{cluster.suggested_action || "复测并记录修正后的理解。"}
              </p>
            ))}
          </div>
        ) : (
          <p className="mt-3 text-xs leading-5 text-slate-500">暂无错因聚类，提交练习或低分反思后自动生成。</p>
        )}
      </div>
      <div className="mt-4 space-y-2">
        {nodes.slice(0, 3).map((node) => (
          <div key={node.node_id || node.title} className="rounded-lg border border-line bg-canvas p-3">
            <div className="flex items-center justify-between gap-2">
              <p className="line-clamp-1 text-sm font-semibold text-ink">{node.title || node.node_id}</p>
              <Badge tone={masteryTone(node.status || "")}>{Math.round(Number(node.mastery_score ?? 0) * 100)}%</Badge>
            </div>
            <p className="mt-2 text-xs leading-5 text-slate-600">{node.suggestion || "继续完成任务并留下学习证据。"}</p>
          </div>
        ))}
        {!nodes.length ? <p className="rounded-lg bg-canvas p-3 text-sm text-slate-500">暂无知识点报告。</p> : null}
      </div>
      <EvalList title="风险" items={report?.risks ?? []} empty="当前没有明显风险信号。" tone="warning" />
      <EvalList title="下一步" items={report?.next_plan ?? []} empty="完成任务后生成下一步计划。" tone="brand" />
      <Button tone="secondary" className="mt-4 w-full" disabled={!canSave || saving || !report} onClick={onSave}>
        {saving ? <Loader2 size={16} className="animate-spin" /> : <BookOpen size={16} />}
        保存报告到 Notebook
      </Button>
    </section>
  );
}

function CoursePackagePanel({
  coursePackage,
  loading,
  canSave,
  saving,
  onSave,
}: {
  coursePackage: GuideV2CoursePackage | null;
  loading: boolean;
  canSave: boolean;
  saving: boolean;
  onSave: () => void;
}) {
  const project = coursePackage?.capstone_project ?? {};
  const rubric = coursePackage?.rubric ?? [];
  const review = coursePackage?.review_plan ?? [];
  const report = coursePackage?.learning_report ?? {};
  const behavior = report.behavior_summary ?? {};
  const behaviorTags = report.behavior_tags ?? [];
  const recentEvents = report.recent_timeline_events ?? [];
  const effectAssessment = report.effect_assessment;
  return (
    <section className="rounded-lg border border-line bg-white p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <GraduationCap size={18} className="text-brand-teal" />
          <h2 className="text-base font-semibold text-ink">课程产出包</h2>
        </div>
        {loading ? <Loader2 size={16} className="animate-spin text-brand-teal" /> : <Badge tone="brand">{project.estimated_minutes ?? "-"}m</Badge>}
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-600">
        {coursePackage?.summary || "系统会把学习路径整理成最终项目、评分标准、复习计划和作品集索引。"}
      </p>
      <div className="mt-4 rounded-lg border border-line bg-canvas p-3">
        <p className="text-sm font-semibold text-ink">{project.title || "学习成果项目"}</p>
        <p className="mt-2 line-clamp-4 text-xs leading-5 text-slate-600">{project.scenario || "完成更多学习任务后会生成更贴合你的项目说明。"}</p>
      </div>
      <div className="mt-4 rounded-lg border border-line bg-white p-3">
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm font-semibold text-ink">产出依据</p>
          <Badge tone="neutral">{Number(behavior.event_count ?? 0)} 条行为</Badge>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <EvalMini label="掌握" value={Number(report.overall_score ?? 0)} />
          <EvalMini label="进度" value={Number(report.progress ?? 0)} suffix="%" />
          <EvalMini label="资源" value={Number(behavior.resource_count ?? 0)} suffix="个" />
          <EvalMini label="练习" value={Number(behavior.quiz_attempt_count ?? 0)} suffix="次" />
        </div>
        {behaviorTags.length ? (
          <div className="mt-3 flex flex-wrap gap-2">
            {behaviorTags.slice(0, 4).map((tag) => (
              <Badge key={tag} tone="brand">{tag}</Badge>
            ))}
          </div>
        ) : null}
        {recentEvents.length ? (
          <p className="mt-3 line-clamp-2 text-xs leading-5 text-slate-500">
            最近：{recentEvents.slice(0, 2).map((event) => event.title || event.description || event.type).join(" / ")}
          </p>
        ) : null}
        {effectAssessment ? (
          <div className="mt-3 rounded-lg border border-line bg-canvas p-2">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-semibold text-ink">学习效果</p>
              <Badge tone={effectStatusTone(effectAssessment.score)}>{effectAssessment.label || Number(effectAssessment.score ?? 0)}</Badge>
            </div>
            <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-600">{effectAssessment.summary || "已生成学习效果评估。"}</p>
          </div>
        ) : null}
      </div>
      <div className="mt-4 space-y-2">
        {rubric.slice(0, 3).map((item) => (
          <div key={item.criterion} className="rounded-lg border border-line bg-white p-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-semibold text-ink">{item.criterion}</p>
              <Badge tone="neutral">{item.weight ?? 0}%</Badge>
            </div>
            <p className="mt-1 text-xs leading-5 text-slate-500">{item.baseline || item.excellent}</p>
          </div>
        ))}
      </div>
      <EvalList
        title="复习重点"
        items={review.slice(0, 3).map((item) => `${item.title || "知识点"}：${item.action || ""}`)}
        empty="完成更多任务后生成复习计划。"
        tone="brand"
      />
      <Button tone="secondary" className="mt-4 w-full" disabled={!canSave || saving || !coursePackage} onClick={onSave}>
        {saving ? <Loader2 size={16} className="animate-spin" /> : <BookOpen size={16} />}
        保存产出包到 Notebook
      </Button>
    </section>
  );
}

function ResourcePushPanel({
  recommendations,
  loading,
  disabled,
  generatingType,
  onGenerate,
}: {
  recommendations: GuideV2ResourceRecommendation[];
  loading: boolean;
  disabled: boolean;
  generatingType: GuideV2ResourceType | null;
  onGenerate: (item: GuideV2ResourceRecommendation) => void;
}) {
  const visibleRecommendations = recommendations.filter((item) => !isResearchResourceType(item.resource_type));
  return (
    <section className="rounded-lg border border-line bg-white p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Lightbulb size={18} className="text-brand-red" />
          <h2 className="text-base font-semibold text-ink">个性化资源推送</h2>
        </div>
        {loading ? <Loader2 size={16} className="animate-spin text-brand-teal" /> : <Badge tone="neutral">{visibleRecommendations.length} 条</Badge>}
      </div>
      <p className="mt-2 text-xs leading-5 text-slate-500">
        根据掌握度、练习证据、资源缺口和偏好，自动建议下一份资源。
      </p>
      <div className="mt-4 space-y-3">
        {visibleRecommendations.slice(0, 4).map((item) => {
          const type = normalizeResourceType(item.resource_type);
          const loadingThis = generatingType === type;
          return (
            <motion.div
              key={item.id}
              className="rounded-lg border border-line bg-canvas p-3"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.16 }}
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={priorityTone(item.priority)}>{priorityLabel(item.priority)}</Badge>
                <Badge tone="neutral">{resourceLabel(type)}</Badge>
                {item.capability ? <Badge tone="neutral">{item.capability}</Badge> : null}
              </div>
              <h3 className="mt-2 text-sm font-semibold leading-5 text-ink">{item.title}</h3>
              {item.target_task_title ? (
                <p className="mt-1 line-clamp-1 text-xs text-slate-500">面向任务：{item.target_task_title}</p>
              ) : null}
              <p className="mt-2 text-xs leading-5 text-slate-600">{item.reason}</p>
              <Button
                tone={item.priority === "high" ? "primary" : "secondary"}
                className="mt-3 min-h-8 w-full px-2 text-xs"
                disabled={disabled || loadingThis}
                onClick={() => onGenerate(item)}
              >
                {loadingThis ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
                按推荐生成
              </Button>
            </motion.div>
          );
        })}
        {!loading && !visibleRecommendations.length ? (
          <p className="rounded-lg bg-canvas p-3 text-sm leading-6 text-slate-500">
            完成一个任务或生成一次资源后，这里会给出更精准的下一步推送。
          </p>
        ) : null}
      </div>
    </section>
  );
}

function LearningTimelinePanel({
  timeline,
  loading,
}: {
  timeline: GuideV2LearningTimeline | null;
  loading: boolean;
}) {
  const summary = timeline?.summary ?? {};
  const recent = timeline?.recent_events ?? [];
  return (
    <section className="rounded-lg border border-line bg-white p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <ListChecks size={18} className="text-brand-teal" />
          <h2 className="text-base font-semibold text-ink">学习轨迹</h2>
        </div>
        {loading ? <Loader2 size={16} className="animate-spin text-brand-teal" /> : <Badge tone="brand">{summary.event_count ?? 0} 条</Badge>}
      </div>
      <p className="mt-2 text-xs leading-5 text-slate-500">
        汇总画像、资源、练习、任务和路径调整，用来支撑学习效果评估。
      </p>
      <div className="mt-4 grid grid-cols-2 gap-2">
        <EvalMini label="证据" value={Number(summary.evidence_count ?? 0)} />
        <EvalMini label="资源" value={Number(summary.resource_count ?? 0)} />
        <EvalMini label="练习" value={Number(summary.quiz_attempt_count ?? 0)} />
        <EvalMini label="调整" value={Number(summary.path_adjustment_count ?? 0)} />
      </div>
      {timeline?.behavior_tags?.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {timeline.behavior_tags.slice(0, 4).map((tag) => (
            <Badge key={tag} tone="neutral">{tag}</Badge>
          ))}
        </div>
      ) : null}
      <div className="mt-4 space-y-2">
        {recent.slice(0, 6).map((event) => (
          <motion.div
            key={event.id}
            className="rounded-lg border border-line bg-canvas p-3"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.15 }}
          >
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={timelineEventTone(event.type)}>{event.label || timelineEventLabel(event.type)}</Badge>
              <span className="text-xs text-slate-400">{formatTime(event.created_at)}</span>
              {event.score !== null && event.score !== undefined ? (
                <Badge tone={Number(event.score) >= 0.75 ? "success" : "warning"}>{Math.round(Number(event.score) * 100)}%</Badge>
              ) : null}
              {event.feedback_tone ? <Badge tone={feedbackTone(event.feedback_tone)}>反馈</Badge> : null}
            </div>
            <p className="mt-2 line-clamp-2 text-sm font-medium leading-5 text-ink">{event.title}</p>
            {event.feedback_title ? <p className="mt-1 line-clamp-1 text-xs font-semibold text-brand-teal">{event.feedback_title}</p> : null}
            {event.impact ? <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-600">{event.impact}</p> : null}
          </motion.div>
        ))}
        {!loading && !recent.length ? (
          <p className="rounded-lg bg-canvas p-3 text-sm leading-6 text-slate-500">
            创建路线后，学习行为会逐步沉淀在这里。
          </p>
        ) : null}
      </div>
    </section>
  );
}

function MistakeReviewPanel({
  review,
  loading,
  disabled,
  generatingType,
  onGenerate,
}: {
  review: GuideV2MistakeReview | null;
  loading: boolean;
  disabled: boolean;
  generatingType: GuideV2ResourceType | null;
  onGenerate: (type: GuideV2ResourceType, taskId: string, prompt: string) => void;
}) {
  const summary = review?.summary ?? {};
  const clusters = review?.clusters ?? [];
  const plan = review?.retest_plan ?? [];
  const remediationTasks = review?.remediation_tasks ?? [];
  const retestTasks = review?.retest_tasks ?? [];
  const pendingRemediation = remediationTasks.find((task) => task.status !== "completed" && task.status !== "skipped") ?? null;
  const pendingRetest = retestTasks.find((task) => task.status !== "completed" && task.status !== "skipped") ?? null;
  const primaryMistake = clusters[0]?.label || "当前错因";
  return (
    <section className="rounded-lg border border-line bg-white p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Target size={18} className="text-brand-red" />
          <h2 className="text-base font-semibold text-ink">错因闭环</h2>
        </div>
        {loading ? (
          <Loader2 size={16} className="animate-spin text-brand-teal" />
        ) : (
          <Badge tone={summary.closed_loop ? "success" : summary.pending_remediation_count || summary.pending_retest_count ? "warning" : clusters.length ? "brand" : "neutral"}>
            {clusters.length} 类
          </Badge>
        )}
      </div>
      <p className="mt-2 text-xs leading-5 text-slate-500">
        把错题、低分证据、补救任务和复测任务串起来，避免“看懂了但没补上”。
      </p>
      <div className="mt-4 grid grid-cols-2 gap-2">
        <EvalMini label="低分" value={Number(summary.low_score_evidence_count ?? 0)} suffix="条" />
        <EvalMini label="补救" value={Number(summary.pending_remediation_count ?? 0)} suffix="待做" />
        <EvalMini label="复测" value={Number(summary.pending_retest_count ?? 0)} suffix="待做" />
        <EvalMini label="关闭" value={Number(summary.closed_cluster_count ?? 0)} suffix="类" />
      </div>
      <div className="mt-4 space-y-2">
        {clusters.slice(0, 3).map((cluster) => (
          <div key={cluster.label} className="rounded-lg border border-line bg-canvas p-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={mistakeLoopStatusTone(cluster.loop_status)}>{mistakeLoopStatusLabel(cluster.loop_status)}</Badge>
              <Badge tone={mistakeSeverityTone(cluster.severity)}>{mistakeSeverityLabel(cluster.severity)}</Badge>
              <Badge tone="neutral">{cluster.count ?? 0} 次</Badge>
              {cluster.average_score !== null && cluster.average_score !== undefined ? (
                <Badge tone={Number(cluster.average_score) >= 0.7 ? "success" : "warning"}>{Math.round(Number(cluster.average_score) * 100)}%</Badge>
              ) : null}
              {cluster.latest_retest_score !== null && cluster.latest_retest_score !== undefined ? (
                <Badge tone={Number(cluster.latest_retest_score) >= 0.75 ? "success" : "warning"}>复测 {Math.round(Number(cluster.latest_retest_score) * 100)}%</Badge>
              ) : null}
            </div>
            <p className="mt-2 text-sm font-semibold text-ink">{cluster.label || "待识别错因"}</p>
            <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-600">{cluster.suggested_action || "完成复测并记录修正后的理解。"}</p>
          </div>
        ))}
        {!clusters.length ? <p className="rounded-lg bg-canvas p-3 text-sm leading-6 text-slate-500">提交练习或低分反思后，会自动形成错因聚类。</p> : null}
      </div>
      {plan.length ? (
        <div className="mt-4 rounded-lg border border-line bg-canvas p-3">
          <p className="text-sm font-semibold text-ink">复测计划</p>
          <div className="mt-2 space-y-2">
            {plan.slice(0, 3).map((item) => (
              <div key={`${item.step}-${item.title}`} className="flex gap-2 text-xs leading-5 text-slate-600">
                <Badge tone="neutral">{item.step ?? "-"}</Badge>
                <span>{item.title}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
      {(pendingRemediation || pendingRetest) ? (
        <div className="mt-4 grid gap-2">
          {pendingRemediation ? (
            <Button
              tone="secondary"
              className="w-full justify-start text-left text-xs"
              disabled={disabled || generatingType === "visual"}
              onClick={() =>
                onGenerate(
                  "visual",
                  pendingRemediation.task_id,
                  `围绕「${primaryMistake}」生成补救图解：先指出常见错误，再给出正确判断步骤和一个小例子。`,
                )
              }
            >
              {generatingType === "visual" ? <Loader2 size={14} className="animate-spin" /> : <Target size={14} />}
              生成补救图解
            </Button>
          ) : null}
          {pendingRetest ? (
            <Button
              tone="primary"
              className="w-full justify-start text-left text-xs"
              disabled={disabled || generatingType === "quiz"}
              onClick={() =>
                onGenerate(
                  "quiz",
                  pendingRetest.task_id,
                  `围绕「${primaryMistake}」生成 4 道复测题，包含选择题、判断题、填空题和简答题，并给出错因提示。`,
                )
              }
            >
              {generatingType === "quiz" ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
              生成复测题
            </Button>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function PlanEventsPanel({ events }: { events: GuideV2PlanEvent[] }) {
  const recent = events.slice(-4).reverse();
  return (
    <section className="rounded-lg border border-line bg-white p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Compass size={18} className="text-brand-teal" />
          <h2 className="text-base font-semibold text-ink">路径调整记录</h2>
        </div>
        <Badge tone={recent.length ? "brand" : "neutral"}>{events.length} 次</Badge>
      </div>
      <div className="mt-4 space-y-2">
        {recent.map((event) => (
          <div key={event.event_id} className="rounded-lg border border-line bg-canvas p-3 text-xs leading-5 text-slate-600">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={planEventTone(event.type)}>{planEventLabel(event.type)}</Badge>
              <span className="text-slate-400">{formatTime(event.created_at)}</span>
            </div>
            <p className="mt-2">{event.reason}</p>
          </div>
        ))}
        {!recent.length ? (
          <p className="rounded-lg bg-canvas p-3 text-sm leading-6 text-slate-500">
            完成任务后，系统会在这里记录补救、跳过或迁移挑战等路线变化。
          </p>
        ) : null}
      </div>
    </section>
  );
}
function EvaluationPanel({
  evaluation,
  loading,
}: {
  evaluation: GuideV2Evaluation | null;
  loading: boolean;
}) {
  const score = evaluation?.overall_score ?? 0;
  const mastery = evaluation?.mastery_distribution ?? {};
  const resources = evaluation?.resource_counts ?? {};
  return (
    <section className="rounded-lg border border-line bg-white p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <BarChart3 size={18} className="text-brand-teal" />
          <h2 className="text-base font-semibold text-ink">学习效果评估</h2>
        </div>
        {loading ? <Loader2 size={16} className="animate-spin text-brand-teal" /> : <Badge tone={score >= 80 ? "success" : score >= 60 ? "brand" : "warning"}>{evaluation?.readiness || "待开始"}</Badge>}
      </div>
      <div className="mt-4">
        <div className="flex items-end justify-between gap-3">
          <div>
            <p className="text-3xl font-semibold text-ink">{score}</p>
            <p className="text-xs text-slate-500">综合掌握分</p>
          </div>
          <div className="text-right text-xs text-slate-500">
            <p>{evaluation?.completed_tasks ?? 0}/{evaluation?.total_tasks ?? 0} 个任务</p>
            <p>{evaluation?.question_count ?? 0} 道练习题</p>
          </div>
        </div>
        <ProgressBar value={score} className="mt-3" />
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2">
        <EvalMini label="证据" value={evaluation?.evidence_count ?? 0} />
        <EvalMini label="平均分" value={Math.round((evaluation?.average_evidence_score ?? 0) * 100)} suffix="%" />
        <EvalMini label="已掌握" value={mastery.mastered ?? 0} />
        <EvalMini label="资源" value={Object.values(resources).reduce((sum, value) => sum + Number(value || 0), 0)} />
      </div>
      <EvalList title="优势" items={evaluation?.strengths ?? []} empty="完成任务后会出现优势判断。" tone="success" />
      <EvalList title="风险" items={evaluation?.risk_signals ?? []} empty="目前没有明显风险信号。" tone="warning" />
      <EvalList title="下一步" items={evaluation?.next_actions ?? []} empty="生成路线后给出建议。" tone="brand" />
    </section>
  );
}

function ProgressBar({ value, className = "" }: { value: number; className?: string }) {
  return (
    <div className={`h-2 overflow-hidden rounded-full bg-slate-100 ${className}`}>
      <div className="h-full rounded-full bg-brand-teal transition-all" style={{ width: `${Math.max(0, Math.min(value, 100))}%` }} />
    </div>
  );
}

function EvalMini({ label, value, suffix = "" }: { label: string; value: number | string; suffix?: string }) {
  return (
    <div className="rounded-lg border border-line bg-canvas p-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-ink">
        {value}
        {suffix}
      </p>
    </div>
  );
}

function EvalList({
  title,
  items,
  empty,
  tone,
}: {
  title: string;
  items: string[];
  empty: string;
  tone: "success" | "warning" | "brand";
}) {
  return (
    <div className="mt-4">
      <p className="text-xs font-semibold text-slate-500">{title}</p>
      <div className="mt-2 space-y-2">
        {(items.length ? items : [empty]).slice(0, 3).map((item) => (
          <p key={item} className="rounded-lg border border-line bg-canvas p-2 text-xs leading-5 text-slate-600">
            <Badge tone={items.length ? tone : "neutral"}>{title}</Badge>
            <span className="ml-2">{item}</span>
          </p>
        ))}
      </div>
    </div>
  );
}

function ResourceArtifactPager({
  artifacts,
  saveNotebookId,
  saving,
  quizSubmitting,
  onSave,
  onSubmitQuiz,
}: {
  artifacts: GuideV2Artifact[];
  saveNotebookId: string;
  saving: boolean;
  quizSubmitting: boolean;
  onSave: (artifact: GuideV2Artifact) => void;
  onSubmitQuiz: (artifact: GuideV2Artifact, answers: QuizResultItem[]) => void;
}) {
  const [activeIndex, setActiveIndex] = useState(0);
  const activeArtifact = artifacts[Math.min(activeIndex, Math.max(artifacts.length - 1, 0))];

  useEffect(() => {
    setActiveIndex((index) => Math.min(index, Math.max(artifacts.length - 1, 0)));
  }, [artifacts.length]);

  if (!activeArtifact) return null;

  return (
    <div className="rounded-lg border border-line bg-canvas p-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-ink">资源浏览</p>
          <p className="mt-1 text-xs text-slate-500">一次只看一个结果，避免页面堆满。</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            tone="secondary"
            className="min-h-8 px-2 text-xs"
            disabled={activeIndex <= 0}
            onClick={() => setActiveIndex((index) => Math.max(0, index - 1))}
          >
            上一个
          </Button>
          <Badge tone="brand">
            {activeIndex + 1}/{artifacts.length}
          </Badge>
          <Button
            tone="secondary"
            className="min-h-8 px-2 text-xs"
            disabled={activeIndex >= artifacts.length - 1}
            onClick={() => setActiveIndex((index) => Math.min(artifacts.length - 1, index + 1))}
          >
            下一个
          </Button>
        </div>
      </div>
      {artifacts.length > 1 ? (
        <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
          {artifacts.map((artifact, index) => (
            <button
              key={artifact.id}
              type="button"
              onClick={() => setActiveIndex(index)}
              className={`shrink-0 rounded-lg border px-3 py-2 text-left text-xs transition ${
                index === activeIndex ? "border-teal-200 bg-teal-50 text-brand-teal" : "border-line bg-white text-slate-600 hover:border-teal-200"
              }`}
            >
              <span className="font-semibold">{resourceLabel(String(artifact.type))}</span>
              <span className="ml-2 text-slate-400">#{index + 1}</span>
            </button>
          ))}
        </div>
      ) : null}
      <div className="mt-3">
        <ResourceArtifact
          artifact={activeArtifact}
          saveNotebookId={saveNotebookId}
          saving={saving}
          quizSubmitting={quizSubmitting}
          onSave={() => onSave(activeArtifact)}
          onSubmitQuiz={(answers) => onSubmitQuiz(activeArtifact, answers)}
        />
      </div>
    </div>
  );
}

function ResourceArtifact({
  artifact,
  saveNotebookId,
  saving,
  quizSubmitting,
  onSave,
  onSubmitQuiz,
}: {
  artifact: GuideV2Artifact;
  saveNotebookId: string;
  saving: boolean;
  quizSubmitting: boolean;
  onSave: () => void;
  onSubmitQuiz: (answers: QuizResultItem[]) => void;
}) {
  const result = asRecord(artifact.result);
  const response = readString(result ?? {}, "response");
  const renderType = readString(result ?? {}, "render_type");
  const hasVisual = Boolean(artifact.type === "visual" && renderType && asRecord(result?.code)?.content);
  const hasVideo = Boolean(artifact.type === "video" && (Array.isArray(result?.artifacts) || asRecord(result?.code)?.content));
  const questions = extractGuideQuizItems(result);
  const showResponse = Boolean(response && !(artifact.type === "quiz" && questions.length));

  return (
    <motion.article
      className="rounded-lg border border-line bg-canvas p-4"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18 }}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Badge tone="brand">{resourceLabel(String(artifact.type))}</Badge>
          {artifact.capability ? <Badge tone="neutral">{artifact.capability}</Badge> : null}
        </div>
        <div className="flex items-center gap-2">
          <Button
            tone="quiet"
            className="min-h-8 px-2 text-xs"
            onClick={onSave}
            disabled={saving || (!saveNotebookId && artifact.type !== "quiz")}
          >
            {saving ? <Loader2 size={14} className="animate-spin" /> : <BookOpen size={14} />}
            保存
          </Button>
          <span className="text-xs text-slate-500">{formatTime(artifact.created_at)}</span>
        </div>
      </div>
      <h3 className="mt-3 text-sm font-semibold text-ink">{artifact.title || "学习资源"}</h3>
      {showResponse ? <MarkdownRenderer className="markdown-body mt-3 text-sm text-slate-600">{response}</MarkdownRenderer> : null}

      {hasVisual ? <div className="mt-4"><VisualizationViewer result={result as unknown as VisualizeResult} /></div> : null}
      {hasVideo ? <div className="mt-4"><MathAnimatorViewer result={result as unknown as MathAnimatorResult} /></div> : null}
      {artifact.type === "quiz" && questions.length ? (
        <QuestionPreview items={questions} submitting={quizSubmitting} onSubmit={onSubmitQuiz} />
      ) : null}
      {artifact.type === "quiz" && !questions.length ? <QuizFallback result={result} response={response} /> : null}
    </motion.article>
  );
}

function QuizFallback({
  result,
  response,
}: {
  result: Record<string, unknown> | null;
  response: string;
}) {
  const text = response || pickFirstText(result, ["summary", "content", "final_answer", "answer"]);
  return (
    <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-800">
      <p className="font-semibold text-ink">这组题暂时无法转换成交互练习</p>
      <p className="mt-1">我没有在结果里找到标准题目结构。可以重新生成练习，或先按下面内容自行作答。</p>
      {text ? <MarkdownRenderer className="markdown-body mt-3 text-sm">{text}</MarkdownRenderer> : null}
    </div>
  );
}

function QuestionPreview({
  items,
  submitting,
  onSubmit,
}: {
  items: unknown[];
  submitting: boolean;
  onSubmit: (answers: QuizResultItem[]) => void;
}) {
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [revealed, setRevealed] = useState<Record<number, boolean>>({});
  const [checked, setChecked] = useState<Record<number, boolean>>({});
  const [submitted, setSubmitted] = useState(false);
  const records = items.slice(0, 8).map((item) => {
    const record = asRecord(item) ?? {};
    const qa = asRecord(record.qa_pair) ?? asRecord(record.question) ?? record;
    return { record, qa, options: normalizeOptions(qa.options ?? record.options) };
  });
  const answeredCount = records.filter((_item, index) => answers[index]?.trim()).length;
  const checkedCount = records.filter((_item, index) => checked[index]).length;
  const allAnswered = records.length > 0 && answeredCount === records.length;
  const allChecked = records.length > 0 && checkedCount === records.length;

  const buildResults = (): QuizResultItem[] =>
    records.map(({ qa, options }, index) => {
      const answer = answers[index] || "";
      const correctAnswer = readString(qa, "correct_answer") || readString(qa, "answer");
      const kind = normalizeGuideQuestionType(readString(qa, "question_type"), options);
      return {
        question_id: readString(qa, "question_id") || `guide-q-${index + 1}`,
        question: readString(qa, "question") || readString(qa, "prompt") || readString(qa, "title") || "已生成练习题",
        question_type: kind,
        options: options ? Object.fromEntries(Object.entries(options).map(([key, value]) => [key, String(value)])) : {},
        user_answer: answer,
        correct_answer: correctAnswer,
        explanation: readString(qa, "explanation"),
        difficulty: readString(qa, "difficulty"),
        is_correct: isGuideQuizCorrect(answer, correctAnswer, options),
      };
    });

  const submitAll = () => {
    if (!allChecked || submitting) return;
    setSubmitted(true);
    setRevealed(Object.fromEntries(records.map((_item, index) => [index, true])));
    setChecked(Object.fromEntries(records.map((_item, index) => [index, true])));
    onSubmit(buildResults());
  };

  return (
    <div className="mt-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line bg-white p-3">
        <div>
          <p className="text-sm font-semibold text-ink">交互式练习</p>
          <p className="mt-1 text-xs text-slate-500">每题提交后会立刻反馈对错，全部提交后再更新学习路径。</p>
        </div>
        <Badge tone={allChecked ? "success" : "neutral"}>{checkedCount}/{records.length}</Badge>
      </div>
      {records.map(({ record, qa, options }, index) => {
        const correctAnswer = readString(qa, "correct_answer") || readString(qa, "answer");
        const answer = answers[index] || "";
        const isRevealed = Boolean(revealed[index]);
        const isChecked = Boolean(checked[index]);
        const kind = normalizeGuideQuestionType(readString(qa, "question_type"), options);
        const isCorrect = answer && correctAnswer && isGuideQuizCorrect(answer, correctAnswer, options);
        return (
          <div key={`${index}-${readString(qa, "question_id")}`} className="rounded-lg border border-line bg-white p-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="neutral">题目 {index + 1}</Badge>
              <Badge tone="neutral">{guideQuestionTypeLabel(kind)}</Badge>
              {isChecked && answer ? <Badge tone={isCorrect ? "success" : correctAnswer ? "danger" : "brand"}>{guideAnswerFeedbackLabel(Boolean(isCorrect), Boolean(correctAnswer))}</Badge> : null}
            </div>
            <p className="mt-2 text-sm font-medium leading-6 text-ink">{readString(qa, "question") || readString(qa, "prompt") || readString(record, "question") || "已生成练习题"}</p>
            {options ? (
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {Object.entries(options).map(([key, value]) => (
                  <button
                    key={key}
                    type="button"
                    disabled={submitted || submitting || isChecked}
                    onClick={() => setAnswers((current) => ({ ...current, [index]: key }))}
                    className={`rounded-lg border px-3 py-2 text-left text-sm transition disabled:cursor-not-allowed ${
                      answer === key ? "border-teal-200 bg-teal-50 text-brand-teal" : "border-line bg-white text-slate-600 hover:border-teal-200"
                    }`}
                  >
                    <span className="font-semibold">{key}.</span> {String(value)}
                  </button>
                ))}
              </div>
            ) : kind === "true_false" ? (
              <div className="mt-3 grid grid-cols-2 gap-2">
                {[
                  ["True", "正确"],
                  ["False", "错误"],
                ].map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    disabled={submitted || submitting || isChecked}
                    onClick={() => setAnswers((current) => ({ ...current, [index]: value }))}
                    className={`rounded-lg border px-3 py-2 text-center text-sm font-semibold transition disabled:cursor-not-allowed ${
                      answer === value ? "border-teal-200 bg-teal-50 text-brand-teal" : "border-line bg-white text-slate-600 hover:border-teal-200"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            ) : (
              <TextInput
                className="mt-3"
                value={answer}
                disabled={submitted || submitting || isChecked}
                onChange={(event) => setAnswers((current) => ({ ...current, [index]: event.target.value }))}
                placeholder={kind === "written" || kind === "coding" ? "写下你的答案或思路" : "输入你的答案"}
              />
            )}
            <div className="mt-3 flex flex-wrap gap-2">
              {!isChecked ? (
                <Button
                  tone="primary"
                  className="min-h-8 px-2 text-xs"
                  disabled={!answer.trim() || submitted || submitting}
                  onClick={() => {
                    setChecked((current) => ({ ...current, [index]: true }));
                    setRevealed((current) => ({ ...current, [index]: true }));
                  }}
                >
                  <CheckCircle2 size={14} />
                  提交答案
                </Button>
              ) : (
                <>
                  <Button
                    tone="secondary"
                    className="min-h-8 px-2 text-xs"
                    onClick={() => setRevealed((current) => ({ ...current, [index]: !current[index] }))}
                  >
                    {isRevealed ? "收起解析" : "查看解析"}
                  </Button>
                  {!submitted ? (
                    <Button
                      tone="quiet"
                      className="min-h-8 px-2 text-xs"
                      onClick={() => {
                        setChecked((current) => ({ ...current, [index]: false }));
                        setRevealed((current) => ({ ...current, [index]: false }));
                      }}
                    >
                      修改答案
                    </Button>
                  ) : null}
                </>
              )}
            </div>
            {isChecked ? (
              <div className={`mt-3 rounded-lg border p-3 text-xs leading-5 ${
                correctAnswer
                  ? isCorrect
                    ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                    : "border-red-200 bg-red-50 text-red-800"
                  : "border-teal-200 bg-teal-50 text-teal-800"
              }`}>
                <p className="font-semibold">
                  {correctAnswer ? (isCorrect ? "回答正确。" : "回答不对，建议看一下解析再复盘。") : "答案已提交，请对照参考解析。"}
                </p>
              </div>
            ) : null}
            {isRevealed ? (
              <div className="mt-3 rounded-lg border border-line bg-canvas p-3 text-xs leading-5 text-slate-600">
                {correctAnswer ? <p className="font-medium text-ink">参考答案：{correctAnswer}</p> : null}
                {readString(qa, "explanation") ? <p className="mt-1">解析：{readString(qa, "explanation")}</p> : null}
              </div>
            ) : null}
          </div>
        );
      })}
      <Button tone="primary" className="w-full" disabled={!allChecked || submitting || submitted} onClick={submitAll}>
        {submitting ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
        {submitted ? "练习已回写" : allChecked ? "提交整组练习并更新路径" : "先逐题提交答案"}
      </Button>
    </div>
  );
}
function TaskRow({ task, active }: { task: GuideV2Task; active: boolean }) {
  return (
    <div className={`flex items-start gap-3 rounded-lg border p-3 ${active ? "border-teal-200 bg-teal-50" : "border-line bg-white"}`}>
      <div className="flex shrink-0 flex-wrap gap-2">
        <Badge tone={task.status === "completed" ? "success" : task.status === "skipped" ? "neutral" : active ? "brand" : "neutral"}>{taskTypeLabel(task.type)}</Badge>
        {task.origin && task.origin !== "planned" ? <Badge tone={originTone(task.origin)}>{originLabel(task.origin)}</Badge> : null}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-ink">{task.title}</p>
        <p className="mt-1 line-clamp-2 text-sm leading-6 text-slate-500">{task.instruction}</p>
        {task.artifact_refs?.length ? <p className="mt-1 text-xs text-brand-teal">{task.artifact_refs.length} 个资源已生成</p> : null}
      </div>
      <span className="shrink-0 text-xs text-slate-500">{task.estimated_minutes ?? 8}m</span>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-line bg-canvas px-3 py-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 line-clamp-2 text-sm font-medium text-ink">{value || "-"}</p>
    </div>
  );
}

function taskTypeLabel(type: string) {
  const labels: Record<string, string> = {
    explain: "讲解",
    visualize: "图解",
    video: "视频",
    practice: "练习",
    remediation: "补救",
    quiz: "复测",
    reflection: "反思",
    project: "项目",
  };
  return labels[type] || type || "任务";
}

function resourceLabel(type: string) {
  const labels: Record<string, string> = {
    visual: "图解",
    video: "短视频",
    quiz: "练习",
  };
  return labels[type] || type || "资源";
}

function resourceOrPreferenceLabel(type: string) {
  const labels: Record<string, string> = {
    visual: "图解",
    video: "短视频",
    practice: "练习",
    explanation: "讲解",
  };
  return labels[type] || resourceLabel(type);
}

function isResearchResourceType(type: string) {
  const value = String(type || "").toLowerCase();
  return value === "research" || value === "material" || value === "materials" || value.includes("资料");
}

function normalizeResourceType(type: string): GuideV2ResourceType {
  if (type === "visual" || type === "video" || type === "quiz") {
    return type;
  }
  return "visual";
}

function priorityTone(priority: string): "neutral" | "success" | "warning" | "danger" | "brand" {
  if (priority === "high") return "danger";
  if (priority === "medium") return "warning";
  if (priority === "low") return "neutral";
  return "brand";
}

function priorityLabel(priority: string) {
  const labels: Record<string, string> = {
    high: "高优先级",
    medium: "中优先级",
    low: "可选",
  };
  return labels[priority] || priority || "推荐";
}

function originLabel(origin: string) {
  const labels: Record<string, string> = {
    adaptive_remediation: "补救",
    adaptive_retest: "复测",
    adaptive_transfer: "迁移",
    diagnostic_remediation: "前测补强",
    learner_memory: "长期画像",
    planned: "计划",
  };
  return labels[origin] || origin || "任务";
}

function originTone(origin: string): "neutral" | "success" | "warning" | "danger" | "brand" {
  if (origin === "adaptive_remediation") return "warning";
  if (origin === "adaptive_retest") return "brand";
  if (origin === "adaptive_transfer") return "brand";
  if (origin === "learner_memory") return "brand";
  return "neutral";
}

function coachModeLabel(mode?: string) {
  const labels: Record<string, string> = {
    remediation: "补救优先",
    retest: "复测优先",
    retest_failed: "复测未过",
    review: "错因追踪",
    closed_loop: "错因已闭环",
    normal: "常规推进",
  };
  return labels[String(mode || "normal")] || "导学中";
}

function coachModeTone(mode?: string): "neutral" | "success" | "warning" | "danger" | "brand" {
  if (mode === "closed_loop") return "success";
  if (mode === "retest_failed") return "danger";
  if (mode === "remediation" || mode === "retest" || mode === "review") return "warning";
  if (mode === "normal") return "brand";
  return "neutral";
}

function feedbackTone(tone?: string): "neutral" | "success" | "warning" | "danger" | "brand" {
  if (tone === "success") return "success";
  if (tone === "warning") return "warning";
  if (tone === "danger") return "danger";
  if (tone === "brand") return "brand";
  return "neutral";
}

function effectStatusTone(score?: number): "neutral" | "success" | "warning" | "danger" | "brand" {
  const value = Number(score ?? 0);
  if (value >= 85) return "success";
  if (value >= 70) return "brand";
  if (value >= 50) return "warning";
  if (value > 0) return "danger";
  return "neutral";
}

function coachModeActions(
  mode: string,
  taskId: string,
  mistakeLabel: string,
  suggestedAction: string,
): NonNullable<GuideV2CoachBriefing["coach_actions"]> {
  if (!taskId) return [];
  const target = mistakeLabel || "当前任务";
  if (mode === "remediation") {
    return [
      {
        type: "visual",
        label: "生成补救图解",
        primary: true,
        prompt: `围绕「${target}」生成一张补救图解：先说明错因，再拆解关键概念、判断步骤、反例和一个修正后的最小例子。${suggestedAction ? `建议动作：${suggestedAction}` : ""}`,
      },
      {
        type: "quiz",
        label: "生成纠错练习",
        prompt: `针对「${target}」生成 4 道由易到难的混合题，题型包含选择、判断、填空和简答；每题给出错因提示和解析。`,
      },
    ];
  }
  if (mode === "retest") {
    return [
      {
        type: "quiz",
        label: "生成复测题",
        primary: true,
        prompt: `围绕「${target}」生成一组复测题，重点验证补救后的判断方法是否稳定；题型混合，要求给出答案、解析和通过标准。`,
      },
    ];
  }
  if (mode === "retest_failed" || mode === "review") {
    return [
      {
        type: "visual",
        label: "重新拆解错因",
        primary: true,
        prompt: `复测或错因追踪仍未闭环。请把「${target}」重新拆成：错误表现、根因、正确判断条件、反例辨析和 3 步补救路径。`,
      },
      {
        type: "quiz",
        label: "生成同类复测",
        prompt: `围绕「${target}」生成 3 道同类复测题，专门暴露相同错因，并在解析里说明如何避免再次犯错。`,
      },
    ];
  }
  return [];
}

function mistakeSeverityLabel(severity?: string) {
  const labels: Record<string, string> = {
    high: "高风险",
    medium: "需补救",
    review: "需复盘",
    closed: "已关闭",
  };
  return labels[String(severity || "")] || "错因";
}

function mistakeSeverityTone(severity?: string): "neutral" | "success" | "warning" | "danger" | "brand" {
  if (severity === "closed") return "success";
  if (severity === "high") return "danger";
  if (severity === "medium") return "warning";
  if (severity === "review") return "brand";
  return "neutral";
}

function mistakeLoopStatusLabel(status?: string) {
  const labels: Record<string, string> = {
    needs_remediation: "待补救",
    ready_for_retest: "待复测",
    closed: "已关闭",
    retest_failed: "复测未过",
    needs_review: "需复盘",
  };
  return labels[String(status || "")] || "追踪中";
}

function mistakeLoopStatusTone(status?: string): "neutral" | "success" | "warning" | "danger" | "brand" {
  if (status === "closed") return "success";
  if (status === "retest_failed") return "danger";
  if (status === "needs_remediation" || status === "ready_for_retest") return "warning";
  if (status === "needs_review") return "brand";
  return "neutral";
}

function planEventLabel(type: string) {
  const labels: Record<string, string> = {
    insert_remediation: "插入补救",
    insert_transfer: "追加迁移",
    skip_redundant: "跳过重复",
  };
  return labels[type] || type || "调整";
}

function planEventTone(type: string): "neutral" | "success" | "warning" | "danger" | "brand" {
  if (type === "insert_remediation") return "warning";
  if (type === "insert_transfer") return "brand";
  if (type === "skip_redundant") return "success";
  return "neutral";
}

function timelineEventLabel(type: string) {
  const labels: Record<string, string> = {
    session_created: "路线创建",
    task_inserted: "任务插入",
    resource_generated: "资源生成",
    quiz_attempt: "练习提交",
    diagnostic: "前测",
    profile_dialogue: "画像对话",
    quiz_evidence: "练习证据",
    task_completed: "任务完成",
    path_adjustment: "路径调整",
  };
  return labels[type] || type || "事件";
}

function timelineEventTone(type: string): "neutral" | "success" | "warning" | "danger" | "brand" {
  if (type === "task_completed" || type === "quiz_attempt" || type === "quiz_evidence") return "success";
  if (type === "path_adjustment" || type === "task_inserted") return "warning";
  if (type === "resource_generated" || type === "profile_dialogue" || type === "diagnostic") return "brand";
  return "neutral";
}

function planStatusLabel(status: string) {
  const labels: Record<string, string> = {
    active: "进行中",
    pending: "待开始",
    completed: "已完成",
    met: "已达成",
    needs_review: "需复盘",
  };
  return labels[status] || status || "待开始";
}

function planStatusTone(status: string): "neutral" | "success" | "warning" | "danger" | "brand" {
  if (status === "completed" || status === "met") return "success";
  if (status === "active") return "brand";
  if (status === "needs_review") return "warning";
  return "neutral";
}

function diagnosticStatusLabel(status: string) {
  const labels: Record<string, string> = {
    completed: "已诊断",
    pending: "待前测",
  };
  return labels[status] || status || "待前测";
}

function masteryTone(status: string): "neutral" | "success" | "warning" | "danger" | "brand" {
  if (status === "mastered") return "success";
  if (status === "learning") return "brand";
  if (status === "needs_support") return "warning";
  return "neutral";
}

function knowledgeNodeStyle(status: string, active: boolean, current: boolean, done: boolean) {
  if (active) {
    return {
      card: "border-teal-300 bg-teal-50 shadow-sm",
      dot: "border-brand-teal bg-brand-teal text-white",
      bar: "bg-brand-teal",
    };
  }
  if (current) {
    return {
      card: "border-blue-200 bg-blue-50",
      dot: "border-blue-600 bg-blue-600 text-white",
      bar: "bg-blue-600",
    };
  }
  if (done || status === "mastered") {
    return {
      card: "border-emerald-200 bg-emerald-50",
      dot: "border-emerald-600 bg-emerald-600 text-white",
      bar: "bg-emerald-600",
    };
  }
  if (status === "needs_support") {
    return {
      card: "border-amber-200 bg-amber-50",
      dot: "border-amber-500 bg-amber-500 text-white",
      bar: "bg-amber-500",
    };
  }
  return {
    card: "border-line bg-white",
    dot: "border-line bg-canvas text-slate-500",
    bar: "bg-slate-300",
  };
}

function masteryStatusLabel(status: string) {
  const labels: Record<string, string> = {
    mastered: "已掌握",
    learning: "学习中",
    needs_support: "需补强",
    not_started: "未开始",
  };
  return labels[status] || status || "未开始";
}

function scorePercent(value: unknown) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  const percent = number <= 1 ? number * 100 : number;
  return Math.max(0, Math.min(100, Math.round(percent)));
}

function extractStringArray(value: unknown) {
  if (Array.isArray(value)) {
    return value.map(String).map((item) => item.trim()).filter(Boolean);
  }
  if (typeof value === "string") {
    return value
      .split(/\s*(?:,|，|、|;|；|\|)\s*/g)
      .map((item) => item.trim())
      .filter(Boolean);
  }
  return [];
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function readString(source: Record<string, unknown>, key: string) {
  const value = source[key];
  return typeof value === "string" ? value : value == null ? "" : String(value);
}

function splitLines(value: string) {
  return value
    .split(/[\n,，]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function arrayText(value: unknown) {
  return Array.isArray(value) && value.length ? value.map(String).join("、") : "-";
}

function parseMaybeJson(value: unknown): unknown {
  if (!value || typeof value !== "string") return value ?? null;
  const text = value.trim();
  if (!text) return "";
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)\s*```/i);
  const candidates = [fenced?.[1]?.trim(), text];
  const firstObject = text.match(/(\{[\s\S]*\}|\[[\s\S]*\])/);
  if (firstObject?.[1]) candidates.push(firstObject[1]);
  for (const candidate of candidates) {
    if (!candidate) continue;
    try {
      return JSON.parse(candidate);
    } catch {
      // Keep trying softer candidates before falling back to text.
    }
  }
  return text;
}

function pickFirstText(source: unknown, keys: string[]) {
  const record = asRecord(source);
  if (!record) return "";
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) return value.trim();
    if (Array.isArray(value) && value.every((item) => typeof item === "string")) return value.join("\n");
  }
  const summary = asRecord(record.summary);
  if (summary) return pickFirstText(summary, keys);
  return "";
}

function extractGuideQuizItems(result: Record<string, unknown> | null): unknown[] {
  const candidates: unknown[] = [];
  const pushFrom = (value: unknown) => {
    if (!value) return;
    const parsed = parseMaybeJson(value);
    if (Array.isArray(parsed)) {
      candidates.push(parsed);
      return;
    }
    const record = asRecord(parsed);
    if (!record) return;
    for (const key of ["results", "questions", "items", "records", "quiz", "data"]) {
      const child = record[key];
      if (Array.isArray(child)) candidates.push(child);
      else if (typeof child === "string") pushFrom(child);
      else if (asRecord(child)) pushFrom(child);
    }
    if (record.summary) pushFrom(record.summary);
  };

  pushFrom(result);
  pushFrom(result?.response);
  pushFrom(result?.content);
  pushFrom(result?.summary);

  const found = candidates.find((items) => Array.isArray(items) && items.some(isQuestionLike));
  return Array.isArray(found) ? found.filter(isQuestionLike) : [];
}

function isQuestionLike(item: unknown) {
  const record = asRecord(item);
  if (!record) return false;
  const qa = asRecord(record.qa_pair) ?? record;
  return Boolean(
    readString(qa, "question") ||
      readString(qa, "prompt") ||
      readString(qa, "title") ||
      readString(qa, "correct_answer") ||
      readString(qa, "answer"),
  );
}

function normalizeOptions(value: unknown): Record<string, string> | null {
  if (!value) return null;
  if (Array.isArray(value)) {
    const entries = value
      .map((item, index) => {
        if (typeof item === "string") return [String.fromCharCode(65 + index), item] as const;
        const record = asRecord(item);
        if (!record) return null;
        const key = readString(record, "key") || readString(record, "value") || String.fromCharCode(65 + index);
        const label = readString(record, "label") || readString(record, "text") || readString(record, "content") || key;
        return [key, label] as const;
      })
      .filter((item): item is readonly [string, string] => Boolean(item));
    return entries.length ? Object.fromEntries(entries) : null;
  }
  const record = asRecord(value);
  if (!record) return null;
  const normalized = Object.fromEntries(Object.entries(record).map(([key, item]) => [key, String(item)]));
  return Object.keys(normalized).length ? normalized : null;
}

function formatTime(value?: number) {
  if (!value) return "";
  return new Date(value * 1000).toLocaleString();
}

function normalizeGuideQuestionType(value: string, options?: Record<string, unknown> | null) {
  const raw = String(value || "").toLowerCase();
  if (raw.includes("choice") || raw.includes("select") || raw === "mcq") return "choice";
  if (raw.includes("true_false") || raw.includes("true-false") || raw.includes("truefalse") || raw === "tf") return "true_false";
  if (raw.includes("judge") || raw.includes("判断") || raw.includes("是非")) return "true_false";
  if (raw.includes("fill") || raw.includes("blank") || raw.includes("cloze") || raw.includes("填空")) return "fill_blank";
  if (raw.includes("code") || raw.includes("program") || raw.includes("编程")) return "coding";
  if (options && Object.keys(options).length > 0) return "choice";
  return raw || "written";
}

function guideQuestionTypeLabel(value: string) {
  const labels: Record<string, string> = {
    choice: "选择题",
    true_false: "判断题",
    fill_blank: "填空题",
    written: "简答题",
    coding: "编程题",
  };
  return labels[value] || value || "题目";
}

function guideAnswerFeedbackLabel(isCorrect: boolean, hasReference: boolean) {
  if (!hasReference) return "已提交";
  return isCorrect ? "答对了" : "答错了";
}

function isGuideQuizCorrect(answer: string, correctAnswer: string, options?: Record<string, unknown> | null) {
  const user = String(answer || "").trim();
  const correct = String(correctAnswer || "").trim();
  if (!user || !correct) return false;
  if (options && Object.keys(options).length > 0) {
    const optionValue = String(options[user] || "");
    return (
      user.toUpperCase() === correct.toUpperCase() ||
      user.toUpperCase() === correct.charAt(0).toUpperCase() ||
      normalizeAnswer(optionValue) === normalizeAnswer(correct)
    );
  }
  const normalizedUser = normalizeAnswer(user);
  const acceptable = correct
    .split(/\s*(?:\||;|；|、|\/)\s*/g)
    .map(normalizeAnswer)
    .filter(Boolean);
  if (["true", "false"].includes(normalizedUser)) {
    return normalizeBooleanText(normalizedUser) === normalizeBooleanText(correct);
  }
  return acceptable.includes(normalizedUser);
}

function normalizeBooleanText(value: string) {
  const normalized = normalizeAnswer(value);
  if (["true", "t", "yes", "y", "correct", "right", "正确", "是", "真"].includes(normalized)) return "true";
  if (["false", "f", "no", "n", "incorrect", "wrong", "错误", "否", "假"].includes(normalized)) return "false";
  return normalized;
}

function normalizeAnswer(value: string) {
  return value.trim().replace(/^选项\s*/i, "").toLowerCase();
}
