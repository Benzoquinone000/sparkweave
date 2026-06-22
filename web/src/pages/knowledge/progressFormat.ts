import type { KnowledgeProgress } from "@/lib/types";

import { formatProgressStage } from "./format";

const LEGACY_TEXT_SEPARATOR = "\u001F";

type KnowledgeTaskPayload = {
  line?: string;
  detail?: string;
  task_id?: string;
  [key: string]: unknown;
};

export type KnowledgeWsStatus = "idle" | "connecting" | "live" | "closed" | "error";

export type KnowledgeWsMessage = {
  type?: string;
  data?: KnowledgeProgress;
  message?: string;
};

export function withLegacyText(visible: string, legacy: string) {
  return `${visible}${LEGACY_TEXT_SEPARATOR}${legacy}`;
}

export function progressPercent(progress: KnowledgeProgress | undefined | null) {
  const value = typeof progress?.percent === "number" ? progress.percent : progress?.progress_percent;
  return typeof value === "number" && Number.isFinite(value) ? clampPercent(value) : undefined;
}

export function formatTaskEvent(label: "log" | "status" | "complete" | "failed" | "message", raw: string) {
  const payload = parseTaskPayload(raw);
  if (payload) {
    if (payload.line) return withLegacyText(formatKnowledgeLogLine(String(payload.line), label), String(payload.line));
    const labelText = formatTaskLabel(label);
    const legacyLabel = label;
    if (payload.detail) return withLegacyText(`${labelText}: ${formatKnowledgeLogLine(String(payload.detail), label)}`, `${legacyLabel}: ${payload.detail}`);
    const serialized = JSON.stringify(payload);
    return withLegacyText(`${labelText}: 收到任务更新`, `${legacyLabel}: ${serialized}`);
  }
  return raw ? withLegacyText(formatKnowledgeLogLine(raw, label), raw) : formatTaskLabel(label);
}

export function parseTaskPayload(raw: string) {
  try {
    return JSON.parse(raw) as KnowledgeTaskPayload;
  } catch {
    return null;
  }
}

function formatTaskLabel(label: "log" | "status" | "complete" | "failed" | "message") {
  return {
    log: "记录",
    status: "状态",
    complete: "完成",
    failed: "失败",
    message: "消息",
  }[label];
}

export function formatWsProgress(progress: KnowledgeProgress) {
  const rawState = progress.stage || progress.status || "progress";
  const state = formatProgressStage(rawState);
  const percentValue = progressPercent(progress);
  const percent = typeof percentValue === "number" ? ` ${percentValue}%` : "";
  const message = progress.message ? ` ${formatKnowledgeLogLine(progress.message)}` : "";
  const legacyMessage = progress.message ? ` ${progress.message}` : "";
  return withLegacyText(`进度 ${state}${percent}${message}`.trim(), `ws: ${rawState}${percent}${legacyMessage}`.trim());
}

export function formatWsStatus(status: KnowledgeWsStatus) {
  return {
    idle: "轮询中",
    connecting: "连接中",
    live: "实时同步",
    closed: "同步完成",
    error: "同步异常",
  }[status];
}

export function visibleKnowledgeLogText(line: string) {
  const [visible] = line.split(LEGACY_TEXT_SEPARATOR);
  return visible || "";
}

export function summarizeKnowledgeTaskLogs(lines: string[]) {
  const milestones: string[] = [];
  for (const line of lines) {
    const visible = visibleKnowledgeLogText(line).trim();
    if (!visible || isNoisyKnowledgeLog(visible)) continue;
    if (milestones[milestones.length - 1] !== visible) milestones.push(visible);
  }
  return milestones.slice(-4);
}

function isNoisyKnowledgeLog(value: string) {
  const lower = value.toLowerCase();
  if (lower.includes("heartbeat")) return true;
  if (lower.includes("已连接任务流") || lower.includes("已连接知识库进度通道")) return true;
  if (lower.includes("进度通道保持连接")) return true;
  if (lower.includes("收到任务更新") || lower.includes("收到进度更新")) return true;
  return false;
}

export function formatProgressMessage(progress: KnowledgeProgress | undefined | null, activeKb: string, hasTaskContext: boolean) {
  const state = String(progress?.stage || progress?.status || "").toLowerCase();
  if (!progress) return activeKb || "暂无任务";
  if (state === "not_started") return hasTaskContext ? "等待资料处理更新..." : "暂无处理任务";
  return progress.message ? formatKnowledgeLogLine(progress.message) : activeKb || "暂无任务";
}

export function formatKnowledgeWsMessage(payload: KnowledgeWsMessage) {
  if (payload.data) return formatWsProgress(payload.data);
  if (payload.message) return withLegacyText(`进度更新: ${formatKnowledgeLogLine(payload.message)}`, `进度更新: ${payload.message}`);
  if (payload.type === "complete" || payload.type === "failed" || payload.type === "log" || payload.type === "message") {
    return `进度更新: ${formatTaskLabel(payload.type)}`;
  }
  if (String(payload.type || "").toLowerCase() === "heartbeat") return "进度更新: 进度通道保持连接";
  if (payload.type) return withLegacyText("进度更新: 收到任务状态", `进度更新: ${payload.type}`);
  return "收到进度更新";
}

