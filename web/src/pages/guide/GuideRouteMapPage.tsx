import { ArrowLeft, ArrowRight, CheckCircle2, CircleDot } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { guideTaskTitle, planStatusLabel, planStatusTone } from "@/lib/guideDisplay";
import type { GuideV2StudyPlan, GuideV2Task } from "@/lib/types";
import { GuideSubPageFrame } from "./GuideSubPageFrame";

export function GuideRouteMapPage({
  plan,
  loading,
  metadata,
  tasks,
  currentTask,
  onBack,
}: {
  plan: GuideV2StudyPlan | null;
  loading: boolean;
  metadata: Record<string, unknown>;
  highlightedSectionId: string | null;
  nodes: Array<Record<string, unknown>>;
  mastery: Record<string, Record<string, unknown>>;
  tasks: GuideV2Task[];
  currentTask: GuideV2Task | null;
  onBack: () => void;
}) {
  const orderedTasks = tasks.length ? tasks : currentTask ? [currentTask] : [];
  const currentTaskId = currentTask?.task_id ?? null;
  const currentIndex = Math.max(0, orderedTasks.findIndex((task) => task.task_id === currentTaskId));
  const [manualSelection, setManualSelection] = useState<{ taskId: string | null; index: number } | null>(null);
  const requestedActiveIndex = manualSelection?.taskId === currentTaskId ? manualSelection.index : currentIndex;
  const activeIndex = Math.min(requestedActiveIndex, Math.max(orderedTasks.length - 1, 0));
  const activeTask = orderedTasks[activeIndex];
  const completedCount = orderedTasks.filter((task) => task.status === "completed").length;
  const courseTitle = useMemo(() => String(metadata?.course_name || metadata?.title || "学习路线"), [metadata]);

  const selectTaskIndex = (index: number) => {
    setManualSelection({ taskId: currentTaskId, index: Math.min(Math.max(index, 0), Math.max(orderedTasks.length - 1, 0)) });
  };

  return (
    <GuideSubPageFrame
      eyebrow="完整路线"
      title="学习路线"
      description="一页只看一个节点；回到主流程继续做当前任务。"
      onBack={onBack}
    >
      <div className="flex h-full min-h-0 flex-col gap-3">
        <section className="shrink-0 rounded-lg border border-line bg-canvas p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="min-w-0">
              <p className="text-xs font-semibold text-steel">{courseTitle}</p>
              <h3 className="mt-1 line-clamp-1 text-base font-semibold text-ink">
                {plan?.summary || "按当前目标生成的学习路线"}
              </h3>
            </div>
            <Badge tone={loading ? "neutral" : "brand"}>{loading ? "读取中" : `${completedCount}/${orderedTasks.length} 完成`}</Badge>
          </div>
          <div className="mt-3 h-1.5 overflow-hidden rounded-lg bg-slate-100">
            <div
              className="h-full rounded-lg bg-brand-purple transition-all"
              style={{ width: `${orderedTasks.length ? (completedCount / orderedTasks.length) * 100 : 0}%` }}
            />
          </div>
        </section>

        {activeTask ? (
          <section className="flex min-h-0 flex-1 flex-col justify-center rounded-lg border border-line bg-white p-5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={activeTask.task_id === currentTask?.task_id ? "brand" : planStatusTone(activeTask.status || "pending")}>
                {activeTask.task_id === currentTask?.task_id ? "当前" : planStatusLabel(activeTask.status || "pending")}
              </Badge>
              <Badge tone="neutral">
                第 {activeIndex + 1} 步 / 共 {orderedTasks.length} 步
              </Badge>
              {activeTask.estimated_minutes ? <Badge tone="neutral">{activeTask.estimated_minutes} 分钟</Badge> : null}
            </div>
            <h3 className="mt-4 text-xl font-semibold leading-8 text-ink">{guideTaskTitle(activeTask, activeIndex)}</h3>
            <p className="mt-3 line-clamp-3 text-sm leading-6 text-slate-600">{activeTask.instruction || "完成这一小步后，回到主流程提交学习记录。"}</p>
            <div className="mt-4 grid gap-2 sm:grid-cols-2">
              {(activeTask.success_criteria ?? []).slice(0, 2).map((item) => (
                <div key={item} className="flex items-start gap-2 rounded-lg border border-line bg-canvas p-3 text-sm text-slate-600">
                  <CheckCircle2 size={15} className="mt-1 shrink-0 text-brand-purple" />
                  <span className="line-clamp-2">{item}</span>
                </div>
              ))}
              {!activeTask.success_criteria?.length ? (
                <div className="flex items-start gap-2 rounded-lg border border-line bg-canvas p-3 text-sm text-slate-600">
                  <CircleDot size={15} className="mt-1 shrink-0 text-brand-purple" />
                  <span>完成后写一句反思，系统会调整下一步。</span>
                </div>
              ) : null}
            </div>
          </section>
        ) : (
          <section className="grid min-h-0 flex-1 place-items-center rounded-lg border border-line bg-white p-5 text-center">
            <div>
              <p className="text-sm font-semibold text-ink">路线还在生成</p>
              <p className="mt-1 text-xs text-slate-500">稍后回来查看。</p>
            </div>
          </section>
        )}

        <div className="grid shrink-0 gap-2 sm:grid-cols-[auto_minmax(0,1fr)_auto]">
          <Button tone="secondary" disabled={activeIndex <= 0} onClick={() => selectTaskIndex(activeIndex - 1)}>
            <ArrowLeft size={16} />
            上一步
          </Button>
          <Button tone="primary" onClick={onBack}>
            回当前任务
          </Button>
          <Button
            tone="secondary"
            disabled={activeIndex >= orderedTasks.length - 1}
            onClick={() => selectTaskIndex(activeIndex + 1)}
          >
            下一步
            <ArrowRight size={16} />
          </Button>
        </div>
      </div>
    </GuideSubPageFrame>
  );
}
