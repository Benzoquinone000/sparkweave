import { motion } from "framer-motion";
import { BarChart3, Brain, CheckCircle2, Compass, Lightbulb, Target } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { effectStatusTone, feedbackTone } from "@/lib/guideDisplay";
import type { GuideV2LearningFeedback, GuideV2LearningReport, GuideV2ResourceType } from "@/lib/types";
import { GuideLearningLoopReceipt, LearningImpactSummary } from "./GuideLearningLoopSummary";
import { guideResourceIcon, isResearchResourceType, normalizeResourceType, resourceLabel } from "./guideResourceUtils";

type FeedbackDecisionResourceAction = {
  kind: "resource";
  label: string;
  resourceType: GuideV2ResourceType;
  taskId: string;
  prompt: string;
};

type FeedbackDecisionUiAction =
  | FeedbackDecisionResourceAction
  | { kind: "current_task"; label: string }
  | { kind: "route_map"; label: string };

type FeedbackDecisionPath = {
  label: string;
  description: string;
  primary: boolean;
  action: FeedbackDecisionUiAction;
};

type NormalizedFeedbackResourceAction = {
  item: NonNullable<GuideV2LearningFeedback["resource_actions"]>[number];
  resourceType: GuideV2ResourceType;
  taskId: string;
  prompt: string;
  label: string;
};

export function GuideLearningFeedbackCard({
  feedback,
  learningEffectReport,
  disabled,
  profileRefreshing,
  onGenerateResource,
  onOpenCurrentTask,
  onOpenRouteMap,
}: {
  feedback: GuideV2LearningFeedback | null;
  learningEffectReport?: GuideV2LearningReport["learning_effect_report"] | null;
  disabled: boolean;
  profileRefreshing: boolean;
  onGenerateResource: (type: GuideV2ResourceType, taskId: string, prompt: string) => void;
  onOpenCurrentTask: () => void;
  onOpenRouteMap: () => void;
}) {
  if (!feedback) return null;
  const resourceActions = (feedback.resource_actions ?? []).filter((item) => !isResearchResourceType(item.resource_type || ""));
  const remediationTask = feedback.remediation_task ?? null;
  const remediationResourceAction = remediationTask
    ? resourceActions.find((item) => item.id === remediationTask.resource_action_id) ?? resourceActions[0] ?? null
    : null;
  const decision = buildFeedbackDecision(feedback, resourceActions);
  const primaryPath =
    decision.paths.find((path) => path.primary) ??
    decision.paths[0] ?? {
      label: "回到当前任务",
      description: "先回到当前任务，把刚学完的内容再压实一下。",
      primary: true,
      action: { kind: "current_task", label: "回到当前任务" } as FeedbackDecisionUiAction,
    };
  const secondaryPaths = decision.paths.filter((path) => path.label !== primaryPath.label).slice(0, 2);
  return (
    <motion.section
      className="rounded-lg border border-line bg-white p-5 shadow-sm"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <CheckCircle2 size={18} className="text-brand-purple" />
            <p className="text-sm font-semibold text-brand-purple">这一步已经完成</p>
            <Badge tone={feedbackTone(feedback.tone)}>{feedback.score_percent == null ? "已记录" : `${Math.round(feedback.score_percent)} 分`}</Badge>
          </div>
          <h2 className="mt-3 text-lg font-semibold text-ink">{feedback.title || "学习记录已保存"}</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            {feedback.summary || "系统已经根据这次学习记录更新了下一步安排。"}
          </p>
        </div>
        {feedback.next_task_title ? <Badge tone="brand">下一步</Badge> : <Badge tone="success">完成</Badge>}
      </div>

      <LearningImpactSummary feedback={feedback} compact />
      <GuideLearningLoopReceipt
        feedback={feedback}
        report={learningEffectReport ?? null}
        profileRefreshing={profileRefreshing}
      />

      {remediationTask ? (
        <MinimalRemediationTaskCard
          task={remediationTask}
          action={remediationResourceAction}
          disabled={disabled}
          onGenerateResource={onGenerateResource}
        />
      ) : null}

      <div className="mt-4 rounded-lg border border-brand-purple-300 bg-tint-lavender p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="text-sm font-semibold text-brand-purple">接下来先做这个</p>
            <h3 className="mt-2 text-base font-semibold text-ink">{primaryPath.label}</h3>
            <p className="mt-1 text-sm leading-6 text-charcoal">{primaryPath.description || decision.summary}</p>
          </div>
          <Badge tone={decision.tone}>{decision.badge}</Badge>
        </div>
        <div className="mt-4">
          <FeedbackPathButton
            path={primaryPath}
            disabled={disabled}
            onGenerateResource={onGenerateResource}
            onOpenCurrentTask={onOpenCurrentTask}
            onOpenRouteMap={onOpenRouteMap}
          />
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {secondaryPaths.map((path) => (
          <FeedbackPathButton
            key={path.label}
            path={path}
            compact
            disabled={disabled}
            onGenerateResource={onGenerateResource}
            onOpenCurrentTask={onOpenCurrentTask}
            onOpenRouteMap={onOpenRouteMap}
          />
        ))}
        <a
          href="/memory"
          className="inline-flex min-h-9 items-center justify-center rounded-md px-3 text-xs font-medium text-slate-500 transition hover:bg-canvas hover:text-brand-purple"
        >
          {profileRefreshing ? "记录同步中" : "看看学习记录怎么变了"}
        </a>
      </div>
    </motion.section>
  );
}

