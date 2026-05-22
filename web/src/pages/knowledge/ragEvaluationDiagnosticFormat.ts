import { readNumber } from "./ragUtils";

export function formatRagDiagnosticHeadline(summary: Record<string, unknown>) {
  const affected = readNumber(summary, "affected_cases") ?? 0;
  const primaryIssue = String(summary.primary_issue_code || "");
  if (!affected) return "这次检查没有发现明显查找异常。";
  return `本次有 ${affected} 个样本需要优先检查，主要问题是：${formatRagCaseIssue(primaryIssue, summary.headline)}`;
}

export function formatRagDiagnosticSummaryAction(summary: Record<string, unknown>) {
  const primaryIssue = String(summary.primary_issue_code || "");
  return `建议先做这一件事：${formatRagCaseRecommendation(primaryIssue, summary.recommendation)}`;
}

export function ragDiagnosticSeverityTone(value: string): "success" | "warning" | "neutral" {
  if (value === "critical" || value === "high") return "warning";
  return "neutral";
}

export function formatRagDiagnosticSeverity(value: string) {
  const labels: Record<string, string> = {
    critical: "严重",
    high: "高",
    low: "低",
    medium: "中",
  };
  return labels[value] || "待查";
}

export function formatRagCaseIssue(issueCode: string, fallback: unknown) {
  const labels: Record<string, string> = {
    context_budget_trimmed: "回答材料上限截断，部分来源没有进入最终材料。",
    expected_source_missed: "期望来源没有命中，可能是文件元数据或切片边界问题。",
    late_expected_source: "期望来源已经找到，但排得太靠后，模型可能优先读到弱来源。",
    low_keyword_recall: "关键词覆盖不足，找到的内容和问题意图贴合度不够。",
    no_sources: "没有找到可用来源。",
    retrieval_error: "资料查找失败。",
    search_failed: "资料服务返回失败。",
    short_context: "找到的来源过短，难以支撑稳定回答。",
    threshold_trimmed: "分数阈值可能过滤掉了有用来源。",
  };
  return labels[issueCode] || String(fallback || "需要检查这个样本的资料查找链路。");
}

export function formatRagCaseRecommendation(issueCode: string, fallback: unknown) {
  const labels: Record<string, string> = {
    context_budget_trimmed: "优先尝试来源重排保留强来源，或适当提高回答材料上限。",
    expected_source_missed: "检查对应文件是否完成入库，再对比混合查找和更细的切片。",
    late_expected_source: "优先启用重排，或调整混合查找权重，把关键来源推到来源列表前 3 条。",
    low_keyword_recall: "尝试开启混合查找、问题改写，或补充课程术语同义词。",
    no_sources: "先确认资料已整理完成，再扩大来源数量或降低相关度阈值。",
    retrieval_error: "检查资料服务、模型服务、策略设置和超时设置。",
    search_failed: "先用基础策略复测，确认是策略问题还是资料服务问题。",
    short_context: "提高回答材料上限，或扩大候选来源数量后再重排。",
    threshold_trimmed: "降低相关度阈值，并与宽松语义查找策略做对比。",
  };
  return labels[issueCode] || String(fallback || "建议查看该样本的资料来源和处理记录。");
}
