import type { GuideV2LearningFeedback, GuideV2LearningReport, GuideV2ResourceType } from "@/lib/types";
import { DemoWrapUpCard } from "./GuideDemoCards";
import { GuideLearningFeedbackCard } from "./GuideLearningFeedbackPanel";

export function GuideFeedbackStagePanel({
  highlightedSectionId,
  feedback,
  learningEffectReport,
  disabled,
  profileRefreshing,
  demoEnabled,
  report,
  reportLoading,
  onGenerateResource,
  onOpenCurrentTask,
  onOpenRouteMap,
  onOpenCoursePackage,
}: {
  highlightedSectionId: string | null;
  feedback: GuideV2LearningFeedback | null;
  learningEffectReport?: GuideV2LearningReport["learning_effect_report"] | null;
  disabled: boolean;
  profileRefreshing: boolean;
  demoEnabled: boolean;
  report: GuideV2LearningReport | null;
  reportLoading: boolean;
  onGenerateResource: (type: GuideV2ResourceType, taskId: string, prompt: string) => void;
  onOpenCurrentTask: () => void;
  onOpenRouteMap: () => void;
  onOpenCoursePackage: () => void;
}) {
  return (
    <div
      id="guide-feedback-section"
      className={`rounded-lg transition-all duration-500 ${
        highlightedSectionId === "guide-feedback-section" ? "ring-2 ring-brand-purple-300 ring-offset-2 ring-offset-canvas" : ""
      }`}
    >
      <GuideLearningFeedbackCard
        feedback={feedback}
        learningEffectReport={learningEffectReport ?? null}
        disabled={disabled}
        profileRefreshing={profileRefreshing}
        onGenerateResource={onGenerateResource}
        onOpenCurrentTask={onOpenCurrentTask}
        onOpenRouteMap={onOpenRouteMap}
      />
      <DemoWrapUpCard
        enabled={demoEnabled}
        report={report}
        loading={reportLoading}
        onOpenCoursePackage={onOpenCoursePackage}
        onOpenRouteMap={onOpenRouteMap}
      />
    </div>
  );
}
