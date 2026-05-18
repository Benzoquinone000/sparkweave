import { CalendarDays, Loader2 } from "lucide-react";
import { motion } from "framer-motion";

import { Badge } from "@/components/ui/Badge";
import {
  effectStatusTone,
  guideTaskTitle,
  planStatusLabel,
  planStatusTone,
} from "@/lib/guideDisplay";
import type { GuideV2StudyPlan } from "@/lib/types";
import { EvalMini, ProgressBar } from "./GuideMetrics";

export function GuideStudyPlanPanel({
  plan,
  loading,
}: {
  plan: GuideV2StudyPlan | null;
  loading: boolean;
}) {
  const blocks = plan?.blocks ?? [];
  const checkpoints = plan?.checkpoints ?? [];
  const remainingMinutes = Number(plan?.remaining_minutes ?? 0);
  const effectAssessment = plan?.effect_assessment;
  return (
    <section className="rounded-lg border border-line bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="grid size-10 place-items-center rounded-lg border border-brand-purple-300 bg-tint-lavender text-brand-purple">
            <CalendarDays size={20} />
          </div>
          <div>
            <h2 className="text-base font-semibold text-ink">学习日程与检查点</h2>
            <p className="mt-1 text-sm leading-6 text-slate-500">
              {plan?.summary || "创建路线后，这里会把任务拆成每次学习可执行的安排。"}
            </p>
          </div>
        </div>
        {loading ? (
          <Loader2 size={16} className="animate-spin text-brand-purple" />
        ) : (
          <Badge tone={blocks.length ? "brand" : "neutral"}>{blocks.length || 0} 次学习</Badge>
        )}
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <EvalMini label="单次预算" value={Number(plan?.daily_time_budget ?? 0)} suffix="m" />
        <EvalMini label="剩余时间" value={remainingMinutes} suffix="m" />
        <EvalMini label="检查点" value={checkpoints.length} />
      </div>
      {effectAssessment ? (
        <div className="mt-4 rounded-lg border border-line bg-canvas p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-semibold text-ink">路径调度依据</p>
            <Badge tone={effectStatusTone(effectAssessment.score)}>{effectAssessment.label || Number(effectAssessment.score ?? 0)}</Badge>
          </div>
          <p className="mt-2 text-xs leading-5 text-slate-600">
            {effectAssessment.summary || "学习日程会根据效果评估动态调整优先级。"}
          </p>
        </div>
      ) : null}

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        {blocks.slice(0, 4).map((block) => {
          const completed = Number(block.completed_tasks ?? 0);
          const total = Number(block.total_tasks ?? 0);
          const progress = total ? Math.round((completed / total) * 100) : 0;
          return (
            <motion.div
              key={block.id}
              className="rounded-lg border border-line bg-canvas p-4"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.16 }}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h3 className="text-sm font-semibold text-ink">{block.title}</h3>
                  <p className="mt-1 line-clamp-1 text-xs text-slate-500">{block.focus || "学习块"}</p>
                </div>
                <Badge tone={planStatusTone(block.status || "")}>{planStatusLabel(block.status || "")}</Badge>
              </div>
              <ProgressBar value={progress} className="mt-3" />
              <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
                <Badge tone="neutral">{block.estimated_minutes ?? 0} 分钟</Badge>
                <Badge tone="neutral">{completed}/{total} 任务</Badge>
              </div>
              <div className="mt-3 space-y-2">
                {(block.tasks ?? []).slice(0, 2).map((task, taskIndex) => (
                  <p key={task.task_id || task.title} className="line-clamp-1 rounded-lg bg-white px-3 py-2 text-xs text-slate-600">
                    {guideTaskTitle(task, taskIndex)}
                  </p>
                ))}
              </div>
              {(block.recommended_actions ?? []).length ? (
                <p className="mt-3 text-xs leading-5 text-slate-600">{block.recommended_actions?.[0]}</p>
              ) : null}
            </motion.div>
          );
        })}
        {!blocks.length ? (
          <p className="rounded-lg border border-dashed border-line bg-canvas p-4 text-sm text-slate-500">
            暂无日程。先创建一条导学路线。
          </p>
        ) : null}
      </div>

      {checkpoints.length ? (
        <div className="mt-4 rounded-lg border border-line bg-canvas p-4">
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm font-semibold text-ink">下一次检查</p>
            <Badge tone={planStatusTone(String(plan?.next_checkpoint?.status || checkpoints[0]?.status || ""))}>
              {planStatusLabel(String(plan?.next_checkpoint?.status || checkpoints[0]?.status || ""))}
            </Badge>
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            {String(plan?.next_checkpoint?.title || checkpoints[0]?.title || "学习复盘")}
          </p>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            {String(plan?.next_checkpoint?.trigger || checkpoints[0]?.trigger || "完成当前学习块后检查。")}
          </p>
        </div>
      ) : null}

      {plan?.rules?.length ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {plan.rules.slice(0, 3).map((rule) => (
            <Badge key={rule} tone="neutral">{rule}</Badge>
          ))}
        </div>
      ) : null}
    </section>
  );
}
