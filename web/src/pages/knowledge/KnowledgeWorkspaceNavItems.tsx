import type { ReactNode } from "react";
import {
  AlertTriangle,
  BarChart3,
  Database,
  FileText,
  FolderSync,
  RefreshCw,
  Search,
  SlidersHorizontal,
  UploadCloud,
} from "lucide-react";

import type { KnowledgeWorkspace } from "./types";

export type KnowledgeWorkspaceNavItem = {
  id: KnowledgeWorkspace;
  title: string;
  description: string;
  icon: ReactNode;
  badge: string;
  tone: "brand" | "success" | "warning" | "neutral";
  accent: string;
};

export type KnowledgeWorkspaceNavItemInput = {
  documentCount: number | string | null | undefined;
  vectorCount: number | string | null | undefined;
  diagnosticStatus: string;
  recoveryBadge: string;
  recoveryNeedsAttention: boolean;
  evaluationAvailable: boolean;
  testSourceCount?: number | string | null;
  folderCount: number;
  taskActive: boolean;
};

export function buildKnowledgeWorkspaceNavItems({
  documentCount,
  diagnosticStatus,
  recoveryBadge,
  recoveryNeedsAttention,
  evaluationAvailable,
  testSourceCount,
  folderCount,
  taskActive,
}: KnowledgeWorkspaceNavItemInput): KnowledgeWorkspaceNavItem[] {
  return [
    {
      id: "overview",
      title: "概览",
      description: "当前知识库的核心状态和下一步入口。",
      icon: <Database size={18} />,
      badge: "首页",
      tone: "brand",
      accent: "bg-tint-sky",
    },
    {
      id: "documents",
      title: "资料清单",
      description: "查看原始文件、文本预览和已入库片段。",
      icon: <FileText size={18} />,
      badge: `${formatWorkspaceCount(documentCount)} 份`,
      tone: "neutral",
      accent: "bg-tint-cream",
    },
    {
      id: "test",
      title: "提问预检",
      description: "输入一个问题，确认资料库能否给出可靠依据。",
      icon: <Search size={18} />,
      badge: testSourceCount == null ? "测试" : `${formatWorkspaceCount(testSourceCount)} 条`,
      tone: testSourceCount ? "success" : "brand",
      accent: "bg-tint-lavender",
    },
    {
      id: "diagnostics",
      title: "连接检查",
      description: "确认检索连接、模型和索引记录是否可用。",
      icon: <Database size={18} />,
      badge: diagnosticStatus || "待检查",
      tone: diagnosticStatus.includes("就绪") ? "success" : "warning",
      accent: "bg-tint-yellow",
    },
    {
      id: "recovery",
      title: "修复向导",
      description: "失败后按建议重试、重建索引或查看处理记录。",
      icon: <AlertTriangle size={18} />,
      badge: recoveryBadge || "向导",
      tone: recoveryNeedsAttention ? "warning" : "neutral",
      accent: "bg-tint-peach",
    },
    {
      id: "quality",
      title: "质量评估",
      description: "用小样本检查召回、排序和上下文质量。",
      icon: <BarChart3 size={18} />,
      badge: evaluationAvailable ? "有报告" : "未评测",
      tone: evaluationAvailable ? "success" : "neutral",
      accent: "bg-tint-mint",
    },
    {
      id: "upload",
      title: "追加资料",
      description: "把新课件、笔记或代码加入当前知识库。",
      icon: <UploadCloud size={18} />,
      badge: "上传",
      tone: "brand",
      accent: "bg-tint-peach",
    },
    {
      id: "settings",
      title: "默认检索",
      description: "调整默认检索模式、说明和重建标记。",
      icon: <SlidersHorizontal size={18} />,
      badge: "设置",
      tone: "neutral",
      accent: "bg-tint-lavender",
    },
    {
      id: "progress",
      title: "索引进度",
      description: "查看导入任务、实时进度和完整处理记录。",
      icon: <RefreshCw size={18} />,
      badge: taskActive ? "运行中" : "记录",
      tone: taskActive ? "brand" : "neutral",
      accent: "bg-tint-sky",
    },
    {
      id: "folders",
      title: "文件夹同步",
      description: "链接本地目录，按需同步课程资料变化。",
      icon: <FolderSync size={18} />,
      badge: `${folderCount} 个`,
      tone: folderCount ? "success" : "neutral",
      accent: "bg-tint-mint",
    },
  ];
}

function formatWorkspaceCount(value: number | string | null | undefined) {
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value === "string" && value.trim()) return value;
  return "-";
}
