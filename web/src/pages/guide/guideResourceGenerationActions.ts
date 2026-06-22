import type { Dispatch, SetStateAction } from "react";

import type { useGuideV2Mutations } from "@/hooks/useApiQueries";
import type { GuideResourceJobSnapshot, GuideV2LearningFeedback, GuideV2ResourceType, GuideV2Task } from "@/lib/types";

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
  setResourceJobSnapshot,
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
  setResourceJobSnapshot: Dispatch<SetStateAction<GuideResourceJobSnapshot | null>>;
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
    setResourceJobSnapshot({
      stage: "queued",
      message: "学习包生成已排队。",
      resourceType: type,
      steps: [],
    });
    try {
      const job = await mutations.startResourceJob.mutateAsync({
        sessionId: activeSessionId,
        taskId: targetTaskId,
        resourceType: type,
        prompt: promptOverride,
        quality: "high",
      });
      setResourceJobId(job.task_id);
      setResourceJobSnapshot({
        jobId: job.task_id,
        stage: "queued",
        message: "学习包生成已排队。",
        resourceType: job.resource_type || type,
        steps: job.agent_steps ?? [],
      });
      const resultsSectionId =
        targetTaskId === currentTask?.task_id ? "guide-resource-results-section" : "guide-prescription-results-section";
      window.setTimeout(() => scrollToGuideSection(resultsSectionId), 160);
    } catch (error) {
      setGeneratingType(null);
      setResourceJobSnapshot({
        stage: "failed",
        message: "资源生成任务启动失败。",
        resourceType: type,
        error: error instanceof Error ? error.message : "资源生成任务启动失败。",
      });
      setSaveMessage(error instanceof Error ? error.message : "资源生成任务启动失败。");
    }
  };

  return { generateResource };
}
