import { CalendarDays, Clock3, GraduationCap } from "lucide-react";
import { motion } from "framer-motion";

import { Badge } from "@/components/ui/Badge";
import { SelectInput } from "@/components/ui/Field";
import { guideDisplayText } from "@/lib/guideDisplay";
import type { GuideV2CourseTemplate, NotebookRecord } from "@/lib/types";
import { EvalMini } from "./GuideMetrics";

export function SourceActionNotice({ action }: { action: Record<string, unknown> | null }) {
  if (!action) return null;
  const title = readString(action, "title") || "学习建议";
  const sourceLabel = readString(action, "source_label");
  const suggestedPrompt = readString(action, "suggested_prompt");
  const kind = readString(action, "kind");
  const confidence = Number(action.confidence);
  const minutes = Number(action.estimated_minutes);
  const kindLabel =
    kind === "weak_point"
      ? "薄弱点接力"
      : kind.startsWith("learning_effect")
        ? "效果评估接力"
        : kind === "mastery" || kind === "mastery_check" || kind === "mastery_support"
          ? "掌握度接力"
          : "学习建议";
  return (
    <motion.div
      className="rounded-lg border border-line bg-tint-lavender px-4 py-3"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18 }}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="brand">已参考记录</Badge>
        <Badge tone="neutral">{kindLabel}</Badge>
        {Number.isFinite(minutes) && minutes > 0 ? <Badge tone="neutral">{Math.round(minutes)} 分钟</Badge> : null}
        {Number.isFinite(confidence) && confidence > 0 ? <Badge tone="neutral">把握 {Math.round(Math.min(confidence, 1) * 100)}%</Badge> : null}
      </div>
      <h3 className="mt-3 text-sm font-semibold text-ink">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-charcoal">
        {sourceLabel ? `这次先围绕「${sourceLabel}」安排学习。` : "这次会直接按学习建议安排学习。"}
        你可以直接创建路线，系统会先做前测，再给资源和练习。
      </p>
      {suggestedPrompt ? <p className="mt-2 rounded-md bg-white/75 px-3 py-2 text-sm leading-6 text-charcoal">{suggestedPrompt}</p> : null}
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs leading-5 text-steel">不准也没关系，学习记录页随时能改。</p>
        <a
          href="/memory"
          className="inline-flex min-h-9 items-center justify-center rounded-md border border-line bg-white px-3 text-xs font-medium text-ink transition hover:border-brand-purple hover:text-brand-purple"
        >
          回到记录页
        </a>
      </div>
    </motion.div>
  );
}

export function ReferencePicker({
  notebooks,
  notebookId,
  records,
  selectedRecordIds,
  loading,
  onNotebookChange,
  onToggleRecord,
}: {
  notebooks: Array<{ id: string; name?: string }>;
  notebookId: string;
  records: NotebookRecord[];
  selectedRecordIds: string[];
  loading: boolean;
  onNotebookChange: (value: string) => void;
  onToggleRecord: (record: NotebookRecord) => void;
}) {
  return (
    <div className="rounded-lg border border-line bg-canvas p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-medium text-ink">引用学习记录</p>
        <Badge tone={selectedRecordIds.length ? "brand" : "neutral"}>{selectedRecordIds.length} 条</Badge>
      </div>
      <SelectInput className="mt-3" value={notebookId} onChange={(event) => onNotebookChange(event.target.value)}>
        <option value="">不引用记录本</option>
        {notebooks.map((item) => (
          <option key={item.id} value={item.id}>
            {item.name || "未命名记录本"}
          </option>
        ))}
      </SelectInput>
      {notebookId ? (
        <div className="mt-3 space-y-2">
          {records.map((record) => {
            const recordId = record.record_id || record.id;
            const selected = selectedRecordIds.includes(recordId);
            return (
              <button
                key={recordId}
                type="button"
                onClick={() => onToggleRecord(record)}
                className={`w-full rounded-lg border p-3 text-left transition ${
                  selected ? "border-ink bg-ink text-white" : "border-line bg-white hover:border-brand-purple-300 hover:bg-tint-lavender"
                }`}
              >
                <p className="truncate text-sm font-semibold text-ink">{record.title || "学习记录"}</p>
                <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{record.summary || record.user_query || "学习记录"}</p>
              </button>
            );
          })}
          {loading ? <p className="text-xs text-slate-500">正在读取记录...</p> : null}
          {!loading && !records.length ? <p className="text-xs text-slate-500">这个记录本暂无可引用记录。</p> : null}
        </div>
      ) : null}
    </div>
  );
}

