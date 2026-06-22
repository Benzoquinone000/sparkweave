import type { GuideV2Diagnostic, GuideV2DiagnosticAnswer } from "@/lib/types";
import { GuideDiagnosticPanel } from "./GuideDiagnosticPanel";

export function GuideDiagnosticStagePanel({
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
    <GuideDiagnosticPanel
      diagnostic={diagnostic}
      loading={loading}
      submitting={submitting}
      disabled={disabled}
      onSubmit={onSubmit}
    />
  );
}
