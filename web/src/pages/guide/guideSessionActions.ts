import type { Dispatch, FormEvent, SetStateAction } from "react";

import type { useGuideV2Mutations } from "@/hooks/useApiQueries";
import type {
  GuideV2CourseTemplate,
  GuideV2LearningFeedback,
  GuideV2DiagnosticAnswer,
  GuideV2Task,
  NotebookReference,
} from "@/lib/types";
import type { GuideSubPage } from "./guideLearningStrategy";
import { splitLines } from "./guideDataUtils";

type GuideV2Mutations = ReturnType<typeof useGuideV2Mutations>;

export function buildGuideSessionActions({
  activeSessionId,
  courseTemplateId,
  courseTemplates,
  currentTask,
  demoTemplate,
  goal,
  horizon,
  level,
  mutations,
  notebookReferences,
  preferences,
  reflection,
  refetchCoursePackage,
  refetchDetail,
  refetchLearningReport,
  refetchSessions,
  refetchStudyPlan,
  refreshLearnerProfileAfterGuide,
  score,
  sourceAction,
  timeBudget,
  weakPoints,
  setCourseTemplateId,
  setForceNewSession,
  setGoal,
  setGoalTouched,
  setHorizon,
  setLearningFeedback,
  setLevel,
  setPreferences,
  setPrescriptionFeedback,
  setReflection,
  setSaveMessage,
  setSelectedSessionId,
  setSourceAction,
  setTimeBudget,
  setWeakPoints,
  setGuideSubPage,
}: {
  activeSessionId: string | null;
  courseTemplateId: string;
  courseTemplates: GuideV2CourseTemplate[];
  currentTask: GuideV2Task | null;
  demoTemplate: GuideV2CourseTemplate | null;
  goal: string;
  horizon: string;
  level: string;
  mutations: GuideV2Mutations;
  notebookReferences: NotebookReference[];
  preferences: string[];
  reflection: string;
  refetchCoursePackage: () => unknown;
  refetchDetail: () => unknown;
  refetchLearningReport: () => unknown;
  refetchSessions: () => unknown;
  refetchStudyPlan: () => unknown;
  refreshLearnerProfileAfterGuide: () => Promise<string>;
  score: string;
  sourceAction: Record<string, unknown> | null;
  timeBudget: string;
  weakPoints: string;
  setCourseTemplateId: Dispatch<SetStateAction<string>>;
  setForceNewSession: Dispatch<SetStateAction<boolean>>;
  setGoal: Dispatch<SetStateAction<string>>;
  setGoalTouched: Dispatch<SetStateAction<boolean>>;
  setHorizon: Dispatch<SetStateAction<string>>;
  setLearningFeedback: Dispatch<SetStateAction<GuideV2LearningFeedback | null>>;
  setLevel: Dispatch<SetStateAction<string>>;
  setPreferences: Dispatch<SetStateAction<string[]>>;
  setPrescriptionFeedback: Dispatch<SetStateAction<GuideV2LearningFeedback | null>>;
  setReflection: Dispatch<SetStateAction<string>>;
  setSaveMessage: Dispatch<SetStateAction<string>>;
  setSelectedSessionId: Dispatch<SetStateAction<string | null>>;
  setSourceAction: Dispatch<SetStateAction<Record<string, unknown> | null>>;
  setTimeBudget: Dispatch<SetStateAction<string>>;
  setWeakPoints: Dispatch<SetStateAction<string>>;
  setGuideSubPage: Dispatch<SetStateAction<GuideSubPage>>;
}) {
  const applyCourseTemplate = (template: GuideV2CourseTemplate, mode: "default" | "demo" = "default") => {
    setCourseTemplateId(template.id);
    const demoPersona = template.demo_seed?.persona;
    if (mode === "demo" && demoPersona?.goal) {
      setGoal(`${demoPersona.goal}。请按稳定 Demo 样例演示 T1 全景图、T4 梯度下降图解、T6 模型评估练习。`);
      setGoalTouched(true);
    } else if (template.default_goal) {
      setGoal(template.default_goal);
      setGoalTouched(true);
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

  const resetToSession = (sessionId: string) => {
    setForceNewSession(false);
    setSourceAction(null);
    setSelectedSessionId(sessionId);
    setReflection("");
    setLearningFeedback(null);
    setPrescriptionFeedback(null);
    setGuideSubPage("main");
  };

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
      resetToSession(created.session.session_id);
      const profileSyncMessage = await refreshLearnerProfileAfterGuide();
      setSaveMessage(`路线已创建。${profileSyncMessage}`);
    }
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
      resetToSession(created.session.session_id);
      const profileSyncMessage = await refreshLearnerProfileAfterGuide();
      setSaveMessage(`已创建稳定演示路线。${profileSyncMessage}`);
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
    void refetchLearningReport();
    void refetchCoursePackage();
    void refetchStudyPlan();
    void refetchDetail();
    void refetchSessions();
    const profileSyncMessage = await refreshLearnerProfileAfterGuide();
    setSaveMessage([result.learning_feedback?.summary || "学习记录已保存。", profileSyncMessage].filter(Boolean).join(" "));
    setReflection("");
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
    setSaveMessage(`前测已更新学习记录：准备度 ${Math.round(scoreValue * 100)}%${weak ? `，优先照顾「${weak}」` : ""}。 ${profileSyncMessage}`);
  };

  const deleteActiveSession = async () => {
    if (!activeSessionId || !window.confirm("删除这条学习路径？")) return;
    await mutations.remove.mutateAsync(activeSessionId);
    setSelectedSessionId(null);
  };

  return {
    applyCourseTemplate,
    completeCurrentTask,
    createSession,
    deleteActiveSession,
    selectCourseTemplate,
    startDemoSession,
    submitDiagnostic,
  };
}
