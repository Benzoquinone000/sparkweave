import type { FormEvent } from "react";
import { Loader2, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FieldShell, TextArea } from "@/components/ui/Field";
import type { GuideV2CourseTemplate } from "@/lib/types";
import { DemoQuickStartCard } from "./GuideDemoCards";
import { CourseTemplateQuickPick, SourceActionNotice } from "./GuideSetupPanels";

export function GuideCreateRoutePanel({
  primaryActionLabel,
  sourceAction,
  profileSuggestedPrompt,
  goal,
  demoTemplate,
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
  return (
    <section id="guide-create-section" className="rounded-lg border border-line bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Badge tone="brand">先做这一件事</Badge>
          <h2 className="mt-3 text-xl font-semibold text-ink">{primaryActionLabel}</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            写下目标、时间和偏好即可。路线、前测、资源和反馈都会在后面自动接上，不需要你自己找入口。
          </p>
        </div>
      </div>
      <form className="mt-6 space-y-4" onSubmit={onSubmit}>
        <SourceActionNotice action={sourceAction} />
        {!sourceAction && profileSuggestedPrompt && goal.trim() === profileSuggestedPrompt ? (
          <p className="rounded-lg border border-brand-purple-300 bg-tint-lavender px-3 py-2 text-xs leading-5 text-charcoal">
            已根据学习记录填好目标。你可以直接开始，也可以改成自己的说法。
          </p>
        ) : null}
        <DemoQuickStartCard
          template={demoTemplate}
          loading={templatesLoading}
          busy={creating}
          onStart={onStartDemo}
        />
        <CourseTemplateQuickPick
          templates={courseTemplates}
          demoTemplateId={demoTemplate?.id ?? ""}
          selectedTemplateId={courseTemplateId}
          busy={creating}
          onPick={onPickTemplate}
        />
        <FieldShell label="你想学什么">
          <TextArea
            value={goal}
            onChange={(event) => onGoalChange(event.target.value)}
            data-testid="guide-goal-input"
            className="min-h-28 text-sm leading-6"
            placeholder="例如：我想在 30 分钟内理解梯度下降，并做几道题确认掌握。"
          />
        </FieldShell>
        <Button tone="primary" type="submit" className="min-h-12 w-full text-base" disabled={!goal.trim() || creating}>
          {creating ? <Loader2 size={18} className="animate-spin" /> : <Sparkles size={18} />}
          帮我安排学习
        </Button>

        <button
          type="button"
          className="mx-auto flex min-h-10 items-center justify-center rounded-md px-3 text-sm font-medium text-slate-500 transition hover:bg-canvas hover:text-brand-purple"
          onClick={onOpenSetup}
        >
          需要更细设置
        </button>
      </form>
    </section>
  );
}
