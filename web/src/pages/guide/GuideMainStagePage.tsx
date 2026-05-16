import { lazy, Suspense } from "react";

import type { useGuideActions } from "./useGuideActions";
import type { useGuideDerivedState } from "./useGuideDerivedState";
import type { useGuidePageState } from "./useGuidePageState";
import type { useGuideRuntimeData } from "./useGuideRuntimeData";

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
  runtime: ReturnType<typeof useGuideRuntimeData>;
  scrollToGuideSection: (sectionId: string) => void;
  state: ReturnType<typeof useGuidePageState>;
};

export function GuideMainStagePage({
  actions,
  derived,
  highlightedSectionId,
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

  return (
    <>
      {!session ? (
        <Suspense fallback={<GuideStageLoading label="正在准备导学路线创建" />}>
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
      ) : null}

      {session && guideStage === "diagnostic" ? (
        <Suspense fallback={<GuideStageLoading label="正在准备诊断题" />}>
          <GuideDiagnosticStagePanel
            highlightedSectionId={highlightedSectionId}
            diagnostic={diagnostic.data ?? null}
            loading={diagnostic.isFetching}
            submitting={mutations.submitDiagnostic.isPending}
            disabled={!activeSessionId || busy}
            onSubmit={(answers) => void submitDiagnostic(answers)}
          />
        </Suspense>
      ) : null}

      {session && guideStage === "feedback" ? (
        <Suspense fallback={<GuideStageLoading label="正在准备学习反馈" />}>
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
            onOpenCurrentTask={() => scrollToGuideSection("guide-current-task-section")}
            onOpenRouteMap={() => {
              setGuideSubPage("routeMap");
              scrollToGuideSection("guide-route-map-section");
            }}
            onOpenCoursePackage={() => setGuideSubPage("coursePackage")}
          />
        </Suspense>
      ) : null}

      {session && (guideStage === "learn" || guideStage === "feedback") ? (
        <Suspense fallback={<GuideStageLoading label="正在准备当前任务" />}>
          <GuideCurrentTaskPanel
            guideStage={guideStage}
            currentTask={currentTask}
            currentDemoStep={currentDemoStep}
            highlightedSectionId={highlightedSectionId}
            busy={busy}
            generatingType={generatingType}
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
      ) : null}

      {session && guideStage === "complete" ? (
        <Suspense fallback={<GuideStageLoading label="正在准备学习报告" />}>
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
      ) : null}

      {session ? (
        <button
          type="button"
          className="mx-auto flex min-h-10 items-center justify-center rounded-md px-3 text-sm font-medium text-slate-500 transition hover:bg-white hover:text-brand-purple"
          onClick={() => setGuideSubPage("routeMap")}
        >
          查看完整路线
        </button>
      ) : null}
    </>
  );
}

function GuideStageLoading({ label }: { label: string }) {
  return (
    <section className="rounded-lg border border-line bg-white/82 p-4">
      <p className="text-sm font-semibold text-ink">{label}</p>
      <div className="mt-3 space-y-2">
        <span className="block h-3 w-44 max-w-full rounded bg-slate-100" />
        <span className="block h-16 rounded bg-slate-100/80" />
        <span className="block h-16 rounded bg-slate-100/60" />
      </div>
    </section>
  );
}
