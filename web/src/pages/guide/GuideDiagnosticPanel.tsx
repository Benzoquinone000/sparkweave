import { ArrowLeft, ArrowRight, Brain, CheckCircle2, Loader2 } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { diagnosticStatusLabel, effectStatusTone } from "@/lib/guideDisplay";
import type {
  GuideV2Diagnostic,
  GuideV2DiagnosticAnswer,
  GuideV2DiagnosticQuestion,
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
  const [requestedActiveIndex, setRequestedActiveIndex] = useState(0);
  const questions = diagnostic?.questions ?? [];
  const activeIndex = Math.min(requestedActiveIndex, Math.max(questions.length - 1, 0));
  const activeQuestion = questions[activeIndex];
  const requiredAnswered = questions
    .filter((question) => question.type !== "multi_select")
    .every((question) => isAnswered(answers[question.question_id]));
  const answerCount = questions.filter((question) => isAnswered(answers[question.question_id])).length;
  const currentAnswered = activeQuestion ? activeQuestion.type === "multi_select" || isAnswered(answers[activeQuestion.question_id]) : false;
  const isLast = activeIndex >= questions.length - 1;
  const progress = questions.length ? Math.round((answerCount / questions.length) * 100) : 0;

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

  const goNext = () => {
    if (!currentAnswered && activeQuestion?.type !== "multi_select") return;
    if (isLast) {
      submit();
      return;
    }
    setRequestedActiveIndex((index) => Math.min(questions.length - 1, index + 1));
  };

  const setAnswer = (questionId: string, value: GuideV2DiagnosticValue) => {
    setAnswers((current) => ({ ...current, [questionId]: value }));
  };

  const toggleMulti = (questionId: string, value: string) => {
    setAnswers((current) => {
      const existing = Array.isArray(current[questionId]) ? (current[questionId] as string[]) : [];
      return {
        ...current,
        [questionId]: existing.includes(value) ? existing.filter((item) => item !== value) : [...existing, value],
      };
    });
  };

  if (loading && !questions.length) {
    return (
      <section className="grid h-full place-items-center rounded-lg border border-line bg-white p-5">
        <div className="text-center">
          <Loader2 size={22} className="mx-auto animate-spin text-brand-purple" />
          <p className="mt-3 text-sm font-semibold text-ink">正在准备前测</p>
        </div>
      </section>
    );
  }

  if (!activeQuestion) {
    return (
      <section className="grid h-full place-items-center rounded-lg border border-line bg-white p-5 text-center">
        <div>
          <Brain size={24} className="mx-auto text-brand-purple" />
          <p className="mt-3 text-sm font-semibold text-ink">还没有前测题</p>
          <p className="mt-1 text-xs text-slate-500">稍后刷新，或返回补充目标。</p>
        </div>
      </section>
    );
  }

  return (
    <section className="flex h-full min-h-0 flex-col rounded-lg border border-line bg-white p-4">
      <div className="shrink-0">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex min-w-0 items-start gap-3">
            <div className="grid size-10 shrink-0 place-items-center rounded-lg border border-red-100 bg-red-50 text-brand-red">
              <Brain size={20} />
            </div>
            <div className="min-w-0">
              <h2 className="text-base font-semibold text-ink">开始前的小校准</h2>
              <p className="mt-1 line-clamp-2 text-sm leading-6 text-slate-500">
                {diagnostic?.summary || "用几个小问题确认基础、偏好和当前卡点。"}
              </p>
            </div>
          </div>
          <Badge tone={diagnostic?.status === "completed" ? "success" : "warning"}>
            {diagnosticStatusLabel(diagnostic?.status || "pending")}
          </Badge>
        </div>

        {diagnostic?.last_result ? (
          <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg border border-line bg-canvas px-3 py-2 text-xs text-slate-600">
            <span className="font-semibold text-ink">上次结果</span>
            {diagnostic.last_result.readiness_score !== undefined ? (
              <Badge tone={effectStatusTone(Number(diagnostic.last_result.readiness_score) * 100)}>
                {Math.round(Number(diagnostic.last_result.readiness_score) * 100)}%
              </Badge>
            ) : null}
            {diagnostic.last_result.bottleneck_label ? <span>卡点：{diagnostic.last_result.bottleneck_label}</span> : null}
          </div>
        ) : null}

        <div className="mt-3">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span>
              第 {activeIndex + 1} 题 / 共 {questions.length} 题
            </span>
            <span>已答 {answerCount} 题</span>
          </div>
          <div className="mt-2 h-1.5 overflow-hidden rounded-lg bg-slate-100">
            <div className="h-full rounded-lg bg-brand-purple transition-all" style={{ width: `${progress}%` }} />
          </div>
        </div>
      </div>

      <QuestionCard
        question={activeQuestion}
        value={answers[activeQuestion.question_id]}
        disabled={disabled || submitting}
        onSetAnswer={setAnswer}
        onToggleMulti={toggleMulti}
      />

      <div className="mt-3 flex shrink-0 items-center justify-between gap-2 border-t border-line pt-3">
        <Button tone="secondary" disabled={activeIndex <= 0 || submitting} onClick={() => setRequestedActiveIndex((index) => Math.max(0, index - 1))}>
          <ArrowLeft size={16} />
          上一题
        </Button>
        <Button
          tone="primary"
          disabled={disabled || submitting || (!currentAnswered && activeQuestion.type !== "multi_select") || (isLast && !requiredAnswered)}
          onClick={goNext}
        >
          {submitting ? <Loader2 size={16} className="animate-spin" /> : isLast ? <CheckCircle2 size={16} /> : <ArrowRight size={16} />}
          {isLast ? "提交前测" : "下一题"}
        </Button>
      </div>
    </section>
  );
}

