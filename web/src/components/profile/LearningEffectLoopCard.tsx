import { motion } from "framer-motion";
import { ArrowRight, BarChart3, BookOpenCheck, CheckCircle2, Clock3, GitBranch, Loader2, RotateCcw, Target } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useLearningEffectMutations, useLearningEffectReport } from "@/hooks/useApiQueries";
import type { LearningEffectConcept, LearningEffectNextAction, LearningEffectReport } from "@/lib/types";

type VisualFlowNode = {
  id: string;
  label: string;
  value: string;
  detail: string;
  tone: string;
  icon: ReactNode;
};

export function LearningEffectLoopCard({ courseId = "" }: { courseId?: string }) {
  const reportQuery = useLearningEffectReport({ courseId, window: "14d" });
  const mutations = useLearningEffectMutations();
  const [completedActionId, setCompletedActionId] = useState<string | null>(null);
  const report = reportQuery.data ?? null;

  const primaryAction = useMemo(() => pickPrimaryAction(report), [report]);
  const weakConcepts = useMemo(() => pickWeakConcepts(report), [report]);
  const remediationLoop = report?.remediation_loop ?? null;
  const studyBrief = report?.study_brief ?? null;
  const explainability = report?.explainability ?? null;
  const score = Math.round(Number(report?.overall?.score ?? 0));
  const evidenceCount = Number(report?.summary?.event_count ?? 0);

  if (reportQuery.isLoading) {
    return (
      <section className="rounded-lg border border-line bg-white p-4 shadow-sm" data-testid="learning-effect-loop-loading">
        <div className="flex items-center gap-2 text-sm font-semibold text-ink">
          <Loader2 size={16} className="animate-spin text-brand-purple" />
          正在整理学习效果
        </div>
        <p className="mt-2 text-sm leading-6 text-slate-500">系统会把练习、资源使用和导学反馈汇成一条闭环。</p>
      </section>
    );
  }

  if (reportQuery.isError || !report) {
    return null;
  }

  const completionPending = mutations.completeAction.isPending;
  const statusTone = score >= 78 ? "success" : score >= 58 ? "brand" : "warning";

  const completePrimaryAction = async () => {
    if (!primaryAction) return;
    setCompletedActionId(null);
    const result = await mutations.completeAction.mutateAsync({
      actionId: primaryAction.id,
      note: "Learner marked the recommended learning action as completed from the profile page.",
      courseId: report.course_id || courseId,
      conceptIds: primaryAction.target_concepts,
    });
    setCompletedActionId(result.event.id);
  };

  return (
    <motion.section
      className="rounded-lg border border-line bg-white p-4 shadow-sm"
      data-testid="learning-effect-loop-card"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <BarChart3 size={17} className="text-brand-purple" />
            <p className="text-sm font-semibold text-ink">学习效果闭环</p>
            <Badge tone={statusTone}>{report.overall?.label || "评估中"}</Badge>
          </div>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            {report.overall?.summary || "根据最近的学习证据，系统会自动判断掌握度、薄弱点和下一步行动。"}
          </p>
        </div>
        <div className="grid min-w-[176px] grid-cols-2 gap-2 text-center">
          <MiniMetric label="效果分" value={score ? `${score}` : "待评"} />
          <MiniMetric label="证据" value={`${evidenceCount}`} />
        </div>
      </div>

      <LearningEffectLearnerReceipt report={report} primaryAction={primaryAction} score={score} evidenceCount={evidenceCount} />

      {studyBrief ? <StudyBriefCard brief={studyBrief} primaryAction={primaryAction} /> : null}

      <LearningEffectKnowledgeEvidenceCard report={report} />

      {explainability ? <LearningEffectExplanationCard explanation={explainability} /> : null}

      <LearningEffectVisualMap
        report={report}
        remediationLoop={remediationLoop}
        primaryAction={primaryAction}
        score={score}
        evidenceCount={evidenceCount}
      />

      {primaryAction ? (
        <div className="mt-4 rounded-lg border border-brand-purple-300 bg-tint-lavender p-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Target size={16} className="text-brand-purple" />
                <p className="text-sm font-semibold text-brand-purple">现在先做这一件事</p>
                <Badge tone="neutral">
                  <Clock3 size={12} className="mr-1" />
                  {primaryAction.estimated_minutes || 8} 分钟
                </Badge>
              </div>
              <h3 className="mt-2 text-base font-semibold text-ink">{primaryAction.title}</h3>
              <p className="mt-1 text-sm leading-6 text-charcoal">{primaryAction.reason}</p>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              <a
                href={primaryAction.href || "/guide"}
                className="dt-interactive inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-brand-purple bg-brand-purple px-4 text-sm font-medium text-white hover:bg-brand-purple-800"
                data-testid="learning-effect-loop-start"
              >
                去执行
                <ArrowRight size={15} />
              </a>
              <Button
                tone="secondary"
                disabled={completionPending}
                onClick={() => void completePrimaryAction()}
                data-testid="learning-effect-loop-complete"
              >
                {completionPending ? <Loader2 size={15} className="animate-spin" /> : <CheckCircle2 size={15} />}
                完成并记录
              </Button>
            </div>
          </div>
          {completedActionId ? (
            <p className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 p-2 text-xs leading-5 text-emerald-700">
              已写入学习证据，画像和下一步建议会随之更新。
            </p>
          ) : null}
        </div>
      ) : (
        <div className="mt-4 rounded-lg border border-line bg-canvas p-3 text-sm leading-6 text-slate-600">
          先完成一次导学、练习或资源反馈，系统就能给出更具体的下一步。
        </div>
      )}

      {remediationLoop?.total ? <RemediationLoopStrip loop={remediationLoop} /> : null}

      {weakConcepts.length ? (
        <div className="mt-4 grid gap-2 md:grid-cols-3">
          {weakConcepts.map((concept) => (
            <ConceptChip key={concept.concept_id} concept={concept} />
          ))}
        </div>
      ) : null}
    </motion.section>
  );
}

