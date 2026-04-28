import { extractMathAnimatorResult, extractVisualizeResult } from "@/lib/capabilityResults";
import { getMessageCapability, getMessageDisplayContent } from "@/lib/chatMessages";
import { extractQuizQuestions } from "@/lib/quiz";
import type { CapabilityId, ChatMessage, NotebookRecord } from "@/lib/types";

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
  const resultEvent = [...(message.events ?? [])].reverse().find((event) => event.type === "result");
  const capability = getMessageCapability(message);
  const quizQuestions = capability === "deep_question" ? extractQuizQuestions(resultEvent?.metadata) : null;
  const visualizeResult = capability === "visualize" ? extractVisualizeResult(resultEvent?.metadata) : null;
  const mathResult = capability === "math_animator" ? extractMathAnimatorResult(resultEvent?.metadata) : null;
  return Boolean(getMessageDisplayContent(message) || quizQuestions?.length || visualizeResult || mathResult);
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
  const userQuery =
    [...messages.slice(0, Math.max(messageIndex, 0))].reverse().find((item) => item.role === "user")?.content ||
    "AI 学习记录";
  const resultEvent = [...(message.events ?? [])].reverse().find((event) => event.type === "result");
  const displayContent = getMessageDisplayContent(message);
  const capability = getMessageCapability(message);
  const quizQuestions = capability === "deep_question" ? extractQuizQuestions(resultEvent?.metadata) : null;
  const visualizeResult = capability === "visualize" ? extractVisualizeResult(resultEvent?.metadata) : null;
  const mathResult = capability === "math_animator" ? extractMathAnimatorResult(resultEvent?.metadata) : null;
  const trace = (message.events ?? [])
    .filter((event) => event.type !== "content")
    .map((event) => ({
      type: event.type,
      stage: event.stage,
      content: event.content,
      metadata: event.metadata,
      seq: event.seq,
      timestamp: event.timestamp,
    }));

  const sections = [
    displayContent ? `## 生成结果\n\n${displayContent}` : "",
    quizQuestions?.length ? formatQuizSection(quizQuestions) : "",
    visualizeResult ? formatVisualizationSection(visualizeResult) : "",
    mathResult ? formatMathAnimatorSection(mathResult) : "",
  ].filter(Boolean);

  const assetKind = getAssetKind(message, {
    quizCount: quizQuestions?.length ?? 0,
    visualizeType: visualizeResult?.render_type,
    mathArtifactCount: mathResult?.artifacts?.length ?? 0,
  });
  const output = sections.length ? sections.join("\n\n") : displayContent || "本次任务暂无可保存内容。";

  return {
    recordType: getRecordType(capability),
    title: userQuery.slice(0, 48),
    summary: buildSummary({ displayContent, assetKind, quizCount: quizQuestions?.length ?? 0, visualizeType: visualizeResult?.render_type }),
    output,
    userQuery,
    assetKind,
    metadata: {
      capability,
      session_id: sessionId,
      turn_id: turnId,
      ui_language: language,
      knowledge_base: knowledgeBase ?? null,
      asset_kind: assetKind,
      visualize: visualizeResult ?? null,
      quiz: quizQuestions?.length ? { count: quizQuestions.length, questions: quizQuestions } : null,
      math_animator: mathResult ?? null,
      trace,
    },
  };
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
    quizCount,
    visualizeType,
    mathArtifactCount,
  }: {
    quizCount: number;
    visualizeType?: string;
    mathArtifactCount: number;
  },
) {
  const capability = getMessageCapability(message);
  if (quizCount) return `题目练习 · ${quizCount} 题`;
  if (visualizeType) return `知识可视化 · ${visualizeType}`;
  if (mathArtifactCount) return `数学动画 · ${mathArtifactCount} 个产物`;
  if (capability === "deep_solve") return "深度解题";
  if (capability === "deep_research") return "研究报告";
  return "AI 对话";
}

function buildSummary({
  displayContent,
  assetKind,
  quizCount,
  visualizeType,
}: {
  displayContent: string;
  assetKind: string;
  quizCount: number;
  visualizeType?: string;
}) {
  if (quizCount) return `${assetKind}，包含题干、参考答案与解析。`;
  if (visualizeType) return `${assetKind}，已保存渲染源码与说明。`;
  const compact = displayContent.replace(/\s+/g, " ").trim();
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
      question.difficulty ? `   - 难度：${question.difficulty}` : "",
    ]
      .filter(Boolean)
      .join("\n");
  });
  return `## 题目练习\n\n${lines.join("\n\n")}`;
}

function formatVisualizationSection(result: NonNullable<ReturnType<typeof extractVisualizeResult>>) {
  const language = result.code.language || result.render_type;
  return [
    "## 可视化资产",
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
  const code = result.code?.content
    ? ["", "```python", result.code.content, "```"].join("\n")
    : "";
  return ["## 数学动画资产", "", artifacts || "- 暂无渲染产物", code].filter(Boolean).join("\n");
}
