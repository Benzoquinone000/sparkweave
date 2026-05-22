export type GuideTone = "neutral" | "success" | "warning" | "danger" | "brand";
export type GuideRouteTone = "success" | "brand" | "warning" | "neutral";

export function demoSeedScalar(value: unknown) {
  return typeof value === "string" || typeof value === "number" ? String(value).trim() : "";
}

export function originLabel(origin: string) {
  const labels: Record<string, string> = {
    adaptive_remediation: "补救",
    adaptive_retest: "复测",
    adaptive_transfer: "迁移",
    diagnostic_remediation: "前测补强",
    learner_memory: "长期记录",
    planned: "计划",
  };
  return labels[origin] || origin || "任务";
}

export function originTone(origin: string): GuideTone {
  if (origin === "adaptive_remediation") return "warning";
  if (origin === "adaptive_retest") return "brand";
  if (origin === "adaptive_transfer") return "brand";
  if (origin === "learner_memory") return "brand";
  return "neutral";
}

export function feedbackTone(tone?: string): GuideTone {
  if (tone === "success") return "success";
  if (tone === "warning") return "warning";
  if (tone === "danger") return "danger";
  if (tone === "brand") return "brand";
  return "neutral";
}

export function feedbackConceptTone(status?: string, score?: number): GuideTone {
  if (status === "stable") return "success";
  if (status === "developing") return "brand";
  if (status === "needs_support") return "warning";
  return effectStatusTone(score);
}

export function effectStatusTone(score?: number): GuideTone {
  const value = Number(score ?? 0);
  if (value >= 85) return "success";
  if (value >= 70) return "brand";
  if (value >= 50) return "warning";
  if (value > 0) return "danger";
  return "neutral";
}

export function formatLearningEffectPercent(score?: number | null) {
  const value = Number(score ?? 0);
  if (!Number.isFinite(value) || value <= 0) return 0;
  return Math.round(value <= 1 ? value * 100 : value);
}

export function safeBadgeTone(tone?: string): GuideTone {
  if (tone === "success" || tone === "warning" || tone === "danger" || tone === "brand") return tone;
  return "neutral";
}

export function demoReadinessTone(status?: string): GuideTone {
  if (status === "ready") return "success";
  if (status === "partial") return "brand";
  if (status === "missing") return "warning";
  return "neutral";
}

export function demoReadinessLabel(status?: string): string {
  if (status === "ready") return "已具备";
  if (status === "partial") return "待加强";
  if (status === "missing") return "待补齐";
  return "检查中";
}

export function fallbackAssetTone(status?: string): GuideTone {
  if (status === "ready") return "success";
  if (status === "seed") return "brand";
  return "neutral";
}

export function fallbackAssetLabel(status?: string): string {
  if (status === "ready") return "可直接展示";
  if (status === "seed") return "可现场生成";
  return "备用";
}

export function submissionStatusTone(status?: string): GuideTone {
  const value = String(status || "").toLowerCase();
  if (value === "ready") return "success";
  if (value === "seed") return "brand";
  if (value === "todo" || value === "missing") return "warning";
  return "neutral";
}

export function submissionStatusLabel(status?: string): string {
  const value = String(status || "").toLowerCase();
  if (value === "ready") return "已就绪";
  if (value === "seed") return "有种子";
  if (value === "todo" || value === "missing") return "待补齐";
  return "待确认";
}

export function preflightStatusTone(status?: string): GuideTone {
  const value = String(status || "").toLowerCase();
  if (value === "ready") return "success";
  if (value === "rehearsable") return "brand";
  if (value === "needs_attention") return "warning";
  return "neutral";
}

export function preflightStatusLabel(status?: string): string {
  const value = String(status || "").toLowerCase();
  if (value === "ready") return "可以录制";
  if (value === "rehearsable") return "可排练";
  if (value === "needs_attention") return "先补一项";
  return "检查中";
}

export function preflightCheckTone(status?: string): GuideTone {
  const value = String(status || "").toLowerCase();
  if (value === "ready") return "success";
  if (value === "seed") return "brand";
  if (value === "todo") return "warning";
  return "neutral";
}

