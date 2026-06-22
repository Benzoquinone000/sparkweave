import {
  ArrowRight,
  CheckCircle2,
  Database,
  FileSearch,
  GitBranch,
  Layers3,
  RotateCcw,
  SearchCheck,
  Sparkles,
  Wrench,
} from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/Badge";
import { buildKnowledgePreflightHref } from "@/lib/ragHandoff";
import type { RagEvidence, RagSource, RagSubQuery } from "@/lib/ragEvidence";

export function RagEvidenceChain({
  evidence,
  className = "",
  showRecoveryLink = true,
}: {
  evidence: RagEvidence;
  className?: string;
  showRecoveryLink?: boolean;
}) {
  const sources = evidence.sources.slice(0, 5);
  const subqueries = evidence.subqueries.slice(0, 4);
  const qualityChecks = evidence.qualityChecks.slice(0, 5);
  const hasQuality = Boolean(evidence.qualityStatus || typeof evidence.qualityScore === "number" || qualityChecks.length);
  const evidenceStatus = describeEvidenceStatus(evidence, sources.length);
  const recoveryHref = showRecoveryLink ? buildKnowledgePreflightHref(evidence, evidenceStatus) : "";

  return (
    <section className={`dt-rag-evidence-chain dt-dynamic-result dt-flow-strip rounded-lg border border-line bg-canvas p-3 ${className}`} data-testid="rag-evidence-chain">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-2">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-line bg-white text-brand-purple">
            {evidence.agentic ? <GitBranch size={16} /> : <FileSearch size={16} />}
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-semibold text-ink">资料来源</p>
              <Badge tone={evidenceStatus.tone}>{evidenceStatus.badge}</Badge>
              <Badge tone={evidence.agentic ? "brand" : "neutral"}>{evidence.agentic ? "多路查找" : "快速查找"}</Badge>
              {evidence.agenticRepaired ? <Badge tone="success">已修复</Badge> : null}
              {evidence.agenticFallback ? <Badge tone="warning">已改用轻量查找</Badge> : null}
              {evidence.queryTransformApplied ? <Badge tone="success">已补充关键词</Badge> : null}
            </div>
            <p className="mt-1 line-clamp-2 text-xs leading-5 text-steel">
              {evidence.query || "系统已从资料库中抽取可引用片段。"}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 text-xs text-steel">
          {evidence.kbName ? <MetaPill icon={<Database size={13} />} label={`资料库 ${evidence.kbName}`} /> : null}
          {evidence.retrievalMode ? <MetaPill icon={<Layers3 size={13} />} label={formatRetrievalMode(evidence.retrievalMode)} /> : null}
          {evidence.retrievalProfile ? <MetaPill icon={<Sparkles size={13} />} label={formatRetrievalProfile(evidence.retrievalProfile)} /> : null}
          <MetaPill icon={<SearchCheck size={13} />} label={`${evidence.sourceCount || sources.length} 条来源`} />
        </div>
      </div>

      <EvidenceSummaryCard evidence={evidence} status={evidenceStatus} sourceCount={sources.length} recoveryHref={recoveryHref} />
      <details className="dt-rag-evidence-details mt-2 rounded-lg border border-line bg-white px-3 py-2">
        <summary className="dt-interactive flex min-h-8 cursor-pointer list-none items-center justify-between gap-3 text-xs font-semibold text-ink [&::-webkit-details-marker]:hidden">
          <span className="inline-flex min-w-0 items-center gap-2">
            <SearchCheck size={14} className="shrink-0 text-brand-purple" />
            <span className="truncate">查看来源与检索过程</span>
          </span>
          <span className="shrink-0 font-medium text-steel">{sources.length ? `${sources.length} 条来源` : "无来源"}</span>
        </summary>

        <div className="mt-3 space-y-3">
          {evidenceStatus.steps?.length ? <EvidenceNextSteps steps={evidenceStatus.steps} /> : null}
          <EvidenceWaterfall
            evidence={evidence}
            sources={sources}
            subqueries={subqueries}
            qualityChecks={qualityChecks}
            status={evidenceStatus}
          />

          {(evidence.agentic || evidence.agenticFallback) && (evidence.planReason || evidence.activityRecommendation || hasQuality) ? (
            <div className="dt-dynamic-panel rounded-lg border border-line bg-white px-3 py-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs font-semibold text-ink">
                  {evidence.agenticFallback ? "轻量查找" : evidence.agenticRepaired ? "补强来源" : "多路查找"}
                </p>
                {hasQuality ? (
                  <div className="flex flex-wrap gap-1.5">
                    <MiniTag tone={evidence.qualityStatus === "weak" ? "warning" : "success"}>
                      {evidence.qualityStatus === "weak" ? "来源偏弱" : "来源充足"}
                    </MiniTag>
                    {typeof evidence.qualityScore === "number" ? <MiniTag>{formatPercent(evidence.qualityScore)}</MiniTag> : null}
                  </div>
                ) : null}
              </div>
              {evidence.explanationSummary ? (
                <p className="mt-1 text-xs leading-5 text-slate-600">
                  {formatExplanationSummary(evidence.explanationDecision, evidence.explanationSummary)}
                </p>
              ) : null}
              {evidence.planReason ? <p className="mt-1 text-xs leading-5 text-steel">触发原因：{formatPlanReason(evidence.planReason)}</p> : null}
              {evidence.activityRecommendation ? (
                <p className="mt-1 text-xs leading-5 text-slate-600">{formatRecommendation(evidence.activityRecommendation)}</p>
              ) : null}
              {hasQuality ? (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {typeof evidence.coverageRatio === "number" ? <MiniTag>覆盖 {formatPercent(evidence.coverageRatio)}</MiniTag> : null}
                  {typeof evidence.relevantCoverageRatio === "number" ? (
                    <MiniTag>相关来源 {formatPercent(evidence.relevantCoverageRatio)}</MiniTag>
                  ) : null}
                  {typeof evidence.contextChars === "number" ? (
                    <MiniTag tone={evidence.contextTruncated ? "warning" : "neutral"}>
                      回答材料 {evidence.contextMaxChars ? `${evidence.contextChars}/${evidence.contextMaxChars}` : evidence.contextChars} 字
                    </MiniTag>
                  ) : null}
                  {evidence.qualityReasons.slice(0, 3).map((reason) => (
                    <MiniTag key={reason} tone="warning">
                      {formatQualityReason(reason)}
                    </MiniTag>
                  ))}
                </div>
              ) : null}
              {qualityChecks.length ? (
                <div className="mt-2 grid gap-1.5 sm:grid-cols-2">
                  {qualityChecks.map((check) => (
                    <div key={check.code} className="dt-dynamic-panel rounded-md border border-line bg-canvas px-2 py-1.5">
                      <div className="flex items-center justify-between gap-2">
                        <p className="truncate text-[11px] font-semibold leading-4 text-ink">{formatQualityCheckCode(check.code)}</p>
                        <MiniTag tone={check.status === "failed" ? "warning" : "success"}>
                          {check.status === "failed" ? "需关注" : "通过"}
                        </MiniTag>
                      </div>
                      <p className="mt-1 text-[11px] leading-4 text-steel">
                        {formatQualityCheckValue(check.observed)} / {formatQualityCheckValue(check.threshold)}
                      </p>
                    </div>
                  ))}
                </div>
              ) : null}
              {evidence.agenticFallback ? (
                <p className="mt-1 text-xs leading-5 text-slate-600">
                  多路查找仍未拿到足够来源，系统已自动回到轻量查找，保证本轮回答继续有资料支撑。
                </p>
              ) : null}
            </div>
          ) : null}

          {subqueries.length ? (
            <div className="grid gap-2 md:grid-cols-2">
              {subqueries.map((item) => (
                <SubQueryCard key={`${item.index}-${item.query}`} item={item} />
              ))}
            </div>
          ) : null}

          {sources.length ? (
            <div className="space-y-2">
              {sources.map((source, index) => (
                <SourceCard key={`${source.title}-${source.source}-${index}`} source={source} index={index + 1} />
              ))}
            </div>
          ) : (
            <p className="dt-dynamic-empty rounded-lg border border-line bg-white px-3 py-2 text-xs leading-5 text-steel">
              本轮没有返回可展示的资料片段，回答主要来自模型归纳。建议确认资料库已选择、文档已处理完成后再问。
            </p>
          )}
        </div>
      </details>
    </section>
  );
}

