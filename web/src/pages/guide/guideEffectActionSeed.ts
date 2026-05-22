export function buildGuideEffectActionSeed({
  effectAction,
  prompt,
  actionTitle,
  sourceLabel,
  estimatedMinutes,
}: {
  effectAction: string;
  prompt: string;
  actionTitle: string;
  sourceLabel: string;
  estimatedMinutes?: number;
}) {
  const cleanAction = effectAction.trim();
  if (!cleanAction) {
    return {
      prompt,
      title: actionTitle,
      sourceLabel,
      estimatedMinutes,
      kind: "",
      targetSection: "",
    };
  }
  const [rawType, ...rest] = cleanAction.split(":");
  const type = rawType.trim().toLowerCase();
  const topic = rest.join(":").trim() || sourceLabel.trim() || "当前薄弱点";
  const targetSection = "guide-create-section";
  const actionMap: Record<string, { title: string; prompt: string; minutes: number; kind: string }> = {
    diagnostic: {
      title: "先做一次诊断",
      prompt: topic === "当前薄弱点" ? "请帮我做一次 5 题诊断，判断我当前最需要补齐哪里。" : `请围绕「${topic}」做一次 5 题诊断，判断我当前最需要补齐哪里。`,
      minutes: 8,
      kind: "learning_effect_diagnostic",
    },
    practice: {
      title: `做「${topic}」小练习`,
      prompt: `围绕「${topic}」安排一轮短导学：先用最少概念补齐直觉，再做 3 道小练习验证掌握。`,
      minutes: 10,
      kind: "learning_effect_practice",
    },
    retest: {
      title: `复测「${topic}」是否还稳`,
      prompt: `围绕「${topic}」安排一次复测导学，用 3 到 5 道题确认我是否真的掌握。`,
      minutes: 7,
      kind: "learning_effect_retest",
    },
    mistake_review: {
      title: "关闭一个反复错因",
      prompt: topic === "当前薄弱点" ? "帮我找出当前最值得处理的错因，安排一个补救任务和一次复测。" : `围绕「${topic}」帮我关闭一个反复错因，先补救再复测。`,
      minutes: 9,
      kind: "learning_effect_mistake_review",
    },
    advance: {
      title: "进入下一节或项目任务",
      prompt: topic === "当前薄弱点" ? "根据我的学习记录，安排一个下一节或小项目任务来验证迁移应用。" : `围绕「${topic}」安排一个下一节或小项目任务，验证迁移应用。`,
      minutes: 15,
      kind: "learning_effect_advance",
    },
    continue: {
      title: "继续当前学习节奏",
      prompt: topic === "当前薄弱点" ? "根据我的学习记录，继续安排一个最合适的下一步学习任务。" : `根据我的学习记录，围绕「${topic}」继续安排一个最合适的下一步学习任务。`,
      minutes: 10,
      kind: "learning_effect_continue",
    },
  };
  const seed = actionMap[type] ?? actionMap.continue;
  return {
    prompt: prompt || seed.prompt,
    title: actionTitle || seed.title,
    sourceLabel: topic === "当前薄弱点" ? sourceLabel : topic,
    estimatedMinutes: estimatedMinutes || seed.minutes,
    kind: seed.kind,
    targetSection,
  };
}
