import { motion } from "framer-motion";
import { Bot, Check, Copy, FilePenLine, FileText, Save, UserRound } from "lucide-react";
import { lazy, Suspense, useMemo, useState } from "react";

import { RagRetrievalStatus } from "@/components/chat/RagRetrievalStatus";
import { LazyExternalImageViewer, LazyExternalVideoViewer, LazyMathAnimatorViewer } from "@/components/results/LazyMediaResultViewers";
import { LazyVisualizationViewer } from "@/components/results/LazyVisualizationViewer";
import { Badge } from "@/components/ui/Badge";
import { MarkdownRenderer } from "@/components/ui/MarkdownRenderer";
import { getAttachmentPreviewDataUrl } from "@/lib/attachmentPreviews";
import {
  extractExternalImageResult,
  extractExternalVideoResult,
  extractMathAnimatorResult,
  extractVisualizeResult,
} from "@/lib/capabilityResults";
import { capabilityLabel } from "@/lib/capabilities";
import { getCanvasDocumentFromMessage, type ChatCanvasDocument } from "@/lib/chatCanvas";
import { getMessageCapability, getMessageDisplayContent } from "@/lib/chatMessages";
import { hasNotebookAssetOutput } from "@/lib/notebookAssets";
import { extractQuizQuestions } from "@/lib/quiz";
import { extractRagEvidence } from "@/lib/ragEvidence";
import type { ChatMessage } from "@/lib/types";

const AgentCollaborationPanel = lazy(() =>
  import("@/components/chat/AgentCollaborationPanel").then((module) => ({ default: module.AgentCollaborationPanel })),
);
const QuizViewer = lazy(() => import("@/components/quiz/QuizViewer").then((module) => ({ default: module.QuizViewer })));
const RagEvidenceChain = lazy(() =>
  import("@/components/results/RagEvidenceChain").then((module) => ({ default: module.RagEvidenceChain })),
);

