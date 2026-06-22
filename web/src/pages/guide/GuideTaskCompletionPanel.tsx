import { CheckCircle2, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FieldShell, TextArea } from "@/components/ui/Field";
import type { GuideV2LearningFeedback, GuideV2Task } from "@/lib/types";
import { taskScoreOptions } from "./guideFormOptions";

export function GuideTaskCompletionPanel({
  currentTask,
  score,
  reflection,
  learningFeedback,
  busy,
  activeSessionId,
  completing,
  onScoreChange,
  onReflectionChange,
  onCompleteTask,
}: {
  currentTask: GuideV2Task;
  currentDemoStep: Record<string, unknown> | null;
  highlightedSectionId: string | null;
  score: string;
  reflection: string;
  learningFeedback: GuideV2LearningFeedback | null;
  busy: boolean;
  activeSessionId: string | null;
  completing: boolean;
  onScoreChange: (value: string) => void;
  onReflectionChange: (value: string) => void;
  onCompleteTask: () => void;
}) {
  const successCriteria = currentTask.success_criteria?.length ? currentTask.success_criteria : ["完成任务并写下一句话总结"];

  return (
    <div id="guide-complete-task-section" className="flex h-full min-h-0 flex-col gap-3">
      <section className="shrink-0 rounded-lg border border-line bg-canvas p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="brand">当前任务</Badge>
          <Badge tone="neutral">{successCriteria.length} 条标准</Badge>
        </div>
        <h3 className="mt-3 line-clamp-2 text-base font-semibold text-ink">{currentTask.title}</h3>
        <ul className="mt-2 space-y-1 text-sm leading-6 text-slate-600">
          {successCriteria.slice(0, 2).map((item) => (
            <li key={item} className="flex gap-2">
              <CheckCircle2 size={15} className="mt-1 shrink-0 text-brand-purple" />
              <span className="line-clamp-1">{item}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="min-h-0 flex-1 rounded-lg border border-line bg-white p-4">
        <FieldShell label="你现在感觉怎么样？">
          <div className="grid gap-2 sm:grid-cols-3">
            {taskScoreOptions.slice(0, 3).map((option) => {
              const active = score === option.value;
              return (
                <button
                  key={option.value}
                  type="button"
                  className={`min-h-16 rounded-md border px-3 text-left transition ${
                    active
                      ? "border-ink bg-ink text-white shadow-sm"
                      : "border-line bg-white text-slate-700 hover:border-brand-purple-300 hover:bg-tint-lavender"
                  }`}
                  onClick={() => onScoreChange(option.value)}
                >
                  <span className="block text-sm font-semibold">{option.label}</span>
                  <span className={`mt-1 line-clamp-1 block text-xs ${active ? "text-white/75" : "text-slate-500"}`}>{option.helper}</span>
                </button>
              );
            })}
          </div>
        </FieldShell>

        <div className="mt-4">
          <FieldShell label="一句话反思">
            <TextArea
              value={reflection}
              onChange={(event) => onReflectionChange(event.target.value)}
              className="min-h-24"
              placeholder="我已经理解了……还不确定的是……"
            />
          </FieldShell>
        </div>

        {learningFeedback ? (
          <p className="mt-3 line-clamp-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs leading-5 text-emerald-800">
            {learningFeedback.summary || learningFeedback.title || "学习记录已保存。"}
          </p>
        ) : null}
      </section>

      <Button
        tone="primary"
        className="min-h-12 w-full shrink-0 text-base"
        data-testid="guide-submit-task-feedback"
        onClick={onCompleteTask}
        disabled={busy || !activeSessionId || completing}
      >
        {completing ? <Loader2 size={18} className="animate-spin" /> : <CheckCircle2 size={18} />}
        完成并获得反馈
      </Button>
    </div>
  );
}
