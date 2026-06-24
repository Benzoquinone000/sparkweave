import {
  extractExternalImageResult,
  extractExternalVideoResult,
  extractMathAnimatorResult,
  extractVisualizeResult,
} from "@/lib/capabilityResults";
import { getMessageCapability, getMessageDisplayContent } from "@/lib/chatMessages";
import { questionDifficultyLabel } from "@/lib/learningLabels";
import { extractQuizQuestions } from "@/lib/quiz";
import type { CapabilityId, ChatAttachment, ChatMessage, NotebookRecord, StreamEvent } from "@/lib/types";

const USER_QUERY_FALLBACK = "AI 学习记录";
const NOTEBOOK_METADATA_SOFT_LIMIT = 18_000;
const SHORT_TEXT_LIMIT = 240;
const MEDIUM_TEXT_LIMIT = 800;
const LONG_TEXT_LIMIT = 2_000;

type BuildNotebookAssetInput = {
  message: ChatMessage;
  messages: ChatMessage[];
  sessionId: string | null;
  turnId: string | null;
  language: "zh" | "en";
  knowledgeBase?: string | null;
};

export type NotebookAsset = {
  recordType: NotebookRecord["record_type"];
  title: string;
  summary: string;
  output: string;
  userQuery: string;
  metadata: Record<string, unknown>;
  assetKind: string;
};

export function hasNotebookAssetOutput(message: ChatMessage) {
  if (message.content.trim() || getMessageDisplayContent(message)) return true;
  if (message.attachments?.length) return true;
  const resultEvent = [...(message.events ?? [])].reverse().find((event) => event.type === "result");
  const capability = getMessageCapability(message);
  const quizQuestions = capability === "deep_question" ? extractQuizQuestions(resultEvent?.metadata) : null;
  const visualizeResult = capability === "visualize" ? extractVisualizeResult(resultEvent?.metadata) : null;
  const mathResult = capability === "math_animator" ? extractMathAnimatorResult(resultEvent?.metadata) : null;
  const externalVideoResult = extractExternalVideoResult(resultEvent?.metadata);
  const externalImageResult = extractExternalImageResult(resultEvent?.metadata);
  if (quizQuestions?.length || visualizeResult || mathResult || externalVideoResult || externalImageResult) return true;
  return Boolean(
    message.events?.some(
      (event) =>
        event.type === "result" ||
        event.type === "tool_result" ||
        Boolean(event.content?.trim()) ||
        Boolean(event.metadata && Object.keys(event.metadata).length),
    ),
  );
}

