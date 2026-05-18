import { useEffect } from "react";
import type { Dispatch, SetStateAction } from "react";

import type { GuideV2LearningFeedback } from "@/lib/types";
import type { GuideStage, GuideSubPage } from "./guideLearningStrategy";

type GuideProfileNextAction = {
  estimated_minutes?: number;
  source_label?: string;
  source_type?: string;
} | null;

export function useGuideLifecycleEffects({
  activeSessionId,
  guideStage,
  hasUrlGuideSeed,
  goal,
  goalTouched,
  profileNextAction,
  profileSuggestedPrompt,
  weakPoints,
  notebooks,
  saveNotebookId,
  setGoal,
  setTimeBudget,
  setWeakPoints,
  setLearningFeedback,
  setPrescriptionFeedback,
  setGuideSubPage,
  setSaveNotebookId,
}: {
  activeSessionId: string | null;
  guideStage: GuideStage;
  hasUrlGuideSeed: boolean;
  goal: string;
  goalTouched: boolean;
  profileNextAction: GuideProfileNextAction;
  profileSuggestedPrompt: string;
  weakPoints: string;
  notebooks: Array<{ id: string }> | undefined;
  saveNotebookId: string;
  setGoal: Dispatch<SetStateAction<string>>;
  setTimeBudget: Dispatch<SetStateAction<string>>;
  setWeakPoints: Dispatch<SetStateAction<string>>;
  setLearningFeedback: Dispatch<SetStateAction<GuideV2LearningFeedback | null>>;
  setPrescriptionFeedback: Dispatch<SetStateAction<GuideV2LearningFeedback | null>>;
  setGuideSubPage: Dispatch<SetStateAction<GuideSubPage>>;
  setSaveNotebookId: Dispatch<SetStateAction<string>>;
}) {
  useEffect(() => {
    if (hasUrlGuideSeed || goalTouched || goal.trim() || !profileSuggestedPrompt) return undefined;
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
  }, [goal, goalTouched, hasUrlGuideSeed, profileNextAction, profileSuggestedPrompt, setGoal, setTimeBudget, setWeakPoints, weakPoints]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setLearningFeedback(null);
      setPrescriptionFeedback(null);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [activeSessionId, setLearningFeedback, setPrescriptionFeedback]);

  useEffect(() => {
    const timer = window.setTimeout(() => setGuideSubPage("main"), 0);
    return () => window.clearTimeout(timer);
  }, [activeSessionId, guideStage, setGuideSubPage]);

  useEffect(() => {
    if (!saveNotebookId && notebooks?.[0]?.id) {
      const timer = window.setTimeout(() => setSaveNotebookId(notebooks[0].id), 0);
      return () => window.clearTimeout(timer);
    }
    return undefined;
  }, [notebooks, saveNotebookId, setSaveNotebookId]);
}
