import { useEffect, useMemo } from "react";

import type { GuideSubPage } from "./guideLearningStrategy";
import { buildGuideEffectActionSeed } from "./guideEffectActionSeed";

type GuideUrlSeedControls = {
  setGoal: (value: string) => void;
  setGoalTouched: (value: boolean) => void;
  setTimeBudget: (value: string) => void;
  setWeakPoints: (value: string) => void;
  setForceNewSession: (value: boolean) => void;
  setSelectedSessionId: (value: string | null) => void;
  setGuideSubPage: (value: GuideSubPage) => void;
  setSourceAction: (value: Record<string, unknown> | null) => void;
  setHighlightedSectionId: (value: string | null) => void;
};

export function useGuideUrlSeed({
  setGoal,
  setGoalTouched,
  setTimeBudget,
  setWeakPoints,
  setForceNewSession,
  setSelectedSessionId,
  setGuideSubPage,
  setSourceAction,
  setHighlightedSectionId,
}: GuideUrlSeedControls) {
  const hasUrlGuideSeed = useMemo(() => {
    if (typeof window === "undefined") return false;
    const search = new URLSearchParams(window.location.search);
    return Boolean(search.get("prompt") || search.get("effect_action") || search.get("new") === "1");
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    const timer = window.setTimeout(() => {
      const search = new URLSearchParams(window.location.search);
      const prompt = search.get("prompt")?.trim();
      const effectAction = search.get("effect_action")?.trim() || "";
      const actionTitle = search.get("action_title")?.trim() || "";
      const rawSourceLabel = search.get("source_label")?.trim() || "";
      const rawEstimatedMinutes = Number(search.get("estimated_minutes") || "") || undefined;
      const effectSeed = buildGuideEffectActionSeed({
        effectAction,
        prompt: prompt || "",
        actionTitle,
        sourceLabel: rawSourceLabel,
        estimatedMinutes: rawEstimatedMinutes,
      });
      const guidePrompt = prompt || effectSeed.prompt;
      const estimatedMinutes = rawEstimatedMinutes || effectSeed.estimatedMinutes;
      const sourceLabel = rawSourceLabel || effectSeed.sourceLabel;
      const actionKind = search.get("action_kind")?.trim() || effectSeed.kind || "next_action";
      const targetSection = search.get("target_section")?.trim() || effectSeed.targetSection || "";
      if (guidePrompt) {
        setGoal(guidePrompt);
        setGoalTouched(true);
      }
      if (estimatedMinutes) {
        setTimeBudget(String(Math.round(estimatedMinutes)));
      }
      if ((actionKind === "weak_point" || effectAction) && sourceLabel) {
        setWeakPoints(sourceLabel);
      }
      if (guidePrompt || effectAction || search.get("new") === "1") {
        setForceNewSession(true);
        setSelectedSessionId(null);
        setGuideSubPage(targetSection === "guide-setup-section" ? "setup" : "main");
        setSourceAction({
          source: effectAction ? "learning_effect" : "learner_profile",
          kind: actionKind,
          title: actionTitle || effectSeed.title,
          source_type: search.get("source_type") || (effectAction ? "learning_effect_next_action" : ""),
          source_label: sourceLabel,
          confidence: Number(search.get("confidence") || "") || undefined,
          estimated_minutes: estimatedMinutes,
          suggested_prompt: guidePrompt || "",
          href: "/guide",
        });
      }
      if (targetSection) {
        setHighlightedSectionId(targetSection);
        window.setTimeout(() => {
          const element = document.getElementById(targetSection);
          if (!element) return;
          element.scrollIntoView({ behavior: "smooth", block: "start" });
        }, 180);
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, [
    setForceNewSession,
    setGoal,
    setGoalTouched,
    setGuideSubPage,
    setHighlightedSectionId,
    setSelectedSessionId,
    setSourceAction,
    setTimeBudget,
    setWeakPoints,
  ]);

  return hasUrlGuideSeed;
}
