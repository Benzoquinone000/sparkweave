import { Volume2 } from "lucide-react";
import { useMemo } from "react";

import { PersonalizationBrief } from "@/components/results/PersonalizationBrief";
import { ResourceEvidenceButton } from "@/components/results/ResourceEvidenceButton";
import { Badge } from "@/components/ui/Badge";
import type { AudioNarrationResult } from "@/lib/types";

function formatSampleRate(sampleRate?: number) {
  if (!sampleRate || !Number.isFinite(sampleRate)) return "";
  return `${Math.round(sampleRate / 1000)} kHz`;
}

export function AudioNarrationViewer({
  result,
  embedded = false,
}: {
  result: AudioNarrationResult;
  embedded?: boolean;
}) {
  const audio = result.audio;
  const evidencePayload = useMemo(() => {
    const fingerprint = audio?.asset_url || audio?.filename || result.script_text || result.response || "audio";
    return {
      source: "resource",
      source_id: `audio:${fingerprint}`,
      actor: "learner",
      verb: "viewed",
      object_type: "resource",
      object_id: `audio:${fingerprint}`,
      title: "语音讲解",
      summary: result.script_text || result.response || "",
      resource_type: "audio",
      confidence: 0.5,
      weight: 0.55,
      metadata: {
        voice: audio?.voice || "",
        sample_rate: audio?.sample_rate ?? null,
        style_hint: result.style_hint || "",
        learner_profile_hints: result.learner_profile_hints ?? {},
      },
    };
  }, [
    audio?.asset_url,
    audio?.filename,
    audio?.sample_rate,
    audio?.voice,
    result.learner_profile_hints,
    result.response,
    result.script_text,
    result.style_hint,
  ]);

  if (!audio?.asset_url) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
        语音讲解已生成，但暂时没有可播放的音频地址。
      </div>
    );
  }

  return (
    <div
      className={embedded ? "" : "rounded-lg border border-line bg-canvas p-3"}
      data-testid="audio-narration-viewer"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="brand">语音讲解</Badge>
        {audio.voice ? <Badge tone="neutral">{audio.voice}</Badge> : null}
        {formatSampleRate(audio.sample_rate) ? <Badge tone="neutral">{formatSampleRate(audio.sample_rate)}</Badge> : null}
      </div>

      {result.response ? <p className="mt-3 text-sm leading-6 text-charcoal">{result.response}</p> : null}
      <PersonalizationBrief hints={result.learner_profile_hints} styleHint={result.style_hint} className="mt-3" />

      <div className="mt-4 rounded-lg border border-line bg-white p-3">
        <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-ink">
          <Volume2 size={16} className="text-brand-purple" />
          点击播放，先听一遍
        </div>
        <audio controls preload="none" className="w-full" src={audio.asset_url} />
      </div>

      <div className="mt-3">
        <ResourceEvidenceButton payload={evidencePayload} testId="audio-narration-evidence-button" />
      </div>

      {result.script_text ? (
        <details className="mt-3 rounded-lg border border-line bg-white p-3">
          <summary className="cursor-pointer text-sm font-medium text-ink">查看讲解稿</summary>
          <p className="mt-2 text-sm leading-6 text-charcoal">{result.script_text}</p>
        </details>
      ) : null}
    </div>
  );
}
