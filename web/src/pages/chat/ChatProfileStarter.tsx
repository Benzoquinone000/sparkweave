import { motion } from "framer-motion";
import { BookOpenCheck, FileQuestion, ImageIcon, Lightbulb, PlayCircle, Route, Sparkles, type LucideIcon } from "lucide-react";

import { capabilityLabel } from "@/lib/capabilities";
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
  activeCapability,
  profile,
  learningEffectAction,
  disabled,
  onQuickSend,
}: {
  activeCapability: string;
  profile?: LearnerProfileSnapshot;
  learningEffectAction?: LearningEffectNextAction | null;
  disabled: boolean;
  onQuickSend: (
    content: string,
    capability?: CapabilityId,
    config?: Record<string, unknown>,
    options?: { knowledgeBases?: string[] },
  ) => void;
}) {
  const action = profile?.next_action;
  const title = cleanText(learningEffectAction?.title) || cleanText(action?.title) || `${profileTopic(profile)}：先迈出一步`;
  const summary =
    cleanText(learningEffectAction?.reason) ||
    cleanText(action?.summary) ||
    cleanText(profile?.overview.summary) ||
    "我会根据你的画像和当前问题，自动选择答疑、练习、图解、视频或导学路径。你只需要点一下，或者直接输入问题。";
  const minutes = Number(learningEffectAction?.estimated_minutes || action?.estimated_minutes || profile?.overview.preferred_time_budget_minutes || 10);
  const actions = quickActionsForProfile(profile);
  const directStartCapability = capabilityFromLearningEffectAction(learningEffectAction);
  const directStartConfig = configFromLearningEffectAction(learningEffectAction);
  const directStartKnowledgeBases = knowledgeBasesFromLearningEffectAction(learningEffectAction);
  const directStartPrompt =
    promptFromLearningEffectAction(learningEffectAction) ||
    (profile ? "继续学习" : `请根据我的学习画像，安排我下一步学习：${profileTopic(profile)}`);

  return (
    <motion.div
      className="mx-auto w-full max-w-5xl py-5 sm:py-7"
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, ease: "easeOut" }}
      data-testid="chat-profile-starter"
    >
      <section className="dt-notion-hero p-5 sm:p-6 lg:p-8">
        <img
          src="/illustrations/notion-note-yellow.svg"
          alt=""
          aria-hidden="true"
          className="dt-hero-note pointer-events-none absolute left-10 top-8 hidden h-10 w-14 sm:block"
        />
        <img
          src="/illustrations/notion-note-pink.svg"
          alt=""
          aria-hidden="true"
          className="dt-hero-note pointer-events-none absolute right-14 top-10 hidden h-10 w-14 md:block"
        />

        <div className="relative z-10 mx-auto max-w-3xl text-center">
          <motion.div
            className="mx-auto mb-3 inline-flex h-12 w-12 items-center justify-center rounded-lg border border-white/10 bg-white/10 text-white shadow-[rgba(255,255,255,0.08)_0_1px_0_inset]"
            animate={{ y: [0, -3, 0] }}
            transition={{ duration: 3.2, repeat: Infinity, ease: "easeInOut" }}
          >
            <Sparkles size={24} />
          </motion.div>
          <p className="text-sm font-semibold text-brand-purple-300">今天先做这一步</p>
          <h2 className="mx-auto mt-3 max-w-3xl text-3xl font-semibold leading-tight text-white sm:text-4xl">{title}</h2>
          <p className="mx-auto mt-3 max-w-2xl text-sm leading-6 text-white/75">{summary}</p>
          <div className="mt-4 flex flex-wrap justify-center gap-2 text-xs text-white/75">
            <span className="rounded-lg border border-white/10 bg-white/10 px-3 py-1.5">{Math.max(3, minutes)} 分钟</span>
            <span className="rounded-lg border border-white/10 bg-white/10 px-3 py-1.5">默认：{capabilityLabel(activeCapability)}</span>
            {profile?.confidence ? (
              <span className="rounded-lg border border-white/10 bg-white/10 px-3 py-1.5">
                画像可信度 {Math.round(profile.confidence * 100)}%
              </span>
            ) : null}
            {directStartKnowledgeBases.length ? (
              <span className="rounded-lg border border-white/10 bg-white/10 px-3 py-1.5">
                资料库：{directStartKnowledgeBases[0]}
              </span>
            ) : null}
          </div>
          <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
            <motion.a
              href={learningEffectAction?.href || guideHref(profile)}
              data-testid="chat-profile-guide"
              className="dt-interactive inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-brand-purple px-[18px] text-sm font-medium text-white shadow-[rgba(86,69,212,0.18)_0_1px_2px] hover:bg-brand-purple-800"
              whileHover={{ y: -1 }}
              whileTap={{ scale: 0.99 }}
            >
              <Route size={16} />
              进入导学
            </motion.a>
            <motion.button
              type="button"
              data-testid="chat-profile-start"
              disabled={disabled}
              className="dt-interactive inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-white/25 bg-white px-[18px] text-sm font-medium text-ink hover:border-white disabled:cursor-not-allowed disabled:opacity-60"
              onClick={() =>
                onQuickSend(directStartPrompt, directStartCapability, directStartConfig, {
                  knowledgeBases: directStartKnowledgeBases.length ? directStartKnowledgeBases : undefined,
                })
              }
              whileHover={disabled ? undefined : { y: -1 }}
              whileTap={disabled ? undefined : { scale: 0.99 }}
            >
              <BookOpenCheck size={16} />
              按画像继续
            </motion.button>
          </div>
        </div>

        <div className="dt-workspace-mockup relative z-10 mx-auto mt-7 max-w-4xl text-ink">
          <div className="grid gap-0 md:grid-cols-[210px_minmax(0,1fr)]">
            <div className="border-b border-line bg-[#fbfbfa] p-4 md:border-b-0 md:border-r">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-navy text-white">
                  <Sparkles size={18} />
                </div>
                <div>
                  <p className="text-sm font-semibold text-ink">SparkWeave</p>
                  <p className="text-xs text-steel">学习空间</p>
                </div>
              </div>
              <div className="mt-5 space-y-2">
                {["当前对话", "导学路线", "学习画像"].map((item, index) => (
                  <div key={item} className="dt-editor-line text-sm text-charcoal">
                    <span
                      className={`h-2.5 w-2.5 ${index === 0 ? "bg-brand-purple" : index === 1 ? "bg-brand-teal" : "bg-brand-orange"}`}
                      style={{ borderRadius: "50%" }}
                    />
                    {item}
                  </div>
                ))}
              </div>
            </div>
            <div className="p-4">
              <div className="dt-feature-tile dt-feature-tile-yellow flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-ink">先补齐当前短点</p>
                  <p className="mt-1 text-xs leading-5 text-charcoal">只围绕这一件事生成讲解、练习和反馈。</p>
                </div>
                <span className="rounded-lg bg-brand-yellow px-3 py-2 text-xs font-semibold text-ink">开始学习 →</span>
              </div>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                {actions.map((item) => (
                  <QuickActionButton key={item.id} action={item} disabled={disabled} onQuickSend={onQuickSend} />
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>
    </motion.div>
  );
}

function quickActionsForProfile(profile?: LearnerProfileSnapshot) {
  const topic = profileTopic(profile);
  return [
    {
      id: "explain",
      label: "讲清卡点",
      description: "用直觉、例子和一个自测题解释。",
      icon: Lightbulb,
      capability: "chat" as const,
      prompt: `请结合我的学习画像，用 5 分钟能读完的方式讲清楚：${topic}。先解释直觉，再给一个例子，最后给我一个自测问题。`,
    },
    {
      id: "practice",
      label: "生成练习",
      description: "选择、判断、填空和简答混合。",
      icon: FileQuestion,
      capability: "deep_question" as const,
      prompt: `围绕「${topic}」生成 5 道交互式练习题，包含选择题、判断题、填空题和简答题，并给出答案解析。`,
      config: {
        mode: "custom",
        topic,
        num_questions: 5,
        difficulty: "auto",
        question_type: "mixed",
      },
    },
    {
      id: "video",
      label: "找公开视频",
      description: "筛 3 个适合当前水平的视频。",
      icon: PlayCircle,
      capability: "chat" as const,
      prompt: `请从网络上帮我推荐适合当前水平的公开视频，主题是「${topic}」。只给 3 个最适合的，并说明为什么适合我。`,
    },
    {
      id: "visual",
      label: "画图解",
      description: "把概念关系画成一张图。",
      icon: ImageIcon,
      capability: "visualize" as const,
      prompt: `请为「${topic}」生成一张简洁的学习图解，突出概念关系、关键步骤和最容易混淆的点。`,
      config: { render_mode: "auto" },
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
      className={`dt-interactive flex min-h-[54px] items-start gap-3 rounded-lg border p-2.5 text-left text-ink disabled:cursor-not-allowed disabled:opacity-50 ${tone.card}`}
      onClick={() => onQuickSend(action.prompt, action.capability, action.config)}
      whileHover={disabled ? undefined : { y: -1 }}
      whileTap={disabled ? undefined : { scale: 0.99 }}
    >
      <span className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${tone.icon}`}>
        <Icon size={16} />
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-semibold text-ink">{action.label}</span>
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
