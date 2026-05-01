import { Code2, Image as ImageIcon, Timer, Video } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { PersonalizationBrief } from "@/components/results/PersonalizationBrief";
import { apiUrl } from "@/lib/api";
import type { MathAnimatorResult } from "@/lib/types";

function assetUrl(url: string) {
  return url.startsWith("http://") || url.startsWith("https://") ? url : apiUrl(url);
}

export function MathAnimatorViewer({ result }: { result: MathAnimatorResult }) {
  const [showCode, setShowCode] = useState(false);
  const artifacts = result.artifacts ?? [];
  const videos = artifacts.filter((item) => item.type === "video");
  const images = artifacts.filter((item) => item.type === "image");

  return (
    <div className="rounded-lg border border-line bg-canvas p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="brand">数学动画</Badge>
        {result.output_mode ? <Badge tone="neutral">{result.output_mode}</Badge> : null}
        {result.render?.quality ? <Badge tone="neutral">质量 {result.render.quality}</Badge> : null}
      </div>

      <PersonalizationBrief hints={result.learner_profile_hints} styleHint={result.style_hint} className="mt-3" />

      {videos.length ? (
        <section className="mt-4 space-y-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-ink">
            <Video size={16} />
            视频输出
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
          {result.render.visual_review.summary || "视觉审查提示：生成结果仍有可改进之处。"}
        </p>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center gap-2">
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
