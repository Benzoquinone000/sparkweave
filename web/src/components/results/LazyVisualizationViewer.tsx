import { lazy, Suspense } from "react";

import type { VisualizeResult } from "@/lib/types";

const VisualizationViewer = lazy(() =>
  import("@/components/results/VisualizationViewer").then((module) => ({ default: module.VisualizationViewer })),
);

export function LazyVisualizationViewer({ result }: { result: VisualizeResult }) {
  return (
    <Suspense fallback={<VisualizationLoadingState />}>
      <VisualizationViewer result={result} />
    </Suspense>
  );
}

function VisualizationLoadingState() {
  return (
    <div className="dt-dynamic-result rounded-lg border border-line bg-canvas p-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="h-6 w-16 rounded bg-slate-100" />
        <span className="h-6 w-20 rounded bg-slate-100" />
      </div>
      <div className="dt-dynamic-panel mt-3 rounded-lg border border-line bg-white p-2.5">
        <div className="h-48 min-h-48 rounded-lg bg-slate-100/70" />
      </div>
      <p className="mt-3 text-xs text-slate-500">正在准备可视化预览...</p>
    </div>
  );
}
