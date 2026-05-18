import type {
  GuideV2LearningFeedback,
  GuideV2ResourceType,
  GuideV2Session,
  GuideV2Task,
  LearnerProfileSnapshot,
} from "@/lib/types";
import type { DemoRecordingCue } from "./GuideDemoCards";
import { asRecord, readString } from "./guideDataUtils";
import { normalizeResourceType, resourceLabel } from "./guideResourceUtils";

export type GuideSubPage = "main" | "setup" | "completeTask" | "resourceChoice" | "routeMap" | "coursePackage";

export type GuideStage = "create" | "diagnostic" | "learn" | "feedback" | "complete";

export function latestLearningFeedbackFromSession(session: GuideV2Session | null, currentTaskId?: string): GuideV2LearningFeedback | null {
  if (!session || !currentTaskId) return null;
  const candidates = (session.evidence ?? [])
    .map((item) => {
      const evidence = asRecord(item);
      const metadata = asRecord(evidence?.metadata);
      const feedback = asRecord(metadata?.learning_feedback);
      if (!feedback) return null;
      const nextTaskId = readString(feedback, "next_task_id");
      const feedbackTaskId = readString(feedback, "task_id");
      const relevant = nextTaskId === currentTaskId || feedbackTaskId === currentTaskId;
      if (!relevant) return null;
      return {
        createdAt: Number(evidence?.created_at ?? 0),
        feedback: feedback as GuideV2LearningFeedback,
      };
    })
    .filter((item): item is { createdAt: number; feedback: GuideV2LearningFeedback } => Boolean(item))
    .sort((a, b) => b.createdAt - a.createdAt);
  return candidates[0]?.feedback ?? null;
}

