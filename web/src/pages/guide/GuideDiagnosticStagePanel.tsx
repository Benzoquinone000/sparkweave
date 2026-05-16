import { Badge } from "@/components/ui/Badge";
import type { GuideV2Diagnostic, GuideV2DiagnosticAnswer } from "@/lib/types";
import { GuideDiagnosticPanel } from "./GuideDiagnosticPanel";

export function GuideDiagnosticStagePanel({
  highlightedSectionId,
  diagnostic,
  loading,
  submitting,
  disabled,
  onSubmit,
}: {
  highlightedSectionId: string | null;
  diagnostic: GuideV2Diagnostic | null;
  loading: boolean;
  submitting: boolean;
  disabled: boolean;
  onSubmit: (answers: GuideV2DiagnosticAnswer[]) => void;
}) {
  return (
    <>
      <section
        id="guide-diagnostic-section"
        className={`rounded-lg border bg-white p-5 shadow-sm transition-all duration-500 ${
          highlightedSectionId === "guide-diagnostic-section"
            ? "border-brand-purple ring-2 ring-brand-purple-300"
            : "border-line"
        }`}
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <Badge tone="brand">先做这一件事</Badge>
            <h2 className="mt-3 text-xl font-semibold text-ink">先回答几道小题，再开始学习</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              系统会先判断你更像是概念没站稳、步骤断了，还是只是缺一点练习，然后再安排更合适的下一步。
            </p>
          </div>
          <Badge tone="warning">约 2 分钟</Badge>
        </div>
      </section>
      <GuideDiagnosticPanel
        diagnostic={diagnostic}
        loading={loading}
        submitting={submitting}
        disabled={disabled}
        onSubmit={onSubmit}
      />
    </>
  );
}
