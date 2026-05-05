import { Code2, Image as ImageIcon, Timer, Video } from "lucide-react";
import { useMemo, useState } from "react";

import { AudioNarrationViewer } from "@/components/results/AudioNarrationViewer";
import { PersonalizationBrief } from "@/components/results/PersonalizationBrief";
import { ResourceEvidenceButton } from "@/components/results/ResourceEvidenceButton";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { apiUrl } from "@/lib/api";
import { evidenceFingerprint } from "@/lib/evidence";
import type { MathAnimatorResult } from "@/lib/types";

function assetUrl(url: string) {
  return url.startsWith("http://") || url.startsWith("https://") ? url : apiUrl(url);
}

export function MathAnimatorViewer({ result }: { result: MathAnimatorResult }) {
  const [showCode, setShowCode] = useState(false);
  const artifacts = useMemo(() => result.artifacts ?? [], [result.artifacts]);
  const videos = useMemo(() => artifacts.filter((item) => item.type === "video"), [artifacts]);
  const images = useMemo(() => artifacts.filter((item) => item.type === "image"), [artifacts]);
  const hasNarratedVideo = Boolean(result.audio_narration?.video?.asset_url);
  const evidencePayload = useMemo(() => {
    const primaryArtifact = artifacts[0];
    const basis = primaryArtifact?.url || result.code?.content || result.response || "math-animation";
    const fingerprint = evidenceFingerprint(basis);
    const resourceType = videos.length ? "video" : "visual";
    return {
      source: "resource",
      source_id: `math_animator:${fingerprint}`,
      actor: "learner",
      verb: "viewed",
      object_type: "resource",
      object_id: primaryArtifact?.url || `math_animator:${fingerprint}`,
      title: videos.length ? "数学动画视频" : "数学动画图解",
      summary: result.response || result.render?.visual_review?.summary || "",
      resource_type: resourceType,
      confidence: 0.5,
      weight: 0.55,
      metadata: {
        output_mode: result.output_mode || "",
        quality: result.render?.quality || "",
        artifact_count: artifacts.length,
        style_hint: result.style_hint || "",
        learner_profile_hints: result.learner_profile_hints ?? {},
        has_narrated_video: hasNarratedVideo,
      },
    };
  }, [artifacts, hasNarratedVideo, result, videos.length]);

  return (
    <div className="rounded-lg border border-line bg-canvas p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="brand">数学动画</Badge>
        {result.output_mode ? <Badge tone="neutral">{result.output_mode}</Badge> : null}
        {result.render?.quality ? <Badge tone="neutral">质量 {result.render.quality}</Badge> : null}
        {hasNarratedVideo ? <Badge tone="success">带旁白成片</Badge> : null}
      </div>

      <PersonalizationBrief hints={result.learner_profile_hints} styleHint={result.style_hint} className="mt-3" />

      {hasNarratedVideo ? (
        <p className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm leading-6 text-emerald-800">
          这是可直接播放的讲解成片，已经把动画和语音讲解合在一起了。
        </p>
      ) : null}

      {videos.length ? (
        <section className="mt-4 space-y-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-ink">
            <Video size={16} />
            {hasNarratedVideo ? "讲解成片" : "视频输出"}
          </div>
          {videos.map((item) => (
            <video
              key={item.url}
              controls
              playsInline
              preload="metadata"
              src={assetUrl(item.url)}
              className="aspect-video w-full rounded-lg border border-line bg-black object-contain"
            />
          ))}
        </section>
      ) : null}

      {result.audio_narration?.audio?.asset_url ? (
        <section className="mt-4 space-y-3">
          <AudioNarrationViewer result={result.audio_narration} embedded />
        </section>
      ) : null}

      {images.length ? (
        <section className="mt-4 space-y-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-ink">
            <ImageIcon size={16} />
            图片输出
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {images.map((item) => (
              <img
                key={item.url}
                src={assetUrl(item.url)}
                alt={item.label || item.filename}
                className="max-h-80 w-full rounded-lg border border-line bg-white object-contain"
              />
            ))}
          </div>
        </section>
      ) : null}

      {result.render?.visual_review?.passed === false ? (
        <p className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-800">
          {result.render.visual_review.summary || "视觉审查提示：当前结果仍有可改进之处。"}
        </p>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <ResourceEvidenceButton payload={evidencePayload} testId="math-animation-evidence-button" />
        {result.timings && Object.keys(result.timings).length ? (
          <span className="inline-flex items-center gap-1 rounded-md border border-line bg-white px-2 py-1 text-xs text-slate-500">
            <Timer size={13} />
            {Object.entries(result.timings)
              .map(([key, value]) => `${key}: ${value}s`)
              .join(" · ")}
          </span>
        ) : null}
        {result.code?.content ? (
          <Button tone="quiet" className="min-h-8 px-2 text-xs" onClick={() => setShowCode((value) => !value)}>
            <Code2 size={14} />
            {showCode ? "隐藏 Manim 代码" : "查看 Manim 代码"}
          </Button>
        ) : null}
      </div>

      {showCode && result.code?.content ? (
        <pre className="dt-code-surface mt-4 max-h-96 overflow-auto rounded-lg p-4 text-xs leading-6">
          {result.code.content}
        </pre>
      ) : null}
    </div>
  );
}
