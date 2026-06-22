import { Fragment, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  AudioLines,
  BookOpen,
  CheckCircle2,
  FileSearch,
  Image,
  ListChecks,
  Loader2,
  SearchCheck,
  Video,
  type LucideIcon,
} from "lucide-react";

import {
  LazyAudioNarrationViewer,
  LazyExternalVideoViewer,
  LazyMathAnimatorViewer,
} from "@/components/results/LazyMediaResultViewers";
import { LazyVisualizationViewer } from "@/components/results/LazyVisualizationViewer";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { TextInput } from "@/components/ui/Field";
import { MarkdownRenderer } from "@/components/ui/MarkdownRenderer";
import { extractStringArray } from "@/lib/guideDisplay";
import type {
  AudioNarrationResult,
  ExternalVideoResult,
  GuideV2Artifact,
  MathAnimatorResult,
  QuizResultItem,
  VisualizeResult,
} from "@/lib/types";
import {
  asRecord,
  extractGuideQuizItems,
  formatTime,
  guideAnswerFeedbackLabel,
  guideQuestionTypeLabel,
  isGuideQuizCorrect,
  normalizeGuideQuestionType,
  normalizeOptions,
  pickFirstText,
  readString,
  splitLines,
} from "./guideDataUtils";
import { resourceLabel } from "./guideResourceUtils";

export function GuideResourceArtifactPager({
  artifacts,
  saveNotebookId,
  saving,
  quizSubmitting,
  compact = false,
  onSave,
  onSubmitQuiz,
  onCompleteTask,
  finalLabel = "去提交",
  finalHint = "写一句反思，系统再给反馈。",
}: {
  artifacts: GuideV2Artifact[];
  saveNotebookId: string;
  saving: boolean;
  quizSubmitting: boolean;
  compact?: boolean;
  onSave: (artifact: GuideV2Artifact) => void;
  onSubmitQuiz: (artifact: GuideV2Artifact, answers: QuizResultItem[]) => void;
  onCompleteTask: () => void;
  finalLabel?: string;
  finalHint?: string;
}) {
  const [activeIndex, setActiveIndex] = useState(0);
  const orderedArtifacts = useMemo(() => sortGuideArtifactsForLearning(artifacts), [artifacts]);
  const activeArtifact = orderedArtifacts[Math.min(activeIndex, Math.max(orderedArtifacts.length - 1, 0))];

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setActiveIndex((index) => Math.min(index, Math.max(orderedArtifacts.length - 1, 0)));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [orderedArtifacts.length]);

  if (!activeArtifact) return null;

  if (compact) {
    return (
      <div className="flex h-full min-h-0 flex-col rounded-lg border border-line bg-canvas p-3">
        <div className="flex shrink-0 flex-wrap items-center justify-between gap-2">
          <div className="min-w-0">
            <p className="text-xs font-semibold text-steel">
              材料 {activeIndex + 1}/{orderedArtifacts.length}
            </p>
            <h4 className="mt-1 line-clamp-1 text-sm font-semibold text-ink">
              {activeArtifact.title || resourceLabel(String(activeArtifact.type))}
            </h4>
          </div>
          <Badge tone="brand">{resourceLabel(String(activeArtifact.type))}</Badge>
        </div>

        <div className="my-3 min-h-0 flex-1 rounded-lg border border-line bg-white p-3">
          <p className="line-clamp-5 text-sm leading-6 text-slate-600">{artifactPreview(activeArtifact)}</p>
          {activeArtifact.learning_package?.study_order?.length ? (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {activeArtifact.learning_package.study_order.slice(0, 3).map((item) => (
                <Badge key={item} tone="neutral">{item}</Badge>
              ))}
            </div>
          ) : null}
        </div>

        <div className="grid shrink-0 gap-2 sm:grid-cols-3">
          <Button
            tone="secondary"
            disabled={activeIndex <= 0}
            onClick={() => setActiveIndex((index) => Math.max(0, index - 1))}
          >
            上一份
          </Button>
          <Button
            tone="secondary"
            disabled={activeIndex >= orderedArtifacts.length - 1}
            onClick={() => setActiveIndex((index) => Math.min(orderedArtifacts.length - 1, index + 1))}
          >
            下一份
          </Button>
          <Button tone="primary" onClick={onCompleteTask}>
            {finalLabel}
          </Button>
        </div>
        <div className="mt-2 flex shrink-0 justify-end">
          <Button
            tone="quiet"
            className="min-h-8 px-2 text-xs"
            disabled={!saveNotebookId || saving || quizSubmitting}
            onClick={() => onSave(activeArtifact)}
          >
            {saving ? "保存中" : "保存材料"}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-line bg-canvas p-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-ink">按这个顺序学</p>
          <p className="mt-1 text-xs text-slate-500">一次只看一个结果，最后回到提交页。</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            tone="secondary"
            className="min-h-8 px-2 text-xs"
            disabled={activeIndex <= 0}
            onClick={() => setActiveIndex((index) => Math.max(0, index - 1))}
          >
            上一个
          </Button>
          <Badge tone="brand">
            {activeIndex + 1}/{orderedArtifacts.length}
          </Badge>
          <Button
            tone="secondary"
            className="min-h-8 px-2 text-xs"
            disabled={activeIndex >= orderedArtifacts.length - 1}
            onClick={() => setActiveIndex((index) => Math.min(orderedArtifacts.length - 1, index + 1))}
          >
            下一个
          </Button>
        </div>
      </div>
      <MultiModalResourceStudio artifacts={orderedArtifacts} activeType={String(activeArtifact.type)} />
      <ResourceLearningSteps
        artifacts={orderedArtifacts}
        activeIndex={activeIndex}
        onSelect={setActiveIndex}
        onCompleteTask={onCompleteTask}
        finalLabel={finalLabel}
        finalHint={finalHint}
      />
      <div className="mt-3">
        <ResourceArtifact
          artifact={activeArtifact}
          saveNotebookId={saveNotebookId}
          saving={saving}
          quizSubmitting={quizSubmitting}
          onSave={() => onSave(activeArtifact)}
          onSubmitQuiz={(answers) => onSubmitQuiz(activeArtifact, answers)}
        />
      </div>
    </div>
  );
}

