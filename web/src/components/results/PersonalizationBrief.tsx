import { Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/Badge";

type Signal = {
  label: string;
  value: string;
};

export function PersonalizationBrief({
  hints,
  styleHint,
  className = "",
}: {
  hints?: Record<string, unknown> | null;
  styleHint?: string;
  className?: string;
}) {
  const insight = buildPersonalizationInsight(hints, styleHint);
  if (!insight) return null;

  return (
    <div
      className={`rounded-lg border border-teal-100 bg-teal-50 px-3 py-3 ${className}`}
      data-testid="personalization-brief"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="brand">按你的画像生成</Badge>
        {insight.signals.slice(0, 4).map((item) => (
          <Badge key={`${item.label}-${item.value}`} tone="neutral">
            {item.label}：{item.value}
          </Badge>
        ))}
      </div>
      <div className="mt-2 flex gap-2 text-sm leading-6 text-teal-950">
        <Sparkles size={16} className="mt-1 shrink-0 text-brand-teal" />
        <p>{insight.headline}</p>
      </div>
      {insight.suggestion ? <p className="mt-2 text-xs leading-5 text-teal-800">{insight.suggestion}</p> : null}
    </div>
  );
}

function buildPersonalizationInsight(hints?: Record<string, unknown> | null, styleHint?: string) {
  const source = hints ?? {};
  const weakPoints = textArray(source.weak_points ?? source.mastery_needs_attention ?? source.mastery_gaps);
  const preferences = textArray(source.preferences);
  const goals = textArray(source.goals);
  const currentFocus = textValue(source.current_focus);
  const level = textValue(source.level);
  const timeBudget = textValue(source.time_budget_minutes);
  const nextAction = recordValue(source.next_action);
  const nextTitle = textValue(nextAction?.title);

  const signals: Signal[] = [];
  if (currentFocus) signals.push({ label: "当前重点", value: currentFocus });
  if (weakPoints.length) signals.push({ label: "优先照顾", value: weakPoints.slice(0, 2).join("、") });
  if (preferences.length) signals.push({ label: "偏好", value: preferences.slice(0, 2).join("、") });
  if (level) signals.push({ label: "水平", value: level });
  if (timeBudget) signals.push({ label: "时间", value: `${timeBudget.replace(/[^\d.]/g, "") || timeBudget} 分钟` });

  const styleOnly = Boolean(styleHint?.trim());
  if (!signals.length && !goals.length && !nextTitle && !styleOnly) return null;

  let headline = "这份资源不是随机生成的，系统已参考你的学习画像调整讲解顺序和呈现方式。";
  if (weakPoints.length) {
    headline = `这份资源会先照顾「${weakPoints.slice(0, 2).join("、")}」，帮助你把当前最容易卡住的地方补清楚。`;
  } else if (currentFocus) {
    headline = `这份资源围绕你当前的学习重点「${currentFocus}」生成，先服务当下任务。`;
  } else if (preferences.length) {
    headline = `系统参考了你的学习偏好「${preferences.slice(0, 2).join("、")}」，尽量用更顺手的方式呈现。`;
  } else if (goals.length) {
    headline = `系统参考了你的学习目标「${goals[0]}」，让资源更贴近后续路线。`;
  }

  const suggestion = nextTitle
    ? `看完后建议回到「${nextTitle}」继续推进，让结果回写画像。`
    : weakPoints.length
      ? "看完后最好立刻做一题或写一句反思，系统才能判断这个卡点是否真的缓解。"
      : "看完后回到当前任务提交反馈，后续推荐会更准。";

  return { headline, suggestion, signals };
}

function textArray(value: unknown) {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item).trim()).filter(Boolean);
}

function textValue(value: unknown) {
  if (typeof value === "string") return value.trim();
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return "";
}

function recordValue(value: unknown): Record<string, unknown> | null {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}