export function buildNotebookAsset({
  message,
  messages,
  sessionId,
  turnId,
  language,
  knowledgeBase,
}: BuildNotebookAssetInput): NotebookAsset {
  const messageIndex = messages.findIndex((item) => item.id === message.id);
  const previousUserQuery =
    [...messages.slice(0, Math.max(messageIndex, 0))].reverse().find((item) => item.role === "user")?.content ||
    "";
  const resultEvent = [...(message.events ?? [])].reverse().find((event) => event.type === "result");
  const displayContent = getMessageDisplayContent(message);
  const capability = getMessageCapability(message);
  const quizQuestions = capability === "deep_question" ? extractQuizQuestions(resultEvent?.metadata) : null;
  const visualizeResult = capability === "visualize" ? extractVisualizeResult(resultEvent?.metadata) : null;
  const mathResult = capability === "math_animator" ? extractMathAnimatorResult(resultEvent?.metadata) : null;
  const externalVideoResult = extractExternalVideoResult(resultEvent?.metadata);
  const externalImageResult = extractExternalImageResult(resultEvent?.metadata);
  const trace = compactTraceEvents(message.events ?? []);

  const sections = [
    displayContent ? formatMessageContentSection(message, displayContent) : "",
    message.attachments?.length ? formatAttachmentSection(message.attachments) : "",
    quizQuestions?.length ? formatQuizSection(quizQuestions) : "",
    visualizeResult ? formatVisualizationSection(visualizeResult) : "",
    mathResult ? formatMathAnimatorSection(mathResult) : "",
    externalImageResult ? formatExternalImageSection(externalImageResult) : "",
    externalVideoResult ? formatExternalVideoSection(externalVideoResult) : "",
    !displayContent && trace.length ? formatTraceSection(trace) : "",
  ].filter(Boolean);

  const assetKind = getAssetKind(message, {
    hasDisplayContent: Boolean(displayContent),
    attachmentCount: message.attachments?.length ?? 0,
    traceCount: trace.length,
    quizCount: quizQuestions?.length ?? 0,
    visualizeType: visualizeResult?.render_type,
    mathArtifactCount: mathResult?.artifacts?.length ?? 0,
    mathNarratedVideo: Boolean(mathResult?.audio_narration?.video?.asset_url),
    externalVideoCount: externalVideoResult?.videos?.length ?? 0,
    externalVideoFallback: externalVideoResult?.fallback_search === true,
    externalImageCount: externalImageResult?.images?.length ?? 0,
    externalImageFallback: externalImageResult?.fallback_search === true,
  });
  const fallbackOutput = message.role === "user" ? "这条用户消息没有文本内容，但已保存相关附件和会话位置。" : "本次消息没有直接文本内容，已保存可用的运行轨迹。";
  const output = truncateText(sections.length ? sections.join("\n\n") : displayContent || fallbackOutput, 100_000);
  const userQuery = truncateText(
    buildUserQuery({
      message,
      previousUserQuery,
      displayContent,
      assetKind,
    }),
    4_000,
  );
  const metadata = fitMetadataBudget({
    role: message.role,
    message_id: message.id,
    message_status: message.status ?? null,
    capability,
    session_id: sessionId,
    turn_id: turnId,
    created_at: message.createdAt,
    ui_language: language,
    knowledge_base: knowledgeBase ?? null,
    asset_kind: assetKind,
    attachments: compactAttachments(message.attachments ?? []),
    visualize: compactVisualizeResult(visualizeResult),
    quiz: quizQuestions?.length ? { count: quizQuestions.length } : null,
    math_animator: compactMathAnimatorResult(mathResult),
    external_image: compactExternalImageResult(externalImageResult),
    external_video: compactExternalVideoResult(externalVideoResult),
    trace,
  });

  return {
    recordType: getRecordType(capability),
    title: buildTitle({ message, userQuery, displayContent, assetKind }),
    summary: buildSummary({
      displayContent,
      assetKind,
      role: message.role,
      attachmentCount: message.attachments?.length ?? 0,
      quizCount: quizQuestions?.length ?? 0,
      visualizeType: visualizeResult?.render_type,
    }),
    output,
    userQuery,
    assetKind,
    metadata,
  };
}

function formatMessageContentSection(message: ChatMessage, displayContent: string) {
  const heading =
    message.role === "user" ? "## 用户消息" : message.role === "system" ? "## 系统消息" : "## 生成结果";
  return `${heading}\n\n${displayContent}`;
}

function formatAttachmentSection(attachments: ChatAttachment[]) {
  const lines = attachments.map((attachment, index) => {
    const size = estimateBase64Bytes(attachment.base64);
    const sizeText = size ? `，约 ${formatBytes(size)}` : "";
    return `${index + 1}. ${attachment.filename}（${attachment.mime_type || attachment.type}${sizeText}）`;
  });
  return `## 附件\n\n${lines.join("\n")}`;
}

function formatTraceSection(trace: ReturnType<typeof compactTraceEvents>) {
  const lines = trace.map((event, index) => {
    const stage = event.stage ? ` / ${event.stage}` : "";
    const content = event.content ? `：${event.content}` : "";
    return `${index + 1}. ${event.type}${stage}${content}`;
  });
  return `## 会话轨迹\n\n${lines.join("\n")}`;
}

function buildUserQuery({
  message,
  previousUserQuery,
  displayContent,
  assetKind,
}: {
  message: ChatMessage;
  previousUserQuery: string;
  displayContent: string;
  assetKind: string;
}) {
  if (message.role === "user") {
    return message.content.trim() || `${USER_QUERY_FALLBACK}：用户附件或空白消息`;
  }
  return previousUserQuery.trim() || displayContent.trim() || `${USER_QUERY_FALLBACK}：${assetKind}`;
}

