import { Check, ChevronLeft, ChevronRight, Loader2, RotateCcw } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { TextArea, TextInput } from "@/components/ui/Field";
import { MarkdownRenderer } from "@/components/ui/MarkdownRenderer";
import { recordQuizResults } from "@/lib/api";
import type { QuizQuestion, QuizResultItem } from "@/lib/types";

type QuestionKind = "choice" | "true_false" | "fill_blank" | "written" | "coding";

type AnswerState = {
  selected: string | null;
  typed: string;
  submitted: boolean;
};

const EMPTY_ANSWER: AnswerState = {
  selected: null,
  typed: "",
  submitted: false,
};

function questionKind(question?: QuizQuestion): QuestionKind {
  const raw = String(question?.question_type || "").toLowerCase();
  if (raw.includes("choice") || raw.includes("select") || raw === "mcq") return "choice";
  if (raw.includes("true_false") || raw.includes("true-false") || raw.includes("truefalse") || raw === "tf") return "true_false";
  if (raw.includes("judge") || raw.includes("判断") || raw.includes("是非")) return "true_false";
  if (raw.includes("fill") || raw.includes("blank") || raw.includes("cloze") || raw.includes("填空")) return "fill_blank";
  if (raw.includes("code") || raw.includes("program")) return "coding";
  return "written";
}

function getAnswer(question: QuizQuestion, answer: AnswerState) {
  const kind = questionKind(question);
  return kind === "choice" || kind === "true_false" ? answer.selected || "" : answer.typed.trim();
}

function normalizeBooleanAnswer(value: string) {
  const normalized = value.trim().toLowerCase();
  if (["true", "t", "yes", "y", "correct", "right", "对", "正确", "是", "真"].includes(normalized)) return "true";
  if (["false", "f", "no", "n", "incorrect", "wrong", "错", "错误", "否", "假"].includes(normalized)) return "false";
  return normalized;
}

function normalizeTextAnswer(value: string) {
  return value.trim().replace(/\s+/g, " ").toLowerCase();
}

function acceptableAnswers(correctAnswer: string) {
  return correctAnswer
    .split(/\s*(?:\||;|；|、|\/)\s*/g)
    .map(normalizeTextAnswer)
    .filter(Boolean);
}

function isCorrect(question: QuizQuestion, answer: AnswerState) {
  const userAnswer = getAnswer(question, answer);
  if (!userAnswer) return false;
  const correct = String(question.correct_answer || "").trim();
  const kind = questionKind(question);
  if (kind === "choice") {
    const optionValue = question.options?.[userAnswer] || "";
    return (
      userAnswer.toUpperCase() === correct.toUpperCase() ||
      userAnswer.toUpperCase() === correct.charAt(0).toUpperCase() ||
      normalizeTextAnswer(optionValue) === normalizeTextAnswer(correct)
    );
  }
  if (kind === "true_false") {
    return normalizeBooleanAnswer(userAnswer) === normalizeBooleanAnswer(correct);
  }
  if (kind === "fill_blank") {
    const user = normalizeTextAnswer(userAnswer);
    return acceptableAnswers(correct).some((item) => item === user);
  }
  return normalizeTextAnswer(userAnswer) === normalizeTextAnswer(correct);
}

function canAutoGrade(question: QuizQuestion) {
  return ["choice", "true_false", "fill_blank"].includes(questionKind(question));
}

function typeLabel(question: QuizQuestion) {
  return {
    choice: "选择题",
    true_false: "判断题",
    fill_blank: "填空题",
    written: "主观题",
    coding: "编程题",
  }[questionKind(question)];
}

