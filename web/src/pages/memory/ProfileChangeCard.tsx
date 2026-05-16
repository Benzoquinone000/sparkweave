import { motion } from "framer-motion";

import { formatDate } from "./memoryDisplayUtils";
import type { ProfileChangeSummary } from "./profileChangeSummary";

export function ProfileChangeCard({ summary }: { summary: ProfileChangeSummary }) {
  const toneClass = summary.tone === "calibration" ? "border-amber-200 bg-amber-50" : "border-brand-purple-300 bg-tint-lavender";
  return (
    <motion.section
      className={`rounded-lg border p-4 ${toneClass}`}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold text-brand-purple">最近变化</p>
          <h2 className="mt-2 text-lg font-semibold text-ink">{summary.title}</h2>
        </div>
        <span className="text-xs text-slate-500">{formatDate(summary.updatedAt)}</span>
      </div>
      <div className="mt-3 grid gap-2">
        {summary.items.map((item, index) => (
          <div key={`${item}-${index}`} className="rounded-lg border border-white/70 bg-white/80 px-3 py-2 text-sm leading-6 text-slate-700">
            {item}
          </div>
        ))}
      </div>
      {summary.details.length ? (
        <div className="mt-4 grid gap-2">
          {summary.details.map((detail) => (
            <div key={`${detail.label}-${detail.previous}-${detail.current}`} className="rounded-lg border border-white/70 bg-white/70 p-3">
              <div className="text-xs font-semibold text-slate-500">{detail.label}</div>
              <div className="mt-2 grid gap-2 md:grid-cols-2">
                <div className="rounded-md border border-line bg-white px-3 py-2">
                  <div className="text-[11px] font-medium text-slate-400">之前</div>
                  <div className="mt-1 text-sm leading-6 text-slate-600">{detail.previous}</div>
                </div>
                <div className="rounded-md border border-brand-purple-300 bg-tint-lavender px-3 py-2">
                  <div className="text-[11px] font-medium text-brand-purple">现在</div>
                  <div className="mt-1 text-sm leading-6 text-ink">{detail.current}</div>
                </div>
              </div>
              {detail.evidenceHints?.length ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {detail.evidenceHints.map((hint) => (
                    <span key={`${detail.label}-${hint}`} className="rounded-md border border-line bg-white px-2 py-1 text-xs text-slate-500">
                      相关依据：{hint}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
    </motion.section>
  );
}
