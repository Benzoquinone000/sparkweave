import {
  BarChart3,
  BookOpenCheck,
  BrainCircuit,
  FileQuestion,
  FlaskConical,
  GraduationCap,
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
    label: "即时答疑",
    shortLabel: "对话",
    description: "面向日常学习、资料追问和推理解释的轻量模式。",
    icon: MessageSquareText,
    tools: ["rag", "web_search", "external_video_search", "paper_search", "code_execution", "reason"],
    config: {},
  },
  {
    id: "deep_solve",
    label: "深度求解",
    shortLabel: "求解",
    description: "规划、调用工具、验证并写出结构化解答。",
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
    description: "拆解主题、检索证据并生成学习报告。",
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
    description: "生成 Manim 代码与动画渲染结果。",
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
  { id: "rag", label: "知识库", icon: BookOpenCheck },
  { id: "web_search", label: "联网检索", icon: Search },
  { id: "external_video_search", label: "精选视频", icon: Video },
  { id: "paper_search", label: "论文检索", icon: GraduationCap },
  { id: "code_execution", label: "代码执行", icon: FlaskConical },
  { id: "reason", label: "深度推理", icon: Sparkles },
  { id: "brainstorm", label: "头脑风暴", icon: PenTool },
];

export function getCapability(id: CapabilityId) {
  return CAPABILITIES.find((item) => item.id === id) ?? CAPABILITIES[0];
}

export function capabilityLabel(id: string | null | undefined) {
  if (id === "external_video_search") return "精选视频工具";
  const capability = CAPABILITIES.find((item) => item.id === id);
  return capability?.label || id || "聊天";
}

export function defaultToolsForCapability(id: CapabilityId) {
  return getCapability(id).tools.slice(0, id === "chat" ? 3 : 3);
}

export function defaultConfigForCapability(id: CapabilityId, content: string) {
  const definition = getCapability(id);
  if (id === "deep_question") {
    return { ...definition.config, topic: content.slice(0, 120) };
  }
  return { ...definition.config };
}