export function buildAdaptiveGuideStrategy(
  profile: LearnerProfileSnapshot | undefined,
  stage: GuideStage,
  currentTaskTitle: string,
  feedback: GuideV2LearningFeedback | null,
) {
  const weakPointCount = profile?.learning_state.weak_points?.length || 0;
  const masteryItems = profile?.learning_state.mastery ?? [];
  const confidence = clampGuideScore(profile?.confidence ?? 0);
  const accuracy = clampGuideScore(profile?.overview.assessment_accuracy ?? 0);
  const preferences = profile?.stable_profile.preferences ?? [];
  const masteryAverage = masteryItems.length
    ? clampGuideScore(masteryItems.reduce((sum, item) => sum + clampGuideScore(item.score ?? 0), 0) / masteryItems.length)
    : 0;
  const prefersExternalVideo = preferences.some((item) => /公开视频|公开课|网课|网络视频|精选视频|外部视频|B站|bilibili|youtube/i.test(item));
  const prefersVideo = preferences.some((item) => item.includes("视频") || /video|youtube|bilibili/i.test(item));
  const prefersAudio = preferences.some((item) => item.includes("语音") || item.includes("音频") || /audio|speech|tts|podcast/i.test(item));
  const prefersPractice = preferences.some((item) => item.includes("练习"));
  const prefersVisual = preferences.some((item) => item.includes("图解"));
  const progressStyle = deriveGuideProgressStyle(preferences, weakPointCount, confidence, accuracy, masteryAverage);
  const topWeakPoints = (profile?.learning_state.weak_points ?? []).slice(0, 2).map((item) => item.label).filter(Boolean);
  const lowMasteryTopics = masteryItems
    .filter((item) => clampGuideScore(item.score ?? 0) < 0.55)
    .slice(0, 2)
    .map((item) => item.title)
    .filter(Boolean);
  const signals: Array<{ label: string; value: string; tone: "neutral" | "brand" | "success" | "warning" }> = [];
  const reasons: Array<{ label: string; detail: string }> = [];

  let recommendedResource: GuideV2ResourceType = "visual";
  let title = "先用图解把关键概念站稳";
  let summary = "当前更适合先降低理解门槛，把概念关系和判断步骤看明白，再进入练习或视频。";
  const recommendations: string[] = [];

  const feedbackScore = typeof feedback?.score_percent === "number" ? feedback.score_percent : null;

  if (stage === "feedback" && feedbackScore !== null && feedbackScore < 60) {
    recommendedResource = "visual";
    title = "先补救错因，再做一轮复测";
    summary = "刚提交的学习证据说明还有关键卡点，先用图解或补救资源把错因拆开，再进入下一轮练习更划算。";
    recommendations.push("先看图解，把错误表现、根因和正确判断条件对齐。");
    recommendations.push("看完后立刻做短练习，确认同类错误是否真的消失。");
    reasons.push({
      label: "刚提交的反馈偏低",
      detail: `这次学习反馈分数约为 ${Math.round(feedbackScore)} 分，先补错因比继续堆新内容更划算。`,
    });
  } else if (accuracy >= 0.72 && masteryAverage >= 0.65) {
    recommendedResource = "quiz";
    title = "进入迁移验证，别只停留在看懂";
    summary = "当前表现已经不差，更值得用一组混合题验证是否能稳定迁移到新场景。";
    recommendations.push("优先做练习，检查是不是已经从“会看”变成“会做”。");
    recommendations.push("如果练习仍稳定，再继续推进下一任务。");
    reasons.push({
      label: "当前基础已经够了",
      detail: `最近正确率约 ${Math.round(accuracy * 100)}%，掌握度均值约 ${Math.round(masteryAverage * 100)}%，现在更适合做迁移验证。`,
    });
  } else if (confidence < 0.45) {
    recommendedResource = prefersPractice ? "quiz" : prefersAudio ? "audio" : "visual";
    title = "先补证据，让系统判断更稳";
    summary = "系统对你当前状态还不够确定，最好先补一轮短资源和可评分证据，避免路线过深或过浅。";
    recommendations.push("优先选择能留下判断依据的资源，再提交一次明确反思。");
    recommendations.push("做完后记得提交结果，让画像判断从“猜测”变成“更确定”。");
    reasons.push({
      label: "系统判断还不够稳",
      detail: `当前画像可信度约 ${Math.round(confidence * 100)}%，先补一轮可评分证据，后面的导学才会更准。`,
    });
  } else if (prefersVideo && weakPointCount === 0 && accuracy >= 0.55) {
    recommendedResource = prefersExternalVideo ? "external_video" : "video";
    title = prefersExternalVideo ? "先找一段精选公开视频" : "可以直接用短视频加速理解";
    summary = prefersExternalVideo
      ? "你对当前任务已经有一定基础，也偏好公开视频或公开课。先看一段外部优质讲解，再回到当前任务验证，会比从零生成材料更省力。"
      : "你对当前任务已经有一定基础，且偏好视频形式，用短视频快速串起步骤会更省力。";
    recommendations.push(prefersExternalVideo ? "先看一段精选公开视频，把另一个讲解视角补上，再回到当前任务。" : "先看短视频把整体流程串起来，再回到当前任务。");
    recommendations.push("看完后补一组小练习，避免只停留在“看过”。");
    reasons.push({
      label: "你的偏好更适合视频",
      detail: prefersExternalVideo
        ? "当前没有明显薄弱点堆积，而且画像里记录到你偏好公开视频、公开课或外部视频资源。"
        : "当前没有明显薄弱点堆积，而且画像里记录到你更愿意通过短视频快速建立整体感。",
    });
  } else if (prefersAudio && accuracy < 0.72) {
    recommendedResource = "audio";
    title = "先听一遍讲解，把关键步骤串起来";
    summary = "你当前更适合先用一段短语音把概念和步骤听顺，再回到图解或练习确认掌握。";
    recommendations.push("先听 1 到 2 分钟的讲解，抓住概念、步骤和下一步动作。");
    recommendations.push("听完后立刻去做一组短练习或回到提交页，别只停在听懂。");
    reasons.push({
      label: "你适合先听后做",
      detail: "画像里已经出现音频或语音偏好，所以这里优先用更轻的讲解方式降低进入门槛。",
    });
  } else if (prefersPractice && accuracy >= 0.45) {
    recommendedResource = "quiz";
    title = "边做边学会更适合你";
    summary = "你已经具备一定起点，而且偏好练习型资源，此时直接做题比继续堆解释更有效。";
    recommendations.push("先做一组短练习，暴露真正不稳的知识点。");
    recommendations.push("练完再决定是否需要图解或视频补救。");
    reasons.push({
      label: "你更适合先动手",
      detail: "画像里记录到你偏好练习驱动的学习方式，所以这里优先让你边做边校准。",
    });
  } else if (prefersVisual || weakPointCount > 0) {
    recommendedResource = "visual";
    title = "先把卡点画清楚，再推进任务";
    summary = "当前仍有薄弱点或概念边界不清，图解最适合先把结构理顺。";
    recommendations.push("重点关注概念关系、判断条件和一个最小例子。");
    recommendations.push("看完后尽快进入提交页，让系统根据结果调整下一步。");
    reasons.push({
      label: "先拆结构比硬做题更值",
      detail: "当前画像里还有待补强的薄弱点，先把概念边界和判断关系看清楚，后面会更顺。",
    });
  }

  if (currentTaskTitle) {
    recommendations.unshift(`当前这一步围绕「${currentTaskTitle}」展开，不需要额外切换任务。`);
  }

  if (weakPointCount > 0) {
    signals.push({
      label: "薄弱点",
      value: topWeakPoints.length ? topWeakPoints.join("、") : `${weakPointCount} 个待补强点`,
      tone: weakPointCount >= 2 ? "warning" : "brand",
    });
    reasons.push({
      label: "当前主要卡点",
      detail: topWeakPoints.length
        ? `系统最近反复捕捉到你在「${topWeakPoints.join("、")}」上不够稳，所以先围绕这些点补。`
        : `系统最近记录到 ${weakPointCount} 个待补强点，先做聚焦补基更合适。`,
    });
  }

  if (lowMasteryTopics.length) {
    signals.push({
      label: "掌握偏低",
      value: lowMasteryTopics.join("、"),
      tone: "warning",
    });
  } else if (masteryItems.length) {
    signals.push({
      label: "掌握度",
      value: `${Math.round(masteryAverage * 100)}%`,
      tone: masteryAverage >= 0.7 ? "success" : "brand",
    });
  }

  if (preferences.length) {
    const preferredMode = prefersPractice ? "练习" : prefersVideo ? "短视频" : prefersAudio ? "语音讲解" : prefersVisual ? "图解" : preferences[0];
    signals.push({
      label: "学习偏好",
      value: preferredMode,
      tone: "neutral",
    });
  }

  if (progressStyle) {
    signals.push({
      label: "推进风格",
      value: progressStyle.label,
      tone: "brand",
    });
    reasons.push({
      label: "你的推进方式",
      detail: progressStyle.detail,
    });
  }

  if (confidence > 0) {
    signals.push({
      label: "画像可信度",
      value: `${Math.round(confidence * 100)}%`,
      tone: confidence >= 0.7 ? "success" : confidence >= 0.45 ? "brand" : "warning",
    });
  }

  if (accuracy > 0) {
    signals.push({
      label: "近期正确率",
      value: `${Math.round(accuracy * 100)}%`,
      tone: accuracy >= 0.72 ? "success" : accuracy >= 0.5 ? "brand" : "warning",
    });
  }

  return {
    title,
    summary,
    recommendations,
    reasons,
    signals,
    recommendedResource,
  };
}

