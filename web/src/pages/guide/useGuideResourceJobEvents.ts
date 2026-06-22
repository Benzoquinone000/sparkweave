import { useEffect } from "react";
import type { Dispatch, SetStateAction } from "react";

import { openGuideV2ResourceJobEvents } from "@/lib/api";
import type { GuideResourceAgentStep, GuideResourceJobSnapshot, GuideV2ResourceType } from "@/lib/types";

type UseGuideResourceJobEventsInput = {
  resourceJobId: string | null;
  refetchCoursePackage: () => unknown;
  refetchDetail: () => unknown;
  refetchLearningReport: () => unknown;
  refetchSessions: () => unknown;
  refetchStudyPlan: () => unknown;
  setGeneratingType: Dispatch<SetStateAction<GuideV2ResourceType | null>>;
  setResourceJobId: Dispatch<SetStateAction<string | null>>;
  setResourceJobSnapshot: Dispatch<SetStateAction<GuideResourceJobSnapshot | null>>;
  setSaveMessage: Dispatch<SetStateAction<string>>;
};

export function useGuideResourceJobEvents({
  resourceJobId,
  refetchCoursePackage,
  refetchDetail,
  refetchLearningReport,
  refetchSessions,
  refetchStudyPlan,
  setGeneratingType,
  setResourceJobId,
  setResourceJobSnapshot,
  setSaveMessage,
}: UseGuideResourceJobEventsInput) {
  useEffect(() => {
    if (!resourceJobId) return undefined;

    const source = openGuideV2ResourceJobEvents(resourceJobId);
    const refreshPartialResult = () => {
      void refetchDetail();
      void refetchStudyPlan();
      void refetchSessions();
    };
    const refreshCompletedResult = () => {
      void refetchDetail();
      void refetchStudyPlan();
      void refetchLearningReport();
      void refetchCoursePackage();
      void refetchSessions();
    };
    const updateSnapshot = (event: Event, fallbackStage: string) => {
      const payload = parseResourceJobPayload(readEventData(event));
      setResourceJobSnapshot((current) => ({
        jobId: payload.task_id || current?.jobId || resourceJobId,
        stage: payload.stage || payload.status || fallbackStage,
        message: payload.message || payload.detail || current?.message || "",
        resourceType: payload.resource_type || current?.resourceType,
        steps: payload.agent_steps || current?.steps || [],
        error: payload.error || current?.error,
      }));
    };
    const finishJob = () => {
      setGeneratingType(null);
      setResourceJobId(null);
      source.close();
    };

    source.addEventListener("status", (event) => updateSnapshot(event, "running"));
    source.addEventListener("trace", (event) => updateSnapshot(event, "running"));
    source.addEventListener("result", (event) => {
      updateSnapshot(event, "result");
      refreshPartialResult();
    });
    source.addEventListener("complete", () => {
      setResourceJobSnapshot((current) =>
        current
          ? {
              ...current,
              stage: "completed",
              message: "学习包已生成。",
              steps: current.steps?.map((step) => ({ ...step, status: "done" })) ?? [],
            }
          : current,
      );
      refreshCompletedResult();
      finishJob();
    });
    source.addEventListener("failed", (event) => {
      const payload = parseResourceJobPayload(readEventData(event));
      setResourceJobSnapshot((current) => ({
        jobId: current?.jobId || resourceJobId,
        stage: "failed",
        message: payload.detail || payload.message || "资源生成失败。",
        resourceType: payload.resource_type || current?.resourceType,
        steps: markActiveStepFailed(current?.steps),
        error: payload.detail || payload.error || "资源生成失败。",
      }));
      finishJob();
    });
    source.onerror = () => {
      setSaveMessage("资源生成连接暂时不可用，请稍后刷新页面查看结果。");
      setResourceJobSnapshot((current) =>
        current
          ? {
              ...current,
              stage: "failed",
              message: "资源生成连接暂时不可用，请稍后刷新页面查看结果。",
              steps: markActiveStepFailed(current.steps),
            }
          : current,
      );
      finishJob();
    };

    return () => source.close();
  }, [
    refetchCoursePackage,
    refetchDetail,
    refetchLearningReport,
    refetchSessions,
    refetchStudyPlan,
    resourceJobId,
    setGeneratingType,
    setResourceJobId,
    setResourceJobSnapshot,
    setSaveMessage,
  ]);
}

function readEventData(event: Event) {
  return event instanceof MessageEvent ? String(event.data || "") : "";
}

function parseResourceJobPayload(value: string): Record<string, unknown> & {
  agent_steps?: GuideResourceAgentStep[];
  detail?: string;
  error?: string;
  message?: string;
  resource_type?: string;
  stage?: string;
  status?: string;
  task_id?: string;
} {
  try {
    const parsed = JSON.parse(value) as Record<string, unknown>;
    return {
      ...parsed,
      agent_steps: Array.isArray(parsed.agent_steps) ? (parsed.agent_steps as GuideResourceAgentStep[]) : undefined,
    };
  } catch {
    return {};
  }
}

function markActiveStepFailed(steps: GuideResourceAgentStep[] | undefined) {
  if (!steps?.length) return [];
  const activeIndex = steps.findIndex((step) => step.status === "active");
  if (activeIndex < 0) return steps;
  return steps.map((step, index) => (index === activeIndex ? { ...step, status: "failed" } : step));
}
