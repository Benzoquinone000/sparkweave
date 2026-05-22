import { motion } from "framer-motion";
import { ArrowRight, Database, FileText, Loader2, MessageSquareText, MoreHorizontal, RefreshCw, Star, Trash2, UploadCloud } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

import { ConfigFact } from "./ConfigFact";
import { formatProgressStage } from "./format";
import type { KnowledgeNextStep } from "./KnowledgeNextStepModel";
import type { KnowledgeWorkspace } from "./types";
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
      <div className="min-w-0">
        <Badge tone={activeKb ? "brand" : "neutral"}>{activeKb || "未选择资料库"}</Badge>
        <h2 className="mt-3 text-xl font-semibold text-ink">{activeKb || "先放入一份资料"}</h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
          {activeKb
            ? "上传资料后直接提问，处理进度会自动汇总在这里。"
            : "上传 PDF、Markdown、文本或代码文件后，系统会自动准备可引用内容。"}
        </p>
      </div>
      <details className="shrink-0 rounded-lg border border-line bg-white px-2.5 py-2 [&>summary::-webkit-details-marker]:hidden">
        <summary className="dt-interactive flex cursor-pointer items-center gap-2 text-xs font-medium text-slate-600">
          <MoreHorizontal size={15} />
          管理
        </summary>
        <div className="mt-2 flex flex-col gap-2 sm:w-36">
          <Button
            tone="secondary"
            className="min-h-8 justify-start px-2 text-xs"
            disabled={!activeKb || reindexing}
            onClick={onReindex}
            data-testid="knowledge-active-reindex"
          >
            {reindexing ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            重新整理资料
          </Button>
          <Button
            tone="secondary"
            className="min-h-8 justify-start px-2 text-xs"
            disabled={!activeKb || diagnosing}
            onClick={onDiagnose}
            data-testid="knowledge-active-diagnose"
          >
            {diagnosing ? <Loader2 size={14} className="animate-spin" /> : <Database size={14} />}
            检查连接
          </Button>
          <Button
            tone="secondary"
            className="min-h-8 justify-start px-2 text-xs"
            data-testid="knowledge-active-set-default"
            disabled={!activeKb || defaultActive || settingDefault}
            onClick={onSetDefault}
          >
            <Star size={14} />
            设为默认
          </Button>
          <Button
            tone="danger"
            className="min-h-8 justify-start px-2 text-xs"
            data-testid="knowledge-active-delete"
            disabled={!activeKb || removing}
            onClick={onDelete}
          >
            <Trash2 size={14} />
            删除
          </Button>
        </div>
      </details>
    </div>
  );
}