export function buildGuideTrendNotice(
  profile: LearnerProfileSnapshot | undefined,
  stage: GuideStage,
) {
  if (!profile) return null;
  const recentEvidence = (profile.evidence_preview ?? []).slice(0, 5);
  const weakPoints = profile.learning_state?.weak_points ?? [];
  const scores = recentEvidence
    .map((item) => (typeof item.score === "number" ? clampGuideScore(item.score) : null))
    .filter((item): item is number => item !== null);
  const averageScore = scores.length ? scores.reduce((sum, item) => sum + item, 0) / scores.length : null;
  const recentText = recentEvidence.map((item) => `${item.source_label} ${item.title} ${item.summary || ""}`).join(" ");
  const hasCalibration = /校准|画像|profile/i.test(recentText);
  const hasQuiz = /练习|答题|quiz|题目/i.test(recentText);
  const hasResource = /图解|视频|语音|音频|资源|visual|video|audio|speech/i.test(recentText);
  const stageVerb =
    stage === "create"
      ? "这次导学会先按这个节奏起步。"
      : stage === "diagnostic"
        ? "所以这次前测更像是在校准起点。"
        : stage === "feedback"
          ? "所以现在先看反馈再决定要不要补救。"
          : stage === "complete"
            ? "所以复盘时更值得看这轮节奏有没有跑顺。"
            : "所以当前任务会优先沿这个节奏推进。";

  const cues = [
    hasQuiz ? "最近有练习反馈" : "",
    hasCalibration ? "最近有显式校准" : "",
    hasResource ? "最近有资源使用" : "",
    averageScore !== null ? `最近证据均值 ${Math.round(averageScore * 100)}%` : "",
  ].filter(Boolean);

  if (hasCalibration || (averageScore !== null && averageScore < 0.6)) {
    return {
      label: "最近更像在修正路径",
      tone: "warning" as const,
      summary: `你最近更适合先补清错因、再确认理解，而不是一下子推进太快。${stageVerb}`,
      guideHint: "进入导学后，系统会更偏向补基、图解和复测，而不是直接堆更多新任务。",
      cues,
    };
  }

  if (averageScore !== null && averageScore >= 0.78 && hasQuiz) {
    return {
      label: "最近正在变稳",
      tone: "success" as const,
      summary: `你最近几次练习和任务证据已经比较稳定，可以少一点铺垫，多一点直接验证。${stageVerb}`,
      guideHint: "进入导学后，系统会更敢把重心放到练习推进和迁移应用上。",
      cues,
    };
  }

  if (hasResource && hasQuiz && averageScore !== null && averageScore >= 0.62) {
    return {
      label: "最近开始提速",
      tone: "brand" as const,
      summary: `你最近的资源使用和练习反馈衔接得更顺，可以在现有基础上稍微加快一点节奏。${stageVerb}`,
      guideHint: "进入导学后，系统会尽量减少重复解释，把更多时间留给当前任务和结果验证。",
      cues,
    };
  }

  if (weakPoints.length) {
    return {
      label: "当前仍以聚焦补强为主",
      tone: "brand" as const,
      summary: `系统最近仍持续捕捉到「${weakPoints.slice(0, 2).map((item) => item.label).join("、")}」这些卡点，所以这次更适合先聚焦补强。${stageVerb}`,
      guideHint: "进入导学后，系统会先围绕薄弱点安排更小、更聚焦的动作。",
      cues,
    };
  }

  return {
    label: "系统仍在继续观察",
    tone: "brand" as const,
    summary: `你的学习节奏正在逐步成形，但系统还在继续观察哪种带学方式最稳。${stageVerb}`,
    guideHint: "这次导学会先保持轻量节奏，根据新的练习和反馈再进一步收紧推荐。",
    cues,
  };
}

