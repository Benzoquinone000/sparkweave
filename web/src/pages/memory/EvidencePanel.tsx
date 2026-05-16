import { motion } from "framer-motion";
import { Database, Loader2 } from "lucide-react";
import type { ReactNode } from "react";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { useLearnerProfileEvidencePreview } from "@/hooks/useApiQueries";
import type { LearnerEvidencePreview, LearnerProfileSnapshot } from "@/lib/types";
import { formatDate, formatPercent } from "./memoryDisplayUtils";

type EvidenceBrief = {
  title: string;
  summary: string;
  stats: Array<{ label: string; value: string }>;
  cues: string[];
};

export function EvidencePanel({ profile }: { profile?: LearnerProfileSnapshot }) {
  const [source, setSource] = useState<string | null>(null);
  const evidence = useLearnerProfileEvidencePreview(source, 40);
  const sources = profile?.sources ?? [];
  const items = evidence.data?.items ?? profile?.evidence_preview ?? [];
  const brief = buildEvidenceBrief(items, profile);

  return (
    <motion.section
      className="space-y-3 rounded-lg border border-line bg-white p-4"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      transition={{ duration: 0.22 }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-ink">画像证据</h2>
          <p className="mt-1 text-sm text-slate-500">每条画像判断都应该能回到真实学习记录。</p>
        </div>
        {evidence.isFetching ? <Loader2 size={18} className="animate-spin text-brand-purple" /> : null}
      </div>

      {brief ? <EvidenceBriefCard brief={brief} /> : null}

      <div className="flex flex-wrap gap-2">
        <FilterButton active={!source} onClick={() => setSource(null)}>
          全部
        </FilterButton>
        {sources.map((item) => (
          <FilterButton key={item.source_id} active={source === item.source_id} onClick={() => setSource(item.source_id)}>
            {evidenceSourceLabel(item.label || item.source_id)}
          </FilterButton>
        ))}
      </div>

      {items.length ? (
        <div className="grid gap-2">
          {items.map((item) => (
            <EvidenceItem key={item.evidence_id} item={item} />
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<Database size={24} />}
          title="还没有画像证据"
          description="完成导学任务、提交练习或保存笔记后，这里会展示画像形成的依据。"
        />
      )}
    </motion.section>
  );
}

function EvidenceBriefCard({ brief }: { brief: EvidenceBrief }) {
  return (
    <div className="rounded-lg border border-brand-purple-300 bg-tint-lavender p-4" data-testid="learner-evidence-brief">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Badge tone="brand">证据结论</Badge>
          <h3 className="mt-2 text-base font-semibold text-ink">{brief.title}</h3>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-charcoal">{brief.summary}</p>
        </div>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-3">
        {brief.stats.map((item) => (
          <div key={`${item.label}-${item.value}`} className="rounded-md border border-brand-purple-300 bg-white/80 px-3 py-2">
            <p className="text-[11px] font-medium text-slate-500">{item.label}</p>
            <p className="mt-1 truncate text-sm font-semibold text-ink">{item.value}</p>
          </div>
        ))}
      </div>
      {brief.cues.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {brief.cues.map((cue) => (
            <span key={cue} className="rounded-md border border-brand-purple-300 bg-white/80 px-2 py-1 text-xs text-charcoal">
              {cue}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function buildEvidenceBrief(items: LearnerEvidencePreview[], profile?: LearnerProfileSnapshot): EvidenceBrief | null {
  const total = Number(profile?.data_quality.evidence_count ?? items.length);
  if (!items.length && !total) return null;

  const latest = items[0];
  const verbs = countTop(items.map((item) => evidenceVerbLabel(metadataText(item.metadata, "verb"))).filter(Boolean));
  const resourceTypes = countTop(items.map((item) => resourceTypeLabel(metadataText(item.metadata, "resource_type"))).filter(Boolean));
  const sourceLabels = countTop(items.map((item) => evidenceSourceLabel(item.source_label)).filter(Boolean));
  const scores = items
    .map((item) => (typeof item.score === "number" && Number.isFinite(item.score) ? item.score : null))
    .filter((value): value is number => value !== null);
  const averageScore = scores.length ? scores.reduce((sum, value) => sum + value, 0) / scores.length : null;
  const latestVerb = latest ? evidenceVerbLabel(metadataText(latest.metadata, "verb")) : "";
  const latestResource = latest ? resourceTypeLabel(metadataText(latest.metadata, "resource_type")) : "";
  const latestSource = latest ? evidenceSourceLabel(latest.source_label) : "";

  let title = "证据正在帮系统收敛判断";
  if (latestVerb === "看过" && latestResource) title = `最近在用${latestResource}补理解`;
  else if (latestVerb === "答题") title = "最近留下了练习证据";
  else if (latestVerb === "完成") title = "最近完成了一步导学任务";
  else if (latestVerb === "确认画像" || latestVerb === "修正画像" || latestVerb === "否定画像") title = "最近主动校准了画像";
  else if (latestSource) title = `最近证据来自${latestSource}`;

  const summaryParts = [
    total ? `当前画像累计参考 ${total} 条学习证据。` : "",
    latest?.summary || latest?.title ? `最近一条是“${latest.summary || latest.title}”。` : "",
    averageScore !== null ? `最近可评分证据均值约 ${Math.round(averageScore * 100)}%。` : "",
  ].filter(Boolean);
  const summary = summaryParts.length
    ? summaryParts.join("")
    : "系统会优先看你真实做过、看过、答过和校准过的记录，而不是只凭一次对话下结论。";

  const stats = [
    { label: "累计证据", value: total ? `${total} 条` : `${items.length} 条` },
    { label: "当前筛选", value: items.length ? `${items.length} 条` : "暂无" },
    { label: "最新记录", value: latest?.created_at ? formatDate(latest.created_at) : "暂无" },
  ];
  if (averageScore !== null) stats[1] = { label: "最近得分", value: formatPercent(averageScore) };

  const cues = [
    ...verbs.slice(0, 2).map((item) => `行为：${item.label} ${item.count} 次`),
    ...resourceTypes.slice(0, 2).map((item) => `资源：${item.label}`),
    ...sourceLabels.slice(0, 2).map((item) => `来源：${item.label}`),
  ].slice(0, 5);

  return { title, summary, stats, cues };
}

function countTop(values: string[]) {
  const counts = new Map<string, number>();
  values.forEach((value) => counts.set(value, (counts.get(value) ?? 0) + 1));
  return [...counts.entries()]
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}

function FilterButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-md border px-3 py-2 text-sm transition ${
        active ? "border-brand-purple-300 bg-tint-lavender text-brand-purple" : "border-line bg-canvas text-slate-600 hover:border-brand-purple-300"
      }`}
    >
      {children}
    </button>
  );
}

function metadataText(metadata: Record<string, unknown> | undefined, key: string) {
  const value = metadata?.[key];
  return typeof value === "string" ? value : "";
}

function metadataTextList(metadata: Record<string, unknown> | undefined, key: string) {
  const value = metadata?.[key];
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item || "").trim()).filter(Boolean).slice(0, 3);
}

function evidenceVerbLabel(value: string) {
  const map: Record<string, string> = {
    requested: "请求",
    viewed: "看过",
    saved: "保存",
    generated: "生成",
    answered: "答题",
    completed: "完成",
    planned: "规划",
    confirmed_profile: "确认画像",
    corrected_profile: "修正画像",
    rejected_profile: "否定画像",
  };
  return map[value] || value;
}

function evidenceSourceLabel(value: string) {
  const map: Record<string, string> = {
    chat: "学习对话",
    evidence: "学习记录",
    guide: "导学任务",
    guide_v2: "导学任务",
    guide_resource: "学习资源",
    guide_quiz: "练习反馈",
    notebook: "笔记本",
    question_notebook: "题库",
    profile_calibration: "画像校准",
    external_video_search: "公开视频智能体",
    math_animator: "短视频智能体",
    visualize: "图解智能体",
    deep_question: "出题智能体",
    deep_research: "研究智能体",
    deep_solve: "解题智能体",
  };
  return map[value] || value || "学习记录";
}

function resourceTypeLabel(value: string) {
  const map: Record<string, string> = {
    external_video: "公开视频",
    video: "视频",
    visual: "图解",
    quiz: "练习",
    research: "研究",
    chat: "对话",
    question: "题目",
    solve: "解题",
  };
  return map[value] || value;
}

function EvidenceItem({ item }: { item: LearnerEvidencePreview }) {
  const verb = evidenceVerbLabel(metadataText(item.metadata, "verb"));
  const resourceType = resourceTypeLabel(metadataText(item.metadata, "resource_type"));
  const sourceLabel = evidenceSourceLabel(item.source_label);
  const watchPlan = metadataTextList(item.metadata, "watch_plan");
  const reflectionPrompt = metadataText(item.metadata, "reflection_prompt");
  return (
    <article className="rounded-lg border border-line bg-canvas p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-xs font-medium text-brand-purple">{sourceLabel}</p>
          <h3 className="mt-1 font-semibold text-ink">{item.title}</h3>
        </div>
        <span className="text-xs text-slate-500">{formatDate(item.created_at)}</span>
      </div>
      {verb || resourceType ? (
        <div className="mt-2 flex flex-wrap gap-2">
          {verb ? <Badge tone="neutral">{verb}</Badge> : null}
          {resourceType ? <Badge tone={resourceType === "公开视频" || resourceType === "视频" ? "brand" : "neutral"}>{resourceType}</Badge> : null}
        </div>
      ) : null}
      {item.summary ? <p className="mt-2 text-sm leading-6 text-slate-600">{item.summary}</p> : null}
      {watchPlan.length ? (
        <div className="mt-3 rounded-md border border-brand-purple-300 bg-white px-3 py-2">
          <p className="text-xs font-medium text-brand-purple">观看计划</p>
          <ol className="mt-1 grid gap-1 text-xs leading-5 text-slate-600">
            {watchPlan.map((step, index) => (
              <li key={`${step}-${index}`}>
                {index + 1}. {step}
              </li>
            ))}
          </ol>
        </div>
      ) : null}
      {reflectionPrompt ? (
        <p className="mt-2 rounded-md border border-line bg-white px-3 py-2 text-xs leading-5 text-slate-600">反思问题：{reflectionPrompt}</p>
      ) : null}
      {item.score !== null && item.score !== undefined ? <p className="mt-2 text-xs text-slate-500">分数：{formatPercent(item.score)}</p> : null}
    </article>
  );
}
