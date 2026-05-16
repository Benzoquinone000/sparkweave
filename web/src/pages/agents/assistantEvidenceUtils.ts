import type { LearningEffectReport } from "@/lib/types";
import { textFromRecord, unknownText } from "./assistantHistoryUtils";

export function assistantEvidenceRefs(report?: LearningEffectReport) {
  const timeline = report?.visualization?.evidence_timeline ?? [];
  const refs = report?.evidence_refs ?? [];
  const timelineItems = timeline.map((item, index) => ({
    id: `timeline-${item.id || index}`,
    title: item.label || item.source || "学习证据",
    detail: [item.detail, item.score === null || item.score === undefined ? "" : `${item.score} 分`].filter(Boolean).join(" · "),
  }));
  const refItems = refs.map((item, index) => ({
    id: `ref-${unknownText(item.id) || index}`,
    title: textFromRecord(item, ["title", "label", "source", "object_type"]) || "学习证据",
    detail: textFromRecord(item, ["summary", "detail", "resource_type", "verb"]) || "已写入学习效果评估。",
  }));
  return [...timelineItems, ...refItems].filter((item) => item.title || item.detail);
}
