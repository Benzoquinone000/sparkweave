import { lazy, Suspense } from "react";

import type { useGuideActions } from "./useGuideActions";
import type { useGuideDerivedState } from "./useGuideDerivedState";
import type { useGuidePageState } from "./useGuidePageState";
import type { useGuideRuntimeData } from "./useGuideRuntimeData";
import { GuideStepFrame } from "./GuideStepFrame";

const GuideCompleteStagePage = lazy(() =>
  import("./GuideCompleteStagePage").then((module) => ({ default: module.GuideCompleteStagePage })),
);
const GuideCreateRoutePanel = lazy(() =>
  import("./GuideCreateRoutePanel").then((module) => ({ default: module.GuideCreateRoutePanel })),
);
const GuideCurrentTaskPanel = lazy(() =>
  import("./GuideCurrentTaskPanel").then((module) => ({ default: module.GuideCurrentTaskPanel })),
);
const GuideDiagnosticStagePanel = lazy(() =>
  import("./GuideDiagnosticStagePanel").then((module) => ({ default: module.GuideDiagnosticStagePanel })),
);
const GuideFeedbackStagePanel = lazy(() =>
  import("./GuideFeedbackStagePanel").then((module) => ({ default: module.GuideFeedbackStagePanel })),
);

type GuideMainStagePageProps = {
  actions: ReturnType<typeof useGuideActions>;
  derived: ReturnType<typeof useGuideDerivedState>;
  highlightedSectionId: string | null;
  onContinueAfterFeedback: () => void;
  runtime: ReturnType<typeof useGuideRuntimeData>;
  scrollToGuideSection: (sectionId: string) => void;
  state: ReturnType<typeof useGuidePageState>;
};

