import { useMemo } from "react";

import type {
  GuideV2CourseTemplate,
  GuideV2LearningFeedback,
  GuideV2LearningReport,
  GuideV2ResourceType,
  GuideV2Session,
  LearnerProfileSnapshot,
  NotebookRecord,
  NotebookReference,
} from "@/lib/types";
import { asRecord, readString } from "./guideDataUtils";
import { normalizeDemoSeedTaskChain } from "./guideDemoSeedUtils";
import {
  buildAdaptiveGuideStrategy,
  buildDemoRecordingCue,
  buildGuideTrendNotice,
  latestLearningFeedbackFromSession,
} from "./guideLearningStrategy";
import type { GuideStage, GuideSubPage } from "./guideLearningStrategy";
import {
  buildGuideResourceActions,
  buildGuideResourceButtonCopy,
  isResearchResourceType,
} from "./guideResourceUtils";

export function useGuideDerivedState({
  courseTemplateId,
  courseTemplatesData,
  diagnosticStatus,
  generatingType,
  guideSubPage,
  learnerProfile,
  learningFeedback,
  learningReport,
  prescriptionTaskId,
  referenceNotebookId,
  referenceNotebookRecords,
  selectedRecordIds,
  session,
}: {
  courseTemplateId: string;
  courseTemplatesData?: GuideV2CourseTemplate[];
  diagnosticStatus?: string;
  generatingType: GuideV2ResourceType | null;
  guideSubPage: GuideSubPage;
  learnerProfile?: LearnerProfileSnapshot;
  learningFeedback: GuideV2LearningFeedback | null;
  learningReport?: GuideV2LearningReport | null;
  prescriptionTaskId: string;
  referenceNotebookId: string;
  referenceNotebookRecords?: NotebookRecord[];
  selectedRecordIds: string[];
  session: GuideV2Session | null;
}) {
  const courseTemplates = courseTemplatesData ?? [];
  const selectedTemplate = courseTemplates.find((item) => item.id === courseTemplateId) ?? null;
  const demoTemplate =
    courseTemplates.find((item) => item.id === "ml_foundations") ??
    courseTemplates.find((item) => (item.demo_seed?.task_chain ?? []).length > 0) ??
    null;
  const profileNextAction = learnerProfile?.next_action ?? null;
  const profileSuggestedPrompt = profileNextAction?.suggested_prompt?.trim() || learnerProfile?.overview.current_focus?.trim() || "";
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
    () => (referenceNotebookRecords ?? []).slice(0, 6),
    [referenceNotebookRecords],
  );
  const notebookReferences = useMemo<NotebookReference[]>(() => {
    if (!referenceNotebookId || !selectedRecordIds.length) return [];
    return [{ notebook_id: referenceNotebookId, record_ids: selectedRecordIds }];
  }, [referenceNotebookId, selectedRecordIds]);
  const currentArtifacts = useMemo(
    () => (currentTask?.artifact_refs ?? []).filter((artifact) => !isResearchResourceType(String(artifact.type))),
    [currentTask?.artifact_refs],
  );
  const demoTaskChain = useMemo(() => {
    const demoSeed = asRecord(courseMetadata.demo_seed);
    return normalizeDemoSeedTaskChain(demoSeed, tasks);
  }, [courseMetadata, tasks]);
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
    const brief = learningReport?.action_brief;
    const candidates = [brief?.primary_action, ...(brief?.secondary_actions ?? [])];
    return candidates.map((item) => String(item?.target_task_id || "")).find(Boolean) || "";
  }, [learningReport?.action_brief]);
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
  const diagnosticDone = diagnosticStatus === "completed";
  const guideStage: GuideStage = !session ? "create" : !diagnosticDone ? "diagnostic" : activeLearningFeedback ? "feedback" : currentTask ? "learn" : "complete";
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
    () => buildAdaptiveGuideStrategy(learnerProfile, guideStage, currentTask?.title || "", activeLearningFeedback),
    [activeLearningFeedback, currentTask?.title, guideStage, learnerProfile],
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
      ? "写下目标和时间就够了，系统会自动把它拆成能执行的学习路线。"
      : guideStage === "diagnostic"
        ? "先用几道问题校准起点，后面的任务才不会太难或太浅。"
        : guideStage === "feedback"
          ? "刚刚的学习证据已经记录。先看反馈，再决定继续还是补救。"
          : guideStage === "complete"
            ? "这条路线已经走完，可以查看报告、导出课程包，或者开启新的目标。"
            : "现在只需要盯住这一件事：完成当前任务，并留下能被系统判断的学习证据。";
  const trendNotice = useMemo(
    () => buildGuideTrendNotice(learnerProfile, guideStage),
    [guideStage, learnerProfile],
  );
  const resourceButtonCopy = useMemo(
    () => buildGuideResourceButtonCopy(adaptiveGuideStrategy.recommendedResource, trendNotice?.label || ""),
    [adaptiveGuideStrategy.recommendedResource, trendNotice?.label],
  );
  const resourceActions = useMemo(
    () => buildGuideResourceActions(adaptiveGuideStrategy.recommendedResource, resourceButtonCopy),
    [adaptiveGuideStrategy.recommendedResource, resourceButtonCopy],
  );

  return {
    activeLearningFeedback,
    adaptiveGuideStrategy,
    courseMetadata,
    courseTemplates,
    currentArtifacts,
    currentDemoStep,
    currentTask,
    demoRecordingCue,
    demoTemplate,
    effectivePrescriptionTaskId,
    guideStage,
    isDemoSeedSession,
    nodes,
    notebookReferences,
    prescriptionArtifacts,
    prescriptionTask,
    primaryActionLabel,
    primaryResourceAction: resourceActions[0],
    profileNextAction,
    profileSuggestedPrompt,
    referenceRecords,
    resourceActions,
    routeUsesUnifiedProfile,
    selectedTemplate,
    showPrescriptionResults,
    stageMessage,
    tasks,
  };
}
