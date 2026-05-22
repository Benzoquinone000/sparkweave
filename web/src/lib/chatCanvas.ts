import {
  extractExternalImageResult,
  extractExternalVideoResult,
  extractMathAnimatorResult,
  extractVisualizeResult,
} from "@/lib/capabilityResults";
import { getMessageCapability, getMessageDisplayContent } from "@/lib/chatMessages";
import { extractQuizQuestions } from "@/lib/quiz";
import type { ChatMessage } from "@/lib/types";

export type ChatCanvasDocument = {
  id: string;
  messageId: string;
  title: string;
  content: string;
  autoOpen: boolean;
  updatedAt: number;
  sourceMessage: ChatMessage;
};

export type ChatCanvasContext = {
  id: string;
  message_id: string;
  title: string;
  content: string;
  updated_at: number;
};

type CanvasDetectionOptions = {
  mode?: "manual" | "tool";
};

const DOCUMENT_CAPABILITIES = new Set(["deep_solve", "deep_research"]);
const DOCUMENT_KEYWORDS = [
  "学习计划",
  "复习计划",
  "研究报告",
  "解题稿",
  "讲稿",
  "提纲",
  "方案",
  "设计文档",
  "说明文档",
  "总结",
  "复盘",
  "笔记",
  "报告",
  "草稿",
  "plan",
  "report",
  "outline",
  "draft",
  "document",
  "proposal",
];

export function getCanvasDocumentFromMessage(
  message: ChatMessage,
  options: CanvasDetectionOptions = {},
): ChatCanvasDocument | null {
  if (message.role !== "assistant") return null;
  const mode = options.mode ?? "manual";

  if (mode === "tool") {
    return getCanvasDocumentFromToolEvent(message);
  }

  if (message.status && message.status !== "done") return null;
  if (hasDedicatedResultViewer(message)) return null;

  const content = getMessageDisplayContent(message).trim();
  if (!content) return null;

  const profile = analyzeDocumentShape(content, getMessageCapability(message));
  if (mode === "manual" && !profile.canOpenManually) return null;

  return {
    id: `${message.id}:canvas:${stableContentHash(content)}`,
    messageId: message.id,
    title: getCanvasTitle(content, profile.fallbackTitle),
    content,
    autoOpen: profile.autoOpen,
    updatedAt: Date.now(),
    sourceMessage: message,
  };
}

function getCanvasDocumentFromToolEvent(message: ChatMessage): ChatCanvasDocument | null {
  const events = message.events ?? [];
  for (const event of [...events].reverse()) {
    const payload = getCanvasPayloadFromEvent(event.metadata);
    if (!payload) continue;
    const content = payload.content.trim();
    if (!content) continue;
    const title = cleanTitle(payload.title || getCanvasTitle(content, "可编辑文档"));
    return {
      id: `${message.id}:canvas-tool:${stableContentHash(`${title}:${content}`)}`,
      messageId: message.id,
      title,
      content,
      autoOpen: true,
      updatedAt: Date.now(),
      sourceMessage: { ...message, content },
    };
  }
  return null;
}

function getCanvasPayloadFromEvent(metadata: Record<string, unknown> | undefined | null) {
  const root = asRecord(metadata);
  if (!root) return null;
  const candidates: Record<string, unknown>[] = [root];
  const resultMetadata = asRecord(root.result_metadata);
  if (resultMetadata) candidates.push(resultMetadata);
  const traces = Array.isArray(root.tool_traces) ? root.tool_traces : [];
  for (const trace of traces) {
    const record = asRecord(trace);
    if (!record) continue;
    candidates.push(record);
    const traceMetadata = asRecord(record.metadata);
    if (traceMetadata) candidates.push(traceMetadata);
  }

  for (const candidate of candidates) {
    const canvasMarked =
      candidate.render_type === "canvas_document" || candidate.tool_name === "canvas" || candidate.tool === "canvas";
    const nested =
      asRecord(candidate.canvas_document) ||
      asRecord(candidate.canvas) ||
      (canvasMarked ? asRecord(candidate.document) : null);
    const record = nested || (canvasMarked ? candidate : null);
    if (!record) continue;
    const content = String(record.content || record.markdown || record.body || "").trim();
    if (!content) continue;
    return {
      title: String(record.title || candidate.title || "可编辑文档"),
      content,
    };
  }
  return null;
}