function buildTitle({
  message,
  userQuery,
  displayContent,
  assetKind,
}: {
  message: ChatMessage;
  userQuery: string;
  displayContent: string;
  assetKind: string;
}) {
  const source =
    message.role === "user"
      ? message.content || userQuery || assetKind
      : userQuery || displayContent || assetKind;
  const prefix = message.role === "user" ? "用户消息" : assetKind;
  const compact = source.replace(/\s+/g, " ").trim();
  if (!compact || compact === prefix) return truncateText(prefix, 48);
  return truncateText(`${prefix}：${compact}`, 48);
}

function compactTraceEvents(events: StreamEvent[]) {
  return events
    .filter((event) => event.type !== "content")
    .slice(-18)
    .map((event) => ({
      type: event.type,
      source: event.source || "",
      stage: event.stage || "",
      content: truncateText(event.content || "", SHORT_TEXT_LIMIT),
      seq: event.seq,
      timestamp: event.timestamp,
      metadata: compactEventMetadata(event.metadata),
    }));
}

function compactEventMetadata(metadata?: Record<string, unknown>) {
  if (!metadata) return {};
  return stripEmpty({
    capability: asText(metadata.capability),
    target_capability: asText(metadata.target_capability),
    selected_route: asText(metadata.selected_route),
    direct_tool: asText(metadata.direct_tool),
    tool_name: asText(metadata.tool_name),
    render_type: asText(metadata.render_type),
    result_count: asNumber(metadata.result_count),
    fallback_search: metadata.fallback_search === true ? true : undefined,
    success: typeof metadata.success === "boolean" ? metadata.success : undefined,
  });
}

function compactAttachments(attachments: ChatAttachment[]) {
  return attachments.map((attachment) => ({
    type: attachment.type,
    filename: truncateText(attachment.filename, SHORT_TEXT_LIMIT),
    mime_type: truncateText(attachment.mime_type, SHORT_TEXT_LIMIT),
    estimated_bytes: estimateBase64Bytes(attachment.base64),
  }));
}

function compactVisualizeResult(result: ReturnType<typeof extractVisualizeResult>) {
  if (!result) return null;
  return stripEmpty({
    render_type: result.render_type,
    style_hint: result.style_hint,
    chart_type: result.analysis?.chart_type,
    description: truncateText(result.analysis?.description || "", MEDIUM_TEXT_LIMIT),
    code_language: result.code.language,
    code_preview: truncateText(result.code.content, LONG_TEXT_LIMIT),
  });
}

function compactMathAnimatorResult(result: ReturnType<typeof extractMathAnimatorResult>) {
  if (!result) return null;
  return stripEmpty({
    output_mode: result.output_mode,
    style_hint: result.style_hint,
    artifact_count: result.artifacts?.length ?? 0,
    artifacts: (result.artifacts ?? []).slice(0, 8).map((item) => ({
      type: item.type,
      filename: item.filename,
      url: item.url,
    })),
    narrated_video: result.audio_narration?.video?.asset_url || "",
    narration_audio: result.audio_narration?.audio?.asset_url || "",
  });
}

function compactExternalVideoResult(result: ReturnType<typeof extractExternalVideoResult>) {
  if (!result) return null;
  return stripEmpty({
    render_type: "external_video",
    fallback_search: result.fallback_search === true,
    response: truncateText(result.response || "", MEDIUM_TEXT_LIMIT),
    watch_plan: (result.watch_plan ?? []).slice(0, 5).map((item) => truncateText(item, SHORT_TEXT_LIMIT)),
    reflection_prompt: truncateText(result.reflection_prompt || "", SHORT_TEXT_LIMIT),
    queries: (result.queries ?? []).slice(0, 6).map((item) => truncateText(item, SHORT_TEXT_LIMIT)),
    videos: (result.videos ?? []).slice(0, 12).map((item) =>
      stripEmpty({
        title: truncateText(item.title || "", SHORT_TEXT_LIMIT),
        url: item.url || "",
        platform: item.platform || "",
        kind: item.kind || "",
        channel: truncateText(item.channel || "", SHORT_TEXT_LIMIT),
        duration_seconds: item.duration_seconds ?? undefined,
        why_recommended: truncateText(item.why_recommended || item.summary || "", MEDIUM_TEXT_LIMIT),
      }),
    ),
    tool_chain: (result.tool_chain ?? result.agent_chain ?? []).slice(0, 8).map((item) =>
      stripEmpty({
        label: truncateText(item.label || "", SHORT_TEXT_LIMIT),
        detail: truncateText(item.detail || "", SHORT_TEXT_LIMIT),
        state: "state" in item ? truncateText(String(item.state || ""), SHORT_TEXT_LIMIT) : undefined,
      }),
    ),
  });
}

