import {
  BarChart3,
  BookOpenCheck,
  BrainCircuit,
  FilePenLine,
  FileQuestion,
  FlaskConical,
  GraduationCap,
  Images,
  MessageSquareText,
  PenTool,
  Search,
  Sparkles,
  SquareFunction,
  Video,
  type LucideIcon,
} from "lucide-react";

import type { CapabilityId } from "@/lib/types";

export interface CapabilityDefinition {
  id: CapabilityId;
  label: string;
  shortLabel: string;
  description: string;
  icon: LucideIcon;
  tools: string[];
  config: Record<string, unknown>;
}

export const CAPABILITIES: CapabilityDefinition[] = [
  {
    id: "chat",
    label: "自动导学",
    shortLabel: "自动",
    description: "直接说学习目标，系统自动选择资料查找、解题、出题、图片/视频查找或动画生成。",
    icon: MessageSquareText,
    tools: [
      "canvas",
      "rag",
      "web_search",
      "external_video_search",
      "external_image_search",
      "iflytek_workflow",
      "iflytek_formula_ocr",
      "iflytek_image_understanding",
      "paper_search",
      "code_execution",
      "reason",
    ],
    config: {},
  },
  {
    id: "deep_solve",
    label: "深度求解",
    shortLabel: "求解",
    description: "规划求解，必要时查找资料验证，并写出结构化解答。",
    icon: BrainCircuit,
    tools: ["rag", "web_search", "code_execution", "reason"],
    config: { detailed_answer: true },
  },
  {
    id: "deep_question",
    label: "题目生成",
    shortLabel: "练习",
    description: "围绕知识点生成题目、答案和解析。",
    icon: FileQuestion,
    tools: ["rag", "web_search", "code_execution"],
    config: {
      mode: "custom",
      num_questions: 5,
      difficulty: "medium",
      question_type: "mixed",
      topic: "",
      preference: "",
    },
  },
  {
    id: "deep_research",
    label: "深度研究",
    shortLabel: "研究",
    description: "拆解主题、查找资料并生成学习报告。",
    icon: Search,
    tools: ["rag", "web_search", "paper_search", "code_execution"],
    config: {
      mode: "report",
      depth: "standard",
      sources: ["web"],
    },
  },
  {
    id: "visualize",
    label: "知识可视化",
    shortLabel: "图解",
    description: "把概念转成图表、Mermaid 或 SVG 结构。",
    icon: BarChart3,
    tools: [],
    config: { render_mode: "auto" },
  },
  {
    id: "math_animator",
    label: "数学动画",
    shortLabel: "动画",
    description: "生成动画脚本与视频结果。",
    icon: SquareFunction,
    tools: [],
    config: {
      output_mode: "video",
      quality: "medium",
      enable_narration_audio: true,
      style_hint: "clean educational animation",
      max_retries: 4,
    },
  },
];

export const TOOL_OPTIONS = [
  { id: "rag", label: "资料库", icon: BookOpenCheck },
  { id: "canvas", label: "文档画布", icon: FilePenLine },
  { id: "web_search", label: "联网查找", icon: Search },
  { id: "external_video_search", label: "精选视频", icon: Video },
  { id: "external_image_search", label: "精选图片", icon: Images },
  { id: "iflytek_workflow", label: "讯飞工作流", icon: Sparkles },
  { id: "iflytek_formula_ocr", label: "讯飞公式识别", icon: SquareFunction },
  { id: "iflytek_image_understanding", label: "讯飞图片理解", icon: Images },
  { id: "paper_search", label: "论文查找", icon: GraduationCap },
  { id: "code_execution", label: "代码演算", icon: FlaskConical },
  { id: "reason", label: "认真推导", icon: Sparkles },
  { id: "brainstorm", label: "头脑风暴", icon: PenTool },
];

export function getCapability(id: CapabilityId) {
  return CAPABILITIES.find((item) => item.id === id) ?? CAPABILITIES[0];
}

export function capabilityLabel(id: string | null | undefined) {
  if (id === "external_video_search") return "精选视频";
  if (id === "external_image_search") return "精选图片";
  if (id === "iflytek_workflow") return "讯飞工作流";
  if (id === "iflytek_formula_ocr") return "讯飞公式识别";
  if (id === "iflytek_image_understanding") return "讯飞图片理解";
  const capability = CAPABILITIES.find((item) => item.id === id);
  return capability?.label || id || "聊天";
}

export function defaultToolsForCapability(id: CapabilityId) {
  const tools = getCapability(id).tools;
  if (id === "chat") {
    return tools.filter((tool) =>
      [
        "canvas",
        "rag",
        "web_search",
        "external_video_search",
        "external_image_search",
        "iflytek_workflow",
        "iflytek_formula_ocr",
        "iflytek_image_understanding",
        "paper_search",
        "code_execution",
        "reason",
      ].includes(tool),
    );
  }
  return tools.slice();
}

export function defaultConfigForCapability(id: CapabilityId, content: string) {
  const definition = getCapability(id);
  if (id === "deep_question") {
    return { ...definition.config, topic: content.slice(0, 120) };
  }
  return { ...definition.config };
}
