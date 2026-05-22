import { AnimatePresence, motion } from "framer-motion";
import { Loader2, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import type { RagDiagnostic, RagPreflight } from "@/lib/types";

import {
  formatDiagnosticError,
  formatRagDiagnosticStatus,
  formatRagDiagnosticSummary,
  ragDiagnosticTone,
} from "./format";
import {
  RagDiagnosticChecksPanel,
  RagPreflightFacts,
  RagReadinessFacts,
} from "./KnowledgeDiagnosticPanels";

export function KnowledgeDiagnosticsPanel({
  activeKb,
  report,
  error,
  fetching,
  visible,
  preflight,
  preflightError,
  preflightFetching,
  reindexing,
  onRefresh,
  onOpenRecovery,
  onOpenTest,
  onReindex,
}: {
  activeKb: string;
  report?: RagDiagnostic;
  error: unknown;
  fetching: boolean;
  visible: boolean;
  preflight?: RagPreflight;
  preflightError: unknown;
  preflightFetching: boolean;
  reindexing: boolean;
  onRefresh: () => void;
  onOpenRecovery: () => void;
  onOpenTest: () => void;
  onReindex: () => void;
}) {
  return (
    <AnimatePresence initial={false}>
      {visible ? (
        <motion.div
          key={`${activeKb}-rag-diagnostic`}
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.18 }}
          className="mt-4 rounded-lg border border-line bg-canvas p-3"
          data-testid="knowledge-active-diagnostic-panel"
        >
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <p className="text-sm font-semibold text-ink">连接检查</p>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                {fetching ? "正在检查资料连接、引用片段和模型配置..." : error ? formatDiagnosticError(error) : formatRagDiagnosticSummary(report)}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                tone="secondary"
                className="min-h-8 px-3 text-xs"
                disabled={fetching || preflightFetching}
                onClick={onRefresh}
                data-testid="knowledge-diagnostics-refresh"
              >
                {fetching || preflightFetching ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                重新检查
              </Button>
              <Badge tone={ragDiagnosticTone(report?.status, Boolean(error))}>
                {fetching ? "检查中" : formatRagDiagnosticStatus(report?.status, Boolean(error))}
              </Badge>
            </div>
          </div>

          <RagDiagnosticChecksPanel report={report} />
          {report ? <RagReadinessFacts report={report} /> : null}
          <RagPreflightFacts
            preflight={preflight}
            error={preflightError}
            fetching={preflightFetching}
            reindexing={reindexing}
            onOpenRecovery={onOpenRecovery}
            onOpenTest={onOpenTest}
            onReindex={onReindex}
          />
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
