export type SparkBotHistoryPiece = {
  role: string;
  content: string;
};

export function latestAssistantReply(history: Array<Record<string, unknown>>) {
  for (const item of history) {
    const piece = sparkBotHistoryPieces(item).find((entry) => ["assistant", "bot"].includes(entry.role) && entry.content);
    if (piece?.content) return piece.content;
  }
  return "";
}

export function textFromRecord(record: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = unknownText(record[key]);
    if (value) return value;
  }
  return "";
}

export function trimText(value: string, maxLength: number) {
  const text = value.trim();
  if (text.length <= maxLength) return text;
  return `${text.slice(0, Math.max(0, maxLength - 1)).trim()}…`;
}

export function sparkBotHistoryPieces(item: Record<string, unknown>): SparkBotHistoryPiece[] {
  const user = unknownText(item.user);
  const assistant = unknownText(item.assistant);
  const paired = [
    user ? { role: "user", content: user } : null,
    assistant ? { role: "assistant", content: assistant } : null,
  ].filter(Boolean) as SparkBotHistoryPiece[];
  if (paired.length) return paired;

  return [
    {
      role: unknownText(item.role) || unknownText(item.type) || "message",
      content: unknownText(item.content) || unknownText(item.message) || unknownText(item.text) || safeJson(item),
    },
  ];
}

export function sparkBotHistoryTimestamp(item: Record<string, unknown>) {
  return unknownText(item.timestamp) || unknownText(item.created_at) || unknownText(item.updated_at);
}

export function sparkBotHistoryChannel(item: Record<string, unknown>) {
  const channel = unknownText(item.channel);
  const chatId = unknownText(item.chat_id);
  if (channel && chatId && channel !== chatId) return `${channel} / ${chatId}`;
  return channel || chatId;
}

export function formatHistoryRole(role: string) {
  return (
    {
      user: "你",
      human: "你",
      assistant: "助教",
      bot: "助教",
      system: "系统",
    }[role] || role
  );
}

export function unknownText(value: unknown) {
  if (typeof value === "string") return value.trim();
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return "";
}

export function safeJson(value: unknown) {
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}
