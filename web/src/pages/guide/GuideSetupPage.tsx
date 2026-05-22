import type { FormEvent } from "react";
import { Loader2, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { FieldShell, SelectInput, TextArea, TextInput } from "@/components/ui/Field";
import type { GuideV2CourseTemplate, NotebookRecord } from "@/lib/types";
import {
  CourseTemplatePreview,
  ReferencePicker,
  SourceActionNotice,
} from "./GuideSetupPanels";
import { GuideSubPageFrame } from "./GuideSubPageFrame";
import { horizonOptions, levelOptions } from "./guideFormOptions";

export function GuideSetupPage({
  highlightedSectionId,
  sourceAction,
  goal,
  courseTemplateId,
  courseTemplates,
  selectedTemplate,
  templatesLoading,
  level,
  timeBudget,
  horizon,
  weakPoints,
  notebooks,
  referenceNotebookId,
  referenceRecords,
  selectedRecordIds,
  referenceLoading,
  creating,
  onBack,
  onSubmit,
  onGoalChange,
  onCourseTemplateChange,
  onLevelChange,
  onTimeBudgetChange,
  onHorizonChange,
  onWeakPointsChange,
  onReferenceNotebookChange,
  onToggleRecord,
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
      title="只在需要时补充这些"
      description="主流程已经足够开始学习。这里仅用于补充偏好，好让后面的路线更贴近你。"
      onBack={onBack}
    >
      <form
        id="guide-setup-section"
        className={`space-y-4 rounded-lg transition-all duration-500 ${
          highlightedSectionId === "guide-setup-section" ? "ring-2 ring-tint-lavender ring-offset-2 ring-offset-canvas" : ""
        }`}
        onSubmit={onSubmit}
      >
        <SourceActionNotice action={sourceAction} />
        <div className="rounded-lg border border-line bg-tint-yellow px-4 py-3 text-sm leading-6 text-charcoal">
          不想填满也没关系。通常只补“时间”和“现在最担心哪一块”就够用了。
        </div>
        <FieldShell label="你想学什么">
          <TextArea
            value={goal}
            onChange={(event) => onGoalChange(event.target.value)}
            data-testid="guide-goal-input"
            className="min-h-28 text-sm leading-6"
            placeholder="例如：我想在 30 分钟内理解梯度下降，并做几道题确认掌握。"
          />
        </FieldShell>
        <div className="grid gap-3 md:grid-cols-2">
          <FieldShell label="想按哪门课学" hint="可选">
            <SelectInput value={courseTemplateId} onChange={(event) => onCourseTemplateChange(event.target.value)}>
              <option value="">自定义学习目标</option>
              {courseTemplates.map((template) => (
                <option key={template.id} value={template.id}>
                  {template.title}
                </option>
              ))}
            </SelectInput>
          </FieldShell>
          <FieldShell label="你现在的基础">
            <SelectInput value={level} onChange={(event) => onLevelChange(event.target.value)}>
              {levelOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </SelectInput>
          </FieldShell>
        </div>
        <CourseTemplatePreview template={selectedTemplate} loading={templatesLoading} />
        <div className="grid gap-3 md:grid-cols-2">
          <FieldShell label="这次准备学多久">
            <TextInput value={timeBudget} onChange={(event) => onTimeBudgetChange(event.target.value)} inputMode="numeric" />
          </FieldShell>
          <FieldShell label="希望按什么节奏学">
            <SelectInput value={horizon} onChange={(event) => onHorizonChange(event.target.value)}>
              {horizonOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </SelectInput>
          </FieldShell>
        </div>
        <FieldShell label="你现在最担心哪一块" hint="可选">
          <TextInput value={weakPoints} onChange={(event) => onWeakPointsChange(event.target.value)} placeholder="例如：公式推导、代码实现、概念直觉" />
        </FieldShell>
        <ReferencePicker
          notebooks={notebooks}
          notebookId={referenceNotebookId}
          records={referenceRecords}
          selectedRecordIds={selectedRecordIds}
          loading={referenceLoading}
          onNotebookChange={onReferenceNotebookChange}
          onToggleRecord={onToggleRecord}
        />
        <Button tone="primary" type="submit" className="min-h-12 w-full text-base" disabled={!goal.trim() || creating}>
          {creating ? <Loader2 size={18} className="animate-spin" /> : <Sparkles size={18} />}
          保存这些偏好
        </Button>
      </form>
    </GuideSubPageFrame>
  );
}
