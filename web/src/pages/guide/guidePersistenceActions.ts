import type { Dispatch, SetStateAction } from "react";

import type { useGuideV2Mutations } from "@/hooks/useApiQueries";
import type {
  GuideV2Artifact,
  GuideV2CoursePackage,
  GuideV2LearningFeedback,
  GuideV2LearningReport,
  GuideV2Task,
  QuizResultItem,
} from "@/lib/types";
import type { GuideStage } from "./guideLearningStrategy";
import { downloadGuideMarkdown } from "./guideDownloadUtils";

type GuideV2Mutations = ReturnType<typeof useGuideV2Mutations>;

export function buildGuidePersistenceActions({
  activeSessionId,
  coursePackageData,
  currentTask,
  effectivePrescriptionTaskId,
  guideStage,
  learningReportData,
  mutations,
  refetchCoursePackage,
  refetchLearningReport,
  refetchSessions,
  refetchStudyPlan,
  refreshLearnerProfileAfterGuide,
  saveNotebookId,
  setLearningFeedback,
  setPrescriptionFeedback,
  setSaveMessage,
  tasks,
}: {
  activeSessionId: string | null;
  coursePackageData: GuideV2CoursePackage | null | undefined;
  currentTask: GuideV2Task | null;
  effectivePrescriptionTaskId: string;
  guideStage: GuideStage;
  learningReportData: GuideV2LearningReport | null | undefined;
  mutations: GuideV2Mutations;
  refetchCoursePackage: () => unknown;
  refetchLearningReport: () => unknown;
  refetchSessions: () => unknown;
  refetchStudyPlan: () => unknown;
  refreshLearnerProfileAfterGuide: () => Promise<string>;
  saveNotebookId: string;
  setLearningFeedback: Dispatch<SetStateAction<GuideV2LearningFeedback | null>>;
  setPrescriptionFeedback: Dispatch<SetStateAction<GuideV2LearningFeedback | null>>;
  setSaveMessage: Dispatch<SetStateAction<string>>;
  tasks: GuideV2Task[];
}) {
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
      title: learningReportData?.title,
      summary: learningReportData?.summary,
    });
    const added = result.notebook?.added_to_notebooks?.length ?? 0;
    setSaveMessage(`学习效果报告已保存到 ${added || 0} 个 Notebook。`);
  };

  const downloadLearningReport = () => {
    const result = downloadGuideMarkdown({
      markdown: learningReportData?.markdown,
      title: learningReportData?.title,
      fallbackName: "sparkweave-learning-report",
    });
    if (!result.ok) {
      setSaveMessage("学习报告还没有可下载内容，请稍后刷新。");
      return;
    }
    setSaveMessage(`已下载学习报告：${result.filename}`);
  };

  const saveCoursePackage = async () => {
    if (!activeSessionId || !saveNotebookId) return;
    setSaveMessage("");
    const result = await mutations.saveCoursePackage.mutateAsync({
      sessionId: activeSessionId,
      notebookIds: [saveNotebookId],
      title: coursePackageData?.title,
      summary: coursePackageData?.summary,
    });
    const added = result.notebook?.added_to_notebooks?.length ?? 0;
    setSaveMessage(`课程产出包已保存到 ${added || 0} 个 Notebook。`);
  };

  const downloadCoursePackage = () => {
    const result = downloadGuideMarkdown({
      markdown: coursePackageData?.markdown,
      title: coursePackageData?.title,
      fallbackName: "sparkweave-course-package",
    });
    if (!result.ok) {
      setSaveMessage("课程产出包还没有可下载内容，请稍后刷新。");
      return;
    }
    setSaveMessage(`已下载课程产出包：${result.filename}`);
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
      void refetchLearningReport();
      void refetchCoursePackage();
      void refetchStudyPlan();
      void refetchSessions();
    }
    const profileSyncMessage = await refreshLearnerProfileAfterGuide();
    setSaveMessage(
      `${isPrescriptionArtifact ? "处方复测已回写" : "练习已回写"}：得分 ${Math.round(scoreValue * 100)}%，同步 ${savedCount} 道题到题目本。 ${profileSyncMessage}`,
    );
  };

  return {
    downloadCoursePackage,
    downloadLearningReport,
    saveArtifact,
    saveCoursePackage,
    saveLearningReport,
    submitQuizArtifact,
  };
}