function compactExternalImageResult(result: ReturnType<typeof extractExternalImageResult>) {
  if (!result) return null;
  return stripEmpty({
    render_type: "external_image",
    fallback_search: result.fallback_search === true,
    response: truncateText(result.response || "", MEDIUM_TEXT_LIMIT),
    view_plan: (result.view_plan ?? []).slice(0, 5).map((item) => truncateText(item, SHORT_TEXT_LIMIT)),
    reflection_prompt: truncateText(result.reflection_prompt || "", SHORT_TEXT_LIMIT),
    queries: (result.queries ?? []).slice(0, 6).map((item) => truncateText(item, SHORT_TEXT_LIMIT)),
    images: (result.images ?? []).slice(0, 12).map((item) =>
      stripEmpty({
        title: truncateText(item.title || "", SHORT_TEXT_LIMIT),
        url: item.url || item.image_url || item.thumbnail || "",
        source: truncateText(item.source || "", SHORT_TEXT_LIMIT),
        kind: item.kind || "",
        license: truncateText(item.license || "", SHORT_TEXT_LIMIT),
        why_recommended: truncateText(item.why_recommended || item.summary || "", MEDIUM_TEXT_LIMIT),
      }),
    ),
    tool_chain: (result.tool_chain ?? result.agent_chain ?? []).slice(0, 8).map((item) =>
      stripEmpty({
        label: truncateText(item.label || "", SHORT_TEXT_LIMIT),
        detail: truncateText(item.detail || "", SHORT_TEXT_LIMIT),
        state: "state" in item ? truncateText(String(item.state || ""), SHORT_TEXT_LIMIT) : undefined,
      }),
    ),
  });
}

function fitMetadataBudget(metadata: Record<string, unknown>) {
  let next = stripEmpty(metadata);
  if (jsonSize(next) <= NOTEBOOK_METADATA_SOFT_LIMIT) return next;

  next = {
    ...next,
    trace: Array.isArray(next.trace) ? next.trace.slice(-8) : undefined,
    metadata_truncated: true,
  };
  if (jsonSize(next) <= NOTEBOOK_METADATA_SOFT_LIMIT) return stripEmpty(next);

  next = {
    ...next,
    trace: undefined,
    metadata_truncated: true,
  };
  if (jsonSize(next) <= NOTEBOOK_METADATA_SOFT_LIMIT) return stripEmpty(next);

  return stripEmpty({
    role: metadata.role,
    message_id: metadata.message_id,
    message_status: metadata.message_status,
    capability: metadata.capability,
    session_id: metadata.session_id,
    turn_id: metadata.turn_id,
    created_at: metadata.created_at,
    ui_language: metadata.ui_language,
    knowledge_base: metadata.knowledge_base,
    asset_kind: metadata.asset_kind,
    metadata_truncated: true,
  });
}

function getRecordType(capability: CapabilityId | undefined): NotebookRecord["record_type"] {
  if (capability === "deep_solve") return "solve";
  if (capability === "deep_question") return "question";
  if (capability === "deep_research") return "research";
  return "chat";
}