export function QuizViewer({
  questions,
  sessionId,
}: {
  questions: QuizQuestion[];
  sessionId?: string | null;
}) {
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<number, AnswerState>>({});
  const [recording, setRecording] = useState(false);
  const [recorded, setRecorded] = useState(false);
  const [recordError, setRecordError] = useState("");
  const lastSignature = useRef("");
  const question = questions[index];
  const kind = questionKind(question);
  const answer = answers[index] ?? EMPTY_ANSWER;
  const total = questions.length;
  const completed = useMemo(() => Object.values(answers).filter((item) => item.submitted).length, [answers]);
  const userAnswer = question ? getAnswer(question, answer) : "";
  const submittedResults = useMemo<QuizResultItem[]>(
    () =>
      questions.flatMap((item, itemIndex) => {
        const state = answers[itemIndex];
        if (!state?.submitted) return [];
        return [
          {
            question_id: item.question_id,
            question: item.question,
            question_type: questionKind(item),
            options: item.options ?? {},
            user_answer: getAnswer(item, state),
            correct_answer: item.correct_answer,
            explanation: item.explanation || "",
            difficulty: item.difficulty || "",
            is_correct: isCorrect(item, state),
          },
        ];
      }),
    [answers, questions],
  );

  useEffect(() => {
    if (!sessionId || !total || completed !== total) return;
    const signature = JSON.stringify(submittedResults);
    if (!signature || signature === lastSignature.current) return;
    lastSignature.current = signature;
    setRecording(true);
    setRecordError("");
    void recordQuizResults({ sessionId, answers: submittedResults })
      .then(() => setRecorded(true))
      .catch((error) => {
        lastSignature.current = "";
        setRecordError(error instanceof Error ? error.message : "题目结果回写失败");
      })
      .finally(() => setRecording(false));
  }, [completed, sessionId, submittedResults, total]);

  if (!question) return null;

  const updateAnswer = (patch: Partial<AnswerState>) => {
    setAnswers((current) => ({
      ...current,
      [index]: { ...(current[index] ?? EMPTY_ANSWER), ...patch },
    }));
  };

  const submit = () => {
    if (!userAnswer || answer.submitted) return;
    updateAnswer({ submitted: true });
  };

  const reset = () => {
    updateAnswer({ selected: null, typed: "", submitted: false });
    setRecorded(false);
    setRecordError("");
    lastSignature.current = "";
  };

  const graded = canAutoGrade(question);
  const correct = isCorrect(question, answer);

  return (
    <div className="rounded-lg border border-line bg-canvas p-3" data-testid="quiz-viewer">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="brand">交互练习</Badge>
          <Badge tone="neutral">{typeLabel(question)}</Badge>
          <Badge tone="neutral">
            {index + 1}/{total}
          </Badge>
          {question.difficulty ? <Badge tone="warning">{question.difficulty}</Badge> : null}
          {recorded ? <Badge tone="success">已写入题目本</Badge> : null}
          {recorded ? <span className="sr-only" data-testid="quiz-recorded">recorded</span> : null}
          {recording ? (
            <span className="inline-flex items-center gap-1 text-xs text-slate-500">
              <Loader2 size={12} className="animate-spin" />
              回写中
            </span>
          ) : null}
        </div>
        <span className="text-xs text-slate-500">
          已完成 {completed}/{total}
        </span>
      </div>

      <MarkdownRenderer className="markdown-body mt-4">{question.question}</MarkdownRenderer>

      {kind === "choice" ? (
        <ChoiceAnswer index={index} question={question} answer={answer} updateAnswer={updateAnswer} />
      ) : kind === "true_false" ? (
        <TrueFalseAnswer index={index} answer={answer} updateAnswer={updateAnswer} />
      ) : kind === "fill_blank" ? (
        <TextInput
          value={answer.typed}
          onChange={(event) => updateAnswer({ typed: event.target.value })}
          disabled={answer.submitted}
          placeholder="填写空缺处的答案"
          className="mt-4"
          data-testid="quiz-fill-blank-input"
        />
      ) : (
        <TextArea
          value={answer.typed}
          onChange={(event) => updateAnswer({ typed: event.target.value })}
          disabled={answer.submitted}
          placeholder={kind === "coding" ? "写下你的代码或思路..." : "写下你的答案..."}
          className={kind === "coding" ? "mt-4 min-h-40 font-mono" : "mt-4 min-h-32"}
        />
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {!answer.submitted ? (
          <Button tone="primary" onClick={submit} disabled={!userAnswer} data-testid="quiz-submit">
            <Check size={16} />
            提交答案
          </Button>
        ) : (
          <>
            <Badge tone={graded ? (correct ? "success" : "danger") : "brand"}>
              {graded ? (correct ? "正确" : "待复盘") : "已提交"}
            </Badge>
            <Button tone="quiet" onClick={reset}>
              <RotateCcw size={15} />
              重做本题
            </Button>
          </>
        )}
        <div className="ml-auto flex gap-2">
          <Button
            tone="quiet"
            className="min-h-8 px-2 text-xs"
            onClick={() => setIndex((value) => Math.max(0, value - 1))}
            disabled={index === 0}
            data-testid="quiz-prev"
          >
            <ChevronLeft size={14} />
            上一题
          </Button>
          <Button
            tone="quiet"
            className="min-h-8 px-2 text-xs"
            onClick={() => setIndex((value) => Math.min(total - 1, value + 1))}
            disabled={index === total - 1}
            data-testid="quiz-next"
          >
            下一题
            <ChevronRight size={14} />
          </Button>
        </div>
      </div>

      {answer.submitted ? (
        <div className="mt-4 rounded-lg border border-line bg-white p-3">
          <p className="text-sm font-semibold text-ink">参考答案：{question.correct_answer || "未提供"}</p>
          {question.explanation ? (
            <MarkdownRenderer className="markdown-body mt-3 text-sm text-slate-600">
              {question.explanation}
            </MarkdownRenderer>
          ) : null}
        </div>
      ) : null}

      {recordError ? (
        <p className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-brand-red">{recordError}</p>
      ) : null}
    </div>
  );
}

function ChoiceAnswer({
  index,
  question,
  answer,
  updateAnswer,
}: {
  index: number;
  question: QuizQuestion;
  answer: AnswerState;
  updateAnswer: (patch: Partial<AnswerState>) => void;
}) {
  return (
    <div className="mt-4 grid gap-2">
      {Object.entries(question.options ?? {}).map(([key, value]) => {
        const selected = answer.selected === key;
        const correct = answer.submitted && isCorrect(question, { ...answer, selected: key });
        const wrong = answer.submitted && selected && !correct;
        return (
          <button
            key={key}
            type="button"
            data-testid={`quiz-option-${index}-${key}`}
            disabled={answer.submitted}
            onClick={() => updateAnswer({ selected: key })}
            className={`dt-interactive rounded-lg border p-3 text-left text-sm disabled:transform-none ${
              correct
                ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                : wrong
                  ? "border-red-200 bg-red-50 text-brand-red"
                  : selected
                    ? "border-teal-200 bg-teal-50 text-ink"
                    : "border-line bg-white text-slate-700 hover:border-teal-200"
            }`}
          >
            <span className="font-semibold text-brand-teal">{key}.</span> {value}
          </button>
        );
      })}
    </div>
  );
}

function TrueFalseAnswer({
  index,
  answer,
  updateAnswer,
}: {
  index: number;
  answer: AnswerState;
  updateAnswer: (patch: Partial<AnswerState>) => void;
}) {
  return (
    <div className="mt-4 grid grid-cols-2 gap-2">
      {[
        ["True", "正确"],
        ["False", "错误"],
      ].map(([value, label]) => {
        const selected = answer.selected === value;
        return (
          <button
            key={value}
            type="button"
            data-testid={`quiz-true-false-${index}-${value}`}
            disabled={answer.submitted}
            onClick={() => updateAnswer({ selected: value })}
            className={`dt-interactive rounded-lg border px-3 py-3 text-sm font-medium disabled:transform-none ${
              selected ? "border-teal-200 bg-teal-50 text-brand-teal" : "border-line bg-white text-slate-700 hover:border-teal-200"
            }`}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
