import { BarChart3, BookOpen, CheckCircle2, Loader2, Map, Video } from "lucide-react";
import { motion } from "framer-motion";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { effectStatusTone, guideDisplayText, guideTaskTitle } from "@/lib/guideDisplay";
import type { GuideV2CourseTemplate, GuideV2LearningReport } from "@/lib/types";

export type DemoRecordingCueAction = "none" | "generate_current_seed" | "open_complete_task" | "open_route_map" | "open_course_package";
export type DemoRecordingCue = {
  title: string;
  detail: string;
  actionLabel: string;
  action: DemoRecordingCueAction;
  tone: "brand" | "success" | "warning";
};

export function DemoQuickStartCard({
  template,
  loading,
  busy,
  onStart,
}: {
  template: GuideV2CourseTemplate | null;
  loading: boolean;
  busy: boolean;
  onStart: () => void;
}) {
  if (loading || !template?.demo_seed) {
    return null;
  }

  const chain = template.demo_seed.task_chain ?? [];
  const chainText = chain
    .slice(0, 3)
    .map((item, index) => guideTaskTitle(item, index))
    .filter(Boolean)
    .join(" / ");

  return (
    <div className="rounded-lg border border-blue-100 bg-blue-50 p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">比赛演示</Badge>
            <Badge tone="neutral">{template.course_name || template.title}</Badge>
          </div>
          <p className="mt-2 text-sm font-semibold text-ink">{template.demo_seed.title || "稳定 Demo 样例"}</p>
          <p className="mt-1 max-w-2xl text-xs leading-5 text-slate-600">{template.demo_seed.scenario || "一键创建可复现演示路线。"}</p>
          {chainText ? <p className="mt-2 text-xs text-slate-500">推荐顺序：{chainText}</p> : null}
        </div>
        <Button tone="primary" className="min-h-9 px-3 text-xs" data-testid="guide-demo-start" disabled={busy} onClick={onStart}>
          {busy ? <Loader2 size={14} className="animate-spin" /> : <Video size={14} />}
          开始稳定演示
        </Button>
      </div>
    </div>
  );
}

export function DemoRecordingCueCard({
  cue,
  busy,
  onAction,
}: {
  cue: DemoRecordingCue | null;
  busy: boolean;
  onAction: () => void;
}) {
  if (!cue) {
    return null;
  }

  return (
    <motion.section
      className="rounded-lg border border-blue-100 bg-white p-4 shadow-sm"
      data-testid="guide-demo-recording-cue"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.16, ease: "easeOut" }}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">录屏下一步</Badge>
            <Badge tone={cue.tone}>{cue.actionLabel}</Badge>
          </div>
          <h2 className="mt-2 text-base font-semibold text-ink">{cue.title}</h2>
          <p className="mt-1 max-w-2xl text-xs leading-5 text-slate-600">{cue.detail}</p>
        </div>
        {cue.action !== "none" ? (
          <Button
            tone={cue.tone === "success" ? "secondary" : "primary"}
            className="min-h-10 px-3 text-xs"
            data-testid="guide-demo-cue-action"
            disabled={busy}
            onClick={onAction}
          >
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Video size={14} />}
            {cue.actionLabel}
          </Button>
        ) : (
          <Loader2 size={16} className="animate-spin text-brand-blue" />
        )}
      </div>
    </motion.section>
  );
}

export function DemoEvidenceShortcut({
  step,
  onApply,
}: {
  step: Record<string, unknown> | null;
  onApply: (score: string, reflection: string) => void;
}) {
  if (!step) {
    return null;
  }

  const reflection = readString(step, "sample_reflection");
  if (!reflection) {
    return null;
  }

  const rawScore = Number(step.sample_score ?? 0.72);
  const normalizedScore = Number.isFinite(rawScore) ? Math.max(0, Math.min(rawScore, 1)) : 0.72;
  const scoreValue = normalizedScore >= 0.8 ? "0.9" : normalizedScore >= 0.6 ? "0.7" : "0.45";

  return (
    <div className="mb-4 rounded-lg border border-blue-100 bg-blue-50 p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Badge tone="brand">演示样例</Badge>
          <p className="mt-2 text-sm font-semibold text-ink">一键填入示例反馈</p>
          <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-600">{reflection}</p>
        </div>
        <Button tone="secondary" className="min-h-9 px-3 text-xs" data-testid="guide-demo-apply-feedback" onClick={() => onApply(scoreValue, reflection)}>
          <CheckCircle2 size={14} />
          带入
        </Button>
      </div>
    </div>
  );
}

export function DemoWrapUpCard({
  enabled,
  report,
  loading,
  onOpenCoursePackage,
  onOpenRouteMap,
}: {
  enabled: boolean;
  report: GuideV2LearningReport | null;
  loading: boolean;
  onOpenCoursePackage: () => void;
  onOpenRouteMap: () => void;
}) {
  if (!enabled) {
    return null;
  }

  const readiness = report?.demo_readiness ?? null;
  const checks = readiness?.checks ?? [];
  const readyCount = checks.filter((item) => item.status === "ready").length;
  const score = Number(readiness?.score ?? 0);
  const nextStep =
    readiness?.next_steps?.[0] ||
    report?.action_brief?.summary ||
    "接着展示路线、学习报告和课程成果，把学习记录、资源、练习、反馈串成一条学习链。";

  return (
    <motion.section
      className="mt-3 rounded-lg border border-blue-100 bg-blue-50 p-4"
      data-testid="guide-demo-wrap-up"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">演示收尾</Badge>
            <Badge tone={effectStatusTone(score)}>{loading ? "检查中" : guideDisplayText(readiness?.label, "准备中")}</Badge>
            {checks.length ? <Badge tone="neutral">{readyCount}/{checks.length} 项就绪</Badge> : null}
          </div>
          <h3 className="mt-3 text-base font-semibold text-ink">下一步看路线与成果</h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            {guideDisplayText(readiness?.summary, "这次反馈已经回写学习记录。录屏时接着展示路线调整、演示就绪度和最终课程成果。")}
          </p>
        </div>
        {loading ? <Loader2 size={16} className="animate-spin text-brand-blue" /> : <BarChart3 size={18} className="text-brand-blue" />}
      </div>
      <p className="mt-3 rounded-lg border border-blue-100 bg-white p-2 text-xs leading-5 text-slate-600">建议：{guideDisplayText(nextStep)}</p>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <Button tone="secondary" className="min-h-10 justify-center" data-testid="guide-demo-open-route-map" onClick={onOpenRouteMap}>
          <Map size={15} />
          看路线
        </Button>
        <Button tone="primary" className="min-h-10 justify-center" data-testid="guide-demo-open-course-package" onClick={onOpenCoursePackage}>
          <BookOpen size={15} />
          看成果
        </Button>
      </div>
    </motion.section>
  );
}

function readString(source: Record<string, unknown>, key: string) {
  const value = source[key];
  return typeof value === "string" ? value : value == null ? "" : String(value);
}
