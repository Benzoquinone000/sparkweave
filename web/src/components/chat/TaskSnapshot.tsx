import { Activity, Boxes, CheckCircle2, Route, Sparkles } from "lucide-react";
import { useMemo } from "react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { extractMathAnimatorResult, extractVisualizeResult } from "@/lib/capabilityResults";
import { getCapability } from "@/lib/capabilities";
import { getMessageCapability, getMessageDisplayContent } from "@/lib/chatMessages";
import { hasNotebookAssetOutput } from "@/lib/notebookAssets";
import { extractQuizQuestions } from "@/lib/quiz";
import type { ChatMessage, StreamEvent } from "@/lib/types";

export function TaskSnapshot({
  messages,
  status,
  stageLabel,
  sessionId,
  onSaveMessage,
}: {
  messages: ChatMessage[];
  status: "idle" | "connecting" | "streaming" | "error";
  stageLabel: string;
  sessionId: string | null;
  turnId: string | null;
  onSaveMessage: (message: ChatMessage) => void;
}) {
  const assistant = useMemo(() => [...messages].reverse().find((message) => message.role === "assistant") ?? null, [messages]);
  const effectiveCapability = assistant ? getMessageCapability(assistant) : undefined;
  const capability = effectiveCapability ? getCapability(effectiveCapability) : null;
  const resultEvent = useMemo(() => [...(assistant?.events ?? [])].reverse().find((event) => event.type === "result"), [assistant?.events]);
  const displayContent = assistant ? getMessageDisplayContent(assistant) : "";
  const quizQuestions = effectiveCapability === "deep_question" ? extractQuizQuestions(resultEvent?.metadata) : null;
  const visualizeResult = effectiveCapability === "visualize" ? extractVisualizeResult(resultEvent?.metadata) : null;
  const mathResult = effectiveCapability === "math_animator" ? extractMathAnimatorResult(resultEvent?.metadata) : null;
  const traceEvents = useMemo(() => getTraceEvents(assistant), [assistant]);
  const canSaveAsset = assistant ? hasNotebookAssetOutput(assistant) : false;
  const terminalResultReady = Boolean(assistant?.events?.some((event) => event.type === "result" || event.type === "done"));
  const output = getOutputLabel({
    displayContent,
    quizCount: quizQuestions?.length ?? 0,
    visualizeType: visualizeResult?.render_type,
    mathArtifactCount: mathResult?.artifacts?.length ?? 0,
  });

  return (
    <section className="rounded-lg border border-line bg-white p-3" data-testid="chat-task-snapshot">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Activity size={17} className="text-brand-blue" />
            <h2 className="text-sm font-semibold text-ink" aria-label="任务快照">
              当前学习
            </h2>
          </div>
          <p className="mt-1 text-xs leading-5 text-slate-500">回答进度会在这里同步。</p>
        </div>
        <Badge tone={status === "error" ? "danger" : terminalResultReady ? "success" : status === "streaming" || status === "connecting" ? "warning" : "neutral"}>
          {terminalResultReady ? "已完成" : formatStatus(status)}
        </Badge>
      </div>

      <div className="mt-3 grid gap-1.5">
        <SnapshotRow icon={<Sparkles size={15} />} label="方式" value={capability?.label || "等待选择"} />
        <SnapshotRow icon={<Route size={15} />} label="进度" value={terminalResultReady ? "已完成" : stageLabel} />
        <SnapshotRow icon={<Boxes size={15} />} label="结果" value={output} />
      </div>

      {traceEvents.length ? (
        <div className="mt-3 rounded-lg border border-line bg-canvas p-3">
          <p className="text-xs font-semibold text-slate-500">协作状态</p>
          <div className="mt-3 space-y-2">
            {traceEvents.map((event, index) => {
              const trace = formatTraceEvent(event);
              return (
                <div key={`${event.seq ?? index}-${event.type}`} className="flex gap-2 text-xs leading-5 text-slate-600">
                  <span
                    className={`mt-1 h-2 w-2 shrink-0 rounded-sm ${
                      trace.tone === "success" ? "bg-brand-teal" : trace.tone === "danger" ? "bg-brand-red" : "bg-brand-blue"
                    }`}
                  />
                  <span className="min-w-0">
                    <span className="font-medium text-ink">{trace.title}</span>
                    {trace.detail ? <span> · {trace.detail}</span> : null}
                    {trace.content ? <span className="block truncate text-slate-500">{trace.content}</span> : null}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      ) : null}

      {assistant && canSaveAsset ? (
        <Button
          tone="primary"
          className="mt-3 w-full"
          onClick={() => onSaveMessage({ ...assistant, content: displayContent })}
          aria-label="保存当前结果"
        >
          <CheckCircle2 size={16} />
          保存到笔记
        </Button>
      ) : (
        <p className="mt-3 rounded-lg border border-dashed border-line bg-canvas p-3 text-xs leading-5 text-slate-500">
          发送后会显示答案、题目、图表或动画结果。
        </p>
      )}
      {sessionId ? <span className="dt-test-legacy">会话 {sessionId}</span> : null}
    </section>
  );
}

function SnapshotRow({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg bg-canvas px-2.5 py-1.5 text-sm">
      <span className="flex items-center gap-2 text-slate-500">
        <span className="text-brand-teal">{icon}</span>
        {label}
      </span>
      <span className="min-w-0 truncate font-medium text-ink">{value}</span>
    </div>
  );
}

function formatStatus(status: "idle" | "connecting" | "streaming" | "error") {
  return {
    idle: "就绪",
    connecting: "连接中",
    streaming: "生成中",
    error: "异常",
  }[status];
}

function getTraceEvents(assistant: ChatMessage | null) {
  const events = (assistant?.events ?? []).filter((event) => event.type !== "content");
  const compacted =
    assistant?.status === "done" || hasTerminalEvent(events)
      ? compactCompletedSnapshotEvents(events)
      : events;
  return compacted.slice(-6);
}

function compactCompletedSnapshotEvents(events: StreamEvent[]) {
  const terminalIndex = findLastTerminalEventIndex(events);
  const cutoff = terminalIndex >= 0 ? terminalIndex : events.length - 1;
  return events.filter((event, index) => {
    if (index > cutoff && event.type !== "error") return false;
    if (event.type === "stage_start" || event.type === "stage_end" || event.type === "progress" || event.type === "thinking") {
      return false;
    }
    return !isGenericThinkingProgress(event) && !isThinkingBoundary(event);
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

function isGenericThinkingProgress(event: StreamEvent) {
  const stage = String(event.stage ?? "").toLowerCase();
  const content = String(event.content ?? "").trim().toLowerCase();
  return event.type === "progress" && stage === "thinking" && (!content || content === "thinking...");
}

function isThinkingBoundary(event: StreamEvent) {
  const stage = String(event.stage ?? "").toLowerCase();
  return stage === "thinking" && (event.type === "stage_start" || event.type === "stage_end");
}

function formatTraceEvent(event: StreamEvent): { title: string; detail?: string; content?: string; tone?: "default" | "success" | "danger" } {
  const stage = String(event.stage ?? "").toLowerCase();
  const content = getTraceContent(event);
  if (event.type === "stage_start" && stage === "thinking") return { title: "开始思考", content };
  if (event.type === "progress" && stage === "thinking") return { title: "思考中", content };
  if (event.type === "stage_end" && stage === "thinking") return { title: "思考完成", content, tone: "success" };
  if (event.type === "stage_start" && stage === "responding") return { title: "开始回答", content };
  if (event.type === "progress" && stage === "responding") return { title: "回答中", content };
  if (event.type === "stage_end" && stage === "responding") return { title: "回答完成", content, tone: "success" };
  if (event.type === "result") return { title: "最终回答", content, tone: "success" };
  if (event.type === "done") return { title: "已完成", content, tone: "success" };
  if (event.type === "error") return { title: "异常", content, tone: "danger" };
  if (event.type === "session") return { title: "建立会话", content };
  if (event.type === "tool_call") return { title: "调用工具", detail: getStageDetail(event.stage), content };
  if (event.type === "tool_result") return { title: "工具完成", detail: getStageDetail(event.stage), content, tone: "success" };
  if (event.type === "sources") return { title: "引用资料", content };
  return { title: "进度", detail: getStageDetail(event.stage || event.type), content };
}

function getTraceContent(event: StreamEvent) {
  const content = String(event.content ?? "").trim();
  if (!content || content.toLowerCase() === "thinking...") return "";
  return content;
}

function getStageDetail(stage?: string) {
  const value = String(stage ?? "").toLowerCase();
  if (!value) return undefined;
  if (value === "thinking") return "思考";
  if (value === "responding") return "回答";
  return stage;
}

function getOutputLabel({
  displayContent,
  quizCount,
  visualizeType,
  mathArtifactCount,
}: {
  displayContent: string;
  quizCount: number;
  visualizeType?: string;
  mathArtifactCount: number;
}) {
  if (quizCount) return `${quizCount} 道题`;
  if (visualizeType) return `可视化 · ${visualizeType}`;
  if (mathArtifactCount) return `${mathArtifactCount} 个动画产物`;
  if (displayContent) return "最终回答";
  return "等待产物";
}