function artifactPreview(artifact: GuideV2Artifact) {
  const result = asRecord(artifact.result);
  return (
    artifact.learning_package?.summary ||
    artifact.learning_package?.why_recommended?.[0] ||
    pickFirstText(result, ["response", "summary", "content", "script_text", "watch_plan", "reflection_prompt"]) ||
    "这份材料已生成。按顺序看完后，回到提交页写一句反思。"
  );
}

function MultiModalResourceStudio({
  artifacts,
  activeType,
}: {
  artifacts: GuideV2Artifact[];
  activeType: string;
}) {
  const lanes = buildResourceStudioLanes(artifacts);
  const readyCount = lanes.filter((lane) => lane.count > 0).length;
  const capabilityBadges = buildIflytekCapabilityBadges(artifacts);

  return (
    <div className="mt-3 rounded-lg border border-line bg-white p-3" data-testid="guide-multimodal-resource-studio">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">多模态资源 Studio</Badge>
            <span className="text-xs font-medium text-ink">{readyCount}/{lanes.length} 类资源已入列</span>
          </div>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            同一学习任务被拆成图解、视频、语音、练习和记录卡，评委能直接看到“资源生成”不是单一文本输出。
          </p>
        </div>
        <Badge tone="neutral">{artifacts.length} 个产物</Badge>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-6">
        {lanes.map((lane) => {
          const Icon = lane.icon;
          const active = lane.types.includes(activeType);
          return (
            <div
              key={lane.key}
              className={`min-h-[6.5rem] rounded-lg border p-3 ${resourceStudioLaneTone(lane.count > 0, active)}`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="grid h-8 w-8 place-items-center rounded-lg border border-line bg-canvas text-brand-purple">
                  <Icon size={15} />
                </span>
                <Badge tone={lane.count > 0 ? (active ? "brand" : "success") : "neutral"}>
                  {lane.count > 0 ? `${lane.count} 个` : "待生成"}
                </Badge>
              </div>
              <p className="mt-2 text-sm font-semibold text-ink">{lane.label}</p>
              <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{lane.detail}</p>
            </div>
          );
        })}
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {capabilityBadges.map((item) => (
          <span
            key={item.label}
            className={`inline-flex min-h-7 items-center gap-1.5 rounded-md border px-2 text-xs font-medium ${resourceStudioCapabilityTone(item.ready)}`}
          >
            <span className={`h-1.5 w-1.5 rounded-sm ${item.ready ? "bg-brand-purple" : "bg-slate-300"}`} />
            {item.label}
          </span>
        ))}
      </div>
    </div>
  );
}

function buildResourceStudioLanes(artifacts: GuideV2Artifact[]) {
  const count = (types: string[]) => artifacts.filter((artifact) => types.includes(String(artifact.type))).length;
  return [
    {
      key: "visual",
      label: "图解",
      detail: "把抽象知识变成结构图、流程图或概念关系图。",
      icon: Image,
      types: ["visual"],
      count: count(["visual"]),
    },
    {
      key: "video",
      label: "短视频",
      detail: "用可播放分镜解释关键步骤和推导过程。",
      icon: Video,
      types: ["video"],
      count: count(["video"]),
    },
    {
      key: "audio",
      label: "语音",
      detail: "把当前任务压缩成可听的讲解脚本与音频。",
      icon: AudioLines,
      types: ["audio"],
      count: count(["audio"]),
    },
    {
      key: "external_video",
      label: "精选视频",
      detail: "从公开资源中筛出适合当前学习情况的补充讲解。",
      icon: SearchCheck,
      types: ["external_video"],
      count: count(["external_video"]),
    },
    {
      key: "quiz",
      label: "练习",
      detail: "用即时反馈验证这轮资源是否真正学会。",
      icon: ListChecks,
      types: ["quiz"],
      count: count(["quiz"]),
    },
    {
      key: "evidence",
      label: "记录",
      detail: "把学习信号、生成理由和评估结果连成完整过程。",
      icon: FileSearch,
      types: artifacts.map((artifact) => String(artifact.type)),
      count: artifacts.length,
    },
  ] satisfies Array<{
    key: string;
    label: string;
    detail: string;
    icon: LucideIcon;
    types: string[];
    count: number;
  }>;
}

function buildIflytekCapabilityBadges(artifacts: GuideV2Artifact[]) {
  const types = new Set(artifacts.map((artifact) => String(artifact.type)));
  const capabilities = new Set(artifacts.map((artifact) => String(artifact.capability || "")));
  return [
    { label: "讯飞星火生成", ready: artifacts.length > 0 },
    { label: "多模态图解", ready: types.has("visual") || capabilities.has("visualize") },
    { label: "TTS 语音讲解", ready: types.has("audio") || capabilities.has("tts") },
    { label: "公开视频查找", ready: types.has("external_video") || capabilities.has("external_video_search") },
    { label: "智能出题评估", ready: types.has("quiz") || capabilities.has("deep_question") },
    { label: "资料来源", ready: artifacts.some((artifact) => Boolean(extractArtifactPersonalization(artifact))) },
  ];
}

function resourceStudioLaneTone(ready: boolean, active: boolean) {
  if (active) return "border-brand-purple-300 bg-tint-lavender";
  if (ready) return "border-line bg-white";
  return "border-dashed border-line bg-canvas";
}

function resourceStudioCapabilityTone(ready: boolean) {
  return ready
    ? "border-brand-purple-300 bg-tint-lavender text-brand-purple"
    : "border-line bg-canvas text-slate-500";
}

function ResourceLearningSteps({
  artifacts,
  activeIndex,
  onSelect,
  onCompleteTask,
  finalLabel,
  finalHint,
}: {
  artifacts: GuideV2Artifact[];
  activeIndex: number;
  onSelect: (index: number) => void;
  onCompleteTask: () => void;
  finalLabel: string;
  finalHint: string;
}) {
  const steps = artifacts.map((artifact, index) => ({
    artifact,
    label: resourceStepLabel(String(artifact.type), index, artifacts),
    hint: resourceStepHint(String(artifact.type)),
  }));

  return (
    <div className="mt-3 rounded-lg border border-line bg-white p-3">
      <div className="grid gap-2 md:grid-cols-4">
        {steps.map((step, index) => (
          <button
            key={step.artifact.id}
            type="button"
            onClick={() => onSelect(index)}
            className={`rounded-lg border p-3 text-left transition ${
              index === activeIndex ? "border-brand-purple-300 bg-tint-lavender" : "border-line bg-white hover:border-brand-purple-300 hover:bg-canvas"
            }`}
          >
            <Badge tone={index === activeIndex ? "brand" : "neutral"}>第 {index + 1} 步</Badge>
            <p className="mt-2 text-sm font-semibold text-ink">{step.label}</p>
            <p className="mt-1 text-xs leading-5 text-slate-500">{step.hint}</p>
          </button>
        ))}
        <button
          type="button"
          onClick={onCompleteTask}
          className="rounded-lg border border-line bg-canvas p-3 text-left transition hover:border-brand-purple-300 hover:bg-tint-lavender"
        >
          <Badge tone="success">最后</Badge>
          <p className="mt-2 text-sm font-semibold text-ink">{finalLabel}</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">{finalHint}</p>
        </button>
      </div>
    </div>
  );
}

function sortGuideArtifactsForLearning(artifacts: GuideV2Artifact[]) {
  const order: Record<string, number> = {
    visual: 0,
    external_video: 1,
    video: 2,
    audio: 3,
    quiz: 4,
  };
  return [...artifacts].sort((left, right) => {
    const leftOrder = order[String(left.type)] ?? 9;
    const rightOrder = order[String(right.type)] ?? 9;
    if (leftOrder !== rightOrder) return leftOrder - rightOrder;
    return Number(left.created_at ?? 0) - Number(right.created_at ?? 0);
  });
}

function resourceStepLabel(type: string, index: number, artifacts: GuideV2Artifact[]) {
  const hasConceptResourceBefore = artifacts
    .slice(0, index)
    .some((item) => item.type === "visual" || item.type === "video" || item.type === "audio" || item.type === "external_video");
  if (type === "visual") return index === 0 ? "先看图解" : "再看图解";
  if (type === "external_video") return index === 0 ? "先看精选视频" : "再看精选视频";
  if (type === "video") return index === 0 ? "先看短视频" : "再看短视频";
  if (type === "audio") return index === 0 ? "先听讲解" : "再听一遍";
  if (type === "quiz") return hasConceptResourceBefore ? "再做练习" : "先做练习";
  return resourceLabel(type);
}

function resourceStepHint(type: string) {
  if (type === "visual") return "先建立直觉和结构。";
  if (type === "external_video") return "用外部讲解补充视角。";
  if (type === "video") return "跟着步骤过一遍。";
  if (type === "audio") return "先听清概念和步骤。";
  if (type === "quiz") return "用题目确认是否掌握。";
  return "看完后继续下一步。";
}

function ResourceArtifact({
  artifact,
  saveNotebookId,
  saving,
  quizSubmitting,
  onSave,
  onSubmitQuiz,
}: {
  artifact: GuideV2Artifact;
  saveNotebookId: string;
  saving: boolean;
  quizSubmitting: boolean;
  onSave: () => void;
  onSubmitQuiz: (answers: QuizResultItem[]) => void;
}) {
  const result = asRecord(artifact.result);
  const response = readString(result ?? {}, "response");
  const renderType = readString(result ?? {}, "render_type");
  const hasVisual = Boolean(artifact.type === "visual" && renderType && asRecord(result?.code)?.content);
  const hasVideo = Boolean(artifact.type === "video" && (Array.isArray(result?.artifacts) || asRecord(result?.code)?.content));
  const hasAudio = Boolean(artifact.type === "audio" && asRecord(result?.audio)?.asset_url);
  const hasExternalVideo = Boolean(artifact.type === "external_video" && Array.isArray(result?.videos));
  const questions = extractGuideQuizItems(result);
  const showResponse = Boolean(
    response && !(artifact.type === "quiz" && questions.length) && artifact.type !== "external_video" && artifact.type !== "audio",
  );
  const personalization = extractArtifactPersonalization(artifact);
  const specialist = agentRoleForArtifact(artifact);

  return (
    <motion.article
      className="rounded-lg border border-line bg-canvas p-4"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18 }}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Badge tone="brand">{resourceLabel(String(artifact.type))}</Badge>
          {artifact.capability ? <Badge tone="neutral">{specialist.label}</Badge> : null}
        </div>
        <div className="flex items-center gap-2">
          <Button
            tone="quiet"
            className="min-h-8 px-2 text-xs"
            onClick={onSave}
            disabled={saving || (!saveNotebookId && artifact.type !== "quiz")}
          >
            {saving ? <Loader2 size={14} className="animate-spin" /> : <BookOpen size={14} />}
            保存
          </Button>
          <span className="text-xs text-slate-500">{formatTime(artifact.created_at)}</span>
        </div>
      </div>
      <h3 className="mt-3 text-sm font-semibold text-ink">{artifact.title || "学习资源"}</h3>
      <ArtifactAgentChain artifact={artifact} personalization={personalization} />
      <ArtifactLearningPackageSummary artifact={artifact} />
      {personalization ? <ArtifactPersonalizationCard personalization={personalization} /> : null}
      {showResponse ? <MarkdownRenderer className="markdown-body mt-3 text-sm text-slate-600">{response}</MarkdownRenderer> : null}

      {hasVisual ? <div className="mt-4"><LazyVisualizationViewer result={result as unknown as VisualizeResult} /></div> : null}
      {hasVideo ? <div className="mt-4"><LazyMathAnimatorViewer result={result as unknown as MathAnimatorResult} /></div> : null}
      {hasAudio ? <div className="mt-4"><LazyAudioNarrationViewer result={result as unknown as AudioNarrationResult} /></div> : null}
      {hasExternalVideo ? <div className="mt-4"><LazyExternalVideoViewer result={result as unknown as ExternalVideoResult} /></div> : null}
      {artifact.type === "quiz" && questions.length ? (
        <QuestionPreview items={questions} submitting={quizSubmitting} onSubmit={onSubmitQuiz} />
      ) : null}
      {artifact.type === "quiz" && !questions.length ? <QuizFallback result={result} response={response} /> : null}
    </motion.article>
  );
}

