import { Clock3, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  planStatusLabel,
  planStatusTone,
} from "@/lib/guideDisplay";
import type { GuideV2Artifact, GuideV2ResourceType, GuideV2Task, QuizResultItem } from "@/lib/types";
import { DemoTaskShortcutCard } from "./GuideDemoTaskShortcutCard";
import { GuideResourceArtifactPager } from "./GuideResourceArtifactPager";
import type { GuideStage } from "./guideLearningStrategy";
import type { GuideActionResourceType } from "./guideResourceUtils";
import { guideResourceIcon, resourceLabel } from "./guideResourceUtils";

export function GuideCurrentTaskPanel({
  guideStage,
  currentTask,
  currentDemoStep,
  highlightedSectionId,
  busy,
  generatingType,
  activeSessionId,
  primaryResourceAction,
  currentArtifacts,
  adaptiveReason,
  saveNotebookId,
  savingArtifact,
  quizSubmitting,
  onGenerateResource,
  onOpenCompleteTask,
  onOpenResourceChoice,
  onSaveArtifact,
  onSubmitQuiz,
}: {
  guideStage: GuideStage;
  currentTask: GuideV2Task | null;
  currentDemoStep: Record<string, unknown> | null;
  highlightedSectionId: string | null;
  busy: boolean;
  generatingType: GuideV2ResourceType | null;
  activeSessionId: string | null;
  primaryResourceAction: { type: GuideActionResourceType; label: string };
  currentArtifacts: GuideV2Artifact[];
  adaptiveReason?: string;
  saveNotebookId: string;
  savingArtifact: boolean;
  quizSubmitting: boolean;
  onGenerateResource: (type: GuideV2ResourceType, taskId?: string, prompt?: string) => void;
  onOpenCompleteTask: () => void;
  onOpenResourceChoice: () => void;
  onSaveArtifact: (artifact: GuideV2Artifact) => void;
  onSubmitQuiz: (artifact: GuideV2Artifact, answers: QuizResultItem[]) => void;
}) {
  return (
    <>
      <section
        id="guide-current-task-section"
        className={`rounded-lg border bg-white p-5 shadow-sm transition-all duration-500 ${
          highlightedSectionId === "guide-current-task-section"
            ? "border-brand-purple ring-2 ring-brand-purple-300"
            : "border-line"
        }`}
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <Badge tone="brand">{guideStage === "feedback" ? "接着做这一步" : "先做这一件事"}</Badge>
            <h2 className="mt-3 text-xl font-semibold text-ink">{currentTask?.title || "路线正在整理下一步"}</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              {currentTask?.instruction || "系统会把目标拆成可执行任务，并根据完成情况更新掌握度与下一步建议。"}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge tone={planStatusTone(currentTask?.status || "pending")}>{planStatusLabel(currentTask?.status || "pending")}</Badge>
            {currentTask ? (
              <Badge tone="neutral">
                <Clock3 size={13} className="mr-1" />
                {currentTask.estimated_minutes ?? 8} 分钟
              </Badge>
            ) : null}
          </div>
        </div>

        {currentTask ? (
          <div className="mt-5 space-y-3">
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_260px]">
              <div className="space-y-3">
                <DemoTaskShortcutCard
                  step={currentDemoStep}
                  busy={busy || Boolean(generatingType)}
                  generatingType={generatingType}
                  onGenerate={(type, prompt) => onGenerateResource(type, currentTask.task_id, prompt)}
                />
                <div className="rounded-lg border border-[#f5d75e] bg-tint-yellow p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold text-ink">现在先看这个</p>
                      <p className="mt-1 text-xs leading-5 text-charcoal">不用自己找材料，系统已经替你选好当前最合适的方式。</p>
                    </div>
                    <Badge tone="brand">{resourceLabel(primaryResourceAction.type)}</Badge>
                  </div>
                  <Button
                    tone="primary"
                    className="mt-4 min-h-12 w-full justify-center text-base"
                    disabled={!activeSessionId || busy || Boolean(generatingType)}
                    onClick={() => onGenerateResource(primaryResourceAction.type)}
                  >
                    {generatingType === primaryResourceAction.type ? <Loader2 size={18} className="animate-spin" /> : guideResourceIcon(primaryResourceAction.type, 18)}
                    {primaryResourceAction.label}
                  </Button>
                </div>
                <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_150px]">
                  <button
                    type="button"
                    data-testid="guide-open-complete-task"
                    className="rounded-lg border border-line bg-canvas p-4 text-left transition hover:border-brand-purple-300 hover:bg-tint-lavender"
                    onClick={onOpenCompleteTask}
                  >
                    <span className="text-sm font-semibold text-ink">学完了，去提交</span>
                    <span className="mt-1 block text-xs leading-5 text-slate-500">评分、反思，系统再给反馈。</span>
                  </button>
                  <button
                    type="button"
                    data-testid="guide-open-resource-choice"
                    className="rounded-lg border border-line bg-white p-4 text-left transition hover:border-brand-purple-300 hover:bg-tint-lavender"
                    onClick={onOpenResourceChoice}
                  >
                    <span className="text-sm font-semibold text-ink">换一种学法</span>
                    <span className="mt-1 block text-xs leading-5 text-slate-500">图解、短视频或练习。</span>
                  </button>
                </div>
              </div>
              <aside className="dt-workspace-mockup">
                <img src="/illustrations/notion-guide-loop.svg" alt="导学过程预览" className="max-h-40 w-full object-contain" />
                <div className="border-t border-line bg-[#fbfbfa] p-3 text-xs leading-5 text-steel">
                  导学只保留一条主线：先学一点，再提交反馈，然后自动调整。
                </div>
              </aside>
            </div>
            {adaptiveReason ? (
              <p className="rounded-lg border border-brand-purple-300 bg-tint-lavender px-3 py-2 text-xs leading-5 text-charcoal">
                调整理由：{adaptiveReason}
              </p>
            ) : null}
          </div>
        ) : null}
      </section>

      {currentArtifacts.length || generatingType ? (
        <section
          id="guide-resource-results-section"
          className={`rounded-lg border bg-white p-5 transition-all duration-500 ${
            highlightedSectionId === "guide-resource-results-section"
              ? "border-brand-purple ring-2 ring-brand-purple-300"
              : "border-line"
          }`}
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-ink">学完看这里</h2>
              <p className="mt-1 text-sm leading-6 text-slate-500">
                系统生成好的内容会按顺序排在这里。看完后直接去提交这一任务。
              </p>
            </div>
            <Badge tone={currentArtifacts.length ? "brand" : "neutral"}>
              {currentArtifacts.length ? `已准备 ${currentArtifacts.length} 份` : "暂未开始"}
            </Badge>
          </div>
          <div className="mt-5 space-y-3">
            {generatingType && !currentArtifacts.length ? (
              <div className="flex items-center gap-2 rounded-lg border border-brand-purple-300 bg-tint-lavender p-3 text-sm text-charcoal">
                <Loader2 size={16} className="animate-spin" />
                正在准备中，完成后会直接出现在这里。
              </div>
            ) : null}
            {currentArtifacts.length ? (
              <GuideResourceArtifactPager
                artifacts={currentArtifacts}
                saveNotebookId={saveNotebookId}
                saving={savingArtifact}
                quizSubmitting={quizSubmitting}
                onSave={onSaveArtifact}
                onSubmitQuiz={onSubmitQuiz}
                onCompleteTask={onOpenCompleteTask}
              />
            ) : null}
            {currentTask && !currentArtifacts.length ? (
              <p className="rounded-lg border border-dashed border-line bg-canvas p-4 text-sm text-slate-500">
                还没有学习材料。建议先点“{primaryResourceAction.label}”，看完后再回来提交当前任务。
              </p>
            ) : null}
          </div>
        </section>
      ) : null}
    </>
  );
}
