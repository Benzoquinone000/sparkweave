import type {
  ExternalVideoResult,
  MathAnimatorResult,
  NotebookRecord,
  QuizQuestion,
  VisualizeResult,
} from "@/lib/types";

export type RecordAsset = ReturnType<typeof getRecordAsset>;

export function getRecordAsset(record: NotebookRecord) {
  const metadata = asRecord(record.metadata);
  const visualize = isVisualizeResult(metadata?.visualize) ? metadata.visualize : null;
  const mathAnimator = isMathAnimatorResult(metadata?.math_animator) ? metadata.math_animator : null;
  const externalVideo = isExternalVideoResult(metadata?.external_video) ? metadata.external_video : null;
  const quizQuestions = getQuizQuestions(metadata?.quiz);
  const guideHtml = getGuideHtml(record, metadata);
  const kind = typeof metadata?.asset_kind === "string" ? metadata.asset_kind : "";
  return {
    kind,
    visualize,
    mathAnimator,
    externalVideo,
    quizQuestions,
    guideHtml,
    hasPreview: Boolean(visualize || mathAnimator || externalVideo || quizQuestions.length || guideHtml || record.output),
  };
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function isVisualizeResult(value: unknown): value is VisualizeResult {
  const record = asRecord(value);
  const code = asRecord(record?.code);
  return Boolean(
    record &&
      (record.render_type === "svg" || record.render_type === "chartjs" || record.render_type === "mermaid") &&
      code &&
      typeof code.content === "string",
  );
}

function isMathAnimatorResult(value: unknown): value is MathAnimatorResult {
  const record = asRecord(value);
  if (!record) return false;
  return Array.isArray(record.artifacts) || Boolean(record.code) || typeof record.response === "string";
}

function isExternalVideoResult(value: unknown): value is ExternalVideoResult {
  const record = asRecord(value);
  return Boolean(record && Array.isArray(record.videos));
}

function getQuizQuestions(value: unknown): QuizQuestion[] {
  const quiz = asRecord(value);
  const questions = Array.isArray(quiz?.questions) ? quiz.questions : [];
  return questions.flatMap((item) => {
    const record = asRecord(item);
    if (!record || typeof record.question !== "string") return [];
    return [
      {
        question_id: typeof record.question_id === "string" ? record.question_id : undefined,
        question: record.question,
        question_type: typeof record.question_type === "string" ? record.question_type : "written",
        options: normalizeOptions(record.options),
        correct_answer: typeof record.correct_answer === "string" ? record.correct_answer : String(record.correct_answer ?? ""),
        explanation: typeof record.explanation === "string" ? record.explanation : "",
        difficulty: typeof record.difficulty === "string" ? record.difficulty : "",
        concentration: typeof record.concentration === "string" ? record.concentration : "",
        knowledge_context: typeof record.knowledge_context === "string" ? record.knowledge_context : "",
      },
    ];
  });
}

function normalizeOptions(value: unknown) {
  const record = asRecord(value);
  if (!record) return undefined;
  return Object.fromEntries(Object.entries(record).map(([key, option]) => [key, String(option)]));
}

function getGuideHtml(record: NotebookRecord, metadata: Record<string, unknown> | null) {
  if (record.record_type !== "guided_learning") return "";
  if (typeof metadata?.guide_html === "string" && metadata.guide_html.trim()) return metadata.guide_html;
  if (metadata?.output_type === "html" && record.output?.trim()) return record.output;
  const output = record.output?.trim() ?? "";
  return output.startsWith("<") && /<\/[a-z][\s\S]*>/i.test(output) ? output : "";
}