function ArtifactLearningPackageSummary({ artifact }: { artifact: GuideV2Artifact }) {
  const learningPackage = artifact.learning_package;
  if (!learningPackage) return null;
  const reasons = (learningPackage.why_recommended ?? []).filter(Boolean).slice(0, 3);
  const studyOrder = (learningPackage.study_order ?? []).filter(Boolean).slice(0, 3);
  const qualityScore = typeof learningPackage.quality_score === "number" ? Math.round(learningPackage.quality_score) : null;
  if (!reasons.length && !studyOrder.length && qualityScore === null) return null;

  return (
    <div className="mt-3 border-l-2 border-emerald-300 bg-white/80 px-3 py-2" data-testid="guide-learning-package-summary">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="success">学习包</Badge>
        {qualityScore !== null ? <span className="text-xs font-medium text-slate-500">质量评审 {qualityScore}</span> : null}
      </div>
      {reasons.length ? <p className="mt-2 text-xs leading-5 text-charcoal">为什么推荐：{reasons[0]}</p> : null}
      {studyOrder.length ? (
        <ol className="mt-2 space-y-1 text-xs leading-5 text-slate-500">
          {studyOrder.map((item, index) => (
            <li key={`${item}-${index}`}>
              {index + 1}. {item}
            </li>
          ))}
        </ol>
      ) : null}
    </div>
  );
}

