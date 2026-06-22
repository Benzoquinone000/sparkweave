import { AlertTriangle, CheckCircle2, Clock3, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { planStatusLabel, planStatusTone } from "@/lib/guideDisplay";
import type {
  GuideResourceAgentStep,
  GuideResourceJobSnapshot,
  GuideV2Artifact,
  GuideV2ResourceType,
  GuideV2Task,
  QuizResultItem,
} from "@/lib/types";
import { GuideResourceArtifactPager } from "./GuideResourceArtifactPager";
import type { GuideStage } from "./guideLearningStrategy";
import type { GuideActionResourceType } from "./guideResourceUtils";
import { guideResourceIcon, resourceLabel } from "./guideResourceUtils";

export function GuideCurrentTaskPanel({
  guideStage,
  currentTask,
  highlightedSectionId,
  busy,
  generatingType,
  resourceJobSnapshot,
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
  resourceJobSnapshot: GuideResourceJobSnapshot | null;
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
  const hasArtifacts = currentArtifacts.length > 0;

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <section
        id="guide-current-task-section"
        className={`shrink-0 rounded-lg border bg-white p-4 shadow-sm transition-all duration-300 ${
          highlightedSectionId === "guide-current-task-section" ? "border-brand-purple ring-2 ring-brand-purple-300" : "border-line"
        }`}
      >
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="brand">{guideStage === "feedback" ? "下一步" : "当前任务"}</Badge>
          <Badge tone={planStatusTone(currentTask?.status || "pending")}>{planStatusLabel(currentTask?.status || "pending")}</Badge>
          {currentTask ? (
            <Badge tone="neutral">
              <Clock3 size={13} className="mr-1" />
              {currentTask.estimated_minutes ?? 8} 分钟
            </Badge>
          ) : null}
        </div>
        <h3 className="mt-3 line-clamp-2 text-lg font-semibold leading-7 text-ink">{currentTask?.title || "路线正在整理下一步"}</h3>
        {currentTask?.instruction ? <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-600">{currentTask.instruction}</p> : null}
        {adaptiveReason ? (
          <p className="mt-3 line-clamp-2 rounded-lg border border-brand-purple-300 bg-tint-lavender px-3 py-2 text-xs leading-5 text-charcoal">
            推荐理由：{adaptiveReason}
          </p>
        ) : null}

        <div className="mt-4 grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto_auto]">
          <Button
            tone="primary"
            className="min-h-11"
            disabled={!activeSessionId || busy || Boolean(generatingType)}
            onClick={() => onGenerateResource(primaryResourceAction.type)}
          >
            {generatingType === primaryResourceAction.type ? <Loader2 size={18} className="animate-spin" /> : guideResourceIcon(primaryResourceAction.type, 18)}
            {hasArtifacts ? "再生成一份材料" : primaryResourceAction.label || `生成${resourceLabel(primaryResourceAction.type)}`}
          </Button>
          <Button tone="secondary" className="min-h-11" onClick={onOpenResourceChoice}>
            换学法
          </Button>
          <Button tone="secondary" className="min-h-11" onClick={onOpenCompleteTask}>
            提交记录
          </Button>
        </div>
      </section>

      {resourceJobSnapshot && resourceJobSnapshot.stage !== "completed" ? (
        <ResourceAgentProgress snapshot={resourceJobSnapshot} fallbackType={generatingType || primaryResourceAction.type} />
      ) : null}

      {generatingType && !hasArtifacts && !resourceJobSnapshot ? (
        <div className="flex shrink-0 items-center gap-2 rounded-lg border border-brand-purple-300 bg-tint-lavender p-3 text-sm text-charcoal">
          <Loader2 size={16} className="animate-spin" />
          正在准备材料，完成后会出现在这里。
        </div>
      ) : null}

      <section className="min-h-0 flex-1 overflow-hidden rounded-lg border border-line bg-white p-3">
        {hasArtifacts ? (
          <>
            <div className="mb-2 flex items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-ink">学习材料</h3>
              <Badge tone="brand">{currentArtifacts.length} 份</Badge>
            </div>
            <GuideResourceArtifactPager
              artifacts={currentArtifacts}
              saveNotebookId={saveNotebookId}
              saving={savingArtifact}
              quizSubmitting={quizSubmitting}
              compact
              onSave={onSaveArtifact}
              onSubmitQuiz={onSubmitQuiz}
              onCompleteTask={onOpenCompleteTask}
            />
          </>
        ) : (
          <div className="grid h-full place-items-center text-center">
            <div>
              <div className="mx-auto grid size-12 place-items-center rounded-lg border border-line bg-canvas text-brand-purple">
                {guideResourceIcon(primaryResourceAction.type, 22)}
              </div>
              <p className="mt-3 text-sm font-semibold text-ink">先生成一份推荐材料</p>
              <p className="mt-1 text-xs leading-5 text-slate-500">学完后点“提交记录”，系统会继续给反馈。</p>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function ResourceAgentProgress({
  snapshot,
  fallbackType,
}: {
  snapshot: GuideResourceJobSnapshot;
  fallbackType: GuideV2ResourceType | string;
}) {
  const steps = snapshot.steps ?? [];
  const failed = snapshot.stage === "failed";
  const activeStep = steps.find((step) => step.status === "active") ?? steps.find((step) => step.status !== "done") ?? steps.at(-1);
  return (
    <div className="shrink-0 rounded-lg border border-brand-purple-300 bg-tint-lavender px-4 py-3" data-testid="guide-resource-agent-progress">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold text-ink">正在生成{resourceLabel(String(snapshot.resourceType || fallbackType))}</p>
        <Badge tone={failed ? "danger" : "brand"}>{failed ? "需要重试" : "生成中"}</Badge>
      </div>
      <div className="mt-2 flex items-center gap-2 text-xs text-charcoal">
        {failed ? <AlertTriangle size={14} /> : <Loader2 size={14} className="animate-spin" />}
        <span className="line-clamp-1">{snapshot.message || activeStep?.title || activeStep?.detail || "等待协作步骤。"}</span>
      </div>
      {snapshot.error ? <p className="mt-2 line-clamp-2 text-xs leading-5 text-red-600">{snapshot.error}</p> : null}
    </div>
  );
}

function ResourceAgentStepRow({ step }: { step: GuideResourceAgentStep }) {
  const status = String(step.status || "waiting");
  const active = status === "active";
  const done = status === "done";
  const failed = status === "failed";
  return (
    <li className="flex items-start gap-3 text-sm">
      <span className={`mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full ${agentStepIconTone(status)}`}>
        {active ? (
          <Loader2 size={12} className="animate-spin" />
        ) : failed ? (
          <AlertTriangle size={12} />
        ) : done ? (
          <CheckCircle2 size={12} />
        ) : (
          <span className="h-1.5 w-1.5 rounded-full bg-current" />
        )}
      </span>
      <span className="min-w-0">
        <span className="block text-xs font-semibold text-ink">{step.title || step.agent || "处理中"}</span>
        {step.detail ? <span className="mt-0.5 block text-xs leading-5 text-slate-500">{step.detail}</span> : null}
      </span>
    </li>
  );
}

function agentStepIconTone(status: string) {
  if (status === "done") return "bg-emerald-50 text-emerald-700";
  if (status === "active") return "bg-accent-purple-active text-accent-purple-ink";
  if (status === "failed") return "bg-red-50 text-red-700";
  return "bg-white text-slate-400";
}

void ResourceAgentStepRow;
