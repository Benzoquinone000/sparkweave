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

interface ReadableTraceItem {
  label: string;
  detail: string;
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
  external_video_search: [
    {
      key: "profile",
      title: "画像提示智能体",
      description: "读取当前学习目标、薄弱点和资源偏好",
      stages: ["coordinating", "planning"],
      eventTypes: ["stage_start", "progress"],
      icon: Sparkles,
    },
    {
      key: "search",
      title: "视频检索智能体",
      description: "从公开网页中检索可观看的课程视频",
      stages: ["searching", "search", "retrieval"],
      eventTypes: ["progress", "sources"],
      icon: Search,
    },
    {
      key: "ranking",
      title: "筛选排序智能体",
      description: "按相关性、入门友好和可嵌入性挑选少量结果",
      stages: ["ranked", "ranking", "filtering"],
      metadataHints: ["video_search"],
      icon: ShieldCheck,
    },
    {
      key: "card",
      title: "资源卡片智能体",
      description: "把精选视频整理成可播放、可保存的学习卡片",
      stages: ["responding", "response", "final"],
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
  const visibleSteps = steps.filter((step) => step.touched || step.status === "running" || step.status === "complete" || step.status === "error");
  const displayedSteps = visibleSteps.length ? visibleSteps : steps.slice(0, 1);
  const activeCount = visibleSteps.length;
  const hasError = steps.some((step) => step.status === "error");
  const running = steps.some((step) => step.status === "running");
  const profileAware = events.some((event) => event.metadata?.profile_hints_applied || event.metadata?.profile_guided);
  const profileGuidedPrompt = useMemo(() => findProfileGuidedPrompt(events), [events]);
  const readableEvents = useMemo(() => buildReadableTraceItems(events, status), [events, status]);
  const routeSummary = summarizeCollaboration(displayedSteps, profileAware);

  if (!events.length) return null;

  return (
    <div className="mt-2 rounded-lg border border-line bg-white p-3" data-testid="agent-collaboration">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold text-ink">智能体协作 · {displayedSteps.length} 个角色参与</p>
          <p className="mt-1 text-xs text-slate-500">
            {profileGuidedPrompt
              ? "已按学习画像把泛化指令转成具体学习任务"
              : profileAware
                ? "已参考学习画像，再调度本轮学习任务"
                : activeCount
                  ? "已按任务自动调度"
                  : "正在等待协作信号"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {profileGuidedPrompt ? <Badge tone="brand">画像触发</Badge> : null}
          {profileAware ? <Badge tone="brand">画像已参与</Badge> : null}
          <Badge tone={hasError ? "danger" : running ? "warning" : "success"}>
            {hasError ? "异常" : running ? "协作中" : "已完成"}
          </Badge>
        </div>
      </div>

      <div className="mt-3 rounded-lg border border-line bg-canvas px-3 py-2" data-testid="agent-collaboration-route">
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <span className="font-medium text-ink">接力路线</span>
          <span>{routeSummary}</span>
        </div>
        {profileGuidedPrompt ? (
          <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">
            画像触发：{profileGuidedPrompt}
          </p>
        ) : null}
        <div className="mt-2 flex gap-1.5 overflow-x-auto pb-1">
          {displayedSteps.map((step, index) => (
            <div key={`${step.key}-route`} className="flex shrink-0 items-center gap-1.5">
              <span
                className={`inline-flex min-h-7 items-center gap-1 rounded-md border px-2 text-xs font-medium ${routeChipTone(step.status)}`}
              >
                <span className={`h-1.5 w-1.5 rounded-full ${routeDotTone(step.status)}`} />
                {shortAgentName(step.title)}
              </span>
              {index < displayedSteps.length - 1 ? <span className="text-slate-300">→</span> : null}
            </div>
          ))}
        </div>
      </div>

      <div className="mt-3 grid gap-2">
        {displayedSteps.map((step, index) => (
          <AgentStepRow key={step.key} step={step} index={index} />
        ))}
      </div>

      {readableEvents.length ? (
        <details className="mt-3 rounded-lg border border-line bg-canvas px-3 py-2 text-xs text-slate-500">
          <summary className="dt-interactive cursor-pointer list-none font-medium text-slate-600">
            协作明细 · {readableEvents.length}
          </summary>
          <div className="mt-2 max-h-48 space-y-1.5 overflow-y-auto" data-testid="agent-readable-trace">
            {readableEvents.map((item, index) => (
              <div key={`${item.label}-${index}`} className="min-w-0">
                <span className="font-medium text-ink">{item.label}</span>
                {item.detail ? <span className="block truncate">{item.detail}</span> : null}
              </div>
            ))}
          </div>
        </details>
      ) : null}
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
  const stepEvents = hasTerminalEvent(events) ? trimEventsAfterTerminal(events) : events;

  stepEvents.forEach((event) => {
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

  const terminalSeen = events.some((event) => event.type === "result" || event.type === "done");
  if (terminalSeen || status === "done") {
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

function trimEventsAfterTerminal(events: StreamEvent[]) {
  const terminalIndex = findLastTerminalEventIndex(events);
  if (terminalIndex < 0) return events;
  return events.filter((event, index) => index <= terminalIndex || event.type === "error");
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

function buildReadableTraceItems(events: StreamEvent[], status: "streaming" | "done" | "error" = "done") {
  const items: ReadableTraceItem[] = [];
  const readableSource = status === "done" || hasTerminalEvent(events) ? compactCompletedTraceEvents(events) : events;

  readableSource.forEach((event) => {
    const content = meaningfulContent(event);
    const tool = getToolName(event);
    const profilePrompt = metadataText(event.metadata, "rewritten_prompt");

    if (event.type === "error") {
      items.push({ label: "遇到异常", detail: content || "某个步骤没有顺利完成。" });
      return;
    }
    if (event.metadata?.profile_guided && profilePrompt) {
      items.push({ label: "画像触发", detail: `按画像改成：${profilePrompt}` });
    }
    if (event.type === "tool_call") {
      items.push({ label: "调用工具", detail: tool ? `正在使用 ${tool}` : content || "正在补充必要信息。" });
      return;
    }
    if (event.type === "tool_result") {
      items.push({ label: "工具返回", detail: tool ? `${tool} 已返回结果` : content || "外部信息已经返回。" });
      return;
    }
    if (event.type === "sources") {
      items.push({ label: "找到资料", detail: content || "已获得可参考来源。" });
      return;
    }
    if (event.type === "observation") {
      items.push({ label: "观察结果", detail: content || "已记录中间观察。" });
      return;
    }
    if (event.type === "result") {
      items.push({ label: "形成回答", detail: content || "最终结果已生成。" });
      return;
    }
    if (content) {
      items.push({ label: readableStageLabel(event), detail: content });
    }
  });

  const compact: ReadableTraceItem[] = [];
  items.forEach((item) => {
    const last = compact[compact.length - 1];
    if (last && last.label === item.label && last.detail === item.detail) return;
    compact.push(item);
  });
  return compact.slice(0, 8);
}

function compactCompletedTraceEvents(events: StreamEvent[]) {
  const terminalIndex = findLastTerminalEventIndex(events);
  const cutoff = terminalIndex >= 0 ? terminalIndex : events.length - 1;
  return events.filter((event, index) => {
    if (index > cutoff && event.type !== "error") return false;
    if (event.type === "stage_start" || event.type === "stage_end" || event.type === "thinking") {
      return false;
    }
    if (event.type === "progress") return Boolean(meaningfulContent(event) || event.metadata?.profile_guided);
    return true;
  });
}

function findLastTerminalEventIndex(events: StreamEvent[]) {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const type = events[index]?.type;
    if (type === "result" || type === "done") return index;
  }
  return -1;
}

function hasTerminalEvent(events: StreamEvent[]) {
  return findLastTerminalEventIndex(events) >= 0;
}

function findProfileGuidedPrompt(events: StreamEvent[]) {
  for (const event of events) {
    if (!event.metadata?.profile_guided) continue;
    const prompt = metadataText(event.metadata, "rewritten_prompt");
    if (prompt) return prompt.length > 120 ? `${prompt.slice(0, 120).trim()}...` : prompt;
  }
  return "";
}

function metadataText(metadata: StreamEvent["metadata"] | undefined, key: string) {
  const value = metadata?.[key];
  return typeof value === "string" ? value.trim() : "";
}

function readableStageLabel(event: StreamEvent) {
  const stage = String(event.stage || "").toLowerCase();
  if (stage.includes("coordinating") || stage.includes("planning") || stage.includes("thinking")) return "识别任务";
  if (stage.includes("retrieval") || stage.includes("search")) return "检索资料";
  if (stage.includes("reasoning") || stage.includes("solve")) return "推理整理";
  if (stage.includes("writing") || stage.includes("responding") || stage.includes("final")) return "组织回答";
  if (stage.includes("render") || stage.includes("visual")) return "生成产物";
  return "步骤更新";
}

function iconTone(status: StepStatus) {
  if (status === "running") return "bg-white text-brand-teal";
  if (status === "complete") return "bg-teal-50 text-brand-teal";
  if (status === "error") return "bg-white text-brand-red";
  return "bg-canvas text-slate-500";
}

function routeChipTone(status: StepStatus) {
  if (status === "running") return "border-teal-200 bg-white text-brand-teal";
  if (status === "complete") return "border-line bg-white text-ink";
  if (status === "error") return "border-red-200 bg-white text-brand-red";
  return "border-line bg-white text-slate-500";
}

function routeDotTone(status: StepStatus) {
  if (status === "running") return "bg-brand-blue animate-pulse";
  if (status === "complete") return "bg-brand-teal";
  if (status === "error") return "bg-brand-red";
  return "bg-slate-300";
}

function shortAgentName(title: string) {
  return title.replace(/智能体$/, "");
}

function summarizeCollaboration(steps: AgentStep[], profileAware: boolean) {
  const completed = steps.filter((step) => step.status === "complete").length;
  const running = steps.find((step) => step.status === "running");
  if (running) return `${shortAgentName(running.title)}正在处理，前序结果会继续传给下一位角色。`;
  if (completed > 1) return profileAware ? "画像先参与判断，再由多个角色接力完成。" : "多个角色已按任务顺序完成接力。";
  return profileAware ? "已带入画像，正在等待更多协作信号。" : "系统会按任务自动选择需要的角色。";
}

function statusText(status: StepStatus) {
  return {
    pending: "待命",
    running: "进行中",
    complete: "已完成",
    error: "异常",
  }[status];
}
