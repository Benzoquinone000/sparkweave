import { Loader2, Wrench } from "lucide-react";

import { Button } from "@/components/ui/Button";
import type { KnowledgeHealth } from "@/lib/types";

import { knowledgeProviderLabel } from "./format";

export function KnowledgeStatusStrip({
  count,
  defaultName,
  configCount,
  staleConfigCount = 0,
  rag,
  refreshing,
  error,
  cleaning = false,
  onCleanConfigs,
}: {
  count: number;
  defaultName: string;
  configCount: string | number;
  staleConfigCount?: number;
  rag?: KnowledgeHealth["rag"];
  refreshing: boolean;
  error: boolean;
  cleaning?: boolean;
  onCleanConfigs?: () => void;
}) {
  const ragOk = ["ok", "configured"].includes(String(rag?.status || "").toLowerCase());
  const items = [
    { label: "资料库", value: String(count), ok: count > 0 },
    { label: "默认", value: defaultName, ok: defaultName !== "未设置" },
    { label: "策略", value: String(configCount), ok: String(configCount) !== "0" },
    { label: "引擎", value: rag?.provider ? knowledgeProviderLabel(rag.provider) : "读取中", ok: ragOk },
    { label: "索引", value: refreshing ? "刷新中" : error ? "需检查" : "就绪", ok: !error },
  ];
  return (
    <section className="px-1" data-testid="knowledge-status-strip">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
        {items.map((item) => (
          <div key={item.label} className="flex min-w-0 items-center gap-1.5 text-xs">
            <span className={`h-1.5 w-1.5 shrink-0 rounded-sm ${item.ok ? "bg-emerald-500" : "bg-slate-300"}`} />
            <span className="shrink-0 text-slate-500">{item.label}</span>
            <span className="max-w-[190px] truncate font-medium text-ink">{item.value}</span>
          </div>
        ))}
        </div>
        {staleConfigCount > 0 && onCleanConfigs ? (
          <Button
            tone="secondary"
            className="min-h-8 rounded-md px-2.5 text-xs"
            onClick={onCleanConfigs}
            disabled={cleaning}
            data-testid="knowledge-clean-stale-configs"
          >
            {cleaning ? <Loader2 size={14} className="animate-spin" /> : <Wrench size={14} />}
            清理失效记录
          </Button>
        ) : null}
      </div>
    </section>
  );
}
