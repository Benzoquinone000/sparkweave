import { Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { guideTaskTitle } from "@/lib/guideDisplay";
import type { GuideV2ResourceType, GuideV2Task } from "@/lib/types";
import { GuideSubPageFrame } from "./GuideSubPageFrame";
import type { GuideActionResourceType } from "./guideResourceUtils";
import { guideResourceDescription, guideResourceIcon, resourceLabel } from "./guideResourceUtils";

export function GuideResourceChoicePage({
  currentTask,
  resourceActions,
  activeSessionId,
  busy,
  generatingType,
  onBack,
  onGenerateResource,
}: {
  currentTask: GuideV2Task;
  resourceActions: Array<{ type: GuideActionResourceType; label: string }>;
  activeSessionId: string | null;
  busy: boolean;
  generatingType: GuideV2ResourceType | null;
  onBack: () => void;
  onGenerateResource: (type: GuideV2ResourceType) => void;
}) {
  return (
    <GuideSubPageFrame
      eyebrow="学习材料"
      title="换一种学法"
      description="一次选一种材料，生成后会回到当前任务页。"
      onBack={onBack}
    >
      <div className="flex h-full min-h-0 flex-col gap-3">
        <section className="shrink-0 rounded-lg border border-brand-purple-300 bg-tint-lavender p-4">
          <Badge tone="brand">当前任务</Badge>
          <h3 className="mt-2 line-clamp-2 text-base font-semibold text-ink">{guideTaskTitle(currentTask)}</h3>
        </section>

        <div className="grid min-h-0 flex-1 gap-3 md:grid-cols-2">
          {resourceActions.slice(0, 4).map((action, index) => {
            const recommended = index === 0;
            return (
              <button
                key={action.type}
                type="button"
                data-testid={`guide-resource-choice-${action.type}`}
                disabled={!activeSessionId || busy || Boolean(generatingType)}
                className={`flex min-h-0 flex-col rounded-lg border p-4 text-left transition disabled:cursor-not-allowed disabled:opacity-60 ${
                  recommended
                    ? "border-brand-purple-300 bg-tint-lavender hover:border-brand-purple"
                    : "border-line bg-white hover:border-brand-purple-300 hover:bg-tint-lavender"
                }`}
                onClick={() => onGenerateResource(action.type)}
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="inline-flex items-center gap-2 text-sm font-semibold text-ink">
                    {generatingType === action.type ? <Loader2 size={16} className="animate-spin" /> : guideResourceIcon(action.type, 16)}
                    {action.label}
                  </span>
                  {recommended ? <Badge tone="brand">推荐</Badge> : <Badge tone="neutral">{resourceLabel(action.type)}</Badge>}
                </span>
                <span className="mt-3 line-clamp-3 text-sm leading-6 text-slate-600">{guideResourceDescription(action.type)}</span>
              </button>
            );
          })}
        </div>

        <Button tone="secondary" className="min-h-11 shrink-0" onClick={onBack}>
          先不换，回当前任务
        </Button>
      </div>
    </GuideSubPageFrame>
  );
}