export function formatKnowledgeWsText(raw: string) {
  const value = raw.trim();
  if (!value) return "收到进度更新";
  if (value.startsWith("{") || value.startsWith("[")) return "收到进度更新";
  return withLegacyText(`进度更新: ${formatKnowledgeLogLine(value)}`, `进度更新: ${value}`);
}

export function formatKnowledgeLogLine(raw: string, label?: "log" | "status" | "complete" | "failed" | "message") {
  const original = String(raw || "").trim();
  if (!original) return formatTaskLabel(label || "message");
  const text = original.replace(/^\[[^\]]+\]\s*/, "").trim();
  const lower = text.toLowerCase();
  const processed = text.match(/^successfully processed\s+(\d+)\s+files?\s+for\s+'([^']+)'/i);
  if (processed) return `完成: 已处理 ${processed[1]} 个文件 (${processed[2]})`;
  const processedFiles = text.match(/^processed\s+(\d+)\s+file\(s\)\s+for\s+'([^']+)'/i);
  if (processedFiles) return `已处理 ${processedFiles[1]} 个文件: ${processedFiles[2]}`;
  const processingFiles = text.match(/^processing\s+(\d+)\s+file\(s\)\s+for\s+kb\s+'([^']+)'/i);
  if (processingFiles) return `正在处理 ${processingFiles[1]} 个文件: ${processingFiles[2]}`;
  const indexed = text.match(/^indexed\s+(\d+)\s+file\(s\)/i);
  if (indexed) return `已整理资料: ${indexed[1]} 个文件`;
  const processedByProvider = text.match(/^processed\s+\(([^)]+)\):\s+(.+)/i);
  if (processedByProvider) return `已整理: ${processedByProvider[2]}`;
  const indexing = text.match(/^indexing\s+\(([^)]+)\)\s+(.+?)(\s+\([^)]+\))?$/i);
  if (indexing) return `正在整理: ${indexing[2]}${indexing[3] || ""}`;
  const staged = text.match(/^staged\s+(\d+)\s+new\s+file\(s\)/i);
  if (staged) return `已暂存 ${staged[1]} 个新文件`;
  const recovering = text.match(/^recovering staged file:\s+(.+)/i);
  if (recovering) return `恢复待处理文件: ${recovering[1]}`;
  const validating = text.match(/^validating documents for\s+'([^']+)'/i);
  if (validating) return `正在校验资料: ${validating[1]}`;
  const found = text.match(/^found\s+(\d+)\s+documents?,\s+starting to process/i);
  if (found) return `找到 ${found[1]} 份资料，开始处理`;
  const initializing = text.match(/^initializing knowledge base\s+'([^']+)'/i);
  if (initializing) return `正在初始化资料库: ${initializing[1]}`;
  const validationFailed = text.match(/^validation failed for file\s+'([^']+)'/i);
  if (validationFailed) return `文件校验未通过: ${validationFailed[1]}`;
  if (lower.includes("mime type validation failed")) return "文件类型校验未通过，请确认资料格式";
  if (lower.includes("rag pipeline returned failure")) return "资料整理流程失败，请检查资料格式或模型配置";
  if (lower.includes("initialization failed")) return "资料库初始化失败";
  if (lower.includes("document processing failed") || lower.includes("failed to process documents")) return "资料处理失败，请检查文件内容";
  if (lower.includes("error processing documents")) return "资料处理失败，请稍后重试";
  if (lower.includes("real-time progress") && lower.includes("unavailable")) return "实时进度暂时不可用，继续自动刷新";
  if (lower.includes("starting to process documents with")) return "正在调用解析与整理流程...";
  if (lower.includes("saved") && lower.includes("preparing index")) return "资料已保存，正在准备整理";
  if (lower.includes("knowledge base created")) return "资料库已创建";
  if (lower.includes("upload complete")) return "上传完成";
  if (lower.includes("folder sync complete")) return "文件夹同步完成";
  const cleared = text.match(/^progress cleared for\s+(.+)/i);
  if (cleared) return `已清理进度: ${cleared[1]}`;
  if (lower.includes("ws parsing files")) return "正在解析文件";
  if (lower.includes("ws index complete")) return "资料整理完成";
  if (lower === "heartbeat") return "进度通道保持连接";
  return text;
}

export function isTerminalProgress(progress: KnowledgeProgress) {
  const state = String(progress.stage || progress.status || "").toLowerCase();
  return ["complete", "completed", "done", "failed", "error", "cancelled", "canceled"].includes(state);
}

export function clampPercent(value: number | undefined) {
  return Math.max(0, Math.min(100, Math.round(value ?? 0)));
}
