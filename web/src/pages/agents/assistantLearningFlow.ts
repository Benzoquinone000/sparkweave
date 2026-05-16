import {
  Clock3,
  MessageSquareText,
  PenTool,
  Play,
  Wand2,
  type LucideIcon,
} from "lucide-react";

import type {
  LearnerProfileSnapshot,
  LearningEffectNextAction,
  LearningEffectReport,
} from "@/lib/types";

export const ASSISTANT_QUICK_ACTIONS: Array<{
  title: string;
  detail: string;
  prompt: string;
  icon: LucideIcon;
}> = [
  {
    title: "继续今天的学习",
    detail: "按画像给一步建议",
    prompt: "根据我的学习画像、最近学习记录和当前课程资料，告诉我今天最应该完成的一步，并说明依据。",
    icon: Play,
  },
  {
    title: "生成练习",
    detail: "围绕薄弱点出题",
    prompt: "围绕我最近的薄弱点生成 3 道由易到难的小测。等我作答后，请分析错因并给出下一步练习。",
    icon: PenTool,
  },
  {
    title: "看图解",
    detail: "把概念画清楚",
    prompt: "把我当前正在学的概念用图解方式讲清楚，优先给结构图、流程图或知识关系图，并说明图中每个节点的含义。",
    icon: Wand2,
  },
  {
    title: "复盘错因",
    detail: "整理错误模式和下一步",
    prompt: "复盘我最近一次学习记录，指出一个最需要巩固的概念、可能错因，以及下一步最小练习。",
    icon: Clock3,
  },
  {
    title: "语音讲解脚本",
    detail: "便于讯飞 TTS 合成",
    prompt: "请生成一段 1 分钟左右的语音讲解脚本，适合后续用讯飞语音合成。要求口语化、分层清楚，并给出一句结尾复习提醒。",
    icon: MessageSquareText,
  },
];

export function pickAssistantPrimaryAction(actions: LearningEffectNextAction[], report?: LearningEffectReport) {
  const candidates = actions.length ? actions : report?.next_actions ?? [];
  return [...candidates].sort((left, right) => Number(right.priority ?? 0) - Number(left.priority ?? 0))[0] ?? null;
}

export function assistantActionPrompt(
  action: LearningEffectNextAction | null,
  brief?: LearningEffectReport["study_brief"] | null,
  profile?: LearnerProfileSnapshot,
) {
  const agendaPrompt = brief?.agenda?.find((item) => item.prompt)?.prompt;
  return (
    action?.prompt ||
    agendaPrompt ||
    profile?.next_action?.suggested_prompt ||
    ASSISTANT_QUICK_ACTIONS[0].prompt
  );
}

export function assistantPromptForLearningAction(action: LearningEffectNextAction) {
  return (
    action.prompt ||
    `请带我完成这个学习行动：「${action.title}」。先说明为什么做它，再给出步骤，最后告诉我完成后会回写哪些学习记录。`
  );
}

export function assistantProfileSummary(profile?: LearnerProfileSnapshot) {
  if (!profile) return "等待画像";
  const focus = profile.overview?.current_focus || profile.next_action?.title;
  if (focus) return String(focus);
  const weakPoint = profile.learning_state?.weak_points?.[0]?.label;
  if (weakPoint) return `薄弱点：${weakPoint}`;
  return `证据 ${profile.data_quality?.evidence_count ?? 0} 条`;
}

export function assistantEffectSummary(report?: LearningEffectReport) {
  if (!report) return "等待评估";
  const label = report.overall?.label || "评估中";
  const count = report.summary?.event_count ?? 0;
  return `${label} · ${count} 条证据`;
}
