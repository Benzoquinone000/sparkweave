import { BookOpen, FileDown, GraduationCap, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { guideDisplayText } from "@/lib/guideDisplay";
import type { GuideV2CoursePackage } from "@/lib/types";

export function GuideCoursePackagePanel({
  coursePackage,
  loading,
  canSave,
  saving,
  onSave,
  canExport,
  onExport,
}: {
  coursePackage: GuideV2CoursePackage | null;
  loading: boolean;
  canSave: boolean;
  saving: boolean;
  onSave: () => void;
  canExport: boolean;
  onExport: () => void;
}) {
  const project = coursePackage?.capstone_project ?? {};
  const rubric = coursePackage?.rubric ?? [];
  const review = coursePackage?.review_plan ?? [];
  const portfolio = coursePackage?.portfolio ?? [];

  return (
    <section className="flex h-full min-h-0 flex-col gap-3" data-testid="guide-course-package-panel">
      <div className="shrink-0 rounded-lg border border-line bg-white p-4">
        <div className="flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-2">
            <GraduationCap size={18} className="shrink-0 text-brand-purple" />
            <div className="min-w-0">
              <h2 className="line-clamp-1 text-base font-semibold text-ink">{guideDisplayText(coursePackage?.title, "课程成果包")}</h2>
              <p className="mt-0.5 line-clamp-1 text-xs text-slate-500">{guideDisplayText(coursePackage?.summary, "把本轮学习整理成可复盘成果。")}</p>
            </div>
          </div>
          {loading ? <Loader2 size={16} className="animate-spin text-brand-purple" /> : <Badge tone="brand">{project.estimated_minutes ?? "-"} 分钟</Badge>}
        </div>
      </div>

      <div className="grid min-h-0 flex-1 gap-3 md:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
        <section className="rounded-lg border border-line bg-canvas p-4">
          <Badge tone="brand">成果项目</Badge>
          <h3 className="mt-3 text-lg font-semibold leading-7 text-ink">{guideDisplayText(project.title, "学习成果项目")}</h3>
          <p className="mt-2 line-clamp-5 text-sm leading-6 text-slate-600">
            {guideDisplayText(project.scenario, "完成更多学习任务后会生成更贴合你的项目说明。")}
          </p>
          {project.deliverables?.length ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {project.deliverables.slice(0, 4).map((item) => (
                <Badge key={item} tone="neutral">{guideDisplayText(item)}</Badge>
              ))}
            </div>
          ) : null}
        </section>

        <section className="rounded-lg border border-line bg-white p-4">
          <Badge tone="neutral">来源</Badge>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <Metric label="材料" value={portfolio.length} />
            <Metric label="评分项" value={rubric.length} />
            <Metric label="复习点" value={review.length} />
            <Metric label="状态" value={coursePackage ? "已生成" : "等待"} />
          </div>
        </section>
      </div>

      <div className="grid shrink-0 gap-3 md:grid-cols-2">
        <section className="rounded-lg border border-line bg-white p-3">
          <p className="text-sm font-semibold text-ink">评分重点</p>
          <div className="mt-2 space-y-2">
            {rubric.slice(0, 2).map((item) => (
              <div key={item.criterion} className="flex items-center justify-between gap-2 rounded-lg bg-canvas px-3 py-2">
                <span className="line-clamp-1 text-xs text-slate-600">{guideDisplayText(item.criterion, "评分项")}</span>
                <Badge tone="neutral">{item.weight ?? 0}%</Badge>
              </div>
            ))}
            {!rubric.length ? <p className="text-xs text-slate-500">生成后显示评分重点。</p> : null}
          </div>
        </section>

        <section className="rounded-lg border border-line bg-white p-3">
          <p className="text-sm font-semibold text-ink">复习重点</p>
          <div className="mt-2 space-y-2">
            {review.slice(0, 2).map((item) => (
              <div key={`${item.node_id || item.title}`} className="rounded-lg bg-canvas px-3 py-2">
                <p className="line-clamp-1 text-xs font-semibold text-ink">{guideDisplayText(item.title, "知识点")}</p>
                <p className="mt-1 line-clamp-1 text-xs text-slate-500">{guideDisplayText(item.action, "继续复习这一点。")}</p>
              </div>
            ))}
            {!review.length ? <p className="text-xs text-slate-500">完成更多任务后生成复习重点。</p> : null}
          </div>
        </section>
      </div>

      <div className="grid shrink-0 gap-2 md:grid-cols-2">
        <Button tone="secondary" className="w-full" disabled={!canSave || saving || !coursePackage} onClick={onSave}>
          {saving ? <Loader2 size={16} className="animate-spin" /> : <BookOpen size={16} />}
          保存到记录本
        </Button>
        <Button
          tone="primary"
          className="w-full"
          disabled={!canExport || !coursePackage}
          onClick={onExport}
          data-testid="guide-course-package-download"
        >
          <FileDown size={16} />
          下载 Markdown
        </Button>
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-line bg-canvas px-3 py-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-ink">{value}</p>
    </div>
  );
}
