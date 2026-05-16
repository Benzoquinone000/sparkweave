import type { LearnerProfileSnapshot } from "@/lib/types";

export type LearningProgressStyle = {
  label: string;
  summary: string;
  confidenceText: string;
  signals: Array<{ label: string; detail: string; tone: "success" | "brand" | "warning" }>;
  suggestions: string[];
  recentShift?: {
    label: string;
    summary: string;
    direction: "stable" | "accelerating" | "correcting" | "observing";
    cues: string[];
  } | null;
};

function profileConfidenceLabel(confidence: number, accuracy: number) {
  if (confidence >= 0.75 && accuracy >= 0.55) return "系统比较有把握";
  if (confidence >= 0.5) return "仍在继续校准";
  return "先轻量观察";
}

export function buildLearningProgressStyle(profile: LearnerProfileSnapshot): LearningProgressStyle {
  const preferences = profile.stable_profile.preferences ?? [];
  const masteryItems = profile.learning_state.mastery ?? [];
  const weakPoints = profile.learning_state.weak_points ?? [];
  const evidenceItems = profile.evidence_preview ?? [];
  const calibrationCount = Number(profile.data_quality.calibration_count ?? 0);
  const confidence = clampScore(profile.confidence ?? 0);
  const accuracy = clampScore(profile.overview.assessment_accuracy ?? 0);
  const masteryAverage = masteryItems.length
    ? clampScore(masteryItems.reduce((sum, item) => sum + clampScore(item.score ?? 0), 0) / masteryItems.length)
    : 0;
  const scoredEvidence = evidenceItems.filter((item) => item.score !== null && item.score !== undefined);
  const evidenceAverage = scoredEvidence.length
    ? clampScore(scoredEvidence.reduce((sum, item) => sum + clampScore(item.score ?? 0), 0) / scoredEvidence.length)
    : 0;

  const prefersPractice = preferences.some((item) => /practice|练习|题/.test(item));
  const prefersVisual = preferences.some((item) => /visual|图解|图|示意/.test(item));
  const prefersVideo = preferences.some((item) => /video|视频/.test(item));

  let label = "渐进压实型";
  let summary = "你现在更像是先获得一个大致理解，再通过练习、反馈和补强把知识一点点压实。";

  if (prefersPractice && accuracy >= 0.55 && masteryAverage >= 0.5) {
    label = "练习驱动型";
    summary = "你更适合边做边学。系统大多可以先给你练习或任务，再根据结果快速校准讲解深浅。";
  } else if (prefersVisual && weakPoints.length > 0) {
    label = "概念澄清型";
    summary = "你更像是先把结构和边界看清楚，再进入练习。系统适合优先给你图解、关系图和最小例子。";
  } else if (prefersVideo && confidence >= 0.55 && weakPoints.length <= 1) {
    label = "快速串联型";
    summary = "当基础已经够用时，你更适合先用短视频或分步讲解把流程串起来，再回到任务区完成验证。";
  } else if (calibrationCount >= 2 && confidence < 0.55) {
    label = "反复校准型";
    summary = "你的学习路径更依赖持续校准。系统需要通过更多反馈、反思和短测，逐步把判断收敛到更准。";
  }

  const signals: LearningProgressStyle["signals"] = [
    {
      label: "起步方式",
      detail: prefersPractice
        ? "当前偏好更接近“先做再调”。"
        : prefersVisual
          ? "当前偏好更接近“先看懂结构再动手”。"
          : prefersVideo
            ? "当前偏好更接近“先串流程再进入任务”。"
            : "系统目前观察到你会在讲解、练习和反馈之间交替推进。",
      tone: prefersPractice || prefersVisual || prefersVideo ? "brand" : "warning",
    },
    {
      label: "稳定程度",
      detail:
        masteryItems.length > 0
          ? `当前掌握跟踪均值约 ${Math.round(masteryAverage * 100)}%，说明你的推进已经开始从“看过”转向“会做”。`
          : "掌握度证据还不够多，系统仍在观察你更适合哪种推进节奏。",
      tone: masteryAverage >= 0.7 ? "success" : masteryAverage >= 0.45 ? "brand" : "warning",
    },
    {
      label: "反馈习惯",
      detail:
        calibrationCount > 0 || scoredEvidence.length > 0
          ? `你已经留下了 ${Math.max(calibrationCount, scoredEvidence.length)} 组可用于调节路线的反馈信号。`
          : "当前主动反馈还不多，后续多提交反思和评分会让系统更快学会你的节奏。",
      tone: calibrationCount >= 2 || scoredEvidence.length >= 3 ? "success" : "brand",
    },
  ];

  const suggestions = [
    prefersPractice
      ? "在导学里优先把“做练习”或“完成当前任务”放到更前面。"
      : prefersVisual
        ? "在卡点明显时，先给你图解或概念关系图，再进入题目。"
        : prefersVideo
          ? "在基础够用时，优先给你短视频或分步讲解，减少进入任务前的阻力。"
          : "先保持轻量资源 + 短任务的节奏，继续观察你更稳定的推进方式。",
    weakPoints.length > 0
      ? `当前仍要优先照顾「${weakPoints.slice(0, 2).map((item) => item.label).join("、")}」这类卡点。`
      : "当前没有明显堆积的薄弱点，可以把更多精力放到连续推进上。",
    evidenceAverage > 0
      ? `最近证据强度约为 ${Math.round(evidenceAverage * 100)}%，继续留下清晰反馈能让路线越走越顺。`
      : "接下来多完成一两次带评分的练习，这块风格判断会更稳。",
  ];

  return {
    label,
    summary,
    confidenceText: profileConfidenceLabel(confidence, accuracy),
    signals,
    suggestions,
    recentShift: buildRecentProgressShift(profile, label),
  };
}

