import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Database,
  FileText,
  FolderSync,
} from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

import type { KnowledgeWorkspace } from "./types";
import type { KnowledgeNextStep } from "./KnowledgeNextStepModel";

export function KnowledgeNextStepStrip({
  step,
  onNavigate,
}: {
  step: KnowledgeNextStep;
  onNavigate: (workspace: KnowledgeWorkspace) => void;
}) {
  const Icon = step.primaryIcon;
  const toneClass =
    step.tone === "success"
      ? "bg-tint-mint"
      : step.tone === "warning"
        ? "bg-tint-yellow"
        : step.tone === "brand"
          ? "bg-tint-lavender"
          : "bg-surface";

  return (
    <div className={`mt-5 rounded-lg ${toneClass} p-3`} data-testid="knowledge-active-next-step">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-ink">下一步：{step.title}</p>
            <Badge tone={step.tone}>{step.badge}</Badge>
          </div>
          <p className="mt-1 max-w-2xl text-xs leading-5 text-slate-600">{step.summary}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            tone="primary"
            className="min-h-9 px-3 text-xs"
            type="button"
            onClick={() => onNavigate(step.primaryWorkspace)}
          >
            <Icon size={15} />
            {step.primaryLabel}
          </Button>
          {step.secondaryWorkspace && step.secondaryLabel ? (
            <Button
              tone="secondary"
              className="min-h-9 bg-white px-3 text-xs"
              type="button"
              onClick={() => onNavigate(step.secondaryWorkspace!)}
            >
              <SecondaryStepIcon workspace={step.secondaryWorkspace} />
              {step.secondaryLabel}
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function SecondaryStepIcon({ workspace }: { workspace: KnowledgeWorkspace }) {
  if (workspace === "documents") return <FileText size={15} />;
  if (workspace === "diagnostics") return <Database size={15} />;
  if (workspace === "folders") return <FolderSync size={15} />;
  if (workspace === "quality") return <BarChart3 size={15} />;
  if (workspace === "recovery") return <AlertTriangle size={15} />;
  return <ArrowRight size={15} />;
}
