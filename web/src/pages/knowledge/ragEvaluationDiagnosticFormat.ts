import { readNumber } from "./ragUtils";

export function formatRagDiagnosticHeadline(summary: Record<string, unknown>) {
  const affected = readNumber(summary, "affected_cases") ?? 0;
  const primaryIssue = String(summary.primary_issue_code || "");
  if (!affected) return "这次评测没有发现明显召回异常。";
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
    context_budget_trimmed: "上下文预算截断，部分证据没有进入最终上下文。",
    expected_source_missed: "期望来源没有命中，可能是文件元数据或分块边界问题。",
    late_expected_source: "期望来源已经召回，但排得太靠后，模型可能优先读到弱证据。",
    low_keyword_recall: "关键词覆盖不足，召回内容和问题意图贴合度不够。",
    no_sources: "没有召回到可用证据。",
    retrieval_error: "检索执行失败。",
    search_failed: "检索服务返回失败。",
    short_context: "召回证据过短，难以支撑稳定回答。",
    threshold_trimmed: "分数阈值可能过滤掉了有用证据。",
  };
  return labels[issueCode] || String(fallback || "需要检查这个样本的召回链路。");
}

export function formatRagCaseRecommendation(issueCode: string, fallback: unknown) {
  const labels: Record<string, string> = {
    context_budget_trimmed: "优先尝试证据重排保留强证据，或适当提高上下文预算。",
    expected_source_missed: "检查对应文件是否完成入库，再对比混合检索和更细的分块。",
    late_expected_source: "优先启用重排，或调整混合检索权重，把关键来源推到证据列表前 3 条。",
    low_keyword_recall: "尝试开启混合检索、问题改写，或补充课程术语同义词。",
    no_sources: "先确认资料已索引，再扩大证据数量或降低相关度阈值。",
    retrieval_error: "检查检索服务、模型服务、策略参数和超时设置。",
    search_failed: "先用基础策略复测，确认是策略问题还是检索服务问题。",
    short_context: "提高上下文预算，或扩大候选证据数量后再重排。",
    threshold_trimmed: "降低相关度阈值，并与宽松语义检索策略做对比。",
  };
  return labels[issueCode] || String(fallback || "建议查看该样本的来源证据和处理记录。");
}