const GUIDE_DISPLAY_COPY: Record<string, string> = {
  "Ready for recording": "可录屏",
  Ready: "可录屏",
  "Stable demo course package": "稳定演示成果",
  "Stable demo course package for a 7-minute recording.": "用于 7 分钟录屏的稳定课程成果。",
  "7-minute demo route": "7 分钟演示路线",
  "Show profile, route, resource, feedback, and package.": "展示学习记录、路线、资源、反馈和成果。",
  "Open guide route before recording.": "录屏前先打开导学路线。",
  "Profile, resource, feedback, report and package can now be shown as one chain.": "学习记录、资源、反馈、报告和课程成果已经串成一条学习链。",
  "Open the route map, then open the course package.": "先看路线，再看课程成果。",
  "Open the route and course package": "查看路线和成果",
  "Use the route map and package to show the closed loop.": "用路线图和课程成果展示完整学习过程。",
  "Machine Learning Foundations": "机器学习基础",
  "Explain gradient descent": "讲清楚梯度下降",
  "Build one visual resource and one feedback loop.": "生成一份图解资源，并完成一次反馈复盘。",
  "Create route": "创建路线",
  "Generate visual": "生成图解",
  "Submit feedback": "提交反馈",
  Route: "路线",
  Visual: "图解",
  Feedback: "反馈",
  Profile: "学习记录",
  profile: "学习记录",
  feedback: "反馈",
  "Closed loop": "完整学习过程",
  "Shows profile to feedback.": "能展示从学习记录到反馈的完整过程。",
  Optimization: "优化方法",
  "Do one short retest.": "做一次短复测。",
  "Retest gradient descent.": "复测梯度下降。",
  "Recording fallback kit": "录屏兜底包",
  "Use stable artifacts if live generation is slow.": "现场生成变慢时，直接展示稳定产物。",
  "Use saved visuals if generation is slow.": "生成变慢时，展示已保存图解。",
  "Gradient descent visual": "梯度下降图解",
  "Use saved visual.": "使用已保存图解。",
  "Profile evidence": "学习记录来源",
  "Profile is present.": "已有学习记录来源。",
  "Open learner profile.": "打开学习记录。",
  Resource: "资源",
  "Visual resource was requested.": "已请求图解资源。",
  "Feedback loop is visible.": "反馈路径可见。",
  "Demo learning report": "演示学习报告",
  "The demo learner has a visible feedback loop.": "演示学习者已经形成可见反馈路径。",
  "Feedback recorded": "反馈已记录",
  "Profile updated.": "学习记录已更新。",
  Demo: "演示",
  ready: "已就绪",
  "Open route": "查看路线",
  "Show the adjusted route.": "展示调整后的路线。",
  "Stable ML foundations demo": "机器学习基础稳定演示",
  "Demo learner": "演示学习者",
  "Concept boundaries": "概念边界",
  ml_foundations: "机器学习基础",
  task_chain: "任务链路",
  route_map: "学习路线",
  course_package: "课程成果包",
  T1: "记录校准",
  T2: "路线创建",
  T3: "资源生成",
  T4: "图解演示",
  T5: "练习反馈",
  T6: "效果报告",
  "T1 profile": "记录校准",
  "T2 route": "路线创建",
  "T3 resource": "资源生成",
  "T4 visual": "图解演示",
  "T5 practice": "练习反馈",
  "T6 report": "效果报告",
  对话协调智能体: "理解任务",
  画像智能体: "学习记录",
  学习画像智能体: "学习记录",
  路径规划智能体: "路线规划",
  资源生成智能体集群: "资源生成",
  评估智能体: "学习评估",
  视频检索智能体: "视频查找",
};

export function guideDisplayText(value: unknown, fallback = ""): string {
  const text = String(value ?? "").trim();
  if (!text) return fallback;
  const translated = GUIDE_DISPLAY_COPY[text];
  if (translated) return translated;
  if (isLikelyInternalIdentifier(text)) return fallback || "学习内容";
  return normalizeGuideUserText(text);
}

function normalizeGuideUserText(text: string) {
  return text
    .replace(/多智能体协同/g, "多步骤协同")
    .replace(/多智能体协作/g, "多步骤协作")
    .replace(/智能体接力/g, "学习步骤接续")
    .replace(/学习画像|用户画像|画像/g, "学习记录")
    .replace(/智能体/g, "步骤")
    .replace(/产出包/g, "成果包")
    .replace(/闭环/g, "学习链")
    .replace(/索引/g, "整理")
    .replace(/检索/g, "查找");
}

