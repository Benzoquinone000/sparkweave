import { CheckCircle2, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FieldShell, TextArea } from "@/components/ui/Field";
import type { GuideV2LearningFeedback, GuideV2Task } from "@/lib/types";
import { DemoEvidenceShortcut } from "./GuideDemoCards";
import { LearningImpactSummary } from "./GuideLearningLoopSummary";
import { taskScoreOptions } from "./guideFormOptions";

export function GuideTaskCompletionPanel({
  currentTask,
  currentDemoStep,
  highlightedSectionId,
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
    <>
      <div
        id="guide-complete-task-section"
        className={`grid gap-4 transition-all duration-500 lg:grid-cols-[minmax(0,1fr)_280px] ${
          highlightedSectionId === "guide-complete-task-section" ? "rounded-lg ring-2 ring-brand-purple-300 ring-offset-2 ring-offset-canvas" : ""
        }`}
      >
        <div className="rounded-lg border border-line bg-canvas p-4">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-ink">完成标准</h3>
            <Badge tone="neutral">{successCriteria.length} 条</Badge>
          </div>
          <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-600">
            {successCriteria.slice(0, 3).map((item) => (
              <li key={item} className="flex gap-2">
                <CheckCircle2 size={16} className="mt-1 shrink-0 text-brand-purple" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-lg border border-line bg-white p-4">
          <DemoEvidenceShortcut
            step={currentDemoStep}
            onApply={(nextScore, nextReflection) => {
              onScoreChange(nextScore);
              onReflectionChange(nextReflection);
            }}
          />
          <FieldShell label="你现在感觉怎么样">
            <div className="grid gap-2">
              {taskScoreOptions.map((option) => {
                const active = score === option.value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    className={`min-h-12 rounded-md border px-3 text-left transition ${
                      active
                        ? "border-ink bg-ink text-white shadow-sm"
                        : "border-line bg-white text-slate-700 hover:border-brand-purple-300 hover:bg-tint-lavender"
                    }`}
                    onClick={() => onScoreChange(option.value)}
                  >
                    <span className="block text-sm font-semibold">{option.label}</span>
                    <span className="mt-0.5 block text-xs text-slate-500">{option.helper}</span>
                  </button>
                );
              })}
            </div>
          </FieldShell>
          <FieldShell label="一句话反思">
            <TextArea
              value={reflection}
              onChange={(event) => onReflectionChange(event.target.value)}
              className="min-h-28"
              placeholder="我已经理解了……还不确定的是……"
            />
          </FieldShell>
          <Button
            tone="primary"
            className="mt-3 w-full"
            data-testid="guide-submit-task-feedback"
            onClick={onCompleteTask}
            disabled={busy || !activeSessionId}
          >
            {completing ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
            完成并获得反馈
          </Button>
        </div>
      </div>
      {learningFeedback ? <LearningImpactSummary feedback={learningFeedback} /> : null}
    </>
  );
}
