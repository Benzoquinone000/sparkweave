import type { StreamEvent } from "@/lib/types";

type ToolTracePhase = "call" | "result";

type ToolTraceCopy = {
  displayName: string;
  callTitle: string;
  resultTitle: string;
  callDetail: string;
  resultDetail: string;
};

const TOOL_TRACE_COPY: Record<string, ToolTraceCopy> = {
  rag: {
    displayName: "资料查找",
    callTitle: "查找资料",
    resultTitle: "资料就绪",
    callDetail: "正在查找课程资料",
    resultDetail: "课程资料已返回",
  },
  rag_search: {
    displayName: "资料查找",
    callTitle: "查找资料",
    resultTitle: "资料就绪",
    callDetail: "正在查找课程资料",
    resultDetail: "课程资料已返回",
  },
  web_search: {
    displayName: "联网搜索",
    callTitle: "联网查找",
    resultTitle: "网页资料就绪",
    callDetail: "正在查找外部资料",
    resultDetail: "外部资料已返回",
  },
  external_video_search: {
    displayName: "精选视频",
    callTitle: "查找视频",
    resultTitle: "视频就绪",
    callDetail: "正在筛选公开视频",
    resultDetail: "视频卡片已准备好",
  },
  external_image_search: {
    displayName: "精选图片",
    callTitle: "查找图片",
    resultTitle: "图片就绪",
    callDetail: "正在筛选图片参考",
    resultDetail: "图片卡片已准备好",
  },
  iflytek_workflow: {
    displayName: "讯飞工作流",
    callTitle: "调用讯飞工作流",
    resultTitle: "讯飞工作流完成",
    callDetail: "正在执行已发布的讯飞星辰工作流",
    resultDetail: "讯飞工作流结果已返回",
  },
  iflytek_formula_ocr: {
    displayName: "讯飞公式识别",
    callTitle: "识别公式",
    resultTitle: "公式识别完成",
    callDetail: "正在把题图中的公式转成可推理文本",
    resultDetail: "公式文本已进入解题上下文",
  },
  iflytek_image_understanding: {
    displayName: "讯飞图片理解",
    callTitle: "理解图片",
    resultTitle: "图片理解完成",
    callDetail: "正在分析截图、板书或示意图中的学习信息",
    resultDetail: "图片理解结果已进入辅导上下文",
  },
  canvas: {
    displayName: "文档画布",
    callTitle: "准备画布",
    resultTitle: "画布已更新",
    callDetail: "正在生成可编辑文档",
    resultDetail: "右侧可编辑文档已准备好",
  },
  document_canvas: {
    displayName: "文档画布",
    callTitle: "准备画布",
    resultTitle: "画布已更新",
    callDetail: "正在生成可编辑文档",
    resultDetail: "右侧可编辑文档已准备好",
  },
  editable_canvas: {
    displayName: "文档画布",
    callTitle: "准备画布",
    resultTitle: "画布已更新",
    callDetail: "正在生成可编辑文档",
    resultDetail: "右侧可编辑文档已准备好",
  },
  code_execution: {
    displayName: "代码运行",
    callTitle: "运行代码",
    resultTitle: "代码结果",
    callDetail: "正在计算或验证",
    resultDetail: "代码运行已完成",
  },
  reason: {
    displayName: "认真推导",
    callTitle: "认真推导",
    resultTitle: "推导完成",
    callDetail: "正在处理复杂步骤",
    resultDetail: "推导结果已返回",
  },
  brainstorm: {
    displayName: "头脑风暴",
    callTitle: "展开思路",
    resultTitle: "思路就绪",
    callDetail: "正在生成多个方向",
    resultDetail: "候选思路已返回",
  },
  paper_search: {
    displayName: "论文查找",
    callTitle: "查找论文",
    resultTitle: "论文资料就绪",
    callDetail: "正在查找论文线索",
    resultDetail: "论文线索已返回",
  },
  geogebra_analysis: {
    displayName: "几何题分析",
    callTitle: "分析题图",
    resultTitle: "图形分析完成",
    callDetail: "正在识别几何结构",
    resultDetail: "图形命令已生成",
  },
};

export function getToolNameFromEvent(event: StreamEvent) {
  const metadata = event.metadata ?? {};
  const raw = metadata.tool ?? metadata.tool_name ?? metadata.name;
  if (raw) return normalizeToolName(String(raw));
  if (event.type === "tool_call" && event.content) return normalizeToolName(event.content);
  return "";
}

export function getToolDisplayName(tool: string) {
  const normalized = normalizeToolName(tool);
  if (TOOL_TRACE_COPY[normalized]) return TOOL_TRACE_COPY[normalized].displayName;
  if (normalized.includes("rag") || normalized.includes("knowledge") || normalized.includes("kb")) return "资料查找";
  if (normalized.includes("canvas") || normalized.includes("document")) return "文档画布";
  if (normalized.includes("video")) return "精选视频";
  if (normalized.includes("image") || normalized.includes("picture")) return "精选图片";
  if (normalized.includes("formula")) return "讯飞公式识别";
  if (normalized.includes("vision") || normalized.includes("image_understanding")) return "讯飞图片理解";
  if (normalized.includes("iflytek") || normalized.includes("xingchen") || normalized.includes("workflow")) return "讯飞工作流";
  if (normalized.includes("search")) return "联网搜索";
  if (normalized.includes("python") || normalized.includes("code")) return "代码运行";
  return tool.includes("_") ? "辅助功能" : tool.trim();
}

export function getToolTraceCopy(event: StreamEvent, phase: ToolTracePhase) {
  const tool = getToolNameFromEvent(event);
  const copy = TOOL_TRACE_COPY[tool];
  if (copy) {
    return {
      tool,
      displayName: copy.displayName,
      title: phase === "call" ? copy.callTitle : copy.resultTitle,
      detail: phase === "call" ? copy.callDetail : copy.resultDetail,
    };
  }
  const displayName = tool ? getToolDisplayName(tool) : "辅助功能";
  return {
    tool,
    displayName,
    title: phase === "call" ? "调用辅助功能" : "辅助功能完成",
    detail: phase === "call" ? `正在使用${displayName}` : `${displayName}已返回结果`,
  };
}

function normalizeToolName(value: string) {
  return value.trim().toLowerCase().replace(/[\s-]+/g, "_");
}
