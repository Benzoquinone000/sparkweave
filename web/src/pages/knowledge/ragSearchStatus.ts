import type { RagSearchTestResult } from "@/lib/types";

import { isRecord, readString, toStringArray } from "./ragUtils";

export type BadgeTone = "neutral" | "success" | "warning" | "danger" | "brand";
export type RagSearchRecoveryAction = "setup" | "deep" | "agentic" | "sources" | "diagnostics";

export type RagSearchRecovery = {
  tone: BadgeTone;
  badge: string;
  title: string;
  description: string;
  primary: {
    label: string;
    action: RagSearchRecoveryAction;
  };
  secondary?: {
    label: string;
    action: RagSearchRecoveryAction;
  };
};

export function describeRagSearchStatus(result: RagSearchTestResult, sourceCount: number, contentChars: number) {
  if (result.success === false) {
    return { tone: "warning" as const, label: "检索失败", shortLabel: "失败" };
  }
  if (sourceCount <= 0) {
    return { tone: "neutral" as const, label: "未找到证据", shortLabel: "0 条证据" };
  }
  if (isWeakRagSearchResult(result, sourceCount, contentChars)) {
    return { tone: "warning" as const, label: "证据偏弱", shortLabel: `${sourceCount} 条证据` };
  }
  return { tone: "success" as const, label: "检索完成", shortLabel: `${sourceCount} 条证据` };
}

export function buildRagSearchRecovery(result: RagSearchTestResult, sourceCount: number, contentChars: number): RagSearchRecovery | null {
  if (result.success === false) {
    const readiness = isRecord(result.readiness) ? result.readiness : null;
    const readinessLabel = readString(readiness, "label");
    const readinessSummary = readString(readiness, "summary");
    const readinessAction = readString(readiness, "primary_action");
    const hasReadiness = Boolean(readinessLabel || readinessSummary || readinessAction);
    return {
      tone: "warning",
      badge: "先修复",
      title: readinessLabel ? `检索未完成：${readinessLabel}` : "这次检索没有完成",
      description: readinessSummary
        ? `${readinessSummary}${readinessAction ? ` 下一步：${readinessAction}` : ""}`
        : "先回到提问预检，换一个更稳妥的方案复测；如果仍失败，再进入诊断页看是哪一步没有拿到资料。",
      primary: hasReadiness ? { label: "检查连接", action: "diagnostics" } : { label: "调整检索", action: "setup" },
      secondary: hasReadiness ? { label: "调整检索", action: "setup" } : { label: "查看检索过程", action: "agentic" },
    };
  }

  if (sourceCount <= 0) {
    return {
      tone: "neutral",
      badge: "需补证据",
      title: "还没有找到可引用资料",
      description: "如果资料已经完成索引，可以先套用深度追问方案，扩大问题拆分和来源上限；如果仍为空，再回到资料管理检查文档入库。",
      primary: { label: "套用深度追问方案", action: "deep" },
      secondary: { label: "调整检索", action: "setup" },
    };
  }

  if (isWeakRagSearchResult(result, sourceCount, contentChars)) {
    return {
      tone: "warning",
      badge: "建议复测",
      title: "证据已经召回，但还不够扎实",
      description: "建议增加来源上限或上下文预算，确认关键片段真的进入回答材料，再让聊天使用这个资料库回答。",
      primary: { label: "调整检索", action: "setup" },
      secondary: { label: "查看证据列表", action: "sources" },
    };
  }

  return null;
}

function isWeakRagSearchResult(result: RagSearchTestResult, sourceCount: number, contentChars: number) {
  const quality = isRecord(result.agentic_quality) ? result.agentic_quality : null;
  const reasons = toStringArray(quality?.reasons ?? result.agentic_fallback_reason);
  const qualityStatus = readString(quality, "status");
  return (
    result.agentic_fallback === true ||
    qualityStatus === "weak" ||
    reasons.includes("low_source_count") ||
    reasons.includes("low_context_chars") ||
    reasons.includes("low_relevance_coverage") ||
    (sourceCount > 0 && sourceCount < 2) ||
    (contentChars > 0 && contentChars < 300)
  );
}