export function KnowledgeStartPanel({
  activeKb,
  nextStep,
  documentCount,
  vectorCount,
  progressMessage,
  progressPercent,
  taskActive,
  recoveryNeedsAttention,
  onNavigate,
}: {
  activeKb: string;
  nextStep: KnowledgeNextStep | null;
  documentCount: number | string | null | undefined;
  vectorCount: number | string | null | undefined;
  progressMessage: string;
  progressPercent: number;
  taskActive: boolean;
  recoveryNeedsAttention: boolean;
  onNavigate: (workspace: KnowledgeWorkspace) => void;
}) {
  const documents = toFiniteNumber(documentCount);
  const vectors = toFiniteNumber(vectorCount);
  const ready = Boolean(activeKb && documents !== null && documents > 0 && (vectors === null || vectors > 0) && !taskActive && !recoveryNeedsAttention);
  const statusTone = recoveryNeedsAttention ? "warning" : ready ? "success" : taskActive ? "brand" : "neutral";
  const statusLabel = recoveryNeedsAttention ? "需处理" : ready ? "可提问" : taskActive ? "处理中" : "待上传";
  const secondaryWorkspace: KnowledgeWorkspace = taskActive ? "progress" : documents ? "documents" : "progress";
  const uploadPrimary = !ready;

  if (!activeKb) {
    return (
      <div className="mt-5 rounded-lg border border-dashed border-line bg-canvas p-4" data-testid="knowledge-user-start-panel">
        <p className="text-sm font-semibold text-ink">先创建一个资料库</p>
        <p className="mt-1 text-sm leading-6 text-slate-500">左侧点击“新建”，选择第一批课程资料，完成后就能围绕资料提问。</p>
        <a
          href="/knowledge/create"
          className="dt-interactive mt-4 inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-ink px-4 text-sm font-medium text-white"
        >
          <UploadCloud size={16} />
          新建资料库
        </a>
      </div>
    );
  }

  return (
    <div className="mt-5 rounded-lg border border-line bg-[#fbfbfa] p-4" data-testid="knowledge-user-start-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-ink">从这里开始</p>
            <Badge tone={statusTone}>{statusLabel}</Badge>
          </div>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-500">
            {ready
              ? "资料已经准备好。你可以直接提问，也可以继续补充新的材料。"
              : progressMessage || "先上传资料，系统会自动完成解析和整理。"}
          </p>
        </div>
        <span className="rounded-lg border border-line bg-white px-3 py-2 text-xs font-medium text-slate-600">{progressPercent}%</span>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-3">
        <button
          type="button"
          className={`dt-interactive flex min-h-[74px] items-start gap-3 rounded-lg border p-3 text-left transition ${
            uploadPrimary
              ? "border-brand-purple-300 bg-tint-lavender hover:bg-white"
              : "border-line bg-white hover:border-brand-purple-300 hover:bg-canvas"
          }`}
          onClick={() => onNavigate("upload")}
          data-testid="knowledge-primary-upload"
        >
          <span
            className={`flex size-8 shrink-0 items-center justify-center rounded-md ${
              uploadPrimary ? "bg-white text-brand-purple" : "bg-tint-peach text-brand-orange"
            }`}
          >
            <UploadCloud size={17} />
          </span>
          <span>
            <span className="block text-sm font-semibold text-ink">上传资料</span>
            <span className="mt-1 block text-xs leading-5 text-slate-500">
              {uploadPrimary ? "先补充资料，系统会自动整理。" : "课件、笔记、论文或代码。"}
            </span>
          </span>
        </button>
        {ready ? (
          <a
            href={buildKnowledgeChatHref(activeKb)}
            className="dt-interactive flex min-h-[74px] items-start gap-3 rounded-lg border border-brand-purple-300 bg-tint-lavender p-3 text-left transition hover:bg-white"
            data-testid="knowledge-primary-ask"
          >
            <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-white text-brand-purple">
              <MessageSquareText size={17} />
            </span>
            <span>
              <span className="block text-sm font-semibold text-ink">问资料</span>
              <span className="mt-1 block text-xs leading-5 text-slate-500">打开问答并带上当前资料库。</span>
            </span>
          </a>
        ) : (
          <button
            type="button"
            disabled
            className="flex min-h-[74px] items-start gap-3 rounded-lg border border-line bg-white p-3 text-left opacity-70"
            data-testid="knowledge-primary-ask"
            title="资料整理完成后可用"
          >
            <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-canvas text-slate-400">
              <MessageSquareText size={17} />
            </span>
            <span>
              <span className="block text-sm font-semibold text-slate-500">问资料</span>
              <span className="mt-1 block text-xs leading-5 text-slate-500">资料整理完成后再提问。</span>
            </span>
          </button>
        )}
        <button
          type="button"
          className="dt-interactive flex min-h-[74px] items-start gap-3 rounded-lg border border-line bg-white p-3 text-left hover:border-brand-purple-300 hover:bg-canvas"
          onClick={() => onNavigate(secondaryWorkspace)}
          data-testid="knowledge-primary-records"
        >
          <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-tint-sky text-brand-blue">
            <FileText size={17} />
          </span>
          <span>
            <span className="block text-sm font-semibold text-ink">{taskActive ? "看处理进度" : "查看资料"}</span>
            <span className="mt-1 block text-xs leading-5 text-slate-500">{taskActive ? "确认是否已经处理完成。" : "浏览已导入内容。"}</span>
          </span>
        </button>
      </div>

      {nextStep ? (
        <button
          type="button"
          className="dt-interactive mt-3 flex w-full items-center justify-between gap-3 rounded-lg border border-line bg-white px-3 py-2 text-left text-xs text-slate-600 hover:border-brand-purple-300"
          onClick={() => onNavigate(nextStep.primaryWorkspace)}
          data-testid="knowledge-active-next-step"
        >
          <span className="min-w-0">
            <span className="font-semibold text-ink">当前建议：{nextStep.title}</span>
            <span className="ml-2 text-slate-500">{nextStep.summary}</span>
          </span>
          <ArrowRight size={15} className="shrink-0 text-brand-purple" />
        </button>
      ) : null}
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
      <ConfigFact label="引用方式" value={activeSearchLabel} />
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
          <p className="text-sm font-semibold text-ink">资料状态</p>
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

function buildKnowledgeChatHref(activeKb: string) {
  const params = new URLSearchParams({ capability: "chat", kb: activeKb });
  return `/chat?${params.toString()}`;
}

function toFiniteNumber(value: number | string | null | undefined) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
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
    <details className="mt-4 rounded-lg border border-line bg-canvas p-3 [&>summary::-webkit-details-marker]:hidden" data-testid="knowledge-active-summary-panel">
      <summary className="dt-interactive flex cursor-pointer flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-semibold text-ink">资料细节</span>
        <Badge tone="neutral">{summaryItems.length} 项</Badge>
      </summary>
      <div className="mt-3 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
        {summaryItems.map((item) => (
          <ConfigFact key={item.key} label={item.label} value={item.value} />
        ))}
      </div>
    </details>
  );
}
