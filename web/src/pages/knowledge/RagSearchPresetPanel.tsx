import { Badge } from "@/components/ui/Badge";

import { RAG_TEST_PRESETS } from "./ragTestConfig";

export function RagSearchPresetPanel({
  presetId,
  onPresetApply,
}: {
  presetId: string;
  onPresetApply: (presetId: string) => void;
}) {
  return (
    <div className="rounded-lg border border-line bg-canvas p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-ink">检索方案</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">按问题复杂度选择一组稳定参数。</p>
        </div>
        <Badge tone={presetId === "custom" ? "neutral" : "success"}>{presetId === "custom" ? "自定义" : "已套用"}</Badge>
      </div>
      <div className="mt-3 grid gap-2 md:grid-cols-3">
        {RAG_TEST_PRESETS.map((preset) => {
          const selected = preset.id === presetId;
          return (
            <button
              key={preset.id}
              type="button"
              className={`min-h-20 rounded-lg border p-3 text-left transition ${
                selected
                  ? "border-brand-purple-300 bg-tint-lavender text-brand-purple"
                  : "border-line bg-white text-slate-600 hover:border-brand-purple-300 hover:text-ink"
              }`}
              onClick={() => onPresetApply(preset.id)}
              data-testid={`knowledge-rag-test-preset-${preset.id}`}
            >
              <span className="block text-sm font-semibold">{preset.label}</span>
              <span className="mt-1 block text-xs leading-5 text-slate-500">{preset.description}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
