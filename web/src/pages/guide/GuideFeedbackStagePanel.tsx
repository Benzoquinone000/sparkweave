import { BarChart3, CheckCircle2, Route } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { effectStatusTone, feedbackTone, guideDisplayText } from "@/lib/guideDisplay";
import type { GuideV2LearningFeedback, GuideV2LearningReport, GuideV2ResourceType } from "@/lib/types";
import { guideResourceIcon, normalizeResourceType, resourceLabel } from "./guideResourceUtils";

export function GuideFeedbackStagePanel({
  feedback,
  learningEffectReport,
  disabled,
  profileRefreshing,
  onGenerateResource,
  onOpenCurrentTask,
  onOpenRouteMap,
}: {
  highlightedSectionId: string | null;
  feedback: GuideV2LearningFeedback | null;
  learningEffectReport?: GuideV2LearningReport["learning_effect_report"] | null;
  disabled: boolean;
  profileRefreshing: boolean;
  demoEnabled: boolean;
  report: GuideV2LearningReport | null;
  reportLoading: boolean;
  onGenerateResource: (type: GuideV2ResourceType, taskId: string, prompt: string) => void;
  onOpenCurrentTask: () => void;
  onOpenRouteMap: () => void;
  onOpenCoursePackage: () => void;
}) {
  const primaryAction = feedback?.resource_actions?.find((item) => item.primary) ?? feedback?.resource_actions?.[0] ?? null;
  const resourceType = normalizeResourceType(primaryAction?.resource_type || "visual");
  const score = typeof feedback?.score_percent === "number" ? Math.round(feedback.score_percent) : null;
  const effectSummary = guideDisplayText(learningEffectReport?.summary, "");

  return (
    <section id="guide-feedback-section" className="flex h-full min-h-0 flex-col gap-3">
      <div className="shrink-0 rounded-lg border border-line bg-white p-4">
        <div className="flex flex-wrap items-center gap-2">
          <CheckCircle2 size={18} className="text-brand-purple" />
          <Badge tone={feedbackTone(feedback?.tone)}>学习记录已保存</Badge>
          {score !== null ? <Badge tone={effectStatusTone(score)}>{score} 分</Badge> : null}
          {profileRefreshing ? <Badge tone="neutral">同步记录中</Badge> : null}
        </div>
        <h3 className="mt-3 line-clamp-2 text-xl font-semibold text-ink">{feedback?.title || "这一步完成了"}</h3>
        <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-600">
          {feedback?.summary || "系统已经根据这次学习记录更新了下一步安排。"}
        </p>
      </div>

      <div className="grid min-h-0 flex-1 gap-3 md:grid-cols-2">
        <div className="rounded-lg border border-line bg-canvas p-4">
          <Badge tone="brand">下一步</Badge>
          <h4 className="mt-3 text-base font-semibold text-ink">{feedback?.next_task_title || "继续当前路线"}</h4>
          <p className="mt-2 line-clamp-4 text-sm leading-6 text-slate-600">
            {effectSummary || feedback?.actions?.[0] || "回到当前任务页，继续完成下一小步。"}
          </p>
          <Button tone="primary" className="mt-4 w-full" onClick={onOpenCurrentTask}>
            继续学习
          </Button>
        </div>

        <div className="rounded-lg border border-line bg-white p-4">
          <Badge tone="neutral">可选补充</Badge>
          <h4 className="mt-3 text-base font-semibold text-ink">
            {primaryAction?.label || `生成${resourceLabel(resourceType)}`}
          </h4>
          <p className="mt-2 line-clamp-4 text-sm leading-6 text-slate-600">
            {primaryAction?.prompt || "如果这一步还不稳，可以先补一份材料，再继续。"}
          </p>
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            <Button
              tone="secondary"
              disabled={disabled || !primaryAction?.target_task_id}
              onClick={() =>
                primaryAction?.target_task_id &&
                onGenerateResource(resourceType, primaryAction.target_task_id, primaryAction.prompt || "")
              }
            >
              {guideResourceIcon(resourceType, 16)}
              补材料
            </Button>
            <Button tone="secondary" onClick={onOpenRouteMap}>
              <Route size={16} />
              看路线
            </Button>
          </div>
        </div>
      </div>

      <a
        href="/memory"
        className="inline-flex min-h-9 shrink-0 items-center justify-center gap-1.5 rounded-lg border border-line bg-white px-3 text-sm font-medium text-slate-600 transition hover:border-brand-purple-300 hover:text-brand-purple"
      >
        <BarChart3 size={16} />
        查看学习记录变化
      </a>
    </section>
  );
}
