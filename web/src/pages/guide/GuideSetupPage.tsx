import type { FormEvent } from "react";
import { Loader2, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { FieldShell, SelectInput, TextArea, TextInput } from "@/components/ui/Field";
import type { GuideV2CourseTemplate, NotebookRecord } from "@/lib/types";
import { SourceActionNotice } from "./GuideSetupPanels";
import { GuideSubPageFrame } from "./GuideSubPageFrame";
import { horizonOptions, levelOptions } from "./guideFormOptions";

export function GuideSetupPage({
  sourceAction,
  goal,
  courseTemplateId,
  courseTemplates,
  level,
  timeBudget,
  horizon,
  weakPoints,
  creating,
  onBack,
  onSubmit,
  onGoalChange,
  onCourseTemplateChange,
  onLevelChange,
  onTimeBudgetChange,
  onHorizonChange,
  onWeakPointsChange,
}: {
  highlightedSectionId: string | null;
  sourceAction: Record<string, unknown> | null;
  goal: string;
  courseTemplateId: string;
  courseTemplates: GuideV2CourseTemplate[];
  selectedTemplate: GuideV2CourseTemplate | null;
  templatesLoading: boolean;
  level: string;
  timeBudget: string;
  horizon: string;
  weakPoints: string;
  notebooks: Array<{ id: string; name?: string }>;
  referenceNotebookId: string;
  referenceRecords: NotebookRecord[];
  selectedRecordIds: string[];
  referenceLoading: boolean;
  creating: boolean;
  onBack: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onGoalChange: (value: string) => void;
  onCourseTemplateChange: (value: string) => void;
  onLevelChange: (value: string) => void;
  onTimeBudgetChange: (value: string) => void;
  onHorizonChange: (value: string) => void;
  onWeakPointsChange: (value: string) => void;
  onReferenceNotebookChange: (value: string) => void;
  onToggleRecord: (record: NotebookRecord) => void;
}) {
  return (
    <GuideSubPageFrame
      eyebrow="补充信息"
      title="只补最关键的"
      description="这里不是必填表单，只用于让路线更贴近你。"
      onBack={onBack}
    >
      <form id="guide-setup-section" className="flex h-full min-h-0 flex-col gap-3" onSubmit={onSubmit}>
        <SourceActionNotice action={sourceAction} />

        <section className="min-h-0 flex-1 rounded-lg border border-line bg-white p-4">
          <FieldShell label="学习目标">
            <TextArea
              value={goal}
              onChange={(event) => onGoalChange(event.target.value)}
              data-testid="guide-goal-input"
              className="min-h-24 text-sm leading-6"
              placeholder="例如：我想在 30 分钟内梳理赛题的学习画像、资源生成和评估闭环。"
            />
          </FieldShell>

          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <FieldShell label="课程模板">
              <SelectInput value={courseTemplateId} onChange={(event) => onCourseTemplateChange(event.target.value)}>
                <option value="">自定义目标</option>
                {courseTemplates.map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.title}
                  </option>
                ))}
              </SelectInput>
            </FieldShell>
            <FieldShell label="当前基础">
              <SelectInput value={level} onChange={(event) => onLevelChange(event.target.value)}>
                {levelOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </SelectInput>
            </FieldShell>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <FieldShell label="这次学多久">
              <TextInput value={timeBudget} onChange={(event) => onTimeBudgetChange(event.target.value)} inputMode="numeric" />
            </FieldShell>
            <FieldShell label="学习节奏">
              <SelectInput value={horizon} onChange={(event) => onHorizonChange(event.target.value)}>
                {horizonOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </SelectInput>
            </FieldShell>
          </div>

          <div className="mt-4">
            <FieldShell label="最担心哪一块" hint="可选">
              <TextInput value={weakPoints} onChange={(event) => onWeakPointsChange(event.target.value)} placeholder="例如：公式推导、代码实现、概念直觉" />
            </FieldShell>
          </div>
        </section>

        <Button tone="primary" type="submit" className="min-h-12 w-full shrink-0 text-base" disabled={!goal.trim() || creating}>
          {creating ? <Loader2 size={18} className="animate-spin" /> : <Sparkles size={18} />}
          保存并回到导学
        </Button>
      </form>
    </GuideSubPageFrame>
  );
}