export function getCanvasContextFromDocument(document: ChatCanvasDocument | null): ChatCanvasContext | null {
  const content = document?.content.trim() ?? "";
  if (!document || !content) return null;
  return {
    id: document.id,
    message_id: document.messageId,
    title: document.title.trim() || "可编辑文档",
    content: content.slice(0, 60000),
    updated_at: document.updatedAt || Date.now(),
  };
}

function hasDedicatedResultViewer(message: ChatMessage) {
  const resultEvent = [...(message.events ?? [])].reverse().find((event) => event.type === "result");
  const capability = getMessageCapability(message);
  const quizQuestions = capability === "deep_question" ? extractQuizQuestions(resultEvent?.metadata) : null;
  return Boolean(
    quizQuestions?.length ||
      extractVisualizeResult(resultEvent?.metadata) ||
      extractMathAnimatorResult(resultEvent?.metadata) ||
      extractExternalVideoResult(resultEvent?.metadata) ||
      extractExternalImageResult(resultEvent?.metadata),
  );
}

function analyzeDocumentShape(content: string, capability?: string) {
  const lower = content.toLowerCase();
  const headingCount = (content.match(/^#{1,3}\s+\S/gm) ?? []).length;
  const listCount = (content.match(/^\s*(?:[-*+]|\d+[.)])\s+\S/gm) ?? []).length;
  const tableLike = /^\|.+\|$/m.test(content);
  const fencedBlocks = (content.match(/```/g) ?? []).length / 2;
  const keywordHit = DOCUMENT_KEYWORDS.some((keyword) => lower.includes(keyword.toLowerCase()));
  const documentCapability = Boolean(capability && DOCUMENT_CAPABILITIES.has(capability));
  const structureScore =
    headingCount * 2 +
    Math.min(listCount, 6) +
    (tableLike ? 2 : 0) +
    (fencedBlocks ? 1 : 0) +
    (keywordHit ? 2 : 0) +
    (documentCapability ? 2 : 0);

  const canOpenManually = content.length >= 120 || headingCount > 0 || listCount >= 3 || keywordHit;
  const autoOpen =
    (content.length >= 200 && structureScore >= 6) ||
    (content.length >= 480 && structureScore >= 4) ||
    (content.length >= 360 && documentCapability && structureScore >= 3) ||
    (content.length >= 760 && keywordHit && structureScore >= 2);

  return {
    autoOpen,
    canOpenManually,
    fallbackTitle: documentCapability
      ? capability === "deep_research"
        ? "研究报告"
        : "解题稿"
      : keywordHit
        ? "可编辑文档"
        : "回答草稿",
  };
}

function getCanvasTitle(content: string, fallbackTitle: string) {
  const heading = /^#{1,3}\s+(.+)$/m.exec(content)?.[1]?.trim();
  if (heading) return cleanTitle(heading);
  const firstLine = content
    .split("\n")
    .map((line) => line.replace(/^[-*+]\s+/, "").trim())
    .find(Boolean);
  return cleanTitle(firstLine || fallbackTitle);
}

function cleanTitle(value: string) {
  const compact = value
    .replace(/[*_`>#]/g, "")
    .replace(/\s+/g, " ")
    .trim();
  return (compact || "可编辑文档").slice(0, 36);
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function stableContentHash(content: string) {
  let hash = 0;
  const sample = `${content.length}:${content.slice(0, 240)}:${content.slice(-120)}`;
  for (let index = 0; index < sample.length; index += 1) {
    hash = (hash * 31 + sample.charCodeAt(index)) >>> 0;
  }
  return hash.toString(36);
}
