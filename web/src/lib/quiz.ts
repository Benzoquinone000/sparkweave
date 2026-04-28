import type { QuizQuestion } from "@/lib/types";

function normalizeQuestionType(value: unknown, options: unknown) {
  const raw = String(value || "").toLowerCase();
  if (raw.includes("choice") || raw.includes("select") || raw === "mcq") return "choice";
  if (raw.includes("true_false") || raw.includes("true-false") || raw.includes("truefalse") || raw === "tf") return "true_false";
  if (raw.includes("judge") || raw.includes("判断") || raw.includes("是非")) return "true_false";
  if (raw.includes("fill") || raw.includes("blank") || raw.includes("cloze") || raw.includes("填空")) return "fill_blank";
  if (raw.includes("code") || raw.includes("program") || raw.includes("编程")) return "coding";
  if (options && typeof options === "object" && Object.keys(options).length > 0) return "choice";
  return raw || "written";
}

export function extractQuizQuestions(resultMetadata: Record<string, unknown> | undefined): QuizQuestion[] | null {
  const summary = resultMetadata?.summary as Record<string, unknown> | undefined;
  const results = summary?.results as Array<Record<string, unknown>> | undefined;
  if (!Array.isArray(results) || !results.length) return null;

  const questions = results.flatMap((item) => {
    const qa = (item.qa_pair ?? item) as Record<string, unknown>;
    if (!qa.question) return [];
    const metadata = qa.metadata as Record<string, unknown> | undefined;
    return [
      {
        question_id: qa.question_id ? String(qa.question_id) : "",
        question: String(qa.question ?? ""),
        question_type: normalizeQuestionType(qa.question_type, qa.options),
        options: qa.options && typeof qa.options === "object" ? (qa.options as Record<string, string>) : undefined,
        correct_answer: String(qa.correct_answer ?? ""),
        explanation: String(qa.explanation ?? ""),
        difficulty: qa.difficulty ? String(qa.difficulty) : undefined,
        concentration: qa.concentration ? String(qa.concentration) : undefined,
        knowledge_context: metadata?.knowledge_context ? String(metadata.knowledge_context) : undefined,
      },
    ];
  });

  return questions.length ? questions : null;
}