export function GuidePrescriptionFeedbackNotice({
  feedback,
  onReviewReport,
  onOpenMemory,
}: {
  feedback: GuideV2LearningFeedback;
  onReviewReport: () => void;
  onOpenMemory: () => void;
}) {
  return (
    <motion.div
      className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 p-4"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18 }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={feedbackTone(feedback.tone)}>处方复测</Badge>
            {typeof feedback.score_percent === "number" ? (
              <Badge tone={effectStatusTone(feedback.score_percent)}>{Math.round(feedback.score_percent)} 分</Badge>
            ) : null}
          </div>
          <p className="mt-3 text-sm font-semibold text-ink">{feedback.title || "处方练习已回写"}</p>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-600">
            {feedback.summary || "系统已经根据这次处方练习更新学习报告和学习记录。"}
          </p>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button tone="primary" className="min-h-9 px-3 text-xs" onClick={onReviewReport}>
          <BarChart3 size={14} />
          回看报告
        </Button>
        <Button tone="secondary" className="min-h-9 px-3 text-xs" onClick={onOpenMemory}>
          <Brain size={14} />
          查看记录变化
        </Button>
      </div>
    </motion.div>
  );
}

function MinimalRemediationTaskCard({
  task,
  action,
  disabled,
  onGenerateResource,
}: {
  task: NonNullable<GuideV2LearningFeedback["remediation_task"]>;
  action: NonNullable<GuideV2LearningFeedback["resource_actions"]>[number] | null;
  disabled: boolean;
  onGenerateResource: (type: GuideV2ResourceType, taskId: string, prompt: string) => void;
}) {
  const resourceType = normalizeResourceType(action?.resource_type || task.resource_type || "visual");
  const targetTaskId = action?.target_task_id || task.target_task_id || "";
  const prompt = action?.prompt || `围绕「${task.concept || task.title || "当前薄弱点"}」生成一个最小补救资源。`;
  const canGenerate = Boolean(targetTaskId);
  return (
    <div className="mt-4 rounded-lg border border-amber-200 bg-tint-yellow p-4" data-testid="guide-minimal-remediation-task">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="warning">10 分钟补救</Badge>
            {task.concept ? <Badge tone="neutral">{task.concept}</Badge> : null}
          </div>
          <h3 className="mt-2 text-base font-semibold text-ink">{task.title || "先补齐这一小块"}</h3>
          <p className="mt-1 text-sm leading-6 text-charcoal">{task.reason || "先完成一个很小的补救复盘，再继续下一步。"}</p>
        </div>
        <Button
          tone="secondary"
          disabled={disabled || !canGenerate}
          onClick={() => {
            if (!targetTaskId) return;
            onGenerateResource(resourceType, targetTaskId, prompt);
          }}
          data-testid="guide-minimal-remediation-generate"
        >
          {guideResourceIcon(resourceType, 15)}
          开始补救
        </Button>
      </div>
      {task.steps?.length ? (
        <div className="mt-3 grid gap-2 md:grid-cols-3">
          {task.steps.slice(0, 3).map((step, index) => (
            <div key={step} className="rounded-lg border border-amber-100 bg-white/80 p-3 text-xs leading-5 text-slate-600">
              <span className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.12em] text-amber-700">Step {index + 1}</span>
              {step}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function FeedbackPathButton({
  path,
  compact = false,
  disabled,
  onGenerateResource,
  onOpenCurrentTask,
  onOpenRouteMap,
}: {
  path: FeedbackDecisionPath;
  compact?: boolean;
  disabled: boolean;
  onGenerateResource: (type: GuideV2ResourceType, taskId: string, prompt: string) => void;
  onOpenCurrentTask: () => void;
  onOpenRouteMap: () => void;
}) {
  const tone = path.primary && !compact ? "primary" : compact ? "quiet" : "secondary";
  const className = compact ? "min-h-9 px-3 text-xs" : "w-full min-h-11 justify-center text-sm";

  if (path.action.kind === "resource") {
    const action = path.action;
    return (
      <Button
        tone={tone}
        className={className}
        disabled={disabled || !action.taskId}
        onClick={() => onGenerateResource(action.resourceType, action.taskId, action.prompt)}
      >
        <Lightbulb size={compact ? 14 : 16} />
        {compact ? path.label : action.label}
      </Button>
    );
  }

  if (path.action.kind === "current_task") {
    return (
      <Button tone={tone} className={className} onClick={onOpenCurrentTask}>
        <Target size={compact ? 14 : 16} />
        {compact ? path.label : path.action.label}
      </Button>
    );
  }

  return (
    <Button tone={tone} className={className} onClick={onOpenRouteMap}>
      <Compass size={compact ? 14 : 16} />
      {compact ? path.label : path.action.label}
    </Button>
  );
}

function buildFeedbackDecision(
  feedback: GuideV2LearningFeedback,
  resourceActions: NonNullable<GuideV2LearningFeedback["resource_actions"]>,
) {
  const score = typeof feedback.score_percent === "number" ? feedback.score_percent : null;
  const normalizedActions: NormalizedFeedbackResourceAction[] = resourceActions
    .map((item) => {
      const resourceType = normalizeResourceType(item.resource_type || "visual");
      const taskId = item.target_task_id || feedback.task_id || "";
      const prompt = item.prompt || `围绕「${item.concept || feedback.task_title || "当前知识点"}」生成学习资源。`;
      const label = item.label || item.title || resourceLabel(resourceType);
      return {
        item,
        resourceType,
        taskId,
        prompt,
        label,
      };
    })
    .filter((item) => item.taskId);

  const findByKeyword = (keywords: string[]) =>
    normalizedActions.find((action) => {
      const haystack = `${action.item.action_type || ""} ${action.item.label || ""} ${action.item.title || ""}`.toLowerCase();
      return keywords.some((keyword) => haystack.includes(keyword));
    }) || null;

  const remediation = findByKeyword(["补救", "remediation"]);
  const retest = findByKeyword(["复测", "retest"]);
  const transfer = findByKeyword(["迁移", "transfer"]);
  const fallbackVisual = normalizedActions.find((action) => action.resourceType === "visual") || null;
  const fallbackQuiz = normalizedActions.find((action) => action.resourceType === "quiz") || null;
  const primaryResource = remediation || retest || transfer || fallbackVisual || fallbackQuiz || normalizedActions[0] || null;

  const resourcePath = (label: string, description: string, action: NormalizedFeedbackResourceAction | null, primary: boolean): FeedbackDecisionPath | null =>
    action
      ? {
          label,
          description,
          primary,
          action: {
            kind: "resource",
            label: action.label,
            resourceType: action.resourceType,
            taskId: action.taskId,
            prompt: action.prompt,
          },
        }
      : null;

  let badge = "继续推进";
  let tone: "success" | "brand" | "warning" = "success";
  let summary = "这次结果已经比较稳，可以直接接着做下一步。";

  const paths: FeedbackDecisionPath[] = [];

  if (score !== null && score < 60) {
    badge = "先补救";
    tone = "warning";
    summary = "这次反馈说明当前卡点还比较明显，先补错因，再做复测，会比继续堆新内容更划算。";
    const primaryPath =
      resourcePath("先补救", "先把刚暴露出来的错因和概念边界补清楚。", remediation || fallbackVisual || primaryResource, true) || {
        label: "先回到当前任务",
        description: "先回到当前任务，看清这一步究竟卡在什么地方。",
        primary: true,
        action: { kind: "current_task", label: "回到当前任务" } as FeedbackDecisionUiAction,
      };
    paths.push(primaryPath);
    if (retest || fallbackQuiz) {
      paths.push(
        resourcePath("再做复测", "补完后马上做一轮短复测，确认问题是不是真的补上了。", retest || fallbackQuiz, false)!,
      );
    }
    paths.push({
      label: "看完整路线",
      description: "如果想知道系统为什么改路线，可以去看知识地图和任务队列。",
      primary: false,
      action: { kind: "route_map", label: "查看完整路线" },
    });
  } else if (score !== null && score < 75) {
    badge = "稳一下再走";
    tone = "brand";
    summary = "这次结果已经有基础，但还不够稳。先做一轮针对性补强或短复测，再继续推进会更稳。";
    const firstChoice = retest || remediation || fallbackQuiz || fallbackVisual || primaryResource;
    paths.push(
      resourcePath("先稳住这一块", "用一轮短资源或复测把当前知识点压实，再继续推进。", firstChoice, true) || {
        label: "回到当前任务",
        description: "先回到当前任务，把刚才还不稳的地方补一句反思或再看一遍。",
        primary: true,
        action: { kind: "current_task", label: "回到当前任务" },
      },
    );
    paths.push({
      label: "继续当前任务",
      description: "如果你已经知道错在哪里，也可以直接回到任务区继续推进。",
      primary: false,
      action: { kind: "current_task", label: "去当前任务" },
    });
    paths.push({
      label: "看完整路线",
      description: "想看系统后面准备怎么安排，可以打开完整路线页。",
      primary: false,
      action: { kind: "route_map", label: "查看完整路线" },
    });
  } else {
    badge = "可以继续";
    tone = "success";
    summary = "这次结果已经比较稳，优先继续推进下一步；如果你想更扎实，也可以顺手做一轮迁移练习。";
    paths.push({
      label: "继续推进",
      description: feedback.next_task_title
        ? `系统已经准备好下一步「${feedback.next_task_title}」，可以直接继续。`
        : "继续当前路线，让系统把你带到下一步任务。",
      primary: true,
      action: { kind: "current_task", label: "去下一步任务" },
    });
    if (transfer || fallbackQuiz || fallbackVisual) {
      paths.push(
        resourcePath("顺手再巩固", "如果你想更扎实，可以再做一轮迁移练习或轻量复习。", transfer || fallbackQuiz || fallbackVisual, false)!,
      );
    }
    paths.push({
      label: "看完整路线",
      description: "如果想提前看看后面的安排，可以打开完整路线页。",
      primary: false,
      action: { kind: "route_map", label: "查看完整路线" },
    });
  }

  return { badge, tone, summary, paths: paths.slice(0, 3) };
}