export function guideSafeFilename(value: unknown, fallback = "sparkweave-course-package"): string {
  const text = guideDisplayText(value, fallback)
    .replace(/[\\/:*?"<>|]+/g, "-")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 80);
  return text || fallback;
}

export function isLikelyInternalIdentifier(text: string) {
  return (
    /^T\d+(\s+[-_a-z]+)?$/i.test(text) ||
    /^N\d+$/i.test(text) ||
    /^(task|node|session|guide|route|plan|kb|artifact|course)[_-][a-z0-9_-]+$/i.test(text)
  );
}

export function guideStageLabel(value: unknown, fallback = "步骤") {
  const raw = String(value ?? "").trim();
  if (!raw) return fallback;
  const exact = GUIDE_DISPLAY_COPY[raw];
  if (exact) return exact;
  const normalized = raw.toLowerCase().replace(/[\s-]+/g, "_");
  if (normalized.includes("profile")) return "记录校准";
  if (normalized.includes("route")) return "路线创建";
  if (normalized.includes("visual")) return "图解演示";
  if (normalized.includes("audio") || normalized.includes("speech") || normalized.includes("tts")) return "语音讲解";
  if (normalized.includes("video")) return "短视频讲解";
  if (normalized.includes("quiz") || normalized.includes("practice")) return "练习验证";
  if (normalized.includes("feedback")) return "反馈回写";
  if (normalized.includes("report")) return "效果报告";
  if (normalized.includes("package") || normalized.includes("project")) return "成果整理";
  if (normalized.includes("resource")) return "资源生成";
  return guideDisplayText(raw, fallback);
}

export function taskTypeLabel(type: string) {
  const labels: Record<string, string> = {
    explain: "讲解",
    visualize: "图解",
    video: "视频",
    audio: "语音",
    external_video: "精选视频",
    external_image: "精选图片",
    practice: "练习",
    remediation: "补救",
    quiz: "复测",
    reflection: "反思",
    project: "项目",
  };
  return labels[type] || type || "任务";
}

export function guideTaskTitle(task: { title?: unknown; type?: unknown } | null | undefined, index?: number) {
  const title = guideDisplayText(task?.title, "");
  if (title && title !== "学习内容") return title;
  const rawType = typeof task?.type === "string" ? task.type : String(task?.type ?? "");
  const type = rawType ? taskTypeLabel(rawType) : "学习任务";
  return typeof index === "number" ? `${type} ${index + 1}` : type;
}

export function planStatusLabel(status: string) {
  const labels: Record<string, string> = {
    active: "进行中",
    in_progress: "进行中",
    pending: "待开始",
    completed: "已完成",
    skipped: "已跳过",
    met: "已达成",
    needs_review: "需复盘",
  };
  return labels[status] || status || "待开始";
}

export function planStatusTone(status: string): GuideTone {
  if (status === "completed" || status === "met") return "success";
  if (status === "active" || status === "in_progress") return "brand";
  if (status === "needs_review") return "warning";
  return "neutral";
}

export function diagnosticStatusLabel(status: string) {
  const labels: Record<string, string> = {
    completed: "已诊断",
    pending: "待前测",
  };
  return labels[status] || status || "待前测";
}

export function masteryTone(status: string): GuideTone {
  if (status === "mastered") return "success";
  if (status === "learning") return "brand";
  if (status === "needs_support") return "warning";
  return "neutral";
}

export function knowledgeNodeStyle(status: string, active: boolean, current: boolean, done: boolean) {
  if (active) {
    return {
      card: "border-brand-purple bg-tint-lavender shadow-sm",
      dot: "border-brand-purple bg-brand-purple text-white",
      bar: "bg-brand-purple",
    };
  }
  if (current) {
    return {
      card: "border-blue-200 bg-blue-50",
      dot: "border-blue-600 bg-blue-600 text-white",
      bar: "bg-blue-600",
    };
  }
  if (done || status === "mastered") {
    return {
      card: "border-emerald-200 bg-emerald-50",
      dot: "border-emerald-600 bg-emerald-600 text-white",
      bar: "bg-emerald-600",
    };
  }
  if (status === "needs_support") {
    return {
      card: "border-amber-200 bg-amber-50",
      dot: "border-amber-500 bg-amber-500 text-white",
      bar: "bg-amber-500",
    };
  }
  return {
    card: "border-line bg-white",
    dot: "border-line bg-canvas text-slate-500",
    bar: "bg-slate-300",
  };
}

export function masteryStatusLabel(status: string) {
  const labels: Record<string, string> = {
    mastered: "已掌握",
    learning: "学习中",
    needs_support: "需补强",
    not_started: "未开始",
  };
  return labels[status] || status || "未开始";
}

export function scorePercent(value: unknown) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  const percent = number <= 1 ? number * 100 : number;
  return Math.max(0, Math.min(100, Math.round(percent)));
}

export function extractStringArray(value: unknown) {
  if (Array.isArray(value)) {
    return value.map(String).map((item) => item.trim()).filter(Boolean);
  }
  if (typeof value === "string") {
    return value
      .split(/\s*(?:,|，|、|;|；|\|)\s*/g)
      .map((item) => item.trim())
      .filter(Boolean);
  }
  return [];
}
