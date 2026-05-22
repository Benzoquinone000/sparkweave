import type { RagDiagnostic } from "@/lib/types";

import { isRecord } from "./ragUtils";

export function formatBytes(size: number) {
  if (size >= 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`;
  if (size >= 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${size} B`;
}

export function formatDocDate(value: unknown) {
  if (!value) return "未知时间";
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export function formatErrorMessage(error: unknown) {
  if (!error) return "未知错误";
  if (error instanceof Error) return error.message;
  return String(error);
}

export function knowledgeProviderLabel(value: unknown) {
  const raw = String(value || "").trim();
  if (!raw) return "智能资料库";
  const normalized = raw.toLowerCase();
  if (normalized.includes("milvus")) return "智能资料库";
  if (normalized.includes("llamaindex")) return "智能资料库";
  if (normalized.includes("mineru")) return "文档解析";
  return raw;
}

export function formatProgressStage(stage: string | undefined) {
  const rawState = String(stage || "idle").toLowerCase();
  const state = rawState.includes(":") ? rawState.split(":").pop() || rawState : rawState;
  const labels: Record<string, string> = {
    done: "已完成",
    ready: "已就绪",
    saved: "已保存",
    init: "准备中",
    idle: "等待中",
    error: "异常",
    failed: "失败",
    running: "处理中",
    processing: "处理中",
    indexing: "整理资料",
    completed: "已完成",
    queued: "排队中",
    uploaded: "已上传",
  };
  return labels[state] || state || "等待中";
}

export function summarizeKnowledgePayload(payload: Record<string, unknown>) {
  const preferredKeys = [
    "rag_provider",
    "provider",
    "embedding_model",
    "embedding_dim",
    "embedding_dimension",
    "chunk_count",
    "node_count",
    "document_count",
    "file_count",
    "updated_at",
    "created_at",
  ];
  const seen = new Set<string>();
  const items: Array<{ key: string; label: string; value: string }> = [];
  const add = (key: string) => {
    if (seen.has(key) || !(key in payload)) return;
    const value = key === "rag_provider" || key === "provider" ? knowledgeProviderLabel(payload[key]) : formatKnowledgeSummaryValue(payload[key]);
    if (!value) return;
    seen.add(key);
    items.push({ key, label: labelKnowledgeSummaryField(key), value });
  };
  preferredKeys.forEach(add);
  Object.keys(payload)
    .filter((key) => !seen.has(key))
    .forEach(add);
  return items.slice(0, 6);
}

function labelKnowledgeSummaryField(key: string) {
  const labels: Record<string, string> = {
    rag_provider: "查找服务",
    provider: "查找服务",
    embedding_model: "查找模型",
    embedding_dim: "模型维度",
    embedding_dimension: "模型维度",
    chunk_count: "片段数",
    node_count: "引用片段",
    document_count: "文档数",
    file_count: "文件数",
    updated_at: "最近更新",
    created_at: "创建时间",
    path: "路径",
  };
  return labels[key] || key.replace(/_/g, " ");
}

function formatKnowledgeSummaryValue(value: unknown) {
  if (value === null || value === undefined || value === "") return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value === "boolean") return value ? "是" : "否";
  if (Array.isArray(value)) return `${value.length} 项`;
  if (isRecord(value)) return `${Object.keys(value).length} 项`;
  return "";
}

export function formatRagDiagnosticStatus(status: unknown, hasError = false) {
  if (hasError) return "异常";
  const normalized = String(status || "").toLowerCase();
  const labels: Record<string, string> = {
    ok: "正常",
    configured: "已配置",
    warning: "需留意",
    error: "异常",
  };
  return labels[normalized] || "未检查";
}

export function ragDiagnosticTone(
  status: unknown,
  hasError = false,
): "neutral" | "success" | "warning" | "danger" | "brand" {
  if (hasError) return "danger";
  const normalized = String(status || "").toLowerCase();
  if (normalized === "ok") return "success";
  if (normalized === "configured") return "brand";
  if (normalized === "warning") return "warning";
  if (normalized === "error") return "danger";
  return "neutral";
}

export function formatRagDiagnosticSummary(report?: RagDiagnostic) {
  if (!report) return "点击检查后，会确认资料连接、引用片段和模型配置。";
  if (report.status === "ok") {
    return report.collection_name
      ? `资料连接正常，资料库「${report.collection_name}」可用。`
      : `资料连接正常，可见 ${report.collection_count ?? 0} 个资料库。`;
  }
  if (report.status === "warning") {
    const warning = report.checks?.find((check) => String(check.status).toLowerCase() === "warning");
    return warning?.message || "资料库可继续使用，但建议检查引用片段、名称或资料服务部署方式。";
  }
  if (report.status === "error") {
    const error = report.checks?.find((check) => String(check.status).toLowerCase() === "error");
    return error?.message || "资料连接失败，请检查服务地址和依赖。";
  }
  return `${knowledgeProviderLabel(report.provider || "milvus")} 已配置，点击检查连接可做完整验证。`;
}

export function formatRagCheckName(name: unknown) {
  const labels: Record<string, string> = {
    marker: "资料标记",
    collection: "资料集合",
    connection: "连接",
    dependency: "依赖",
    provider: "引擎",
    milvus_lite: "本地资料库",
  };
  const key = String(name || "");
  return labels[key] || key || "检查项";
}

export function formatDiagnosticError(error: unknown) {
  if (error instanceof Error) return error.message;
  return "检查请求失败，请稍后重试。";
}
