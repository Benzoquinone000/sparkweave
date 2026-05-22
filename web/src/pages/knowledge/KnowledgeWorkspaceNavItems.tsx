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
  group: "main" | "advanced";
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
      title: "资料首页",
      description: "回到上传、提问和处理状态。",
      icon: <Database size={18} />,
      badge: "首页",
      tone: "brand",
      accent: "bg-tint-sky",
      group: "main",
    },
    {
      id: "upload",
      title: "添加资料",
      description: "添加课件、笔记、论文或代码文件。",
      icon: <UploadCloud size={18} />,
      badge: "上传",
      tone: "brand",
      accent: "bg-tint-peach",
      group: "main",
    },
    {
      id: "documents",
      title: "资料列表",
      description: "浏览已导入的文件和文本预览。",
      icon: <FileText size={18} />,
      badge: `${formatWorkspaceCount(documentCount)} 份`,
      tone: "neutral",
      accent: "bg-tint-cream",
      group: "main",
    },
    {
      id: "test",
      title: "问资料",
      description: "用一个真实问题确认资料能否支撑回答。",
      icon: <Search size={18} />,
      badge: testSourceCount == null ? "试问" : `${formatWorkspaceCount(testSourceCount)} 条来源`,
      tone: testSourceCount ? "success" : "brand",
      accent: "bg-tint-lavender",
      group: "main",
    },
    {
      id: "progress",
      title: "处理记录",
      description: "查看导入进度和关键处理步骤。",
      icon: <RefreshCw size={18} />,
      badge: taskActive ? "处理中" : "记录",
      tone: taskActive ? "brand" : "neutral",
      accent: "bg-tint-sky",
      group: taskActive ? "main" : "advanced",
    },
    {
      id: "recovery",
      title: "整理向导",
      description: "资料不可用时，按建议重试或重新整理。",
      icon: <AlertTriangle size={18} />,
      badge: recoveryBadge || "整理",
      tone: recoveryNeedsAttention ? "warning" : "neutral",
      accent: "bg-tint-peach",
      group: recoveryNeedsAttention ? "main" : "advanced",
    },
    {
      id: "diagnostics",
      title: "可用性检查",
      description: "检查资料服务、模型和引用来源。",
      icon: <Database size={18} />,
      badge: diagnosticStatus || "待检查",
      tone: diagnosticStatus.includes("就绪") ? "success" : "warning",
      accent: "bg-tint-yellow",
      group: "advanced",
    },
    {
      id: "quality",
      title: "来源检查",
      description: "用小样本检查资料来源是否稳定。",
      icon: <BarChart3 size={18} />,
      badge: evaluationAvailable ? "有报告" : "未评测",
      tone: evaluationAvailable ? "success" : "neutral",
      accent: "bg-tint-mint",
      group: "advanced",
    },
    {
      id: "settings",
      title: "资料设置",
      description: "调整默认说明、查找方式和整理标记。",
      icon: <SlidersHorizontal size={18} />,
      badge: "设置",
      tone: "neutral",
      accent: "bg-tint-lavender",
      group: "advanced",
    },
    {
      id: "folders",
      title: "同步文件夹",
      description: "资料集中在本地目录时按需同步。",
      icon: <FolderSync size={18} />,
      badge: `${folderCount} 个`,
      tone: folderCount ? "success" : "neutral",
      accent: "bg-tint-mint",
      group: "advanced",
    },
  ];
}

function formatWorkspaceCount(value: number | string | null | undefined) {
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value === "string" && value.trim()) return value;
  return "-";
}
