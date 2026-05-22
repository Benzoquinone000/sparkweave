type TraceLabelItem = {
  label?: string;
  detail?: string;
};

const MEDIA_TRACE_LABELS: Record<string, string> = {
  画像智能体: "学习记录",
  画像提示智能体: "学习记录",
  学习画像智能体: "学习记录",
  视频检索智能体: "查找视频",
  图片检索智能体: "查找图片",
  筛选智能体: "筛选排序",
  筛选排序智能体: "筛选排序",
  资源卡片智能体: "整理卡片",
  学习卡片智能体: "整理卡片",
  图片卡片智能体: "整理卡片",
  精选视频工具: "精选视频",
  精选图片工具: "精选图片",
  "Curated Video Search Tool": "精选视频",
  "Curated Image Search Tool": "精选图片",
};

export function formatMediaTraceLabel(item: TraceLabelItem) {
  const raw = String(item.label || item.detail || "").trim();
  if (!raw) return "处理";
  if (MEDIA_TRACE_LABELS[raw]) return MEDIA_TRACE_LABELS[raw];
  return raw
    .replace(/智能体/g, "")
    .replace(/工具/g, "")
    .replace(/检索/g, "查找")
    .replace(/\s*Agent$/i, "")
    .trim();
}
