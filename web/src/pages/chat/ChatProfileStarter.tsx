import { motion } from "framer-motion";
import { BookOpenCheck, FileQuestion, ImageIcon, Lightbulb, PlayCircle, Route, UploadCloud, type LucideIcon } from "lucide-react";

import type { CapabilityId, LearningEffectNextAction, LearnerProfileSnapshot } from "@/lib/types";
import {
  capabilityFromLearningEffectAction,
  cleanText,
  configFromLearningEffectAction,
  guideHref,
  knowledgeBasesFromLearningEffectAction,
  profileTopic,
  promptFromLearningEffectAction,
} from "./chatPageUtils";

export function ChatProfileStarter({
  profile,
  learningEffectAction,
  knowledgeBases,
  disabled,
  onQuickSend,
}: {
  profile?: LearnerProfileSnapshot;
  learningEffectAction?: LearningEffectNextAction | null;
  knowledgeBases: string[];
  disabled: boolean;
  onQuickSend: (
    content: string,
    capability?: CapabilityId,
    config?: Record<string, unknown>,
    options?: { knowledgeBases?: string[] },
  ) => void;
}) {
  const action = profile?.next_action;
  const directStartKnowledgeBases = knowledgeBasesFromLearningEffectAction(learningEffectAction);
  const selectedKnowledgeBases = directStartKnowledgeBases.length ? directStartKnowledgeBases : knowledgeBases;
  const hasKnowledgeContext = selectedKnowledgeBases.length > 0;
  const hasRecommendation = Boolean(learningEffectAction || action || profile);
  const title =
    cleanText(learningEffectAction?.title) ||
    cleanText(action?.title) ||
    (hasKnowledgeContext ? "先问一个具体问题" : "先从一个问题开始");
  const summary =
    cleanText(learningEffectAction?.reason) ||
    cleanText(action?.summary) ||
    cleanText(profile?.overview.summary) ||
    (hasKnowledgeContext
      ? "已选择资料库。你可以直接问概念、段落、公式或让它整理重点。"
      : "可以直接在下方输入问题；如果想围绕课件、笔记或论文提问，先上传资料会更稳。");
  const minutes = Number(learningEffectAction?.estimated_minutes || action?.estimated_minutes || profile?.overview.preferred_time_budget_minutes || 10);
  const actions = quickActionsForProfile(profile, hasKnowledgeContext);
  const directStartCapability = capabilityFromLearningEffectAction(learningEffectAction);
  const directStartConfig = configFromLearningEffectAction(learningEffectAction);
  const directStartPrompt =
    promptFromLearningEffectAction(learningEffectAction) ||
    (profile
      ? "继续学习"
      : hasKnowledgeContext
        ? "请先概括当前资料库最核心的内容，并给我三个可以继续追问的问题。"
        : `请帮我梳理一个 20 分钟的学习起步计划，主题是：${profileTopic(profile)}`);

  return (
    <motion.div
      className="mx-auto w-full max-w-3xl py-3 sm:py-4"
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, ease: "easeOut" }}
      data-testid="chat-profile-starter"
    >
      <section className="rounded-lg border border-line bg-white p-3.5 shadow-[0_6px_18px_rgba(15,15,15,0.03)] sm:p-4">
        <div className="grid gap-3.5 lg:grid-cols-[minmax(0,1fr)_250px]">
          <div className="min-w-0">
            <p className="text-xs font-semibold text-steel">现在可以问</p>
            <h2 className="mt-1.5 max-w-2xl text-xl font-semibold leading-tight text-ink sm:text-2xl">
              {hasKnowledgeContext ? "你想问这份资料的哪一部分？" : "你想先解决什么问题？"}
            </h2>
            <p className="mt-2 max-w-2xl text-xs leading-5 text-slate-500">
              {hasKnowledgeContext
                ? "直接输入问题即可。需要限定资料库、学习记录或回答方式时，点右下方的“资料与偏好”。"
                : "可以直接提问；如果问题来自课件或论文，先上传资料，回答会更有依据。"}
            </p>
            <div className="mt-4 grid gap-2 sm:grid-cols-2">
              {actions.map((item) => (
                <QuickActionButton key={item.id} action={item} disabled={disabled} onQuickSend={onQuickSend} />
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-line bg-[#fbfbfa] p-3">
            <p className="text-xs font-semibold text-steel">当前建议</p>
            <h3 className="mt-1.5 text-sm font-semibold leading-5 text-ink">{title}</h3>
            <p className="mt-1.5 line-clamp-4 text-xs leading-5 text-slate-500">{summary}</p>
            <div className="mt-2.5 flex flex-wrap gap-1.5 text-xs text-slate-500">
              <span className="rounded-md border border-line bg-white px-2 py-1">{Math.max(3, minutes)} 分钟</span>
              {directStartKnowledgeBases.length ? (
                <span className="max-w-full truncate rounded-md border border-line bg-white px-2 py-1">
                  {directStartKnowledgeBases[0]}
                </span>
              ) : hasKnowledgeContext ? (
                <span className="max-w-full truncate rounded-md border border-line bg-white px-2 py-1">
                  {selectedKnowledgeBases[0]}
                </span>
              ) : null}
            </div>
            <div className="mt-3 grid gap-2">
              {hasRecommendation || hasKnowledgeContext ? (
                <motion.button
                  type="button"
                  data-testid="chat-profile-start"
                  disabled={disabled}
                  className="dt-interactive inline-flex min-h-9 items-center justify-center gap-2 rounded-lg bg-ink px-3 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
                  onClick={() =>
                    onQuickSend(directStartPrompt, directStartCapability, directStartConfig, {
                      knowledgeBases: selectedKnowledgeBases.length ? selectedKnowledgeBases : undefined,
                    })
                  }
                  whileHover={disabled ? undefined : { y: -1 }}
                  whileTap={disabled ? undefined : { scale: 0.99 }}
                >
                  <BookOpenCheck size={16} />
                  {hasRecommendation ? "按画像继续" : "概括资料"}
                </motion.button>
              ) : (
                <motion.a
                  href="/guide"
                  data-testid="chat-profile-start"
                  className="dt-interactive inline-flex min-h-9 items-center justify-center gap-2 rounded-lg bg-ink px-3 text-sm font-medium text-white"
                  whileHover={{ y: -1 }}
                  whileTap={{ scale: 0.99 }}
                >
                  <Route size={16} />
                  生成学习路线
                </motion.a>
              )}
              <motion.a
                href={hasKnowledgeContext ? learningEffectAction?.href || guideHref(profile) : "/knowledge/create"}
                data-testid="chat-profile-guide"
                className="dt-interactive inline-flex min-h-9 items-center justify-center gap-2 rounded-lg border border-line bg-white px-3 text-sm font-medium text-charcoal hover:bg-canvas"
                whileHover={{ y: -1 }}
                whileTap={{ scale: 0.99 }}
              >
                {hasKnowledgeContext ? <Route size={16} /> : <UploadCloud size={16} />}
                {hasKnowledgeContext ? "进入导学" : "先上传资料"}
              </motion.a>
            </div>
          </div>
        </div>
      </section>
    </motion.div>
  );
}

function quickActionsForProfile(profile: LearnerProfileSnapshot | undefined, hasKnowledgeContext: boolean) {
  const topic = profileTopic(profile);
  return [
    {
      id: "explain",
      label: hasKnowledgeContext ? "解释资料" : "讲清卡点",
      description: hasKnowledgeContext ? "用资料里的依据解释概念。" : "用直觉、例子和一个自测题解释。",
      icon: Lightbulb,
      capability: "chat" as const,
      prompt: hasKnowledgeContext
        ? "请结合已选择资料，解释我最应该先理解的核心概念。先讲直觉，再列出资料依据，最后给一个自测问题。"
        : `请结合我的学习画像，用 5 分钟能读完的方式讲清楚：${topic}。先解释直觉，再给一个例子，最后给我一个自测问题。`,
    },
    {
      id: "practice",
      label: hasKnowledgeContext ? "根据资料出题" : "生成练习",
      description: "选择、判断、填空和简答混合。",
      icon: FileQuestion,
      capability: "deep_question" as const,
      prompt: hasKnowledgeContext
        ? "请围绕已选择资料生成 5 道练习题，包含选择题、判断题、填空题和简答题，并给出答案解析。"
        : `围绕「${topic}」生成 5 道交互式练习题，包含选择题、判断题、填空题和简答题，并给出答案解析。`,
      config: {
        mode: "custom",
        topic: hasKnowledgeContext ? "当前资料" : topic,
        num_questions: 5,
        difficulty: "auto",
        question_type: "mixed",
      },
    },
    {
      id: "video",
      label: hasKnowledgeContext ? "找补充视频" : "找公开视频",
      description: "筛 3 个适合当前水平的视频。",
      icon: PlayCircle,
      capability: "chat" as const,
      prompt: hasKnowledgeContext
        ? "请根据已选择资料的主题，从网络上推荐 3 个适合当前水平的公开视频，并说明为什么适合我。"
        : `请从网络上帮我推荐适合当前水平的公开视频，主题是「${topic}」。只给 3 个最适合的，并说明为什么适合我。`,
    },
    {
      id: "visual",
      label: hasKnowledgeContext ? "整理重点" : "画图解",
      description: hasKnowledgeContext ? "提炼资料结构和关键概念。" : "把概念关系画成一张图。",
      icon: ImageIcon,
      capability: hasKnowledgeContext ? ("chat" as const) : ("visualize" as const),
      prompt: hasKnowledgeContext
        ? "请把已选择资料整理成一份重点提纲：先列主题结构，再标出最重要概念、易错点和建议阅读顺序。"
        : `请为「${topic}」生成一张简洁的学习图解，突出概念关系、关键步骤和最容易混淆的点。`,
      config: hasKnowledgeContext ? undefined : { render_mode: "auto" },
    },
  ];
}

function QuickActionButton({
  action,
  disabled,
  onQuickSend,
}: {
  action: ReturnType<typeof quickActionsForProfile>[number];
  disabled: boolean;
  onQuickSend: (
    content: string,
    capability?: CapabilityId,
    config?: Record<string, unknown>,
    options?: { knowledgeBases?: string[] },
  ) => void;
}) {
  const Icon = action.icon as LucideIcon;
  const tone = quickActionTone(action.id);
  return (
    <motion.button
      type="button"
      disabled={disabled}
      data-testid={`chat-profile-action-${action.id}`}
      className={`dt-interactive flex min-h-12 items-start gap-2.5 rounded-lg border p-2 text-left text-ink disabled:cursor-not-allowed disabled:opacity-50 ${tone.card}`}
      onClick={() => onQuickSend(action.prompt, action.capability, action.config)}
      whileHover={disabled ? undefined : { y: -1 }}
      whileTap={disabled ? undefined : { scale: 0.99 }}
    >
      <span className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md ${tone.icon}`}>
        <Icon size={15} />
      </span>
      <span className="min-w-0">
        <span className="block text-xs font-semibold text-ink">{action.label}</span>
        <span className="mt-1 block text-xs leading-5 text-slate-500">{action.description}</span>
      </span>
    </motion.button>
  );
}

function quickActionTone(actionId: string) {
  const tones: Record<string, { card: string; icon: string }> = {
    explain: {
      card: "border-line bg-white hover:border-[#c8c4be] hover:bg-canvas",
      icon: "bg-tint-sky text-brand-blue",
    },
    practice: {
      card: "border-line bg-white hover:border-[#c8c4be] hover:bg-canvas",
      icon: "bg-tint-yellow text-brand-orange",
    },
    video: {
      card: "border-line bg-white hover:border-[#c8c4be] hover:bg-canvas",
      icon: "bg-tint-rose text-brand-pink",
    },
    visual: {
      card: "border-line bg-white hover:border-[#c8c4be] hover:bg-canvas",
      icon: "bg-tint-mint text-brand-teal",
    },
  };
  return tones[actionId] ?? { card: "border-line bg-white hover:border-brand-purple-300", icon: "bg-canvas text-brand-purple" };
}