function getAssetKind(
  message: ChatMessage,
  {
    hasDisplayContent,
    attachmentCount,
    traceCount,
    quizCount,
    visualizeType,
    mathArtifactCount,
    mathNarratedVideo,
    externalVideoCount,
    externalVideoFallback,
    externalImageCount,
    externalImageFallback,
  }: {
    hasDisplayContent: boolean;
    attachmentCount: number;
    traceCount: number;
    quizCount: number;
    visualizeType?: string;
    mathArtifactCount: number;
    mathNarratedVideo: boolean;
    externalVideoCount: number;
    externalVideoFallback: boolean;
    externalImageCount: number;
    externalImageFallback: boolean;
  },
) {
  const capability = getMessageCapability(message);
  if (quizCount) return `题目练习 · ${quizCount} 题`;
  if (visualizeType) return `知识可视化 · ${visualizeType}`;
  if (mathNarratedVideo) return "数学讲解成片";
  if (mathArtifactCount) return `数学动画 · ${mathArtifactCount} 个产物`;
  if (externalImageCount) return `${externalImageFallback ? "图片搜索入口" : "精选图片"} · ${externalImageCount} 张`;
  if (externalVideoCount) return `${externalVideoFallback ? "视频搜索入口" : "精选视频"} · ${externalVideoCount} 个`;
  if (capability === "deep_solve") return "深度解题";
  if (capability === "deep_research") return "研究报告";
  if (message.role === "user") return attachmentCount ? `用户消息 · ${attachmentCount} 个附件` : "用户消息";
  if (attachmentCount) return `会话附件 · ${attachmentCount} 个`;
  if (hasDisplayContent) return "AI 对话";
  if (traceCount) return "会话轨迹";
  return "AI 对话";
}

function buildSummary({
  displayContent,
  assetKind,
  role,
  attachmentCount,
  quizCount,
  visualizeType,
}: {
  displayContent: string;
  assetKind: string;
  role: ChatMessage["role"];
  attachmentCount: number;
  quizCount: number;
  visualizeType?: string;
}) {
  if (quizCount) return `${assetKind}，包含题干、参考答案与解析。`;
  if (visualizeType) return `${assetKind}，已保存渲染源码与说明。`;
  const compact = displayContent.replace(/\s+/g, " ").trim();
  if (compact && role === "user") return `保存了一条用户消息：${compact.slice(0, 120)}`;
  if (!compact && attachmentCount) return `${assetKind}，包含 ${attachmentCount} 个附件。`;
  return compact ? compact.slice(0, 140) : assetKind;
}

function formatQuizSection(questions: NonNullable<ReturnType<typeof extractQuizQuestions>>) {
  const lines = questions.map((question, index) => {
    const options = question.options
      ? Object.entries(question.options)
          .map(([key, value]) => `   - ${key}. ${value}`)
          .join("\n")
      : "";
    return [
      `${index + 1}. ${question.question}`,
      options,
      `   - 参考答案：${question.correct_answer || "未提供"}`,
      question.explanation ? `   - 解析：${question.explanation}` : "",
      question.difficulty ? `   - 难度：${questionDifficultyLabel(question.difficulty)}` : "",
    ]
      .filter(Boolean)
      .join("\n");
  });
  return `## 题目练习\n\n${lines.join("\n\n")}`;
}

function formatVisualizationSection(result: NonNullable<ReturnType<typeof extractVisualizeResult>>) {
  const language = result.code.language || result.render_type;
  return [
    "## 可视化资源",
    "",
    `- 渲染模式：${result.render_type}`,
    result.analysis?.chart_type ? `- 图表类型：${result.analysis.chart_type}` : "",
    result.analysis?.description ? `- 说明：${result.analysis.description}` : "",
    "",
    `\`\`\`${language}`,
    result.code.content,
    "```",
  ]
    .filter(Boolean)
    .join("\n");
}

function formatMathAnimatorSection(result: NonNullable<ReturnType<typeof extractMathAnimatorResult>>) {
  const artifacts = (result.artifacts ?? [])
    .map((item) => `- ${item.type}: ${item.filename} (${item.url})`)
    .join("\n");
  const narratedVideo = result.audio_narration?.video?.asset_url
    ? `- narrated_video: ${result.audio_narration.video.filename || "narrated.mp4"} (${result.audio_narration.video.asset_url})`
    : "";
  const narrationAudio = !narratedVideo && result.audio_narration?.audio?.asset_url
    ? `- narration_audio: ${result.audio_narration.audio.filename || "narration.mp3"} (${result.audio_narration.audio.asset_url})`
    : "";
  const code = result.code?.content
    ? ["", "```python", result.code.content, "```"].join("\n")
    : "";
  return ["## 数学讲解资源", "", narratedVideo, narrationAudio, artifacts || "- 暂无渲染产物", code].filter(Boolean).join("\n");
}

