import { motion } from "framer-motion";
import { ArrowRight, CalendarDays, CheckCircle2, Clock3 } from "lucide-react";

import type { GuideV2Task } from "@/lib/types";
import type { GuideStage } from "./guideLearningStrategy";

export function GuideHero({
  primaryActionLabel,
  stageMessage,
  guideStage,
  currentTask,
  onEnterCurrentStep,
  onOpenSupport,
}: {
  primaryActionLabel: string;
  stageMessage: string;
  guideStage: GuideStage;
  currentTask: GuideV2Task | null;
  onEnterCurrentStep: () => void;
  onOpenSupport: () => void;
}) {
  const minutes = currentTask?.estimated_minutes ?? 8;
  const stageLabel = guideStage === "create" ? "先定目标" : guideStage === "diagnostic" ? "先做前测" : "继续当前任务";

  return (
    <motion.section
      className="p-0"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
    >
      <div className="grid gap-3.5 lg:grid-cols-[minmax(0,1fr)_292px]">
        <div className="min-w-0 rounded-lg border border-line bg-white/92 p-3.5 shadow-[0_8px_24px_rgba(15,15,15,0.035)] sm:p-4">
          <p className="text-xs font-semibold text-steel">今天先做</p>
          <h1 className="mt-1.5 max-w-3xl text-xl font-semibold leading-tight text-ink sm:text-2xl">
            {primaryActionLabel}
          </h1>
          <p className="mt-2 max-w-2xl text-xs leading-5 text-slate-500">{stageMessage}</p>

          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <span className="inline-flex min-h-7 items-center gap-2 rounded-lg border border-line bg-canvas px-2.5">
              <Clock3 size={14} />
              {minutes} 分钟
            </span>
            <span className="inline-flex min-h-7 items-center gap-2 rounded-lg border border-line bg-canvas px-2.5">
              <CheckCircle2 size={14} />
              {stageLabel}
            </span>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button
              type="button"
              className="dt-interactive inline-flex min-h-9 items-center gap-2 rounded-lg bg-ink px-3.5 text-sm font-medium text-white shadow-soft"
              onClick={onEnterCurrentStep}
            >
              进入当前一步
              <ArrowRight size={16} />
            </button>
            <button
              type="button"
              className="dt-interactive inline-flex min-h-9 items-center gap-2 rounded-lg border border-line bg-white px-3.5 text-sm font-medium text-charcoal hover:bg-canvas"
              onClick={onOpenSupport}
            >
              <CalendarDays size={16} />
              查看路线
            </button>
          </div>
        </div>

        <aside className="rounded-lg border border-line bg-[#fbfbfa] p-3.5">
          <p className="text-xs font-semibold text-steel">当前卡片</p>
          <h2 className="mt-2 text-base font-semibold leading-6 text-ink">
            {currentTask?.title || "先生成一条学习路线"}
          </h2>
          <p className="mt-2 text-xs leading-5 text-slate-500">
            {currentTask?.instruction || "写下课程目标和时间预算，系统会把它拆成可以马上执行的小任务。"}
          </p>
          <div className="mt-4 rounded-lg border border-dashed border-line bg-white px-3 py-2 text-xs leading-5 text-slate-500">
            完成后会自动进入下一步，不需要在一堆工具里找入口。
          </div>
        </aside>
      </div>
    </motion.section>
  );
}
