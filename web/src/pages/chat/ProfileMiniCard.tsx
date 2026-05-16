import { Sparkles } from "lucide-react";

import type { LearnerProfileSnapshot } from "@/lib/types";

export function ProfileMiniCard({ profile, loading }: { profile?: LearnerProfileSnapshot; loading: boolean }) {
  const weakPoints = profile?.learning_state.weak_points?.slice(0, 2) ?? [];
  const nextAction = profile?.next_action?.title?.trim();

  return (
    <section className="border-b border-line bg-tint-lavender p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-sm font-semibold text-brand-purple">
            <Sparkles size={16} />
            学习画像
          </div>
          {loading ? (
            <p className="mt-2 text-sm text-charcoal">正在读取画像...</p>
          ) : profile ? (
            <>
              <p className="mt-2 line-clamp-2 text-sm leading-6 text-ink">
                {profile.overview.current_focus || "继续学习后，系统会整理你的当前重点。"}
              </p>
              {nextAction ? <p className="mt-1 text-xs text-charcoal">下一步：{nextAction}</p> : null}
              {weakPoints.length ? (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {weakPoints.map((item) => (
                    <span key={`${item.label}-${item.source_ids.join("-")}`} className="rounded-md bg-white px-2 py-1 text-xs text-charcoal">
                      {item.label}
                    </span>
                  ))}
                </div>
              ) : null}
            </>
          ) : (
            <p className="mt-2 text-sm leading-6 text-charcoal">完成一次导学或练习后，系统会自动形成画像。</p>
          )}
        </div>
        <a
          href="/memory"
          className="dt-interactive shrink-0 rounded-lg border border-brand-purple-300 bg-white px-2.5 py-1.5 text-xs font-medium text-brand-purple hover:border-brand-purple"
        >
          修正
        </a>
      </div>
    </section>
  );
}