function QuestionCard({
  question,
  value,
  disabled,
  onSetAnswer,
  onToggleMulti,
}: {
  question: GuideV2DiagnosticQuestion;
  value: GuideV2DiagnosticValue | undefined;
  disabled: boolean;
  onSetAnswer: (questionId: string, value: GuideV2DiagnosticValue) => void;
  onToggleMulti: (questionId: string, value: string) => void;
}) {
  const scaleValues = useMemo(() => {
    const min = Number(question.min ?? 1);
    const max = Number(question.max ?? 5);
    const start = Number.isFinite(min) ? min : 1;
    const end = Number.isFinite(max) && max >= start ? max : 5;
    return Array.from({ length: end - start + 1 }, (_item, index) => start + index);
  }, [question.max, question.min]);

  return (
    <div className="my-3 flex min-h-0 flex-1 flex-col justify-center rounded-lg border border-line bg-canvas p-4">
      <Badge tone="brand">{question.node_title || "当前问题"}</Badge>
      <h3 className="mt-3 text-lg font-semibold leading-7 text-ink">{question.prompt}</h3>

      {question.type === "scale" ? (
        <div className="mt-5 flex flex-wrap gap-2">
          {scaleValues.map((option) => (
            <button
              key={option}
              type="button"
              disabled={disabled}
              onClick={() => onSetAnswer(question.question_id, option)}
              className={`min-h-11 min-w-11 rounded-lg border px-3 text-sm font-semibold transition disabled:cursor-not-allowed ${
                value === option ? "border-ink bg-ink text-white" : "border-line bg-white text-slate-600 hover:border-brand-purple-300 hover:bg-tint-lavender"
              }`}
              title={question.labels?.[String(option)]}
            >
              {option}
            </button>
          ))}
        </div>
      ) : question.type === "multi_select" ? (
        <div className="mt-5 grid gap-2 sm:grid-cols-2">
          {(question.options ?? []).slice(0, 6).map((option) => {
            const selected = Array.isArray(value) && value.includes(option.value);
            return (
              <button
                key={option.value}
                type="button"
                disabled={disabled}
                onClick={() => onToggleMulti(question.question_id, option.value)}
                className={`min-h-11 rounded-lg border px-3 py-2 text-left text-sm transition disabled:cursor-not-allowed ${
                  selected ? "border-ink bg-ink text-white" : "border-line bg-white text-slate-600 hover:border-brand-purple-300 hover:bg-tint-lavender"
                }`}
              >
                {option.label}
              </button>
            );
          })}
        </div>
      ) : (
        <div className="mt-5 grid gap-2 sm:grid-cols-2">
          {(question.options ?? []).slice(0, 6).map((option) => (
            <button
              key={option.value}
              type="button"
              disabled={disabled}
              onClick={() => onSetAnswer(question.question_id, option.value)}
              className={`min-h-11 rounded-lg border px-3 py-2 text-left text-sm transition disabled:cursor-not-allowed ${
                value === option.value ? "border-ink bg-ink text-white" : "border-line bg-white text-slate-600 hover:border-brand-purple-300 hover:bg-tint-lavender"
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function isAnswered(value: GuideV2DiagnosticValue | undefined) {
  if (Array.isArray(value)) return value.length > 0;
  return value !== undefined && String(value).length > 0;
}
