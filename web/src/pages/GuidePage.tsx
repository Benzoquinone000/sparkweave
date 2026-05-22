import { motion } from "framer-motion";
import { lazy, Suspense, useState } from "react";

import { GuideHero } from "./guide/GuideHero";
import { GuideWorkspaceRouter } from "./guide/GuideWorkspaceRouter";
import { useGuideActions } from "./guide/useGuideActions";
import { useGuideDerivedState } from "./guide/useGuideDerivedState";
import { useGuideLifecycleEffects } from "./guide/useGuideLifecycleEffects";
import { useGuidePageState } from "./guide/useGuidePageState";
import { useGuideRuntimeData } from "./guide/useGuideRuntimeData";
import { useGuideSectionHighlight } from "./guide/useGuideSectionHighlight";
import { useGuideUrlSeed } from "./guide/useGuideUrlSeed";

const DemoRecordingCueCard = lazy(() =>
  import("./guide/GuideDemoCards").then((module) => ({ default: module.DemoRecordingCueCard })),
);
const GuideSupportDrawer = lazy(() =>
  import("./guide/GuideSupportDrawer").then((module) => ({ default: module.GuideSupportDrawer })),
);

export function GuidePage() {
  const guideState = useGuidePageState();
  const {
    courseTemplateId,
    forceNewSession,
    generatingType,
    goal,
    goalTouched,
    guideSubPage,
    learningFeedback,
    prescriptionTaskId,
    referenceNotebookId,
    resetForNewRoute,
    saveMessage,
    saveNotebookId,
    selectExistingRoute,
    selectedRecordIds,
    selectedSessionId,
    supportOpen,
    weakPoints,
    setForceNewSession,
    setGoal,
    setGoalTouched,
    setGuideSubPage,
    setLearningFeedback,
    setPrescriptionFeedback,
    setSaveNotebookId,
    setSelectedSessionId,
    setSourceAction,
    setSupportOpen,
    setTimeBudget,
    setWeakPoints,
  } = guideState;
  const [supportDrawerMounted, setSupportDrawerMounted] = useState(false);
  const { highlightedSectionId, setHighlightedSectionId, scrollToGuideSection } = useGuideSectionHighlight();
  const hasUrlGuideSeed = useGuideUrlSeed({
    setGoal,
    setGoalTouched,
    setTimeBudget,
    setWeakPoints,
    setForceNewSession,
    setSelectedSessionId,
    setGuideSubPage,
    setSourceAction,
    setHighlightedSectionId,
  });

  const guideRuntime = useGuideRuntimeData({
    forceNewSession,
    referenceNotebookId,
    selectedSessionId,
  });
  const {
    activeSessionId,
    diagnostic,
    learnerProfile,
    learningReport,
    mutations,
    notebooks,
    referenceNotebook,
    session,
    sessions,
    templates,
  } = guideRuntime;
  const guideDerived = useGuideDerivedState({
    courseTemplateId,
    courseTemplatesData: templates.data,
    diagnosticStatus: diagnostic.data?.status,
    generatingType,
    guideSubPage,
    learnerProfile: learnerProfile.data,
    learningFeedback,
    learningReport: learningReport.data,
    prescriptionTaskId,
    referenceNotebookId,
    referenceNotebookRecords: referenceNotebook.data?.records,
    selectedRecordIds,
    session,
  });
  const {
    currentTask,
    demoRecordingCue,
    guideStage,
    isDemoSeedSession,
    primaryActionLabel,
    profileNextAction,
    profileSuggestedPrompt,
    routeUsesUnifiedProfile,
    stageMessage,
  } = guideDerived;
  useGuideLifecycleEffects({
    activeSessionId,
    guideStage,
    hasUrlGuideSeed,
    goal,
    goalTouched,
    profileNextAction,
    profileSuggestedPrompt,
    weakPoints,
    notebooks: notebooks.data,
    saveNotebookId,
    setGoal,
    setTimeBudget,
    setWeakPoints,
    setLearningFeedback,
    setPrescriptionFeedback,
    setGuideSubPage,
    setSaveNotebookId,
  });

  const guideActions = useGuideActions({
    derived: guideDerived,
    runtime: guideRuntime,
    scrollToGuideSection,
    state: guideState,
  });
  const {
    busy,
    deleteActiveSession,
    runDemoRecordingCue,
  } = guideActions;

  const openSupportDrawer = () => {
    setSupportDrawerMounted(true);
    setSupportOpen(true);
  };

  return (
    <div className="dt-dynamic-page h-full overflow-y-auto px-3.5 py-3.5 pb-20 lg:px-4 lg:pb-5">
      <div className="mx-auto max-w-[940px] space-y-3.5">
        <GuideHero
          primaryActionLabel={primaryActionLabel}
          stageMessage={stageMessage}
          guideStage={guideStage}
          currentTask={currentTask}
          onEnterCurrentStep={() => scrollToGuideSection(currentTask ? "guide-current-task-section" : "guide-create-section")}
          onOpenSupport={openSupportDrawer}
        />

        {saveMessage ? (
          <motion.div
            className="rounded-lg border border-line bg-tint-lavender px-3 py-2.5 text-xs leading-5 text-brand-purple-800"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.16 }}
          >
            {saveMessage}
          </motion.div>
        ) : null}

        {isDemoSeedSession && demoRecordingCue ? (
          <Suspense fallback={<GuideDemoCueLoading />}>
            <DemoRecordingCueCard
              cue={demoRecordingCue}
              busy={busy || Boolean(generatingType)}
              onAction={runDemoRecordingCue}
            />
          </Suspense>
        ) : null}

        <div className="grid gap-3.5">
          <main className="space-y-3.5">
            <GuideWorkspaceRouter
              actions={guideActions}
              derived={guideDerived}
              highlightedSectionId={highlightedSectionId}
              runtime={guideRuntime}
              scrollToGuideSection={scrollToGuideSection}
              state={guideState}
            />
          </main>

        </div>

        {supportDrawerMounted ? (
          <Suspense fallback={supportOpen ? <GuideSupportDrawerLoading onClose={() => setSupportOpen(false)} /> : null}>
            <GuideSupportDrawer
              open={supportOpen}
              currentTask={currentTask}
              routeUsesUnifiedProfile={routeUsesUnifiedProfile}
              sessions={sessions.data ?? []}
              activeSessionId={activeSessionId}
              busy={busy}
              onClose={() => setSupportOpen(false)}
              onNewRoute={resetForNewRoute}
              onSelectSession={selectExistingRoute}
              onRefreshRecommendations={() => activeSessionId && mutations.refreshRecommendations.mutate(activeSessionId)}
              onDeleteActiveSession={() => void deleteActiveSession()}
            />
          </Suspense>
        ) : null}
      </div>
    </div>
  );
}
function GuideDemoCueLoading() {
  return (
    <section className="dt-dynamic-panel rounded-lg border border-blue-100 bg-white p-3 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0 flex-1">
          <span className="block h-3 w-24 max-w-full rounded bg-slate-100" />
          <span className="mt-3 block h-4 w-56 max-w-full rounded bg-slate-100/80" />
          <span className="mt-2 block h-3 w-[min(520px,100%)] rounded bg-slate-100/70" />
        </div>
        <span className="h-9 w-24 rounded-lg bg-slate-100" />
      </div>
    </section>
  );
}
function GuideSupportDrawerLoading({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 bg-slate-900/25">
      <button
        type="button"
        className="absolute inset-0 cursor-default"
        aria-label="关闭路线面板"
        onClick={onClose}
      />
      <aside className="dt-dynamic-drawer absolute right-0 top-0 h-full w-full max-w-[380px] overflow-y-auto border-l border-line p-3 shadow-panel">
        <div className="dt-dynamic-panel rounded-lg border border-line bg-white p-3">
          <span className="block h-3 w-20 rounded bg-slate-100" />
          <span className="mt-3 block h-5 w-64 max-w-full rounded bg-slate-100/80" />
        </div>
        <div className="mt-3 space-y-3">
          <span className="dt-dynamic-panel block h-24 rounded-lg bg-white" />
          <span className="dt-dynamic-panel block h-32 rounded-lg bg-white" />
          <span className="dt-dynamic-panel block h-28 rounded-lg bg-white" />
        </div>
      </aside>
    </div>
  );
}
