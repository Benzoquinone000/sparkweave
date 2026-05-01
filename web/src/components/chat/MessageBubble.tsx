import { motion } from "framer-motion";
import { Bot, Check, Copy, FileText, Save, UserRound } from "lucide-react";
import { useMemo, useState } from "react";

import { AgentCollaborationPanel } from "@/components/chat/AgentCollaborationPanel";
import { Badge } from "@/components/ui/Badge";
import { MarkdownRenderer } from "@/components/ui/MarkdownRenderer";
import { QuizViewer } from "@/components/quiz/QuizViewer";
import { ExternalVideoViewer } from "@/components/results/ExternalVideoViewer";
import { MathAnimatorViewer } from "@/components/results/MathAnimatorViewer";
import { VisualizationViewer } from "@/components/results/VisualizationViewer";
import { extractExternalVideoResult, extractMathAnimatorResult, extractVisualizeResult } from "@/lib/capabilityResults";
import { getMessageCapability, getMessageDisplayContent } from "@/lib/chatMessages";
import { capabilityLabel } from "@/lib/capabilities";
import { hasNotebookAssetOutput } from "@/lib/notebookAssets";
import { extractQuizQuestions } from "@/lib/quiz";
import type { ChatMessage } from "@/lib/types";

export function MessageBubble({
  message,
  onSave,
  sessionId,
}: {
  message: ChatMessage;
  onSave?: (message: ChatMessage) => void;
  sessionId?: string | null;
}) {
  const isUser = message.role === "user";
  const events = message.events ?? [];
  const traceEvents = events.filter((event) => event.type !== "content" && event.type !== "done");
  const resultEvent = events.find((event) => event.type === "result");
  const effectiveCapability = useMemo(() => getMessageCapability(message), [message]);
  const displayContent = useMemo(() => getMessageDisplayContent(message), [message]);
  const quizQuestions =
    !isUser && effectiveCapability === "deep_question" ? extractQuizQuestions(resultEvent?.metadata) : null;
  const mathAnimatorResult =
    !isUser && effectiveCapability === "math_animator" ? extractMathAnimatorResult(resultEvent?.metadata) : null;
  const visualizeResult =
    !isUser && effectiveCapability === "visualize" ? extractVisualizeResult(resultEvent?.metadata) : null;
  const externalVideoResult = !isUser ? extractExternalVideoResult(resultEvent?.metadata) : null;
  const canSaveAsset = !isUser && hasNotebookAssetOutput(message);

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: "easeOut" }}
      className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}
    >
      {!isUser ? (
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-teal-50 text-brand-teal">
          <Bot size={18} />
        </div>
      ) : null}
      <div className={`max-w-[min(760px,100%)] ${isUser ? "order-first" : ""}`}>
        <div
          className={`rounded-lg border p-4 ${
            isUser ? "border-teal-200 bg-teal-50" : "border-line bg-white"
          }`}
        >
          <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
            <span className={`font-semibold ${isUser ? "text-brand-teal" : "text-ink"}`}>
              {isUser ? "你" : message.status === "streaming" ? "SparkWeave 正在回答" : "SparkWeave"}
            </span>
            {effectiveCapability ? <Badge tone="neutral">{capabilityLabel(effectiveCapability)}</Badge> : null}
            {message.attachments?.length ? <Badge tone="warning">{message.attachments.length} 个附件</Badge> : null}
            {!isUser && (displayContent || canSaveAsset) ? (
              <div className="ml-auto flex gap-2">
                {displayContent ? <CopyButton content={displayContent} /> : null}
                {onSave && canSaveAsset ? (
                  <button
                    type="button"
                    onClick={() => onSave({ ...message, content: displayContent || message.content })}
                    aria-label="保存当前结果"
                    className="inline-flex min-h-8 items-center gap-1 rounded-md border border-line bg-white px-2 text-xs text-slate-600 transition hover:border-teal-200 hover:text-brand-teal"
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
            <MathAnimatorViewer result={mathAnimatorResult} />
          ) : externalVideoResult ? (
            <ExternalVideoViewer result={externalVideoResult} />
          ) : visualizeResult ? (
            <VisualizationViewer result={visualizeResult} />
          ) : quizQuestions?.length ? (
            <QuizViewer questions={quizQuestions} sessionId={sessionId} />
          ) : displayContent ? (
            <MarkdownRenderer className="markdown-body">{displayContent}</MarkdownRenderer>
          ) : (
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <span className="h-2 w-2 animate-pulse rounded-sm bg-brand-blue" />
              正在组织解答
            </div>
          )}
        </div>
        {!isUser && traceEvents.length ? (
          <AgentCollaborationPanel
            events={traceEvents}
            capability={effectiveCapability}
            status={message.status === "error" ? "error" : message.status === "streaming" ? "streaming" : "done"}
          />
        ) : null}
      </div>
      {isUser ? (
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-teal text-white">
          <UserRound size={18} />
        </div>
      ) : null}
    </motion.article>
  );
}

function AttachmentStrip({ attachments }: { attachments: NonNullable<ChatMessage["attachments"]> }) {
  return (
    <div className="mb-3 flex flex-wrap gap-2">
      {attachments.map((attachment, index) =>
        attachment.type === "image" ? (
          <a
            key={`${attachment.filename}-${index}`}
            href={`data:${attachment.mime_type};base64,${attachment.base64}`}
            target="_blank"
            rel="noreferrer"
            className="block overflow-hidden rounded-lg border border-line bg-white"
          >
            <img
              src={`data:${attachment.mime_type};base64,${attachment.base64}`}
              alt={attachment.filename}
              className="h-28 w-36 object-cover"
            />
          </a>
        ) : (
          <div key={`${attachment.filename}-${index}`} className="flex items-center gap-2 rounded-lg border border-line bg-white px-3 py-2 text-xs text-slate-600">
            <FileText size={15} className="text-brand-blue" />
            <span className="max-w-[220px] truncate">{attachment.filename}</span>
          </div>
        ),
      )}
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
      className="inline-flex min-h-8 items-center gap-1 rounded-md border border-line bg-white px-2 text-xs text-slate-600 transition hover:border-teal-200 hover:text-brand-teal"
    >
      {copied ? <Check size={13} /> : <Copy size={13} />}
      {copied ? "已复制" : "复制"}
    </button>
  );
}


