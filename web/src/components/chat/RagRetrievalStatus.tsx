import { CheckCircle2, Database, FileSearch, GitBranch, Loader2, SearchCheck, ShieldCheck } from "lucide-react";
import { useMemo, type ReactNode } from "react";

import { Badge } from "@/components/ui/Badge";
import { extractRagLiveStatus, type RagLiveStatus } from "@/lib/ragLiveStatus";
import type { StreamEvent } from "@/lib/types";

export function RagRetrievalStatus({
  events,
  className = "",
}: {
  events: StreamEvent[];
  className?: string;
}) {
  const status = useMemo(() => extractRagLiveStatus(events), [events]);
  if (!status) return null;

  const tone = status.phase === "error" ? "danger" : status.fallback ? "warning" : status.phase === "complete" ? "success" : "brand";
  const Icon = status.phase === "complete" ? CheckCircle2 : status.phase === "multi_search" ? GitBranch : FileSearch;

  return (
    <section
      className={`dt-rag-flow ${status.running ? "dt-rag-flow-active" : ""} rounded-lg border border-line bg-canvas px-3 py-2 ${className}`}
      data-testid="rag-retrieval-status"
    >
      <div className="flex items-start gap-2">
        <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-line bg-white text-brand-purple">
          {status.running ? <Loader2 size={15} className="animate-spin" /> : <Icon size={15} />}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-ink">{status.title}</p>
            <Badge tone={tone}>{status.phase === "complete" ? "已完成" : status.phase === "error" ? "需检查" : "进行中"}</Badge>
            {status.subqueryCount && status.subqueryCount > 1 ? <MiniBadge>多路查找</MiniBadge> : null}
            {status.transformed ? <MiniBadge>补充关键词</MiniBadge> : null}
          </div>
          <p className="mt-1 line-clamp-2 text-xs leading-5 text-steel">{status.detail}</p>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {status.query ? <Fact icon={<FileSearch size={12} />} label={status.query} /> : null}
            {status.kbName ? <Fact icon={<Database size={12} />} label={status.kbName} /> : null}
            {typeof status.sourceCount === "number" ? <Fact icon={<SearchCheck size={12} />} label={`${status.sourceCount} 条来源`} /> : null}
            {qualityLabel(status) ? <Fact icon={<ShieldCheck size={12} />} label={qualityLabel(status)} warning={status.qualityStatus === "weak"} /> : null}
          </div>
        </div>
      </div>
    </section>
  );
}

function qualityLabel(status: RagLiveStatus) {
  if (status.qualityStatus === "weak") return "来源偏弱";
  if (status.qualityStatus === "sufficient") return "来源可用";
  if (typeof status.qualityScore === "number") return `来源 ${formatPercent(status.qualityScore)}`;
  if (status.repaired) return "已补强";
  if (status.fallback) return "已稳妥重试";
  return "";
}

function formatPercent(value: number) {
  const normalized = value > 1 ? value : value * 100;
  return `${Math.round(normalized)}%`;
}

function MiniBadge({ children }: { children: string }) {
  return <span className="rounded-md border border-line bg-white px-1.5 py-0.5 text-[11px] font-medium text-steel">{children}</span>;
}

function Fact({
  icon,
  label,
  warning,
}: {
  icon: ReactNode;
  label: string;
  warning?: boolean;
}) {
  return (
    <span
      className={`dt-rag-fact inline-flex min-h-6 max-w-full items-center gap-1 rounded-md border bg-white px-1.5 text-[11px] leading-5 ${
        warning ? "border-amber-200 text-amber-700" : "border-line text-slate-500"
      }`}
      title={label}
    >
      <span className="shrink-0">{icon}</span>
      <span className="truncate">{label}</span>
    </span>
  );
}
