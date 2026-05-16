import type { Dispatch, SetStateAction } from "react";

import type { useGuideV2Mutations } from "@/hooks/useApiQueries";
import type { GuideV2LearningFeedback, GuideV2ResourceType, GuideV2Task } from "@/lib/types";

type GuideV2Mutations = ReturnType<typeof useGuideV2Mutations>;

export function buildGuideResourceGenerationActions({
  activeSessionId,
  currentTask,
  mutations,
  scrollToGuideSection,
  setGeneratingType,
  setPrescriptionFeedback,
  setPrescriptionTaskId,
  setResourceJobId,
  setSaveMessage,
}: {
  activeSessionId: string | null;
  currentTask: GuideV2Task | null;
  mutations: GuideV2Mutations;
  scrollToGuideSection: (sectionId: string) => void;
  setGeneratingType: Dispatch<SetStateAction<GuideV2ResourceType | null>>;
  setPrescriptionFeedback: Dispatch<SetStateAction<GuideV2LearningFeedback | null>>;
  setPrescriptionTaskId: Dispatch<SetStateAction<string>>;
  setResourceJobId: Dispatch<SetStateAction<string | null>>;
  setSaveMessage: Dispatch<SetStateAction<string>>;
}) {
  const generateResource = async (
    type: GuideV2ResourceType,
    targetTaskId = currentTask?.task_id || "",
    promptOverride = "",
  ) => {
    if (!activeSessionId || !targetTaskId) return;
    setPrescriptionTaskId(targetTaskId);
    setPrescriptionFeedback(null);
    setGeneratingType(type);
    try {
      const job = await mutations.startResourceJob.mutateAsync({
        sessionId: activeSessionId,
        taskId: targetTaskId,
        resourceType: type,
        prompt: promptOverride,
        quality: type === "video" ? "low" : "medium",
      });
      setResourceJobId(job.task_id);
      window.setTimeout(() => scrollToGuideSection("guide-prescription-results-section"), 160);
    } catch (error) {
      setGeneratingType(null);
      setSaveMessage(error instanceof Error ? error.message : "资源生成任务启动失败。");
    }
  };

  return { generateResource };
}
