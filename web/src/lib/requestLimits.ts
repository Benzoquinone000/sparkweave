// Keep these values aligned with sparkweave/api/request_limits.py.
export const NOTEBOOK_LIMITS = {
  name: 120,
  description: 1000,
  title: 200,
  summary: 2000,
  userQuery: 4000,
  output: 100000,
} as const;

export const QUESTION_LIMITS = {
  sessionId: 160,
  questionId: 160,
  question: 6000,
  answer: 8000,
  explanation: 12000,
  categoryName: 100,
} as const;

export const CHAT_LIMITS = {
  message: 20000,
  attachments: 5,
  attachmentBytes: 10 * 1024 * 1024,
  filename: 180,
} as const;