function ArtifactAgentChain({
  artifact,
  personalization,
}: {
  artifact: GuideV2Artifact;
  personalization: ReturnType<typeof extractArtifactPersonalization>;
}) {
  const specialist = agentRoleForArtifact(artifact);
  const evidenceText = personalization?.signals?.[0]
    ? `${personalization.signals[0].label}：${personalization.signals[0].value}`
    : "当前任务与学习记录";
  const steps = [
    {
      label: "学习记录",
      detail: `先判断入口：${evidenceText}`,
      tone: "brand" as const,
    },
    {
      label: specialist.label,
      detail: specialist.detail,
      tone: "neutral" as const,
    },
    {
      label: "反馈评估",
      detail: artifact.type === "quiz" ? "提交后批改并更新下一步" : "学完后通过提交页更新学习记录",
      tone: "success" as const,
    },
  ];
  const summary =
    artifact.type === "quiz"
      ? "按学习记录定向出题，提交后直接进入反馈和下一步调整。"
      : `先根据学习记录定向，再由${specialist.label}生成当前材料，学完后回到提交页完成复盘。`;

  return (
    <div className="mt-3 rounded-lg border border-line bg-white px-3 py-3" data-testid="guide-artifact-agent-route">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Badge tone="brand">学习流程</Badge>
          <span className="text-xs font-medium text-ink">{summary}</span>
        </div>
      </div>
      <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
        {steps.map((step, index) => (
          <Fragment key={step.label}>
            <motion.div
              className="min-w-[8rem] shrink-0 rounded-md border border-line bg-canvas px-3 py-2"
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.16, delay: index * 0.04 }}
            >
              <div className="flex items-center gap-2">
                <span className={`h-1.5 w-1.5 rounded-sm ${agentRouteDotTone(step.tone)}`} />
                <span className="text-xs font-semibold text-ink">{shortGuideAgentName(step.label)}</span>
              </div>
              <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{step.detail}</p>
            </motion.div>
            {index < steps.length - 1 ? <span className="mt-5 shrink-0 text-slate-300">→</span> : null}
          </Fragment>
        ))}
      </div>
    </div>
  );
}

function shortGuideAgentName(label: string) {
  const normalized = label.trim();
  const labels: Record<string, string> = {
    画像智能体: "学习记录",
    学习画像智能体: "学习记录",
    资源智能体: "资源整理",
    出题智能体: "练习生成",
    反馈智能体: "反馈复盘",
    评估智能体: "学习评估",
    图解智能体: "图解整理",
    视频智能体: "视频整理",
  };
  if (labels[normalized]) return labels[normalized];
  return normalized
    .replace(/学习画像|用户画像|画像/g, "学习记录")
    .replace(/智能体/g, "步骤")
    .replace(/\s*Agent/gi, "")
    .replace(/步骤$/, "");
}

