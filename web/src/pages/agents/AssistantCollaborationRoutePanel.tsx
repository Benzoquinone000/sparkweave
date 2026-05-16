import type { LucideIcon } from "lucide-react";

import { Badge } from "@/components/ui/Badge";

export type AssistantCollaborationStep = {
  id: string;
  title: string;
  detail: string;
  label: string;
  tone: "neutral" | "success" | "warning" | "brand";
  icon: LucideIcon;
};

export function AssistantCollaborationRoutePanel({
  steps,
  readyCount,
}: {
  steps: AssistantCollaborationStep[];
  readyCount: number;
}) {
  return (
    <div className="mt-4 border-t border-line pt-3" data-testid="assistant-collaboration-route">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-ink">学习协作路线</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">从画像、资料、讲解、练习到评估回写，当前学习闭环一眼可查。</p>
        </div>
        <Badge tone={readyCount === steps.length ? "success" : "neutral"}>
          {readyCount}/{steps.length}
        </Badge>
      </div>
      <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-6">
        {steps.map((step) => {
          const Icon = step.icon;
          return (
            <div key={step.id} className="border border-line bg-canvas p-3" style={{ borderRadius: 8 }}>
              <div className="flex items-start justify-between gap-2">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center border border-line bg-white text-brand-purple" style={{ borderRadius: 8 }}>
                  <Icon size={15} />
                </span>
                <Badge tone={step.tone}>{step.label}</Badge>
              </div>
              <p className="mt-3 text-sm font-semibold text-ink">{step.title}</p>
              <p className="mt-1 line-clamp-3 text-xs leading-5 text-slate-500">{step.detail}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
