import { Bot, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { FieldShell, SelectInput, TextArea, TextInput } from "@/components/ui/Field";
import type { SparkBotSoul } from "@/lib/types";
import {
  ASSISTANT_COURSE_PRESETS,
  ASSISTANT_STYLE_PRESETS,
  assistantCoursePreset,
  assistantStylePreset,
} from "./assistantCreateWizardPresets";

export function AssistantCreateWizard({
  step,
  courseId,
  styleId,
  botId,
  name,
  description,
  persona,
  souls,
  pending,
  onStepChange,
  onCourseSelect,
  onStyleSelect,
  onBotIdChange,
  onNameChange,
  onDescriptionChange,
  onPersonaChange,
  onApplyPreset,
  onUseSoul,
  onSubmit,
}: {
  step: number;
  courseId: string;
  styleId: string;
  botId: string;
  name: string;
  description: string;
  persona: string;
  souls: SparkBotSoul[];
  pending: boolean;
  onStepChange: (step: number) => void;
  onCourseSelect: (courseId: string) => void;
  onStyleSelect: (styleId: string) => void;
  onBotIdChange: (value: string) => void;
  onNameChange: (value: string) => void;
  onDescriptionChange: (value: string) => void;
  onPersonaChange: (value: string) => void;
  onApplyPreset: () => void;
  onUseSoul: (soul: SparkBotSoul) => void;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
}) {
  const selectedCourse = assistantCoursePreset(courseId);
  const selectedStyle = assistantStylePreset(styleId);
  const steps = ["课程", "风格", "确认"];
  return (
    <form className="mt-4 border-t border-line pt-4" onSubmit={onSubmit}>
      <div className="grid gap-2 sm:grid-cols-3">
        {steps.map((item, index) => {
          const active = step === index;
          return (
            <button
              key={item}
              type="button"
              className={`dt-interactive rounded-lg border px-3 py-2 text-left text-sm transition ${
                active ? "border-ink bg-ink text-white" : "border-line bg-canvas text-slate-600 hover:border-brand-purple-300"
              }`}
              onClick={() => onStepChange(index)}
              data-testid={`assistant-create-step-${index}`}
            >
              <span className="block text-xs font-semibold">
                {index + 1}. {item}
              </span>
              <span className={`mt-1 block text-xs ${active ? "text-white/75" : "text-slate-500"}`}>
                {index === 0 ? selectedCourse.title : index === 1 ? selectedStyle.title : name || selectedCourse.name}
              </span>
            </button>
          );
        })}
      </div>

      {step === 0 ? (
        <div className="mt-4 grid gap-2">
          {ASSISTANT_COURSE_PRESETS.map((course) => {
            const active = course.id === courseId;
            return (
              <button
                key={course.id}
                type="button"
                className={`dt-interactive rounded-lg border p-3 text-left transition ${active ? "border-brand-purple-300 bg-tint-lavender" : "border-line bg-white hover:border-brand-purple-300"}`}
                onClick={() => onCourseSelect(course.id)}
                data-testid={`assistant-course-${course.id}`}
              >
                <span className="block text-sm font-semibold text-ink">{course.title}</span>
                <span className="mt-1 block text-xs leading-5 text-slate-500">{course.focus}</span>
              </button>
            );
          })}
          <div className="flex justify-end pt-2">
            <Button tone="primary" onClick={() => onStepChange(1)} data-testid="assistant-create-next-style">
              下一步
            </Button>
          </div>
        </div>
      ) : null}

      {step === 1 ? (
        <div className="mt-4 grid gap-2">
          {ASSISTANT_STYLE_PRESETS.map((style) => {
            const active = style.id === styleId;
            return (
              <button
                key={style.id}
                type="button"
                className={`dt-interactive rounded-lg border p-3 text-left transition ${active ? "border-brand-purple-300 bg-tint-lavender" : "border-line bg-white hover:border-brand-purple-300"}`}
                onClick={() => onStyleSelect(style.id)}
                data-testid={`assistant-style-${style.id}`}
              >
                <span className="block text-sm font-semibold text-ink">{style.title}</span>
                <span className="mt-1 block text-xs leading-5 text-slate-500">{style.detail}</span>
              </button>
            );
          })}
          <div className="flex flex-wrap justify-between gap-2 pt-2">
            <Button tone="secondary" onClick={() => onStepChange(0)}>
              上一步
            </Button>
            <Button tone="primary" onClick={() => onStepChange(2)} data-testid="assistant-create-next-confirm">
              下一步
            </Button>
          </div>
        </div>
      ) : null}

      {step === 2 ? (
        <div className="mt-4 grid gap-3">
          <div className="rounded-lg border border-line bg-canvas p-3">
            <p className="text-xs font-semibold text-brand-purple">即将创建</p>
            <p className="mt-1 text-sm font-semibold text-ink">{name || selectedCourse.name}</p>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              {selectedCourse.title} · {selectedStyle.title}
            </p>
          </div>
          <FieldShell label="助教 ID">
            <TextInput value={botId} onChange={(event) => onBotIdChange(event.target.value)} placeholder="ai_learning_agents_tutor" data-testid="assistant-create-bot-id" />
          </FieldShell>
          <FieldShell label="助教名称">
            <TextInput value={name} onChange={(event) => onNameChange(event.target.value)} placeholder={selectedCourse.name} data-testid="assistant-create-name" />
          </FieldShell>
          <FieldShell label="学习任务">
            <TextInput value={description} onChange={(event) => onDescriptionChange(event.target.value)} placeholder={selectedCourse.description} data-testid="assistant-create-description" />
          </FieldShell>
          <FieldShell label="助教工作方式">
            <TextArea value={persona} onChange={(event) => onPersonaChange(event.target.value)} className="min-h-40" data-testid="assistant-create-persona" />
          </FieldShell>
          {souls.length ? (
            <FieldShell label="套用已有模板">
              <SelectInput
                value=""
                onChange={(event) => {
                  const soul = souls.find((item) => item.id === event.target.value);
                  if (soul) onUseSoul(soul);
                }}
                data-testid="assistant-create-soul"
              >
                <option value="">选择一个模板</option>
                {souls.map((soul) => (
                  <option key={soul.id} value={soul.id}>
                    {soul.name}
                  </option>
                ))}
              </SelectInput>
            </FieldShell>
          ) : null}
          <div className="flex flex-wrap justify-between gap-2 pt-1">
            <Button tone="secondary" onClick={onApplyPreset}>
              恢复推荐设定
            </Button>
            <Button tone="primary" type="submit" disabled={!botId.trim() || pending} data-testid="assistant-create-submit">
              {pending ? <Loader2 size={16} className="animate-spin" /> : <Bot size={16} />}
              创建并启动
            </Button>
          </div>
        </div>
      ) : null}
    </form>
  );
}
