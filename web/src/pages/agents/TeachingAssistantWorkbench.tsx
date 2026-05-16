import {
  BookOpen,
  FileText,
  Loader2,
  Play,
  Save,
  Wand2,
} from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import type {
  LearnerProfileSnapshot,
  LearningEffectNextAction,
  LearningEffectReport,
  SparkBotSummary,
} from "@/lib/types";
import {
  ASSISTANT_QUICK_ACTIONS,
  assistantActionPrompt,
  assistantEffectSummary,
  assistantProfileSummary,
  assistantPromptForLearningAction,
  pickAssistantPrimaryAction,
} from "./assistantLearningFlow";

export function TeachingAssistantWorkbench({
  bot,
  activeBotId,
  fileCount,
  historyCount,
  recentCount,
  profile,
  report,
  nextActions,
  learningLoading,
  pending,
  completePending,
  onStart,
  onUseAction,
  onOpenCapabilities,
  onOpenWorkspace,
  onCompleteAction,
}: {
  bot?: SparkBotSummary;
  activeBotId: string | null;
  fileCount: number;
  historyCount: number;
  recentCount: number;
  profile?: LearnerProfileSnapshot;
  report?: LearningEffectReport;
  nextActions: LearningEffectNextAction[];
  learningLoading: boolean;
  pending: boolean;
  completePending: boolean;
  onStart: () => void;
  onUseAction: (prompt: string) => void;
  onOpenCapabilities: () => void;
  onOpenWorkspace: () => void;
  onCompleteAction: (action: LearningEffectNextAction) => Promise<unknown>;
}) {
  const [completedActionId, setCompletedActionId] = useState("");
  const botName = bot?.name || activeBotId || "课程助教";
  const running = Boolean(bot?.running);
  const primaryAction = pickAssistantPrimaryAction(nextActions, report);
  const profileAction = profile?.next_action ?? null;
  const studyBrief = report?.study_brief ?? null;
  const actionPrompt = assistantActionPrompt(primaryAction, studyBrief, profile);
  const suggestedAction = running
    ? studyBrief?.headline || primaryAction?.title || profileAction?.title || (historyCount > 0
      ? "先复盘最近一次提问，再生成 3 道小测。"
      : fileCount > 0
        ? "先用课程资料问一个核心概念，再让助教给你出题。"
        : "先补充课程资料或学习笔记，再开始个性化答疑。")
    : "先启动当前助教，让它读取课程资料和学习记录。";
  const reason = running
    ? studyBrief?.summary || primaryAction?.reason || profileAction?.summary || (historyCount > 0
      ? `依据：当前助教已有 ${historyCount} 条最近历史，可以直接衔接上次上下文。`
      : fileCount > 0
        ? `依据：当前工作区已有 ${fileCount} 个资料文件，可以先做来源约束答疑。`
        : "依据：当前助教还缺少可复用资料，先沉淀笔记会让后续回答更稳。")
    : "依据：长期助教需要运行后才能持续接收问题、生成资源和写入记录。";
  const completeRecommendedAction = async () => {
    if (!primaryAction) return;
    setCompletedActionId("");
    await onCompleteAction(primaryAction);
    setCompletedActionId(primaryAction.id);
  };

  return (
    <section className="relative overflow-hidden rounded-lg border border-line bg-white shadow-[0_12px_34px_-30px_rgba(15,15,15,0.35)]" data-testid="teaching-assistant-workbench">
      <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="relative overflow-hidden border-b border-line bg-[linear-gradient(135deg,#fff_0%,#fbfaf8_48%,#f8f5e8_100%)] p-4 lg:border-b-0 lg:border-r">
          <div className="pointer-events-none absolute right-4 top-4 hidden h-10 w-14 rotate-2 rounded-md bg-tint-yellow opacity-80 md:block" />
          <div className="pointer-events-none absolute bottom-5 right-24 hidden h-8 w-12 -rotate-3 rounded-md bg-tint-sky opacity-75 md:block" />
          <div className="relative flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={running ? "success" : "warning"}>{running ? "助教在线" : "需要启动"}</Badge>
                <Badge tone="neutral">大模型与智能学习系统</Badge>
                {learningLoading ? <Badge tone="brand">整理画像中</Badge> : null}
              </div>
              <h2 className="mt-3 max-w-3xl text-xl font-semibold leading-7 text-ink">今天建议：{suggestedAction}</h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{reason}</p>
              {completedActionId ? (
                <p className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs leading-5 text-emerald-700">
                  已写入学习证据，画像和下一步建议会随之更新。
                </p>
              ) : null}
            </div>
            <div className="rounded-lg border border-line bg-white/88 px-3 py-2 text-right shadow-[0_1px_2px_rgba(15,15,15,0.03)]">
              <p className="text-xs text-slate-500">当前助教</p>
              <p className="mt-1 max-w-40 truncate text-sm font-semibold text-ink">{botName}</p>
            </div>
          </div>
          <div className="relative mt-4 flex flex-wrap gap-2">
            {running ? (
              <Button tone="primary" onClick={() => onUseAction(actionPrompt)} data-testid="assistant-start-learning">
                <Play size={16} />
                开始今天的学习
              </Button>
            ) : (
              <Button tone="primary" onClick={onStart} disabled={!activeBotId || pending} data-testid="assistant-start-bot">
                {pending ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
                启动助教
              </Button>
            )}
            <Button tone="secondary" onClick={onOpenCapabilities}>
              <Wand2 size={16} />
              选择能力
            </Button>
            {primaryAction ? (
              <Button tone="secondary" onClick={() => void completeRecommendedAction()} disabled={completePending} data-testid="assistant-complete-learning-action">
                {completePending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                做完后记录
              </Button>
            ) : null}
            <Button tone="quiet" onClick={onOpenWorkspace}>
              <FileText size={16} />
              资料与笔记
            </Button>
          </div>
          <div className="relative mt-4 grid gap-2 sm:grid-cols-4">
            {[
              { label: "提问", detail: "课程资料答疑", tone: "bg-tint-lavender" },
              { label: "图解", detail: "把概念可视化", tone: "bg-tint-sky" },
              { label: "小测", detail: "确认薄弱点", tone: "bg-tint-yellow" },
              { label: "回写", detail: "更新下一步", tone: "bg-tint-mint" },
            ].map((step, index) => (
              <div key={step.label} className={`rounded-lg border border-line px-3 py-2 ${step.tone}`}>
                <p className="text-xs font-semibold text-ink">{index + 1}. {step.label}</p>
                <p className="mt-1 text-xs leading-5 text-slate-600">{step.detail}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white p-4">
          <div className="flex items-center gap-2">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-line bg-tint-lavender text-brand-purple">
              <BookOpen size={17} />
            </span>
            <div className="min-w-0">
              <h3 className="text-sm font-semibold text-ink">助教会参考</h3>
              <p className="mt-0.5 text-xs text-slate-500">推荐不是凭空生成</p>
            </div>
          </div>
          <div className="mt-3 grid gap-2">
            {[
              { label: "学习画像", value: assistantProfileSummary(profile), tone: "bg-tint-lavender" },
              { label: "学习效果", value: assistantEffectSummary(report), tone: "bg-tint-mint" },
              { label: "课程资料", value: `${fileCount} 个工作区文件`, tone: "bg-tint-sky" },
              { label: "最近记录", value: `${recentCount} 个活跃助教`, tone: "bg-tint-yellow" },
            ].map((item) => (
              <div key={item.label} className={`rounded-lg border border-line px-3 py-2 ${item.tone}`}>
                <p className="text-xs font-semibold text-ink">{item.label}</p>
                <p className="mt-1 text-xs leading-5 text-slate-600">{item.value}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
      {nextActions.length ? (
        <div className="border-t border-line bg-canvas/70 p-3" data-testid="assistant-learning-next-actions">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-sm font-semibold text-ink">学习效果给出的下一步</p>
              <p className="mt-1 text-xs leading-5 text-slate-500">这些行动来自最近练习、资源反馈和画像证据。</p>
            </div>
            <Badge tone="neutral">{nextActions.length}</Badge>
          </div>
          <div className="mt-3 grid gap-2 md:grid-cols-3">
            {nextActions.slice(0, 3).map((action) => (
              <button
                key={action.id}
                type="button"
                onClick={() => onUseAction(assistantPromptForLearningAction(action))}
                className="dt-interactive rounded-lg border border-line bg-white p-3 text-left transition hover:border-brand-purple-300"
                data-testid={`assistant-next-action-${action.id}`}
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-semibold text-ink">{action.title}</span>
                  <span className="shrink-0 text-xs text-slate-500">{action.estimated_minutes || 8} 分钟</span>
                </span>
                <span className="mt-2 line-clamp-2 block text-xs leading-5 text-slate-600">{action.reason || "按当前画像推进一个最小学习动作。"}</span>
              </button>
            ))}
          </div>
        </div>
      ) : null}
      <div className="grid gap-2 border-t border-line p-3 sm:grid-cols-2 lg:grid-cols-5">
        {ASSISTANT_QUICK_ACTIONS.map((action) => {
          const Icon = action.icon;
          return (
            <button
              key={action.title}
              type="button"
              onClick={() => onUseAction(action.prompt)}
              className="dt-interactive rounded-lg border border-line bg-white p-3 text-left transition hover:border-brand-purple-300"
              data-testid={`assistant-action-${action.title}`}
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-line bg-canvas text-brand-purple">
                <Icon size={16} />
              </span>
              <span className="mt-3 block text-sm font-semibold text-ink">{action.title}</span>
              <span className="mt-1 block text-xs leading-5 text-slate-500">{action.detail}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