function formatExternalVideoSection(result: NonNullable<ReturnType<typeof extractExternalVideoResult>>) {
  const heading = result.fallback_search ? "## 视频搜索入口" : "## 精选视频";
  const plan = formatPlanSection("建议看法", result.watch_plan, result.reflection_prompt);
  const videos = (result.videos ?? [])
    .map((item, index) =>
      [
        `${index + 1}. [${item.title}](${item.url})`,
        item.kind === "search_fallback" ? "   - 类型：搜索入口" : "",
        item.platform ? `   - 平台：${item.platform}` : "",
        item.channel ? `   - 来源：${item.channel}` : "",
        item.why_recommended ? `   - 推荐原因：${item.why_recommended}` : "",
      ]
        .filter(Boolean)
        .join("\n"),
    )
    .join("\n\n");
  return [heading, "", result.response || "", plan, videos || "- 暂无可保存的视频链接"].filter(Boolean).join("\n");
}

function formatExternalImageSection(result: NonNullable<ReturnType<typeof extractExternalImageResult>>) {
  const heading = result.fallback_search ? "## 图片搜索入口" : "## 精选图片";
  const plan = formatPlanSection("建议看法", result.view_plan, result.reflection_prompt);
  const images = (result.images ?? [])
    .map((item, index) =>
      [
        `${index + 1}. [${item.title}](${item.url || item.image_url || item.thumbnail})`,
        item.kind === "search_fallback" ? "   - 类型：搜索入口" : "",
        item.source ? `   - 来源：${item.source}` : "",
        item.license ? `   - 授权：${item.license}` : "",
        item.why_recommended ? `   - 推荐原因：${item.why_recommended}` : "",
      ]
        .filter(Boolean)
        .join("\n"),
    )
    .join("\n\n");
  return [heading, "", result.response || "", plan, images || "- 暂无可保存的图片链接"].filter(Boolean).join("\n");
}

function formatPlanSection(title: string, steps?: string[], reflectionPrompt?: string) {
  const planSteps = (steps ?? []).filter(Boolean);
  const reflection = String(reflectionPrompt || "").trim();
  if (!planSteps.length && !reflection) return "";
  const lines = [
    `### ${title}`,
    "",
    ...planSteps.map((step, index) => `${index + 1}. ${step}`),
    reflection ? `> ${reflection}` : "",
  ];
  return lines.filter(Boolean).join("\n");
}

function truncateText(value: unknown, limit: number) {
  const text = String(value ?? "").trim();
  if (text.length <= limit) return text;
  return `${text.slice(0, Math.max(0, limit - 1))}…`;
}

function stripEmpty<T extends Record<string, unknown>>(value: T): Record<string, unknown> {
  const entries = Object.entries(value).filter(([, item]) => {
    if (item === null || item === undefined) return false;
    if (typeof item === "string") return item.trim().length > 0;
    if (Array.isArray(item)) return item.length > 0;
    if (typeof item === "object") return Object.keys(item as Record<string, unknown>).length > 0;
    return true;
  });
  return Object.fromEntries(entries);
}

function asText(value: unknown) {
  return typeof value === "string" && value.trim() ? truncateText(value, SHORT_TEXT_LIMIT) : undefined;
}

function asNumber(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function jsonSize(value: unknown) {
  try {
    return JSON.stringify(value).length;
  } catch {
    return Number.POSITIVE_INFINITY;
  }
}

function estimateBase64Bytes(base64: string) {
  const clean = base64.replace(/^data:[^,]+,/, "").replace(/\s/g, "");
  if (!clean) return 0;
  const padding = clean.endsWith("==") ? 2 : clean.endsWith("=") ? 1 : 0;
  return Math.max(0, Math.floor((clean.length * 3) / 4) - padding);
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