export function buildDemoRecordingCue({
  enabled,
  guideStage,
  guideSubPage,
  currentTask,
  currentDemoStep,
  generatingType,
  artifactCount,
}: {
  enabled: boolean;
  guideStage: GuideStage;
  guideSubPage: GuideSubPage;
  currentTask: GuideV2Task | null;
  currentDemoStep: Record<string, unknown> | null;
  generatingType: GuideV2ResourceType | null;
  artifactCount: number;
}): DemoRecordingCue | null {
  if (!enabled || guideSubPage !== "main") {
    return null;
  }

  if (generatingType) {
    return {
      title: `等待${resourceLabel(generatingType)}准备好`,
      detail: "录屏时可以讲：系统正在按画像、当前任务和资源偏好调度资源生成智能体。",
      actionLabel: "准备中",
      action: "none",
      tone: "brand",
    };
  }

  if (guideStage === "learn" && currentTask) {
    const prompt = currentDemoStep ? readString(currentDemoStep, "prompt") : "";
    const resourceType = currentDemoStep ? normalizeResourceType(readString(currentDemoStep, "resource_type")) : null;
    if (artifactCount > 0) {
      return {
        title: "学完素材后提交一句反馈",
        detail: "录屏时可以讲：学生不需要填复杂表格，只要给出掌握状态和一句反思，系统就能回写画像。",
        actionLabel: "去提交",
        action: "open_complete_task",
        tone: "success",
      };
    }
    if (prompt && resourceType) {
      return {
        title: `先生成${resourceLabel(resourceType)}`,
        detail: "录屏时可以讲：这个提示词来自稳定 Demo 任务链，避免现场临时想提示词导致结果飘。",
        actionLabel: "生成稳定素材",
        action: "generate_current_seed",
        tone: "brand",
      };
    }
    return {
      title: "先完成当前任务",
      detail: "录屏时可以讲：导学页始终只把当前最该做的一件事放在前面。",
      actionLabel: "去提交",
      action: "open_complete_task",
      tone: "brand",
    };
  }

  if (guideStage === "feedback") {
    return {
      title: "反馈已经回写，接着展示产出包",
      detail: "录屏时可以讲：刚刚的分数和反思已经进入画像，接下来用产出包证明闭环完整。",
      actionLabel: "看产出包",
      action: "open_course_package",
      tone: "success",
    };
  }

  if (guideStage === "complete") {
    return {
      title: "最后展示课程产出包",
      detail: "录屏时可以讲：系统把路线、资源、反馈、报告整理成可提交的课程学习成果。",
      actionLabel: "看产出包",
      action: "open_course_package",
      tone: "success",
    };
  }

  return null;
}