function StudyBriefCard({
  brief,
  primaryAction,
}: {
  brief: NonNullable<LearningEffectReport["study_brief"]>;
  primaryAction: LearningEffectNextAction | null;
}) {
  const agenda = (brief.agenda ?? []).slice(0, 3);
  const criteria = (brief.success_criteria ?? []).slice(0, 3);
  const avoid = (brief.avoid ?? []).slice(0, 2);
  const firstAction = agenda.find((item) => item.action_href) ?? null;
  const href = firstAction?.action_href || primaryAction?.href || "";
  const label = firstAction?.action_label || (primaryAction ? "开始这一步" : "");

  return (
    <div className="mt-4 rounded-lg border border-line bg-white p-3 shadow-sm" data-testid="learning-effect-study-brief">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="grid size-8 place-items-center rounded-lg bg-tint-yellow text-amber-700">
              <Clock3 size={15} />
            </span>
            <div>
              <p className="text-xs font-semibold text-slate-500">今天只做这一步</p>
              <h3 className="text-base font-semibold text-ink">{brief.headline || "继续学习"}</h3>
            </div>
            <Badge tone="brand">{brief.mode_label || "学习安排"}</Badge>
            <Badge tone="neutral">{brief.timebox_minutes || 10} 分钟</Badge>
          </div>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            {brief.summary || "按当前画像只推进一个最小任务，完成后系统会更新下一步。"}
          </p>
        </div>
        {href ? (
          <a
            href={href}
            className="dt-interactive inline-flex min-h-9 shrink-0 items-center justify-center gap-2 rounded-lg border border-ink bg-ink px-3 text-xs font-medium text-white hover:bg-charcoal"
            data-testid="learning-effect-study-brief-action"
          >
            {label || "开始"}
            <ArrowRight size={13} />
          </a>
        ) : null}
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-[minmax(0,1.2fr)_minmax(220px,0.8fr)]">
        <div className="rounded-lg border border-line bg-canvas p-3">
          <p className="text-xs font-semibold text-slate-500">学习步骤</p>
          <div className="mt-2 grid gap-2">
            {agenda.length ? (
              agenda.map((step, index) => (
                <div key={`${step.label || "step"}-${index}`} className="flex gap-3 rounded-lg border border-line bg-white px-3 py-2">
                  <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-tint-lavender text-xs font-semibold text-brand-purple">
                    {index + 1}
                  </span>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-semibold text-ink">{step.label || "学习步骤"}</p>
                      <span className="text-xs text-slate-400">{step.minutes || 1} 分钟</span>
                    </div>
                    <p className="mt-1 text-xs leading-5 text-slate-600">{step.detail || "完成后留下学习证据。"}</p>
                  </div>
                </div>
              ))
            ) : (
              <p className="rounded-lg border border-line bg-white px-3 py-2 text-xs leading-5 text-slate-500">继续完成一条学习证据，系统会自动生成安排。</p>
            )}
          </div>
        </div>

        <div className="grid gap-3">
          <div className="rounded-lg border border-line bg-canvas p-3">
            <p className="text-xs font-semibold text-slate-500">完成标准</p>
            <div className="mt-2 grid gap-1.5">
              {criteria.length ? criteria.map((item) => <p key={item} className="text-xs leading-5 text-charcoal">- {item}</p>) : <p className="text-xs text-slate-500">完成后回写画像。</p>}
            </div>
          </div>
          <div className="rounded-lg border border-line bg-canvas p-3">
            <p className="text-xs font-semibold text-slate-500">先别做</p>
            <div className="mt-2 grid gap-1.5">
              {avoid.length ? avoid.map((item) => <p key={item} className="text-xs leading-5 text-charcoal">- {item}</p>) : <p className="text-xs text-slate-500">不要开太多任务。</p>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function LearningEffectKnowledgeEvidenceCard({ report }: { report: LearningEffectReport }) {
  const evidence = report.study_brief?.knowledge_evidence;
  const context = report.knowledge_context;
  const kbName = evidence?.kb_name || context?.kb_name || "";
  if (!kbName) return null;

  const ready = Boolean(evidence?.ready ?? context?.ready);
  const metrics =
    evidence?.metrics?.length
      ? evidence.metrics
      : [
          { label: "资料", value: `${context?.document_count ?? 0} 份` },
          { label: "状态", value: context?.status_label || "待检查" },
        ];
  const actionHref = evidence?.action_href || context?.action_href || "/knowledge";
  const actionLabel = evidence?.action_label || context?.action_label || "打开资料库";

  return (
    <div className="mt-4 rounded-lg border border-line bg-canvas p-3" data-testid="learning-effect-knowledge-evidence">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="grid size-8 place-items-center rounded-lg bg-white text-brand-blue">
              <BookOpenCheck size={15} />
            </span>
            <div>
              <p className="text-xs font-semibold text-slate-500">资料依据</p>
              <h3 className="text-base font-semibold text-ink">{kbName}</h3>
            </div>
            <Badge tone={ready ? "success" : "warning"}>{evidence?.status_label || context?.status_label || "待检查"}</Badge>
          </div>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            {evidence?.summary || context?.summary || "下一步执行时会优先检查可用资料库。"}
          </p>
        </div>
        <a
          href={actionHref}
          className="dt-interactive inline-flex min-h-9 shrink-0 items-center justify-center gap-2 rounded-lg border border-line bg-white px-3 text-xs font-medium text-slate-700 hover:border-brand-purple-300 hover:text-brand-purple"
          data-testid="learning-effect-knowledge-open"
        >
          {actionLabel}
          <ArrowRight size={13} />
        </a>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-4">
        {metrics.slice(0, 4).map((item) => (
          <div key={`${item.label || "metric"}-${item.value || ""}`} className="rounded-lg border border-line bg-white px-3 py-2">
            <p className="text-xs font-medium text-slate-500">{item.label || "指标"}</p>
            <p className="mt-1 truncate text-sm font-semibold text-ink">{item.value || "-"}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function LearningEffectExplanationCard({
  explanation,
}: {
  explanation: NonNullable<LearningEffectReport["explainability"]>;
}) {
  const confidence = explanation.confidence ?? {};
  const evidence = (explanation.evidence_used ?? []).slice(0, 4);
  const rules = (explanation.decision_rules ?? []).slice(0, 3);
  const factors = (explanation.attention_factors?.length ? explanation.attention_factors : explanation.score_breakdown ?? []).slice(0, 3);
  const because = (explanation.action_rationale?.because ?? []).slice(0, 3);
  const confidenceTone = confidence.level === "high" ? "success" : confidence.level === "none" || confidence.level === "low" ? "warning" : "brand";

  return (
    <div className="mt-4 rounded-lg border border-line bg-canvas p-3" data-testid="learning-effect-explanation-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="grid size-8 place-items-center rounded-lg bg-white text-brand-purple">
              <GitBranch size={15} />
            </span>
            <div>
              <p className="text-xs font-semibold text-slate-500">为什么这样判断</p>
              <h3 className="text-base font-semibold text-ink">{explanation.headline || "系统综合学习证据生成判断"}</h3>
            </div>
            <Badge tone={confidenceTone}>{confidence.label || "等待证据"}</Badge>
          </div>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            {explanation.summary || "系统会综合作答、资源使用、反思和错因闭环来解释当前评估。"}
          </p>
        </div>
      </div>

      <div className="mt-3 grid gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="rounded-lg border border-line bg-white p-3">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs font-semibold text-slate-500">用到了哪些证据</p>
            {typeof confidence.score === "number" ? <span className="text-xs text-slate-400">可信度 {confidence.score}%</span> : null}
          </div>
          <div className="mt-2 grid gap-2">
            {evidence.map((item) => (
              <div key={`${item.label || "evidence"}-${item.value || ""}`} className="rounded-lg border border-line bg-canvas px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-semibold text-charcoal">{item.label || "学习证据"}</p>
                  <Badge tone={explanationTone(item.tone)}>{item.value || "-"}</Badge>
                </div>
                <p className="mt-1 text-xs leading-5 text-slate-500">{item.detail || "这条证据会参与当前判断。"}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-line bg-white p-3">
          <p className="text-xs font-semibold text-slate-500">判断规则</p>
          <div className="mt-2 grid gap-2">
            {rules.map((rule) => (
              <div key={rule.label || rule.result} className="rounded-lg border border-line bg-canvas px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-semibold text-charcoal">{rule.label || "规则"}</p>
                  <Badge tone={explanationTone(rule.status)}>{rule.status === "success" ? "通过" : rule.status === "warning" ? "需关注" : "观察"}</Badge>
                </div>
                <p className="mt-1 text-xs leading-5 text-slate-600">{rule.result || rule.explanation || "系统会按规则更新判断。"}</p>
                {rule.explanation ? <p className="mt-1 text-xs leading-5 text-slate-400">{rule.explanation}</p> : null}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="rounded-lg border border-line bg-white p-3">
          <p className="text-xs font-semibold text-slate-500">最影响判断的维度</p>
          <div className="mt-2 grid gap-2">
            {factors.map((factor) => {
              const value = Math.max(0, Math.min(100, Math.round(Number(factor.score ?? 0))));
              return (
                <div key={factor.id || factor.label} className="rounded-lg border border-line bg-canvas px-3 py-2">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs font-semibold text-charcoal">{factor.label || "评估维度"}</p>
                    <span className="text-xs text-slate-500">{value}%</span>
                  </div>
                  <div className="mt-2 h-1.5 overflow-hidden rounded-sm bg-white">
                    <div className="h-full rounded-sm bg-brand-purple transition-all" style={{ width: `${Math.max(4, value)}%` }} />
                  </div>
                  <p className="mt-1 text-xs leading-5 text-slate-500">{factor.explanation || "这个维度会影响综合评分。"}</p>
                </div>
              );
            })}
          </div>
        </div>

        <div className="rounded-lg border border-line bg-white p-3">
          <p className="text-xs font-semibold text-slate-500">为什么推荐这一步</p>
          <h4 className="mt-1 text-sm font-semibold text-ink">{explanation.action_rationale?.title || "继续学习"}</h4>
          <p className="mt-1 text-xs leading-5 text-slate-600">
            {explanation.action_rationale?.reason || "系统会选择最小可执行动作，并在完成后回写画像。"}
          </p>
          <div className="mt-2 grid gap-1.5">
            {because.map((item) => (
              <p key={item} className="text-xs leading-5 text-charcoal">- {item}</p>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function pickPrimaryAction(report: LearningEffectReport | null): LearningEffectNextAction | null {
  return [...(report?.next_actions ?? [])].sort((left, right) => Number(right.priority ?? 0) - Number(left.priority ?? 0))[0] ?? null;
}

function pickWeakConcepts(report: LearningEffectReport | null): LearningEffectConcept[] {
  return [...(report?.concepts ?? [])]
    .filter((item) => item.status !== "mastered" || item.open_mistake_count > 0)
    .sort((left, right) => {
      const mistakeGap = Number(right.open_mistake_count ?? 0) - Number(left.open_mistake_count ?? 0);
      if (mistakeGap) return mistakeGap;
      return Number(left.score ?? 0) - Number(right.score ?? 0);
    })
    .slice(0, 3);
}

function LearningEffectLearnerReceipt({
  report,
  primaryAction,
  score,
  evidenceCount,
}: {
  report: LearningEffectReport;
  primaryAction: LearningEffectNextAction | null;
  score: number;
  evidenceCount: number;
}) {
  const receipt = report.learner_receipt;
  const headline = receipt?.headline || (primaryAction ? `现在先做：${primaryAction.title}` : "继续留下学习证据，系统会自动更新画像");
  const evidenceSummary = receipt?.evidence_summary || `已汇总 ${evidenceCount} 条学习证据。`;
  const profileUpdate = receipt?.profile_update || "学习画像会随导学、练习和资源反馈自动更新。";
  const nextStep = receipt?.next_step || primaryAction?.title || "继续学习";
  const reason = receipt?.reason || primaryAction?.reason || report.overall?.summary || "系统会根据最新证据安排下一步。";
  const actionHref = receipt?.action_href || primaryAction?.href || "";
  const actionLabel = receipt?.action_label || "开始这一步";
  const confidenceLabel = receipt?.confidence_label || (evidenceCount >= 4 ? "初步可靠" : "证据偏少");
  const scoreLabel = receipt?.score_label || (score ? `${score} 分` : "待建立");

  return (
    <div className="mt-4 rounded-lg border border-line bg-canvas p-3" data-testid="learning-effect-learner-receipt">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <CheckCircle2 size={16} className="text-emerald-600" />
            <p className="text-xs font-semibold text-slate-500">学习闭环回执</p>
            <Badge tone="neutral">{scoreLabel}</Badge>
            <Badge tone={confidenceLabel === "证据较充分" ? "success" : confidenceLabel === "等待证据" ? "warning" : "brand"}>{confidenceLabel}</Badge>
          </div>
          <h3 className="mt-2 text-base font-semibold text-ink">{headline}</h3>
          <p className="mt-1 text-sm leading-6 text-slate-600">{evidenceSummary}</p>
        </div>
        {actionHref ? (
          <a
            href={actionHref}
            className="dt-interactive inline-flex min-h-9 shrink-0 items-center justify-center gap-2 rounded-lg border border-ink bg-ink px-3 text-xs font-medium text-white hover:bg-charcoal"
            data-testid="learning-effect-learner-receipt-action"
          >
            {actionLabel}
            <ArrowRight size={13} />
          </a>
        ) : null}
      </div>
      <div className="mt-3 grid gap-2 md:grid-cols-2">
        <div className="rounded-lg border border-line bg-white px-3 py-2" data-testid="learning-effect-learner-receipt-profile">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-500">
            <GitBranch size={13} />
            画像更新
          </div>
          <p className="mt-1 text-xs leading-5 text-charcoal">{profileUpdate}</p>
        </div>
        <div className="rounded-lg border border-line bg-white px-3 py-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-500">
            <Target size={13} />
            下一步
          </div>
          <p className="mt-1 text-xs font-semibold text-ink">{nextStep}</p>
          <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{reason}</p>
        </div>
      </div>
    </div>
  );
}

function LearningEffectVisualMap({
  report,
  remediationLoop,
  primaryAction,
  score,
  evidenceCount,
}: {
  report: LearningEffectReport;
  remediationLoop: LearningEffectReport["remediation_loop"] | null;
  primaryAction: LearningEffectNextAction | null;
  score: number;
  evidenceCount: number;
}) {
  const visualization = report.visualization;
  const actionCount = report.next_actions?.length ?? 0;
  const totalLoop = Number(remediationLoop?.total ?? 0);
  const pendingLoop = Number(remediationLoop?.pending_remediation_count ?? 0);
  const readyLoop = Number(remediationLoop?.ready_for_retest_count ?? 0);
  const closedLoop = Number(remediationLoop?.closed_count ?? 0);
  const quizCount = Number(report.summary?.quiz_count ?? 0);
  const resourceCount = Number(report.summary?.resource_count ?? 0);
  const dimensions = (visualization?.dimension_bars?.length ? visualization.dimension_bars : report.dimensions ?? []).slice(0, 4);
  const timeline = (visualization?.evidence_timeline ?? []).slice(0, 3);
  const flowNodes =
    visualization?.nodes?.length
      ? visualization.nodes.map((node) => ({
          id: node.id || node.label || "node",
          label: node.label || "节点",
          value: node.value || "",
          detail: node.detail || "",
          tone: node.tone || "brand",
          icon: visualNodeIcon(node.id),
        }))
      : [
          {
            id: "evidence",
            label: "证据流",
            value: `${evidenceCount} 条`,
            detail: `${quizCount} 次练习 · ${resourceCount} 个资源`,
            tone: "brand",
            icon: <GitBranch size={15} />,
          },
          {
            id: "assessment",
            label: "效果评估",
            value: score ? `${score} 分` : "待评",
            detail: report.overall?.label || "等待更多证据",
            tone: "brand",
            icon: <BarChart3 size={15} />,
          },
          {
            id: "dispatch",
            label: "动态调度",
            value: `${actionCount} 个动作`,
            detail: actionCount ? "已生成下一步" : "继续收集证据",
            tone: "brand",
            icon: <Target size={15} />,
          },
          {
            id: "closed_loop",
            label: "闭环进度",
            value: totalLoop ? `${closedLoop}/${totalLoop}` : "0/0",
            detail: totalLoop ? `待补 ${pendingLoop} · 待测 ${readyLoop}` : "暂无错因任务",
            tone: "brand",
            icon: <RotateCcw size={15} />,
          },
        ];
  const evidenceNode = flowNodes.find((node) => node.id === "evidence") ?? flowNodes[0];
  const assessmentNode = flowNodes.find((node) => node.id === "assessment") ?? flowNodes[1];
  const dispatchNode = flowNodes.find((node) => node.id === "dispatch") ?? flowNodes[2];
  const loopNode = flowNodes.find((node) => node.id === "closed_loop") ?? flowNodes[3];
  const loopPercent = totalLoop ? Math.round((closedLoop / Math.max(1, totalLoop)) * 100) : 0;

  return (
    <div className="mt-4 rounded-lg border border-line bg-canvas p-3" data-testid="learning-effect-visual-map">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-ink">学习效果地图</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            {visualization?.summary || "证据进入画像后，会经过评估、调度和错因闭环。"}
          </p>
        </div>
        <Badge tone={closedLoop && totalLoop === closedLoop ? "success" : pendingLoop ? "warning" : "brand"}>闭环图</Badge>
      </div>

      <div className="mt-3 grid gap-3 xl:grid-cols-[minmax(0,0.95fr)_minmax(260px,0.9fr)_minmax(0,1fr)]">
        <div className="rounded-lg border border-line bg-white p-3">
          <MapNodeHeader node={evidenceNode} />
          <LearningEvidenceMiniTimeline items={timeline} compact />
        </div>

        <div className="rounded-lg border border-brand-purple-300 bg-white p-3 shadow-soft">
          <MapNodeHeader node={assessmentNode} emphasized />
          <div className="mt-3 grid place-items-center rounded-lg border border-line bg-canvas px-4 py-5 text-center">
            <div
              className="grid size-24 place-items-center rounded-lg p-2"
              style={{ background: `conic-gradient(#5645D4 ${Math.max(0, Math.min(100, score)) * 3.6}deg, #E5E3DF 0deg)` }}
              aria-label={`学习效果分 ${score || 0}`}
            >
              <div className="grid h-full w-full place-items-center rounded-lg border border-line bg-white">
                <span className="text-2xl font-semibold text-ink">{score || "待评"}</span>
              </div>
            </div>
            <p className="mt-3 text-sm font-semibold text-ink">{report.overall?.label || "等待更多证据"}</p>
            <p className="mt-1 max-w-xs text-xs leading-5 text-slate-500">{report.overall?.summary || assessmentNode?.detail}</p>
          </div>
          {dimensions.length ? <DimensionMiniBars dimensions={dimensions} /> : null}
        </div>

        <div className="rounded-lg border border-line bg-white p-3">
          <MapNodeHeader node={dispatchNode} />
          <div className="mt-3 rounded-lg border border-line bg-canvas p-3" data-testid="learning-effect-prescription-panel">
            <div className="flex items-start gap-3">
              <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-tint-yellow text-amber-700">
                <Target size={16} />
              </span>
              <div className="min-w-0">
                <p className="text-xs font-semibold text-slate-500">下一步处方</p>
                <p className="mt-1 text-sm font-semibold text-ink">{primaryAction?.title || "先完成一次诊断或练习"}</p>
                <p className="mt-1 line-clamp-3 text-xs leading-5 text-slate-600">
                  {primaryAction?.reason || "系统会根据新证据生成更准确的补救、复测或复习建议。"}
                </p>
              </div>
            </div>
            {primaryAction?.href ? (
              <a
                href={primaryAction.href}
                className="dt-interactive mt-3 inline-flex min-h-9 w-full items-center justify-center gap-2 rounded-lg border border-brand-purple bg-brand-purple px-3 text-xs font-medium text-white hover:bg-brand-purple-800"
                data-testid="learning-effect-map-primary-action"
              >
                立即执行
                <ArrowRight size={13} />
              </a>
            ) : null}
          </div>
          <div className="mt-3 rounded-lg border border-line bg-canvas p-3">
            <MapNodeHeader node={loopNode} compact />
            <div className="mt-3 h-2 overflow-hidden rounded-md bg-white">
              <div className="h-full rounded-md bg-brand-purple transition-all" style={{ width: `${Math.max(totalLoop ? 8 : 0, loopPercent)}%` }} />
            </div>
            <p className="mt-2 text-xs leading-5 text-slate-500">
              {totalLoop ? `已闭环 ${closedLoop} 个，待补救 ${pendingLoop} 个，待复测 ${readyLoop} 个。` : "暂无错因任务，继续留下练习证据即可。"}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function LearningEvidenceMiniTimeline({
  items,
  compact = false,
}: {
  items: NonNullable<NonNullable<LearningEffectReport["visualization"]>["evidence_timeline"]>;
  compact?: boolean;
}) {
  if (!items.length) {
    return (
      <div className="mt-3 rounded-lg border border-line bg-canvas px-3 py-4 text-xs leading-5 text-slate-500" data-testid="learning-effect-evidence-timeline">
        还没有足够证据。先做一次导学、练习或资源反馈。
      </div>
    );
  }

  return (
    <div className={compact ? "mt-3" : "mt-3 rounded-lg border border-line bg-white p-3"} data-testid="learning-effect-evidence-timeline">
      {!compact ? (
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs font-semibold text-ink">最近证据</p>
          <span className="text-xs text-slate-400">自动回写</span>
        </div>
      ) : (
        <p className="text-xs font-semibold text-ink">最近证据</p>
      )}
      <div className={compact ? "mt-3 space-y-2" : "mt-3 grid gap-2 md:grid-cols-3"}>
        {items.map((item) => (
          <div key={item.id || item.label} className="relative rounded-lg border border-line bg-canvas px-3 py-2">
            {compact ? <span className="absolute -left-1 top-3 size-2 rounded-sm bg-brand-purple" /> : null}
            <div className="flex items-center justify-between gap-2">
              <p className="min-w-0 truncate text-xs font-semibold text-charcoal">{item.label || "学习证据"}</p>
              {typeof item.score === "number" ? <Badge tone={item.score >= 80 ? "success" : item.score >= 50 ? "brand" : "warning"}>{item.score}%</Badge> : null}
            </div>
            <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{item.detail || evidenceKindLabel(item.kind)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function MapNodeHeader({ node, emphasized = false, compact = false }: { node?: VisualFlowNode; emphasized?: boolean; compact?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="flex min-w-0 items-center gap-2">
        <span className={`grid shrink-0 place-items-center rounded-lg ${compact ? "size-7" : "size-8"} ${nodeToneClass(node?.tone)}`}>{node?.icon}</span>
        <div className="min-w-0">
          <p className={`truncate text-xs font-semibold ${emphasized ? "text-brand-purple" : "text-slate-500"}`}>{node?.label || "节点"}</p>
          <p className={`${compact ? "text-sm" : "text-base"} font-semibold text-ink`}>{node?.value || "-"}</p>
        </div>
      </div>
      {!compact && node?.detail ? <span className="max-w-[8.5rem] truncate text-right text-xs text-slate-400">{node.detail}</span> : null}
    </div>
  );
}

function DimensionMiniBars({
  dimensions,
}: {
  dimensions: Array<{ id?: string; label?: string; score?: number; status?: string; evidence?: string }>;
}) {
  return (
    <div className="mt-3 grid gap-2" data-testid="learning-effect-dimension-bars">
      {dimensions.slice(0, 3).map((dimension) => {
        const value = Math.max(0, Math.min(100, Math.round(Number(dimension.score ?? 0))));
        return (
          <div key={dimension.id || dimension.label} className="rounded-lg border border-line bg-white px-3 py-2">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-semibold text-charcoal">{learningDimensionLabel(dimension.id, dimension.label)}</p>
              <span className="text-xs text-slate-500">{value}%</span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-sm bg-canvas">
              <div className="h-full rounded-sm bg-brand-purple transition-all" style={{ width: `${Math.max(4, value)}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function RemediationLoopStrip({ loop }: { loop: NonNullable<LearningEffectReport["remediation_loop"]> }) {
  const primary = loop.items.find((item) => item.status !== "closed") ?? loop.items[0] ?? null;
  const tone = loop.pending_remediation_count ? "warning" : loop.ready_for_retest_count ? "brand" : "success";
  return (
    <div className="mt-4 rounded-lg border border-line bg-canvas p-3" data-testid="learning-effect-remediation-loop">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-ink">错因闭环</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            待补救 {loop.pending_remediation_count} · 待复测 {loop.ready_for_retest_count} · 已闭环 {loop.closed_count}
          </p>
        </div>
        <Badge tone={tone}>{primary?.status_label || "已同步"}</Badge>
      </div>
      {primary ? (
        <div className="mt-3 rounded-lg border border-line bg-white p-3" data-testid="learning-effect-remediation-explanation">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-ink">{primary.title || "补齐当前薄弱点"}</p>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                {primary.concept || "薄弱概念"} · {primary.estimated_minutes || 10} 分钟 · {primary.resource_type || "resource"}
              </p>
            </div>
            {primary.progress_label ? <Badge tone={tone}>{primary.progress_label}</Badge> : null}
          </div>
          <RemediationStepper status={primary.status || "pending_remediation"} />
          {primary.evidence_summary ? <p className="mt-3 text-xs leading-5 text-charcoal">{primary.evidence_summary}</p> : null}
          {primary.reason ? (
            <p className="mt-2 rounded-lg border border-line bg-canvas px-3 py-2 text-xs leading-5 text-slate-600">判断：{primary.reason}</p>
          ) : null}
          {primary.next_step ? (
            <div className="mt-2 rounded-lg border border-brand-purple-300 bg-tint-lavender px-3 py-2">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-semibold text-brand-purple">下一步</p>
                  <p className="mt-1 text-xs leading-5 text-charcoal">{primary.next_step}</p>
                </div>
                {primary.action_href ? (
                  <a
                    href={primary.action_href}
                    className="dt-interactive inline-flex min-h-8 shrink-0 items-center justify-center gap-1 rounded-lg border border-brand-purple bg-brand-purple px-3 text-xs font-medium text-white hover:bg-brand-purple-800"
                    data-testid="learning-effect-remediation-action"
                  >
                    {primary.action_label || "去执行"}
                    <ArrowRight size={13} />
                  </a>
                ) : null}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function RemediationStepper({ status }: { status: string }) {
  const currentIndex = status === "closed" ? 2 : status === "ready_for_retest" ? 1 : 0;
  const steps = [
    { label: "补救", hint: "先补齐薄弱点" },
    { label: "复测", hint: "用小测确认" },
    { label: "闭环", hint: "进入复习" },
  ];
  return (
    <div className="mt-3 grid gap-2 sm:grid-cols-3" data-testid="learning-effect-remediation-stepper">
      {steps.map((step, index) => {
        const active = index === currentIndex;
        const done = status === "closed" || index < currentIndex;
        return (
          <div
            key={step.label}
            className={`rounded-lg border px-3 py-2 ${
              active
                ? "border-brand-purple-300 bg-tint-lavender text-brand-purple"
                : done
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                  : "border-line bg-canvas text-slate-500"
            }`}
            aria-current={active ? "step" : undefined}
          >
            <div className="flex items-center gap-2">
              <span className={`h-2.5 w-2.5 shrink-0 rounded-sm ${done ? "bg-emerald-500" : active ? "bg-brand-purple" : "bg-slate-300"}`} />
              <p className="text-xs font-semibold">{step.label}</p>
            </div>
            <p className="mt-1 text-xs leading-5 opacity-80">{step.hint}</p>
          </div>
        );
      })}
    </div>
  );
}

function ConceptChip({ concept }: { concept: LearningEffectConcept }) {
  const score = Math.round(Number(concept.score ?? 0) * 100);
  const tone = concept.status === "mastered" ? "success" : concept.status === "needs_support" ? "warning" : "brand";
  return (
    <div className="rounded-lg border border-line bg-canvas p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="min-w-0 truncate text-sm font-semibold text-ink">{concept.title || concept.concept_id}</p>
        <Badge tone={tone}>{score}%</Badge>
      </div>
      <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-600">
        {concept.recommendation || concept.common_mistakes?.[0] || "继续留下练习证据，系统会判断是否需要复习。"}
      </p>
    </div>
  );
}

function visualNodeIcon(id?: string) {
  if (id === "evidence") return <GitBranch size={15} />;
  if (id === "assessment") return <BarChart3 size={15} />;
  if (id === "dispatch") return <Target size={15} />;
  return <RotateCcw size={15} />;
}

function nodeToneClass(tone?: string) {
  if (tone === "success" || tone === "good") return "bg-emerald-50 text-emerald-700";
  if (tone === "warning" || tone === "watch" || tone === "needs_support") return "bg-amber-50 text-amber-700";
  if (tone === "thin_evidence" || tone === "neutral") return "bg-white text-slate-500 border border-line";
  return "bg-tint-lavender text-brand-purple";
}

function explanationTone(tone?: string): "neutral" | "success" | "warning" | "brand" {
  if (tone === "success" || tone === "good") return "success";
  if (tone === "warning" || tone === "thin_evidence" || tone === "needs_support") return "warning";
  if (tone === "brand" || tone === "watch") return "brand";
  return "neutral";
}

function evidenceKindLabel(kind?: string) {
  const labels: Record<string, string> = {
    quiz: "练习作答",
    completion: "任务完成",
    resource: "资源使用",
    reflection: "学习反思",
    evidence: "学习证据",
  };
  return labels[String(kind || "")] || "学习证据";
}

function learningDimensionLabel(id?: string, fallback?: string) {
  const labels: Record<string, string> = {
    mastery: "知识掌握",
    progress: "学习推进",
    stability: "稳定迁移",
    evidence_quality: "证据质量",
    engagement: "学习投入",
    remediation: "错因闭环",
    resource_effectiveness: "资源有效性",
  };
  return labels[String(id || "")] || fallback || "评估维度";
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-line bg-canvas px-3 py-2">
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className="mt-1 text-base font-semibold text-ink">{value}</p>
    </div>
  );
}
