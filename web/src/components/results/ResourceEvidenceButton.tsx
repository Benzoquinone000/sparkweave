import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { appendLearningEffectEvent } from "@/lib/api";
import { invalidateLearningQueries } from "@/lib/queryInvalidation";
import type { LearnerEvidenceEvent } from "@/lib/types";

type ResourceEvidencePayload = Partial<LearnerEvidenceEvent> & {
  concept_ids?: string[];
  result?: Record<string, unknown>;
  signals?: Record<string, unknown>;
};

export function ResourceEvidenceButton({
  payload,
  label = "有帮助，记入画像",
  recordedLabel = "已记入学习证据",
  testId,
}: {
  payload: ResourceEvidencePayload;
  label?: string;
  recordedLabel?: string;
  testId?: string;
}) {
  const queryClient = useQueryClient();
  const [recording, setRecording] = useState(false);
  const [recorded, setRecorded] = useState(false);
  const [error, setError] = useState("");

  const record = async () => {
    if (recording || recorded) return;
    setRecording(true);
    setError("");
    try {
      await appendLearningEffectEvent({
        ...payload,
        source: payload.source || "resource",
        actor: payload.actor || "learner",
        verb: payload.verb || "viewed",
        object_type: payload.object_type || "resource",
      });
      setRecorded(true);
      invalidateLearningQueries(queryClient);
    } catch (recordError) {
      setError(recordError instanceof Error ? recordError.message : "学习证据记录失败");
    } finally {
      setRecording(false);
    }
  };

  if (recorded) {
    return (
      <span
        className="inline-flex min-h-8 items-center gap-1 rounded-md border border-line bg-canvas px-2 text-xs text-slate-500"
        data-testid={testId ? `${testId}-recorded` : undefined}
      >
        <CheckCircle2 size={13} className="text-brand-purple" />
        {recordedLabel}
      </span>
    );
  }

  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <Button
        tone="quiet"
        className="min-h-8 px-2 text-xs"
        onClick={() => void record()}
        disabled={recording}
        data-testid={testId}
      >
        {recording ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
        {label}
      </Button>
      {error ? <span className="text-xs text-brand-red">{error}</span> : null}
    </span>
  );
}
