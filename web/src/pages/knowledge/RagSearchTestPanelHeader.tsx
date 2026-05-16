import { ChevronLeft } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

import {
  formatRagTestPanelDescription,
  formatRagTestPanelTitle,
  type RagTestPanelView,
} from "./ragTestConfig";

type RagSearchHeaderStatus = {
  tone?: "neutral" | "success" | "warning" | "danger" | "brand";
  shortLabel?: string;
} | null;

export function RagSearchTestPanelHeader({
  panelView,
  showResultNavigation,
  resultStatus,
  sourceCount,
  onBackToSummary,
  onOpenSetup,
}: {
  panelView: RagTestPanelView;
  showResultNavigation: boolean;
  resultStatus: RagSearchHeaderStatus;
  sourceCount: number;
  onBackToSummary: () => void;
  onOpenSetup: () => void;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 className="text-base font-semibold text-ink">{formatRagTestPanelTitle(panelView)}</h2>
        <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-500">
          {formatRagTestPanelDescription(panelView)}
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        {showResultNavigation && panelView !== "summary" ? (
          <Button tone="secondary" className="min-h-9 px-3 text-xs" type="button" onClick={onBackToSummary}>
            <ChevronLeft size={15} />
            返回结果
          </Button>
        ) : null}
        {showResultNavigation ? (
          <Button tone="secondary" className="min-h-9 px-3 text-xs" type="button" onClick={onOpenSetup}>
            <ChevronLeft size={15} />
            调整检索
          </Button>
        ) : null}
        {resultStatus ? (
          <Badge tone={resultStatus.tone ?? "neutral"}>{resultStatus.shortLabel ?? `${sourceCount} 条证据`}</Badge>
        ) : null}
      </div>
    </div>
  );
}
