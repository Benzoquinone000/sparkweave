import { Activity, CircleDot, Gauge } from "lucide-react";

import type { LearnerEvidencePreview, LearnerProfileSnapshot } from "@/lib/types";
import { formatPercent } from "./memoryDisplayUtils";

type Axis = {
  key: string;
  label: string;
  value: number;
  detail: string;
};

const SVG_SIZE = 240;
const SVG_CENTER = SVG_SIZE / 2;
const SVG_RADIUS = 78;

export function LearnerProfileVisualMap({ profile }: { profile: LearnerProfileSnapshot }) {
  const axes = buildProfileAxes(profile);
  const points = axes.map((axis, index) => polarPoint(index, axes.length, axis.value)).join(" ");
  const fullPoints = axes.map((_, index) => polarPoint(index, axes.length, 1)).join(" ");
  const evidenceFlow = (profile.evidence_preview ?? []).slice(0, 4);

  return (
    <section className="mt-5 border-t border-line-soft pt-5" data-testid="learner-profile-visual-map">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-ink">学习地图</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">把目标、卡点、偏好和学习记录整理成一张图。</p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-md border border-line bg-surface px-2.5 py-1 text-xs font-medium text-slate-600">
          <Gauge size={14} />
          {formatPercent(profile.confidence)}
        </span>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
        <div className="min-w-0" data-testid="learner-profile-decision-radar">
          <div className="mx-auto aspect-square w-full max-w-[260px]">
            <svg viewBox={`0 0 ${SVG_SIZE} ${SVG_SIZE}`} role="img" aria-label="学习建议雷达图" className="h-full w-full">
              {[0.33, 0.66, 1].map((ring) => (
                <polygon
                  key={ring}
                  points={axes.map((_, index) => polarPoint(index, axes.length, ring)).join(" ")}
                  fill="none"
                  stroke={ring === 1 ? "#cbd5e1" : "#e5e7eb"}
                  strokeWidth={ring === 1 ? 1.2 : 1}
                />
              ))}
              {axes.map((axis, index) => {
                const outer = polarPointTuple(index, axes.length, 1);
                const label = polarPointTuple(index, axes.length, 1.18);
                return (
                  <g key={axis.key}>
                    <line x1={SVG_CENTER} y1={SVG_CENTER} x2={outer[0]} y2={outer[1]} stroke="#e5e7eb" strokeWidth="1" />
                    <text
                      x={label[0]}
                      y={label[1]}
                      textAnchor={label[0] < SVG_CENTER - 8 ? "end" : label[0] > SVG_CENTER + 8 ? "start" : "middle"}
                      dominantBaseline="middle"
                      className="fill-slate-500 text-[11px] font-medium"
                    >
                      {axis.label}
                    </text>
                  </g>
                );
              })}
              <polygon points={fullPoints} fill="#f8fafc" opacity="0.8" />
              <polygon points={points} fill="#2563eb" opacity="0.16" stroke="#2563eb" strokeWidth="2" />
              {axes.map((axis, index) => {
                const [x, y] = polarPointTuple(index, axes.length, axis.value);
                return (
                  <circle key={`${axis.key}-dot`} cx={x} cy={y} r="4" fill={axisTone(axis.value)} stroke="#fff" strokeWidth="2" />
                );
              })}
              <circle cx={SVG_CENTER} cy={SVG_CENTER} r="22" fill="#ffffff" stroke="#e5e7eb" />
              <text x={SVG_CENTER} y={SVG_CENTER - 2} textAnchor="middle" className="fill-slate-950 text-[11px] font-semibold">
                建议
              </text>
              <text x={SVG_CENTER} y={SVG_CENTER + 12} textAnchor="middle" className="fill-slate-500 text-[10px]">
                记录
              </text>
            </svg>
          </div>
        </div>

        <div className="grid min-w-0 content-center gap-3">
          {axes.map((axis) => (
            <SignalBar key={axis.key} axis={axis} />
          ))}
        </div>
      </div>

      <div className="mt-4" data-testid="learner-profile-evidence-flow">
        <div className="mb-2 flex items-center justify-between gap-3">
          <span className="inline-flex items-center gap-2 text-sm font-semibold text-ink">
            <Activity size={16} className="text-brand-blue" />
            最近学习记录
          </span>
          <span className="text-xs text-slate-500">{profile.data_quality.source_count ?? 0} 个来源</span>
        </div>
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          {evidenceFlow.length ? (
            evidenceFlow.map((item) => <EvidencePulse key={item.evidence_id} item={item} />)
          ) : (
            <p className="dt-dynamic-empty rounded-lg border border-dashed border-line bg-surface px-3 py-3 text-sm text-slate-500">
              还没有足够学习记录，完成一次导学或练习后这里会开始成形。
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

function SignalBar({ axis }: { axis: Axis }) {
  const percent = Math.round(axis.value * 100);
  return (
    <div className="min-w-0">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-semibold text-ink">{axis.label}</span>
        <span className="text-xs font-medium text-slate-500">{percent}%</span>
      </div>
      <div className="mt-1 h-2 overflow-hidden rounded-lg bg-slate-100">
        <span className={`block h-full rounded-lg ${barTone(axis.value)}`} style={{ width: `${Math.max(8, percent)}%` }} />
      </div>
      <p className="mt-1 truncate text-xs text-slate-500">{axis.detail}</p>
    </div>
  );
}

function EvidencePulse({ item }: { item: LearnerEvidencePreview }) {
  const score = normalizeScore(item.score);
  return (
    <div className="dt-dynamic-result min-w-0 rounded-lg border border-line bg-surface px-3 py-2">
      <div className="flex items-center justify-between gap-2">
        <span className="inline-flex min-w-0 items-center gap-1.5 text-xs font-semibold text-slate-600">
          <CircleDot size={13} className="shrink-0 text-brand-orange" />
          <span className="truncate">{sourceLabel(item.source_label || item.source_id)}</span>
        </span>
        {score !== null ? <span className="text-xs font-medium text-slate-500">{Math.round(score * 100)}%</span> : null}
      </div>
      <p className="mt-1 line-clamp-2 text-sm font-medium leading-5 text-ink">{item.title || "学习记录"}</p>
      <p className="mt-1 truncate text-xs text-slate-500">{formatEvidenceDate(item.created_at)}</p>
    </div>
  );
}

function buildProfileAxes(profile: LearnerProfileSnapshot): Axis[] {
  const goals = profile.stable_profile.goals ?? [];
  const preferences = profile.stable_profile.preferences ?? [];
  const weakPoints = profile.learning_state.weak_points ?? [];
  const mastery = profile.learning_state.mastery ?? [];
  const evidenceCount = Number(profile.data_quality.evidence_count ?? 0);
  const sourceCount = Number(profile.data_quality.source_count ?? 0);
  const topWeak = weakPoints[0];
  const masteryScores = mastery
    .map((item) => normalizeScore(item.score))
    .filter((score): score is number => score !== null);
  const masteryAverage = masteryScores.length
    ? masteryScores.reduce((total, score) => total + score, 0) / masteryScores.length
    : 0.36;

  return [
    {
      key: "goal",
      label: "目标",
      value: axisScore(profile, "goal", Math.max(goals.length / 3, profile.overview.current_focus ? 0.72 : 0.24)),
      detail: goals[0] || profile.overview.current_focus || "等待明确目标",
    },
    {
      key: "weak",
      label: "卡点",
      value: axisScore(profile, "weakness", topWeak ? (topWeak.score ?? severityWeight(topWeak.severity) * 0.46 + (topWeak.confidence ?? 0.5) * 0.54) : 0.18),
      detail: topWeak?.label || "暂无稳定薄弱点",
    },
    {
      key: "preference",
      label: "偏好",
      value: axisScore(profile, "preference", Math.max(preferences.length / 4, preferences.length ? 0.46 : 0.18)),
      detail: preferences.slice(0, 2).map(preferenceLabel).join("、") || "继续观察资源偏好",
    },
    {
      key: "evidence",
      label: "记录",
      value: axisScore(profile, "evidence", Math.max(evidenceCount / 12, sourceCount / 5)),
      detail: `${evidenceCount} 条记录 · ${sourceCount} 个来源`,
    },
    {
      key: "mastery",
      label: "掌握",
      value: axisScore(profile, "mastery", masteryAverage),
      detail: mastery[0]?.title || "还在积累掌握度",
    },
  ];
}

function axisScore(profile: LearnerProfileSnapshot, key: string, fallback: number) {
  const score = profile.quantification?.axes?.[key]?.score;
  if (score === null || score === undefined) return clamp01(fallback);
  return normalizeScore(score) ?? clamp01(fallback);
}

function polarPoint(index: number, total: number, ratio: number) {
  const [x, y] = polarPointTuple(index, total, ratio);
  return `${x.toFixed(1)},${y.toFixed(1)}`;
}

function polarPointTuple(index: number, total: number, ratio: number): [number, number] {
  const angle = (-90 + (360 / total) * index) * (Math.PI / 180);
  const radius = SVG_RADIUS * ratio;
  return [SVG_CENTER + Math.cos(angle) * radius, SVG_CENTER + Math.sin(angle) * radius];
}

function clamp01(value: number) {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(1, value));
}

function normalizeScore(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return null;
  const numeric = Number(value);
  return clamp01(numeric > 1 ? numeric / 100 : numeric);
}

function severityWeight(value?: string) {
  const normalized = String(value || "").toLowerCase();
  if (normalized === "high") return 1;
  if (normalized === "medium") return 0.68;
  if (normalized === "low") return 0.42;
  return 0.56;
}

function axisTone(value: number) {
  if (value >= 0.72) return "#059669";
  if (value >= 0.45) return "#2563eb";
  return "#f97316";
}

function barTone(value: number) {
  if (value >= 0.72) return "bg-emerald-600";
  if (value >= 0.45) return "bg-brand-blue";
  return "bg-brand-orange";
}

function preferenceLabel(value: string) {
  const normalized = String(value || "").trim();
  const lowered = normalized.toLowerCase();
  if (lowered === "external_video" || lowered === "public_video") return "公开视频";
  if (lowered === "external_image" || lowered === "public_image") return "公开图片";
  if (lowered === "short_video" || lowered === "video") return "视频";
  if (lowered === "visual") return "图解";
  if (lowered === "practice") return "练习";
  if (lowered === "quiz") return "测验";
  return normalized;
}

function sourceLabel(value: string) {
  const normalized = String(value || "").trim();
  const labels: Record<string, string> = {
    chat: "对话",
    guide: "导学",
    guide_v2: "导学",
    question: "练习",
    question_notebook: "错题本",
    external_video_search: "公开视频",
    external_image_search: "公开图片",
    visualize: "图解",
    profile_calibration: "建议修正",
  };
  return labels[normalized] || normalized || "学习记录";
}

function formatEvidenceDate(value?: string | null) {
  if (!value) return "暂无时间";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString();
}