export function MessageBubble({
  message,
  onOpenCanvas,
  onSave,
  sessionId,
}: {
  message: ChatMessage;
  onOpenCanvas?: (document: ChatCanvasDocument) => void;
  onSave?: (message: ChatMessage) => void;
  sessionId?: string | null;
}) {
  const isUser = message.role === "user";
  const events = useMemo(() => message.events ?? [], [message.events]);
  const traceEvents = events.filter((event) => event.type !== "content" && event.type !== "done");
  const resultEvent = [...events].reverse().find((event) => event.type === "result");
  const effectiveCapability = useMemo(() => getMessageCapability(message), [message]);
  const displayContent = useMemo(() => getMessageDisplayContent(message), [message]);
  const ragEvidence = useMemo(() => (!isUser ? extractRagEvidence(events) : null), [events, isUser]);
  const quizQuestions =
    !isUser && effectiveCapability === "deep_question" ? extractQuizQuestions(resultEvent?.metadata) : null;
  const mathAnimatorResult =
    !isUser && effectiveCapability === "math_animator" ? extractMathAnimatorResult(resultEvent?.metadata) : null;
  const visualizeResult =
    !isUser && effectiveCapability === "visualize" ? extractVisualizeResult(resultEvent?.metadata) : null;
  const externalVideoResult = !isUser ? extractExternalVideoResult(resultEvent?.metadata) : null;
  const externalImageResult = !isUser ? extractExternalImageResult(resultEvent?.metadata) : null;
  const hasNarratedMathVideo = Boolean(mathAnimatorResult?.audio_narration?.video?.asset_url);
  const canSaveAsset = !isUser && hasNotebookAssetOutput(message);
  const canvasDocument = useMemo(
    () => (!isUser ? getCanvasDocumentFromMessage(message, { mode: "manual" }) : null),
    [isUser, message],
  );
  const showAssistantActions = !isUser && (Boolean(displayContent) || canSaveAsset || Boolean(canvasDocument));

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: "easeOut" }}
      className={`flex gap-2.5 ${isUser ? "justify-end" : "justify-start"}`}
    >
      {!isUser ? (
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-tint-lavender text-brand-purple">
          <Bot size={16} />
        </div>
      ) : null}
      <div className={`max-w-[min(720px,100%)] ${isUser ? "order-first" : ""}`}>
        <div className={`rounded-lg border p-3 shadow-sm ${isUser ? "border-transparent bg-tint-yellow" : "border-line bg-white"}`}>
          <div className="mb-2 flex flex-wrap items-center gap-1.5 text-xs">
            <span className={`font-semibold ${isUser ? "text-charcoal" : "text-ink"}`}>
              {isUser ? "你" : message.status === "streaming" ? "SparkWeave 正在回答" : "SparkWeave"}
            </span>
            {effectiveCapability ? <Badge tone="neutral">{capabilityLabel(effectiveCapability)}</Badge> : null}
            {hasNarratedMathVideo ? <Badge tone="success">带旁白成片</Badge> : null}
            {message.attachments?.length ? <Badge tone="warning">{message.attachments.length} 个附件</Badge> : null}
            {showAssistantActions ? (
              <div className="ml-auto flex flex-wrap justify-end gap-2">
                {onOpenCanvas && canvasDocument ? (
                  <button
                    type="button"
                    onClick={() => onOpenCanvas(canvasDocument)}
                    aria-label="在画布中编辑"
                    className="inline-flex min-h-7 items-center gap-1 rounded-md border border-line bg-white px-2 text-xs text-steel transition hover:border-[#c8c4be] hover:text-brand-purple"
                  >
                    <FilePenLine size={13} />
                    画布
                  </button>
                ) : null}
                {displayContent ? <CopyButton content={displayContent} /> : null}
                {onSave && canSaveAsset ? (
                  <button
                    type="button"
                    onClick={() => onSave({ ...message, content: displayContent || message.content })}
                    aria-label="保存当前结果"
                    className="inline-flex min-h-7 items-center gap-1 rounded-md border border-line bg-white px-2 text-xs text-steel transition hover:border-[#c8c4be] hover:text-brand-purple"
                  >
                    <Save size={13} />
                    保存
                  </button>
                ) : null}
              </div>
            ) : null}
          </div>
          {message.attachments?.length ? <AttachmentStrip attachments={message.attachments} /> : null}
          {mathAnimatorResult ? (
            <LazyMathAnimatorViewer result={mathAnimatorResult} />
          ) : externalImageResult ? (
            <LazyExternalImageViewer result={externalImageResult} />
          ) : externalVideoResult ? (
            <LazyExternalVideoViewer result={externalVideoResult} />
          ) : visualizeResult ? (
            <LazyVisualizationViewer result={visualizeResult} />
          ) : quizQuestions?.length ? (
            <Suspense fallback={<InlineResultLoading label="正在准备练习题" />}>
              <QuizViewer questions={quizQuestions} sessionId={sessionId} />
            </Suspense>
          ) : displayContent ? (
            <MarkdownRenderer className="markdown-body">{displayContent}</MarkdownRenderer>
          ) : (
            <div className="flex items-center gap-2 text-xs text-steel">
              <span className="h-2 w-2 animate-pulse rounded-sm bg-brand-blue" />
              正在组织解答
            </div>
          )}
          {!isUser && !ragEvidence ? <RagRetrievalStatus events={events} className="mt-3" /> : null}
          {ragEvidence ? (
            <Suspense fallback={<InlineResultLoading label="正在准备证据链" />}>
              <RagEvidenceChain evidence={ragEvidence} className="mt-3" />
            </Suspense>
          ) : null}
        </div>
        {!isUser && traceEvents.length ? (
          <Suspense fallback={<InlineResultLoading label="正在准备协作轨迹" />}>
            <AgentCollaborationPanel
              events={traceEvents}
              capability={effectiveCapability}
              status={message.status === "error" ? "error" : message.status === "streaming" ? "streaming" : "done"}
            />
          </Suspense>
        ) : null}
      </div>
      {isUser ? (
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-brand-purple text-white">
          <UserRound size={16} />
        </div>
      ) : null}
    </motion.article>
  );
}

function InlineResultLoading({ label }: { label: string }) {
  return (
    <div className="mt-3 rounded-lg border border-line bg-canvas px-3 py-2 text-xs text-slate-500">
      <span className="font-medium text-ink">{label}</span>
    </div>
  );
}

function AttachmentStrip({ attachments }: { attachments: NonNullable<ChatMessage["attachments"]> }) {
  return (
    <div className="mb-2 flex flex-wrap gap-1.5">
      {attachments.map((attachment, index) => (
        <AttachmentStripItem key={`${attachment.filename}-${index}`} attachment={attachment} />
      ))}
    </div>
  );
}

function AttachmentStripItem({ attachment }: { attachment: NonNullable<ChatMessage["attachments"]>[number] }) {
  const previewUrl = getAttachmentPreviewDataUrl(attachment);
  if (previewUrl) {
    return (
      <a href={previewUrl} download={attachment.filename} className="block overflow-hidden rounded-md border border-line bg-white">
        <img src={previewUrl} alt={attachment.filename} className="h-20 w-28 object-cover" />
      </a>
    );
  }

  return (
    <div className="flex items-center gap-2 rounded-md border border-line bg-white px-2.5 py-1.5 text-xs text-steel">
      <FileText size={15} className="text-brand-blue" />
      <span className="max-w-[220px] truncate">{attachment.filename}</span>
    </div>
  );
}

function CopyButton({ content }: { content: string }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  return (
    <button
      type="button"
      onClick={() => void copy()}
      className="inline-flex min-h-7 items-center gap-1 rounded-md border border-line bg-white px-2 text-xs text-steel transition hover:border-[#c8c4be] hover:text-brand-purple"
    >
      {copied ? <Check size={13} /> : <Copy size={13} />}
      {copied ? "已复制" : "复制"}
    </button>
  );
}
