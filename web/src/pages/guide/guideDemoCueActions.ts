import type { Dispatch, SetStateAction } from "react";

import type { GuideV2ResourceType, GuideV2Task } from "@/lib/types";
import type { DemoRecordingCue } from "./GuideDemoCards";
import type { GuideSubPage } from "./guideLearningStrategy";
import { readString } from "./guideDataUtils";
import { normalizeResourceType } from "./guideResourceUtils";

export function buildGuideDemoCueAction({
  currentDemoStep,
  currentTask,
  demoRecordingCue,
  generateResource,
  scrollToGuideSection,
  setGuideSubPage,
}: {
  currentDemoStep: Record<string, unknown> | null;
  currentTask: GuideV2Task | null;
  demoRecordingCue: DemoRecordingCue | null;
  generateResource: (type: GuideV2ResourceType, targetTaskId?: string, promptOverride?: string) => Promise<void>;
  scrollToGuideSection: (sectionId: string) => void;
  setGuideSubPage: Dispatch<SetStateAction<GuideSubPage>>;
}) {
  return () => {
    if (!demoRecordingCue || demoRecordingCue.action === "none") return;
    if (demoRecordingCue.action === "generate_current_seed") {
      const prompt = currentDemoStep ? readString(currentDemoStep, "prompt") : "";
      const resourceType = currentDemoStep ? normalizeResourceType(readString(currentDemoStep, "resource_type")) : null;
      if (currentTask && prompt && resourceType) {
        void generateResource(resourceType, currentTask.task_id, prompt);
      }
      return;
    }
    if (demoRecordingCue.action === "open_complete_task") {
      setGuideSubPage("completeTask");
      return;
    }
    if (demoRecordingCue.action === "open_route_map") {
      setGuideSubPage("routeMap");
      scrollToGuideSection("guide-route-map-section");
      return;
    }
    if (demoRecordingCue.action === "open_course_package") {
      setGuideSubPage("coursePackage");
    }
  };
}
