import { lazy, Suspense } from "react";

import { GuideSubPageFrame } from "./GuideSubPageFrame";
import type { useGuideActions } from "./useGuideActions";
import type { useGuideDerivedState } from "./useGuideDerivedState";
import type { useGuidePageState } from "./useGuidePageState";
import type { useGuideRuntimeData } from "./useGuideRuntimeData";

const GuideCoursePackagePanel = lazy(() =>
  import("./GuideCoursePackagePanel").then((module) => ({ default: module.GuideCoursePackagePanel })),
);
const GuideMainStagePage = lazy(() =>
  import("./GuideMainStagePage").then((module) => ({ default: module.GuideMainStagePage })),
);
const GuideResourceChoicePage = lazy(() =>
  import("./GuideResourceChoicePage").then((module) => ({ default: module.GuideResourceChoicePage })),
);
const GuideRouteMapPage = lazy(() =>
  import("./GuideRouteMapPage").then((module) => ({ default: module.GuideRouteMapPage })),
);
const GuideSetupPage = lazy(() => import("./GuideSetupPage").then((module) => ({ default: module.GuideSetupPage })));
const GuideTaskCompletionPanel = lazy(() =>
  import("./GuideTaskCompletionPanel").then((module) => ({ default: module.GuideTaskCompletionPanel })),
);

type GuideWorkspaceRouterProps = {
  actions: ReturnType<typeof useGuideActions>;
  derived: ReturnType<typeof useGuideDerivedState>;
  highlightedSectionId: string | null;
  onContinueAfterFeedback: () => void;
  runtime: ReturnType<typeof useGuideRuntimeData>;
  scrollToGuideSection: (sectionId: string) => void;
  state: ReturnType<typeof useGuidePageState>;
};

