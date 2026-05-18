import { AlertTriangle, RefreshCw, Search, UploadCloud, type LucideIcon } from "lucide-react";

import type { KnowledgeWorkspace } from "./types";

export type KnowledgeNextStep = {
  title: string;
  summary: string;
  badge: string;
  tone: "brand" | "success" | "warning" | "neutral";
  primaryLabel: string;
  primaryWorkspace: KnowledgeWorkspace;
  primaryIcon: LucideIcon;
  secondaryLabel?: string;
  secondaryWorkspace?: KnowledgeWorkspace;
};

export function buildKnowledgeNextStep({
  documentCount,
  vectorCount,
  progressPercent,
  progressStage,
  taskActive,
  recoveryNeedsAttention,
  testSourceCount,
}: {
  documentCount: number | string | null | undefined;
  vectorCount: number | string | null | undefined;
  progressPercent: number;
  progressStage: string;
  taskActive: boolean;
  recoveryNeedsAttention: boolean;
  testSourceCount?: number | string | null;
}): KnowledgeNextStep {
  const documents = toFiniteNumber(documentCount);
  const vectors = toFiniteNumber(vectorCount);
  const testSources = toFiniteNumber(testSourceCount);
  const stage = String(progressStage || "").trim();
  const stillIndexing = taskActive || (progressPercent > 0 && progressPercent < 100);

  if (stillIndexing) {
    return {
      title: "先等索引跑完",
      summary: "资料正在解析或写入引用索引。完成前可以查看进度，避免在半成品状态下测试问答。",
      badge: stage || "运行中",
      tone: "brand",
      primaryLabel: "查看索引进度",
      primaryWorkspace: "progress",
      primaryIcon: RefreshCw,
      secondaryLabel: "查看资料清单",
      secondaryWorkspace: "documents",
    };
  }

  if (recoveryNeedsAttention) {
    return {
      title: "先处理资料库状态",
      summary: "当前资料库还有需要关注的地方。按修复向导走一遍，会比直接重试问答更省时间。",
      badge: "需处理",
      tone: "warning",
      primaryLabel: "打开修复向导",
      primaryWorkspace: "recovery",
      primaryIcon: AlertTriangle,
      secondaryLabel: "检查连接",
      secondaryWorkspace: "diagnostics",
    };
  }

  if (documents !== null && documents <= 0) {
    return {
      title: "先放入第一批资料",
      summary: "上传课件、笔记或代码文件后，SparkWeave 才能把它们转成可引用的学习上下文。",
      badge: "待导入",
      tone: "neutral",
      primaryLabel: "上传资料",
      primaryWorkspace: "upload",
      primaryIcon: UploadCloud,
      secondaryLabel: "同步文件夹",
      secondaryWorkspace: "folders",
    };
  }

  if (vectors !== null && vectors <= 0) {
    return {
      title: "资料已保存，还差引用索引",
      summary: "文件清单里有资料，但还没有可检索片段。先进入修复向导重建索引，再做问答测试。",
      badge: "需建索引",
      tone: "warning",
      primaryLabel: "打开修复向导",
      primaryWorkspace: "recovery",
      primaryIcon: AlertTriangle,
      secondaryLabel: "查看资料清单",
      secondaryWorkspace: "documents",
    };
  }

  if (testSources === null) {
    return {
      title: "用一个真实问题试一下",
      summary: "资料库已经具备使用条件。先做提问预检，确认关键证据能被召回，再进入聊天问答。",
      badge: "建议预检",
      tone: "brand",
      primaryLabel: "提问预检",
      primaryWorkspace: "test",
      primaryIcon: Search,
      secondaryLabel: "查看资料清单",
      secondaryWorkspace: "documents",
    };
  }

  if (testSources <= 0) {
    return {
      title: "上次预检没有找到证据",
      summary: "先回到提问预检调整检索方案，或进入修复向导检查索引覆盖。",
      badge: "需复测",
      tone: "warning",
      primaryLabel: "继续预检",
      primaryWorkspace: "test",
      primaryIcon: Search,
      secondaryLabel: "打开修复向导",
      secondaryWorkspace: "recovery",
    };
  }

  return {
    title: "资料库已经可以进入问答",
    summary: `上次预检召回 ${testSources} 条证据。可以继续在预检页带证据进入聊天，或先做一次质量评估。`,
    badge: "可使用",
    tone: "success",
    primaryLabel: "继续提问预检",
    primaryWorkspace: "test",
    primaryIcon: Search,
    secondaryLabel: "质量评估",
    secondaryWorkspace: "quality",
  };
}

function toFiniteNumber(value: number | string | null | undefined) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}
