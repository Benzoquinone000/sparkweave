import { ArrowRight, Brain, CheckCircle2, RefreshCw, Target } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { feedbackConceptTone, feedbackTone } from "@/lib/guideDisplay";
import type { GuideV2LearningFeedback, GuideV2LearningReport } from "@/lib/types";

export function LearningImpactSummary({
  feedback,
  compact = false,
}: {
  feedback: GuideV2LearningFeedback;
  compact?: boolean;
}) {
  const concepts = (feedback.concept_feedback ?? []).slice(0, compact ? 2 : 3);
  const evidenceScore = typeof feedback.evidence_quality?.score === "number" ? Math.round(feedback.evidence_quality.score) : null;
  const nextAction = feedback.next_task_title || feedback.resource_actions?.[0]?.title || feedback.actions?.[0] || "已更新下一步";
  const rows = [
    {
      label: "证据",
      value: evidenceScore == null ? "已记录" : `${evidenceScore}/100`,
      helper: feedback.evidence_quality?.label || "本次学习行为已进入画像证据账本。",
    },
    {
      label: "概念",
      value: concepts.length ? `${concepts.length} 个` : "待积累",
      helper: concepts[0]?.summary || "系统会继续收集题目、资源和反思证据。",
    },
    {
      label: "路线",
      value: feedback.next_task_title ? "已调整" : "已同步",
      helper: nextAction,
    },
  ];

  return (
    <div className={`mt-4 rounded-lg border border-line bg-canvas p-3 ${compact ? "" : "shadow-sm"}`} data-testid="guide-learning-impact-summary">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold text-ink">这次提交改变了什么</p>
        <Badge tone={feedbackTone(feedback.tone)}>画像已同步</Badge>
      </div>
      <div className="mt-3 grid gap-2 md:grid-cols-3">
        {rows.map((row) => (
          <div key={row.label} className="rounded-lg border border-line bg-white p-3">
            <p className="text-xs text-slate-500">{row.label}</p>
            <p className="mt-1 text-sm font-semibold text-ink">{row.value}</p>
            <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{row.helper}</p>
          </div>
        ))}
      </div>
      {concepts.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {concepts.map((item) => (
            <Badge key={`${item.concept}-${item.status}`} tone={feedbackConceptTone(item.status, item.score_percent)}>
              {item.concept || "知识点"} · {item.score_percent == null ? "已更新" : `${Math.round(Number(item.score_percent))}%`}
            </Badge>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function GuideLearningLoopReceipt({
  feedback,
  report,
  profileRefreshing,
}: {
  feedback: GuideV2LearningFeedback;
  report: GuideV2LearningReport["learning_effect_report"] | null;
  profileRefreshing: boolean;
}) {
  const primaryAction = [...(report?.next_actions ?? [])].sort((left, right) => Number(right.priority ?? 0) - Number(left.priority ?? 0))[0];
  const evidenceCount = Number(report?.summary?.event_count ?? 0);
  const score = typeof report?.overall?.score === "number" ? Math.round(report.overall.score) : null;
  const conceptCount = report?.concepts?.length || feedback.concept_feedback?.length || 0;
  const timeline = (report?.visualization?.evidence_timeline ?? []).slice(0, 2);
  const nextTitle = primaryAction?.title || feedback.next_task_title || feedback.actions?.[0] || "继续当前路线";
  const receiptRows = [
    {
      label: "证据写回",
      value: evidenceCount ? `${evidenceCount} 条` : "已记录",
      detail: feedback.evidence_quality?.label || feedback.summary || "这次提交已经进入学习证据账本。",
      icon: <CheckCircle2 size={15} />,
    },
    {
      label: "画像判断",
      value: score == null ? "已同步" : `${score} 分`,
      detail: report?.overall?.summary || `${conceptCount || "多个"} 个知识点正在重新评估。`,
      icon: <Brain size={15} />,
    },
    {
      label: "下一步处方",
      value: primaryAction?.estimated_minutes ? `${primaryAction.estimated_minutes} 分钟` : "已生成",
      detail: nextTitle,
      icon: <Target size={15} />,
    },
  ];

  return (
    <div className="mt-4 rounded-lg border border-line bg-canvas p-3" data-testid="guide-learning-loop-receipt">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <RefreshCw size={15} className="text-brand-purple" />
            <p className="text-sm font-semibold text-ink">学习闭环回执</p>
            <Badge tone="brand">已同步画像</Badge>
          </div>
          <p className="mt-1 text-xs leading-5 text-slate-500">不用自己查报告：系统已经把这次提交串到证据、画像和下一步处方里。</p>
        </div>
        <a
          href="/memory"
          className="dt-interactive inline-flex min-h-9 items-center justify-center gap-2 rounded-lg border border-line bg-white px-3 text-xs font-medium text-slate-700 hover:border-brand-purple-300 hover:text-brand-purple"
          data-testid="guide-learning-loop-open-memory"
        >
          <Brain size={14} />
          {profileRefreshing ? "画像同步中" : "查看画像"}
        </a>
      </div>

      <div className="mt-3 grid gap-2 md:grid-cols-3">
        {receiptRows.map((row) => (
          <div key={row.label} className="rounded-lg border border-line bg-white p-3">
            <div className="flex items-center gap-2 text-xs font-semibold text-brand-purple">
              {row.icon}
              {row.label}
            </div>
            <p className="mt-2 text-sm font-semibold text-ink">{row.value}</p>
            <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{row.detail}</p>
          </div>
        ))}
      </div>

      {timeline.length ? (
        <div className="mt-3 rounded-lg border border-line bg-white p-3" data-testid="guide-learning-loop-evidence">
          <p className="text-xs font-semibold text-slate-500">最近证据</p>
          <div className="mt-2 grid gap-2 md:grid-cols-2">
            {timeline.map((item, index) => (
              <div key={item.id || `${item.label}-${index}`} className="rounded-md bg-canvas px-3 py-2 text-xs leading-5 text-slate-600">
                <span className="font-semibold text-ink">{item.label || "学习证据"}</span>
                {item.detail ? <span className="ml-1">{item.detail}</span> : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {primaryAction?.href ? (
        <a
          href={primaryAction.href}
          className="dt-interactive mt-3 inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-lg border border-brand-purple bg-brand-purple px-3 text-sm font-medium text-white hover:bg-brand-purple-800"
          data-testid="guide-learning-loop-receipt-action"
        >
          按处方继续
          <ArrowRight size={15} />
        </a>
      ) : null}
    </div>
  );
}
