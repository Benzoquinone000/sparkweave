import type { SessionSummary } from "@/lib/types";

const INTERNAL_TITLE_PATTERNS = [
  /^(session|chat|guide|turn|task|op)[-_:.]/i,
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
];

function clean(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function looksInternal(value: string, session?: Pick<SessionSummary, "id" | "session_id">) {
  const normalized = value.trim();
  if (!normalized) return true;
  if (session && (normalized === session.session_id || normalized === session.id)) return true;
  return INTERNAL_TITLE_PATTERNS.some((pattern) => pattern.test(normalized));
}

function truncateTitle(value: string) {
  return value.length > 26 ? `${value.slice(0, 26)}...` : value;
}

export function sessionDisplayTitle(session: SessionSummary, index = 0) {
  const title = clean(session.title);
  if (title && !looksInternal(title, session)) return title;

  const lastMessage = clean(session.last_message);
  if (lastMessage && !looksInternal(lastMessage)) return truncateTitle(lastMessage);

  return `学习会话 ${index + 1}`;
}
