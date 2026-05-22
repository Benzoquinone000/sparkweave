import { motion } from "framer-motion";
import {
  BookOpenCheck,
  Bot,
  ChevronRight,
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

import { getToolDisplayName, getToolNameFromEvent, getToolTraceCopy } from "@/lib/toolTraceLabels";
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

interface StructuredRouteItem {
  key: string;
  label: string;
  detail: string;
  status?: StepStatus;
}

const BLUEPRINTS: Record<CapabilityId, AgentBlueprint[]> = {
  chat: [
    {
      key: "coordinator",
      title: "理解任务",
      description: "识别问题并选择学习策略",
      stages: ["coordinating", "thinking", "planning"],
      eventTypes: ["stage_start", "thinking", "progress"],
      icon: Bot,
    },
    {
      key: "tool",
      title: "补充资料",
      description: "按需查找资料、搜索网页或运行代码",
      stages: ["acting", "tools", "reasoning", "retrieval"],
      eventTypes: ["tool_call", "tool_result", "sources", "observation"],
      icon: Wrench,
    },
    {
      key: "tutor",
      title: "组织讲解",
      description: "整理成适合学生阅读的回答",
      stages: ["responding", "response", "answering", "final", "writing"],
      eventTypes: ["result"],
      icon: MessageSquareText,
    },
  ],
  external_video_search: [
    {
      key: "profile",
      title: "学习记录",
      description: "读取当前学习目标、薄弱点和资源偏好",
      stages: ["coordinating", "planning"],
      eventTypes: ["stage_start", "progress"],
      icon: Sparkles,
    },
    {
      key: "search",
      title: "查找视频",
      description: "从公开网页中查找可观看的课程视频",
      stages: ["searching", "search", "retrieval"],
      eventTypes: ["progress", "sources"],
      icon: Search,
    },
    {
      key: "ranking",
      title: "筛选排序",
      description: "按相关性、入门友好和可嵌入性挑选少量结果",
      stages: ["ranked", "ranking", "filtering"],
      metadataHints: ["video_search"],
      icon: ShieldCheck,
    },
    {
      key: "card",
      title: "整理卡片",
      description: "把精选视频整理成可播放、可保存的学习卡片",
      stages: ["responding", "response", "final"],
      eventTypes: ["result"],
      icon: MessageSquareText,
    },
  ],
  external_image_search: [
    {
      key: "profile",
      title: "学习记录",
      description: "读取当前学习目标、薄弱点和资源偏好",
      stages: ["coordinating", "planning"],
      eventTypes: ["stage_start", "progress"],
      icon: Sparkles,
    },
    {
      key: "search",
      title: "查找图片",
      description: "从公开网页中查找图片、图解和示意图",
      stages: ["searching", "search", "retrieval"],
      eventTypes: ["progress", "sources"],
      icon: Search,
    },
    {
      key: "ranking",
      title: "筛选排序",
      description: "按相关性、清晰度和来源可信度挑选少量结果",
      stages: ["ranked", "ranking", "filtering"],
      metadataHints: ["image_search"],
      icon: ShieldCheck,
    },
    {
      key: "card",
      title: "整理卡片",
      description: "把精选图片整理成可查看、可保存的学习卡片",
      stages: ["responding", "response", "final"],
      eventTypes: ["result"],
      icon: MessageSquareText,
    },
  ],
  deep_solve: [
    {
      key: "planner",
      title: "规划解法",
      description: "拆解题目并制定求解路线",
      stages: ["planning", "plan", "thinking"],
      icon: Route,
    },
    {
      key: "tool",
      title: "补充资料",
      description: "查找资料、运行代码或补充来源",
      stages: ["acting", "tools", "tool", "retrieval"],
      eventTypes: ["tool_call", "tool_result", "sources"],
      icon: Wrench,
    },
    {
      key: "solver",
      title: "推理解题",
      description: "基于计划和观察结果完成推理",
      stages: ["reasoning", "solve", "solving"],
      icon: Sparkles,
    },
    {
      key: "verifier",
      title: "校验答案",
      description: "检查结论、公式和事实一致性",
      stages: ["verify", "verification", "checking"],
      metadataHints: ["verification"],
      eventTypes: ["observation"],
      icon: ShieldCheck,
    },
    {
      key: "writer",
      title: "组织讲解",
      description: "把最终解法整理成学习讲解",
      stages: ["writing", "responding", "response", "answering", "final"],
      eventTypes: ["result"],
      icon: MessageSquareText,
    },
  ],
  deep_research: [
    {
      key: "rephrase",
      title: "改写问题",
      description: "把需求转成清晰研究问题",
      stages: ["rephrase", "thinking", "planning"],
      icon: PenTool,
    },
    {
      key: "decompose",
      title: "拆解主题",
      description: "拆出子主题、路径和关键问题",
      stages: ["decompose", "outline", "preview_outline"],
      icon: Route,
    },
    {
      key: "research",
      title: "查找资料",
      description: "从资料库、网络和论文中整理来源",
      stages: ["research", "researching", "acting", "retrieval"],
      eventTypes: ["tool_call", "tool_result", "sources"],
      icon: Search,
    },
    {
      key: "report",
      title: "整理报告",
      description: "整合来源并生成学习报告",
      stages: ["report", "reporting", "writing", "responding", "final"],
      eventTypes: ["result"],
      icon: BookOpenCheck,
    },
  ],
  deep_question: [
    {
      key: "ideation",
      title: "分析知识点",
      description: "定位要考察的概念和掌握点",
      stages: ["ideation", "thinking", "planning"],
      icon: Sparkles,
    },
    {
      key: "generation",
      title: "生成练习",
      description: "生成题干、选项、答案和解析",
      stages: ["generation", "generate", "generating"],
      icon: FileQuestion,
    },
    {
      key: "validation",
      title: "校验题目",
      description: "检查题目格式、答案和难度",
      stages: ["validation", "validate", "validating"],
      icon: ShieldCheck,
    },
    {
      key: "repair",
      title: "修正题目",
      description: "必要时修正无效题目",
      stages: ["repair", "repairing"],
      icon: Wrench,
    },
    {
      key: "writer",
      title: "整理练习",
      description: "输出练习并支持结果回写",
      stages: ["writing", "responding", "final"],
      eventTypes: ["result"],
      icon: BookOpenCheck,
    },
  ],
  visualize: [
    {
      key: "analysis",
      title: "分析结构",
      description: "识别概念关系和图解重点",
      stages: ["analysis", "analyzing", "thinking", "planning"],
      icon: Sparkles,
    },
    {
      key: "design",
      title: "设计图解",
      description: "选择图表、流程图或结构图形式",
      stages: ["design", "visualize", "generation", "generating"],
      icon: Route,
    },
    {
      key: "render",
      title: "生成图解",
      description: "生成可视化代码和预览结果",
      stages: ["render", "rendering", "reviewing", "final"],
      eventTypes: ["result"],
      icon: Code2,
    },
  ],
  math_animator: [
    {
      key: "analysis",
      title: "分析概念",
      description: "提取数学目标和视觉对象",
      stages: ["concept_analysis", "analysis", "analyze", "thinking"],
      icon: Sparkles,
    },
    {
      key: "design",
      title: "设计分镜",
      description: "规划动画节奏、画面和讲解步骤",
      stages: ["design", "scene_design", "concept_design"],
      icon: Route,
    },
    {
      key: "code",
      title: "生成脚本",
      description: "生成可运行的动画脚本",
      stages: ["generate_code", "code_generation", "code", "code_retry"],
      icon: Code2,
    },
    {
      key: "render",
      title: "检查渲染",
      description: "调用渲染并修复失败脚本",
      stages: ["render", "render_output", "visual_review"],
      icon: ShieldCheck,
    },
    {
      key: "writer",
      title: "整理结果",
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
  const hasError = steps.some((step) => step.status === "error");
  const running = steps.some((step) => step.status === "running");
  const profileAware = events.some((event) => event.metadata?.profile_hints_applied || event.metadata?.profile_guided);
  const profileGuidedPrompt = useMemo(() => findProfileGuidedPrompt(events), [events]);
  const readableEvents = useMemo(() => buildReadableTraceItems(events, status), [events, status]);
  const structuredRoute = useMemo(() => findStructuredRoute(events), [events]);
  const routeItems = structuredRoute.length
    ? structuredRoute
    : displayedSteps.map((step) => ({
        key: step.key,
        label: learnerRoleName(step.title),
        detail: normalizeLearningTraceText(step.description),
        status: step.status,
      }));
  const routeSummary = normalizeCollaborationSummary(findCollaborationSummary(events)) || summarizeCollaboration(displayedSteps, profileAware);
  const collaborationStatus: StepStatus = hasError ? "error" : running ? "running" : "complete";
  const collaborationLabel = hasError ? "异常" : running ? "处理中" : "已完成";

  if (!events.length) return null;

  return (
    <div className="dt-dynamic-result mt-2 rounded-lg border border-line bg-white/90 px-3 py-2 text-xs" data-testid="agent-collaboration">
      <div className="flex items-start gap-2">
        <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-sm ${routeDotTone(collaborationStatus)}`} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-ink">学习流程</span>
            <span className="text-slate-300">·</span>
            <span className="text-slate-500">{collaborationLabel}</span>
            {profileGuidedPrompt ? <CompactTag tone="brand">按你情况调整</CompactTag> : null}
            {profileAware ? <CompactTag tone="brand">已结合记录</CompactTag> : null}
          </div>
          <p className="mt-1 line-clamp-1 text-slate-500">{profileGuidedPrompt || routeSummary}</p>
        </div>
      </div>

      <div className="dt-dynamic-panel dt-flow-strip mt-2 rounded-md bg-canvas px-2.5 py-2" data-testid="agent-collaboration-route">
        <div className="flex min-w-0 items-center gap-2 text-slate-500">
          <span className="shrink-0 font-medium text-ink">处理路线</span>
          <span className="min-w-0 truncate">{routeSummary}</span>
        </div>
        <AgentRelayTheater routeItems={routeItems} displayedSteps={displayedSteps} />
        {profileGuidedPrompt ? (
          <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">
            调整理由：{profileGuidedPrompt}
          </p>
        ) : null}
        {structuredRoute.length ? (
          <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">
            {structuredRoute
              .map((item) => item.detail)
              .filter(Boolean)
              .slice(0, 2)
              .join("；")}
          </p>
        ) : null}
      </div>

      <details className="mt-2 border-t border-line pt-2 text-slate-500">
        <summary className="dt-interactive cursor-pointer list-none font-medium text-slate-600">
          过程明细 · {readableEvents.length || displayedSteps.length}
        </summary>
        <div className="mt-2 grid gap-1.5">
          {displayedSteps.map((step, index) => (
            <AgentStepRow key={step.key} step={step} index={index} />
          ))}
        </div>
        {readableEvents.length ? (
          <div className="mt-2 max-h-48 space-y-1.5 overflow-y-auto" data-testid="agent-readable-trace">
            {readableEvents.map((item, index) => (
              <div key={`${item.label}-${index}`} className="min-w-0">
                <span className="font-medium text-ink">{item.label}</span>
                {item.detail ? <span className="block truncate">{item.detail}</span> : null}
              </div>
            ))}
          </div>
        ) : null}
      </details>
    </div>
  );
}

function AgentRelayTheater({
  routeItems,
  displayedSteps,
}: {
  routeItems: StructuredRouteItem[];
  displayedSteps: AgentStep[];
}) {
  const items = routeItems.slice(0, 6).map((item, index) => {
    const fallback = displayedSteps[Math.min(index, Math.max(displayedSteps.length - 1, 0))];
    return {
      ...item,
      status: item.status ?? fallback?.status ?? "complete",
      detail: normalizeLearningTraceText(item.detail || fallback?.description || "接收上一阶段结果并继续处理。"),
    };
  });

  return (
    <div className="mt-2 flex gap-1.5 overflow-x-auto pb-0.5" data-testid="agent-relay-theater">
      {items.map((item, index) => (
        <div key={`${item.key}-theater`} className="flex shrink-0 items-center gap-1.5" title={item.detail}>
          <span className={`inline-flex h-7 max-w-[10rem] items-center gap-1.5 rounded-md border px-2 font-medium ${routeChipTone(item.status)}`}>
            <span className={`h-1.5 w-1.5 shrink-0 rounded-sm ${routeDotTone(item.status)}`} />
            <span className="truncate">{item.label}</span>
          </span>
          {index < items.length - 1 ? <ChevronRight size={13} className="text-slate-300" /> : null}
        </div>
      ))}
    </div>
  );
}

function CompactTag({ children, tone = "neutral" }: { children: string; tone?: "brand" | "neutral" }) {
  return (
    <span
      className={`rounded-md px-1.5 py-0.5 font-medium ${
        tone === "brand" ? "bg-tint-lavender text-brand-purple" : "bg-canvas text-slate-500"
      }`}
    >
      {children}
    </span>
  );
}

function AgentStepRow({ step, index }: { step: AgentStep; index: number }) {
  const Icon = step.icon;
  const title = learnerRoleName(step.title);
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18, delay: Math.min(index * 0.03, 0.12) }}
      className={`dt-dynamic-panel grid grid-cols-[2rem_minmax(0,1fr)] gap-2 rounded-lg border px-2.5 py-2 ${
        step.status === "running"
          ? "border-brand-purple-300 bg-tint-lavender"
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
          <span className="font-medium text-ink">{title}</span>
          <span className="text-xs text-slate-500">{statusText(step.status)}</span>
        </span>
        <span className="mt-0.5 block truncate text-xs text-slate-500">
          {normalizeLearningTraceText(step.detail || step.description)}
        </span>
        {step.tools.length ? (
          <span className="mt-1 flex flex-wrap gap-1">
            {step.tools.slice(0, 4).map((tool) => (
              <span key={tool} className="rounded-md bg-white px-1.5 py-0.5 text-[11px] text-brand-blue">
                {toolDisplayName(tool)}
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
  const readable = normalizeTraceContent(content);
  if (readable.length > 120) return `${readable.slice(0, 120)}...`;
  return readable;
}

function getToolName(event: StreamEvent) {
  return getToolNameFromEvent(event);
}

function buildReadableTraceItems(events: StreamEvent[], status: "streaming" | "done" | "error" = "done") {
  const items: ReadableTraceItem[] = [];
  const readableSource = status === "done" || hasTerminalEvent(events) ? compactCompletedTraceEvents(events) : events;

  readableSource.forEach((event) => {
    const content = meaningfulContent(event);
    const profilePrompt = metadataText(event.metadata, "rewritten_prompt");

    if (event.type === "error") {
      items.push({ label: "遇到异常", detail: content || "某个步骤没有顺利完成。" });
      return;
    }
    if (event.metadata?.profile_guided && profilePrompt) {
      items.push({ label: "按你情况调整", detail: `已改成：${profilePrompt}` });
    }
    if (event.type === "tool_call") {
      const copy = getToolTraceCopy(event, "call");
      items.push({ label: copy.title, detail: content || copy.detail });
      return;
    }
    if (event.type === "tool_result") {
      const copy = getToolTraceCopy(event, "result");
      items.push({ label: copy.title, detail: content || copy.detail });
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

function findStructuredRoute(events: StreamEvent[]): StructuredRouteItem[] {
  for (const event of events) {
    const route = routeFromMetadataValue(event.metadata?.collaboration_route);
    if (route.length) return route;
  }
  for (const event of events) {
    const route = routeFromMetadataValue(event.metadata?.agent_chain);
    if (route.length) return route;
  }
  return [];
}

function routeFromMetadataValue(value: unknown): StructuredRouteItem[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item, index): StructuredRouteItem | null => {
      if (!item || typeof item !== "object") return null;
      const record = item as Record<string, unknown>;
      const label = String(record.label ?? record.title ?? record.name ?? "").trim();
      const detail = String(record.detail ?? record.description ?? record.summary ?? "").trim();
      const key = String(record.key ?? record.id ?? label ?? `route-${index}`).trim();
      if (!label && !detail) return null;
      const status = normalizeRouteStatus(record.status);
      return {
        key: key || `route-${index}`,
        label: learnerRoleName(label || detail || "学习步骤"),
        detail: normalizeLearningTraceText(detail),
        ...(status ? { status } : {}),
      };
    })
    .filter((item): item is StructuredRouteItem => item !== null)
    .slice(0, 6);
}

function normalizeRouteStatus(value: unknown): StepStatus | undefined {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (normalized === "pending") return "pending";
  if (normalized === "running" || normalized === "active" || normalized === "working") return "running";
  if (normalized === "complete" || normalized === "completed" || normalized === "done" || normalized === "success") return "complete";
  if (normalized === "error" || normalized === "failed" || normalized === "failure") return "error";
  return undefined;
}

function findCollaborationSummary(events: StreamEvent[]) {
  for (const event of events) {
    const summary = metadataText(event.metadata, "collaboration_summary");
    if (summary) return summary.length > 120 ? `${summary.slice(0, 120).trim()}...` : summary;
  }
  return "";
}

function normalizeCollaborationSummary(summary: string) {
  const value = summary.trim();
  if (!value) return "";
  const profileHandoff = value.match(/画像先提供学习依据，协调智能体再唤醒\s*(.+?)\s*接力。?/);
  if (profileHandoff) return `已结合学习记录，进入${agentDisplayName(profileHandoff[1])}流程。`;
  const handoff = value.match(/协调智能体根据当前请求唤醒\s*(.+?)\s*接力。?/);
  if (handoff) return `已识别任务，进入${agentDisplayName(handoff[1])}流程。`;
  return normalizeLearningTraceText(value);
}

function learnerRoleName(title: string) {
  const normalized = title.trim();
  const labels: Record<string, string> = {
    对话协调智能体: "理解任务",
    工具检索智能体: "补充资料",
    工具智能体: "补充资料",
    讲解智能体: "组织讲解",
    画像提示智能体: "学习记录",
    学习画像智能体: "学习记录",
    视频检索智能体: "查找视频",
    图片检索智能体: "查找图片",
    筛选排序智能体: "筛选排序",
    筛选智能体: "筛选排序",
    资源卡片智能体: "整理卡片",
    学习卡片智能体: "整理卡片",
    图片卡片智能体: "整理卡片",
    规划智能体: "规划解法",
    解题规划智能体: "规划解法",
    解题智能体: "推理解题",
    验证智能体: "校验答案",
    校验智能体: "校验答案",
    修复智能体: "修正题目",
    评估智能体: "评估反馈",
    问题改写智能体: "改写问题",
    主题拆解智能体: "拆解主题",
    资料检索智能体: "查找资料",
    报告智能体: "整理报告",
    知识点分析智能体: "分析知识点",
    出题智能体: "生成练习",
    题目本智能体: "整理练习",
    结构分析智能体: "分析结构",
    图解设计智能体: "设计图解",
    渲染智能体: "生成结果",
    可视化渲染智能体: "生成图解",
    概念分析智能体: "分析概念",
    分镜设计智能体: "设计分镜",
    分镜智能体: "设计分镜",
    "Manim 编码智能体": "生成脚本",
    渲染检查智能体: "检查渲染",
    总结智能体: "整理结果",
  };
  if (labels[normalized]) return labels[normalized];
  const lower = normalized.toLowerCase();
  if (lower.includes("profile")) return "学习记录";
  if (lower.includes("coordinator") || lower.includes("dialogue")) return "理解任务";
  if (lower.includes("knowledge") || lower.includes("visual")) return "知识图解";
  if (lower.includes("video")) return "查找视频";
  if (lower.includes("image") || lower.includes("picture")) return "查找图片";
  if (lower.includes("rank") || lower.includes("filter")) return "筛选排序";
  if (lower.includes("question")) return "生成练习";
  if (lower.includes("solve")) return "推理解题";
  if (lower.includes("research")) return "查找资料";
  if (lower.includes("tool") || lower.includes("retrieval") || lower.includes("search")) return "补充资料";
  if (lower.includes("writer") || lower.includes("tutor") || lower.includes("explain")) return "组织讲解";
  return normalizeLearningTraceText(normalized).replace(/步骤$/, "");
}

function normalizeLearningTraceText(text: string) {
  return text
    .replace(/学习画像|用户画像|画像/g, "学习记录")
    .replace(/智能体/g, "步骤")
    .replace(/知识库/g, "资料库")
    .replace(/检索/g, "查找")
    .replace(/唤醒/g, "进入")
    .replace(/接力/g, "继续")
    .replace(/专门步骤/g, "合适步骤")
    .replace(/工具/g, "辅助功能")
    .replace(/\s*Agent/gi, "")
    .trim();
}

function toolDisplayName(tool: string) {
  return getToolDisplayName(tool);
}

function normalizeTraceContent(content: string) {
  const awakened = content.match(/^awakened\s+(.+?)\s+agent\.?$/i);
  if (awakened) {
    return `已进入${agentDisplayName(awakened[1])}流程。`;
  }
  return normalizeLearningTraceText(content);
}

function agentDisplayName(value: string) {
  const normalized = value.trim().toLowerCase();
  if (normalized.includes("knowledge") || normalized.includes("visual")) return "知识图解";
  if (normalized.includes("video")) return "视频查找";
  if (normalized.includes("image")) return "图片查找";
  if (normalized.includes("math") || normalized.includes("animator")) return "数学动画";
  if (normalized.includes("question")) return "练习生成";
  if (normalized.includes("solve")) return "深度求解";
  if (normalized.includes("research")) return "学习研究";
  return learnerRoleName(value.trim());
}

function readableStageLabel(event: StreamEvent) {
  const stage = String(event.stage || "").toLowerCase();
  if (stage.includes("coordinating") || stage.includes("planning") || stage.includes("thinking")) return "识别任务";
  if (stage.includes("retrieval") || stage.includes("search")) return "查找资料";
  if (stage.includes("reasoning") || stage.includes("solve")) return "推理整理";
  if (stage.includes("writing") || stage.includes("responding") || stage.includes("final")) return "组织回答";
  if (stage.includes("render") || stage.includes("visual")) return "生成产物";
  return "步骤更新";
}

function iconTone(status: StepStatus) {
  if (status === "running") return "bg-white text-brand-purple";
  if (status === "complete") return "bg-tint-lavender text-brand-purple";
  if (status === "error") return "bg-white text-brand-red";
  return "bg-canvas text-slate-500";
}

function routeChipTone(status: StepStatus) {
  if (status === "running") return "border-brand-purple-300 bg-white text-brand-purple";
  if (status === "complete") return "border-line bg-white text-ink";
  if (status === "error") return "border-red-200 bg-white text-brand-red";
  return "border-line bg-white text-slate-500";
}

function routeDotTone(status: StepStatus) {
  if (status === "running") return "bg-brand-blue animate-pulse";
  if (status === "complete") return "bg-brand-purple";
  if (status === "error") return "bg-brand-red";
  return "bg-slate-300";
}

function summarizeCollaboration(steps: AgentStep[], profileAware: boolean) {
  const completed = steps.filter((step) => step.status === "complete").length;
  const running = steps.find((step) => step.status === "running");
  if (running) return `${learnerRoleName(running.title)}正在处理，前序结果会继续进入下一步。`;
  if (completed > 1) return profileAware ? "已结合学习记录，由多个学习步骤完成。" : "多个学习步骤已按顺序完成。";
  return profileAware ? "已带入学习记录，正在等待下一步信号。" : "系统会按任务自动选择下一步。";
}

function statusText(status: StepStatus) {
  return {
    pending: "待命",
    running: "进行中",
    complete: "已完成",
    error: "异常",
  }[status];
}
