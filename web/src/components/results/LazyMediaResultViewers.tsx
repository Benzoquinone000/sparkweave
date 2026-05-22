import { lazy, Suspense } from "react";

import type { AudioNarrationResult, ExternalImageResult, ExternalVideoResult, MathAnimatorResult } from "@/lib/types";

const MathAnimatorViewer = lazy(() =>
  import("@/components/results/MathAnimatorViewer").then((module) => ({ default: module.MathAnimatorViewer })),
);
const ExternalVideoViewer = lazy(() =>
  import("@/components/results/ExternalVideoViewer").then((module) => ({ default: module.ExternalVideoViewer })),
);
const ExternalImageViewer = lazy(() =>
  import("@/components/results/ExternalImageViewer").then((module) => ({ default: module.ExternalImageViewer })),
);
const AudioNarrationViewer = lazy(() =>
  import("@/components/results/AudioNarrationViewer").then((module) => ({ default: module.AudioNarrationViewer })),
);

export function LazyMathAnimatorViewer({ result }: { result: MathAnimatorResult }) {
  return (
    <Suspense fallback={<MediaLoadingState label="数学动画" />}>
      <MathAnimatorViewer result={result} />
    </Suspense>
  );
}

export function LazyExternalVideoViewer({ result }: { result: ExternalVideoResult }) {
  return (
    <Suspense fallback={<MediaLoadingState label="精选视频" />}>
      <ExternalVideoViewer result={result} />
    </Suspense>
  );
}

export function LazyExternalImageViewer({ result }: { result: ExternalImageResult }) {
  return (
    <Suspense fallback={<MediaLoadingState label="精选图片" />}>
      <ExternalImageViewer result={result} />
    </Suspense>
  );
}

export function LazyAudioNarrationViewer({
  result,
  embedded = false,
}: {
  result: AudioNarrationResult;
  embedded?: boolean;
}) {
  return (
    <Suspense fallback={<MediaLoadingState label="语音讲解" embedded={embedded} />}>
      <AudioNarrationViewer result={result} embedded={embedded} />
    </Suspense>
  );
}

function MediaLoadingState({ label, embedded = false }: { label: string; embedded?: boolean }) {
  return (
    <div className={embedded ? "dt-dynamic-result rounded-lg bg-white/70 p-3" : "dt-dynamic-result rounded-lg border border-line bg-canvas p-3"}>
      <div className="flex items-center gap-2">
        <span className="h-6 w-16 rounded bg-slate-100" />
        <span className="text-xs font-medium text-slate-500">正在准备{label}...</span>
      </div>
      <div className="mt-3 h-24 rounded-lg bg-slate-100/70" />
    </div>
  );
}
