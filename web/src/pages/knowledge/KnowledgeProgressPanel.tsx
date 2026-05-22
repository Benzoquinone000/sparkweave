import { ChevronLeft, Loader2, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import type { KnowledgeTaskStatusResponse } from "@/lib/types";

import {
  KnowledgeProgressLogs,
  KnowledgeProgressMeter,
  KnowledgeProgressMilestones,
  KnowledgeProgressStatusSummary,
} from "./KnowledgeProgressPanels";
import { formatWsStatus, type KnowledgeWsStatus } from "./progressFormat";

export function KnowledgeProgressPanel({
  visible,
  activeKb,
  progressStage,
  progressMessage,
  progressPercent,
  wsStatus,
  taskMilestones,
  taskLogs,
  taskStatus,
  taskStatusLoading,
  clearing,
  onBack,
  onClear,
}: {
  visible: boolean;
  activeKb: string;
  progressStage: string;
  progressMessage: string;
  progressPercent: number;
  wsStatus: KnowledgeWsStatus;
  taskMilestones: string[];
  taskLogs: string[];
  taskStatus?: KnowledgeTaskStatusResponse | null;
  taskStatusLoading?: boolean;
  clearing: boolean;
  onBack?: () => void;
  onClear: () => void;
}) {
  return (
    <section
      className={visible ? "order-6 rounded-lg border border-line bg-white p-3" : "hidden"}
      data-testid="knowledge-progress-details"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-tint-lavender px-3 py-3" data-testid="knowledge-progress-toggle">
        <div>
          <h2 className="text-base font-semibold text-ink">处理进度</h2>
          <p className="mt-1 text-sm text-slate-500">导入资料后查看处理过程。</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {onBack ? (
            <Button
              tone="secondary"
              className="min-h-9 px-3 text-xs"
              type="button"
              onClick={onBack}
              data-testid="knowledge-progress-back"
            >
              <ChevronLeft size={14} />
              返回概览
            </Button>
          ) : null}
          <Badge tone="brand">{progressStage}</Badge>
          <Badge tone={wsStatus === "live" ? "success" : wsStatus === "error" ? "danger" : "neutral"}>
            {formatWsStatus(wsStatus)}
          </Badge>
        </div>
      </div>
      <div className="mt-4 border-t border-line pt-4">
        <div className="mb-4 flex justify-end">
          <Button
            tone="secondary"
            className="min-h-9 text-xs"
            type="button"
            disabled={!activeKb || clearing}
            onClick={onClear}
            data-testid="knowledge-progress-clear"
          >
            {clearing ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
            清理进度
          </Button>
        </div>
        <KnowledgeProgressStatusSummary taskStatus={taskStatus} taskStatusLoading={taskStatusLoading} />
        <KnowledgeProgressMeter progressMessage={progressMessage} progressPercent={progressPercent} />
      </div>
      <KnowledgeProgressMilestones taskMilestones={taskMilestones} />
      <KnowledgeProgressLogs taskLogs={taskLogs} />
    </section>
  );
}