export function GuideMainStagePage({
  actions,
  derived,
  highlightedSectionId,
  onContinueAfterFeedback,
  runtime,
  scrollToGuideSection,
  state,
}: GuideMainStagePageProps) {
  const {
    activeSessionId,
    diagnostic,
    learnerProfileMutations,
    learningReport,
    mutations,
    session,
    templates,
  } = runtime;
  const {
    courseTemplateId,
    generatingType,
    goal,
    prescriptionFeedback,
    resourceJobSnapshot,
    saveNotebookId,
    sourceAction,
    setGuideSubPage,
    updateGoal,
  } = state;
  const {
    activeLearningFeedback,
    adaptiveGuideStrategy,
    courseTemplates,
    currentArtifacts,
    currentDemoStep,
    currentTask,
    demoTemplate,
    guideStage,
    isDemoSeedSession,
    prescriptionArtifacts,
    prescriptionTask,
    primaryActionLabel,
    primaryResourceAction,
    profileSuggestedPrompt,
    showPrescriptionResults,
  } = derived;
  const {
    applyCourseTemplate,
    busy,
    createSession,
    downloadLearningReport,
    generateResource,
    saveArtifact,
    saveLearningReport,
    startDemoSession,
    submitDiagnostic,
    submitQuizArtifact,
  } = actions;

  if (!session) {
    return (
      <GuideStepFrame step={1} total={4} title="先定一个目标" subtitle="写一句话就够，系统会拆成学习路线。">
        <Suspense fallback={<GuideStageLoading label="正在准备路线" />}>
          <GuideCreateRoutePanel
            primaryActionLabel={primaryActionLabel}
            sourceAction={sourceAction}
            profileSuggestedPrompt={profileSuggestedPrompt}
            goal={goal}
            demoTemplate={demoTemplate}
            templatesLoading={templates.isFetching}
            creating={mutations.create.isPending}
            courseTemplates={courseTemplates}
            courseTemplateId={courseTemplateId}
            onSubmit={createSession}
            onGoalChange={updateGoal}
            onStartDemo={() => void startDemoSession()}
            onPickTemplate={applyCourseTemplate}
            onOpenSetup={() => setGuideSubPage("setup")}
          />
        </Suspense>
      </GuideStepFrame>
    );
  }

  if (guideStage === "diagnostic") {
    return (
      <GuideStepFrame
        step={2}
        total={4}
        title="做一个小前测"
        subtitle="一题一页，答完自动进入学习任务。"
        previousLabel="补充信息"
        onPrevious={() => setGuideSubPage("setup")}
      >
        <Suspense fallback={<GuideStageLoading label="正在准备前测" />}>
          <GuideDiagnosticStagePanel
            highlightedSectionId={highlightedSectionId}
            diagnostic={diagnostic.data ?? null}
            loading={diagnostic.isFetching}
            submitting={mutations.submitDiagnostic.isPending}
            disabled={!activeSessionId || busy}
            onSubmit={(answers) => void submitDiagnostic(answers)}
          />
        </Suspense>
      </GuideStepFrame>
    );
  }

  if (guideStage === "feedback") {
    return (
      <GuideStepFrame
        step={4}
        total={4}
        title="看反馈"
        subtitle="只看结论和下一步，详细记录放在记录页。"
        previousLabel="提交记录"
        nextLabel="继续学习"
        onPrevious={() => setGuideSubPage("completeTask")}
        onNext={onContinueAfterFeedback}
      >
        <Suspense fallback={<GuideStageLoading label="正在准备反馈" />}>
          <GuideFeedbackStagePanel
            highlightedSectionId={highlightedSectionId}
            feedback={activeLearningFeedback}
            learningEffectReport={learningReport.data?.learning_effect_report ?? null}
            disabled={busy || Boolean(generatingType)}
            profileRefreshing={learnerProfileMutations.refresh.isPending}
            demoEnabled={isDemoSeedSession}
            report={learningReport.data ?? null}
            reportLoading={learningReport.isFetching}
            onGenerateResource={(type, taskId, prompt) => void generateResource(type, taskId, prompt)}
            onOpenCurrentTask={onContinueAfterFeedback}
            onOpenRouteMap={() => {
              setGuideSubPage("routeMap");
              scrollToGuideSection("guide-route-map-section");
            }}
            onOpenCoursePackage={() => setGuideSubPage("coursePackage")}
          />
        </Suspense>
      </GuideStepFrame>
    );
  }

  if (guideStage === "complete") {
    return (
      <GuideStepFrame
        step={4}
        total={4}
        title="学习报告"
        subtitle="这一轮结束了，先看摘要，再保存或查看成果。"
        previousLabel="看路线"
        onPrevious={() => setGuideSubPage("routeMap")}
      >
        <Suspense fallback={<GuideStageLoading label="正在准备报告" />}>
          <GuideCompleteStagePage
            highlightedSectionId={highlightedSectionId}
            report={learningReport.data ?? null}
            reportLoading={learningReport.isFetching}
            canSaveReport={Boolean(activeSessionId && saveNotebookId)}
            savingReport={mutations.saveReport.isPending}
            canExportReport={Boolean(learningReport.data?.markdown)}
            prescriptionFeedback={prescriptionFeedback}
            showPrescriptionResults={showPrescriptionResults}
            prescriptionTask={prescriptionTask}
            prescriptionArtifacts={prescriptionArtifacts}
            generatingType={generatingType}
            saveNotebookId={saveNotebookId}
            savingArtifact={mutations.saveArtifact.isPending}
            quizSubmitting={mutations.submitQuiz.isPending}
            onSaveReport={() => void saveLearningReport()}
            onExportReport={downloadLearningReport}
            onOpenRouteMap={() => setGuideSubPage("routeMap")}
            onOpenCoursePackage={() => setGuideSubPage("coursePackage")}
            onGenerateResource={(type, taskId, prompt) => void generateResource(type, taskId, prompt)}
            onReviewReport={() => scrollToGuideSection("guide-complete-section")}
            onOpenMemory={() => {
              window.location.href = "/memory";
            }}
            onSaveArtifact={(artifact) => void saveArtifact(artifact)}
            onSubmitQuiz={(artifact, answers) => void submitQuizArtifact(artifact, answers)}
          />
        </Suspense>
      </GuideStepFrame>
    );
  }

  return (
    <GuideStepFrame
      step={3}
      total={4}
      title={currentTask?.title || "当前任务"}
      subtitle="这一页只完成当前任务。需要路线或提交结果，用底部按钮切换。"
      previousLabel="看路线"
      nextLabel="提交学习记录"
      onPrevious={() => setGuideSubPage("routeMap")}
      onNext={() => setGuideSubPage("completeTask")}
    >
      <Suspense fallback={<GuideStageLoading label="正在准备当前任务" />}>
        <GuideCurrentTaskPanel
          guideStage={guideStage}
          currentTask={currentTask}
          currentDemoStep={currentDemoStep}
          highlightedSectionId={highlightedSectionId}
          busy={busy}
          generatingType={generatingType}
          resourceJobSnapshot={resourceJobSnapshot}
          activeSessionId={activeSessionId}
          primaryResourceAction={primaryResourceAction}
          currentArtifacts={currentArtifacts}
          adaptiveReason={adaptiveGuideStrategy.reasons[0]?.detail}
          saveNotebookId={saveNotebookId}
          savingArtifact={mutations.saveArtifact.isPending}
          quizSubmitting={mutations.submitQuiz.isPending}
          onGenerateResource={(type, taskId, prompt) => void generateResource(type, taskId, prompt)}
          onOpenCompleteTask={() => setGuideSubPage("completeTask")}
          onOpenResourceChoice={() => setGuideSubPage("resourceChoice")}
          onSaveArtifact={(artifact) => void saveArtifact(artifact)}
          onSubmitQuiz={(artifact, answers) => void submitQuizArtifact(artifact, answers)}
        />
      </Suspense>
    </GuideStepFrame>
  );
}

function GuideStageLoading({ label }: { label: string }) {
  return (
    <section className="grid h-full place-items-center rounded-lg border border-line bg-white/90 p-4">
      <div className="text-center">
        <p className="text-sm font-semibold text-ink">{label}</p>
        <span className="mx-auto mt-3 block h-2.5 w-32 rounded bg-slate-100" />
      </div>
    </section>
  );
}
