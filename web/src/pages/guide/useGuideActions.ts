import { buildGuideDemoCueAction } from "./guideDemoCueActions";
import { buildGuidePersistenceActions } from "./guidePersistenceActions";
import { buildGuideResourceGenerationActions } from "./guideResourceGenerationActions";
import { buildGuideSessionActions } from "./guideSessionActions";
import type { useGuideDerivedState } from "./useGuideDerivedState";
import type { useGuidePageState } from "./useGuidePageState";
import { useGuideResourceJobEvents } from "./useGuideResourceJobEvents";
import type { useGuideRuntimeData } from "./useGuideRuntimeData";

type GuideActionsParams = {
  derived: ReturnType<typeof useGuideDerivedState>;
  runtime: ReturnType<typeof useGuideRuntimeData>;
  scrollToGuideSection: (sectionId: string) => void;
  state: ReturnType<typeof useGuidePageState>;
};

export function useGuideActions({
  derived,
  runtime,
  scrollToGuideSection,
  state,
}: GuideActionsParams) {
  const {
    activeSessionId,
    coursePackage,
    detail,
    learnerProfileMutations,
    learningReport,
    mutations,
    sessions,
    studyPlan,
  } = runtime;
  const {
    courseTemplateId,
    goal,
    horizon,
    level,
    preferences,
    reflection,
    resourceJobId,
    saveNotebookId,
    score,
    sourceAction,
    timeBudget,
    weakPoints,
    setCourseTemplateId,
    setForceNewSession,
    setGeneratingType,
    setGoal,
    setGoalTouched,
    setGuideSubPage,
    setHorizon,
    setLearningFeedback,
    setLevel,
    setPreferences,
    setPrescriptionFeedback,
    setPrescriptionTaskId,
    setReflection,
    setResourceJobId,
    setSaveMessage,
    setSelectedSessionId,
    setSourceAction,
    setTimeBudget,
    setWeakPoints,
  } = state;
  const {
    courseTemplates,
    currentDemoStep,
    currentTask,
    demoRecordingCue,
    demoTemplate,
    effectivePrescriptionTaskId,
    guideStage,
    notebookReferences,
    tasks,
  } = derived;

  const busy =
    mutations.create.isPending ||
    mutations.completeTask.isPending ||
    mutations.submitDiagnostic.isPending ||
    mutations.refreshRecommendations.isPending ||
    mutations.startResourceJob.isPending ||
    mutations.remove.isPending ||
    learnerProfileMutations.refresh.isPending;

  const refreshLearnerProfileAfterGuide = async () => {
    try {
      const profile = await learnerProfileMutations.refresh.mutateAsync({ force: true });
      const focus = profile?.overview?.current_focus?.trim();
      return focus ? `画像已同步，当前重点：${focus}。` : "画像已同步，可前往学习画像页查看变化。";
    } catch {
      return "学习证据已记录，画像会在后台继续同步。";
    }
  };

  const refetchCoursePackage = coursePackage.refetch;
  const refetchDetail = detail.refetch;
  const refetchLearningReport = learningReport.refetch;
  const refetchSessions = sessions.refetch;
  const refetchStudyPlan = studyPlan.refetch;

  useGuideResourceJobEvents({
    resourceJobId,
    refetchCoursePackage,
    refetchDetail,
    refetchLearningReport,
    refetchSessions,
    refetchStudyPlan,
    setGeneratingType,
    setResourceJobId,
    setSaveMessage,
  });

  const sessionActions = buildGuideSessionActions({
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
    setGuideSubPage,
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
  });
  const { generateResource } = buildGuideResourceGenerationActions({
    activeSessionId,
    currentTask,
    mutations,
    scrollToGuideSection,
    setGeneratingType,
    setPrescriptionFeedback,
    setPrescriptionTaskId,
    setResourceJobId,
    setSaveMessage,
  });
  const runDemoRecordingCue = buildGuideDemoCueAction({
    currentDemoStep,
    currentTask,
    demoRecordingCue,
    generateResource,
    scrollToGuideSection,
    setGuideSubPage,
  });
  const persistenceActions = buildGuidePersistenceActions({
    activeSessionId,
    coursePackageData: coursePackage.data,
    currentTask,
    effectivePrescriptionTaskId,
    guideStage,
    learningReportData: learningReport.data,
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
  });

  return {
    ...sessionActions,
    ...persistenceActions,
    busy,
    generateResource,
    runDemoRecordingCue,
  };
}
