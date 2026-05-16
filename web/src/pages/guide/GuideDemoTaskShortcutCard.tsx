import { Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { guideDisplayText, guideStageLabel } from "@/lib/guideDisplay";
import type { GuideV2ResourceType } from "@/lib/types";
import { readString } from "./guideDataUtils";
import { guideResourceIcon, normalizeResourceType, resourceLabel } from "./guideResourceUtils";

export function DemoTaskShortcutCard({
  step,
  busy,
  generatingType,
  onGenerate,
}: {
  step: Record<string, unknown> | null;
  busy: boolean;
  generatingType: GuideV2ResourceType | null;
  onGenerate: (type: GuideV2ResourceType, prompt: string) => void;
}) {
  if (!step) {
    return null;
  }

  const prompt = readString(step, "prompt");
  const resourceType = normalizeResourceType(readString(step, "resource_type"));
  if (!prompt || !resourceType) {
    return null;
  }

  const stage = guideStageLabel(readString(step, "stage"), "稳定演示");
  const show = guideDisplayText(readString(step, "show"), "使用内置 Demo 提示词生成稳定素材。");

  return (
    <div className="rounded-lg border border-blue-100 bg-blue-50 p-3" data-testid="guide-demo-task-shortcut">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">{stage}</Badge>
            <Badge tone="neutral">{resourceLabel(resourceType)}</Badge>
          </div>
          <p className="mt-2 text-sm font-semibold text-ink">使用稳定提示词生成</p>
          <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-600">{show}</p>
        </div>
        <Button tone="primary" className="min-h-9 px-3 text-xs" data-testid="guide-demo-generate" disabled={busy} onClick={() => onGenerate(resourceType, prompt)}>
          {generatingType === resourceType ? <Loader2 size={14} className="animate-spin" /> : guideResourceIcon(resourceType, 14)}
          生成{resourceLabel(resourceType)}
        </Button>
      </div>
      <p className="mt-2 line-clamp-2 rounded-lg border border-blue-100 bg-white p-2 text-xs leading-5 text-slate-500">
        {prompt}
      </p>
    </div>
  );
}
