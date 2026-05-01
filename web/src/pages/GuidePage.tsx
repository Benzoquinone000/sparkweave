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
  RefreshCw,
  Sparkles,
  Target,
  Trash2,
  Video,
  X,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { Fragment, useEffect, useMemo, useState } from "react";
import type { FormEvent, ReactNode } from "react";

import { ExternalVideoViewer } from "@/components/results/ExternalVideoViewer";
import { MathAnimatorViewer } from "@/components/results/MathAnimatorViewer";
import { VisualizationViewer } from "@/components/results/VisualizationViewer";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FieldShell, SelectInput, TextArea, TextInput } from "@/components/ui/Field";
import { MarkdownRenderer } from "@/components/ui/MarkdownRenderer";
import { openGuideV2ResourceJobEvents } from "@/lib/api";
import { questionDifficultyLabel } from "@/lib/learningLabels";
import {
  useGuideV2CoursePackage,
  useGuideV2Diagnostic,
  useGuideV2LearningReport,
  useGuideV2Mutations,
  useGuideV2SessionDetail,
  useGuideV2Sessions,
  useGuideV2StudyPlan,
  useGuideV2Templates,
  useLearnerProfile,
  useLearnerProfileMutations,
  useNotebookDetail,
  useNotebooks,
} from "@/hooks/useApiQueries";
import type {
  GuideV2Artifact,
  GuideV2CoursePackage,
  GuideV2Diagnostic,
  GuideV2DiagnosticAnswer,
  GuideV2DiagnosticValue,
  GuideV2CourseTemplate,
  GuideV2LearningFeedback,
  GuideV2LearningReport,
  GuideV2ResourceType,
  GuideV2Session,
  GuideV2StudyPlan,
  GuideV2Task,
  ExternalVideoResult,
  LearnerProfileSnapshot,
  MathAnimatorResult,
  NotebookRecord,
  NotebookReference,
  QuizResultItem,
  VisualizeResult,
} from "@/lib/types";

type GuideSubPage = "main" | "setup" | "completeTask" | "resourceChoice" | "routeMap" | "coursePackage";
type DemoRecordingCueAction = "none" | "generate_current_seed" | "open_complete_task" | "open_route_map" | "open_course_package";
type DemoRecordingCue = {
  title: string;
  detail: string;
  actionLabel: string;
  action: DemoRecordingCueAction;
  tone: "brand" | "success" | "warning";
};

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

const taskScoreOptions = [
  { value: "0.45", label: "还没懂", helper: "需要补讲" },
  { value: "0.7", label: "有点懂", helper: "还要巩固" },
  { value: "0.9", label: "掌握了", helper: "可以继续" },
];

