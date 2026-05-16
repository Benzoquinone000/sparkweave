import { Badge } from "@/components/ui/Badge";
import { guideStageLabel } from "@/lib/guideDisplay";
export function GuideCourseSyllabusPanel({ metadata }: { metadata: Record<string, unknown> }) {
  const outcomes = Array.isArray(metadata.learning_outcomes) ? metadata.learning_outcomes.map(String) : [];
  const weeklySchedule = Array.isArray(metadata.weekly_schedule) ? metadata.weekly_schedule : [];
  const assessment = Array.isArray(metadata.assessment) ? metadata.assessment : [];
  const milestones = Array.isArray(metadata.project_milestones) ? metadata.project_milestones : [];
  if (!Object.keys(metadata).length) return null;
  return (
    <section className="rounded-lg border border-line bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-ink">课程大纲</h2>
          <p className="mt-1 text-sm leading-6 text-slate-500">
            {String(metadata.course_name || "完整课程")} · {String(metadata.suggested_weeks || "-")} 周 · {String(metadata.credits || "-")} 学分建议
          </p>
        </div>
        <Badge tone="brand">课程大纲</Badge>
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-[1fr_1.2fr]">
        <div className="space-y-3">
          <div className="rounded-lg border border-line bg-canvas p-3">
            <p className="text-sm font-semibold text-ink">学习目标</p>
            <div className="mt-2 space-y-2">
              {outcomes.slice(0, 4).map((item) => (
                <p key={item} className="text-xs leading-5 text-slate-600">• {item}</p>
              ))}
            </div>
          </div>
          <div className="rounded-lg border border-line bg-canvas p-3">
            <p className="text-sm font-semibold text-ink">考核构成</p>
            <div className="mt-2 grid grid-cols-2 gap-2">
              {assessment.slice(0, 4).map((raw) => {
                const item = asRecord(raw) ?? {};
                return (
                  <div key={String(item.name)} className="rounded-lg bg-white p-2">
                    <p className="line-clamp-1 text-xs text-slate-500">{String(item.name || "考核")}</p>
                    <p className="mt-1 text-sm font-semibold text-ink">{String(item.weight || 0)}%</p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
        <div className="rounded-lg border border-line bg-canvas p-3">
          <p className="text-sm font-semibold text-ink">周次安排</p>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {weeklySchedule.slice(0, 8).map((raw, index) => {
              const item = asRecord(raw) ?? {};
              return (
                <div key={`${item.week || index}`} className="rounded-lg border border-line bg-white p-3">
                  <Badge tone="neutral">第 {String(item.week || index + 1)} 周</Badge>
                  <p className="mt-2 line-clamp-2 text-sm font-medium text-ink">{String(item.topic || "学习主题")}</p>
                  <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{String(item.deliverable || "阶段产出")}</p>
                </div>
              );
            })}
          </div>
        </div>
      </div>
      {milestones.length ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {milestones.slice(0, 4).map((raw, index) => {
            const item = asRecord(raw) ?? {};
            return <Badge key={String(item.stage || index)} tone="neutral">{guideStageLabel(item.stage, `里程碑 ${index + 1}`)}</Badge>;
          })}
        </div>
      ) : null}
    </section>
  );
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

