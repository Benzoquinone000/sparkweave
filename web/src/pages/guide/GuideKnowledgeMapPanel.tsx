import { CheckCircle2 } from "lucide-react";
import { motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import {
  extractStringArray,
  guideDisplayText,
  guideTaskTitle,
  knowledgeNodeStyle,
  masteryStatusLabel,
  masteryTone,
  originLabel,
  originTone,
  scorePercent,
  taskTypeLabel,
} from "@/lib/guideDisplay";
import { questionDifficultyLabel } from "@/lib/learningLabels";
import type { GuideV2Task } from "@/lib/types";
import { EvalMini } from "./GuideMetrics";

export function GuideKnowledgeMapPanel({
  nodes,
  mastery,
  tasks,
  currentTask,
}: {
  nodes: Array<Record<string, unknown>>;
  mastery: Record<string, Record<string, unknown>>;
  tasks: GuideV2Task[];
  currentTask: GuideV2Task | null;
}) {
  const currentNodeId = currentTask?.node_id || "";
  const [selectedNodeId, setSelectedNodeId] = useState("");

  const items = useMemo(
    () =>
      nodes.map((node, index) => {
        const nodeId = readString(node, "node_id") || `N${index + 1}`;
        const nodeMastery = mastery[nodeId] ?? {};
        const nodeTasks = tasks.filter((task) => task.node_id === nodeId);
        const completedTasks = nodeTasks.filter((task) => task.status === "completed").length;
        const status = readString(nodeMastery, "status") || readString(node, "status") || "not_started";
        return {
          nodeId,
          index,
          title: guideNodeTitle(node, index),
          description: guideDisplayText(readString(node, "description"), "等待路线生成。"),
          difficulty: readString(node, "difficulty") || "medium",
          target: guideDisplayText(readString(node, "mastery_target")),
          prerequisites: extractStringArray(node.prerequisites),
          strategies: extractStringArray(node.resource_strategy),
          tags: extractStringArray(node.tags),
          status,
          displayStatus: deriveNodeDisplayStatus(status, nodeTasks, currentNodeId === nodeId),
          score: scorePercent(nodeMastery.mastery_score ?? nodeMastery.score ?? node.mastery_score),
          tasks: nodeTasks,
          completedTasks,
          isCurrent: currentNodeId === nodeId,
        };
      }),
    [currentNodeId, mastery, nodes, tasks],
  );

  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (!items.length) {
        setSelectedNodeId("");
        return;
      }
      setSelectedNodeId((current) => {
        if (current && items.some((item) => item.nodeId === current)) return current;
        return currentNodeId || items[0].nodeId;
      });
    }, 0);
    return () => window.clearTimeout(timer);
  }, [currentNodeId, items]);

  if (!items.length) {
    return <p className="mt-4 rounded-lg border border-dashed border-line bg-canvas p-4 text-sm text-slate-500">生成路线后展示知识地图。</p>;
  }

  const selected = items.find((item) => item.nodeId === selectedNodeId) ?? items[0];
  const masteredCount = items.filter((item) => item.status === "mastered").length;
  const currentIndex = Math.max(0, items.findIndex((item) => item.isCurrent));
  const averageMastery = Math.round(items.reduce((sum, item) => sum + item.score, 0) / items.length);
  const selectedDone = selected.status === "mastered" || (selected.tasks.length > 0 && selected.completedTasks === selected.tasks.length);

  return (
    <div className="mt-4 space-y-4">
      <div className="rounded-lg border border-brand-purple-300 bg-tint-lavender p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold text-brand-purple">Learning Map</p>
            <h3 className="mt-1 text-lg font-semibold text-ink">从起点到掌握的路线</h3>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-charcoal">
              当前在第 {currentIndex + 1} 步。点击任意知识点，可以查看它的目标、掌握度和对应任务。
            </p>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="rounded-lg border border-brand-purple-300 bg-white px-3 py-2">
              <p className="text-lg font-semibold text-ink">{items.length}</p>
              <p className="text-xs text-slate-500">知识点</p>
            </div>
            <div className="rounded-lg border border-brand-purple-300 bg-white px-3 py-2">
              <p className="text-lg font-semibold text-ink">{masteredCount}</p>
              <p className="text-xs text-slate-500">已掌握</p>
            </div>
            <div className="rounded-lg border border-brand-purple-300 bg-white px-3 py-2">
              <p className="text-lg font-semibold text-ink">{averageMastery}%</p>
              <p className="text-xs text-slate-500">平均</p>
            </div>
          </div>
        </div>
      </div>

      <MasteryTransitMap items={items} selectedNodeId={selected.nodeId} onSelect={setSelectedNodeId} />

      <div className="overflow-x-auto rounded-lg border border-line bg-white p-4 shadow-sm">
        <div className="flex min-w-max items-stretch">
          {items.map((item, index) => {
            const active = item.nodeId === selected.nodeId;
            const done = item.status === "mastered" || (item.tasks.length > 0 && item.completedTasks === item.tasks.length);
            const style = knowledgeNodeStyle(item.status, active, item.isCurrent, done);
            return (
              <div key={item.nodeId} className="flex items-center">
                <button
                  type="button"
                  onClick={() => setSelectedNodeId(item.nodeId)}
                  className={`min-h-40 w-40 rounded-lg border p-3 text-left transition hover:shadow-sm ${style.card}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className={`flex size-9 items-center justify-center rounded-lg border text-sm font-semibold ${style.dot}`}>
                      {done ? <CheckCircle2 size={17} /> : index + 1}
                    </span>
                    <Badge tone={item.isCurrent ? "brand" : masteryDisplayTone(item.displayStatus)}>{item.isCurrent ? "当前" : masteryDisplayLabel(item.displayStatus)}</Badge>
                  </div>
                  <span className="mt-3 block line-clamp-2 min-h-10 text-sm font-semibold leading-5 text-ink">{item.title}</span>
                  <span className="mt-2 block line-clamp-2 text-xs leading-5 text-slate-500">{item.description}</span>
                  <div className="mt-3">
                    <div className="flex items-center justify-between text-xs text-slate-500">
                      <span>掌握</span>
                      <span>{item.score}%</span>
                    </div>
                    <div className="mt-1 h-1.5 overflow-hidden rounded-sm bg-slate-100">
                      <div className={`h-full rounded-sm ${style.bar}`} style={{ width: `${item.score}%` }} />
                    </div>
                  </div>
                  <span className="mt-3 block text-xs text-slate-500">{item.completedTasks}/{item.tasks.length || 0} 个任务完成</span>
                </button>
                {index < items.length - 1 ? (
                  <div className="flex h-full items-center px-2">
                    <div className={`h-0.5 w-8 ${done ? "bg-emerald-300" : "bg-slate-200"}`} />
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      </div>

      <motion.div
        key={selected.nodeId}
        className="grid gap-4 rounded-lg border border-line bg-white p-4 shadow-sm lg:grid-cols-[minmax(0,1fr)_280px]"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.18 }}
      >
        <div className="rounded-lg border border-line bg-canvas p-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={selected.isCurrent ? "brand" : masteryDisplayTone(selected.displayStatus)}>
              {selected.isCurrent ? "当前" : masteryDisplayLabel(selected.displayStatus)}
            </Badge>
            <Badge tone="neutral">第 {selected.index + 1} 步</Badge>
            <Badge tone="neutral">{questionDifficultyLabel(selected.difficulty)}</Badge>
          </div>
          <h3 className="mt-3 text-lg font-semibold text-ink">{selected.title}</h3>
          <p className="mt-2 text-sm leading-6 text-slate-600">{selected.description}</p>
          {selected.target ? (
            <div className="mt-4 rounded-lg border border-brand-purple-300 bg-white p-3">
              <p className="text-xs font-semibold text-brand-purple">掌握目标</p>
              <p className="mt-1 text-sm leading-6 text-charcoal">{selected.target}</p>
            </div>
          ) : null}
          <div className="mt-4 flex flex-wrap gap-2">
            {selected.prerequisites.slice(0, 4).map((item) => (
              <Badge key={`pre-${item}`} tone="neutral">前置：{item}</Badge>
            ))}
            {selected.strategies.slice(0, 4).map((item) => (
              <Badge key={`strategy-${item}`} tone="brand">{item}</Badge>
            ))}
            {!selected.prerequisites.length && !selected.strategies.length && selected.tags.slice(0, 4).map((item) => (
              <Badge key={`tag-${item}`} tone="neutral">{item}</Badge>
            ))}
          </div>
        </div>
        <div className="rounded-lg border border-line bg-white p-4">
          <div className="grid place-items-center">
            <div className="relative grid size-28 place-items-center rounded-lg border border-line bg-canvas">
              <div
                className="absolute inset-2 rounded-lg"
                style={{ background: `conic-gradient(#0F766E ${selected.score * 3.6}deg, #E2E8F0 0deg)` }}
              />
              <div className="relative grid size-20 place-items-center rounded-lg border border-line bg-white">
                <div className="text-center">
                  <p className="text-2xl font-semibold text-ink">{selected.score}%</p>
                  <p className="text-xs text-slate-500">掌握</p>
                </div>
              </div>
            </div>
            <Badge tone={selectedDone ? "success" : masteryDisplayTone(selected.displayStatus)}>{selectedDone ? "节点完成" : masteryDisplayLabel(selected.displayStatus)}</Badge>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <EvalMini label="任务" value={selected.tasks.length} />
            <EvalMini label="完成" value={selected.completedTasks} />
          </div>
          <p className="mt-3 rounded-lg border border-line bg-canvas p-2 text-xs leading-5 text-slate-600">
            建议：先完成当前节点任务，再进入下一步，路线会根据练习反馈自动调整。
          </p>
        </div>
      </motion.div>

      <div className="rounded-lg border border-line bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold text-ink">行动清单</h3>
            <p className="mt-1 text-xs text-slate-500">只展示当前选中知识点的任务。</p>
          </div>
          <Badge tone="neutral">{selected.tasks.length} 个</Badge>
        </div>
        <div className="mt-3 space-y-2">
          {selected.tasks.map((task) => (
            <GuideTaskRow key={task.task_id} task={task} active={task.task_id === currentTask?.task_id} />
          ))}
          {!selected.tasks.length ? (
            <p className="rounded-lg bg-canvas p-3 text-sm text-slate-500">这个知识点暂时没有单独任务。</p>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function MasteryTransitMap({
  items,
  selectedNodeId,
  onSelect,
}: {
  items: Array<{
    nodeId: string;
    index: number;
    title: string;
    displayStatus: string;
    score: number;
    isCurrent: boolean;
  }>;
  selectedNodeId: string;
  onSelect: (nodeId: string) => void;
}) {
  const summary = [
    { status: "mastered", label: "已掌握", count: items.filter((item) => item.displayStatus === "mastered").length },
    { status: "learning", label: "正在学", count: items.filter((item) => item.displayStatus === "learning").length },
    { status: "not_started", label: "可开始", count: items.filter((item) => item.displayStatus === "not_started").length },
    { status: "needs_support", label: "需补救", count: items.filter((item) => item.displayStatus === "needs_support").length },
    { status: "retest", label: "待复测", count: items.filter((item) => item.displayStatus === "retest").length },
  ];

  return (
    <div className="rounded-lg border border-line bg-white p-4 shadow-sm" data-testid="guide-knowledge-transit-map">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">知识掌握地铁图</Badge>
            <span className="text-sm font-semibold text-ink">每个站点都是一个可评估知识点</span>
          </div>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            颜色代表掌握状态，复测和补救会直接插回路线，让个性化路径调整变得可见。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {summary.map((item) => (
            <Badge key={item.status} tone={masteryDisplayTone(item.status)}>
              {item.label} {item.count}
            </Badge>
          ))}
        </div>
      </div>
      <div className="mt-4 overflow-x-auto pb-1">
        <div className="flex min-w-max items-start">
          {items.map((item, index) => {
            const selected = item.nodeId === selectedNodeId;
            return (
              <div key={`${item.nodeId}-transit`} className="flex items-start">
                <button
                  type="button"
                  onClick={() => onSelect(item.nodeId)}
                  className="group min-w-[8rem] text-left"
                  title={item.title}
                >
                  <div className="flex items-center">
                    <span
                      className={`grid h-10 w-10 place-items-center rounded-lg border text-sm font-semibold transition ${masteryStationTone(item.displayStatus, selected, item.isCurrent)}`}
                    >
                      {item.displayStatus === "mastered" ? <CheckCircle2 size={17} /> : item.index + 1}
                    </span>
                    <span className={`h-0.5 w-20 ${index < items.length - 1 ? masteryLineTone(item.displayStatus) : "bg-transparent"}`} />
                  </div>
                  <p className="mt-2 line-clamp-2 max-w-[7.25rem] text-xs font-semibold leading-5 text-ink">{item.title}</p>
                  <div className="mt-1 flex items-center gap-1.5">
                    <span className="h-1.5 flex-1 overflow-hidden rounded-sm bg-slate-100">
                      <span className={`block h-full rounded-sm ${masteryBarTone(item.displayStatus)}`} style={{ width: `${item.score}%` }} />
                    </span>
                    <span className="text-[11px] text-slate-500">{item.score}%</span>
                  </div>
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export function GuideTaskRow({ task, active }: { task: GuideV2Task; active: boolean }) {
  return (
    <div className={`flex items-start gap-3 rounded-lg border p-3 ${active ? "border-brand-purple-300 bg-tint-lavender" : "border-line bg-white"}`}>
      <div className="flex shrink-0 flex-wrap gap-2">
        <Badge tone={task.status === "completed" ? "success" : task.status === "skipped" ? "neutral" : active ? "brand" : "neutral"}>{taskTypeLabel(task.type)}</Badge>
        {task.origin && task.origin !== "planned" ? <Badge tone={originTone(task.origin)}>{originLabel(task.origin)}</Badge> : null}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-ink">{guideTaskTitle(task)}</p>
        <p className="mt-1 line-clamp-2 text-sm leading-6 text-slate-500">{guideDisplayText(task.instruction, "完成当前小任务，系统会继续安排下一步。")}</p>
        {task.artifact_refs?.length ? <p className="mt-1 text-xs text-brand-purple">{task.artifact_refs.length} 个资源已生成</p> : null}
      </div>
      <span className="shrink-0 text-xs text-slate-500">{task.estimated_minutes ?? 8}m</span>
    </div>
  );
}

function guideNodeTitle(node: Record<string, unknown>, index: number) {
  const title = guideDisplayText(readString(node, "title"), "");
  if (title && title !== "学习内容") return title;
  return `知识点 ${index + 1}`;
}

function readString(source: Record<string, unknown>, key: string) {
  const value = source[key];
  return typeof value === "string" ? value : value == null ? "" : String(value);
}

function deriveNodeDisplayStatus(status: string, tasks: GuideV2Task[], current: boolean) {
  if (status === "mastered" || status === "needs_support") return status;
  const hasOpenRetest = tasks.some((task) => task.origin === "adaptive_retest" && task.status !== "completed");
  if (hasOpenRetest) return "retest";
  const hasOpenRemediation = tasks.some((task) => task.origin === "adaptive_remediation" && task.status !== "completed");
  if (hasOpenRemediation) return "needs_support";
  if (current) return "learning";
  return status || "not_started";
}

function masteryDisplayLabel(status: string) {
  if (status === "retest") return "待复测";
  if (status === "needs_support") return "需补救";
  if (status === "not_started") return "可开始";
  return masteryStatusLabel(status);
}

function masteryDisplayTone(status: string) {
  if (status === "retest") return "brand";
  return masteryTone(status);
}

function masteryStationTone(status: string, selected: boolean, current: boolean) {
  if (selected) return "border-brand-purple bg-brand-purple text-white shadow-sm";
  if (current) return "border-blue-600 bg-blue-600 text-white";
  if (status === "mastered") return "border-emerald-600 bg-emerald-600 text-white";
  if (status === "needs_support") return "border-amber-500 bg-amber-500 text-white";
  if (status === "retest") return "border-brand-purple-300 bg-tint-lavender text-brand-purple";
  return "border-line bg-canvas text-slate-500 group-hover:border-brand-purple-300";
}

function masteryLineTone(status: string) {
  if (status === "mastered") return "bg-emerald-300";
  if (status === "needs_support") return "bg-amber-200";
  if (status === "retest") return "bg-brand-purple-300";
  if (status === "learning") return "bg-blue-200";
  return "bg-slate-200";
}

function masteryBarTone(status: string) {
  if (status === "mastered") return "bg-emerald-600";
  if (status === "needs_support") return "bg-amber-500";
  if (status === "retest") return "bg-brand-purple";
  if (status === "learning") return "bg-blue-600";
  return "bg-slate-300";
}
