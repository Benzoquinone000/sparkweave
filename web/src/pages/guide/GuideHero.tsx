import { motion } from "framer-motion";
import { ArrowRight, CalendarDays, Sparkles } from "lucide-react";

import { PeopleAccent } from "@/components/ui/PeopleAccent";
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
  return (
    <motion.section
      className="dt-notion-hero p-5 sm:p-6 lg:p-7"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: "easeOut" }}
    >
      <img
        src="/illustrations/notion-thread.svg"
        alt=""
        aria-hidden="true"
        className="pointer-events-none absolute inset-y-0 right-0 hidden h-full w-[76%] object-cover opacity-35 lg:block"
      />
      <img
        src="/illustrations/notion-note-yellow.svg"
        alt=""
        aria-hidden="true"
        className="dt-hero-note pointer-events-none absolute right-10 top-5 hidden h-12 w-16 sm:block"
      />
      <img
        src="/illustrations/notion-note-pink.svg"
        alt=""
        aria-hidden="true"
        className="dt-hero-note pointer-events-none absolute right-28 top-28 hidden h-11 w-14 lg:block"
      />
      <div className="relative z-10 mx-auto max-w-4xl text-center">
        <p className="text-sm font-semibold text-brand-purple-300">今天先做这一小步</p>
        <h1 className="mx-auto mt-3 max-w-3xl text-3xl font-semibold leading-tight text-white sm:text-4xl">{primaryActionLabel}</h1>
        <p className="mx-auto mt-3 max-w-2xl text-sm leading-6 text-white/75">{stageMessage}</p>
        <div className="mt-4 flex flex-wrap items-center justify-center gap-2 text-xs text-white/75">
          <span className="rounded-lg border border-white/10 bg-white/10 px-3 py-1.5">
            {currentTask ? `${currentTask.estimated_minutes ?? 8} 分钟` : "懒人式路线"}
          </span>
          <span className="rounded-lg border border-white/10 bg-white/10 px-3 py-1.5">
            {guideStage === "create" ? "先写目标" : guideStage === "diagnostic" ? "先前测" : "资源和反馈自动接上"}
          </span>
          <span className="rounded-lg border border-white/10 bg-white/10 px-3 py-1.5">画像持续校准</span>
        </div>
        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
          <button
            type="button"
            className="dt-interactive inline-flex min-h-10 items-center gap-2 rounded-lg bg-brand-purple px-4 text-sm font-medium text-white shadow-soft"
            onClick={onEnterCurrentStep}
          >
            <Sparkles size={16} />
            进入当前一步
          </button>
          <button
            type="button"
            className="dt-interactive inline-flex min-h-10 items-center gap-2 rounded-lg border border-white/25 bg-white px-4 text-sm font-medium text-ink shadow-soft"
            onClick={onOpenSupport}
          >
            <CalendarDays size={16} />
            查看路线
          </button>
        </div>
      </div>

      <div className="dt-workspace-mockup relative z-10 mx-auto mt-7 max-w-4xl text-ink">
        <div className="grid min-h-[230px] lg:grid-cols-[210px_minmax(0,1fr)]">
          <aside className="hidden border-r border-line bg-[#fbfbfa] p-4 lg:block">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-navy text-white">
                <Sparkles size={18} />
              </div>
              <div>
                <p className="text-sm font-semibold text-ink">SparkWeave</p>
                <p className="text-xs text-steel">导学空间</p>
              </div>
            </div>
            <div className="mt-7 space-y-4 text-sm text-charcoal">
              {[
                ["当前一步", "bg-brand-purple"],
                ["学习画像", "bg-brand-teal"],
                ["反馈复盘", "bg-brand-orange"],
              ].map(([label, dot]) => (
                <div key={label} className="flex items-center gap-3">
                  <span className={`h-2.5 w-2.5 ${dot}`} style={{ borderRadius: "50%" }} />
                  <span>{label}</span>
                </div>
              ))}
            </div>
          </aside>
          <div className="relative overflow-hidden p-4 sm:p-5">
            <PeopleAccent name="course_map" className="pointer-events-none absolute bottom-[-28px] right-[-20px] h-44 w-52 opacity-80" />
            <div className="relative z-10">
              <div className="dt-feature-tile dt-feature-tile-yellow flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                <div>
                  <p className="text-sm font-semibold text-ink">{currentTask ? "当前只做这一件事" : "先生成一条路线"}</p>
                  <p className="mt-1 text-xs leading-5 text-charcoal">
                    {currentTask ? currentTask.title : "告诉系统你想学什么，后面会自动拆成可执行的小步。"}
                  </p>
                </div>
                <button
                  type="button"
                  className="dt-interactive inline-flex min-h-9 items-center gap-2 rounded-lg bg-brand-yellow px-3 text-sm font-semibold text-ink"
                  onClick={onEnterCurrentStep}
                >
                  开始
                  <ArrowRight size={15} />
                </button>
              </div>
              <div className="mt-3 grid gap-3 sm:grid-cols-3">
                <div className="dt-feature-tile dt-feature-tile-sky px-3 py-3">
                  <p className="text-sm font-semibold text-ink">图解</p>
                  <p className="mt-1 text-xs leading-5 text-steel">把概念变成一张图。</p>
                </div>
                <div className="dt-feature-tile dt-feature-tile-rose px-3 py-3">
                  <p className="text-sm font-semibold text-ink">练习</p>
                  <p className="mt-1 text-xs leading-5 text-steel">选择、判断、填空。</p>
                </div>
                <div className="dt-feature-tile dt-feature-tile-mint px-3 py-3">
                  <p className="text-sm font-semibold text-ink">反馈</p>
                  <p className="mt-1 text-xs leading-5 text-steel">提交后更新画像。</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </motion.section>
  );
}