function clampGuideScore(value: number) {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(1, value));
}

function deriveGuideProgressStyle(
  preferences: string[],
  weakPointCount: number,
  confidence: number,
  accuracy: number,
  masteryAverage: number,
) {
  const prefersVideo = preferences.some((item) => item.includes("视频"));
  const prefersAudio = preferences.some((item) => item.includes("语音") || item.includes("音频"));
  const prefersPractice = preferences.some((item) => item.includes("练习"));
  const prefersVisual = preferences.some((item) => item.includes("图解"));

  if (prefersPractice && accuracy >= 0.55 && masteryAverage >= 0.5) {
    return {
      label: "练习驱动型",
      detail: "你更像是先通过练习暴露真实卡点，再用反馈把理解压实，所以这里更适合先动手而不是继续堆解释。",
    };
  }
  if (prefersVisual && weakPointCount > 0) {
    return {
      label: "概念澄清型",
      detail: "你更适合先把概念关系和边界看清楚，再进入练习；所以当前优先图解会更顺。",
    };
  }
  if (prefersVideo && weakPointCount === 0 && confidence >= 0.55) {
    return {
      label: "快速串联型",
      detail: "当基础已经够用时，你更适合先用短视频把流程串起来，再回到任务区完成验证。",
    };
  }
  if (prefersAudio && confidence < 0.75) {
    return {
      label: "先听后做型",
      detail: "你更适合先用一段简洁语音把概念和步骤听顺，再回到图解或练习完成验证。",
    };
  }
  if (confidence < 0.5) {
    return {
      label: "反复校准型",
      detail: "你当前更依赖短资源、可评分证据和连续反馈来帮助系统收敛判断，所以这一步会更看重补证据。",
    };
  }
  return {
    label: "渐进压实型",
    detail: "你更像是先获得一个大致理解，再通过练习、反馈和补强把知识一点点压实，所以系统会采用稳步推进的节奏。",
  };
}
