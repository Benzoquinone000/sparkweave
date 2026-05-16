import { motion } from "framer-motion";
import { Database, Loader2, RefreshCw, Star, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

import { ConfigFact } from "./ConfigFact";
import { formatProgressStage } from "./format";
import { formatWsStatus, type KnowledgeWsStatus } from "./progressFormat";
import { formatOptionalCount } from "./ragUtils";

export type KnowledgeSummaryItem = {
  key: string;
  label: string;
  value: string;
};

export function KnowledgeOverviewHeader({
  activeKb,
  reindexing,
  diagnosing,
  defaultActive,
  settingDefault,
  removing,
  onReindex,
  onDiagnose,
  onSetDefault,
  onDelete,
}: {
  activeKb: string;
  reindexing: boolean;
  diagnosing: boolean;
  defaultActive: boolean;
  settingDefault: boolean;
  removing: boolean;
  onReindex: () => void;
  onDiagnose: () => void;
  onSetDefault: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <Badge tone={activeKb ? "brand" : "neutral"}>{activeKb || "未选择资料库"}</Badge>
        <h2 className="mt-3 text-xl font-semibold text-ink">{activeKb || "先创建或选择资料库"}</h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
          {activeKb
            ? "这里展示当前资料库的核心状态。复杂配置先收起来，日常只需要上传资料、等待索引完成。"
            : "上传 PDF、Markdown、文本或代码文件后，系统会自动建立索引。"}
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button
          tone="secondary"
          className="min-h-9 text-xs"
          disabled={!activeKb || reindexing}
          onClick={onReindex}
          data-testid="knowledge-active-reindex"
        >
          {reindexing ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          重建索引
        </Button>
        <Button
          tone="secondary"
          className="min-h-9 text-xs"
          disabled={!activeKb || diagnosing}
          onClick={onDiagnose}
          data-testid="knowledge-active-diagnose"
        >
          {diagnosing ? <Loader2 size={14} className="animate-spin" /> : <Database size={14} />}
          检查连接
        </Button>
        <Button
          tone="secondary"
          className="min-h-9 text-xs"
          data-testid="knowledge-active-set-default"
          disabled={!activeKb || defaultActive || settingDefault}
          onClick={onSetDefault}
        >
          <Star size={14} />
          设为默认
        </Button>
        <Button
          tone="danger"
          className="min-h-9 text-xs"
          data-testid="knowledge-active-delete"
          disabled={!activeKb || removing}
          onClick={onDelete}
        >
          <Trash2 size={14} />
          删除
        </Button>
      </div>
    </div>
  );
}

export function KnowledgeOverviewFacts({
  activeStatus,
  activeFileCount,
  activeDocumentCount,
  activeSearchLabel,
}: {
  activeStatus: string;
  activeFileCount?: number;
  activeDocumentCount?: number;
  activeSearchLabel: string;
}) {
  return (
    <div className="mt-5 grid gap-3 sm:grid-cols-4">
      <ConfigFact label="状态" value={formatProgressStage(activeStatus)} tone={activeStatus === "error" ? "warning" : "success"} />
      <ConfigFact label="文件" value={formatOptionalCount(activeFileCount)} />
      <ConfigFact label="文档" value={formatOptionalCount(activeDocumentCount)} />
      <ConfigFact label="检索" value={activeSearchLabel} />
    </div>
  );
}

export function KnowledgeIndexStatusCard({
  progressMessage,
  progressPercent,
  progressStage,
  wsStatus,
  taskActive,
}: {
  progressMessage: string;
  progressPercent: number;
  progressStage: string;
  wsStatus: KnowledgeWsStatus;
  taskActive: boolean;
}) {
  return (
    <div className="mt-5 rounded-lg border border-line bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-ink">索引状态</p>
          <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{progressMessage}</p>
        </div>
        <Badge tone={progressPercent >= 100 ? "success" : taskActive ? "brand" : "neutral"}>{progressStage}</Badge>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-sm bg-white">
        <motion.div
          className="h-full rounded-sm bg-brand-purple"
          initial={false}
          animate={{ width: `${progressPercent}%` }}
          transition={{ duration: 0.35, ease: "easeOut" }}
        />
      </div>
      <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
        <span>{formatWsStatus(wsStatus)}</span>
        <span>{progressPercent}%</span>
      </div>
    </div>
  );
}

export function KnowledgeOverviewSummaryPanel({
  summaryItems,
  workspace,
}: {
  summaryItems: KnowledgeSummaryItem[];
  workspace: string;
}) {
  if (!summaryItems.length || workspace !== "overview") return null;

  return (
    <div className="mt-4 rounded-lg border border-line bg-canvas p-3" data-testid="knowledge-active-summary-panel">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold text-ink">索引摘要</p>
        <Badge tone="neutral">{summaryItems.length} 项</Badge>
      </div>
      <div className="mt-3 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
        {summaryItems.map((item) => (
          <ConfigFact key={item.key} label={item.label} value={item.value} />
        ))}
      </div>
    </div>
  );
}
