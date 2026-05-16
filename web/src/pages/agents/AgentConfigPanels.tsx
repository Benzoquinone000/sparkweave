import { BookOpen, FileText, HelpCircle, PenTool, Search, type LucideIcon } from "lucide-react";
import { motion } from "framer-motion";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import type { AgentUiConfig } from "@/lib/types";

const AGENT_ICON_MAP: Record<string, LucideIcon> = {
  BookOpen,
  FileText,
  HelpCircle,
  PenTool,
  Search,
};

const AGENT_TARGETS: Record<string, { href: string; title: string; description: string }> = {
  solve: {
    href: "/chat?capability=deep_solve",
    title: "深度解题",
    description: "复杂题目拆解、推理和校验",
  },
  question: {
    href: "/question",
    title: "题目工坊",
    description: "知识点出题和试卷仿题",
  },
  research: {
    href: "/chat?capability=deep_research",
    title: "深度研究",
    description: "资料检索、引用和报告生成",
  },
  co_writer: {
    href: "/co-writer",
    title: "协作写作",
    description: "润色、扩写、缩写和结构编辑",
  },
  guide: {
    href: "/guide",
    title: "导学空间",
    description: "生成学习路径和交互式页面",
  },
};

export function AgentConfigCard({
  agentType,
  config,
  active,
  onInspect,
}: {
  agentType: string;
  config: AgentUiConfig;
  active: boolean;
  onInspect: () => void;
}) {
  const Icon = AGENT_ICON_MAP[config.icon || ""] ?? HelpCircle;
  const target = AGENT_TARGETS[agentType] ?? {
    href: "/chat",
    title: agentType,
    description: "可用的助教能力入口",
  };
  return (
    <motion.article
      className={`dt-interactive rounded-lg border p-4 transition ${active ? "border-brand-purple-300 bg-tint-lavender" : "border-line bg-white hover:border-brand-purple-300"}`}
      whileHover={{ y: -2 }}
      transition={{ duration: 0.18 }}
    >
      <div className="flex items-start justify-between gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-line bg-white text-brand-purple">
          <Icon size={18} />
        </span>
        <Badge tone="neutral">{config.color || "默认"}</Badge>
      </div>
      <h3 className="mt-4 text-sm font-semibold text-ink">{target.title}</h3>
      <p className="mt-2 min-h-10 text-xs leading-5 text-slate-500">{target.description}</p>
      <div className="mt-4 grid gap-2 border-t border-line pt-3">
        <div className="flex items-center justify-between gap-3 text-xs">
          <span className="shrink-0 text-slate-500">入口</span>
          <span className="min-w-0 truncate font-semibold text-ink">{target.title}</span>
        </div>
        <div className="flex items-center justify-between gap-3 text-xs">
          <span className="shrink-0 text-slate-500">说明</span>
          <span className="min-w-0 truncate text-slate-600">{target.description}</span>
        </div>
      </div>
      <div className="mt-4 grid gap-2">
        <Button tone={active ? "primary" : "secondary"} onClick={onInspect} data-testid={`agent-config-inspect-${agentType}`}>
          查看详情
        </Button>
        <a
          href={target.href}
          className="inline-flex min-h-9 w-full items-center justify-center rounded-lg border border-line bg-white px-3 text-sm font-medium text-slate-700 transition hover:border-brand-purple-300 hover:text-brand-purple"
        >
          打开入口
        </a>
      </div>
    </motion.article>
  );
}

export function AgentConfigDetail({
  agentType,
  config,
  loading,
  error,
}: {
  agentType: string | null;
  config?: AgentUiConfig;
  loading: boolean;
  error: Error | null;
}) {
  if (!agentType) return null;
  const displayTitle = AGENT_TARGETS[agentType]?.title ?? agentType;
  const displayDescription = AGENT_TARGETS[agentType]?.description ?? "可用的学习能力入口";
  const resultLabel = typeof config?.label_key === "string" ? config.label_key : "学习结果";
  const iconLabel = typeof config?.icon === "string" ? config.icon : "默认";
  return (
    <div className="mt-4 border-t border-line pt-4" data-testid="agent-config-detail">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase text-slate-500">能力详情</p>
          <h3 className="mt-1 text-base font-semibold text-ink">{displayTitle}</h3>
          <p className="mt-1 text-sm leading-6 text-slate-500">{displayDescription}</p>
        </div>
        <Badge tone={error ? "danger" : loading ? "brand" : "success"}>{error ? "异常" : loading ? "同步中" : "可用"}</Badge>
      </div>
      {error ? <p className="mt-4 rounded-md border border-red-100 bg-red-50 p-3 text-sm text-red-700">{error.message}</p> : null}
      <div className="mt-4 grid gap-2 md:grid-cols-3">
        <div className="rounded-lg bg-canvas px-3 py-2">
          <p className="text-xs text-slate-500">输出类型</p>
          <p className="mt-1 truncate text-sm font-semibold text-ink">{resultLabel}</p>
        </div>
        <div className="rounded-lg bg-canvas px-3 py-2">
          <p className="text-xs text-slate-500">入口</p>
          <p className="mt-1 truncate text-sm font-semibold text-ink">{displayTitle}</p>
        </div>
        <div className="rounded-lg bg-canvas px-3 py-2">
          <p className="text-xs text-slate-500">图标</p>
          <p className="mt-1 truncate text-sm font-semibold text-ink">{iconLabel}</p>
        </div>
      </div>
    </div>
  );
}
