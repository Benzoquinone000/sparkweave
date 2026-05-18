import { buildRecoveryChecks, normalize, toFiniteNumber } from "./KnowledgeRecoveryChecks";
import type { KnowledgeRecoveryInput, KnowledgeRecoveryPlan } from "./KnowledgeRecoveryTypes";

export type {
  KnowledgeRecoveryAction,
  KnowledgeRecoveryActionId,
  KnowledgeRecoveryCheck,
  KnowledgeRecoveryInput,
  KnowledgeRecoveryPlan,
  KnowledgeRecoveryTone,
} from "./KnowledgeRecoveryTypes";

export function buildKnowledgeRecoveryPlan(input: KnowledgeRecoveryInput): KnowledgeRecoveryPlan {
  const documentCount = toFiniteNumber(input.documentCount);
  const vectorCount = toFiniteNumber(input.vectorCount);
  const stage = normalize(input.progressStage);
  const readinessState = normalize(input.readinessState);
  const diagnosticStatus = normalize(input.diagnosticStatus);
  const latestError = String(input.latestError || "").trim();
  const running = Boolean(input.taskActive) || ["running", "processing", "indexing", "queued", "uploaded"].includes(stage);
  const failed = Boolean(latestError) || ["error", "failed"].includes(stage);
  const connectionProblem =
    readinessState === "error" ||
    readinessState === "connection" ||
    diagnosticStatus === "error" ||
    diagnosticStatus === "异常" ||
    input.readinessLabel === "连接异常";
  const needsIndex =
    ["legacy", "not_indexed", "attention", "needs_index", "needs_reindex"].includes(readinessState) ||
    (documentCount !== null && documentCount > 0 && vectorCount !== null && vectorCount <= 0);
  const empty = documentCount !== null && documentCount <= 0;
  const checks = buildRecoveryChecks(input, documentCount, vectorCount);

  if (failed) {
    return {
      state: "failed",
      title: "刚才的处理没有完成",
      summary: latestError || input.progressMessage || "资料处理遇到异常，先查看处理记录，再选择重试或重建索引。",
      badge: "需处理",
      tone: "danger",
      needsAttention: true,
      primaryAction: {
        id: "progress",
        label: "查看处理记录",
        detail: "先确认失败发生在上传、解析还是索引阶段。",
      },
      secondaryActions: [
        { id: "upload", label: "重新上传", detail: "适合文件校验或上传中断。" },
        { id: "reindex", label: "重建索引", detail: "适合资料已在清单中但不能检索。" },
        { id: "diagnostics", label: "检查连接", detail: "适合检索服务或模型配置异常。" },
      ],
      checks,
    };
  }

  if (running) {
    return {
      state: "running",
      title: "资料正在处理",
      summary: input.progressMessage || "系统正在解析资料并建立引用索引，完成后会自动刷新清单和检索状态。",
      badge: "运行中",
      tone: "brand",
      needsAttention: false,
      primaryAction: {
        id: "progress",
        label: "查看进度",
        detail: "查看当前处理到哪一步。",
      },
      secondaryActions: [
        { id: "documents", label: "看资料清单", detail: "确认已保存的文件。" },
        { id: "diagnostics", label: "检查连接", detail: "处理太久时确认检索服务可用。" },
      ],
      checks,
    };
  }

  if (connectionProblem) {
    return {
      state: "connection",
      title: "检索连接需要检查",
      summary: input.readinessSummary || "资料库暂时无法确认检索连接，聊天可能拿不到资料依据。",
      badge: "连接异常",
      tone: "danger",
      needsAttention: true,
      primaryAction: {
        id: "diagnostics",
        label: "检查连接",
        detail: input.readinessAction || "确认检索服务、模型配置和索引记录。",
      },
      secondaryActions: [
        { id: "progress", label: "查看处理记录", detail: "确认最近一次索引是否失败。" },
        { id: "reindex", label: "重建索引", detail: "连接恢复后刷新引用索引。" },
      ],
      checks,
    };
  }

  if (needsIndex) {
    return {
      state: "needs_index",
      title: "资料还不能稳定引用",
      summary: input.readinessSummary || "资料可能已经保存，但引用索引还不完整，问答时容易找不到依据。",
      badge: "需建索引",
      tone: "warning",
      needsAttention: true,
      primaryAction: {
        id: "reindex",
        label: "重建索引",
        detail: input.readinessAction || "重新解析现有资料并写入可检索引用。",
      },
      secondaryActions: [
        { id: "documents", label: "查看资料", detail: "确认原始文件已经保存。" },
        { id: "diagnostics", label: "检查连接", detail: "确认检索服务可写入。" },
        { id: "upload", label: "追加资料", detail: "如果清单为空，先补充资料。" },
      ],
      checks,
    };
  }

  if (empty) {
    return {
      state: "empty",
      title: "先放入第一批资料",
      summary: "这个资料库还没有可用资料。上传课件、笔记或代码文件后，系统会自动建立引用索引。",
      badge: "待导入",
      tone: "neutral",
      needsAttention: false,
      primaryAction: {
        id: "upload",
        label: "上传资料",
        detail: "选择文件并开始索引。",
      },
      secondaryActions: [
        { id: "folders", label: "同步文件夹", detail: "资料集中在本地目录时使用。" },
        { id: "diagnostics", label: "检查连接", detail: "上传前确认检索服务可用。" },
      ],
      checks,
    };
  }

  return {
    state: "ready",
    title: "资料库可以使用",
    summary: input.readinessSummary || "资料已保存并建立引用索引，可以在聊天或导学中使用。",
    badge: "可使用",
    tone: "success",
    needsAttention: false,
    primaryAction: {
      id: "test",
      label: "提问预检",
      detail: "用一个真实问题确认能找到依据。",
    },
    secondaryActions: [
      { id: "documents", label: "查看资料", detail: "检查原文和引用片段。" },
      { id: "diagnostics", label: "检查连接", detail: "查看检索状态详情。" },
      { id: "upload", label: "继续上传", detail: "补充新的课程资料。" },
    ],
    checks,
  };
}
