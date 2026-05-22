import type { KnowledgeRecoveryCheck, KnowledgeRecoveryInput } from "./KnowledgeRecoveryTypes";

export function buildRecoveryChecks(
  input: KnowledgeRecoveryInput,
  documentCount: number | null,
  vectorCount: number | null,
): KnowledgeRecoveryCheck[] {
  const readinessLabel = input.readinessLabel || input.diagnosticStatus || "未检查";
  return [
    {
      label: "资料清单",
      detail: documentCount === null ? "正在读取" : `${documentCount} 份资料`,
      tone: documentCount === null ? "neutral" : documentCount > 0 ? "success" : "warning",
    },
    {
      label: "引用片段",
      detail: vectorCount === null ? "等待检查" : `${vectorCount} 条可引用片段`,
      tone: vectorCount === null ? "neutral" : vectorCount > 0 ? "success" : "warning",
    },
    {
      label: "资料状态",
      detail: String(readinessLabel),
      tone: normalize(input.readinessState) === "ready" ? "success" : input.diagnosticStatus === "异常" ? "danger" : "neutral",
    },
    {
      label: "当前任务",
      detail: input.progressMessage || input.progressStage || "暂无任务",
      tone: input.taskActive ? "brand" : ["error", "failed"].includes(normalize(input.progressStage)) ? "danger" : "neutral",
    },
  ];
}

export function toFiniteNumber(value: number | string | null | undefined) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

export function normalize(value: unknown) {
  const text = String(value || "").trim().toLowerCase();
  if (!text) return "";
  return text.includes(":") ? text.split(":").pop() || text : text;
}
