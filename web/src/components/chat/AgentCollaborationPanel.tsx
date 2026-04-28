import { motion } from "framer-motion";
import {
  BookOpenCheck,
  Bot,
  CheckCircle2,
  Code2,
  FileQuestion,
  Loader2,
  MessageSquareText,
  PenTool,
  Route,
  Search,
  ShieldCheck,
  Sparkles,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { useMemo } from "react";

import { Badge } from "@/components/ui/Badge";
import type { CapabilityId, StreamEvent } from "@/lib/types";

type StepStatus = "pending" | "running" | "complete" | "error";

interface AgentBlueprint {
  key: string;
  title: string;
  description: string;
  stages: string[];
  eventTypes?: string[];
  metadataHints?: string[];
  icon: LucideIcon;
}

interface AgentStep extends AgentBlueprint {
  status: StepStatus;
  detail: string;
  tools: string[];
  touched: boolean;
}

const BLUEPRINTS: Record<CapabilityId, AgentBlueprint[]> = {
  chat: [
    {
      key: "coordinator",
      title: "对话协调智能体",
      description: "理解问题并选择学习策略",
      stages: ["coordinating", "thinking", "planning"],
      eventTypes: ["stage_start", "thinking", "progress"],
      icon: Bot,
    },
    {
      key: "tool",
      title: "工具检索智能体",
      description: "按需调用知识库、搜索或代码工具",
      stages: ["acting", "tools", "reasoning", "retrieval"],
      eventTypes: ["tool_call", "tool_result", "sources", "observation"],
      icon: Wrench,
    },
    {
      key: "tutor",
      title: "讲解智能体",
      description: "组织成适合学生阅读的回答",
      stages: ["responding", "response", "answering", "final", "writing"],
      eventTypes: ["result"],
      icon: MessageSquareText,
    },
  ],
  deep_solve: [
    {
      key: "planner",
      title: "规划智能体",
      description: "拆解题目并制定求解路线",
      stages: ["planning", "plan", "thinking"],
      icon: Route,
    },
    {
      key: "tool",
      title: "工具智能体",
      description: "检索资料、运行代码或补充证据",
      stages: ["acting", "tools", "tool", "retrieval"],
      eventTypes: ["tool_call", "tool_result", "sources"],
      icon: Wrench,
    },
    {
      key: "solver",
      title: "解题智能体",
      description: "基于计划和观察结果完成推理",
      stages: ["reasoning", "solve", "solving"],
      icon: Sparkles,
    },
    {
      key: "verifier",
      title: "验证智能体",
      description: "检查结论、公式和事实一致性",
      stages: ["verify", "verification", "checking"],
      metadataHints: ["verification"],
      eventTypes: ["observation"],
      icon: ShieldCheck,
    },
    {
      key: "writer",
      title: "讲解智能体",
      description: "把最终解法整理成学习讲解",
      stages: ["writing", "responding", "response", "answering", "final"],
      eventTypes: ["result"],
      icon: MessageSquareText,
    },
  ],
  deep_research: [
    {
      key: "rephrase",
      title: "问题改写智能体",
      description: "把需求转成清晰研究问题",
      stages: ["rephrase", "thinking", "planning"],
      icon: PenTool,
    },
    {
      key: "decompose",
      title: "主题拆解智能体",
      description: "拆出子主题、路径和关键问题",
      stages: ["decompose", "outline", "preview_outline"],
      icon: Route,
    },
    {
      key: "research",
      title: "资料检索智能体",
      description: "从知识库、网络和论文中收集证据",
      stages: ["research", "researching", "acting", "retrieval"],
      eventTypes: ["tool_call", "tool_result", "sources"],
      icon: Search,
    },
    {
      key: "report",
      title: "报告智能体",
      description: "整合证据并生成学习报告",
      stages: ["report", "reporting", "writing", "responding", "final"],
      eventTypes: ["result"],
      icon: BookOpenCheck,
    },
  ],
  deep_question: [
    {
      key: "ideation",
      title: "知识点分析智能体",
      description: "定位要考察的概念和能力",
      stages: ["ideation", "thinking", "planning"],
      icon: Sparkles,
    },
    {
      key: "generation",
      title: "出题智能体",
      description: "生成题干、选项、答案和解析",
      stages: ["generation", "generate", "generating"],
      icon: FileQuestion,
    },
    {
      key: "validation",
      title: "校验智能体",
      description: "检查题目格式、答案和难度",
      stages: ["validation", "validate", "validating"],
      icon: ShieldCheck,
    },
    {
      key: "repair",
      title: "修复智能体",
      description: "必要时修正无效题目",
      stages: ["repair", "repairing"],
      icon: Wrench,
    },
    {
      key: "writer",
      title: "题目本智能体",
      description: "输出练习并支持结果回写",
      stages: ["writing", "responding", "final"],
      eventTypes: ["result"],
      icon: BookOpenCheck,
    },
  ],
  visualize: [
    {
      key: "analysis",
      title: "结构分析智能体",
      description: "识别概念关系和图解重点",
      stages: ["analysis", "analyzing", "thinking", "planning"],
      icon: Sparkles,
    },
    {
      key: "design",
      title: "图解设计智能体",
      description: "选择图表、流程图或结构图形式",
      stages: ["design", "visualize", "generation", "generating"],
      icon: Route,
    },
    {
      key: "render",
      title: "渲染智能体",
      description: "生成可视化代码和预览结果",
      stages: ["render", "rendering", "reviewing", "final"],
      eventTypes: ["result"],
      icon: Code2,
    },
  ],
  math_animator: [
    {
      key: "analysis",
      title: "概念分析智能体",
      description: "提取数学目标和视觉对象",
      stages: ["concept_analysis", "analysis", "analyze", "thinking"],
      icon: Sparkles,
    },
    {
      key: "design",
      title: "分镜设计智能体",
      description: "规划动画节奏、画面和讲解步骤",
      stages: ["design", "scene_design", "concept_design"],
      icon: Route,
    },
    {
      key: "code",
      title: "Manim 编码智能体",
      description: "生成可运行的动画脚本",
      stages: ["generate_code", "code_generation", "code", "code_retry"],
      icon: Code2,
    },
    {
      key: "render",
      title: "渲染检查智能体",
      description: "调用渲染并修复失败脚本",
      stages: ["render", "render_output", "visual_review"],
      icon: ShieldCheck,
    },
    {
      key: "writer",
      title: "总结智能体",
      description: "整理动画产物和学习说明",
      stages: ["summarize", "summary", "writing", "responding", "final"],
      eventTypes: ["result"],
      icon: MessageSquareText,
    },
  ],
};

export function AgentCollaborationPanel({
  events,
  capability,
  status = "done",
}: {
  events: StreamEvent[];
  capability?: CapabilityId;
  status?: "streaming" | "done" | "error";
}) {
  const steps = useMemo(() => buildAgentSteps(events, capability ?? "chat", status), [capability, events, status]);
  const activeCount = steps.filter((step) => step.touched || step.status === "running" || step.status === "complete").length;
  const hasError = steps.some((step) => step.status === "error");
  const running = steps.some((step) => step.status === "running");

  if (!events.length) return null;

  return (
    <div className="mt-2 rounded-lg border border-line bg-white p-3" data-testid="agent-collaboration">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold text-ink">智能体协作 · {steps.length} 个角色编排</p>
          <p className="mt-1 text-xs text-slate-500">
            {activeCount ? `${activeCount} 个角色已参与本轮学习任务` : "正在等待协作信号"}
          </p>
        </div>
        <Badge tone={hasError ? "danger" : running ? "warning" : "success"}>
          {hasError ? "异常" : running ? "协作中" : "已完成"}
        </Badge>
      </div>

      <div className="mt-3 grid gap-2">
        {steps.map((step, index) => (
          <AgentStepRow key={step.key} step={step} index={index} />
        ))}
      </div>

      <details className="mt-3 rounded-lg border border-line bg-canvas px-3 py-2 text-xs text-slate-500">
        <summary className="dt-interactive cursor-pointer list-none font-medium text-slate-600">
          思考过程 · {events.length}
        </summary>
        <div className="mt-2 max-h-48 space-y-1.5 overflow-y-auto" data-testid="agent-raw-trace">
          {events.map((event, index) => (
            <div key={`${event.seq ?? index}-${event.type}-${event.stage}`} className="min-w-0">
              <span className="font-medium text-ink">{event.type}</span>
              {event.stage ? <span> · {event.stage}</span> : null}
              {event.content ? <span className="block truncate">{event.content}</span> : null}
              {getToolName(event) ? <span className="block truncate text-slate-400">tool: {getToolName(event)}</span> : null}
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}

function AgentStepRow({ step, index }: { step: AgentStep; index: number }) {
  const Icon = step.icon;
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18, delay: Math.min(index * 0.03, 0.12) }}
      className={`grid grid-cols-[2rem_minmax(0,1fr)] gap-2 rounded-lg border px-2.5 py-2 ${
        step.status === "running"
          ? "border-teal-200 bg-teal-50"
          : step.status === "complete"
            ? "border-line bg-canvas"
            : step.status === "error"
              ? "border-red-200 bg-red-50"
              : "border-line bg-white"
      }`}
    >
      <span className={`flex h-8 w-8 items-center justify-center rounded-lg ${iconTone(step.status)}`}>
        {step.status === "running" ? (
          <Loader2 size={15} className="animate-spin" />
        ) : step.status === "complete" ? (
          <CheckCircle2 size={15} />
        ) : (
          <Icon size={15} />
        )}
      </span>
      <span className="min-w-0">
        <span className="flex flex-wrap items-center gap-2">
          <span className="font-medium text-ink">{step.title}</span>
          <span className="text-xs text-slate-500">{statusText(step.status)}</span>
        </span>
        <span className="mt-0.5 block truncate text-xs text-slate-500">
          {step.detail || step.description}
        </span>
        {step.tools.length ? (
          <span className="mt-1 flex flex-wrap gap-1">
            {step.tools.slice(0, 4).map((tool) => (
              <span key={tool} className="rounded-md bg-white px-1.5 py-0.5 text-[11px] text-brand-blue">
                {tool}
              </span>
            ))}
          </span>
        ) : null}
      </span>
    </motion.div>
  );
}

function buildAgentSteps(events: StreamEvent[], capability: CapabilityId, status: "streaming" | "done" | "error") {
  const steps: AgentStep[] = BLUEPRINTS[capability].map((step) => ({
    ...step,
    status: "pending",
    detail: "",
    tools: [],
    touched: false,
  }));
  let lastTouched = -1;

  events.forEach((event) => {
    const index = findStepIndex(event, steps);
    if (index < 0) return;
    const step = steps[index];
    step.touched = true;
    lastTouched = Math.max(lastTouched, index);

    const content = meaningfulContent(event);
    if (content) step.detail = content;

    const tool = getToolName(event);
    if (tool && !step.tools.includes(tool)) step.tools.push(tool);

    if (event.type === "error") {
      step.status = "error";
      return;
    }
    if (isCompleteEvent(event)) {
      step.status = "complete";
      return;
    }
    if (step.status !== "complete") {
      step.status = "running";
    }
  });

  steps.forEach((step, index) => {
    if (index < lastTouched && step.touched && step.status === "running") {
      step.status = "complete";
    }
  });

  const hasTerminalEvent = events.some((event) => event.type === "result" || event.type === "done");
  if (hasTerminalEvent || status === "done") {
    steps.forEach((step) => {
      if (step.touched && step.status === "running") step.status = "complete";
    });
  }
  if (status === "error" && !steps.some((step) => step.status === "error") && lastTouched >= 0) {
    steps[lastTouched].status = "error";
  }
  if (lastTouched < 0 && events.length) {
    steps[0].touched = true;
    steps[0].status = status === "error" ? "error" : status === "streaming" ? "running" : "complete";
  }

  return steps;
}

function findStepIndex(event: StreamEvent, steps: AgentStep[]) {
  const stage = String(event.stage ?? "").toLowerCase();
  const source = String(event.source ?? "").toLowerCase();
  const type = String(event.type ?? "").toLowerCase();
  const metadata = event.metadata ?? {};
  const traceKind = String(metadata.trace_kind ?? metadata.kind ?? "").toLowerCase();
  const node = String(metadata.node ?? metadata.stage ?? "").toLowerCase();

  if (type === "tool_call" || type === "tool_result" || getToolName(event)) {
    const toolIndex = steps.findIndex((step) => step.key === "tool" || step.key === "research" || step.stages.includes("render"));
    if (toolIndex >= 0) return toolIndex;
  }
  if (traceKind.includes("verification")) {
    const verifyIndex = steps.findIndex((step) => step.key === "verifier" || step.metadataHints?.includes("verification"));
    if (verifyIndex >= 0) return verifyIndex;
  }
  if (type === "result") {
    return steps.length - 1;
  }

  const candidates = [stage, source, type, traceKind, node].filter(Boolean);
  const exactIndex = steps.findIndex((step) =>
    candidates.some((candidate) => step.stages.includes(candidate) || step.eventTypes?.includes(candidate)),
  );
  if (exactIndex >= 0) return exactIndex;

  return steps.findIndex((step) =>
    candidates.some((candidate) => step.stages.some((stageName) => candidate.includes(stageName))),
  );
}

function isCompleteEvent(event: StreamEvent) {
  return event.type === "stage_end" || event.type === "tool_result" || event.type === "result" || event.type === "done";
}

function meaningfulContent(event: StreamEvent) {
  const content = String(event.content ?? "").trim();
  if (!content || content.toLowerCase() === "thinking...") return "";
  if (content.length > 120) return `${content.slice(0, 120)}...`;
  return content;
}

function getToolName(event: StreamEvent) {
  const metadata = event.metadata ?? {};
  const raw = metadata.tool ?? metadata.tool_name ?? metadata.name;
  return raw ? String(raw) : "";
}

function iconTone(status: StepStatus) {
  if (status === "running") return "bg-white text-brand-teal";
  if (status === "complete") return "bg-teal-50 text-brand-teal";
  if (status === "error") return "bg-white text-brand-red";
  return "bg-canvas text-slate-500";
}

function statusText(status: StepStatus) {
  return {
    pending: "待命",
    running: "进行中",
    complete: "已完成",
    error: "异常",
  }[status];
}
