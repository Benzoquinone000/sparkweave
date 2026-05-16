import { useEffect } from "react";
import type { Dispatch, SetStateAction } from "react";

import { openGuideV2ResourceJobEvents } from "@/lib/api";
import type { GuideV2ResourceType } from "@/lib/types";

type UseGuideResourceJobEventsInput = {
  resourceJobId: string | null;
  refetchCoursePackage: () => unknown;
  refetchDetail: () => unknown;
  refetchLearningReport: () => unknown;
  refetchSessions: () => unknown;
  refetchStudyPlan: () => unknown;
  setGeneratingType: Dispatch<SetStateAction<GuideV2ResourceType | null>>;
  setResourceJobId: Dispatch<SetStateAction<string | null>>;
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
    const finishJob = () => {
      setGeneratingType(null);
      setResourceJobId(null);
      source.close();
    };

    source.addEventListener("status", () => undefined);
    source.addEventListener("trace", () => undefined);
    source.addEventListener("result", refreshPartialResult);
    source.addEventListener("complete", () => {
      refreshCompletedResult();
      finishJob();
    });
    source.addEventListener("failed", finishJob);
    source.onerror = () => {
      setSaveMessage("资源生成连接暂时不可用，请稍后刷新页面查看结果。");
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
    setSaveMessage,
  ]);
}