function buildRecentProgressShift(profile: LearnerProfileSnapshot, styleLabel: string): LearningProgressStyle["recentShift"] {
  const recentEvidence = (profile.evidence_preview ?? []).slice(0, 5);
  if (!recentEvidence.length) return null;

  const scores = recentEvidence
    .map((item) => (typeof item.score === "number" ? clampScore(item.score) : null))
    .filter((item): item is number => item !== null);
  const averageScore = scores.length ? scores.reduce((sum, item) => sum + item, 0) / scores.length : null;
  const recentText = recentEvidence.map((item) => `${item.source_label} ${item.title} ${item.summary || ""}`).join(" ");
  const hasCalibration = /校准|画像|profile/i.test(recentText);
  const hasQuiz = /练习|答题|quiz|题目/i.test(recentText);
  const hasResource = /图解|视频|资源|visual|video/i.test(recentText);

  const cues = [
    hasQuiz ? "最近有练习反馈" : "",
    hasCalibration ? "最近有显式校准" : "",
    hasResource ? "最近有资源使用" : "",
    averageScore !== null ? `最近证据均值约 ${Math.round(averageScore * 100)}%` : "",
  ].filter(Boolean);

  if (hasCalibration || (averageScore !== null && averageScore < 0.6)) {
    return {
      label: "最近更像在修正路径",
      direction: "correcting",
      summary: "最近几条学习证据说明，系统仍在边学边修正你的路线。当前更适合先补清、再确认，而不是直接快推。",
      cues,
    };
  }

  if (averageScore !== null && averageScore >= 0.78 && hasQuiz) {
    return {
      label: "最近正在变稳",
      direction: "stable",
      summary: `最近几次练习和任务证据已经比较稳定，说明你这段时间的「${styleLabel}」开始真正站住了。`,
      cues,
    };
  }

  if (hasResource && hasQuiz && averageScore !== null && averageScore >= 0.62) {
    return {
      label: "最近开始提速",
      direction: "accelerating",
      summary: `最近的资源使用和练习反馈衔接得更顺，系统判断你可以在现有「${styleLabel}」基础上稍微加快一点节奏。`,
      cues,
    };
  }

  return {
    label: "最近仍在继续观察",
    direction: "observing",
    summary: "最近证据还在持续积累中。系统已经能看出你大致适合的学习方式，但还在观察哪种节奏最稳。",
    cues,
  };
}

function clampScore(value: number) {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(1, value));
}
