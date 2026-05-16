import {
  ArrowRight,
  BarChart3,
  BookOpen,
  Compass,
  FileDown,
  GraduationCap,
  GitBranch,
  ListChecks,
  Loader2,
  Map,
  Target,
  Video,
  Volume2,
} from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  demoReadinessLabel,
  demoReadinessTone,
  effectStatusTone,
  formatLearningEffectPercent,
  guideDisplayText,
  safeBadgeTone,
} from "@/lib/guideDisplay";
import type { GuideV2LearningFeedback, GuideV2LearningReport, GuideV2ResourceType } from "@/lib/types";
import { EvalMini } from "./GuideMetrics";
import { asRecord } from "./guideDataUtils";

type ReportResourceType = "visual" | "quiz" | "video" | "audio" | "external_video";

type FeedbackRoutingSummary = Array<{
  label: string;
  count: number;
  tone: "success" | "brand" | "warning" | "neutral";
}>;

export function GuideLearningReportPanel({
  report,
  loading,
  canSave,
  saving,
  onSave,
  canExport,
  onExport,
  onOpenRouteMap,
  onOpenCoursePackage,
  onGenerateResource,
}: {
  report: GuideV2LearningReport | null;
  loading: boolean;
  canSave: boolean;
  saving: boolean;
  onSave: () => void;
  canExport: boolean;
  onExport: () => void;
  onOpenRouteMap: () => void;
  onOpenCoursePackage: () => void;
  onGenerateResource: (type: GuideV2ResourceType, taskId: string, prompt: string) => void;
}) {
  const overview = report?.overview ?? {};
  const nodes = report?.node_cards ?? [];
  const score = Number(overview.overall_score ?? 0);
  const progress = Number(overview.progress ?? 0);
  const feedbackDigest = report?.feedback_digest;
  const latestFeedback = feedbackDigest?.latest;
  const effectAssessment = report?.effect_assessment ?? null;
  const feedbackRoutingSummary = summarizeFeedbackRouting(
    (feedbackDigest?.items ?? []).map((item) => ({
      score_percent: item.score_percent,
      actions: item.actions,
      adjustment_types: [],
    })),
  );
  const profileContext = asRecord(report?.learner_profile_context);
  const profileWeakPoints = Array.isArray(profileContext?.weak_points) ? profileContext.weak_points.map(String) : [];
  const nextActionSteps = buildNextActionSteps(report?.next_plan ?? [], feedbackRoutingSummary, profileWeakPoints);
  const actionBrief =
    report?.action_brief ??
    (nextActionSteps[0]
      ? {
          title: nextActionSteps[0].title,
          summary: nextActionSteps[0].detail,
          primary_action: {
            label: "查看完整路线",
            detail: "回到路线页继续执行下一步。",
            kind: "route_map",
          },
          secondary_actions: [],
          signals: [],
        }
      : null);
  const demoReadiness = report?.demo_readiness ?? null;
  const mistakeReview = report?.mistake_review;
  const mistakeClusters = mistakeReview?.clusters ?? [];
  const attentionItems: Array<{ label: string; detail: string; tone: "neutral" | "brand" | "success" | "warning" | "danger" }> = [
    ...mistakeClusters.slice(0, 1).map((cluster) => ({
      label: `错因：${cluster.label}`,
      detail: cluster.suggested_action || "先复测并记录修正后的理解。",
      tone: "warning" as const,
    })),
    ...nodes.slice(0, 1).map((node) => ({
      label: `知识点：${guideDisplayText(node.title, "当前知识点")}`,
      detail: node.suggestion || "继续完成任务并留下学习证据。",
      tone: "brand" as const,
    })),
    ...(report?.risks ?? []).slice(0, 1).map((item) => ({
      label: "风险",
      detail: item,
      tone: "warning" as const,
    })),
  ].slice(0, 3);
  return (
    <section className="rounded-lg border border-line bg-white p-4" data-testid="guide-learning-report-panel">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <BarChart3 size={18} className="text-brand-purple" />
          <h2 className="text-base font-semibold text-ink">学习效果报告</h2>
        </div>
        {loading ? <Loader2 size={16} className="animate-spin text-brand-purple" /> : <Badge tone={score >= 80 ? "success" : score >= 60 ? "brand" : "warning"}>{score || 0}</Badge>}
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-600">
        {report?.summary || "完成任务后，这里会汇总学习画像、薄弱点、路径调整和下一步计划。"}
      </p>
      <div className="mt-4 grid grid-cols-3 gap-2">
        <EvalMini label="分数" value={score} />
        <EvalMini label="进度" value={progress} suffix="%" />
        <EvalMini label="反馈" value={Number(feedbackDigest?.count ?? 0)} suffix="次" />
      </div>
      <EffectAssessmentCard assessment={effectAssessment} />
      <PathAdjustmentMorphCard report={report} actionBrief={actionBrief} />
      <LearningEffectReportCard report={report?.learning_effect_report ?? null} />
      <ReportActionBriefCard
        brief={actionBrief}
        canSave={canSave}
        saving={saving}
        onSave={onSave}
        onOpenRouteMap={onOpenRouteMap}
        onOpenCoursePackage={onOpenCoursePackage}
        onGenerateResource={onGenerateResource}
      />
      <DemoReadinessCard readiness={demoReadiness} />
      {attentionItems.length ? (
        <div className="mt-4 rounded-lg border border-line bg-canvas p-3">
          <p className="text-sm font-semibold text-ink">留意这几点</p>
          <div className="mt-3 space-y-2">
            {attentionItems.map((item) => (
              <div key={`${item.label}-${item.detail}`} className="rounded-lg border border-line bg-white p-2">
                <div className="flex items-center gap-2">
                  <Badge tone={item.tone}>{item.label}</Badge>
                </div>
                <p className="mt-2 text-xs leading-5 text-slate-600">{item.detail}</p>
              </div>
            ))}
          </div>
        </div>
      ) : null}
      {latestFeedback ? (
        <p className="mt-4 rounded-lg border border-line bg-white p-3 text-xs leading-5 text-slate-600">
          最近反馈：{latestFeedback.summary || latestFeedback.title || "系统已根据学习证据更新路线。"}
        </p>
      ) : null}
      <div className="mt-4 grid gap-2 md:grid-cols-2">
        <Button tone="secondary" className="w-full" disabled={!canSave || saving || !report} onClick={onSave}>
          {saving ? <Loader2 size={16} className="animate-spin" /> : <BookOpen size={16} />}
          保存到 Notebook
        </Button>
        <Button
          tone="primary"
          className="w-full"
          disabled={!canExport || !report}
          onClick={onExport}
          data-testid="guide-learning-report-download"
        >
          <FileDown size={16} />
          下载 Markdown
        </Button>
      </div>
    </section>
  );
}