export function GuideWorkspaceRouter({
  actions,
  derived,
  highlightedSectionId,
  onContinueAfterFeedback,
  runtime,
  scrollToGuideSection,
  state,
}: GuideWorkspaceRouterProps) {
  const {
    activeSessionId,
    coursePackage,
    mutations,
    notebooks,
    referenceNotebook,
    session,
    studyPlan,
    templates,
  } = runtime;
  const {
    courseTemplateId,
    generatingType,
    goal,
    guideSubPage,
    horizon,
    learningFeedback,
    level,
    referenceNotebookId,
    reflection,
    saveNotebookId,
    score,
    selectedRecordIds,
    sourceAction,
    timeBudget,
    updateGoal,
    weakPoints,
    resetReferenceNotebook,
    setGuideSubPage,
    setHorizon,
    setLevel,
    setReflection,
    setScore,
    setTimeBudget,
    setWeakPoints,
    toggleReferenceRecord,
  } = state;
  const {
    courseMetadata,
    courseTemplates,
    currentDemoStep,
    currentTask,
    nodes,
    referenceRecords,
    resourceActions,
    selectedTemplate,
    tasks,
  } = derived;
  const {
    busy,
    completeCurrentTask,
    createSession,
    downloadCoursePackage,
    generateResource,
    saveCoursePackage,
    selectCourseTemplate,
  } = actions;

  if (guideSubPage === "setup") {
    return (
      <Suspense fallback={<GuideWorkspaceLoading />}>
        <GuideSetupPage
          highlightedSectionId={highlightedSectionId}
          sourceAction={sourceAction}
          goal={goal}
          courseTemplateId={courseTemplateId}
          courseTemplates={courseTemplates}
          selectedTemplate={selectedTemplate}
          templatesLoading={templates.isFetching}
          level={level}
          timeBudget={timeBudget}
          horizon={horizon}
          weakPoints={weakPoints}
          notebooks={notebooks.data ?? []}
          referenceNotebookId={referenceNotebookId}
          referenceRecords={referenceRecords}
          selectedRecordIds={selectedRecordIds}
          referenceLoading={referenceNotebook.isFetching}
          creating={mutations.create.isPending}
          onBack={() => setGuideSubPage("main")}
          onSubmit={createSession}
          onGoalChange={updateGoal}
          onCourseTemplateChange={selectCourseTemplate}
          onLevelChange={setLevel}
          onTimeBudgetChange={setTimeBudget}
          onHorizonChange={setHorizon}
          onWeakPointsChange={setWeakPoints}
          onReferenceNotebookChange={resetReferenceNotebook}
          onToggleRecord={toggleReferenceRecord}
        />
      </Suspense>
    );
  }

  if (guideSubPage === "completeTask" && currentTask) {
    return (
      <GuideSubPageFrame
        eyebrow="提交学习记录"
        title="完成当前任务"
        description="写下掌握评分和一句话反思，系统会据此给出下一步反馈。"
        onBack={() => setGuideSubPage("main")}
      >
        <Suspense fallback={<GuideInnerLoading />}>
          <GuideTaskCompletionPanel
            currentTask={currentTask}
            currentDemoStep={currentDemoStep}
            highlightedSectionId={highlightedSectionId}
            score={score}
            reflection={reflection}
            learningFeedback={learningFeedback}
            busy={busy}
            activeSessionId={activeSessionId}
            completing={mutations.completeTask.isPending}
            onScoreChange={setScore}
            onReflectionChange={setReflection}
            onCompleteTask={() => void completeCurrentTask()}
          />
        </Suspense>
      </GuideSubPageFrame>
    );
  }

  if (guideSubPage === "resourceChoice" && currentTask) {
    return (
      <Suspense fallback={<GuideWorkspaceLoading />}>
        <GuideResourceChoicePage
          currentTask={currentTask}
          resourceActions={resourceActions}
          activeSessionId={activeSessionId}
          busy={busy}
          generatingType={generatingType}
          onBack={() => setGuideSubPage("main")}
          onGenerateResource={(type) => {
            setGuideSubPage("main");
            void generateResource(type);
          }}
        />
      </Suspense>
    );
  }

  if (guideSubPage === "routeMap" && session) {
    return (
      <Suspense fallback={<GuideWorkspaceLoading />}>
        <GuideRouteMapPage
          plan={studyPlan.data ?? null}
          loading={studyPlan.isFetching}
          metadata={courseMetadata}
          highlightedSectionId={highlightedSectionId}
          nodes={nodes}
          mastery={session.mastery ?? {}}
          tasks={tasks}
          currentTask={currentTask}
          onBack={() => setGuideSubPage("main")}
        />
      </Suspense>
    );
  }

  if (guideSubPage === "coursePackage" && session) {
    return (
      <GuideSubPageFrame
        eyebrow="学习产出"
        title="课程成果包"
        description="把本轮学习整理成可以保存和复盘的成果。"
        onBack={() => setGuideSubPage("main")}
      >
        <Suspense fallback={<GuideInnerLoading />}>
          <GuideCoursePackagePanel
            coursePackage={coursePackage.data ?? null}
            loading={coursePackage.isFetching}
            canSave={Boolean(activeSessionId && saveNotebookId)}
            saving={mutations.saveCoursePackage.isPending}
            onSave={() => void saveCoursePackage()}
            canExport={Boolean(coursePackage.data?.markdown)}
            onExport={downloadCoursePackage}
          />
        </Suspense>
      </GuideSubPageFrame>
    );
  }

  if (guideSubPage !== "main") return null;

  return (
    <Suspense fallback={<GuideWorkspaceLoading />}>
      <GuideMainStagePage
        actions={actions}
        derived={derived}
        highlightedSectionId={highlightedSectionId}
        onContinueAfterFeedback={onContinueAfterFeedback}
        runtime={runtime}
        scrollToGuideSection={scrollToGuideSection}
        state={state}
      />
    </Suspense>
  );
}

function GuideWorkspaceLoading() {
  return (
    <section className="rounded-lg border border-line bg-white/90 p-5">
      <p className="text-sm font-semibold text-ink">正在准备导学工作区</p>
      <div className="mt-4 space-y-3">
        <span className="block h-3 w-48 max-w-full rounded bg-slate-100" />
        <span className="block h-16 rounded bg-slate-100/80" />
        <span className="block h-16 rounded bg-slate-100/60" />
      </div>
    </section>
  );
}

function GuideInnerLoading() {
  return (
    <div className="space-y-3 py-1">
      <span className="block h-3 w-40 max-w-full rounded bg-slate-100" />
      <span className="block h-14 rounded bg-slate-100/80" />
      <span className="block h-14 rounded bg-slate-100/60" />
    </div>
  );
}
