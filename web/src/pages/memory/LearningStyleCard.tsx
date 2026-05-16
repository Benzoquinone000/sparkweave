import { motion } from "framer-motion";
import { ArrowRight, CheckCircle2 } from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/Badge";
import type { LearningProgressStyle } from "./learningProgressStyle";

export function LearningStyleCard({
  progressStyle,
  actionHref,
  actionLabel,
}: {
  progressStyle: LearningProgressStyle;
  actionHref: string;
  actionLabel: string;
}) {
  const shift = progressStyle.recentShift;
  const directionTone: Record<NonNullable<LearningProgressStyle["recentShift"]>["direction"], string> = {
    stable: "border-emerald-100 bg-emerald-50 text-emerald-700",
    accelerating: "border-blue-100 bg-blue-50 text-brand-blue",
    correcting: "border-amber-100 bg-amber-50 text-amber-700",
    observing: "border-line bg-canvas text-slate-600",
  };

  return (
    <section className="rounded-lg border border-line bg-white p-4 shadow-sm" data-testid="learner-progress-style-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase text-brand-purple">你的学习推进方式</p>
          <h2 className="mt-2 text-lg font-semibold text-ink">系统会按“{progressStyle.label}”带你走</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{progressStyle.summary}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Tag>{progressStyle.confidenceText}</Tag>
          <a
            href={actionHref}
            className="dt-interactive inline-flex min-h-9 items-center justify-center gap-2 rounded-md border border-brand-purple-300 bg-tint-lavender px-3 text-xs font-medium text-brand-purple hover:bg-white"
          >
            {actionLabel}
            <ArrowRight size={14} />
          </a>
        </div>
      </div>

      <div className="mt-4 grid gap-2 md:grid-cols-3">
        {progressStyle.signals.slice(0, 3).map((signal, index) => (
          <motion.div
            key={signal.label}
            className="rounded-lg border border-line bg-canvas p-3"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.04, duration: 0.18 }}
          >
            <div className="flex items-center gap-2">
              <span className="flex size-6 shrink-0 items-center justify-center rounded-md bg-white text-xs font-semibold text-brand-purple">
                {index + 1}
              </span>
              <Badge tone={signal.tone}>{signal.label}</Badge>
            </div>
            <p className="mt-2 text-xs leading-5 text-slate-600">{signal.detail}</p>
          </motion.div>
        ))}
      </div>

      <div className={`mt-3 rounded-lg border p-3 ${shift ? directionTone[shift.direction] : "border-line bg-canvas text-slate-600"}`}>
        <div className="flex flex-wrap items-center gap-2">
          <CheckCircle2 size={15} />
          <p className="text-xs font-semibold">{shift?.label || "最近仍在观察"}</p>
        </div>
        <p className="mt-2 text-xs leading-5">{shift?.summary || "继续完成一次任务或练习后，系统会更清楚你适合怎样推进。"}</p>
        {shift?.cues.length ? (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {shift.cues.slice(0, 3).map((cue) => (
              <span key={cue} className="rounded-md border border-white/70 bg-white/80 px-2 py-1 text-[11px] text-slate-600">
                {cue}
              </span>
            ))}
          </div>
        ) : null}
      </div>

      {progressStyle.suggestions.length ? (
        <p className="mt-3 text-xs leading-5 text-slate-500">系统接下来会优先：{progressStyle.suggestions[0]}</p>
      ) : null}
    </section>
  );
}

function Tag({ children }: { children: ReactNode }) {
  return <span className="rounded-md border border-brand-purple-300 bg-tint-lavender px-2 py-1 text-xs font-medium text-brand-purple">{children}</span>;
}