function PathAdjustmentMorphCard({
  report,
  actionBrief,
}: {
  report: GuideV2LearningReport | null;
  actionBrief: GuideV2LearningReport["action_brief"] | null;
}) {
  if (!report) return null;

  const latestTimeline = report.timeline_events?.[0];
  const latestFeedback = report.feedback_digest?.latest;
  const firstIntervention = report.interventions?.[0];
  const adjustmentCount = Number(report.overview?.path_adjustment_count ?? report.interventions?.length ?? 0);
  const evidence =
    latestTimeline?.feedback_summary ||
    latestTimeline?.description ||
    latestFeedback?.summary ||
    report.evidence_summary?.latest_reflection ||
    "学生完成了一次任务、练习或资源反馈，系统拿到了新的学习证据。";
  const judgement =
    report.effect_assessment?.summary ||
    firstIntervention?.reason ||
    latestTimeline?.impact ||
    "系统综合画像、练习表现和资源使用反馈，判断是否需要补救、复测或继续推进。";
  const prescription =
    actionBrief?.title ||
    actionBrief?.primary_action?.detail ||
    report.next_plan?.[0] ||
    report.effect_assessment?.strategy_adjustments?.[0] ||
    "生成下一步学习处方，并把任务插入到个性化路线中。";
  const before =
    firstIntervention?.skipped_task_ids?.length
      ? `原路线跳过 ${firstIntervention.skipped_task_ids.length} 个不再优先的任务`
      : "按初始学习路线继续推进";
  const after =
    firstIntervention?.inserted_task_ids?.length
      ? `插入 ${firstIntervention.inserted_task_ids.length} 个补救/复测任务`
      : actionBrief?.primary_action?.label || "切换到更适合当前状态的下一步";

  return (
    <div className="mt-4 rounded-lg border border-line bg-white p-3" data-testid="guide-path-adjustment-morph">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <GitBranch size={16} className="text-brand-purple" />
            <p className="text-sm font-semibold text-ink">路线调整前后</p>
            <Badge tone={adjustmentCount > 0 ? "brand" : "neutral"}>{adjustmentCount} 次调整</Badge>
          </div>
          <p className="mt-1 text-xs leading-5 text-slate-600">
            学习效果评估会把新证据转成路径变化，展示“评估 → 调整 → 推送”的闭环。
          </p>
        </div>
      </div>
      <div className="mt-3 grid gap-2 md:grid-cols-[minmax(0,1fr)_2.5rem_minmax(0,1fr)]">
        <div className="rounded-lg border border-line bg-canvas p-3">
          <Badge tone="neutral">调整前</Badge>
          <p className="mt-2 text-sm font-semibold text-ink">{before}</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">路线先按课程结构和初始画像推进。</p>
        </div>
        <div className="hidden place-items-center text-slate-300 md:grid">
          <ArrowRight size={18} />
        </div>
        <div className="rounded-lg border border-brand-purple-300 bg-tint-lavender p-3">
          <Badge tone="brand">调整后</Badge>
          <p className="mt-2 text-sm font-semibold text-ink">{after}</p>
          <p className="mt-1 text-xs leading-5 text-slate-600">{guideDisplayText(prescription)}</p>
        </div>
      </div>
      <div className="mt-3 grid gap-2 md:grid-cols-3">
        {[
          { label: "新证据", detail: evidence, tone: "neutral" as const },
          { label: "系统判断", detail: judgement, tone: "brand" as const },
          { label: "下一步处方", detail: prescription, tone: "success" as const },
        ].map((item) => (
          <div key={item.label} className="rounded-lg border border-line bg-canvas p-3">
            <Badge tone={item.tone}>{item.label}</Badge>
            <p className="mt-2 line-clamp-3 text-xs leading-5 text-slate-600">{guideDisplayText(item.detail)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function EffectAssessmentCard({
  assessment,
}: {
  assessment: GuideV2LearningReport["effect_assessment"] | null;
}) {
  if (!assessment) return null;

  const dimensions = [...(assessment.dimensions ?? [])]
    .filter((item) => item.label || item.id)
    .sort((left, right) => Number(left.score ?? 0) - Number(right.score ?? 0));
  const chain =
    assessment.assessment_chain?.length
      ? assessment.assessment_chain
      : [
          {
            label: "定位瓶颈",
            detail:
              dimensions[0]?.evidence ||
              assessment.summary ||
              "系统会根据任务进度、练习结果、错因和画像综合判断。",
          },
          {
            label: "调整策略",
            detail: assessment.strategy_adjustments?.[0] || "继续完成当前任务并留下可评分证据。",
          },
        ];

  return (
    <div className="mt-4 rounded-lg border border-line bg-canvas p-3" data-testid="guide-effect-assessment-chain">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-ink">评估依据与调度理由</p>
          <p className="mt-1 text-xs leading-5 text-slate-600">
            {assessment.summary || "系统会参考你刚留下的学习证据、练习反馈和画像信号，决定下一步更适合怎么继续。"}
          </p>
        </div>
        <Badge tone={Number(assessment.score ?? 0) >= 70 ? "success" : "warning"}>
          {assessment.label || "评估中"}
        </Badge>
      </div>
      <div className="mt-3 grid gap-2 md:grid-cols-3">
        {chain.slice(0, 3).map((item, index) => (
          <div key={`${item.label}-${index}`} className="rounded-lg border border-line bg-white p-3">
            <p className="text-xs font-semibold text-brand-purple">{guideDisplayText(item.label, `第 ${index + 1} 步`)}</p>
            <p className="mt-1 text-xs leading-5 text-slate-600">{guideDisplayText(item.detail, "继续留下学习证据。")}</p>
          </div>
        ))}
      </div>
      {dimensions.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {dimensions.slice(0, 3).map((item) => (
            <Badge key={`${item.id}-${item.label}`} tone={Number(item.score ?? 0) >= 70 ? "brand" : "warning"}>
              {guideDisplayText(item.label, "维度")}：{Number(item.score ?? 0)}
            </Badge>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function LearningEffectReportCard({
  report,
}: {
  report: GuideV2LearningReport["learning_effect_report"] | null;
}) {
  if (!report) return null;

  const score = Math.round(Number(report.overall?.score ?? 0));
  const primaryAction = [...(report.next_actions ?? [])].sort((left, right) => Number(right.priority ?? 0) - Number(left.priority ?? 0))[0];
  const concepts = [...(report.concepts ?? [])]
    .sort((left, right) => {
      const mistakeGap = Number(right.open_mistake_count ?? 0) - Number(left.open_mistake_count ?? 0);
      if (mistakeGap) return mistakeGap;
      return Number(left.score ?? 0) - Number(right.score ?? 0);
    })
    .slice(0, 3);
  const tone = score >= 78 ? "success" : score >= 58 ? "brand" : "warning";

  return (
    <div className="mt-4 rounded-lg border border-line bg-white p-3" data-testid="guide-learning-effect-report-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <BarChart3 size={16} className="text-brand-purple" />
            <p className="text-sm font-semibold text-ink">全局学习效果闭环</p>
            <Badge tone={tone}>{report.overall?.label || `${score} 分`}</Badge>
          </div>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            {report.overall?.summary || "这份报告会把导学、练习、资源反馈和画像证据统一汇总，用来决定下一步。"}
          </p>
        </div>
        <Badge tone="neutral">{Number(report.summary?.event_count ?? 0)} 条证据</Badge>
      </div>
      {primaryAction ? (
        <div className="mt-3 rounded-lg border border-brand-purple-300 bg-tint-lavender p-3">
          <div className="flex flex-wrap items-center gap-2">
            <Target size={15} className="text-brand-purple" />
            <p className="text-sm font-semibold text-brand-purple">系统建议</p>
            <Badge tone="neutral">{primaryAction.estimated_minutes || 8} 分钟</Badge>
          </div>
          <p className="mt-2 text-sm font-semibold text-ink">{primaryAction.title}</p>
          <p className="mt-1 text-xs leading-5 text-slate-600">{primaryAction.reason}</p>
        </div>
      ) : null}
      {concepts.length ? (
        <div className="mt-3 grid gap-2 md:grid-cols-3">
          {concepts.map((concept) => (
            <div key={concept.concept_id} className="rounded-lg border border-line bg-canvas p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="min-w-0 truncate text-xs font-semibold text-ink">{concept.title || concept.concept_id}</p>
                <Badge tone={concept.status === "mastered" ? "success" : concept.status === "needs_support" ? "warning" : "brand"}>
                  {formatLearningEffectPercent(concept.score)}%
                </Badge>
              </div>
              <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-600">{concept.recommendation || "继续观察这一概念的练习表现。"}</p>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function ReportActionBriefCard({
  brief,
  canSave,
  saving,
  onSave,
  onOpenRouteMap,
  onOpenCoursePackage,
  onGenerateResource,
}: {
  brief: GuideV2LearningReport["action_brief"] | null;
  canSave: boolean;
  saving: boolean;
  onSave: () => void;
  onOpenRouteMap: () => void;
  onOpenCoursePackage: () => void;
  onGenerateResource: (type: GuideV2ResourceType, taskId: string, prompt: string) => void;
}) {
  if (!brief) {
    return (
      <div className="mt-4 rounded-lg border border-brand-purple-300 bg-tint-lavender p-3">
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm font-semibold text-brand-purple">下一步建议</p>
          <Badge tone="neutral">等待</Badge>
        </div>
        <p className="mt-3 text-sm leading-6 text-slate-600">完成更多任务后，系统会把“现在该做什么”整理成一个更明确的动作。</p>
      </div>
    );
  }

  const primary = brief.primary_action ?? {};
  const secondary = brief.secondary_actions ?? [];
  const signals = brief.signals ?? [];
  const steps = brief.steps ?? [];

  return (
    <div className="mt-4 rounded-lg border border-brand-purple-300 bg-tint-lavender p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-brand-purple">下一步建议</p>
          <h3 className="mt-2 text-base font-semibold text-ink">{brief.title || "现在先做这一件事"}</h3>
        </div>
        <Badge tone="brand">先做</Badge>
      </div>
      <p className="mt-2 text-sm leading-6 text-charcoal">{brief.summary || primary.detail || "系统已经把下一步压缩成一个更明确、更容易开始的动作。"}</p>
      {steps.length ? (
        <div className="mt-3 grid gap-2 md:grid-cols-3" data-testid="guide-report-action-steps">
          {steps.slice(0, 3).map((item, index) => (
            <div key={`${item.label}-${item.detail}-${index}`} className="rounded-lg border border-brand-purple-300 bg-white/80 p-3">
              <p className="text-xs font-semibold text-brand-purple">{guideDisplayText(item.label, `第 ${index + 1} 步`)}</p>
              <p className="mt-1 text-xs leading-5 text-slate-600">{guideDisplayText(item.detail, "按这一步继续推进。")}</p>
            </div>
          ))}
        </div>
      ) : null}
      {signals.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {signals.slice(0, 4).map((item) => (
            <Badge key={`${item.label}-${item.value}`} tone={safeBadgeTone(item.tone)}>
              {item.label}：{item.value}
            </Badge>
          ))}
        </div>
      ) : null}
      <div className="mt-4">
        <ReportActionButton
          action={primary}
          primary
          canSave={canSave}
          saving={saving}
          onSave={onSave}
          onOpenRouteMap={onOpenRouteMap}
          onOpenCoursePackage={onOpenCoursePackage}
          onGenerateResource={onGenerateResource}
        />
      </div>
      {secondary.length ? (
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          {secondary.slice(0, 2).map((item) => (
            <div key={`${item.label}-${item.detail}`} className="rounded-lg border border-brand-purple-300 bg-white/80 p-3">
              <p className="text-xs font-semibold text-ink">{item.label || "备选动作"}</p>
              <p className="mt-1 text-xs leading-5 text-slate-600">{item.detail || "如果当前方式不顺，可以改走这一条。 "}</p>
              <ReportActionButton
                action={item}
                className="mt-3"
                canSave={canSave}
                saving={saving}
                onSave={onSave}
                onOpenRouteMap={onOpenRouteMap}
                onOpenCoursePackage={onOpenCoursePackage}
                onGenerateResource={onGenerateResource}
              />
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function DemoReadinessCard({
  readiness,
}: {
  readiness: GuideV2LearningReport["demo_readiness"] | null;
}) {
  if (!readiness) {
    return null;
  }

  const score = Number(readiness.score ?? 0);
  const checks = readiness.checks ?? [];
  const nextStep = readiness.next_steps?.[0];

  return (
    <div className="mt-4 rounded-lg border border-line bg-white p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Target size={16} className="text-brand-blue" />
          <p className="text-sm font-semibold text-ink">演示就绪</p>
        </div>
        <Badge tone={effectStatusTone(score)}>{guideDisplayText(readiness.label, `${score} 分`)}</Badge>
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-600">
        {guideDisplayText(readiness.summary, "系统会检查画像、资源、练习、报告和可展示产物是否已经成链。")}
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        {checks.slice(0, 5).map((item) => (
          <Badge key={item.id || item.label} tone={demoReadinessTone(item.status)}>
            {guideDisplayText(item.label || item.id)}：{demoReadinessLabel(item.status)}
          </Badge>
        ))}
      </div>
      {nextStep ? (
        <p className="mt-3 rounded-lg border border-line bg-canvas p-2 text-xs leading-5 text-slate-600">
          下一步：{guideDisplayText(nextStep)}
        </p>
      ) : null}
    </div>
  );
}

function ReportActionButton({
  action,
  primary = false,
  className = "",
  canSave,
  saving,
  onSave,
  onOpenRouteMap,
  onOpenCoursePackage,
  onGenerateResource,
}: {
  action: NonNullable<GuideV2LearningReport["action_brief"]>["primary_action"];
  primary?: boolean;
  className?: string;
  canSave: boolean;
  saving: boolean;
  onSave: () => void;
  onOpenRouteMap: () => void;
  onOpenCoursePackage: () => void;
  onGenerateResource: (type: GuideV2ResourceType, taskId: string, prompt: string) => void;
}) {
  const kind = String(action?.kind || "");
  const resourceType = normalizeReportResourceType(action?.resource_type);
  const taskId = String(action?.target_task_id || "");
  const prompt = String(action?.prompt || action?.detail || "");
  const canGenerate = Boolean(resourceType && taskId);
  const opensCoursePackage = ["course_package", "project"].includes(kind);
  const rawLabel = action?.label || (opensCoursePackage ? "查看课程产出包" : canGenerate ? `生成${reportResourceLabel(resourceType)}` : "查看完整路线");
  const label = guideDisplayText(rawLabel);
  const tone = primary ? "primary" : "secondary";
  const sizeClass = primary ? "w-full justify-center" : "min-h-9 px-3 text-xs";

  if (canGenerate) {
    return (
      <Button
        tone={tone}
        className={`${sizeClass} ${className}`}
        onClick={() => onGenerateResource(resourceType, taskId, prompt)}
      >
        {reportResourceIcon(resourceType, primary ? 16 : 14)}
        {label}
      </Button>
    );
  }

  if (opensCoursePackage) {
    return (
      <Button tone={tone} className={`${sizeClass} ${className}`} onClick={onOpenCoursePackage}>
        <GraduationCap size={primary ? 16 : 14} />
        {label}
      </Button>
    );
  }

  if (kind === "save_report") {
    return (
      <Button tone={tone} className={`${sizeClass} ${className}`} disabled={!canSave || saving} onClick={onSave}>
        {saving ? <Loader2 size={primary ? 16 : 14} className="animate-spin" /> : <BookOpen size={primary ? 16 : 14} />}
        {label}
      </Button>
    );
  }

  return (
    <Button tone={tone} className={`${sizeClass} ${className}`} onClick={onOpenRouteMap}>
      <Compass size={primary ? 16 : 14} />
      {label}
    </Button>
  );
}

function reportResourceLabel(type: string) {
  const labels: Record<string, string> = {
    visual: "图解",
    video: "短视频",
    audio: "语音讲解",
    external_video: "精选视频",
    quiz: "练习",
  };
  return labels[type] || type || "资源";
}

function reportResourceIcon(type: ReportResourceType, size = 16) {
  if (type === "quiz") return <ListChecks size={size} />;
  if (type === "video") return <Video size={size} />;
  if (type === "audio") return <Volume2 size={size} />;
  if (type === "external_video") return <Video size={size} />;
  return <Map size={size} />;
}

function normalizeReportResourceType(type: unknown): ReportResourceType {
  if (type === "visual" || type === "video" || type === "audio" || type === "quiz" || type === "external_video") {
    return type;
  }
  return "visual";
}

function feedbackRouteBadge(
  feedback?: Pick<GuideV2LearningFeedback, "score_percent" | "adjustment_types" | "actions"> | null,
): { label: string; tone: "success" | "brand" | "warning" | "neutral" } | null {
  if (!feedback) return null;
  const adjustments = feedback.adjustment_types ?? [];
  const actions = feedback.actions ?? [];
  const actionText = actions.join(" ");
  if (adjustments.some((item) => item.includes("remediation")) || /补救/.test(actionText)) {
    return { label: "先补救", tone: "warning" };
  }
  if (adjustments.some((item) => item.includes("retest")) || /复测/.test(actionText)) {
    return { label: "去复测", tone: "brand" };
  }
  if (adjustments.some((item) => item.includes("transfer")) || /迁移|巩固/.test(actionText)) {
    return { label: "做巩固", tone: "brand" };
  }
  const score = typeof feedback.score_percent === "number" ? feedback.score_percent : null;
  if (score !== null) {
    if (score < 60) return { label: "先补救", tone: "warning" };
    if (score < 75) return { label: "稳一下", tone: "brand" };
    return { label: "继续推进", tone: "success" };
  }
  return null;
}

function summarizeFeedbackRouting(
  items: Array<Pick<GuideV2LearningFeedback, "score_percent" | "adjustment_types" | "actions"> | null | undefined>,
): FeedbackRoutingSummary {
  const counts: Record<string, { label: string; count: number; tone: "success" | "brand" | "warning" | "neutral" }> = {};
  items.forEach((item) => {
    const badge = feedbackRouteBadge(item ?? null);
    if (!badge) return;
    const current = counts[badge.label];
    if (current) {
      current.count += 1;
      return;
    }
    counts[badge.label] = { ...badge, count: 1 };
  });
  return Object.values(counts).sort((left, right) => right.count - left.count);
}

function buildNextActionSteps(
  items: string[],
  routing: FeedbackRoutingSummary,
  weakPoints: string[],
) {
  const normalized = items.map((item) => item.trim()).filter(Boolean);
  const steps = normalized.slice(0, 3).map((item) => {
    if (/复测|再测|验证/.test(item)) {
      return {
        title: weakPoints.length ? `先复测「${weakPoints[0]}」` : "先做一轮复测",
        detail: item,
      };
    }
    if (/补|错因|薄弱|基础/.test(item)) {
      return {
        title: weakPoints.length ? `先补「${weakPoints[0]}」` : "先补当前短板",
        detail: item,
      };
    }
    if (/图解|视频|讲解/.test(item)) {
      return {
        title: "先看一份讲解资源",
        detail: item,
      };
    }
    if (/练习|题/.test(item)) {
      return {
        title: "先做一组短练习",
        detail: item,
      };
    }
    return {
      title: item.length > 16 ? `${item.slice(0, 16)}...` : item,
      detail: item,
    };
  });

  if (steps.length) return steps;

  const dominant = routing[0]?.label || "";
  if (dominant === "先补救") {
    return [
      { title: weakPoints.length ? `先补「${weakPoints[0]}」` : "先补当前错因", detail: "这一轮更适合先把错因补清楚，再继续推进新的内容。" },
      { title: "再做一轮复测", detail: "补完后立刻验证，确认这次不是“看懂了”，而是真的改掉了。" },
    ];
  }
  if (dominant === "去复测") {
    return [
      { title: "先做一轮复测", detail: "这轮更值得确认掌握是否稳定，而不是马上增加新的学习负荷。" },
      { title: "再继续推进", detail: "如果复测稳定，再进入下一组任务或迁移应用会更顺。" },
    ];
  }
  if (dominant === "继续推进") {
    return [
      { title: "直接进入下一步", detail: "这轮整体推进比较顺，下一轮可以少一点铺垫，多一点任务验证。" },
      { title: "保留一次短复盘", detail: "继续推进的同时，仍建议在关键节点留一轮简短复盘来稳住掌握。" },
    ];
  }
  return [];
}
