import type { CapabilityId, ChatMessage, StreamEvent } from "@/lib/types";

const RESULT_TEXT_KEYS = ["response", "final_answer", "answer", "output", "result", "text", "content"];
const CAPABILITY_IDS = new Set<CapabilityId>([
  "chat",
  "deep_solve",
  "deep_question",
  "deep_research",
  "visualize",
  "math_animator",
]);
const SPECIALIST_CAPABILITIES = new Set<CapabilityId>([
  "deep_solve",
  "deep_question",
  "deep_research",
  "visualize",
  "math_animator",
]);

export function getMessageDisplayContent(message: ChatMessage) {
  const content = message.content.trim();
  if (content) return content;
  const resultEvent = [...(message.events ?? [])].reverse().find((event) => event.type === "result");
  return getResultEventText(resultEvent);
}

export function getResultEventText(event?: StreamEvent | null) {
  if (!event) return "";
  const direct = event.content?.trim();
  if (direct) return direct;
  return getTextFromRecord(event.metadata) || getTextFromRecord(asRecord(event.metadata?.metadata));
}

export function getCapabilityFromEvent(event?: StreamEvent | null): CapabilityId | null {
  if (!event) return null;
  const metadata = event.metadata ?? {};
  const metadataCapability = metadata.target_capability ?? metadata.capability;
  if (isCapabilityId(metadataCapability)) return metadataCapability;
  if (isCapabilityId(event.source)) return event.source;
  return null;
}

export function getMessageCapability(message: ChatMessage): CapabilityId | undefined {
  const eventCapability = [...(message.events ?? [])]
    .reverse()
    .map((event) => getCapabilityFromEvent(event))
    .find((capability): capability is CapabilityId => Boolean(capability && SPECIALIST_CAPABILITIES.has(capability)));
  if (eventCapability) return eventCapability;
  return message.capability;
}

function getTextFromRecord(record?: Record<string, unknown> | null) {
  if (!record) return "";
  for (const key of RESULT_TEXT_KEYS) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return "";
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function isCapabilityId(value: unknown): value is CapabilityId {
  return typeof value === "string" && CAPABILITY_IDS.has(value as CapabilityId);
}
