import { createElement } from "react";
import { ListChecks, Map, Video, Volume2 } from "lucide-react";

import type { GuideV2ResourceType } from "@/lib/types";

export type GuideActionResourceType = "visual" | "quiz" | "video" | "audio" | "external_video";

const guideActionResourceTypes: GuideActionResourceType[] = ["visual", "audio", "external_video", "quiz", "video"];

export function resourceLabel(type: string) {
  const labels: Record<string, string> = {
    visual: "图解",
    video: "短视频",
    audio: "语音讲解",
    external_video: "精选视频",
    quiz: "练习",
  };
  return labels[type] || type || "资源";
}

export function normalizeGuideActionResourceType(type: GuideV2ResourceType): GuideActionResourceType {
  if (type === "quiz" || type === "video" || type === "audio" || type === "external_video") return type;
  return "visual";
}

export function buildGuideResourceActions(
  recommended: GuideV2ResourceType,
  copy: Record<GuideActionResourceType, string>,
) {
  const primary = normalizeGuideActionResourceType(recommended);
  return [primary, ...guideActionResourceTypes.filter((type) => type !== primary)].map((type) => ({
    type,
    label: copy[type],
  }));
}

export function guideResourceIcon(type: GuideActionResourceType, size = 16) {
  if (type === "quiz") return createElement(ListChecks, { size });
  if (type === "video") return createElement(Video, { size });
  if (type === "audio") return createElement(Volume2, { size });
  if (type === "external_video") return createElement(Video, { size });
  return createElement(Map, { size });
}

export function guideResourceDescription(type: GuideActionResourceType) {
  const descriptions: Record<GuideActionResourceType, string> = {
    visual: "把概念关系画出来，适合先建立直觉。",
    quiz: "用选择、判断、填空和简答验证理解，做完可获得反馈。",
    video: "生成一段默认带旁白的短视频讲解，适合按步骤跟着看。",
    audio: "生成一段可直接播放的语音讲解，适合先听一遍再继续。",
    external_video: "从公开网络里找少量讲解视频，看完后回到导学提交反思。",
  };
  return descriptions[type];
}

export function buildGuideResourceButtonCopy(recommended: GuideV2ResourceType, trendLabel: string) {
  const copy = {
    visual: "看图解",
    quiz: "做练习",
    video: "看讲解视频",
    audio: "听讲解",
    external_video: "找精选视频",
  };

  if (trendLabel.includes("修正路径")) {
    copy.visual = recommended === "visual" ? "先看补救图解" : "看补救图解";
    copy.quiz = recommended === "quiz" ? "先做复测题" : "做复测题";
    copy.video = recommended === "video" ? "看纠错讲解" : "看纠错讲解";
    copy.audio = recommended === "audio" ? "先听纠错讲解" : "听纠错讲解";
    copy.external_video = recommended === "external_video" ? "先找讲解视频" : "找讲解视频";
    return copy;
  }

  if (trendLabel.includes("变稳")) {
    copy.visual = recommended === "visual" ? "先看关键图解" : "看关键图解";
    copy.quiz = recommended === "quiz" ? "直接做验证题" : "做验证题";
    copy.video = recommended === "video" ? "看步骤串讲" : "看步骤串讲";
    copy.audio = recommended === "audio" ? "先听步骤讲解" : "听步骤讲解";
    copy.external_video = recommended === "external_video" ? "找参考视频" : "找参考视频";
    return copy;
  }

  if (trendLabel.includes("提速")) {
    copy.visual = recommended === "visual" ? "快速看图解" : "看图解";
    copy.quiz = recommended === "quiz" ? "直接做这组题" : "做这组题";
    copy.video = recommended === "video" ? "快速看讲解视频" : "看讲解视频";
    copy.audio = recommended === "audio" ? "快速听讲解" : "听讲解";
    copy.external_video = recommended === "external_video" ? "快速找视频" : "找精选视频";
    return copy;
  }

  if (trendLabel.includes("聚焦补强")) {
    copy.visual = recommended === "visual" ? "先看这张图解" : "看这张图解";
    copy.quiz = recommended === "quiz" ? "做这组补强题" : "做补强题";
    copy.video = recommended === "video" ? "看补强短视频" : "看补强短视频";
    copy.audio = recommended === "audio" ? "先听补强讲解" : "听补强讲解";
    copy.external_video = recommended === "external_video" ? "先找公开视频" : "找公开视频";
    return copy;
  }

  if (recommended === "visual") copy.visual = "先看这张图解";
  if (recommended === "quiz") copy.quiz = "先做这组题";
  if (recommended === "video") copy.video = "先看这段短视频";
  if (recommended === "audio") copy.audio = "先听这段讲解";
  if (recommended === "external_video") copy.external_video = "先找精选视频";
  return copy;
}

export function isResearchResourceType(type: string) {
  const value = String(type || "").toLowerCase();
  return value === "research" || value === "material" || value === "materials" || value.includes("资料");
}

export function normalizeResourceType(type: unknown): GuideActionResourceType {
  if (type === "visual" || type === "video" || type === "audio" || type === "quiz" || type === "external_video") {
    return type;
  }
  return "visual";
}
