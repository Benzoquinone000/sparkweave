import type { FormEvent } from "react";
import { Loader2, Settings2, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { FieldShell, TextArea } from "@/components/ui/Field";
import type { GuideV2CourseTemplate } from "@/lib/types";
import { CourseTemplateQuickPick, SourceActionNotice } from "./GuideSetupPanels";

export function GuideCreateRoutePanel({
  primaryActionLabel,
  sourceAction,
  profileSuggestedPrompt,
  goal,
  templatesLoading,
  creating,
  courseTemplates,
  courseTemplateId,
  onSubmit,
  onGoalChange,
  onStartDemo,
  onPickTemplate,
  onOpenSetup,
}: {
  primaryActionLabel: string;
  sourceAction: Record<string, unknown> | null;
  profileSuggestedPrompt: string;
  goal: string;
  demoTemplate: GuideV2CourseTemplate | null;
  templatesLoading: boolean;
  creating: boolean;
  courseTemplates: GuideV2CourseTemplate[];
  courseTemplateId: string;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onGoalChange: (value: string) => void;
  onStartDemo: () => void;
  onPickTemplate: (template: GuideV2CourseTemplate) => void;
  onOpenSetup: () => void;
}) {
  const demoTemplate = courseTemplates.find((template) => template.id === "deep_learning_foundations") ?? null;

  return (
    <section id="guide-create-section" className="flex h-full min-h-0 flex-col">
      <form className="flex h-full min-h-0 flex-col gap-3" onSubmit={onSubmit}>
        <SourceActionNotice action={sourceAction} />

        {!sourceAction && profileSuggestedPrompt && goal.trim() === profileSuggestedPrompt ? (
          <p className="line-clamp-1 rounded-lg border border-brand-purple-300 bg-tint-lavender px-3 py-2 text-xs text-charcoal">
            已按学习记录填好目标，可以直接开始。
          </p>
        ) : null}

        <div className="min-h-0 flex-1 rounded-lg border border-line bg-white p-4">
          <FieldShell label={primaryActionLabel || "你想学什么？"}>
            <TextArea
              value={goal}
              onChange={(event) => onGoalChange(event.target.value)}
              data-testid="guide-goal-input"
              className="min-h-28 text-sm leading-6"
              placeholder="例如：我想用 45 分钟梳理 CNN 图像检索、注意力机制和 Transformer。"
            />
          </FieldShell>

          <div className="mt-4 max-h-40 overflow-hidden">
            <CourseTemplateQuickPick
              templates={courseTemplates.slice(0, 4)}
              demoTemplateId={demoTemplate?.id ?? ""}
              selectedTemplateId={courseTemplateId}
              busy={creating || templatesLoading}
              onPick={onPickTemplate}
            />
          </div>
        </div>

        <div className="grid shrink-0 gap-2 sm:grid-cols-[minmax(0,1fr)_auto_auto]">
          <Button tone="primary" type="submit" className="min-h-12 text-base" disabled={!goal.trim() || creating}>
            {creating ? <Loader2 size={18} className="animate-spin" /> : <Sparkles size={18} />}
            帮我安排学习
          </Button>
          <Button tone="secondary" className="min-h-12" disabled={creating} onClick={onOpenSetup}>
            <Settings2 size={17} />
            设置
          </Button>
          {demoTemplate ? (
            <Button tone="quiet" className="min-h-12" disabled={creating} onClick={onStartDemo}>
              演示课程
            </Button>
          ) : null}
        </div>
      </form>
    </section>
  );
}
