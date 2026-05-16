export function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

export function readString(source: Record<string, unknown>, key: string) {
  const value = source[key];
  return typeof value === "string" ? value : value == null ? "" : String(value);
}

export function splitLines(value: string) {
  return value
    .split(/[\n,，]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function parseMaybeJson(value: unknown): unknown {
  if (!value || typeof value !== "string") return value ?? null;
  const text = value.trim();
  if (!text) return "";
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)\s*```/i);
  const candidates = [fenced?.[1]?.trim(), text];
  const firstObject = text.match(/(\{[\s\S]*\}|\[[\s\S]*\])/);
  if (firstObject?.[1]) candidates.push(firstObject[1]);
  for (const candidate of candidates) {
    if (!candidate) continue;
    try {
      return JSON.parse(candidate);
    } catch {
      // Keep trying softer candidates before falling back to text.
    }
  }
  return text;
}

export function pickFirstText(source: unknown, keys: string[]) {
  const record = asRecord(source);
  if (!record) return "";
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) return value.trim();
    if (Array.isArray(value) && value.every((item) => typeof item === "string")) return value.join("\n");
  }
  const summary = asRecord(record.summary);
  if (summary) return pickFirstText(summary, keys);
  return "";
}

export function extractGuideQuizItems(result: Record<string, unknown> | null): unknown[] {
  const candidates: unknown[] = [];
  const pushFrom = (value: unknown) => {
    if (!value) return;
    const parsed = parseMaybeJson(value);
    if (Array.isArray(parsed)) {
      candidates.push(parsed);
      return;
    }
    const record = asRecord(parsed);
    if (!record) return;
    for (const key of ["results", "questions", "items", "records", "quiz", "data"]) {
      const child = record[key];
      if (Array.isArray(child)) candidates.push(child);
      else if (typeof child === "string") pushFrom(child);
      else if (asRecord(child)) pushFrom(child);
    }
    if (record.summary) pushFrom(record.summary);
  };

  pushFrom(result);
  pushFrom(result?.response);
  pushFrom(result?.content);
  pushFrom(result?.summary);

  const found = candidates.find((items) => Array.isArray(items) && items.some(isQuestionLike));
  return Array.isArray(found) ? found.filter(isQuestionLike) : [];
}

export function isQuestionLike(item: unknown) {
  const record = asRecord(item);
  if (!record) return false;
  const qa = asRecord(record.qa_pair) ?? record;
  return Boolean(
    readString(qa, "question") ||
      readString(qa, "prompt") ||
      readString(qa, "title") ||
      readString(qa, "correct_answer") ||
      readString(qa, "answer"),
  );
}

export function normalizeOptions(value: unknown): Record<string, string> | null {
  if (!value) return null;
  if (Array.isArray(value)) {
    const entries = value
      .map((item, index) => {
        if (typeof item === "string") return [String.fromCharCode(65 + index), item] as const;
        const record = asRecord(item);
        if (!record) return null;
        const key = readString(record, "key") || readString(record, "value") || String.fromCharCode(65 + index);
        const label = readString(record, "label") || readString(record, "text") || readString(record, "content") || key;
        return [key, label] as const;
      })
      .filter((item): item is readonly [string, string] => Boolean(item));
    return entries.length ? Object.fromEntries(entries) : null;
  }
  const record = asRecord(value);
  if (!record) return null;
  const normalized = Object.fromEntries(Object.entries(record).map(([key, item]) => [key, String(item)]));
  return Object.keys(normalized).length ? normalized : null;
}

export function formatTime(value?: number) {
  if (!value) return "";
  return new Date(value * 1000).toLocaleString();
}

export function normalizeGuideQuestionType(value: string, options?: Record<string, unknown> | null) {
  const raw = String(value || "").toLowerCase();
  if (raw.includes("choice") || raw.includes("select") || raw === "mcq") return "choice";
  if (raw.includes("true_false") || raw.includes("true-false") || raw.includes("truefalse") || raw === "tf") return "true_false";
  if (raw.includes("judge") || raw.includes("判断") || raw.includes("是非")) return "true_false";
  if (raw.includes("fill") || raw.includes("blank") || raw.includes("cloze") || raw.includes("填空")) return "fill_blank";
  if (raw.includes("code") || raw.includes("program") || raw.includes("编程")) return "coding";
  if (options && Object.keys(options).length > 0) return "choice";
  return raw || "written";
}

export function guideQuestionTypeLabel(value: string) {
  const labels: Record<string, string> = {
    choice: "选择题",
    true_false: "判断题",
    fill_blank: "填空题",
    written: "简答题",
    coding: "编程题",
  };
  return labels[value] || value || "题目";
}

export function guideAnswerFeedbackLabel(isCorrect: boolean, hasReference: boolean) {
  if (!hasReference) return "已提交";
  return isCorrect ? "答对了" : "答错了";
}

export function isGuideQuizCorrect(answer: string, correctAnswer: string, options?: Record<string, unknown> | null) {
  const user = String(answer || "").trim();
  const correct = String(correctAnswer || "").trim();
  if (!user || !correct) return false;
  if (options && Object.keys(options).length > 0) {
    const optionValue = String(options[user] || "");
    return (
      user.toUpperCase() === correct.toUpperCase() ||
      user.toUpperCase() === correct.charAt(0).toUpperCase() ||
      normalizeAnswer(optionValue) === normalizeAnswer(correct)
    );
  }
  const normalizedUser = normalizeAnswer(user);
  const acceptable = correct
    .split(/\s*(?:\||;|；|、|\/)\s*/g)
    .map(normalizeAnswer)
    .filter(Boolean);
  if (["true", "false"].includes(normalizedUser)) {
    return normalizeBooleanText(normalizedUser) === normalizeBooleanText(correct);
  }
  return acceptable.includes(normalizedUser);
}

export function normalizeBooleanText(value: string) {
  const normalized = normalizeAnswer(value);
  if (["true", "t", "yes", "y", "correct", "right", "正确", "是", "真"].includes(normalized)) return "true";
  if (["false", "f", "no", "n", "incorrect", "wrong", "错误", "否", "假"].includes(normalized)) return "false";
  return normalized;
}

export function normalizeAnswer(value: string) {
  return value.trim().replace(/^选项\s*/i, "").toLowerCase();
}