function agentRouteDotTone(tone: "brand" | "neutral" | "success") {
  if (tone === "brand") return "bg-brand-purple";
  if (tone === "success") return "bg-emerald-500";
  return "bg-brand-blue";
}

function ArtifactPersonalizationCard({
  personalization,
}: {
  personalization: {
    headline: string;
    reasons: string[];
    signals: Array<{ label: string; value: string }>;
    progressStyle?: {
      label: string;
      explanation: string;
      recommendation: string;
    } | null;
  };
}) {
  return (
    <div className="mt-3 rounded-lg border border-brand-purple-300 bg-tint-lavender px-3 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="brand">生成来源</Badge>
        {personalization.signals.slice(0, 4).map((item) => (
          <Badge key={`${item.label}-${item.value}`} tone="neutral">
            {item.label}：{item.value}
          </Badge>
        ))}
      </div>
      <p className="mt-2 text-sm leading-6 text-charcoal">{personalization.headline}</p>
      {personalization.progressStyle ? (
        <div className="mt-2 rounded-lg border border-brand-purple-300 bg-white/80 px-3 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">按你的学习方式生成</Badge>
            <Badge tone="neutral">{personalization.progressStyle.label}</Badge>
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-700">{personalization.progressStyle.explanation}</p>
          <p className="mt-2 text-xs leading-5 text-slate-500">{personalization.progressStyle.recommendation}</p>
        </div>
      ) : null}
      {personalization.reasons.length ? (
        <div className="mt-2 grid gap-2">
          {personalization.reasons.slice(0, 3).map((reason) => (
            <p key={reason} className="rounded-lg border border-white/70 bg-white/80 px-3 py-2 text-xs leading-5 text-slate-700">
              {reason}
            </p>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function agentRoleForArtifact(artifact: GuideV2Artifact) {
  const capability = String(artifact.capability || "");
  const type = String(artifact.type || "");
  if (type === "video" || capability === "math_animator") {
    return {
      label: "动画讲解",
      detail: "把关键步骤拆成可播放的短视频讲解。",
    };
  }
  if (type === "audio" || capability === "tts") {
    return {
      label: "语音讲解",
      detail: "把当前任务压缩成一段可以直接听的语音讲解。",
    };
  }
  if (type === "external_video" || capability === "external_video_search") {
    return {
      label: "视频查找",
      detail: "从公开视频中筛选适合当前学习情况和任务的学习材料。",
    };
  }
  if (type === "quiz" || capability === "deep_question") {
    return {
      label: "练习生成",
      detail: "生成可提交、可反馈的交互练习。",
    };
  }
  if (type === "visual" || capability === "visualize") {
    return {
      label: "图解整理",
      detail: "把概念关系整理成图解或结构化可视化。",
    };
  }
  if (type === "research" || capability === "deep_research") {
    return {
      label: "资料整理",
      detail: "补充来源并整理成当前任务可用的材料。",
    };
  }
  return {
    label: "资源生成",
    detail: "按当前任务生成一份可继续学习的材料。",
  };
}

function QuizFallback({
  result,
  response,
}: {
  result: Record<string, unknown> | null;
  response: string;
}) {
  const text = response || pickFirstText(result, ["summary", "content", "final_answer", "answer"]);
  return (
    <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-800">
      <p className="font-semibold text-ink">这组题暂时无法转换成交互练习</p>
      <p className="mt-1">我没有在结果里找到标准题目结构。可以重新生成练习，或先按下面内容自行作答。</p>
      {text ? <MarkdownRenderer className="markdown-body mt-3 text-sm">{text}</MarkdownRenderer> : null}
    </div>
  );
}

function QuestionPreview({
  items,
  submitting,
  onSubmit,
}: {
  items: unknown[];
  submitting: boolean;
  onSubmit: (answers: QuizResultItem[]) => void;
}) {
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [revealed, setRevealed] = useState<Record<number, boolean>>({});
  const [checked, setChecked] = useState<Record<number, boolean>>({});
  const [startedAt, setStartedAt] = useState<Record<number, number>>({});
  const [checkedAt, setCheckedAt] = useState<Record<number, number>>({});
  const [submitted, setSubmitted] = useState(false);
  const records = items.slice(0, 8).map((item) => {
    const record = asRecord(item) ?? {};
    const qa = asRecord(record.qa_pair) ?? asRecord(record.question) ?? record;
    return { record, qa, options: normalizeOptions(qa.options ?? record.options) };
  });
  const checkedCount = records.filter((_item, index) => checked[index]).length;
  const allChecked = records.length > 0 && checkedCount === records.length;
  const markStarted = (itemIndex: number) => {
    setStartedAt((current) => (current[itemIndex] ? current : { ...current, [itemIndex]: Date.now() }));
  };

  const buildResults = (): QuizResultItem[] =>
    records.map(({ record, qa, options }, index) => {
      const answer = answers[index] || "";
      const correctAnswer = readString(qa, "correct_answer") || readString(qa, "answer");
      const kind = normalizeGuideQuestionType(readString(qa, "question_type"), options);
      const concepts = extractGuideQuestionConcepts(qa, record);
      const finishedAt = checkedAt[index] || Date.now();
      const started = startedAt[index] || finishedAt;
      return {
        question_id: readString(qa, "question_id") || `guide-q-${index + 1}`,
        question: readString(qa, "question") || readString(qa, "prompt") || readString(qa, "title") || "已生成练习题",
        question_type: kind,
        options: options ? Object.fromEntries(Object.entries(options).map(([key, value]) => [key, String(value)])) : {},
        concepts,
        knowledge_points: concepts,
        user_answer: answer,
        correct_answer: correctAnswer,
        explanation: readString(qa, "explanation"),
        difficulty: readString(qa, "difficulty"),
        duration_seconds: Math.max(1, Math.round((finishedAt - started) / 1000)),
        attempt_count: 1,
        is_correct: isGuideQuizCorrect(answer, correctAnswer, options),
      };
    });
  const currentResults = buildResults();
  const correctCount = currentResults.filter((item) => item.is_correct).length;
  const scoreRatio = records.length ? correctCount / records.length : 0;

  const submitAll = () => {
    if (!allChecked || submitting) return;
    setSubmitted(true);
    setRevealed(Object.fromEntries(records.map((_item, index) => [index, true])));
    setChecked(Object.fromEntries(records.map((_item, index) => [index, true])));
    onSubmit(buildResults());
  };

  return (
    <div className="mt-4 space-y-3" data-testid="guide-quiz-preview">
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line bg-white p-3">
        <div>
          <p className="text-sm font-semibold text-ink">交互式练习</p>
          <p className="mt-1 text-xs text-slate-500">每题提交后会立刻反馈对错，全部提交后再更新学习路径。</p>
        </div>
        <Badge tone={allChecked ? "success" : "neutral"}>{checkedCount}/{records.length}</Badge>
      </div>
      {records.map(({ record, qa, options }, index) => {
        const correctAnswer = readString(qa, "correct_answer") || readString(qa, "answer");
        const answer = answers[index] || "";
        const isRevealed = Boolean(revealed[index]);
        const isChecked = Boolean(checked[index]);
        const kind = normalizeGuideQuestionType(readString(qa, "question_type"), options);
        const isCorrect = answer && correctAnswer && isGuideQuizCorrect(answer, correctAnswer, options);
        return (
          <div key={`${index}-${readString(qa, "question_id")}`} className="rounded-lg border border-line bg-white p-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="neutral">题目 {index + 1}</Badge>
              <Badge tone="neutral">{guideQuestionTypeLabel(kind)}</Badge>
              {isChecked && answer ? <Badge tone={isCorrect ? "success" : correctAnswer ? "danger" : "brand"}>{guideAnswerFeedbackLabel(Boolean(isCorrect), Boolean(correctAnswer))}</Badge> : null}
            </div>
            <p className="mt-2 text-sm font-medium leading-6 text-ink">{readString(qa, "question") || readString(qa, "prompt") || readString(record, "question") || "已生成练习题"}</p>
            {options ? (
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {Object.entries(options).map(([key, value]) => (
                  <button
                    key={key}
                    type="button"
                    data-testid={`guide-quiz-option-${index}-${key}`}
                    disabled={submitted || submitting || isChecked}
                    onClick={() => {
                      markStarted(index);
                      setAnswers((current) => ({ ...current, [index]: key }));
                    }}
                    className={`rounded-lg border px-3 py-2 text-left text-sm transition disabled:cursor-not-allowed ${
                      answer === key ? "border-brand-purple-300 bg-tint-lavender text-brand-purple" : "border-line bg-white text-slate-600 hover:border-brand-purple-300"
                    }`}
                  >
                    <span className="font-semibold">{key}.</span> {String(value)}
                  </button>
                ))}
              </div>
            ) : kind === "true_false" ? (
              <div className="mt-3 grid grid-cols-2 gap-2">
                {[
                  ["True", "正确"],
                  ["False", "错误"],
                ].map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    data-testid={`guide-quiz-true-false-${index}-${value}`}
                    disabled={submitted || submitting || isChecked}
                    onClick={() => {
                      markStarted(index);
                      setAnswers((current) => ({ ...current, [index]: value }));
                    }}
                    className={`rounded-lg border px-3 py-2 text-center text-sm font-semibold transition disabled:cursor-not-allowed ${
                      answer === value ? "border-brand-purple-300 bg-tint-lavender text-brand-purple" : "border-line bg-white text-slate-600 hover:border-brand-purple-300"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            ) : (
              <TextInput
                className="mt-3"
                data-testid={`guide-quiz-input-${index}`}
                value={answer}
                disabled={submitted || submitting || isChecked}
                onChange={(event) => {
                  markStarted(index);
                  setAnswers((current) => ({ ...current, [index]: event.target.value }));
                }}
                placeholder={kind === "written" || kind === "coding" ? "写下你的答案或思路" : "输入你的答案"}
              />
            )}
            <div className="mt-3 flex flex-wrap gap-2">
              {!isChecked ? (
                <Button
                  tone="primary"
                  className="min-h-8 px-2 text-xs"
                  data-testid={`guide-quiz-submit-${index}`}
                  disabled={!answer.trim() || submitted || submitting}
                  onClick={() => {
                    const now = Date.now();
                    setStartedAt((current) => (current[index] ? current : { ...current, [index]: now }));
                    setCheckedAt((current) => ({ ...current, [index]: now }));
                    setChecked((current) => ({ ...current, [index]: true }));
                    setRevealed((current) => ({ ...current, [index]: true }));
                  }}
                >
                  <CheckCircle2 size={14} />
                  提交答案
                </Button>
              ) : (
                <>
                  <Button
                    tone="secondary"
                    className="min-h-8 px-2 text-xs"
                    onClick={() => setRevealed((current) => ({ ...current, [index]: !current[index] }))}
                  >
                    {isRevealed ? "收起解析" : "查看解析"}
                  </Button>
                  {!submitted ? (
                    <Button
                      tone="quiet"
                      className="min-h-8 px-2 text-xs"
                      onClick={() => {
                        setChecked((current) => ({ ...current, [index]: false }));
                        setCheckedAt((current) => {
                          const next = { ...current };
                          delete next[index];
                          return next;
                        });
                        setStartedAt((current) => ({ ...current, [index]: Date.now() }));
                        setRevealed((current) => ({ ...current, [index]: false }));
                      }}
                    >
                      修改答案
                    </Button>
                  ) : null}
                </>
              )}
            </div>
            {isChecked ? (
              <div className={`mt-3 rounded-lg border p-3 text-xs leading-5 ${
                correctAnswer
                  ? isCorrect
                    ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                    : "border-red-200 bg-red-50 text-red-800"
                  : "border-brand-purple-300 bg-tint-lavender text-charcoal"
              }`}>
                <p className="font-semibold">
                  {correctAnswer ? (isCorrect ? "回答正确。" : "回答不对，建议看一下解析再复盘。") : "答案已提交，请对照参考解析。"}
                </p>
              </div>
            ) : null}
            {isRevealed ? (
              <div className="mt-3 rounded-lg border border-line bg-canvas p-3 text-xs leading-5 text-slate-600">
                {correctAnswer ? <p className="font-medium text-ink">参考答案：{correctAnswer}</p> : null}
                {readString(qa, "explanation") ? <p className="mt-1">解析：{readString(qa, "explanation")}</p> : null}
              </div>
            ) : null}
          </div>
        );
      })}
      {allChecked ? (
        <div
          className={`rounded-lg border p-3 text-sm leading-6 ${
            scoreRatio >= 0.8
              ? "border-emerald-200 bg-emerald-50 text-emerald-800"
              : scoreRatio >= 0.5
                ? "border-amber-200 bg-amber-50 text-amber-800"
                : "border-red-200 bg-red-50 text-red-800"
          }`}
          data-testid="guide-quiz-score-preview"
        >
          <p className="font-semibold text-ink">
            本组练习 {correctCount}/{records.length} 题正确
          </p>
          <p className="mt-1 text-xs">
            {scoreRatio >= 0.8
              ? "整体不错，提交后系统会把掌握记录写回路线。"
              : scoreRatio >= 0.5
                ? "有一部分已经掌握，提交后系统会根据错题安排补强。"
                : "先别急着继续推进，提交后系统会优先帮你补错因。"}
          </p>
        </div>
      ) : null}
      <Button tone="primary" className="w-full" data-testid="guide-quiz-submit-all" disabled={!allChecked || submitting || submitted} onClick={submitAll}>
        {submitting ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
        {submitted ? "练习已回写" : allChecked ? "提交整组练习并更新路径" : "先逐题提交答案"}
      </Button>
    </div>
  );
}

function extractGuideQuestionConcepts(...sources: Array<Record<string, unknown>>) {
  const keys = [
    "concepts",
    "concept",
    "tested_concepts",
    "tested_concept",
    "knowledge_points",
    "knowledge_point",
    "learning_points",
    "learning_point",
    "categories",
    "category",
    "tags",
  ];
  const labels: string[] = [];
  for (const source of sources) {
    for (const key of keys) {
      for (const label of extractConceptLabels(source[key])) {
        if (label && !labels.includes(label)) labels.push(label);
      }
    }
    const metadata = asRecord(source.metadata);
    if (metadata) {
      for (const key of keys) {
        for (const label of extractConceptLabels(metadata[key])) {
          if (label && !labels.includes(label)) labels.push(label);
        }
      }
    }
  }
  return labels.slice(0, 8);
}

function extractConceptLabels(value: unknown): string[] {
  if (!value) return [];
  if (typeof value === "string") return extractStringArray(value);
  if (Array.isArray(value)) return value.flatMap(extractConceptLabels).filter(Boolean);
  const record = asRecord(value);
  if (record) {
    for (const key of ["label", "name", "title", "value", "concept", "concept_id", "id"]) {
      const text = readString(record, key).trim();
      if (text) return [text];
    }
    return [];
  }
  return [String(value).trim()].filter(Boolean);
}

function extractArtifactPersonalization(artifact: GuideV2Artifact) {
  const result = asRecord(artifact.result) ?? {};
  const config = asRecord(artifact.config) ?? {};
  const direct = asRecord(result.personalization) ?? asRecord(config.personalization);
  const hints =
    asRecord(result.learner_profile_hints) ??
    asRecord(config.learner_profile_hints) ??
    asRecord(asRecord(result.metadata ?? null)?.learner_profile_hints);

  const reasons: string[] = [];
  const signals: Array<{ label: string; value: string }> = [];

  const appendLines = (value: unknown) => {
    if (typeof value === "string") {
      splitLines(value).forEach((item) => reasons.push(item));
      return;
    }
    if (Array.isArray(value)) {
      value.map(String).map((item) => item.trim()).filter(Boolean).forEach((item) => reasons.push(item));
    }
  };

  if (direct) {
    appendLines(direct.reason);
    appendLines(direct.rationale);
    appendLines(direct.summary);
    appendLines(direct.reasons);
  }

  const weakPoints = normalizeTextArray(hints?.weak_points ?? direct?.weak_points);
  const mistakes = normalizeTextArray(hints?.mistake_patterns ?? direct?.mistake_patterns);
  const preferences = normalizeTextArray(hints?.preferences ?? direct?.preferences);
  const masteryTopics = normalizeTextArray(hints?.mastery_gaps ?? direct?.mastery_gaps);
  const level = readMaybeString(hints, "level") || readMaybeString(direct, "level");
  const timeBudget = readMaybeString(hints, "time_budget_minutes") || readMaybeString(direct, "time_budget_minutes");
  const progressStyle = deriveArtifactProgressStyle({
    artifactType: String(artifact.type),
    weakPoints,
    mistakes,
    preferences,
    masteryTopics,
    level,
    timeBudget,
  });

  if (weakPoints.length) {
    signals.push({ label: "薄弱点", value: weakPoints.slice(0, 2).join("、") });
    reasons.push(`这份资源优先照顾你当前不稳的点：${weakPoints.slice(0, 2).join("、")}。`);
  }
  if (masteryTopics.length) {
    signals.push({ label: "掌握待补", value: masteryTopics.slice(0, 2).join("、") });
  }
  if (mistakes.length) {
    signals.push({ label: "常见错因", value: mistakes.slice(0, 2).join("、") });
    reasons.push(`系统也参考了你最近暴露出的错因：${mistakes.slice(0, 2).join("、")}。`);
  }
  if (preferences.length) {
    signals.push({ label: "学习偏好", value: preferences.slice(0, 2).join("、") });
  }
  if (level) {
    signals.push({ label: "当前水平", value: level });
  }
  if (timeBudget) {
    signals.push({ label: "时间预算", value: `${String(timeBudget).replace(/[^\d]/g, "") || timeBudget} 分钟` });
  }
  if (progressStyle) {
    signals.push({ label: "推进风格", value: progressStyle.label });
    reasons.push(progressStyle.explanation);
  }

  const uniqueReasons = Array.from(new Set(reasons.map((item) => item.trim()).filter(Boolean)));
  if (!signals.length && !uniqueReasons.length) return null;

  const headline =
    uniqueReasons[0] ||
    `这份${resourceLabel(String(artifact.type))}不是随机生成的，而是结合你当前的学习记录、卡点和偏好做了针对性调整。`;

  return {
    headline,
    reasons: uniqueReasons,
    signals,
    progressStyle,
  };
}

function deriveArtifactProgressStyle({
  artifactType,
  weakPoints,
  mistakes,
  preferences,
  masteryTopics,
  level,
  timeBudget,
}: {
  artifactType: string;
  weakPoints: string[];
  mistakes: string[];
  preferences: string[];
  masteryTopics: string[];
  level: string;
  timeBudget: string;
}) {
  const normalizedPreferences = preferences.map((item) => item.toLowerCase());
  const prefersPractice = normalizedPreferences.some((item) => /练|题|quiz|practice|刷题/.test(item));
  const prefersVisual = normalizedPreferences.some((item) => /图|visual|diagram|结构|示意/.test(item));
  const prefersVideo = normalizedPreferences.some((item) => /视频|video|动画|manim/.test(item));
  const prefersAudio = normalizedPreferences.some((item) => /语音|音频|audio|speech|tts|podcast/.test(item));
  const hasWeakPoints = weakPoints.length > 0 || masteryTopics.length > 0;
  const hasMistakes = mistakes.length > 0;
  const compactTime = Number.parseInt(String(timeBudget).replace(/[^\d]/g, ""), 10);
  const lowLevel = /零基础|初学|入门|beginner/i.test(level);

  if (prefersPractice || artifactType === "quiz") {
    return {
      label: "练习驱动型",
      explanation: "系统判断你更适合先通过动手作答来压实理解，所以这份资源会更强调可检验和可反馈。",
      recommendation: "建议先独立完成，再结合反馈看错因，会比只看讲解更容易形成稳定掌握。",
    };
  }

  if (artifactType === "external_video") {
    return {
      label: "外部补充型",
      explanation: "系统判断你适合先参考公开视频，用另一个讲解视角降低理解门槛，再回到当前任务做反馈。",
      recommendation: "建议只看一到两个精选视频，不要陷入搜索；看完立刻回到导学提交一句反思。",
    };
  }

  if (prefersAudio || artifactType === "audio") {
    return {
      label: "先听后做型",
      explanation: "系统判断你更适合先用一段简洁讲解把概念和步骤听顺，再回到当前任务完成验证。",
      recommendation: "先完整听一遍，再立刻做题、看图或写一句反思，效果会比反复被动播放更好。",
    };
  }

  if (prefersVideo || artifactType === "video") {
    return {
      label: "渐进演示型",
      explanation: "系统判断你更适合跟着过程一步步进入问题，所以这份资源会把关键步骤拆开讲，而不是一次性堆满信息。",
      recommendation: "先顺着演示走一遍，再回到当前任务复述关键步骤，吸收会更扎实。",
    };
  }

  if (prefersVisual || artifactType === "visual") {
    return {
      label: "概念澄清型",
      explanation: "系统判断你当前更需要把概念边界和结构关系看清楚，所以这份资源会优先帮你建立直观理解。",
      recommendation: "先把图里的关系讲明白，再去做题或看公式推导，后续会更顺。",
    };
  }

  if (hasMistakes) {
    return {
      label: "反复校准型",
      explanation: "系统发现你最近更需要先修正错因，所以这份资源会优先对准容易出错的地方，而不是平均铺开。",
      recommendation: "重点盯住这些错因是否真的被改掉，学完后最好立刻做一次复测。",
    };
  }

  if (hasWeakPoints || lowLevel) {
    return {
      label: "渐进压实型",
      explanation: "系统判断你当前还处在补基础和压实关键节点的阶段，所以这份资源会先保住核心理解，再逐步扩展。",
      recommendation: "先吃透这一份，再继续推进下一步，比一口气看太多更适合当前状态。",
    };
  }

  if (Number.isFinite(compactTime) && compactTime > 0 && compactTime <= 12) {
    return {
      label: "快速串联型",
      explanation: "系统参考了你当前较紧的时间预算，所以这份资源会尽量快速串起关键概念和步骤。",
      recommendation: "先抓主线，不必一开始就抠所有细节，后面再按反馈补重点会更有效。",
    };
  }

  return null;
}

function normalizeTextArray(value: unknown) {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => String(item).trim())
    .filter(Boolean);
}

function readMaybeString(source: Record<string, unknown> | null | undefined, key: string) {
  if (!source) return "";
  const value = source[key];
  if (typeof value === "string" && value.trim()) return value.trim();
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return "";
}