export function GuidePage() {
  const sessions = useGuideV2Sessions();
  const templates = useGuideV2Templates();
  const learnerProfile = useLearnerProfile();
  const learnerProfileMutations = useLearnerProfileMutations();
  const mutations = useGuideV2Mutations();
  const notebooks = useNotebooks();

  const [goal, setGoal] = useState("");
  const [goalTouched, setGoalTouched] = useState(false);
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
  const [generatingType, setGeneratingType] = useState<GuideV2ResourceType | null>(null);
  const [resourceJobId, setResourceJobId] = useState<string | null>(null);
  const [prescriptionTaskId, setPrescriptionTaskId] = useState("");
  const [saveNotebookId, setSaveNotebookId] = useState("");
  const [saveMessage, setSaveMessage] = useState("");
  const [supportOpen, setSupportOpen] = useState(false);
  const [learningFeedback, setLearningFeedback] = useState<GuideV2LearningFeedback | null>(null);
  const [prescriptionFeedback, setPrescriptionFeedback] = useState<GuideV2LearningFeedback | null>(null);
  const [guideSubPage, setGuideSubPage] = useState<GuideSubPage>("main");
  const [forceNewSession, setForceNewSession] = useState(false);
  const [sourceAction, setSourceAction] = useState<Record<string, unknown> | null>(null);
  const [highlightedSectionId, setHighlightedSectionId] = useState<string | null>(null);
  const hasUrlGuideSeed = useMemo(() => {
    if (typeof window === "undefined") return false;
    const search = new URLSearchParams(window.location.search);
    return Boolean(search.get("prompt") || search.get("new") === "1");
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const search = new URLSearchParams(window.location.search);
      const prompt = search.get("prompt")?.trim();
      const estimatedMinutes = Number(search.get("estimated_minutes") || "") || undefined;
      const sourceLabel = search.get("source_label")?.trim() || "";
      const actionKind = search.get("action_kind")?.trim() || "next_action";
      const targetSection = search.get("target_section")?.trim() || "";
      if (prompt) {
        setGoal(prompt);
        setGoalTouched(true);
      }
      if (estimatedMinutes) {
        setTimeBudget(String(Math.round(estimatedMinutes)));
      }
      if (actionKind === "weak_point" && sourceLabel) {
        setWeakPoints(sourceLabel);
      }
      if (prompt || search.get("new") === "1") {
        setForceNewSession(true);
        setSelectedSessionId(null);
        setGuideSubPage(targetSection === "guide-setup-section" ? "setup" : "main");
        setSourceAction({
          source: "learner_profile",
          kind: actionKind,
          title: search.get("action_title") || "",
          source_type: search.get("source_type") || "",
          source_label: sourceLabel,
          confidence: Number(search.get("confidence") || "") || undefined,
          estimated_minutes: estimatedMinutes,
          suggested_prompt: prompt || "",
          href: "/guide",
        });
      }
      if (targetSection) {
        setHighlightedSectionId(targetSection);
        window.setTimeout(() => {
          const element = document.getElementById(targetSection);
          if (!element) return;
          element.scrollIntoView({ behavior: "smooth", block: "start" });
        }, 180);
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const referenceNotebook = useNotebookDetail(referenceNotebookId || null);
  const courseTemplates = templates.data ?? [];
  const selectedTemplate = courseTemplates.find((item) => item.id === courseTemplateId) ?? null;
  const demoTemplate =
    courseTemplates.find((item) => item.id === "ml_foundations") ??
    courseTemplates.find((item) => (item.demo_seed?.task_chain ?? []).length > 0) ??
    null;
  const activeSessionId = forceNewSession ? null : selectedSessionId || sessions.data?.[0]?.session_id || null;
  const detail = useGuideV2SessionDetail(activeSessionId);
  const studyPlan = useGuideV2StudyPlan(activeSessionId);
  const diagnostic = useGuideV2Diagnostic(activeSessionId);
  const learningReport = useGuideV2LearningReport(activeSessionId);
  const coursePackage = useGuideV2CoursePackage(activeSessionId);
  const session = detail.data ?? null;
  const profileNextAction = learnerProfile.data?.next_action ?? null;
  const profileSuggestedPrompt = profileNextAction?.suggested_prompt?.trim() || learnerProfile.data?.overview.current_focus?.trim() || "";
  const nodes = useMemo(() => session?.course_map?.nodes ?? [], [session?.course_map?.nodes]);
  const tasks = useMemo(() => session?.tasks ?? [], [session?.tasks]);
  const courseMetadata = useMemo(
    () => asRecord(session?.course_map?.metadata) ?? {},
    [session?.course_map?.metadata],
  );
  const currentTask = session?.current_task ?? tasks.find((task) => task.status !== "completed" && task.status !== "skipped") ?? null;
  const profile = session?.profile ?? {};
  const profileContextSummary = readString(profile, "source_context_summary");
  const routeUsesUnifiedProfile = profileContextSummary.includes("Unified learner profile");
  const restoredLearningFeedback = useMemo(
    () => latestLearningFeedbackFromSession(session, currentTask?.task_id),
    [currentTask?.task_id, session],
  );
  const activeLearningFeedback = learningFeedback ?? restoredLearningFeedback;
  const referenceRecords = useMemo(
    () => (referenceNotebook.data?.records ?? []).slice(0, 6),
    [referenceNotebook.data?.records],
  );
  const currentArtifacts = useMemo(
    () => (currentTask?.artifact_refs ?? []).filter((artifact) => !isResearchResourceType(String(artifact.type))),
    [currentTask?.artifact_refs],
  );
  const demoTaskChain = useMemo(() => {
    const demoSeed = asRecord(courseMetadata.demo_seed);
    const chain = Array.isArray(demoSeed?.task_chain) ? demoSeed.task_chain : [];
    return chain.map((item) => asRecord(item)).filter((item): item is Record<string, unknown> => Boolean(item));
  }, [courseMetadata]);
  const currentDemoStep = useMemo(() => {
    if (!currentTask || !demoTaskChain.length) return null;
    return (
      demoTaskChain.find((item) => readString(item, "task_id") === currentTask.task_id) ??
      demoTaskChain.find((item) => readString(item, "title") === currentTask.title) ??
      null
    );
  }, [currentTask, demoTaskChain]);
  const isDemoSeedSession = useMemo(() => {
    const metadataSourceAction = asRecord(courseMetadata.source_action) ?? {};
    return (
      demoTaskChain.length > 0 ||
      readString(metadataSourceAction, "source") === "demo_seed" ||
      readString(courseMetadata, "created_from") === "demo_seed"
    );
  }, [courseMetadata, demoTaskChain.length]);
  const reportActionTaskId = useMemo(() => {
    const brief = learningReport.data?.action_brief;
    const candidates = [brief?.primary_action, ...(brief?.secondary_actions ?? [])];
    return candidates.map((item) => String(item?.target_task_id || "")).find(Boolean) || "";
  }, [learningReport.data?.action_brief]);
  const effectivePrescriptionTaskId = prescriptionTaskId || reportActionTaskId;
  const prescriptionTask = useMemo(
    () => tasks.find((task) => task.task_id === effectivePrescriptionTaskId) ?? null,
    [effectivePrescriptionTaskId, tasks],
  );
  const prescriptionArtifacts = useMemo(
    () => (prescriptionTask?.artifact_refs ?? []).filter((artifact) => !isResearchResourceType(String(artifact.type))),
    [prescriptionTask?.artifact_refs],
  );
  const showPrescriptionResults = Boolean(prescriptionTaskId || generatingType || prescriptionArtifacts.length);
  const diagnosticDone = diagnostic.data?.status === "completed";
  const guideStage = !session ? "create" : !diagnosticDone ? "diagnostic" : activeLearningFeedback ? "feedback" : currentTask ? "learn" : "complete";
  const demoRecordingCue = useMemo(
    () =>
      buildDemoRecordingCue({
        enabled: isDemoSeedSession,
        guideStage,
        guideSubPage,
        currentTask,
        currentDemoStep,
        generatingType,
        artifactCount: currentArtifacts.length,
      }),
    [currentArtifacts.length, currentDemoStep, currentTask, generatingType, guideStage, guideSubPage, isDemoSeedSession],
  );
  const adaptiveGuideStrategy = useMemo(
    () => buildAdaptiveGuideStrategy(learnerProfile.data, guideStage, currentTask?.title || "", activeLearningFeedback),
    [activeLearningFeedback, currentTask?.title, guideStage, learnerProfile.data],
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
  const trendNotice = useMemo(
    () => buildGuideTrendNotice(learnerProfile.data, guideStage),
    [guideStage, learnerProfile.data],
  );
  const resourceButtonCopy = useMemo(
    () => buildGuideResourceButtonCopy(adaptiveGuideStrategy.recommendedResource, trendNotice?.label || ""),
    [adaptiveGuideStrategy.recommendedResource, trendNotice?.label],
  );
  const resourceActions = useMemo(
    () => buildGuideResourceActions(adaptiveGuideStrategy.recommendedResource, resourceButtonCopy),
    [adaptiveGuideStrategy.recommendedResource, resourceButtonCopy],
  );
  const primaryResourceAction = resourceActions[0];
  useEffect(() => {
    if (hasUrlGuideSeed || goalTouched || goal.trim() || !profileSuggestedPrompt) return;
    const timer = window.setTimeout(() => {
      setGoal(profileSuggestedPrompt);
      if (typeof profileNextAction?.estimated_minutes === "number" && Number.isFinite(profileNextAction.estimated_minutes)) {
        setTimeBudget(String(Math.round(profileNextAction.estimated_minutes)));
      }
      if (profileNextAction?.source_type === "weak_point" && profileNextAction.source_label && !weakPoints.trim()) {
        setWeakPoints(profileNextAction.source_label);
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, [goal, goalTouched, hasUrlGuideSeed, profileNextAction, profileSuggestedPrompt, weakPoints]);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setLearningFeedback(null);
      setPrescriptionFeedback(null);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [activeSessionId]);

  useEffect(() => {
    const timer = window.setTimeout(() => setGuideSubPage("main"), 0);
    return () => window.clearTimeout(timer);
  }, [activeSessionId, guideStage]);

  const applyCourseTemplate = (template: GuideV2CourseTemplate, mode: "default" | "demo" = "default") => {
    setCourseTemplateId(template.id);
    const demoPersona = template.demo_seed?.persona;
    if (mode === "demo" && demoPersona?.goal) {
      setGoal(`${demoPersona.goal}。请按稳定 Demo 样例演示 T1 全景图、T4 梯度下降图解、T6 模型评估练习。`);
      setGoalTouched(true);
    } else if (template.default_goal) {
      setGoal(template.default_goal);
    }
    if (template.default_time_budget_minutes) setTimeBudget(String(template.default_time_budget_minutes));
    if (template.default_preferences?.length) setPreferences(template.default_preferences);
    if (mode === "demo" && demoPersona?.weak_points?.length) {
      setWeakPoints(demoPersona.weak_points.join("、"));
    }
    if (!level && template.level) setLevel(template.level);
    if (!horizon && template.suggested_weeks && template.suggested_weeks > 1) setHorizon("week");
  };

  const selectCourseTemplate = (templateId: string) => {
    const template = courseTemplates.find((item) => item.id === templateId);
    if (!template) {
      setCourseTemplateId("");
      return;
    }
    applyCourseTemplate(template);
  };

  const startDemoSession = async () => {
    const template = demoTemplate;
    if (!template) return;
    const demoPersona = template.demo_seed?.persona ?? {};
    const demoGoal = `${demoPersona.goal || template.default_goal || "系统学习机器学习基础"}。请按稳定 Demo 样例演示 T1 全景图、T4 梯度下降图解、T6 模型评估练习。`;
    const demoWeakPoints = (demoPersona.weak_points ?? []).length
      ? demoPersona.weak_points ?? []
      : ["概念边界不清", "公式直觉不足", "指标容易混淆"];
    applyCourseTemplate(template, "demo");
    const created = await mutations.create.mutateAsync({
      goal: demoGoal,
      level: template.level || "beginner",
      horizon: template.suggested_weeks && template.suggested_weeks > 1 ? "week" : horizon,
      timeBudgetMinutes: template.default_time_budget_minutes || 45,
      courseTemplateId: template.id,
      preferences: template.default_preferences?.length ? template.default_preferences : ["visual", "practice"],
      weakPoints: demoWeakPoints,
      notebookReferences: [],
      sourceAction: {
        source: "demo_seed",
        kind: "competition_demo",
        title: template.demo_seed?.title || "稳定 Demo 样例",
        source_type: "course_template",
        source_label: template.course_name || template.title,
        suggested_prompt: demoGoal,
        href: "/guide",
      },
    });
    if (created.session?.session_id) {
      setForceNewSession(false);
      setSourceAction(null);
      setSelectedSessionId(created.session.session_id);
      setReflection("");
      setLearningFeedback(null);
      setPrescriptionFeedback(null);
      setGuideSubPage("main");
      const profileSyncMessage = await refreshLearnerProfileAfterGuide();
      setSaveMessage(`已创建稳定演示路线。${profileSyncMessage}`);
    }
  };

  const busy =
    mutations.create.isPending ||
    mutations.completeTask.isPending ||
    mutations.submitDiagnostic.isPending ||
    mutations.refreshRecommendations.isPending ||
    mutations.startResourceJob.isPending ||
    mutations.remove.isPending ||
    learnerProfileMutations.refresh.isPending;

  const notebookReferences = useMemo<NotebookReference[]>(() => {
    if (!referenceNotebookId || !selectedRecordIds.length) return [];
    return [{ notebook_id: referenceNotebookId, record_ids: selectedRecordIds }];
  }, [referenceNotebookId, selectedRecordIds]);

  useEffect(() => {
    if (!saveNotebookId && notebooks.data?.[0]?.id) {
      const timer = window.setTimeout(() => setSaveNotebookId(notebooks.data![0].id), 0);
      return () => window.clearTimeout(timer);
    }
  }, [notebooks.data, saveNotebookId]);

  const refreshLearnerProfileAfterGuide = async () => {
    try {
      const profile = await learnerProfileMutations.refresh.mutateAsync({ force: true });
      const focus = profile?.overview?.current_focus?.trim();
      return focus ? `画像已同步，当前重点：${focus}。` : "画像已同步，可前往学习画像页查看变化。";
    } catch {
      return "学习证据已记录，画像会在后台继续同步。";
    }
  };

  const scrollToGuideSection = (sectionId: string) => {
    setHighlightedSectionId(sectionId);
    window.setTimeout(() => {
      const element = document.getElementById(sectionId);
      if (!element) return;
      element.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 120);
  };

  useEffect(() => {
    if (!highlightedSectionId) return;
    const timer = window.setTimeout(() => setHighlightedSectionId(null), 2200);
    return () => window.clearTimeout(timer);
  }, [highlightedSectionId]);

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
      sourceAction: sourceAction ?? undefined,
    });
    if (created.session?.session_id) {
      setForceNewSession(false);
      setSourceAction(null);
      setSelectedSessionId(created.session.session_id);
      setReflection("");
      setLearningFeedback(null);
      const profileSyncMessage = await refreshLearnerProfileAfterGuide();
      setSaveMessage(`路线已创建。${profileSyncMessage}`);
    }
  };

  const completeCurrentTask = async () => {
    if (!activeSessionId || !currentTask) return;
    const result = await mutations.completeTask.mutateAsync({
      sessionId: activeSessionId,
      taskId: currentTask.task_id,
      score: Number(score),
      reflection: reflection.trim(),
    });
    setLearningFeedback(result.learning_feedback ?? null);
    const profileSyncMessage = await refreshLearnerProfileAfterGuide();
    setSaveMessage([result.learning_feedback?.summary || "学习证据已记录。", profileSyncMessage].filter(Boolean).join(" "));
    setReflection("");
  };

  const generateResource = async (
    type: GuideV2ResourceType,
    targetTaskId = currentTask?.task_id || "",
    promptOverride = "",
  ) => {
    if (!activeSessionId || !targetTaskId) return;
    setPrescriptionTaskId(targetTaskId);
    setPrescriptionFeedback(null);
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
      window.setTimeout(() => scrollToGuideSection("guide-prescription-results-section"), 160);
    } catch (error) {
      setGeneratingType(null);
      setSaveMessage(error instanceof Error ? error.message : "资源生成任务启动失败。");
    }
  };

  const refetchCoursePackage = coursePackage.refetch;
  const refetchDetail = detail.refetch;
  const refetchLearningReport = learningReport.refetch;
  const refetchSessions = sessions.refetch;
  const refetchStudyPlan = studyPlan.refetch;

  useEffect(() => {
    if (!resourceJobId) return;
    const source = openGuideV2ResourceJobEvents(resourceJobId);
    const handle = (type: string) => () => {
      if (type === "result") {
        void refetchDetail();
        void refetchStudyPlan();
        void refetchSessions();
      }
      if (type === "complete" || type === "failed") {
        if (type === "complete") {
          void refetchDetail();
          void refetchStudyPlan();
          void refetchLearningReport();
          void refetchCoursePackage();
          void refetchSessions();
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
  }, [refetchCoursePackage, refetchDetail, refetchLearningReport, refetchSessions, refetchStudyPlan, resourceJobId]);

  const deleteActiveSession = async () => {
    if (!activeSessionId || !window.confirm("删除这条学习路径？")) return;
    await mutations.remove.mutateAsync(activeSessionId);
    setSelectedSessionId(null);
  };

  const taskIdForArtifact = (artifact: GuideV2Artifact) =>
    tasks.find((task) => (task.artifact_refs ?? []).some((item) => item.id === artifact.id))?.task_id ||
    currentTask?.task_id ||
    "";

  const saveArtifact = async (artifact: GuideV2Artifact) => {
    const taskId = taskIdForArtifact(artifact);
    if (!activeSessionId || !taskId) return;
    setSaveMessage("");
    const result = await mutations.saveArtifact.mutateAsync({
      sessionId: activeSessionId,
      taskId,
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
    const taskId = taskIdForArtifact(artifact);
    if (!activeSessionId || !taskId) return;
    setSaveMessage("");
    const result = await mutations.submitQuiz.mutateAsync({
      sessionId: activeSessionId,
      taskId,
      artifactId: artifact.id,
      answers,
      saveQuestions: true,
    });
    const attempt = result.attempt ?? {};
    const scoreValue = Number(attempt.score ?? 0);
    const savedCount = result.question_notebook?.count ?? 0;
    const isPrescriptionArtifact = guideStage === "complete" && taskId === effectivePrescriptionTaskId;
    if (isPrescriptionArtifact) {
      setPrescriptionFeedback(result.learning_feedback ?? null);
      void refetchLearningReport();
      void refetchCoursePackage();
    } else {
      setLearningFeedback(result.learning_feedback ?? null);
    }
    const profileSyncMessage = await refreshLearnerProfileAfterGuide();
    setSaveMessage(
      `${isPrescriptionArtifact ? "处方复测已回写" : "练习已回写"}：得分 ${Math.round(scoreValue * 100)}%，同步 ${savedCount} 道题到题目本。 ${profileSyncMessage}`,
    );
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
    const profileSyncMessage = await refreshLearnerProfileAfterGuide();
    setSaveMessage(`前测已更新画像：准备度 ${Math.round(scoreValue * 100)}%${weak ? `，优先照顾「${weak}」` : ""}。 ${profileSyncMessage}`);
  };

  const toggleReferenceRecord = (record: NotebookRecord) => {
    const recordId = record.record_id || record.id;
    setSelectedRecordIds((current) => (current.includes(recordId) ? current.filter((id) => id !== recordId) : [...current, recordId]));
  };

  const runDemoRecordingCue = () => {
    if (!demoRecordingCue || demoRecordingCue.action === "none") return;
    if (demoRecordingCue.action === "generate_current_seed") {
      const prompt = currentDemoStep ? readString(currentDemoStep, "prompt") : "";
      const resourceType = currentDemoStep ? normalizeResourceType(readString(currentDemoStep, "resource_type")) : null;
      if (currentTask && prompt && resourceType) {
        void generateResource(resourceType, currentTask.task_id, prompt);
      }
      return;
    }
    if (demoRecordingCue.action === "open_complete_task") {
      setGuideSubPage("completeTask");
      return;
    }
    if (demoRecordingCue.action === "open_route_map") {
      setGuideSubPage("routeMap");
      scrollToGuideSection("guide-route-map-section");
      return;
    }
    if (demoRecordingCue.action === "open_course_package") {
      setGuideSubPage("coursePackage");
    }
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
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">{stageMessage}</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button tone="quiet" className="min-h-9 px-3 text-xs" onClick={() => setSupportOpen(true)}>
                <CalendarDays size={15} />
                路线
              </Button>
            </div>
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

        <DemoRecordingCueCard
          cue={demoRecordingCue}
          busy={busy || Boolean(generatingType)}
          onAction={runDemoRecordingCue}
        />

        <div className="grid gap-4">
          <main className="space-y-4">
            {guideSubPage === "setup" ? (
              <GuideSubPageFrame
                eyebrow="学习偏好"
                title="需要时再调这些"
                description="主流程可以直接开始；这里仅用于补充课程模板、时间、薄弱点和 Notebook 引用。"
                onBack={() => setGuideSubPage("main")}
              >
                <form
                  id="guide-setup-section"
                  className={`space-y-4 rounded-xl transition-all duration-500 ${
                    highlightedSectionId === "guide-setup-section" ? "ring-2 ring-teal-100 ring-offset-2 ring-offset-canvas" : ""
                  }`}
                  onSubmit={createSession}
                >
                  <SourceActionNotice action={sourceAction} />
                  <FieldShell label="你想学什么">
                    <TextArea
                      value={goal}
                      onChange={(event) => {
                        setGoalTouched(true);
                        setGoal(event.target.value);
                      }}
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

            {guideSubPage === "completeTask" && currentTask ? (
              <GuideSubPageFrame
                eyebrow="提交学习证据"
                title="完成当前任务"
                description="写下掌握评分和一句话反思，系统会据此给出下一步反馈。"
                onBack={() => setGuideSubPage("main")}
              >
                <div
                  id="guide-complete-task-section"
                  className={`grid gap-4 transition-all duration-500 lg:grid-cols-[minmax(0,1fr)_280px] ${
                    highlightedSectionId === "guide-complete-task-section" ? "rounded-xl ring-2 ring-teal-100 ring-offset-2 ring-offset-canvas" : ""
                  }`}
                >
                  <div className="rounded-lg border border-line bg-canvas p-4">
                    <div className="flex items-center justify-between gap-2">
                      <h3 className="text-sm font-semibold text-ink">完成标准</h3>
                      <Badge tone="neutral">
                        {(currentTask.success_criteria?.length ? currentTask.success_criteria : ["完成任务并写下一句话总结"]).length} 条
                      </Badge>
                    </div>
                    <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-600">
                      {(currentTask.success_criteria?.length ? currentTask.success_criteria : ["完成任务并写下一句话总结"]).slice(0, 3).map((item) => (
                        <li key={item} className="flex gap-2">
                          <CheckCircle2 size={16} className="mt-1 shrink-0 text-brand-teal" />
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="rounded-lg border border-line bg-white p-4">
                    <DemoEvidenceShortcut
                      step={currentDemoStep}
                      onApply={(nextScore, nextReflection) => {
                        setScore(nextScore);
                        setReflection(nextReflection);
                      }}
                    />
                    <FieldShell label="你现在感觉怎么样">
                      <div className="grid gap-2">
                        {taskScoreOptions.map((option) => {
                          const active = score === option.value;
                          return (
                            <button
                              key={option.value}
                              type="button"
                              className={`min-h-12 rounded-md border px-3 text-left transition ${
                                active
                                  ? "border-teal-300 bg-teal-50 text-teal-950 shadow-sm"
                                  : "border-line bg-white text-slate-700 hover:border-teal-200 hover:bg-teal-50"
                              }`}
                              onClick={() => setScore(option.value)}
                            >
                              <span className="block text-sm font-semibold">{option.label}</span>
                              <span className="mt-0.5 block text-xs text-slate-500">{option.helper}</span>
                            </button>
                          );
                        })}
                      </div>
                    </FieldShell>
                    <FieldShell label="一句话反思">
                      <TextArea
                        value={reflection}
                        onChange={(event) => setReflection(event.target.value)}
                        className="min-h-28"
                        placeholder="我已经理解了……还不确定的是……"
                      />
                    </FieldShell>
                    <Button
                      tone="primary"
                      className="mt-3 w-full"
                      data-testid="guide-submit-task-feedback"
                      onClick={() => void completeCurrentTask()}
                      disabled={busy || !activeSessionId}
                    >
                      {mutations.completeTask.isPending ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
                      完成并获得反馈
                    </Button>
                  </div>
                </div>
              </GuideSubPageFrame>
            ) : null}

            {guideSubPage === "resourceChoice" && currentTask ? (
              <GuideSubPageFrame
                eyebrow="学习材料"
                title="选择一种学习材料"
                description="系统已经把推荐项放在主流程里；这里仅用于你想换一种学习方式时使用。"
                onBack={() => setGuideSubPage("main")}
              >
                <div className="rounded-lg border border-teal-100 bg-teal-50 p-4">
                  <Badge tone="brand">当前任务</Badge>
                  <h3 className="mt-3 text-base font-semibold text-teal-950">{currentTask.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-teal-900">
                    不确定怎么选就返回主流程，直接使用系统推荐。每次生成的材料都会回到当前任务里分页展示。
                  </p>
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  {resourceActions.map((action, index) => {
                    const recommended = index === 0;
                    return (
                      <button
                        key={action.type}
                        type="button"
                        data-testid={`guide-resource-choice-${action.type}`}
                        disabled={!activeSessionId || busy || Boolean(generatingType)}
                        className={`min-h-32 rounded-lg border p-4 text-left transition disabled:cursor-not-allowed disabled:opacity-60 ${
                          recommended
                            ? "border-teal-200 bg-teal-50 hover:border-teal-300"
                            : "border-line bg-white hover:border-blue-200 hover:bg-blue-50"
                        }`}
                        onClick={() => {
                          setGuideSubPage("main");
                          void generateResource(action.type);
                        }}
                      >
                        <span className="flex items-center justify-between gap-2">
                          <span className="inline-flex items-center gap-2 text-sm font-semibold text-ink">
                            {generatingType === action.type ? <Loader2 size={16} className="animate-spin" /> : guideResourceIcon(action.type, 16)}
                            {action.label}
                          </span>
                          {recommended ? <Badge tone="brand">推荐</Badge> : <Badge tone="neutral">{resourceLabel(action.type)}</Badge>}
                        </span>
                        <span className="mt-3 block text-sm leading-6 text-slate-600">{guideResourceDescription(action.type)}</span>
                      </button>
                    );
                  })}
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
                <section
                  id="guide-route-map-section"
                  className={`rounded-lg border bg-white p-5 transition-all duration-500 ${
                    highlightedSectionId === "guide-route-map-section"
                      ? "border-teal-300 ring-2 ring-teal-100"
                      : "border-line"
                  }`}
                >
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

            {guideSubPage === "coursePackage" && session ? (
              <GuideSubPageFrame
                eyebrow="学习产出"
                title="课程产出包"
                description="把本轮学习整理成可以保存和复盘的成果。"
                onBack={() => setGuideSubPage("main")}
              >
                <CoursePackagePanel
                  coursePackage={coursePackage.data ?? null}
                  loading={coursePackage.isFetching}
                  canSave={Boolean(activeSessionId && saveNotebookId)}
                  saving={mutations.saveCoursePackage.isPending}
                  onSave={() => void saveCoursePackage()}
                />
              </GuideSubPageFrame>
            ) : null}

            {guideSubPage === "main" ? (
              <>
            {!session ? (
              <section id="guide-create-section" className="rounded-lg border border-line bg-white p-5 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <Badge tone="brand">先做这一件事</Badge>
                    <h2 className="mt-3 text-xl font-semibold text-ink">{primaryActionLabel}</h2>
                    <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
                      写下目标、时间和偏好即可。路线、前测、资源和反馈都会在后面自动接上，不需要你自己找入口。
                    </p>
                  </div>
                </div>
                <form className="mt-6 space-y-4" onSubmit={createSession}>
                  <SourceActionNotice action={sourceAction} />
                  {!sourceAction && profileSuggestedPrompt && goal.trim() === profileSuggestedPrompt ? (
                    <p className="rounded-lg border border-teal-100 bg-teal-50 px-3 py-2 text-xs leading-5 text-teal-800">
                      已根据学习画像填好目标。你可以直接开始，也可以改成自己的说法。
                    </p>
                  ) : null}
                  <DemoQuickStartCard
                    template={demoTemplate}
                    loading={templates.isFetching}
                    busy={mutations.create.isPending}
                    onStart={startDemoSession}
                  />
                  <FieldShell label="你想学什么">
                    <TextArea
                      value={goal}
                      onChange={(event) => {
                        setGoalTouched(true);
                        setGoal(event.target.value);
                      }}
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
                    className="mx-auto flex min-h-10 items-center justify-center rounded-md px-3 text-sm font-medium text-slate-500 transition hover:bg-canvas hover:text-brand-teal"
                    onClick={() => setGuideSubPage("setup")}
                  >
                    需要更细设置
                  </button>
                </form>
              </section>
            ) : null}

            {session && guideStage === "diagnostic" ? (
              <>
                <section
                  id="guide-diagnostic-section"
                  className={`rounded-lg border bg-white p-5 shadow-sm transition-all duration-500 ${
                    highlightedSectionId === "guide-diagnostic-section"
                      ? "border-teal-300 ring-2 ring-teal-100"
                      : "border-teal-200"
                  }`}
                >
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
              </>
            ) : null}

            {session && guideStage === "feedback" ? (
              <div
                id="guide-feedback-section"
                className={`rounded-xl transition-all duration-500 ${
                  highlightedSectionId === "guide-feedback-section" ? "ring-2 ring-teal-100 ring-offset-2 ring-offset-canvas" : ""
                }`}
              >
                <LearningFeedbackCard
                  feedback={activeLearningFeedback}
                  disabled={busy || Boolean(generatingType)}
                  profileRefreshing={learnerProfileMutations.refresh.isPending}
                  onGenerateResource={(type, taskId, prompt) => void generateResource(type, taskId, prompt)}
                  onOpenCurrentTask={() => scrollToGuideSection("guide-current-task-section")}
                  onOpenRouteMap={() => {
                    setGuideSubPage("routeMap");
                    scrollToGuideSection("guide-route-map-section");
                  }}
                />
                <DemoWrapUpCard
                  enabled={isDemoSeedSession}
                  report={learningReport.data ?? null}
                  loading={learningReport.isFetching}
                  onOpenCoursePackage={() => setGuideSubPage("coursePackage")}
                  onOpenRouteMap={() => {
                    setGuideSubPage("routeMap");
                    scrollToGuideSection("guide-route-map-section");
                  }}
                />
              </div>
            ) : null}

            {session && (guideStage === "learn" || guideStage === "feedback") ? (
              <>
                <section
                  id="guide-current-task-section"
                  className={`rounded-lg border bg-white p-5 shadow-sm transition-all duration-500 ${
                    highlightedSectionId === "guide-current-task-section"
                      ? "border-teal-300 ring-2 ring-teal-100"
                      : "border-line"
                  }`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <Badge tone="brand">{guideStage === "feedback" ? "接着做这一步" : "先做这一件事"}</Badge>
                      <h2 className="mt-3 text-xl font-semibold text-ink">{currentTask?.title || "路线正在整理下一步"}</h2>
                      <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                        {currentTask?.instruction || "系统会把目标拆成可执行任务，并根据完成情况更新掌握度与下一步建议。"}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge tone={planStatusTone(currentTask?.status || "pending")}>{planStatusLabel(currentTask?.status || "pending")}</Badge>
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
                      <DemoTaskShortcutCard
                        step={currentDemoStep}
                        busy={busy || Boolean(generatingType)}
                        generatingType={generatingType}
                        onGenerate={(type, prompt) => void generateResource(type, currentTask.task_id, prompt)}
                      />
                      <div className="rounded-lg border border-teal-100 bg-teal-50 p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div>
                            <p className="text-sm font-semibold text-teal-950">系统建议先做这个</p>
                            <p className="mt-1 text-xs leading-5 text-teal-800">不想纠结资源类型，直接点这个就行。</p>
                          </div>
                          <Badge tone="brand">{resourceLabel(primaryResourceAction.type)}</Badge>
                        </div>
                        <Button
                          tone="primary"
                          className="mt-3 min-h-12 w-full justify-center text-base"
                          disabled={!activeSessionId || busy || Boolean(generatingType)}
                          onClick={() => void generateResource(primaryResourceAction.type)}
                        >
                          {generatingType === primaryResourceAction.type ? <Loader2 size={18} className="animate-spin" /> : guideResourceIcon(primaryResourceAction.type, 18)}
                          {primaryResourceAction.label}
                        </Button>
                      </div>
                      {adaptiveGuideStrategy.reasons[0]?.detail ? (
                        <p className="rounded-lg border border-teal-100 bg-teal-50 px-3 py-2 text-xs leading-5 text-teal-800">
                          画像依据：{adaptiveGuideStrategy.reasons[0].detail}
                        </p>
                      ) : null}
                      <div className="space-y-2">
                        <button
                          type="button"
                          data-testid="guide-open-complete-task"
                          className="w-full rounded-lg border border-line bg-canvas p-4 text-left transition hover:border-teal-200 hover:bg-teal-50"
                          onClick={() => setGuideSubPage("completeTask")}
                        >
                          <span className="text-sm font-semibold text-ink">学完了，去提交</span>
                          <span className="mt-1 block text-xs leading-5 text-slate-500">选一下掌握状态，写一句反思，系统再给反馈。</span>
                        </button>
                        <button
                          type="button"
                          data-testid="guide-open-resource-choice"
                          className="ml-auto block rounded-md px-2 py-1 text-xs font-medium text-brand-blue transition hover:bg-blue-50 hover:text-blue-700"
                          onClick={() => setGuideSubPage("resourceChoice")}
                        >
                          不适合？换一种材料
                        </button>
                      </div>
                    </div>
                  ) : null}
                </section>

                {currentArtifacts.length || generatingType ? (
                <section
                  id="guide-resource-results-section"
                  className={`rounded-lg border bg-white p-5 transition-all duration-500 ${
                    highlightedSectionId === "guide-resource-results-section"
                      ? "border-teal-300 ring-2 ring-teal-100"
                      : "border-line"
                  }`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h2 className="text-base font-semibold text-ink">你的学习材料</h2>
                      <p className="mt-1 text-sm leading-6 text-slate-500">
                        按顺序来：先看懂，再验证，最后提交当前任务。
                      </p>
                    </div>
                    <Badge tone={generatingType ? "brand" : currentArtifacts.length ? "brand" : "neutral"}>
                      {generatingType ? "准备中" : `已准备 ${currentArtifacts.length} 份`}
                    </Badge>
                  </div>
                  <div className="mt-5 space-y-3">
                    {generatingType ? (
                      <div className="flex items-center gap-2 rounded-lg border border-teal-200 bg-teal-50 p-3 text-sm text-teal-800">
                        <Loader2 size={16} className="animate-spin" />
                        正在准备{resourceLabel(generatingType)}，好了会自动出现在这里。
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
                        onCompleteTask={() => setGuideSubPage("completeTask")}
                      />
                    ) : null}
                    {currentTask && !currentArtifacts.length ? (
                      <p className="rounded-lg border border-dashed border-line bg-canvas p-4 text-sm text-slate-500">
                        还没有学习材料。建议先点“{primaryResourceAction.label}”，看完后再回来提交当前任务。
                      </p>
                    ) : null}
                  </div>
                </section>
                ) : null}
              </>
            ) : null}

            {session && guideStage === "complete" ? (
              <section
                id="guide-complete-section"
                className={`rounded-lg border bg-white p-5 shadow-sm transition-all duration-500 ${
                  highlightedSectionId === "guide-complete-section"
                    ? "border-teal-300 ring-2 ring-teal-100"
                    : "border-line"
                }`}
              >
                <Badge tone="success">路线完成</Badge>
                <h2 className="mt-3 text-xl font-semibold text-ink">你已经走完这条学习路线</h2>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                  先看总结，再决定下一轮学什么。
                </p>
                <div className="mt-4">
                  <LearningReportPanel
                    report={learningReport.data ?? null}
                    loading={learningReport.isFetching}
                    canSave={Boolean(activeSessionId && saveNotebookId)}
                    saving={mutations.saveReport.isPending}
                    onSave={() => void saveLearningReport()}
                    onOpenRouteMap={() => setGuideSubPage("routeMap")}
                    onOpenCoursePackage={() => setGuideSubPage("coursePackage")}
                    onGenerateResource={(type, taskId, prompt) => void generateResource(type, taskId, prompt)}
                  />
                </div>
                {prescriptionFeedback ? (
                  <PrescriptionFeedbackNotice
                    feedback={prescriptionFeedback}
                    onReviewReport={() => scrollToGuideSection("guide-complete-section")}
                    onOpenMemory={() => {
                      window.location.href = "/memory";
                    }}
                  />
                ) : null}
                {showPrescriptionResults ? (
                  <div
                    id="guide-prescription-results-section"
                    className={`mt-4 rounded-lg border bg-white p-4 transition-all duration-500 ${
                      highlightedSectionId === "guide-prescription-results-section"
                        ? "border-teal-300 ring-2 ring-teal-100"
                        : "border-line"
                    }`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-ink">处方产物</p>
                        <p className="mt-1 text-xs leading-5 text-slate-500">
                          {prescriptionTask?.title
                            ? `围绕「${prescriptionTask.title}」生成，学完后回到报告继续调整。`
                            : "围绕学习处方生成，完成后可以保存或提交。"}
                        </p>
                      </div>
                      <Badge tone={generatingType ? "brand" : prescriptionArtifacts.length ? "success" : "neutral"}>
                        {generatingType ? "准备中" : `已生成 ${prescriptionArtifacts.length} 份`}
                      </Badge>
                    </div>
                    <div className="mt-3 space-y-3">
                      {generatingType ? (
                        <div className="flex items-center gap-2 rounded-lg border border-teal-200 bg-teal-50 p-3 text-sm text-teal-800">
                          <Loader2 size={16} className="animate-spin" />
                          正在准备{resourceLabel(generatingType)}，完成后会出现在这里。
                        </div>
                      ) : null}
                      {prescriptionArtifacts.length ? (
                        <ResourceArtifactPager
                          artifacts={prescriptionArtifacts}
                          saveNotebookId={saveNotebookId}
                          saving={mutations.saveArtifact.isPending}
                          quizSubmitting={mutations.submitQuiz.isPending}
                          onSave={(artifact) => void saveArtifact(artifact)}
                          onSubmitQuiz={(artifact, answers) => void submitQuizArtifact(artifact, answers)}
                          onCompleteTask={() => scrollToGuideSection("guide-complete-section")}
                          finalLabel="回到报告"
                          finalHint="看完产物后，继续按学习处方调整。"
                        />
                      ) : null}
                    </div>
                  </div>
                ) : null}
                <button
                  type="button"
                  className="mt-4 w-full rounded-lg border border-line bg-canvas p-4 text-left transition hover:border-teal-200 hover:bg-teal-50"
                  onClick={() => setGuideSubPage("coursePackage")}
                >
                  <span className="text-sm font-semibold text-ink">查看课程产出包</span>
                  <span className="mt-1 block text-xs leading-5 text-slate-500">项目、评分标准和复习重点放在单独页面里。</span>
                </button>
              </section>
            ) : null}

            {session ? (
              <button
                type="button"
                className="mx-auto flex min-h-10 items-center justify-center rounded-md px-3 text-sm font-medium text-slate-500 transition hover:bg-white hover:text-brand-teal"
                onClick={() => setGuideSubPage("routeMap")}
              >
                查看完整路线
              </button>
            ) : null}
              </>
            ) : null}
          </main>

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
                aria-label="关闭路线面板"
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
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-brand-teal">路线</p>
                    <h2 className="mt-1 text-lg font-semibold text-ink">切换或重新开始</h2>
                  </div>
                  <Button tone="quiet" className="min-h-8 px-2" onClick={() => setSupportOpen(false)}>
                    <X size={16} />
                  </Button>
                </div>

                <div className="space-y-4">
                  <section className="rounded-lg border border-line bg-white p-4">
                    <h2 className="text-base font-semibold text-ink">历史路线</h2>
                    <p className="mt-1 text-xs leading-5 text-slate-500">只在想回看或切换时使用。</p>
                    <div className="mt-4 space-y-3">
                      <Button
                        tone="primary"
                        className="w-full"
                        onClick={() => {
                          setForceNewSession(true);
                          setSourceAction(null);
                          setSelectedSessionId(null);
                          setGuideSubPage("main");
                          setSupportOpen(false);
                        }}
                      >
                        <Sparkles size={16} />
                        新建一条路线
                      </Button>
                      <div className="max-h-52 space-y-2 overflow-y-auto pr-1">
                        {(sessions.data ?? []).slice(0, 5).map((item) => (
                          <button
                            key={item.session_id}
                            type="button"
                            onClick={() => {
                              setForceNewSession(false);
                              setSourceAction(null);
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
                    <div className="flex items-start gap-3">
                      <Brain size={18} className="mt-0.5 text-brand-teal" />
                      <div>
                        <h2 className="text-base font-semibold text-ink">画像已参与</h2>
                        <p className="mt-1 text-sm leading-6 text-slate-600">
                          {routeUsesUnifiedProfile
                            ? "这条路线已经参考你的偏好和薄弱点。"
                            : "完成前测、练习和反思后，画像会继续变准。"}
                        </p>
                      </div>
                    </div>
                    <a
                      href="/memory"
                      className="mt-3 inline-flex min-h-9 items-center justify-center rounded-md border border-line bg-canvas px-3 text-xs font-medium text-slate-700 transition hover:border-teal-200 hover:text-brand-teal"
                    >
                      查看学习画像
                    </a>
                  </section>

                  {currentTask ? (
                    <section className="rounded-lg border border-line bg-white p-4">
                      <div className="flex items-start gap-3">
                        <Target size={18} className="mt-0.5 text-brand-teal" />
                        <div>
                          <h2 className="text-base font-semibold text-ink">当前一步</h2>
                          <p className="mt-1 text-sm font-semibold leading-6 text-ink">{currentTask.title}</p>
                          <p className="mt-1 line-clamp-3 text-xs leading-5 text-slate-600">{currentTask.instruction || "继续完成当前任务。"}</p>
                        </div>
                      </div>
                    </section>
                  ) : null}

                  <div className="rounded-lg border border-line bg-white p-3">
                    <p className="text-xs font-semibold text-slate-500">路线管理</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Button
                        tone="quiet"
                        className="min-h-8 px-2 text-xs"
                        disabled={!activeSessionId || busy}
                        onClick={() => activeSessionId && mutations.refreshRecommendations.mutate(activeSessionId)}
                      >
                        <RefreshCw size={14} />
                        重新整理
                      </Button>
                      <Button
                        tone="quiet"
                        className="min-h-8 px-2 text-xs text-brand-red hover:bg-red-50"
                        disabled={!activeSessionId || busy}
                        onClick={() => void deleteActiveSession()}
                      >
                        <Trash2 size={14} />
                        删除
                      </Button>
                    </div>
                  </div>
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

function SourceActionNotice({ action }: { action: Record<string, unknown> | null }) {
  if (!action) return null;
  const title = readString(action, "title") || "学习画像建议";
  const sourceLabel = readString(action, "source_label");
  const suggestedPrompt = readString(action, "suggested_prompt");
  const kind = readString(action, "kind");
  const confidence = Number(action.confidence);
  const minutes = Number(action.estimated_minutes);
  const kindLabel =
    kind === "weak_point"
      ? "薄弱点接力"
      : kind === "mastery" || kind === "mastery_check" || kind === "mastery_support"
        ? "掌握度接力"
        : "画像推荐";
  return (
    <motion.div
      className="rounded-lg border border-teal-100 bg-teal-50 px-4 py-3"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18 }}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="brand">画像已带入</Badge>
        <Badge tone="neutral">{kindLabel}</Badge>
        {Number.isFinite(minutes) && minutes > 0 ? <Badge tone="neutral">{Math.round(minutes)} 分钟</Badge> : null}
        {Number.isFinite(confidence) && confidence > 0 ? <Badge tone="neutral">依据 {Math.round(Math.min(confidence, 1) * 100)}%</Badge> : null}
      </div>
      <h3 className="mt-3 text-sm font-semibold text-teal-950">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-teal-900">
        {sourceLabel ? `这次先围绕「${sourceLabel}」安排学习。` : "这次会直接按画像建议安排学习。"}
        你可以直接创建路线，系统会先做前测，再给资源和练习。
      </p>
      {suggestedPrompt ? <p className="mt-2 rounded-md bg-white/75 px-3 py-2 text-sm leading-6 text-slate-700">{suggestedPrompt}</p> : null}
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs leading-5 text-slate-600">不准也没关系，画像页随时能改。</p>
        <a
          href="/memory"
          className="inline-flex min-h-9 items-center justify-center rounded-md border border-line bg-white px-3 text-xs font-medium text-slate-700 transition hover:border-teal-200 hover:text-brand-teal"
        >
          回到画像页
        </a>
      </div>
    </motion.div>
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
      {template.demo_seed?.scenario ? (
        <p className="mt-3 rounded-lg border border-teal-100 bg-white/80 p-2 text-xs leading-5 text-teal-900">
          推荐演示：{template.demo_seed.scenario}
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

function DemoQuickStartCard({
  template,
  loading,
  busy,
  onStart,
}: {
  template: GuideV2CourseTemplate | null;
  loading: boolean;
  busy: boolean;
  onStart: () => void;
}) {
  if (loading || !template?.demo_seed) {
    return null;
  }

  const chain = template.demo_seed.task_chain ?? [];
  const chainText = chain
    .slice(0, 3)
    .map((item) => item.task_id || item.title)
    .filter(Boolean)
    .join(" / ");

  return (
    <div className="rounded-lg border border-blue-100 bg-blue-50 p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">比赛演示</Badge>
            <Badge tone="neutral">{template.course_name || template.title}</Badge>
          </div>
          <p className="mt-2 text-sm font-semibold text-ink">{template.demo_seed.title || "稳定 Demo 样例"}</p>
          <p className="mt-1 max-w-2xl text-xs leading-5 text-slate-600">
            {template.demo_seed.scenario || "一键创建可复现演示路线。"}
          </p>
          {chainText ? <p className="mt-2 text-xs text-slate-500">推荐顺序：{chainText}</p> : null}
        </div>
        <Button tone="primary" className="min-h-9 px-3 text-xs" data-testid="guide-demo-start" disabled={busy} onClick={onStart}>
          {busy ? <Loader2 size={14} className="animate-spin" /> : <Video size={14} />}
          开始稳定演示
        </Button>
      </div>
    </div>
  );
}

function DemoRecordingCueCard({
  cue,
  busy,
  onAction,
}: {
  cue: DemoRecordingCue | null;
  busy: boolean;
  onAction: () => void;
}) {
  if (!cue) {
    return null;
  }

  return (
    <motion.section
      className="rounded-lg border border-blue-100 bg-white p-4 shadow-sm"
      data-testid="guide-demo-recording-cue"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.16, ease: "easeOut" }}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">录屏下一步</Badge>
            <Badge tone={cue.tone}>{cue.actionLabel}</Badge>
          </div>
          <h2 className="mt-2 text-base font-semibold text-ink">{cue.title}</h2>
          <p className="mt-1 max-w-2xl text-xs leading-5 text-slate-600">{cue.detail}</p>
        </div>
        {cue.action !== "none" ? (
          <Button
            tone={cue.tone === "success" ? "secondary" : "primary"}
            className="min-h-10 px-3 text-xs"
            data-testid="guide-demo-cue-action"
            disabled={busy}
            onClick={onAction}
          >
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Video size={14} />}
            {cue.actionLabel}
          </Button>
        ) : (
          <Loader2 size={16} className="animate-spin text-brand-blue" />
        )}
      </div>
    </motion.section>
  );
}

function DemoTaskShortcutCard({
  step,
  busy,
  generatingType,
  onGenerate,
}: {
  step: Record<string, unknown> | null;
  busy: boolean;
  generatingType: GuideV2ResourceType | null;
  onGenerate: (type: GuideV2ResourceType, prompt: string) => void;
}) {
  if (!step) {
    return null;
  }

  const prompt = readString(step, "prompt");
  const resourceType = normalizeResourceType(readString(step, "resource_type"));
  if (!prompt || !resourceType) {
    return null;
  }

  const stage = readString(step, "stage") || "稳定演示";
  const show = readString(step, "show") || "使用内置 Demo 提示词生成稳定素材。";

  return (
    <div className="rounded-lg border border-blue-100 bg-blue-50 p-3" data-testid="guide-demo-task-shortcut">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">{stage}</Badge>
            <Badge tone="neutral">{resourceLabel(resourceType)}</Badge>
          </div>
          <p className="mt-2 text-sm font-semibold text-ink">使用稳定提示词生成</p>
          <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-600">{show}</p>
        </div>
        <Button tone="primary" className="min-h-9 px-3 text-xs" data-testid="guide-demo-generate" disabled={busy} onClick={() => onGenerate(resourceType, prompt)}>
          {generatingType === resourceType ? <Loader2 size={14} className="animate-spin" /> : guideResourceIcon(resourceType, 14)}
          生成{resourceLabel(resourceType)}
        </Button>
      </div>
      <p className="mt-2 line-clamp-2 rounded-lg border border-blue-100 bg-white p-2 text-xs leading-5 text-slate-500">
        {prompt}
      </p>
    </div>
  );
}

function DemoEvidenceShortcut({
  step,
  onApply,
}: {
  step: Record<string, unknown> | null;
  onApply: (score: string, reflection: string) => void;
}) {
  if (!step) {
    return null;
  }

  const reflection = readString(step, "sample_reflection");
  if (!reflection) {
    return null;
  }

  const rawScore = Number(step.sample_score ?? 0.72);
  const normalizedScore = Number.isFinite(rawScore) ? Math.max(0, Math.min(rawScore, 1)) : 0.72;
  const scoreValue = normalizedScore >= 0.8 ? "0.9" : normalizedScore >= 0.6 ? "0.7" : "0.45";

  return (
    <div className="mb-4 rounded-lg border border-blue-100 bg-blue-50 p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Badge tone="brand">演示样例</Badge>
          <p className="mt-2 text-sm font-semibold text-ink">一键填入示例反馈</p>
          <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-600">{reflection}</p>
        </div>
        <Button tone="secondary" className="min-h-9 px-3 text-xs" data-testid="guide-demo-apply-feedback" onClick={() => onApply(scoreValue, reflection)}>
          <CheckCircle2 size={14} />
          带入
        </Button>
      </div>
    </div>
  );
}

function DemoWrapUpCard({
  enabled,
  report,
  loading,
  onOpenCoursePackage,
  onOpenRouteMap,
}: {
  enabled: boolean;
  report: GuideV2LearningReport | null;
  loading: boolean;
  onOpenCoursePackage: () => void;
  onOpenRouteMap: () => void;
}) {
  if (!enabled) {
    return null;
  }

  const readiness = report?.demo_readiness ?? null;
  const checks = readiness?.checks ?? [];
  const readyCount = checks.filter((item) => item.status === "ready").length;
  const score = Number(readiness?.score ?? 0);
  const nextStep =
    readiness?.next_steps?.[0] ||
    report?.action_brief?.summary ||
    "接着展示路线、学习报告和课程产出包，把画像、资源、练习、反馈串成一条闭环。";

  return (
    <motion.section
      className="mt-3 rounded-lg border border-blue-100 bg-blue-50 p-4"
      data-testid="guide-demo-wrap-up"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">演示收尾</Badge>
            <Badge tone={effectStatusTone(score)}>
              {loading ? "检查中" : guideDisplayText(readiness?.label, "准备中")}
            </Badge>
            {checks.length ? <Badge tone="neutral">{readyCount}/{checks.length} 项就绪</Badge> : null}
          </div>
          <h3 className="mt-3 text-base font-semibold text-ink">下一步看路线与产出包</h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            {guideDisplayText(readiness?.summary, "这次反馈已经回写学习画像。录屏时接着展示路线调整、演示就绪度和最终课程产出包。")}
          </p>
        </div>
        {loading ? <Loader2 size={16} className="animate-spin text-brand-blue" /> : <BarChart3 size={18} className="text-brand-blue" />}
      </div>
      <p className="mt-3 rounded-lg border border-blue-100 bg-white p-2 text-xs leading-5 text-slate-600">
        建议：{guideDisplayText(nextStep)}
      </p>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <Button tone="secondary" className="min-h-10 justify-center" data-testid="guide-demo-open-route-map" onClick={onOpenRouteMap}>
          <Map size={15} />
          看路线
        </Button>
        <Button tone="primary" className="min-h-10 justify-center" data-testid="guide-demo-open-course-package" onClick={onOpenCoursePackage}>
          <BookOpen size={15} />
          看产出包
        </Button>
      </div>
    </motion.section>
  );
}

function LearningFeedbackCard({
  feedback,
  disabled,
  profileRefreshing,
  onGenerateResource,
  onOpenCurrentTask,
  onOpenRouteMap,
}: {
  feedback: GuideV2LearningFeedback | null;
  disabled: boolean;
  profileRefreshing: boolean;
  onGenerateResource: (type: GuideV2ResourceType, taskId: string, prompt: string) => void;
  onOpenCurrentTask: () => void;
  onOpenRouteMap: () => void;
}) {
  if (!feedback) return null;
  const resourceActions = (feedback.resource_actions ?? []).filter((item) => !isResearchResourceType(item.resource_type || ""));
  const decision = buildFeedbackDecision(feedback, resourceActions);
  const primaryPath =
    decision.paths.find((path) => path.primary) ??
    decision.paths[0] ?? {
      label: "回到当前任务",
      description: "先回到当前任务，把刚学完的内容再压实一下。",
      primary: true,
      action: { kind: "current_task", label: "回到当前任务" } as FeedbackDecisionUiAction,
    };
  const secondaryPaths = decision.paths.filter((path) => path.label !== primaryPath.label).slice(0, 2);
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
            <p className="text-sm font-semibold text-brand-teal">这一步完成了</p>
            <Badge tone={feedbackTone(feedback.tone)}>{feedback.score_percent == null ? "已记录" : `${Math.round(feedback.score_percent)} 分`}</Badge>
          </div>
          <h2 className="mt-3 text-lg font-semibold text-ink">{feedback.title || "学习证据已记录"}</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            {feedback.summary || "系统已经根据这次学习证据更新路线。"}
          </p>
        </div>
        {feedback.next_task_title ? <Badge tone="brand">下一步</Badge> : <Badge tone="success">完成</Badge>}
      </div>

      <div className="mt-4 rounded-lg border border-teal-100 bg-teal-50 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="text-sm font-semibold text-brand-teal">接下来只做这个</p>
            <h3 className="mt-2 text-base font-semibold text-teal-950">{primaryPath.label}</h3>
            <p className="mt-1 text-sm leading-6 text-teal-800">{primaryPath.description || decision.summary}</p>
          </div>
          <Badge tone={decision.tone}>{decision.badge}</Badge>
        </div>
        <div className="mt-4">
          <FeedbackPathButton
            path={primaryPath}
            disabled={disabled}
            onGenerateResource={onGenerateResource}
            onOpenCurrentTask={onOpenCurrentTask}
            onOpenRouteMap={onOpenRouteMap}
          />
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {secondaryPaths.map((path) => (
          <FeedbackPathButton
            key={path.label}
            path={path}
            compact
            disabled={disabled}
            onGenerateResource={onGenerateResource}
            onOpenCurrentTask={onOpenCurrentTask}
            onOpenRouteMap={onOpenRouteMap}
          />
        ))}
        <a
          href="/memory"
          className="inline-flex min-h-9 items-center justify-center rounded-md px-3 text-xs font-medium text-slate-500 transition hover:bg-canvas hover:text-brand-teal"
        >
          {profileRefreshing ? "画像同步中" : "查看画像变化"}
        </a>
      </div>
    </motion.section>
  );
}

function FeedbackPathButton({
  path,
  compact = false,
  disabled,
  onGenerateResource,
  onOpenCurrentTask,
  onOpenRouteMap,
}: {
  path: FeedbackDecisionPath;
  compact?: boolean;
  disabled: boolean;
  onGenerateResource: (type: GuideV2ResourceType, taskId: string, prompt: string) => void;
  onOpenCurrentTask: () => void;
  onOpenRouteMap: () => void;
}) {
  const tone = path.primary && !compact ? "primary" : compact ? "quiet" : "secondary";
  const className = compact ? "min-h-9 px-3 text-xs" : "w-full min-h-11 justify-center text-sm";

  if (path.action.kind === "resource") {
    const action = path.action;
    return (
      <Button
        tone={tone}
        className={className}
        disabled={disabled || !action.taskId}
        onClick={() => onGenerateResource(action.resourceType, action.taskId, action.prompt)}
      >
        <Lightbulb size={compact ? 14 : 16} />
        {compact ? path.label : action.label}
      </Button>
    );
  }

  if (path.action.kind === "current_task") {
    return (
      <Button tone={tone} className={className} onClick={onOpenCurrentTask}>
        <Target size={compact ? 14 : 16} />
        {compact ? path.label : path.action.label}
      </Button>
    );
  }

  return (
    <Button tone={tone} className={className} onClick={onOpenRouteMap}>
      <Compass size={compact ? 14 : 16} />
      {compact ? path.label : path.action.label}
    </Button>
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
    const timer = window.setTimeout(() => {
    if (!items.length) {
      setSelectedNodeId("");
      return;
    }
    setSelectedNodeId((current) => {
      if (current && items.some((item) => item.nodeId === current)) return current;
      return currentNodeId || items[0].nodeId;
    });
    }, 0);
    return () => window.clearTimeout(timer);
  }, [currentNodeId, items]);

  if (!items.length) {
    return <p className="mt-4 rounded-lg border border-dashed border-line bg-canvas p-4 text-sm text-slate-500">生成路线后展示知识地图。</p>;
  }

  const selected = items.find((item) => item.nodeId === selectedNodeId) ?? items[0];
  const masteredCount = items.filter((item) => item.status === "mastered").length;
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
            <Badge tone="neutral">{questionDifficultyLabel(selected.difficulty)}</Badge>
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
  onOpenRouteMap,
  onOpenCoursePackage,
  onGenerateResource,
}: {
  report: GuideV2LearningReport | null;
  loading: boolean;
  canSave: boolean;
  saving: boolean;
  onSave: () => void;
  onOpenRouteMap: () => void;
  onOpenCoursePackage: () => void;
  onGenerateResource: (type: GuideV2ResourceType, taskId: string, prompt: string) => void;
}) {
  const overview = report?.overview ?? {};
  const nodes = report?.node_cards ?? [];
  const score = Number(overview.overall_score ?? 0);
  const progress = Number(overview.progress ?? 0);
  const feedbackDigest = report?.feedback_digest;
  const latestFeedback = feedbackDigest?.latest;
  const feedbackRoutingSummary = summarizeFeedbackRouting(
    (feedbackDigest?.items ?? []).map((item) => ({
      score_percent: item.score_percent,
      actions: item.actions,
      adjustment_types: [],
    })),
  );
  const profileContext = asRecord(report?.learner_profile_context);
  const profileWeakPoints = Array.isArray(profileContext?.weak_points) ? profileContext.weak_points.map(String) : [];
  const nextActionSteps = buildNextActionSteps(report?.next_plan ?? [], feedbackRoutingSummary, profileWeakPoints);
  const actionBrief =
    report?.action_brief ??
    (nextActionSteps[0]
      ? {
          title: nextActionSteps[0].title,
          summary: nextActionSteps[0].detail,
          primary_action: {
            label: "查看完整路线",
            detail: "回到路线页继续执行下一步。",
            kind: "route_map",
          },
          secondary_actions: [],
          signals: [],
        }
      : null);
  const demoReadiness = report?.demo_readiness ?? null;
  const mistakeReview = report?.mistake_review;
  const mistakeClusters = mistakeReview?.clusters ?? [];
  const attentionItems: Array<{ label: string; detail: string; tone: "neutral" | "brand" | "success" | "warning" | "danger" }> = [
    ...mistakeClusters.slice(0, 1).map((cluster) => ({
      label: `错因：${cluster.label}`,
      detail: cluster.suggested_action || "先复测并记录修正后的理解。",
      tone: "warning" as const,
    })),
    ...nodes.slice(0, 1).map((node) => ({
      label: `知识点：${node.title || node.node_id}`,
      detail: node.suggestion || "继续完成任务并留下学习证据。",
      tone: "brand" as const,
    })),
    ...(report?.risks ?? []).slice(0, 1).map((item) => ({
      label: "风险",
      detail: item,
      tone: "warning" as const,
    })),
  ].slice(0, 3);
  return (
    <section className="rounded-lg border border-line bg-white p-4" data-testid="guide-learning-report-panel">
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
      <div className="mt-4 grid grid-cols-3 gap-2">
        <EvalMini label="分数" value={score} />
        <EvalMini label="进度" value={progress} suffix="%" />
        <EvalMini label="反馈" value={Number(feedbackDigest?.count ?? 0)} suffix="次" />
      </div>
      <ReportActionBriefCard
        brief={actionBrief}
        canSave={canSave}
        saving={saving}
        onSave={onSave}
        onOpenRouteMap={onOpenRouteMap}
        onOpenCoursePackage={onOpenCoursePackage}
        onGenerateResource={onGenerateResource}
      />
      <DemoReadinessCard readiness={demoReadiness} />
      {attentionItems.length ? (
        <div className="mt-4 rounded-lg border border-line bg-canvas p-3">
          <p className="text-sm font-semibold text-ink">留意这几点</p>
          <div className="mt-3 space-y-2">
            {attentionItems.map((item) => (
              <div key={`${item.label}-${item.detail}`} className="rounded-lg border border-line bg-white p-2">
                <div className="flex items-center gap-2">
                  <Badge tone={item.tone}>{item.label}</Badge>
                </div>
                <p className="mt-2 text-xs leading-5 text-slate-600">{item.detail}</p>
              </div>
            ))}
          </div>
        </div>
      ) : null}
      {latestFeedback ? (
        <p className="mt-4 rounded-lg border border-line bg-white p-3 text-xs leading-5 text-slate-600">
          最近反馈：{latestFeedback.summary || latestFeedback.title || "系统已根据学习证据更新路线。"}
        </p>
      ) : null}
      <Button tone="secondary" className="mt-4 w-full" disabled={!canSave || saving || !report} onClick={onSave}>
        {saving ? <Loader2 size={16} className="animate-spin" /> : <BookOpen size={16} />}
        保存报告到 Notebook
      </Button>
    </section>
  );
}

function ReportActionBriefCard({
  brief,
  canSave,
  saving,
  onSave,
  onOpenRouteMap,
  onOpenCoursePackage,
  onGenerateResource,
}: {
  brief: GuideV2LearningReport["action_brief"] | null;
  canSave: boolean;
  saving: boolean;
  onSave: () => void;
  onOpenRouteMap: () => void;
  onOpenCoursePackage: () => void;
  onGenerateResource: (type: GuideV2ResourceType, taskId: string, prompt: string) => void;
}) {
  if (!brief) {
    return (
      <div className="mt-4 rounded-lg border border-teal-100 bg-teal-50 p-3">
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm font-semibold text-brand-teal">学习处方</p>
          <Badge tone="neutral">等待</Badge>
        </div>
        <p className="mt-3 text-sm leading-6 text-slate-600">完成更多任务后，系统会把下一步整理成一个明确动作。</p>
      </div>
    );
  }

  const primary = brief.primary_action ?? {};
  const secondary = brief.secondary_actions ?? [];
  const signals = brief.signals ?? [];

  return (
    <div className="mt-4 rounded-lg border border-teal-100 bg-teal-50 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-brand-teal">学习处方</p>
          <h3 className="mt-2 text-base font-semibold text-teal-950">{brief.title || "先完成下一步"}</h3>
        </div>
        <Badge tone="brand">先做</Badge>
      </div>
      <p className="mt-2 text-sm leading-6 text-teal-800">{brief.summary || primary.detail || "系统已经把下一步压缩成一个明确动作。"}</p>
      {signals.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {signals.slice(0, 4).map((item) => (
            <Badge key={`${item.label}-${item.value}`} tone={safeBadgeTone(item.tone)}>
              {item.label}：{item.value}
            </Badge>
          ))}
        </div>
      ) : null}
      <div className="mt-4">
        <ReportActionButton
          action={primary}
          primary
          canSave={canSave}
          saving={saving}
          onSave={onSave}
          onOpenRouteMap={onOpenRouteMap}
          onOpenCoursePackage={onOpenCoursePackage}
          onGenerateResource={onGenerateResource}
        />
      </div>
      {secondary.length ? (
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          {secondary.slice(0, 2).map((item) => (
            <div key={`${item.label}-${item.detail}`} className="rounded-lg border border-teal-100 bg-white/80 p-3">
              <p className="text-xs font-semibold text-ink">{item.label || "备选动作"}</p>
              <p className="mt-1 text-xs leading-5 text-slate-600">{item.detail || "作为下一步的备选安排。"}</p>
              <ReportActionButton
                action={item}
                className="mt-3"
                canSave={canSave}
                saving={saving}
                onSave={onSave}
                onOpenRouteMap={onOpenRouteMap}
                onOpenCoursePackage={onOpenCoursePackage}
                onGenerateResource={onGenerateResource}
              />
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function DemoReadinessCard({
  readiness,
}: {
  readiness: GuideV2LearningReport["demo_readiness"] | null;
}) {
  if (!readiness) {
    return null;
  }

  const score = Number(readiness.score ?? 0);
  const checks = readiness.checks ?? [];
  const nextStep = readiness.next_steps?.[0];

  return (
    <div className="mt-4 rounded-lg border border-line bg-white p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Target size={16} className="text-brand-blue" />
          <p className="text-sm font-semibold text-ink">演示就绪</p>
        </div>
        <Badge tone={effectStatusTone(score)}>{guideDisplayText(readiness.label, `${score} 分`)}</Badge>
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-600">
        {guideDisplayText(readiness.summary, "系统会检查画像、资源、练习、报告和可展示产物是否已经成链。")}
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        {checks.slice(0, 5).map((item) => (
          <Badge key={item.id || item.label} tone={demoReadinessTone(item.status)}>
            {guideDisplayText(item.label || item.id)}：{demoReadinessLabel(item.status)}
          </Badge>
        ))}
      </div>
      {nextStep ? (
        <p className="mt-3 rounded-lg border border-line bg-canvas p-2 text-xs leading-5 text-slate-600">
          下一步：{guideDisplayText(nextStep)}
        </p>
      ) : null}
    </div>
  );
}

function ReportActionButton({
  action,
  primary = false,
  className = "",
  canSave,
  saving,
  onSave,
  onOpenRouteMap,
  onOpenCoursePackage,
  onGenerateResource,
}: {
  action: NonNullable<GuideV2LearningReport["action_brief"]>["primary_action"];
  primary?: boolean;
  className?: string;
  canSave: boolean;
  saving: boolean;
  onSave: () => void;
  onOpenRouteMap: () => void;
  onOpenCoursePackage: () => void;
  onGenerateResource: (type: GuideV2ResourceType, taskId: string, prompt: string) => void;
}) {
  const kind = String(action?.kind || "");
  const resourceType = normalizeResourceType(action?.resource_type);
  const taskId = String(action?.target_task_id || "");
  const prompt = String(action?.prompt || action?.detail || "");
  const canGenerate = Boolean(resourceType && taskId);
  const opensCoursePackage = ["course_package", "project"].includes(kind);
  const rawLabel = action?.label || (opensCoursePackage ? "查看课程产出包" : canGenerate ? `生成${resourceLabel(resourceType)}` : "查看完整路线");
  const label = guideDisplayText(rawLabel);
  const tone = primary ? "primary" : "secondary";
  const sizeClass = primary ? "w-full justify-center" : "min-h-9 px-3 text-xs";

  if (canGenerate && resourceType) {
    return (
      <Button
        tone={tone}
        className={`${sizeClass} ${className}`}
        onClick={() => onGenerateResource(resourceType, taskId, prompt)}
      >
        {guideResourceIcon(resourceType, primary ? 16 : 14)}
        {label}
      </Button>
    );
  }

  if (opensCoursePackage) {
    return (
      <Button tone={tone} className={`${sizeClass} ${className}`} onClick={onOpenCoursePackage}>
        <GraduationCap size={primary ? 16 : 14} />
        {label}
      </Button>
    );
  }

  if (kind === "save_report") {
    return (
      <Button tone={tone} className={`${sizeClass} ${className}`} disabled={!canSave || saving} onClick={onSave}>
        {saving ? <Loader2 size={primary ? 16 : 14} className="animate-spin" /> : <BookOpen size={primary ? 16 : 14} />}
        {label}
      </Button>
    );
  }

  return (
    <Button tone={tone} className={`${sizeClass} ${className}`} onClick={onOpenRouteMap}>
      <Compass size={primary ? 16 : 14} />
      {label}
    </Button>
  );
}

function PrescriptionFeedbackNotice({
  feedback,
  onReviewReport,
  onOpenMemory,
}: {
  feedback: GuideV2LearningFeedback;
  onReviewReport: () => void;
  onOpenMemory: () => void;
}) {
  return (
    <motion.div
      className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 p-4"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18 }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={feedbackTone(feedback.tone)}>处方复测</Badge>
            {typeof feedback.score_percent === "number" ? (
              <Badge tone={effectStatusTone(feedback.score_percent)}>{Math.round(feedback.score_percent)} 分</Badge>
            ) : null}
          </div>
          <p className="mt-3 text-sm font-semibold text-ink">{feedback.title || "处方练习已回写"}</p>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-600">
            {feedback.summary || "系统已经根据这次处方练习更新学习报告和画像证据。"}
          </p>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button tone="primary" className="min-h-9 px-3 text-xs" onClick={onReviewReport}>
          <BarChart3 size={14} />
          回看报告
        </Button>
        <Button tone="secondary" className="min-h-9 px-3 text-xs" onClick={onOpenMemory}>
          <Brain size={14} />
          查看画像变化
        </Button>
      </div>
    </motion.div>
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
  const demoBlueprint = coursePackage?.demo_blueprint ?? null;
  const fallbackKit = coursePackage?.demo_fallback_kit ?? null;
  const seedPack = coursePackage?.demo_seed_pack ?? null;
  const learningStyle = coursePackage?.learning_style ?? demoBlueprint?.learning_style ?? null;
  return (
    <section className="rounded-lg border border-line bg-white p-4" data-testid="guide-course-package-panel">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <GraduationCap size={18} className="text-brand-teal" />
          <div>
            <h2 className="text-base font-semibold text-ink">课程产出包</h2>
            {coursePackage?.title ? (
              <p className="mt-0.5 text-xs text-slate-500">{guideDisplayText(coursePackage.title)}</p>
            ) : null}
          </div>
        </div>
        {loading ? <Loader2 size={16} className="animate-spin text-brand-teal" /> : <Badge tone="brand">{project.estimated_minutes ?? "-"} 分钟</Badge>}
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-600">
        {guideDisplayText(coursePackage?.summary, "系统会把学习路径整理成最终项目、评分标准、复习计划和作品集索引。")}
      </p>
      <div className="mt-4 rounded-lg border border-line bg-canvas p-3">
        <p className="text-sm font-semibold text-ink">{guideDisplayText(project.title, "学习成果项目")}</p>
        <p className="mt-2 line-clamp-4 text-xs leading-5 text-slate-600">{guideDisplayText(project.scenario, "完成更多学习任务后会生成更贴合你的项目说明。")}</p>
      </div>
      <CourseLearningStyleCard learningStyle={learningStyle} />
      <CourseDemoRecordingChecklistCard blueprint={demoBlueprint} kit={fallbackKit} seed={seedPack} learningStyle={learningStyle} />
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
              <Badge key={tag} tone="brand">{guideDisplayText(tag)}</Badge>
            ))}
          </div>
        ) : null}
        {recentEvents.length ? (
          <p className="mt-3 line-clamp-2 text-xs leading-5 text-slate-500">
            最近：{recentEvents.slice(0, 2).map((event) => guideDisplayText(event.title || event.description || event.type)).join(" / ")}
          </p>
        ) : null}
        {effectAssessment ? (
          <div className="mt-3 rounded-lg border border-line bg-canvas p-2">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-semibold text-ink">学习效果</p>
              <Badge tone={effectStatusTone(effectAssessment.score)}>{guideDisplayText(effectAssessment.label, `${Number(effectAssessment.score ?? 0)} 分`)}</Badge>
            </div>
            <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-600">{guideDisplayText(effectAssessment.summary, "已生成学习效果评估。")}</p>
          </div>
        ) : null}
      </div>
      <div className="mt-4 space-y-2">
        {rubric.slice(0, 3).map((item) => (
          <div key={item.criterion} className="rounded-lg border border-line bg-white p-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-semibold text-ink">{guideDisplayText(item.criterion)}</p>
              <Badge tone="neutral">{item.weight ?? 0}%</Badge>
            </div>
            <p className="mt-1 text-xs leading-5 text-slate-500">{guideDisplayText(item.baseline || item.excellent)}</p>
          </div>
        ))}
      </div>
      <EvalList
        title="复习重点"
        items={review.slice(0, 3).map((item) => `${guideDisplayText(item.title, "知识点")}：${guideDisplayText(item.action)}`)}
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

function CourseLearningStyleCard({ learningStyle }: { learningStyle: GuideV2CoursePackage["learning_style"] | null }) {
  if (!learningStyle?.label && !learningStyle?.summary) return null;
  const signals = learningStyle.signals ?? [];
  return (
    <div className="mt-4 rounded-lg border border-teal-100 bg-teal-50 p-3" data-testid="guide-course-learning-style">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="brand">画像驱动产出</Badge>
        {learningStyle.label ? <Badge tone="neutral">{learningStyle.label}</Badge> : null}
      </div>
      <p className="mt-2 text-sm leading-6 text-teal-950">
        {learningStyle.summary || "课程产出包会把画像、资源、练习和报告串成可展示的学习闭环。"}
      </p>
      {learningStyle.trend ? <p className="mt-1 text-xs leading-5 text-teal-800">{learningStyle.trend}</p> : null}
      {signals.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {signals.slice(0, 3).map((signal) => (
            <span key={`${signal.label}-${signal.value}`} className="rounded-md border border-teal-100 bg-white px-2 py-1 text-xs text-slate-600">
              {signal.label || "信号"}：{signal.value || "-"}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function CourseDemoRecordingChecklistCard({
  blueprint,
  kit,
  seed,
  learningStyle,
}: {
  blueprint: GuideV2CoursePackage["demo_blueprint"] | null;
  kit: GuideV2CoursePackage["demo_fallback_kit"] | null;
  seed: GuideV2CoursePackage["demo_seed_pack"] | null;
  learningStyle: GuideV2CoursePackage["learning_style"] | null;
}) {
  const storyline = blueprint?.storyline ?? [];
  const taskChain = seed?.task_chain ?? [];
  const steps = storyline.length
    ? storyline.slice(0, 3).map((step, index) => ({
        key: `${step.minute || index}-${step.title || index}`,
        label: step.minute || `片段 ${index + 1}`,
        title: step.title || "演示片段",
        detail: step.show || step.talking_point || step.requirement || "",
      }))
    : taskChain.slice(0, 3).map((task, index) => ({
        key: `${task.task_id || index}-${task.stage || index}`,
        label: task.stage || `步骤 ${index + 1}`,
        title: task.title || "演示任务",
        detail: task.show || task.sample_reflection || task.prompt || "",
      }));
  const persona = kit?.persona ?? seed?.persona ?? {};
  const assets = kit?.assets ?? [];
  const fallback = kit?.checklist?.[0] || blueprint?.fallbacks?.[0] || seed?.rehearsal_notes?.[0] || "";
  const title = guideDisplayText(blueprint?.title || seed?.title, "录屏检查");
  const summary = guideDisplayText(blueprint?.summary || kit?.summary || seed?.scenario, "打开画像、路线、资源、反馈和产出包，讲一条完整学习闭环。");
  const hasContent = Boolean(blueprint || kit || seed || steps.length || assets.length || fallback);

  if (!hasContent) {
    return null;
  }

  return (
    <div className="mt-4 rounded-lg border border-line bg-white p-3" data-testid="guide-demo-recording-checklist">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Video size={16} className="text-brand-teal" />
          <p className="text-sm font-semibold text-ink">录屏检查</p>
        </div>
        <Badge tone={effectStatusTone(Number(blueprint?.readiness_score ?? 0))}>
          {guideDisplayText(blueprint?.readiness_label, `${blueprint?.duration_minutes ?? 7} 分钟`)}
        </Badge>
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-600">{summary}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Badge tone="brand">{title}</Badge>
        {learningStyle?.label ? <Badge tone="success">{learningStyle.label}</Badge> : null}
        {persona.name ? <Badge tone="neutral">{guideDisplayText(persona.name)}</Badge> : null}
        {(persona.weak_points ?? []).slice(0, 1).map((item) => (
          <Badge key={item} tone="warning">{guideDisplayText(item)}</Badge>
        ))}
      </div>
      {steps.length ? (
        <div className="mt-3 grid gap-2 md:grid-cols-3">
          {steps.map((step) => (
            <div key={step.key} className="rounded-lg border border-line bg-canvas p-2">
              <div className="flex items-center gap-2">
                <Badge tone="brand">{guideDisplayText(step.label)}</Badge>
                <p className="min-w-0 truncate text-xs font-semibold text-ink">{guideDisplayText(step.title)}</p>
              </div>
              <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-600">{guideDisplayText(step.detail, "按当前页面顺序展示即可。")}</p>
            </div>
          ))}
        </div>
      ) : null}
      {assets.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {assets.slice(0, 2).map((asset) => (
            <Badge key={`${asset.type}-${asset.title}`} tone={fallbackAssetTone(asset.status)}>
              {fallbackAssetLabel(asset.status)}：{guideDisplayText(asset.title || asset.type, "演示素材")}
            </Badge>
          ))}
        </div>
      ) : null}
      {fallback ? (
        <p className="mt-3 rounded-lg border border-line bg-canvas p-2 text-xs leading-5 text-slate-600">
          兜底：{guideDisplayText(fallback)}
        </p>
      ) : null}
    </div>
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
  onCompleteTask,
  finalLabel = "去提交",
  finalHint = "写一句反思，系统再给反馈。",
}: {
  artifacts: GuideV2Artifact[];
  saveNotebookId: string;
  saving: boolean;
  quizSubmitting: boolean;
  onSave: (artifact: GuideV2Artifact) => void;
  onSubmitQuiz: (artifact: GuideV2Artifact, answers: QuizResultItem[]) => void;
  onCompleteTask: () => void;
  finalLabel?: string;
  finalHint?: string;
}) {
  const [activeIndex, setActiveIndex] = useState(0);
  const orderedArtifacts = useMemo(() => sortGuideArtifactsForLearning(artifacts), [artifacts]);
  const activeArtifact = orderedArtifacts[Math.min(activeIndex, Math.max(orderedArtifacts.length - 1, 0))];

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setActiveIndex((index) => Math.min(index, Math.max(orderedArtifacts.length - 1, 0)));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [orderedArtifacts.length]);

  if (!activeArtifact) return null;

  return (
    <div className="rounded-lg border border-line bg-canvas p-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-ink">按这个顺序学</p>
          <p className="mt-1 text-xs text-slate-500">一次只看一个结果，最后回到提交页。</p>
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
            {activeIndex + 1}/{orderedArtifacts.length}
          </Badge>
          <Button
            tone="secondary"
            className="min-h-8 px-2 text-xs"
            disabled={activeIndex >= orderedArtifacts.length - 1}
            onClick={() => setActiveIndex((index) => Math.min(orderedArtifacts.length - 1, index + 1))}
          >
            下一个
          </Button>
        </div>
      </div>
      <ResourceLearningSteps
        artifacts={orderedArtifacts}
        activeIndex={activeIndex}
        onSelect={setActiveIndex}
        onCompleteTask={onCompleteTask}
        finalLabel={finalLabel}
        finalHint={finalHint}
      />
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

function ResourceLearningSteps({
  artifacts,
  activeIndex,
  onSelect,
  onCompleteTask,
  finalLabel,
  finalHint,
}: {
  artifacts: GuideV2Artifact[];
  activeIndex: number;
  onSelect: (index: number) => void;
  onCompleteTask: () => void;
  finalLabel: string;
  finalHint: string;
}) {
  const steps = artifacts.map((artifact, index) => ({
    artifact,
    label: resourceStepLabel(String(artifact.type), index, artifacts),
    hint: resourceStepHint(String(artifact.type)),
  }));

  return (
    <div className="mt-3 rounded-lg border border-line bg-white p-3">
      <div className="grid gap-2 md:grid-cols-4">
        {steps.map((step, index) => (
          <button
            key={step.artifact.id}
            type="button"
            onClick={() => onSelect(index)}
            className={`rounded-lg border p-3 text-left transition ${
              index === activeIndex ? "border-teal-200 bg-teal-50" : "border-line bg-white hover:border-teal-200 hover:bg-canvas"
            }`}
          >
            <Badge tone={index === activeIndex ? "brand" : "neutral"}>第 {index + 1} 步</Badge>
            <p className="mt-2 text-sm font-semibold text-ink">{step.label}</p>
            <p className="mt-1 text-xs leading-5 text-slate-500">{step.hint}</p>
          </button>
        ))}
        <button
          type="button"
          onClick={onCompleteTask}
          className="rounded-lg border border-line bg-canvas p-3 text-left transition hover:border-teal-200 hover:bg-teal-50"
        >
          <Badge tone="success">最后</Badge>
          <p className="mt-2 text-sm font-semibold text-ink">{finalLabel}</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">{finalHint}</p>
        </button>
      </div>
    </div>
  );
}

function sortGuideArtifactsForLearning(artifacts: GuideV2Artifact[]) {
  const order: Record<string, number> = {
    visual: 0,
    external_video: 1,
    video: 2,
    quiz: 3,
  };
  return [...artifacts].sort((left, right) => {
    const leftOrder = order[String(left.type)] ?? 9;
    const rightOrder = order[String(right.type)] ?? 9;
    if (leftOrder !== rightOrder) return leftOrder - rightOrder;
    return Number(left.created_at ?? 0) - Number(right.created_at ?? 0);
  });
}

function resourceStepLabel(type: string, index: number, artifacts: GuideV2Artifact[]) {
  const hasConceptResourceBefore = artifacts
    .slice(0, index)
    .some((item) => item.type === "visual" || item.type === "video" || item.type === "external_video");
  if (type === "visual") return index === 0 ? "先看图解" : "再看图解";
  if (type === "external_video") return index === 0 ? "先看精选视频" : "再看精选视频";
  if (type === "video") return index === 0 ? "先看短视频" : "再看短视频";
  if (type === "quiz") return hasConceptResourceBefore ? "再做练习" : "先做练习";
  return resourceLabel(type);
}

function resourceStepHint(type: string) {
  if (type === "visual") return "先建立直觉和结构。";
  if (type === "external_video") return "用外部讲解补充视角。";
  if (type === "video") return "跟着步骤过一遍。";
  if (type === "quiz") return "用题目确认是否掌握。";
  return "看完后继续下一步。";
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
  const hasExternalVideo = Boolean(artifact.type === "external_video" && Array.isArray(result?.videos));
  const questions = extractGuideQuizItems(result);
  const showResponse = Boolean(response && !(artifact.type === "quiz" && questions.length) && artifact.type !== "external_video");
  const personalization = extractArtifactPersonalization(artifact);
  const specialist = agentRoleForArtifact(artifact);

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
          {artifact.capability ? <Badge tone="neutral">{specialist.label}</Badge> : null}
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
      <ArtifactAgentChain artifact={artifact} personalization={personalization} />
      {personalization ? <ArtifactPersonalizationCard personalization={personalization} /> : null}
      {showResponse ? <MarkdownRenderer className="markdown-body mt-3 text-sm text-slate-600">{response}</MarkdownRenderer> : null}

      {hasVisual ? <div className="mt-4"><VisualizationViewer result={result as unknown as VisualizeResult} /></div> : null}
      {hasVideo ? <div className="mt-4"><MathAnimatorViewer result={result as unknown as MathAnimatorResult} /></div> : null}
      {hasExternalVideo ? <div className="mt-4"><ExternalVideoViewer result={result as unknown as ExternalVideoResult} /></div> : null}
      {artifact.type === "quiz" && questions.length ? (
        <QuestionPreview items={questions} submitting={quizSubmitting} onSubmit={onSubmitQuiz} />
      ) : null}
      {artifact.type === "quiz" && !questions.length ? <QuizFallback result={result} response={response} /> : null}
    </motion.article>
  );
}

function ArtifactAgentChain({
  artifact,
  personalization,
}: {
  artifact: GuideV2Artifact;
  personalization: ReturnType<typeof extractArtifactPersonalization>;
}) {
  const specialist = agentRoleForArtifact(artifact);
  const evidenceText = personalization?.signals?.[0]
    ? `${personalization.signals[0].label}：${personalization.signals[0].value}`
    : "当前任务与学习画像";
  const steps = [
    {
      label: "画像智能体",
      detail: `先判断入口：${evidenceText}`,
      tone: "brand" as const,
    },
    {
      label: specialist.label,
      detail: specialist.detail,
      tone: "neutral" as const,
    },
    {
      label: "评估智能体",
      detail: artifact.type === "quiz" ? "提交后批改并更新下一步" : "学完后通过提交页回写画像",
      tone: "success" as const,
    },
  ];
  const summary =
    artifact.type === "quiz"
      ? "画像定向出题，提交后直接进入反馈和下一步调整。"
      : `画像先定向，再由${specialist.label}生成当前材料，学完后回到提交页形成闭环。`;

  return (
    <div className="mt-3 rounded-lg border border-line bg-white px-3 py-3" data-testid="guide-artifact-agent-route">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Badge tone="brand">智能体接力</Badge>
          <span className="text-xs font-medium text-ink">{summary}</span>
        </div>
      </div>
      <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
        {steps.map((step, index) => (
          <Fragment key={step.label}>
            <motion.div
              className="min-w-[8rem] shrink-0 rounded-md border border-line bg-canvas px-3 py-2"
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.16, delay: index * 0.04 }}
            >
              <div className="flex items-center gap-2">
                <span className={`h-1.5 w-1.5 rounded-full ${agentRouteDotTone(step.tone)}`} />
                <span className="text-xs font-semibold text-ink">{shortGuideAgentName(step.label)}</span>
              </div>
              <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{step.detail}</p>
            </motion.div>
            {index < steps.length - 1 ? <span className="mt-5 shrink-0 text-slate-300">→</span> : null}
          </Fragment>
        ))}
      </div>
    </div>
  );
}

function shortGuideAgentName(label: string) {
  return label.replace(/智能体$/, "");
}

function agentRouteDotTone(tone: "brand" | "neutral" | "success") {
  if (tone === "brand") return "bg-brand-teal";
  if (tone === "success") return "bg-emerald-500";
  return "bg-brand-blue";
}

function ArtifactPersonalizationCard({
  personalization,
}: {
  personalization: {
    headline: string;
    reasons: string[];
    signals: Array<{ label: string; value: string }>;
    progressStyle?: {
      label: string;
      explanation: string;
      recommendation: string;
    } | null;
  };
}) {
  return (
    <div className="mt-3 rounded-lg border border-teal-100 bg-teal-50 px-3 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="brand">生成依据</Badge>
        {personalization.signals.slice(0, 4).map((item) => (
          <Badge key={`${item.label}-${item.value}`} tone="neutral">
            {item.label}：{item.value}
          </Badge>
        ))}
      </div>
      <p className="mt-2 text-sm leading-6 text-teal-900">{personalization.headline}</p>
      {personalization.progressStyle ? (
        <div className="mt-2 rounded-lg border border-teal-200 bg-white/80 px-3 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">按你的学习方式生成</Badge>
            <Badge tone="neutral">{personalization.progressStyle.label}</Badge>
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-700">{personalization.progressStyle.explanation}</p>
          <p className="mt-2 text-xs leading-5 text-slate-500">{personalization.progressStyle.recommendation}</p>
        </div>
      ) : null}
      {personalization.reasons.length ? (
        <div className="mt-2 grid gap-2">
          {personalization.reasons.slice(0, 3).map((reason) => (
            <p key={reason} className="rounded-lg border border-white/70 bg-white/80 px-3 py-2 text-xs leading-5 text-slate-700">
              {reason}
            </p>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function agentRoleForArtifact(artifact: GuideV2Artifact) {
  const capability = String(artifact.capability || "");
  const type = String(artifact.type || "");
  if (type === "video" || capability === "math_animator") {
    return {
      label: "动画智能体",
      detail: "把关键步骤拆成可播放的短视频讲解。",
    };
  }
  if (type === "external_video" || capability === "external_video_search") {
    return {
      label: "视频检索智能体",
      detail: "从公开视频中筛选适合当前画像和任务的学习材料。",
    };
  }
  if (type === "quiz" || capability === "deep_question") {
    return {
      label: "出题智能体",
      detail: "生成可提交、可反馈的交互练习。",
    };
  }
  if (type === "visual" || capability === "visualize") {
    return {
      label: "图解智能体",
      detail: "把概念关系整理成图解或结构化可视化。",
    };
  }
  if (type === "research" || capability === "deep_research") {
    return {
      label: "资料整理智能体",
      detail: "补充依据并整理成当前任务可用的材料。",
    };
  }
  return {
    label: "资源智能体",
    detail: "按当前任务生成一份可继续学习的材料。",
  };
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
  const checkedCount = records.filter((_item, index) => checked[index]).length;
  const allChecked = records.length > 0 && checkedCount === records.length;

  const buildResults = (): QuizResultItem[] =>
    records.map(({ record, qa, options }, index) => {
      const answer = answers[index] || "";
      const correctAnswer = readString(qa, "correct_answer") || readString(qa, "answer");
      const kind = normalizeGuideQuestionType(readString(qa, "question_type"), options);
      const concepts = extractGuideQuestionConcepts(qa, record);
      return {
        question_id: readString(qa, "question_id") || `guide-q-${index + 1}`,
        question: readString(qa, "question") || readString(qa, "prompt") || readString(qa, "title") || "已生成练习题",
        question_type: kind,
        options: options ? Object.fromEntries(Object.entries(options).map(([key, value]) => [key, String(value)])) : {},
        concepts,
        knowledge_points: concepts,
        user_answer: answer,
        correct_answer: correctAnswer,
        explanation: readString(qa, "explanation"),
        difficulty: readString(qa, "difficulty"),
        is_correct: isGuideQuizCorrect(answer, correctAnswer, options),
      };
    });
  const currentResults = buildResults();
  const correctCount = currentResults.filter((item) => item.is_correct).length;
  const scoreRatio = records.length ? correctCount / records.length : 0;

  const submitAll = () => {
    if (!allChecked || submitting) return;
    setSubmitted(true);
    setRevealed(Object.fromEntries(records.map((_item, index) => [index, true])));
    setChecked(Object.fromEntries(records.map((_item, index) => [index, true])));
    onSubmit(buildResults());
  };

  return (
    <div className="mt-4 space-y-3" data-testid="guide-quiz-preview">
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
                    data-testid={`guide-quiz-option-${index}-${key}`}
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
                    data-testid={`guide-quiz-true-false-${index}-${value}`}
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
                data-testid={`guide-quiz-input-${index}`}
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
                  data-testid={`guide-quiz-submit-${index}`}
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
      {allChecked ? (
        <div
          className={`rounded-lg border p-3 text-sm leading-6 ${
            scoreRatio >= 0.8
              ? "border-emerald-200 bg-emerald-50 text-emerald-800"
              : scoreRatio >= 0.5
                ? "border-amber-200 bg-amber-50 text-amber-800"
                : "border-red-200 bg-red-50 text-red-800"
          }`}
          data-testid="guide-quiz-score-preview"
        >
          <p className="font-semibold text-ink">
            本组练习 {correctCount}/{records.length} 题正确
          </p>
          <p className="mt-1 text-xs">
            {scoreRatio >= 0.8
              ? "整体不错，提交后系统会把掌握证据写回路线。"
              : scoreRatio >= 0.5
                ? "有一部分已经掌握，提交后系统会根据错题安排补强。"
                : "先别急着继续推进，提交后系统会优先帮你补错因。"}
          </p>
        </div>
      ) : null}
      <Button tone="primary" className="w-full" data-testid="guide-quiz-submit-all" disabled={!allChecked || submitting || submitted} onClick={submitAll}>
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

function taskTypeLabel(type: string) {
  const labels: Record<string, string> = {
    explain: "讲解",
    visualize: "图解",
    video: "视频",
    external_video: "精选视频",
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
    external_video: "精选视频",
    quiz: "练习",
  };
  return labels[type] || type || "资源";
}

type GuideActionResourceType = "visual" | "quiz" | "video" | "external_video";

const guideActionResourceTypes: GuideActionResourceType[] = ["visual", "external_video", "quiz", "video"];

function normalizeGuideActionResourceType(type: GuideV2ResourceType): GuideActionResourceType {
  if (type === "quiz" || type === "video" || type === "external_video") return type;
  return "visual";
}

function buildGuideResourceActions(
  recommended: GuideV2ResourceType,
  copy: Record<GuideActionResourceType, string>,
) {
  const primary = normalizeGuideActionResourceType(recommended);
  return [primary, ...guideActionResourceTypes.filter((type) => type !== primary)].map((type) => ({
    type,
    label: copy[type],
  }));
}

function guideResourceIcon(type: GuideActionResourceType, size = 16) {
  if (type === "quiz") return <ListChecks size={size} />;
  if (type === "video") return <Video size={size} />;
  if (type === "external_video") return <Video size={size} />;
  return <Map size={size} />;
}

function guideResourceDescription(type: GuideActionResourceType) {
  const descriptions: Record<GuideActionResourceType, string> = {
    visual: "把概念关系画出来，适合先建立直觉。",
    quiz: "用选择、判断、填空和简答验证理解，做完可获得反馈。",
    video: "生成一段短讲解，适合需要步骤演示时使用。",
    external_video: "从公开网络里找少量讲解视频，看完后回到导学提交反思。",
  };
  return descriptions[type];
}

function buildGuideResourceButtonCopy(recommended: GuideV2ResourceType, trendLabel: string) {
  const copy = {
    visual: "看图解",
    quiz: "做练习",
    video: "看短视频",
    external_video: "找精选视频",
  };

  if (trendLabel.includes("修正路径")) {
    copy.visual = recommended === "visual" ? "先看补救图解" : "看补救图解";
    copy.quiz = recommended === "quiz" ? "先做复测题" : "做复测题";
    copy.video = recommended === "video" ? "看纠错讲解" : "看纠错讲解";
    copy.external_video = recommended === "external_video" ? "先找讲解视频" : "找讲解视频";
    return copy;
  }

  if (trendLabel.includes("变稳")) {
    copy.visual = recommended === "visual" ? "先看关键图解" : "看关键图解";
    copy.quiz = recommended === "quiz" ? "直接做验证题" : "做验证题";
    copy.video = recommended === "video" ? "看步骤串讲" : "看步骤串讲";
    copy.external_video = recommended === "external_video" ? "找参考视频" : "找参考视频";
    return copy;
  }

  if (trendLabel.includes("提速")) {
    copy.visual = recommended === "visual" ? "快速看图解" : "看图解";
    copy.quiz = recommended === "quiz" ? "直接做这组题" : "做这组题";
    copy.video = recommended === "video" ? "快速看短视频" : "看短视频";
    copy.external_video = recommended === "external_video" ? "快速找视频" : "找精选视频";
    return copy;
  }

  if (trendLabel.includes("聚焦补强")) {
    copy.visual = recommended === "visual" ? "先看这张图解" : "看这张图解";
    copy.quiz = recommended === "quiz" ? "做这组补强题" : "做补强题";
    copy.video = recommended === "video" ? "看补强短视频" : "看补强短视频";
    copy.external_video = recommended === "external_video" ? "先找公开视频" : "找公开视频";
    return copy;
  }

  if (recommended === "visual") copy.visual = "先看这张图解";
  if (recommended === "quiz") copy.quiz = "先做这组题";
  if (recommended === "video") copy.video = "先看这段短视频";
  if (recommended === "external_video") copy.external_video = "先找精选视频";
  return copy;
}

function isResearchResourceType(type: string) {
  const value = String(type || "").toLowerCase();
  return value === "research" || value === "material" || value === "materials" || value.includes("资料");
}

function normalizeResourceType(type: unknown): GuideActionResourceType {
  if (type === "visual" || type === "video" || type === "quiz" || type === "external_video") {
    return type;
  }
  return "visual";
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

function safeBadgeTone(tone?: string): "neutral" | "success" | "warning" | "danger" | "brand" {
  if (tone === "success" || tone === "warning" || tone === "danger" || tone === "brand") return tone;
  return "neutral";
}

function demoReadinessTone(status?: string): "neutral" | "success" | "warning" | "danger" | "brand" {
  if (status === "ready") return "success";
  if (status === "partial") return "brand";
  if (status === "missing") return "warning";
  return "neutral";
}

function demoReadinessLabel(status?: string): string {
  if (status === "ready") return "已具备";
  if (status === "partial") return "待加强";
  if (status === "missing") return "待补齐";
  return "检查中";
}

function fallbackAssetTone(status?: string): "neutral" | "success" | "warning" | "danger" | "brand" {
  if (status === "ready") return "success";
  if (status === "seed") return "brand";
  return "neutral";
}

function fallbackAssetLabel(status?: string): string {
  if (status === "ready") return "可直接展示";
  if (status === "seed") return "可现场生成";
  return "备用";
}

const GUIDE_DISPLAY_COPY: Record<string, string> = {
  "Ready for recording": "可录屏",
  Ready: "可录屏",
  "Stable demo course package": "稳定演示产出包",
  "Stable demo course package for a 7-minute recording.": "用于 7 分钟录屏的稳定课程产出包。",
  "7-minute demo route": "7 分钟演示路线",
  "Show profile, route, resource, feedback, and package.": "展示画像、路线、资源、反馈和产出包。",
  "Open guide route before recording.": "录屏前先打开导学路线。",
  "Profile, resource, feedback, report and package can now be shown as one chain.": "画像、资源、反馈、报告和产出包已经能串成一条闭环。",
  "Open the route map, then open the course package.": "先看路线，再看课程产出包。",
  "Open the route and course package": "查看路线和产出包",
  "Use the route map and package to show the closed loop.": "用路线图和产出包展示学习闭环。",
  "Machine Learning Foundations": "机器学习基础",
  "Explain gradient descent": "讲清楚梯度下降",
  "Build one visual resource and one feedback loop.": "生成一份图解资源，并完成一次反馈闭环。",
  "Create route": "创建路线",
  "Generate visual": "生成图解",
  "Submit feedback": "提交反馈",
  Route: "路线",
  Visual: "图解",
  Feedback: "反馈",
  Profile: "画像",
  profile: "画像",
  feedback: "反馈",
  "Closed loop": "闭环",
  "Shows profile to feedback.": "能展示画像到反馈的闭环。",
  Optimization: "优化方法",
  "Do one short retest.": "做一次短复测。",
  "Retest gradient descent.": "复测梯度下降。",
  "Recording fallback kit": "录屏兜底包",
  "Use stable artifacts if live generation is slow.": "现场生成变慢时，直接展示稳定产物。",
  "Use saved visuals if generation is slow.": "生成变慢时，展示已保存图解。",
  "Gradient descent visual": "梯度下降图解",
  "Use saved visual.": "使用已保存图解。",
  "Profile evidence": "画像证据",
  "Profile is present.": "已有画像证据。",
  "Open learner profile.": "打开学习画像。",
  Resource: "资源",
  "Visual resource was requested.": "已请求图解资源。",
  "Feedback loop is visible.": "反馈闭环可见。",
  "Demo learning report": "演示学习报告",
  "The demo learner has a visible feedback loop.": "演示学习者已经形成可见反馈闭环。",
  "Feedback recorded": "反馈已记录",
  "Profile updated.": "画像已更新。",
  Demo: "演示",
  ready: "已就绪",
  "Open route": "查看路线",
  "Show the adjusted route.": "展示调整后的路线。",
  "Stable ML foundations demo": "机器学习基础稳定演示",
  "Demo learner": "演示学习者",
  "Concept boundaries": "概念边界",
};

function guideDisplayText(value: unknown, fallback = ""): string {
  const text = String(value ?? "").trim();
  if (!text) return fallback;
  return GUIDE_DISPLAY_COPY[text] || text;
}

function feedbackRouteBadge(
  feedback?: Pick<GuideV2LearningFeedback, "score_percent" | "adjustment_types" | "actions"> | null,
): { label: string; tone: "success" | "brand" | "warning" | "neutral" } | null {
  if (!feedback) return null;
  const adjustments = feedback.adjustment_types ?? [];
  const actions = feedback.actions ?? [];
  const actionText = actions.join(" ");
  if (adjustments.some((item) => item.includes("remediation")) || /补救/.test(actionText)) {
    return { label: "先补救", tone: "warning" };
  }
  if (adjustments.some((item) => item.includes("retest")) || /复测/.test(actionText)) {
    return { label: "去复测", tone: "brand" };
  }
  if (adjustments.some((item) => item.includes("transfer")) || /迁移|巩固/.test(actionText)) {
    return { label: "做巩固", tone: "brand" };
  }
  const score = typeof feedback.score_percent === "number" ? feedback.score_percent : null;
  if (score !== null) {
    if (score < 60) return { label: "先补救", tone: "warning" };
    if (score < 75) return { label: "稳一下", tone: "brand" };
    return { label: "继续推进", tone: "success" };
  }
  return null;
}

function summarizeFeedbackRouting(
  items: Array<Pick<GuideV2LearningFeedback, "score_percent" | "adjustment_types" | "actions"> | null | undefined>,
): Array<{ label: string; count: number; tone: "success" | "brand" | "warning" | "neutral" }> {
  const counts: Record<string, { label: string; count: number; tone: "success" | "brand" | "warning" | "neutral" }> = {};
  items.forEach((item) => {
    const badge = feedbackRouteBadge(item ?? null);
    if (!badge) return;
    const current = counts[badge.label];
    if (current) {
      current.count += 1;
      return;
    }
    counts[badge.label] = { ...badge, count: 1 };
  });
  return Object.values(counts).sort((left, right) => right.count - left.count);
}

function buildNextActionSteps(
  items: string[],
  routing: Array<{ label: string; count: number; tone: "success" | "brand" | "warning" | "neutral" }>,
  weakPoints: string[],
) {
  const normalized = items.map((item) => item.trim()).filter(Boolean);
  const steps = normalized.slice(0, 3).map((item) => {
    if (/复测|再测|验证/.test(item)) {
      return {
        title: weakPoints.length ? `先复测「${weakPoints[0]}」` : "先做一轮复测",
        detail: item,
      };
    }
    if (/补|错因|薄弱|基础/.test(item)) {
      return {
        title: weakPoints.length ? `先补「${weakPoints[0]}」` : "先补当前短板",
        detail: item,
      };
    }
    if (/图解|视频|讲解/.test(item)) {
      return {
        title: "先看一份讲解资源",
        detail: item,
      };
    }
    if (/练习|题/.test(item)) {
      return {
        title: "先做一组短练习",
        detail: item,
      };
    }
    return {
      title: item.length > 16 ? `${item.slice(0, 16)}...` : item,
      detail: item,
    };
  });

  if (steps.length) return steps;

  const dominant = routing[0]?.label || "";
  if (dominant === "先补救") {
    return [
      { title: weakPoints.length ? `先补「${weakPoints[0]}」` : "先补当前错因", detail: "这一轮更适合先把错因补清楚，再继续推进新的内容。" },
      { title: "再做一轮复测", detail: "补完后立刻验证，确认这次不是“看懂了”，而是真的改掉了。" },
    ];
  }
  if (dominant === "去复测") {
    return [
      { title: "先做一轮复测", detail: "这轮更值得确认掌握是否稳定，而不是马上增加新的学习负荷。" },
      { title: "再继续推进", detail: "如果复测稳定，再进入下一组任务或迁移应用会更顺。" },
    ];
  }
  if (dominant === "继续推进") {
    return [
      { title: "直接进入下一步", detail: "这轮整体推进比较顺，下一轮可以少一点铺垫，多一点任务验证。" },
      { title: "保留一次短复盘", detail: "继续推进的同时，仍建议在关键节点留一轮简短复盘来稳住掌握。" },
    ];
  }
  return [];
}

function planStatusLabel(status: string) {
  const labels: Record<string, string> = {
    active: "进行中",
    in_progress: "进行中",
    pending: "待开始",
    completed: "已完成",
    skipped: "已跳过",
    met: "已达成",
    needs_review: "需复盘",
  };
  return labels[status] || status || "待开始";
}

function planStatusTone(status: string): "neutral" | "success" | "warning" | "danger" | "brand" {
  if (status === "completed" || status === "met") return "success";
  if (status === "active" || status === "in_progress") return "brand";
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

function extractGuideQuestionConcepts(...sources: Array<Record<string, unknown>>) {
  const keys = [
    "concepts",
    "concept",
    "tested_concepts",
    "tested_concept",
    "knowledge_points",
    "knowledge_point",
    "learning_points",
    "learning_point",
    "categories",
    "category",
    "tags",
  ];
  const labels: string[] = [];
  for (const source of sources) {
    for (const key of keys) {
      for (const label of extractConceptLabels(source[key])) {
        if (label && !labels.includes(label)) labels.push(label);
      }
    }
    const metadata = asRecord(source.metadata);
    if (metadata) {
      for (const key of keys) {
        for (const label of extractConceptLabels(metadata[key])) {
          if (label && !labels.includes(label)) labels.push(label);
        }
      }
    }
  }
  return labels.slice(0, 8);
}

function extractConceptLabels(value: unknown): string[] {
  if (!value) return [];
  if (typeof value === "string") return extractStringArray(value);
  if (Array.isArray(value)) return value.flatMap(extractConceptLabels).filter(Boolean);
  const record = asRecord(value);
  if (record) {
    for (const key of ["label", "name", "title", "value", "concept", "concept_id", "id"]) {
      const text = readString(record, key).trim();
      if (text) return [text];
    }
    return [];
  }
  return [String(value).trim()].filter(Boolean);
}

function latestLearningFeedbackFromSession(session: GuideV2Session | null, currentTaskId?: string): GuideV2LearningFeedback | null {
  if (!session || !currentTaskId) return null;
  const candidates = (session.evidence ?? [])
    .map((item) => {
      const evidence = asRecord(item);
      const metadata = asRecord(evidence?.metadata);
      const feedback = asRecord(metadata?.learning_feedback);
      if (!feedback) return null;
      const nextTaskId = readString(feedback, "next_task_id");
      const feedbackTaskId = readString(feedback, "task_id");
      const relevant = nextTaskId === currentTaskId || feedbackTaskId === currentTaskId;
      if (!relevant) return null;
      return {
        createdAt: Number(evidence?.created_at ?? 0),
        feedback: feedback as GuideV2LearningFeedback,
      };
    })
    .filter((item): item is { createdAt: number; feedback: GuideV2LearningFeedback } => Boolean(item))
    .sort((a, b) => b.createdAt - a.createdAt);
  return candidates[0]?.feedback ?? null;
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

function buildAdaptiveGuideStrategy(
  profile: LearnerProfileSnapshot | undefined,
  stage: string,
  currentTaskTitle: string,
  feedback: GuideV2LearningFeedback | null,
) {
  const weakPointCount = profile?.learning_state.weak_points?.length || 0;
  const masteryItems = profile?.learning_state.mastery ?? [];
  const confidence = clampGuideScore(profile?.confidence ?? 0);
  const accuracy = clampGuideScore(profile?.overview.assessment_accuracy ?? 0);
  const preferences = profile?.stable_profile.preferences ?? [];
  const masteryAverage = masteryItems.length
    ? clampGuideScore(masteryItems.reduce((sum, item) => sum + clampGuideScore(item.score ?? 0), 0) / masteryItems.length)
    : 0;
  const prefersExternalVideo = preferences.some((item) => /公开视频|公开课|网课|网络视频|精选视频|外部视频|B站|bilibili|youtube/i.test(item));
  const prefersVideo = preferences.some((item) => item.includes("视频") || /video|youtube|bilibili/i.test(item));
  const prefersPractice = preferences.some((item) => item.includes("练习"));
  const prefersVisual = preferences.some((item) => item.includes("图解"));
  const progressStyle = deriveGuideProgressStyle(preferences, weakPointCount, confidence, accuracy, masteryAverage);
  const topWeakPoints = (profile?.learning_state.weak_points ?? []).slice(0, 2).map((item) => item.label).filter(Boolean);
  const lowMasteryTopics = masteryItems
    .filter((item) => clampGuideScore(item.score ?? 0) < 0.55)
    .slice(0, 2)
    .map((item) => item.title)
    .filter(Boolean);
  const signals: Array<{ label: string; value: string; tone: "neutral" | "brand" | "success" | "warning" }> = [];
  const reasons: Array<{ label: string; detail: string }> = [];

  let recommendedResource: GuideV2ResourceType = "visual";
  let title = "先用图解把关键概念站稳";
  let summary = "当前更适合先降低理解门槛，把概念关系和判断步骤看明白，再进入练习或视频。";
  const recommendations: string[] = [];

  const feedbackScore = typeof feedback?.score_percent === "number" ? feedback.score_percent : null;

  if (stage === "feedback" && feedbackScore !== null && feedbackScore < 60) {
    recommendedResource = "visual";
    title = "先补救错因，再做一轮复测";
    summary = "刚提交的学习证据说明还有关键卡点，先用图解或补救资源把错因拆开，再进入下一轮练习更划算。";
    recommendations.push("先看图解，把错误表现、根因和正确判断条件对齐。");
    recommendations.push("看完后立刻做短练习，确认同类错误是否真的消失。");
    reasons.push({
      label: "刚提交的反馈偏低",
      detail: `这次学习反馈分数约为 ${Math.round(feedbackScore)} 分，先补错因比继续堆新内容更划算。`,
    });
  } else if (accuracy >= 0.72 && masteryAverage >= 0.65) {
    recommendedResource = "quiz";
    title = "进入迁移验证，别只停留在看懂";
    summary = "当前表现已经不差，更值得用一组混合题验证是否能稳定迁移到新场景。";
    recommendations.push("优先做练习，检查是不是已经从“会看”变成“会做”。");
    recommendations.push("如果练习仍稳定，再继续推进下一任务。");
    reasons.push({
      label: "当前基础已经够了",
      detail: `最近正确率约 ${Math.round(accuracy * 100)}%，掌握度均值约 ${Math.round(masteryAverage * 100)}%，现在更适合做迁移验证。`,
    });
  } else if (confidence < 0.45) {
    recommendedResource = prefersPractice ? "quiz" : "visual";
    title = "先补证据，让系统判断更稳";
    summary = "系统对你当前状态还不够确定，最好先补一轮短资源和可评分证据，避免路线过深或过浅。";
    recommendations.push("优先选择能留下判断依据的资源，再提交一次明确反思。");
    recommendations.push("做完后记得提交结果，让画像判断从“猜测”变成“更确定”。");
    reasons.push({
      label: "系统判断还不够稳",
      detail: `当前画像可信度约 ${Math.round(confidence * 100)}%，先补一轮可评分证据，后面的导学才会更准。`,
    });
  } else if (prefersVideo && weakPointCount === 0 && accuracy >= 0.55) {
    recommendedResource = prefersExternalVideo ? "external_video" : "video";
    title = prefersExternalVideo ? "先找一段精选公开视频" : "可以直接用短视频加速理解";
    summary = prefersExternalVideo
      ? "你对当前任务已经有一定基础，也偏好公开视频或公开课。先看一段外部优质讲解，再回到当前任务验证，会比从零生成材料更省力。"
      : "你对当前任务已经有一定基础，且偏好视频形式，用短视频快速串起步骤会更省力。";
    recommendations.push(prefersExternalVideo ? "先看一段精选公开视频，把另一个讲解视角补上，再回到当前任务。" : "先看短视频把整体流程串起来，再回到当前任务。");
    recommendations.push("看完后补一组小练习，避免只停留在“看过”。");
    reasons.push({
      label: "你的偏好更适合视频",
      detail: prefersExternalVideo
        ? "当前没有明显薄弱点堆积，而且画像里记录到你偏好公开视频、公开课或外部视频资源。"
        : "当前没有明显薄弱点堆积，而且画像里记录到你更愿意通过短视频快速建立整体感。",
    });
  } else if (prefersPractice && accuracy >= 0.45) {
    recommendedResource = "quiz";
    title = "边做边学会更适合你";
    summary = "你已经具备一定起点，而且偏好练习型资源，此时直接做题比继续堆解释更有效。";
    recommendations.push("先做一组短练习，暴露真正不稳的知识点。");
    recommendations.push("练完再决定是否需要图解或视频补救。");
    reasons.push({
      label: "你更适合先动手",
      detail: "画像里记录到你偏好练习驱动的学习方式，所以这里优先让你边做边校准。",
    });
  } else if (prefersVisual || weakPointCount > 0) {
    recommendedResource = "visual";
    title = "先把卡点画清楚，再推进任务";
    summary = "当前仍有薄弱点或概念边界不清，图解最适合先把结构理顺。";
    recommendations.push("重点关注概念关系、判断条件和一个最小例子。");
    recommendations.push("看完后尽快进入提交页，让系统根据结果调整下一步。");
    reasons.push({
      label: "先拆结构比硬做题更值",
      detail: "当前画像里还有待补强的薄弱点，先把概念边界和判断关系看清楚，后面会更顺。",
    });
  }

  if (currentTaskTitle) {
    recommendations.unshift(`当前这一步围绕「${currentTaskTitle}」展开，不需要额外切换任务。`);
  }

  if (weakPointCount > 0) {
    signals.push({
      label: "薄弱点",
      value: topWeakPoints.length ? topWeakPoints.join("、") : `${weakPointCount} 个待补强点`,
      tone: weakPointCount >= 2 ? "warning" : "brand",
    });
    reasons.push({
      label: "当前主要卡点",
      detail: topWeakPoints.length
        ? `系统最近反复捕捉到你在「${topWeakPoints.join("、")}」上不够稳，所以先围绕这些点补。`
        : `系统最近记录到 ${weakPointCount} 个待补强点，先做聚焦补基更合适。`,
    });
  }

  if (lowMasteryTopics.length) {
    signals.push({
      label: "掌握偏低",
      value: lowMasteryTopics.join("、"),
      tone: "warning",
    });
  } else if (masteryItems.length) {
    signals.push({
      label: "掌握度",
      value: `${Math.round(masteryAverage * 100)}%`,
      tone: masteryAverage >= 0.7 ? "success" : "brand",
    });
  }

  if (preferences.length) {
    const preferredMode = prefersPractice ? "练习" : prefersVideo ? "短视频" : prefersVisual ? "图解" : preferences[0];
    signals.push({
      label: "学习偏好",
      value: preferredMode,
      tone: "neutral",
    });
  }

  if (progressStyle) {
    signals.push({
      label: "推进风格",
      value: progressStyle.label,
      tone: "brand",
    });
    reasons.push({
      label: "你的推进方式",
      detail: progressStyle.detail,
    });
  }

  if (confidence > 0) {
    signals.push({
      label: "画像可信度",
      value: `${Math.round(confidence * 100)}%`,
      tone: confidence >= 0.7 ? "success" : confidence >= 0.45 ? "brand" : "warning",
    });
  }

  if (accuracy > 0) {
    signals.push({
      label: "近期正确率",
      value: `${Math.round(accuracy * 100)}%`,
      tone: accuracy >= 0.72 ? "success" : accuracy >= 0.5 ? "brand" : "warning",
    });
  }

  return {
    title,
    summary,
    recommendations,
    reasons,
    signals,
    recommendedResource,
  };
}

function buildGuideTrendNotice(
  profile: LearnerProfileSnapshot | undefined,
  stage: "create" | "diagnostic" | "learn" | "feedback" | "complete",
) {
  if (!profile) return null;
  const recentEvidence = (profile.evidence_preview ?? []).slice(0, 5);
  const weakPoints = profile.learning_state?.weak_points ?? [];
  const scores = recentEvidence
    .map((item) => (typeof item.score === "number" ? clampGuideScore(item.score) : null))
    .filter((item): item is number => item !== null);
  const averageScore = scores.length ? scores.reduce((sum, item) => sum + item, 0) / scores.length : null;
  const recentText = recentEvidence.map((item) => `${item.source_label} ${item.title} ${item.summary || ""}`).join(" ");
  const hasCalibration = /校准|画像|profile/i.test(recentText);
  const hasQuiz = /练习|答题|quiz|题目/i.test(recentText);
  const hasResource = /图解|视频|资源|visual|video/i.test(recentText);
  const stageVerb =
    stage === "create"
      ? "这次导学会先按这个节奏起步。"
      : stage === "diagnostic"
        ? "所以这次前测更像是在校准起点。"
        : stage === "feedback"
          ? "所以现在先看反馈再决定要不要补救。"
          : stage === "complete"
            ? "所以复盘时更值得看这轮节奏有没有跑顺。"
            : "所以当前任务会优先沿这个节奏推进。";

  const cues = [
    hasQuiz ? "最近有练习反馈" : "",
    hasCalibration ? "最近有显式校准" : "",
    hasResource ? "最近有资源使用" : "",
    averageScore !== null ? `最近证据均值 ${Math.round(averageScore * 100)}%` : "",
  ].filter(Boolean);

  if (hasCalibration || (averageScore !== null && averageScore < 0.6)) {
    return {
      label: "最近更像在修正路径",
      tone: "warning" as const,
      summary: `你最近更适合先补清错因、再确认理解，而不是一下子推进太快。${stageVerb}`,
      guideHint: "进入导学后，系统会更偏向补基、图解和复测，而不是直接堆更多新任务。",
      cues,
    };
  }

  if (averageScore !== null && averageScore >= 0.78 && hasQuiz) {
    return {
      label: "最近正在变稳",
      tone: "success" as const,
      summary: `你最近几次练习和任务证据已经比较稳定，可以少一点铺垫，多一点直接验证。${stageVerb}`,
      guideHint: "进入导学后，系统会更敢把重心放到练习推进和迁移应用上。",
      cues,
    };
  }

  if (hasResource && hasQuiz && averageScore !== null && averageScore >= 0.62) {
    return {
      label: "最近开始提速",
      tone: "brand" as const,
      summary: `你最近的资源使用和练习反馈衔接得更顺，可以在现有基础上稍微加快一点节奏。${stageVerb}`,
      guideHint: "进入导学后，系统会尽量减少重复解释，把更多时间留给当前任务和结果验证。",
      cues,
    };
  }

  if (weakPoints.length) {
    return {
      label: "当前仍以聚焦补强为主",
      tone: "brand" as const,
      summary: `系统最近仍持续捕捉到「${weakPoints.slice(0, 2).map((item) => item.label).join("、")}」这些卡点，所以这次更适合先聚焦补强。${stageVerb}`,
      guideHint: "进入导学后，系统会先围绕薄弱点安排更小、更聚焦的动作。",
      cues,
    };
  }

  return {
    label: "系统仍在继续观察",
    tone: "brand" as const,
    summary: `你的学习节奏正在逐步成形，但系统还在继续观察哪种带学方式最稳。${stageVerb}`,
    guideHint: "这次导学会先保持轻量节奏，根据新的练习和反馈再进一步收紧推荐。",
    cues,
  };
}

function buildDemoRecordingCue({
  enabled,
  guideStage,
  guideSubPage,
  currentTask,
  currentDemoStep,
  generatingType,
  artifactCount,
}: {
  enabled: boolean;
  guideStage: "create" | "diagnostic" | "learn" | "feedback" | "complete";
  guideSubPage: GuideSubPage;
  currentTask: GuideV2Task | null;
  currentDemoStep: Record<string, unknown> | null;
  generatingType: GuideV2ResourceType | null;
  artifactCount: number;
}): DemoRecordingCue | null {
  if (!enabled || guideSubPage !== "main") {
    return null;
  }

  if (generatingType) {
    return {
      title: `等待${resourceLabel(generatingType)}准备好`,
      detail: "录屏时可以讲：系统正在按画像、当前任务和资源偏好调度资源生成智能体。",
      actionLabel: "准备中",
      action: "none",
      tone: "brand",
    };
  }

  if (guideStage === "learn" && currentTask) {
    const prompt = currentDemoStep ? readString(currentDemoStep, "prompt") : "";
    const resourceType = currentDemoStep ? normalizeResourceType(readString(currentDemoStep, "resource_type")) : null;
    if (artifactCount > 0) {
      return {
        title: "学完素材后提交一句反馈",
        detail: "录屏时可以讲：学生不需要填复杂表格，只要给出掌握状态和一句反思，系统就能回写画像。",
        actionLabel: "去提交",
        action: "open_complete_task",
        tone: "success",
      };
    }
    if (prompt && resourceType) {
      return {
        title: `先生成${resourceLabel(resourceType)}`,
        detail: "录屏时可以讲：这个提示词来自稳定 Demo 任务链，避免现场临时想提示词导致结果飘。",
        actionLabel: "生成稳定素材",
        action: "generate_current_seed",
        tone: "brand",
      };
    }
    return {
      title: "先完成当前任务",
      detail: "录屏时可以讲：导学页始终只把当前最该做的一件事放在前面。",
      actionLabel: "去提交",
      action: "open_complete_task",
      tone: "brand",
    };
  }

  if (guideStage === "feedback") {
    return {
      title: "反馈已经回写，接着展示产出包",
      detail: "录屏时可以讲：刚刚的分数和反思已经进入画像，接下来用产出包证明闭环完整。",
      actionLabel: "看产出包",
      action: "open_course_package",
      tone: "success",
    };
  }

  if (guideStage === "complete") {
    return {
      title: "最后展示课程产出包",
      detail: "录屏时可以讲：系统把路线、资源、反馈、报告整理成可提交的课程学习成果。",
      actionLabel: "看产出包",
      action: "open_course_package",
      tone: "success",
    };
  }

  return null;
}

function clampGuideScore(value: number) {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(1, value));
}

function deriveGuideProgressStyle(
  preferences: string[],
  weakPointCount: number,
  confidence: number,
  accuracy: number,
  masteryAverage: number,
) {
  const prefersVideo = preferences.some((item) => item.includes("视频"));
  const prefersPractice = preferences.some((item) => item.includes("练习"));
  const prefersVisual = preferences.some((item) => item.includes("图解"));

  if (prefersPractice && accuracy >= 0.55 && masteryAverage >= 0.5) {
    return {
      label: "练习驱动型",
      detail: "你更像是先通过练习暴露真实卡点，再用反馈把理解压实，所以这里更适合先动手而不是继续堆解释。",
    };
  }
  if (prefersVisual && weakPointCount > 0) {
    return {
      label: "概念澄清型",
      detail: "你更适合先把概念关系和边界看清楚，再进入练习；所以当前优先图解会更顺。",
    };
  }
  if (prefersVideo && weakPointCount === 0 && confidence >= 0.55) {
    return {
      label: "快速串联型",
      detail: "当基础已经够用时，你更适合先用短视频把流程串起来，再回到任务区完成验证。",
    };
  }
  if (confidence < 0.5) {
    return {
      label: "反复校准型",
      detail: "你当前更依赖短资源、可评分证据和连续反馈来帮助系统收敛判断，所以这一步会更看重补证据。",
    };
  }
  return {
    label: "渐进压实型",
    detail: "你更像是先获得一个大致理解，再通过练习、反馈和补强把知识一点点压实，所以系统会采用稳步推进的节奏。",
  };
}

type FeedbackDecisionResourceAction = {
  kind: "resource";
  label: string;
  resourceType: GuideV2ResourceType;
  taskId: string;
  prompt: string;
};

type FeedbackDecisionUiAction =
  | FeedbackDecisionResourceAction
  | { kind: "current_task"; label: string }
  | { kind: "route_map"; label: string };

type FeedbackDecisionPath = {
  label: string;
  description: string;
  primary: boolean;
  action: FeedbackDecisionUiAction;
};

type NormalizedFeedbackResourceAction = {
  item: NonNullable<GuideV2LearningFeedback["resource_actions"]>[number];
  resourceType: GuideV2ResourceType;
  taskId: string;
  prompt: string;
  label: string;
};

function buildFeedbackDecision(
  feedback: GuideV2LearningFeedback,
  resourceActions: NonNullable<GuideV2LearningFeedback["resource_actions"]>,
) {
  const score = typeof feedback.score_percent === "number" ? feedback.score_percent : null;
  const normalizedActions: NormalizedFeedbackResourceAction[] = resourceActions
    .map((item) => {
      const resourceType = normalizeResourceType(item.resource_type || "visual");
      const taskId = item.target_task_id || feedback.task_id || "";
      const prompt = item.prompt || `围绕「${item.concept || feedback.task_title || "当前知识点"}」生成学习资源。`;
      const label = item.label || item.title || resourceLabel(resourceType);
      return {
        item,
        resourceType,
        taskId,
        prompt,
        label,
      };
    })
    .filter((item) => item.taskId);

  const findByKeyword = (keywords: string[]) =>
    normalizedActions.find((action) => {
      const haystack = `${action.item.action_type || ""} ${action.item.label || ""} ${action.item.title || ""}`.toLowerCase();
      return keywords.some((keyword) => haystack.includes(keyword));
    }) || null;

  const remediation = findByKeyword(["补救", "remediation"]);
  const retest = findByKeyword(["复测", "retest"]);
  const transfer = findByKeyword(["迁移", "transfer"]);
  const fallbackVisual = normalizedActions.find((action) => action.resourceType === "visual") || null;
  const fallbackQuiz = normalizedActions.find((action) => action.resourceType === "quiz") || null;
  const primaryResource = remediation || retest || transfer || fallbackVisual || fallbackQuiz || normalizedActions[0] || null;

  const resourcePath = (label: string, description: string, action: NormalizedFeedbackResourceAction | null, primary: boolean): FeedbackDecisionPath | null =>
    action
      ? {
          label,
          description,
          primary,
          action: {
            kind: "resource",
            label: action.label,
            resourceType: action.resourceType,
            taskId: action.taskId,
            prompt: action.prompt,
          },
        }
      : null;

  let badge = "继续推进";
  let tone: "success" | "brand" | "warning" = "success";
  let summary = "这次结果已经比较稳，可以直接接着做下一步。";

  const paths: FeedbackDecisionPath[] = [];

  if (score !== null && score < 60) {
    badge = "先补救";
    tone = "warning";
    summary = "这次反馈说明当前卡点还比较明显，先补错因，再做复测，会比继续堆新内容更划算。";
    const primaryPath =
      resourcePath("先补救", "先把刚暴露出来的错因和概念边界补清楚。", remediation || fallbackVisual || primaryResource, true) || {
        label: "先回到当前任务",
        description: "先回到当前任务，看清这一步究竟卡在什么地方。",
        primary: true,
        action: { kind: "current_task", label: "回到当前任务" } as FeedbackDecisionUiAction,
      };
    paths.push(primaryPath);
    if (retest || fallbackQuiz) {
      paths.push(
        resourcePath("再做复测", "补完后马上做一轮短复测，确认问题是不是真的补上了。", retest || fallbackQuiz, false)!,
      );
    }
    paths.push({
      label: "看完整路线",
      description: "如果想知道系统为什么改路线，可以去看知识地图和任务队列。",
      primary: false,
      action: { kind: "route_map", label: "查看完整路线" },
    });
  } else if (score !== null && score < 75) {
    badge = "稳一下再走";
    tone = "brand";
    summary = "这次结果已经有基础，但还不够稳。先做一轮针对性补强或短复测，再继续推进会更稳。";
    const firstChoice = retest || remediation || fallbackQuiz || fallbackVisual || primaryResource;
    paths.push(
      resourcePath("先稳住这一块", "用一轮短资源或复测把当前知识点压实，再继续推进。", firstChoice, true) || {
        label: "回到当前任务",
        description: "先回到当前任务，把刚才还不稳的地方补一句反思或再看一遍。",
        primary: true,
        action: { kind: "current_task", label: "回到当前任务" },
      },
    );
    paths.push({
      label: "继续当前任务",
      description: "如果你已经知道错在哪里，也可以直接回到任务区继续推进。",
      primary: false,
      action: { kind: "current_task", label: "去当前任务" },
    });
    paths.push({
      label: "看完整路线",
      description: "想看系统后面准备怎么安排，可以打开完整路线页。",
      primary: false,
      action: { kind: "route_map", label: "查看完整路线" },
    });
  } else {
    badge = "可以继续";
    tone = "success";
    summary = "这次结果已经比较稳，优先继续推进下一步；如果你想更扎实，也可以顺手做一轮迁移练习。";
    paths.push({
      label: "继续推进",
      description: feedback.next_task_title
        ? `系统已经准备好下一步「${feedback.next_task_title}」，可以直接继续。`
        : "继续当前路线，让系统把你带到下一步任务。",
      primary: true,
      action: { kind: "current_task", label: "去下一步任务" },
    });
    if (transfer || fallbackQuiz || fallbackVisual) {
      paths.push(
        resourcePath("顺手再巩固", "如果你想更扎实，可以再做一轮迁移练习或轻量复习。", transfer || fallbackQuiz || fallbackVisual, false)!,
      );
    }
    paths.push({
      label: "看完整路线",
      description: "如果想提前看看后面的安排，可以打开完整路线页。",
      primary: false,
      action: { kind: "route_map", label: "查看完整路线" },
    });
  }

  return { badge, tone, summary, paths: paths.slice(0, 3) };
}

function extractArtifactPersonalization(artifact: GuideV2Artifact) {
  const result = asRecord(artifact.result) ?? {};
  const config = asRecord(artifact.config) ?? {};
  const direct = asRecord(result.personalization) ?? asRecord(config.personalization);
  const hints =
    asRecord(result.learner_profile_hints) ??
    asRecord(config.learner_profile_hints) ??
    asRecord(asRecord(result.metadata ?? null)?.learner_profile_hints);

  const reasons: string[] = [];
  const signals: Array<{ label: string; value: string }> = [];

  const appendLines = (value: unknown) => {
    if (typeof value === "string") {
      splitLines(value).forEach((item) => reasons.push(item));
      return;
    }
    if (Array.isArray(value)) {
      value.map(String).map((item) => item.trim()).filter(Boolean).forEach((item) => reasons.push(item));
    }
  };

  if (direct) {
    appendLines(direct.reason);
    appendLines(direct.rationale);
    appendLines(direct.summary);
    appendLines(direct.reasons);
  }

  const weakPoints = normalizeTextArray(hints?.weak_points ?? direct?.weak_points);
  const mistakes = normalizeTextArray(hints?.mistake_patterns ?? direct?.mistake_patterns);
  const preferences = normalizeTextArray(hints?.preferences ?? direct?.preferences);
  const masteryTopics = normalizeTextArray(hints?.mastery_gaps ?? direct?.mastery_gaps);
  const level = readMaybeString(hints, "level") || readMaybeString(direct, "level");
  const timeBudget = readMaybeString(hints, "time_budget_minutes") || readMaybeString(direct, "time_budget_minutes");
  const progressStyle = deriveArtifactProgressStyle({
    artifactType: String(artifact.type),
    weakPoints,
    mistakes,
    preferences,
    masteryTopics,
    level,
    timeBudget,
  });

  if (weakPoints.length) {
    signals.push({ label: "薄弱点", value: weakPoints.slice(0, 2).join("、") });
    reasons.push(`这份资源优先照顾你当前不稳的点：${weakPoints.slice(0, 2).join("、")}。`);
  }
  if (masteryTopics.length) {
    signals.push({ label: "掌握待补", value: masteryTopics.slice(0, 2).join("、") });
  }
  if (mistakes.length) {
    signals.push({ label: "常见错因", value: mistakes.slice(0, 2).join("、") });
    reasons.push(`系统也参考了你最近暴露出的错因：${mistakes.slice(0, 2).join("、")}。`);
  }
  if (preferences.length) {
    signals.push({ label: "学习偏好", value: preferences.slice(0, 2).join("、") });
  }
  if (level) {
    signals.push({ label: "当前水平", value: level });
  }
  if (timeBudget) {
    signals.push({ label: "时间预算", value: `${String(timeBudget).replace(/[^\d]/g, "") || timeBudget} 分钟` });
  }
  if (progressStyle) {
    signals.push({ label: "推进风格", value: progressStyle.label });
    reasons.push(progressStyle.explanation);
  }

  const uniqueReasons = Array.from(new Set(reasons.map((item) => item.trim()).filter(Boolean)));
  if (!signals.length && !uniqueReasons.length) return null;

  const headline =
    uniqueReasons[0] ||
    `这份${resourceLabel(String(artifact.type))}不是随机生成的，而是结合你当前的学习画像、卡点和偏好做了针对性调整。`;

  return {
    headline,
    reasons: uniqueReasons,
    signals,
    progressStyle,
  };
}

function deriveArtifactProgressStyle({
  artifactType,
  weakPoints,
  mistakes,
  preferences,
  masteryTopics,
  level,
  timeBudget,
}: {
  artifactType: string;
  weakPoints: string[];
  mistakes: string[];
  preferences: string[];
  masteryTopics: string[];
  level: string;
  timeBudget: string;
}) {
  const normalizedPreferences = preferences.map((item) => item.toLowerCase());
  const prefersPractice = normalizedPreferences.some((item) => /练|题|quiz|practice|刷题/.test(item));
  const prefersVisual = normalizedPreferences.some((item) => /图|visual|diagram|结构|示意/.test(item));
  const prefersVideo = normalizedPreferences.some((item) => /视频|video|动画|manim/.test(item));
  const hasWeakPoints = weakPoints.length > 0 || masteryTopics.length > 0;
  const hasMistakes = mistakes.length > 0;
  const compactTime = Number.parseInt(String(timeBudget).replace(/[^\d]/g, ""), 10);
  const lowLevel = /零基础|初学|入门|beginner/i.test(level);

  if (prefersPractice || artifactType === "quiz") {
    return {
      label: "练习驱动型",
      explanation: "系统判断你更适合先通过动手作答来压实理解，所以这份资源会更强调可检验和可反馈。",
      recommendation: "建议先独立完成，再结合反馈看错因，会比只看讲解更容易形成稳定掌握。",
    };
  }

  if (artifactType === "external_video") {
    return {
      label: "外部补充型",
      explanation: "系统判断你适合先参考公开视频，用另一个讲解视角降低理解门槛，再回到当前任务做反馈。",
      recommendation: "建议只看一到两个精选视频，不要陷入搜索；看完立刻回到导学提交一句反思。",
    };
  }

  if (prefersVideo || artifactType === "video") {
    return {
      label: "渐进演示型",
      explanation: "系统判断你更适合跟着过程一步步进入问题，所以这份资源会把关键步骤拆开讲，而不是一次性堆满信息。",
      recommendation: "先顺着演示走一遍，再回到当前任务复述关键步骤，吸收会更扎实。",
    };
  }

  if (prefersVisual || artifactType === "visual") {
    return {
      label: "概念澄清型",
      explanation: "系统判断你当前更需要把概念边界和结构关系看清楚，所以这份资源会优先帮你建立直观理解。",
      recommendation: "先把图里的关系讲明白，再去做题或看公式推导，后续会更顺。",
    };
  }

  if (hasMistakes) {
    return {
      label: "反复校准型",
      explanation: "系统发现你最近更需要先修正错因，所以这份资源会优先对准容易出错的地方，而不是平均铺开。",
      recommendation: "重点盯住这些错因是否真的被改掉，学完后最好立刻做一次复测。",
    };
  }

  if (hasWeakPoints || lowLevel) {
    return {
      label: "渐进压实型",
      explanation: "系统判断你当前还处在补基础和压实关键节点的阶段，所以这份资源会先保住核心理解，再逐步扩展。",
      recommendation: "先吃透这一份，再继续推进下一步，比一口气看太多更适合当前状态。",
    };
  }

  if (Number.isFinite(compactTime) && compactTime > 0 && compactTime <= 12) {
    return {
      label: "快速串联型",
      explanation: "系统参考了你当前较紧的时间预算，所以这份资源会尽量快速串起关键概念和步骤。",
      recommendation: "先抓主线，不必一开始就抠所有细节，后面再按反馈补重点会更有效。",
    };
  }

  return null;
}

function normalizeTextArray(value: unknown) {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => String(item).trim())
    .filter(Boolean);
}

function readMaybeString(source: Record<string, unknown> | null | undefined, key: string) {
  if (!source) return "";
  const value = source[key];
  if (typeof value === "string" && value.trim()) return value.trim();
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return "";
}