export function CourseTemplatePreview({
  template,
  loading,
}: {
  template: GuideV2CourseTemplate | null;
  loading: boolean;
}) {
  if (loading && !template) {
    return <div className="rounded-lg border border-line bg-canvas p-3 text-sm text-slate-500">正在读取课程模板...</div>;
  }
  if (!template) {
    return (
      <div className="rounded-lg border border-line bg-canvas p-3 text-sm leading-6 text-slate-500">
        选择内置课程会自动填入学习目标、时间预算和偏好；自定义目标适合临时补课或短期专项学习。
      </div>
    );
  }
  return (
    <motion.div
      className="rounded-lg border border-brand-purple-300 bg-tint-lavender p-3"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.16 }}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-ink">{template.course_name || template.title}</p>
          <p className="mt-1 text-xs leading-5 text-slate-600">{template.description}</p>
        </div>
        <Badge tone="brand">内置课程</Badge>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2">
        <EvalMini label="周期" value={Number(template.suggested_weeks ?? 0)} suffix="周" />
        <EvalMini label="学分" value={Number(template.credits ?? 0)} />
        <EvalMini label="课时" value={Number(template.estimated_minutes ?? 0)} suffix="m" />
      </div>
      {template.learning_outcomes?.length ? <p className="mt-3 line-clamp-2 text-xs leading-5 text-slate-600">{template.learning_outcomes[0]}</p> : null}
      {template.demo_seed?.scenario ? (
        <p className="mt-3 rounded-lg border border-brand-purple-300 bg-white/80 p-2 text-xs leading-5 text-charcoal">
          推荐演示：{template.demo_seed.scenario}
        </p>
      ) : null}
      {template.tags?.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {template.tags.slice(0, 4).map((tag) => (
            <Badge key={tag} tone="neutral">
              {tag}
            </Badge>
          ))}
        </div>
      ) : null}
    </motion.div>
  );
}

export function CourseTemplateQuickPick({
  templates,
  demoTemplateId,
  selectedTemplateId,
  busy,
  onPick,
}: {
  templates: GuideV2CourseTemplate[];
  demoTemplateId: string;
  selectedTemplateId: string;
  busy: boolean;
  onPick: (template: GuideV2CourseTemplate) => void;
}) {
  const visibleTemplates = templates
    .filter((template) => template.id !== demoTemplateId)
    .sort((left, right) => courseTemplateQuickPickPriority(left) - courseTemplateQuickPickPriority(right))
    .slice(0, 3);
  if (!visibleTemplates.length) {
    return null;
  }

  return (
    <div className="rounded-lg border border-line bg-canvas p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-ink">也可以直接选一门完整课程</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">适合录屏演示或从零开始，点一下就填好目标和时间。</p>
        </div>
        <Badge tone="neutral">{visibleTemplates.length} 门</Badge>
      </div>
      <div className="mt-3 grid gap-2 md:grid-cols-3">
        {visibleTemplates.map((template) => {
          const selected = template.id === selectedTemplateId;
          const competitionTemplate = template.id === "ai_learning_agents_systems";
          const title = guideDisplayText(template.course_name || template.title, "内置课程");
          const minutes = template.default_time_budget_minutes || template.estimated_minutes || 0;
          return (
            <button
              key={template.id}
              type="button"
              className={`rounded-lg border bg-white p-3 text-left transition ${
                selected
                  ? "border-brand-purple ring-2 ring-brand-purple-300"
                  : competitionTemplate
                    ? "border-brand-purple-300 hover:border-brand-purple hover:bg-tint-lavender"
                    : "border-line hover:border-brand-purple-300 hover:bg-tint-lavender"
              }`}
              data-testid={`guide-course-template-${template.id}`}
              disabled={busy}
              onClick={() => onPick(template)}
            >
              <div className="flex items-start justify-between gap-2">
                <GraduationCap size={16} className={selected ? "mt-0.5 shrink-0 text-brand-purple" : "mt-0.5 shrink-0 text-brand-blue"} />
                <Badge tone={selected || competitionTemplate ? "brand" : "neutral"}>{selected ? "已选择" : competitionTemplate ? "赛题主线" : "课程"}</Badge>
              </div>
              <p className="mt-3 line-clamp-2 min-h-10 text-sm font-semibold leading-5 text-ink">{title}</p>
              <p className="mt-2 line-clamp-2 min-h-10 text-xs leading-5 text-slate-500">
                {guideDisplayText(template.description, template.default_goal || "按完整课程路线开始学习。")}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {template.suggested_weeks ? (
                  <span className="inline-flex items-center gap-1 rounded-md border border-line px-2 py-1 text-xs text-slate-600">
                    <CalendarDays size={13} />
                    {template.suggested_weeks} 周
                  </span>
                ) : null}
                {minutes ? (
                  <span className="inline-flex items-center gap-1 rounded-md border border-line px-2 py-1 text-xs text-slate-600">
                    <Clock3 size={13} />
                    {Math.round(minutes)} 分钟
                  </span>
                ) : null}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function courseTemplateQuickPickPriority(template: GuideV2CourseTemplate): number {
  if (template.id === "ai_learning_agents_systems") return 0;
  if ((template.demo_seed?.task_chain ?? []).length > 0) return 1;
  return 2;
}

function readString(source: Record<string, unknown>, key: string) {
  const value = source[key];
  return typeof value === "string" ? value : value == null ? "" : String(value);
}
