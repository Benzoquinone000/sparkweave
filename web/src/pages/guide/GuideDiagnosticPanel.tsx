import { Brain, CheckCircle2, Loader2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { diagnosticStatusLabel, effectStatusTone } from "@/lib/guideDisplay";
import type {
  GuideV2Diagnostic,
  GuideV2DiagnosticAnswer,
  GuideV2DiagnosticValue,
} from "@/lib/types";

export function GuideDiagnosticPanel({
  diagnostic,
  loading,
  submitting,
  disabled,
  onSubmit,
}: {
  diagnostic: GuideV2Diagnostic | null;
  loading: boolean;
  submitting: boolean;
  disabled: boolean;
  onSubmit: (answers: GuideV2DiagnosticAnswer[]) => void;
}) {
  const [answers, setAnswers] = useState<Record<string, GuideV2DiagnosticValue>>({});
  const questions = diagnostic?.questions ?? [];
  const requiredAnswered = questions
    .filter((question) => question.type !== "multi_select")
    .every((question) => answers[question.question_id] !== undefined && String(answers[question.question_id]).length > 0);
  const answerCount = questions.filter((question) => {
    const value = answers[question.question_id];
    return Array.isArray(value) ? value.length > 0 : value !== undefined && String(value).length > 0;
  }).length;

  const setAnswer = (questionId: string, value: GuideV2DiagnosticValue) => {
    setAnswers((current) => ({ ...current, [questionId]: value }));
  };

  const toggleMulti = (questionId: string, value: string) => {
    setAnswers((current) => {
      const existing = Array.isArray(current[questionId]) ? current[questionId] as string[] : [];
      return {
        ...current,
        [questionId]: existing.includes(value) ? existing.filter((item) => item !== value) : [...existing, value],
      };
    });
  };

  const submit = () => {
    const payload = questions
      .map((question) => ({
        question_id: question.question_id,
        value: answers[question.question_id],
      }))
      .filter((item): item is GuideV2DiagnosticAnswer => item.value !== undefined);
    if (!payload.length || !requiredAnswered || submitting || disabled) return;
    onSubmit(payload);
  };

  return (
    <section className="rounded-lg border border-line bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="grid size-10 place-items-center rounded-lg border border-red-100 bg-red-50 text-brand-red">
            <Brain size={20} />
          </div>
          <div>
            <h2 className="text-base font-semibold text-ink">开始前的小校准</h2>
            <p className="mt-1 text-sm leading-6 text-slate-500">
              {diagnostic?.summary || "开始前先用几个小问题确认基础、偏好和当前卡点，后面的安排会更贴身。"}
            </p>
          </div>
        </div>
        {loading ? (
          <Loader2 size={16} className="animate-spin text-brand-purple" />
        ) : (
          <Badge tone={diagnostic?.status === "completed" ? "success" : "warning"}>
            {diagnosticStatusLabel(diagnostic?.status || "pending")}
          </Badge>
        )}
      </div>

      {diagnostic?.last_result?.recommendations?.length ? (
        <div className="mt-4 rounded-lg border border-line bg-canvas p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-semibold text-ink">上一次的小结</p>
            {diagnostic.last_result.readiness_score !== undefined ? (
              <Badge tone={effectStatusTone(Number(diagnostic.last_result.readiness_score) * 100)}>
                {Math.round(Number(diagnostic.last_result.readiness_score) * 100)}%
              </Badge>
            ) : null}
          </div>
          {diagnostic.last_result.bottleneck_label ? (
            <p className="mt-2 text-xs leading-5 text-brand-purple">
              当前卡点：{diagnostic.last_result.bottleneck_label}
            </p>
          ) : null}
          <div className="mt-2 space-y-1">
            {diagnostic.last_result.recommendations.slice(0, 3).map((item) => (
              <p key={item} className="text-xs leading-5 text-slate-600">• {item}</p>
            ))}
          </div>
          {diagnostic.last_result.learning_strategy?.length ? (
            <div className="mt-3 grid gap-2 sm:grid-cols-3">
              {diagnostic.last_result.learning_strategy.slice(0, 3).map((item) => (
                <div key={`${item.phase}-${item.action}`} className="rounded-lg border border-line bg-white p-3">
                  <Badge tone="neutral">{item.phase || "策略"}</Badge>
                  <p className="mt-2 line-clamp-3 text-xs font-medium leading-5 text-ink">{item.action}</p>
                  {item.success_check ? (
                    <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-500">{item.success_check}</p>
                  ) : null}
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="mt-4 space-y-3">
        {questions.slice(0, 7).map((question) => (
          <div key={question.question_id} className="rounded-lg border border-line bg-canvas p-3">
            <p className="text-sm font-medium leading-6 text-ink">{question.prompt}</p>
            {question.type === "scale" ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {Array.from({ length: Number(question.max ?? 5) - Number(question.min ?? 1) + 1 }, (_item, index) => Number(question.min ?? 1) + index).map((value) => (
                  <button
                    key={value}
                    type="button"
                    disabled={disabled || submitting}
                    onClick={() => setAnswer(question.question_id, value)}
                    className={`min-h-9 min-w-9 rounded-lg border px-3 text-sm font-semibold transition disabled:cursor-not-allowed ${
                      answers[question.question_id] === value ? "border-ink bg-ink text-white" : "border-line bg-white text-slate-600 hover:border-brand-purple-300 hover:bg-tint-lavender"
                    }`}
                    title={question.labels?.[String(value)]}
                  >
                    {value}
                  </button>
                ))}
              </div>
            ) : question.type === "multi_select" ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {(question.options ?? []).map((option) => {
                  const current = answers[question.question_id];
                  const selected = Array.isArray(current) && current.includes(option.value);
                  return (
                    <button
                      key={option.value}
                      type="button"
                      disabled={disabled || submitting}
                      onClick={() => toggleMulti(question.question_id, option.value)}
                      className={`rounded-lg border px-3 py-2 text-sm transition disabled:cursor-not-allowed ${
                        selected ? "border-ink bg-ink text-white" : "border-line bg-white text-slate-600 hover:border-brand-purple-300 hover:bg-tint-lavender"
                      }`}
                    >
                      {option.label}
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="mt-3 grid gap-2 sm:grid-cols-3">
                {(question.options ?? []).map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    disabled={disabled || submitting}
                    onClick={() => setAnswer(question.question_id, option.value)}
                    className={`rounded-lg border px-3 py-2 text-left text-sm transition disabled:cursor-not-allowed ${
                      answers[question.question_id] === option.value ? "border-ink bg-ink text-white" : "border-line bg-white text-slate-600 hover:border-brand-purple-300 hover:bg-tint-lavender"
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-slate-500">已回答 {answerCount}/{questions.length} 项，多选题可留空。</p>
        <Button tone="primary" disabled={!questions.length || !requiredAnswered || disabled || submitting} onClick={submit}>
          {submitting ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
          提交前测并调整路线
        </Button>
      </div>
    </section>
  );
}