function EvidenceWaterfall({
  evidence,
  sources,
  subqueries,
  qualityChecks,
  status,
}: {
  evidence: RagEvidence;
  sources: RagSource[];
  subqueries: RagSubQuery[];
  qualityChecks: RagEvidence["qualityChecks"];
  status: EvidenceStatus;
}) {
  const steps = [
    {
      label: "用户问题",
      detail: evidence.query || "收到一个需要资料支撑的学习问题。",
      icon: FileSearch,
      tone: "brand" as const,
    },
    {
      label: "问题拆解",
      detail: subqueries.length ? `拆成 ${subqueries.length} 个查找视角。` : "问题较集中，本轮不需要额外拆分。",
      icon: GitBranch,
      tone: subqueries.length ? "brand" as const : "neutral" as const,
    },
    {
      label: "查找视角",
      detail: evidence.agentic ? "多路查找并互相补来源。" : "按当前资料库快速查找。",
      icon: Database,
      tone: evidence.agentic ? "brand" as const : "neutral" as const,
    },
    {
      label: "来源片段",
      detail: sources.length ? `筛出 ${evidence.sourceCount || sources.length} 条可展示来源。` : "暂未找到可展示来源。",
      icon: Layers3,
      tone: sources.length ? "success" as const : "warning" as const,
    },
    {
      label: "可用性判断",
      detail: qualityChecks.length ? `${qualityChecks.length} 项检查，结论：${status.badge}。` : status.summary,
      icon: SearchCheck,
      tone: status.tone,
    },
    {
      label: "最终回答",
      detail: status.tone === "warning" ? "带着来源强弱提示生成回答。" : "把可用来源汇总成学习讲解。",
      icon: Sparkles,
      tone: status.tone === "neutral" ? "neutral" as const : "success" as const,
    },
  ];

  return (
    <div className="dt-dynamic-panel dt-flow-strip mt-3 rounded-lg border border-line bg-white p-3" data-testid="rag-evidence-waterfall">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="brand">来源整理</Badge>
          <span className="text-xs font-medium text-ink">回答前的资料查找过程</span>
        </div>
        <Badge tone={status.tone}>{status.badge}</Badge>
      </div>
      <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
        {steps.map((step, index) => {
          const Icon = step.icon;
          return (
            <div key={step.label} className="flex shrink-0 items-start gap-2">
              <div className={`min-h-[7rem] w-36 rounded-lg border p-3 ${waterfallCardTone(step.tone)}`}>
                <div className="flex items-center justify-between gap-2">
                  <span className="grid h-8 w-8 place-items-center rounded-lg border border-line bg-white text-brand-purple">
                    <Icon size={15} />
                  </span>
                  <span className="text-[11px] font-semibold text-slate-400">0{index + 1}</span>
                </div>
                <p className="mt-2 text-sm font-semibold text-ink">{step.label}</p>
                <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-600">{step.detail}</p>
              </div>
              {index < steps.length - 1 ? (
                <span className="mt-12 shrink-0 text-slate-300">
                  <ArrowRight size={16} />
                </span>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

type EvidenceStatus = {
  tone: "success" | "warning" | "neutral";
  badge: string;
  title: string;
  summary: string;
  nextAction: string;
  steps?: Array<{
    label: string;
    detail: string;
  }>;
};

function describeEvidenceStatus(evidence: RagEvidence, visibleSourceCount: number): EvidenceStatus {
  const sourceCount = evidence.sourceCount || visibleSourceCount;
  const weak =
    evidence.qualityStatus === "weak" ||
    evidence.agenticFallback ||
    evidence.qualityReasons.some((reason) =>
      ["low_context_chars", "low_relevance_coverage", "low_score", "low_source_count", "low_subquery_coverage"].includes(reason),
    ) ||
    sourceCount < 2;

  if (!sourceCount) {
    return {
      tone: "neutral",
      badge: "无来源",
      title: "这次没有找到可引用资料",
      summary: "回答可能主要来自模型已有知识，不能代表资料库里的确定内容。",
      nextAction: "下一步：确认已选择资料库，或到资料库页面检查文档是否处理完成。",
      steps: [
        { label: "确认资料库", detail: "先确认本轮问题绑定了正确资料库。" },
        { label: "检查整理", detail: "确认文档已经处理出引用片段。" },
        { label: "复测问题", detail: "带这个问题去预检，扩大来源后再问。" },
      ],
    };
  }

  if (weak) {
    return {
      tone: "warning",
      badge: "来源偏弱",
      title: "回答有资料支撑，但来源还不够稳",
      summary: "系统已经找到资料片段，但覆盖、相关性或回答材料长度仍可能不足。",
      nextAction: "下一步：可以把问题说得更具体，或补充相关资料后再问一次。",
      steps: [
        { label: "收窄问题", detail: "把问题改得更具体，减少无关片段。" },
        { label: "提高来源", detail: "扩大来源上限或回答材料上限。" },
        { label: "核对片段", detail: "展开来源，确认关键结论来自可信资料。" },
      ],
    };
  }

  return {
    tone: "success",
      badge: "来源可用",
      title: "回答已有资料支撑",
      summary: "系统找到了可引用片段，并把它们作为本轮回答的来源。",
      nextAction: "下一步：可以展开下方来源，核对关键结论是否来自你信任的资料。",
      steps: [
        { label: "核对来源", detail: "先看关键来源是否覆盖核心结论。" },
        { label: "继续追问", detail: "再问一个更具体的应用或例题。" },
        { label: "保存记录", detail: "把有价值结论沉淀到学习记录。" },
      ],
    };
}

function EvidenceSummaryCard({
  evidence,
  status,
  sourceCount,
  recoveryHref,
}: {
  evidence: RagEvidence;
  status: EvidenceStatus;
  sourceCount: number;
  recoveryHref: string;
}) {
  const contextLabel =
    typeof evidence.contextChars === "number"
      ? evidence.contextMaxChars
        ? `${evidence.contextChars}/${evidence.contextMaxChars} 字`
        : `${evidence.contextChars} 字`
      : "-";

  return (
    <div className="dt-dynamic-panel mt-3 rounded-lg border border-line bg-white px-3 py-2">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-ink">{status.title}</p>
          <p className="mt-1 text-xs leading-5 text-slate-600">{status.summary}</p>
        </div>
        <Badge tone={status.tone}>{status.badge}</Badge>
      </div>
      <div className="mt-2 grid gap-2 sm:grid-cols-3">
        <EvidenceFact label="可见来源" value={`${sourceCount} 条`} />
        <EvidenceFact label="覆盖情况" value={formatCoverageLabel(evidence)} />
        <EvidenceFact label="回答材料" value={contextLabel} warning={evidence.contextTruncated} />
      </div>
      <p className="dt-dynamic-empty mt-2 rounded-md border border-line bg-canvas px-2 py-1.5 text-xs leading-5 text-steel">{status.nextAction}</p>
      {recoveryHref ? (
        <a
          href={recoveryHref}
          className="dt-interactive mt-2 inline-flex min-h-8 items-center justify-center gap-2 rounded-md border border-brand-purple bg-white px-2.5 text-xs font-medium text-brand-purple transition hover:bg-tint-lavender"
          data-testid="rag-evidence-open-preflight"
        >
          <SearchCheck size={14} />
          {status.tone === "neutral" ? "带这个问题去预检" : "复测来源质量"}
        </a>
      ) : null}
    </div>
  );
}

function EvidenceNextSteps({ steps }: { steps: NonNullable<EvidenceStatus["steps"]> }) {
  return (
    <div className="grid gap-2 md:grid-cols-[minmax(0,1fr)_1.75rem_minmax(0,1fr)_1.75rem_minmax(0,1fr)]">
      {steps.slice(0, 3).map((step, index) => (
        <div key={`${step.label}-${index}`} className="contents">
          <div className="rounded-md border border-line bg-canvas px-2 py-1.5">
            <p className="text-[11px] font-semibold text-ink">{step.label}</p>
            <p className="mt-0.5 line-clamp-2 text-[11px] leading-4 text-steel">{step.detail}</p>
          </div>
          {index < Math.min(steps.length, 3) - 1 ? (
            <div className="hidden place-items-center text-slate-300 md:grid">
              <ArrowRight size={13} />
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function EvidenceFact({
  label,
  value,
  warning,
}: {
  label: string;
  value: string;
  warning?: boolean;
}) {
  return (
    <div className="dt-dynamic-panel rounded-md border border-line bg-canvas px-2 py-1.5">
      <p className="text-[11px] leading-4 text-steel">{label}</p>
      <p className={`mt-0.5 truncate text-xs font-semibold ${warning ? "text-amber-700" : "text-ink"}`}>{value}</p>
    </div>
  );
}

function SubQueryCard({ item }: { item: RagSubQuery }) {
  const status = item.success === false ? "failed" : item.relevant === false ? "weak" : "ok";
  return (
    <div className="dt-dynamic-result rounded-lg border border-line bg-white px-3 py-2">
      <div className="flex items-start gap-2">
        <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-md bg-tint-lavender text-xs font-semibold text-brand-purple">
          {item.index}
        </span>
        <div className="min-w-0">
          <div className="flex items-start gap-1.5">
            <StatusIcon status={status} />
            <p className="line-clamp-2 min-w-0 text-xs font-semibold leading-5 text-charcoal">{item.query}</p>
          </div>
          <p className="mt-1 line-clamp-2 text-xs leading-5 text-steel">{item.purpose}</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {typeof item.sourceCount === "number" ? <MiniTag>{item.sourceCount} 条来源</MiniTag> : null}
            {typeof item.contentChars === "number" ? <MiniTag>{item.contentChars} 字回答材料</MiniTag> : null}
            {typeof item.relevanceScore === "number" ? <MiniTag>相关 {formatPercent(item.relevanceScore)}</MiniTag> : null}
            {item.action ? <MiniTag tone={item.action.includes("repair") ? "success" : "neutral"}>{formatStepAction(item.action)}</MiniTag> : null}
            {item.repaired ? <MiniTag tone="success">已修复</MiniTag> : null}
            {item.repairAttempted && !item.repaired ? <MiniTag tone="warning">已重试</MiniTag> : null}
            {item.success === false || item.relevant === false ? <MiniTag tone="warning">需要补来源</MiniTag> : null}
            {item.matchedTerms.slice(0, 3).map((term) => (
              <MiniTag key={term}>{term}</MiniTag>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function SourceCard({ source, index }: { source: RagSource; index: number }) {
  return (
    <article className="dt-dynamic-result rounded-lg border border-line bg-white px-3 py-2">
      <div className="flex items-start gap-2">
        <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-md border border-line bg-canvas text-xs font-semibold text-charcoal">
          {index}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="min-w-0 truncate text-xs font-semibold text-ink">{source.title}</p>
            {source.page ? <MiniTag>第 {source.page} 页</MiniTag> : null}
            {source.score ? <MiniTag>相关度 {source.score}</MiniTag> : null}
          </div>
          {source.evidenceReason ? <p className="mt-1 text-xs leading-5 text-brand-purple">{source.evidenceReason}</p> : null}
          {source.content ? <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-600">{source.content}</p> : null}
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {source.source ? <MiniTag>{basename(source.source)}</MiniTag> : null}
            {source.subquery ? <MiniTag tone="brand">来自视角 {source.subqueryIndex || ""}</MiniTag> : null}
            {source.matchedKeywords.slice(0, 4).map((keyword) => (
              <MiniTag key={keyword}>{keyword}</MiniTag>
            ))}
          </div>
        </div>
      </div>
    </article>
  );
}

function StatusIcon({ status }: { status: "ok" | "weak" | "failed" }) {
  if (status === "failed") return <RotateCcw size={13} className="mt-1 shrink-0 text-amber-600" />;
  if (status === "weak") return <Wrench size={13} className="mt-1 shrink-0 text-amber-600" />;
  return <CheckCircle2 size={13} className="mt-1 shrink-0 text-emerald-600" />;
}

function MetaPill({ icon, label }: { icon: ReactNode; label: string }) {
  return (
    <span className="inline-flex min-h-7 items-center gap-1 rounded-md border border-line bg-white px-2">
      {icon}
      {label}
    </span>
  );
}

function MiniTag({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "brand" | "warning" | "success";
}) {
  const toneClass =
    tone === "brand"
      ? "border-brand-purple-300 bg-tint-lavender text-brand-purple"
      : tone === "warning"
        ? "border-amber-200 bg-amber-50 text-amber-700"
        : tone === "success"
          ? "border-emerald-200 bg-emerald-50 text-emerald-700"
          : "border-line bg-canvas text-steel";
  return <span className={`rounded-md border px-1.5 py-0.5 text-[11px] leading-4 ${toneClass}`}>{children}</span>;
}

function waterfallCardTone(tone: "neutral" | "brand" | "warning" | "success") {
  if (tone === "brand") return "border-brand-purple-300 bg-tint-lavender";
  if (tone === "warning") return "border-amber-200 bg-amber-50";
  if (tone === "success") return "border-emerald-200 bg-emerald-50";
  return "border-line bg-canvas";
}

function basename(path: string) {
  const normalized = path.replace(/\\/g, "/");
  return normalized.split("/").filter(Boolean).pop() || path;
}

function formatPercent(value: number) {
  const normalized = value > 1 ? value : value * 100;
  return `${Math.round(normalized)}%`;
}

function formatCoverageLabel(evidence: RagEvidence) {
  if (typeof evidence.relevantCoverageRatio === "number") return `相关 ${formatPercent(evidence.relevantCoverageRatio)}`;
  if (typeof evidence.coverageRatio === "number") return `覆盖 ${formatPercent(evidence.coverageRatio)}`;
  if (evidence.subqueries.length) {
    const covered = evidence.subqueries.filter((item) => (item.sourceCount ?? 0) > 0).length;
    return `${covered}/${evidence.subqueries.length} 路`;
  }
  return evidence.sourceCount ? "已找到" : "未找到";
}

function formatRetrievalMode(value: string) {
  const labels: Record<string, string> = {
    dense: "语义查找",
    hybrid: "混合查找",
    naive: "轻量查找",
    sparse: "关键词查找",
  };
  return labels[value] || value;
}

function formatRetrievalProfile(value: string) {
  const labels: Record<string, string> = {
    auto: "自动匹配",
    broad: "综合问题",
    concept: "概念解释",
    exact: "精确事实",
    formula: "公式推导",
  };
  return labels[value] || value;
}

function formatQualityReason(reason: string) {
  const labels: Record<string, string> = {
    all_subqueries_failed: "视角无结果",
    low_context_chars: "回答材料偏少",
    low_relevance_coverage: "相关来源不足",
    low_score: "分数偏低",
    low_source_count: "来源偏少",
    low_subquery_coverage: "视角覆盖不足",
    no_sources: "无来源",
  };
  return labels[reason] || reason;
}

function formatPlanReason(reason: string) {
  const labels: Record<string, string> = {
    auto_complex_query: "问题需要拆成多个查找视角。",
    forced_by_caller: "系统选择了拆分查找。",
    query_too_broad: "问题范围较宽，需要多路补来源。",
    multi_intent: "问题包含多个意图。",
    "The question has multiple learning intents.": "问题包含多个学习意图。",
    "This request explicitly asked for deeper retrieval.": "系统选择了更深入的资料查找。",
    "The question contains multiple questions.": "问题里包含多个子问题。",
    "The question is long enough to benefit from focused retrieval.": "问题较长，适合拆成多个查找视角。",
    "The question is structured as a list of sub-tasks.": "问题以多个子任务的形式组织。",
    "The question combines several requirements.": "问题组合了多个要求。",
    "The planner used a rule-based split.": "系统按规则生成多个查找视角。",
    "Multi-step retrieval was selected for this request.": "系统选择了多路查找。",
  };
  return labels[reason] || reason;
}

function formatExplanationSummary(decision: string, summary: string) {
  if (decision === "single_search_fallback") {
    return "多路查找的部分来源偏弱，系统已回到轻量查找，优先保证回答仍有资料支撑。";
  }
  if (decision === "subquery_repair") {
    return "系统补强了来源薄弱的查找视角，并保留多路查找得到的来源。";
  }
  if (decision === "weak_multi_query") {
    return "系统完成了问题拆分，但来源检查提示部分来源仍偏弱。";
  }
  if (summary.includes("split the question")) {
    return "系统把问题拆成多个子问题，并找到了足够的资料来源。";
  }
  const labels: Record<string, string> = {
    "Multi-step retrieval was weak, so the answer used safer single-search evidence.":
      "多路查找的来源偏弱，系统已改用更稳的轻量查找来源。",
    "Weak retrieval branches were repaired before answering.":
      "系统先补强了来源偏弱的查找视角，再汇总回答来源。",
    "Evidence was found, but some quality checks need review.":
      "系统找到了资料来源，但仍有部分来源检查需要留意。",
    "Multi-step retrieval found enough evidence.":
      "系统通过多路查找找到了足够的资料来源。",
    "Retrieval evidence was checked before answering.":
      "系统已在回答前检查资料来源。",
  };
  if (labels[summary]) return labels[summary];
  return summary;
}

function formatRecommendation(value: string) {
  const labels: Record<string, string> = {
    "Some branches returned weakly related chunks; retry the original query with broader retrieval.":
      "部分查找视角的来源相关性偏弱，系统已尝试使用更宽的查找路径补来源。",
    "No evidence was found. Check indexing coverage or widen candidate_top_k.":
      "没有找到来源，请检查资料覆盖，或扩大候选来源数量。",
    "Relevant coverage is low; repair weak branches or retry with broader retrieval.":
      "相关来源不足，建议补强薄弱视角或使用更宽的查找策略。",
    "Review the fallback sources before relying on the answer.":
      "改用轻量查找后，建议先核对来源片段再使用答案。",
    "Review the repaired branches and source snippets.":
      "建议查看已补强的查找视角和对应来源片段。",
    "Open the knowledge base preflight and check whether the documents were indexed.":
      "建议打开资料库预检，确认文档已经完成整理。",
    "Run a stronger evidence preset or rephrase the missing branch.":
      "建议把问题改写得更具体，或补充缺失资料后再问。",
    "Treat the answer as tentative and inspect the evidence list.":
      "这次回答应视为暂定结论，请先检查来源列表。",
    "Open the cited sources to verify the important claims.":
      "可以展开引用来源，核对关键结论是否来自可信资料。",
  };
  return labels[value] || value;
}

function formatStepAction(action: string) {
  const labels: Record<string, string> = {
    accepted_repair: "采纳修复",
    repair_rejected: "修复未采纳",
    retry_or_fallback: "需重试",
    needs_more_evidence: "需补来源",
    use_evidence: "使用来源",
  };
  return labels[action] || action;
}

function formatQualityCheckCode(code: string) {
  const labels: Record<string, string> = {
    source_count: "来源数量",
    subquery_coverage: "拆分覆盖",
    relevance_coverage: "相关来源",
    context_chars: "回答材料长度",
    score: "最高相关度",
  };
  return labels[code] || code;
}

function formatQualityCheckValue(value: number | string | undefined) {
  if (value === null || typeof value === "undefined" || value === "") return "-";
  if (typeof value === "number" && value >= 0 && value <= 1) return formatPercent(value);
  return String(value);
}
