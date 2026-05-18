import { AnimatePresence, motion } from "framer-motion";
import { FileText, Paperclip, SendHorizontal, Square, X } from "lucide-react";
import { type KeyboardEvent, useLayoutEffect, useRef, useState } from "react";

import { getAttachmentPreviewDataUrl, isPreviewableImageMime } from "@/lib/attachmentPreviews";
import { CHAT_LIMITS } from "@/lib/requestLimits";
import type { ChatAttachment } from "@/lib/types";

export function Composer({
  disabled,
  onSend,
  onCancel,
}: {
  disabled?: boolean;
  onSend: (content: string, attachments: ChatAttachment[]) => void;
  onCancel: () => void;
}) {
  const [content, setContent] = useState("");
  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);
  const [attachmentError, setAttachmentError] = useState("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useLayoutEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "0px";
    textarea.style.height = `${Math.min(Math.max(textarea.scrollHeight, 36), 128)}px`;
  }, [content]);

  const submit = () => {
    if (!content.trim() || disabled) return;
    onSend(content, attachments);
    setContent("");
    setAttachments([]);
    setAttachmentError("");
  };

  const handleFiles = async (files: FileList | null) => {
    if (!files?.length) return;
    setAttachmentError("");
    const remaining = Math.max(0, CHAT_LIMITS.attachments - attachments.length);
    if (!remaining) {
      setAttachmentError(`最多添加 ${CHAT_LIMITS.attachments} 个附件`);
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }
    const next: ChatAttachment[] = [];
    for (const file of Array.from(files).slice(0, remaining)) {
      if (file.size > CHAT_LIMITS.attachmentBytes) {
        setAttachmentError(`附件不能超过 ${Math.round(CHAT_LIMITS.attachmentBytes / 1024 / 1024)}MB`);
        continue;
      }
      const base64 = await readFileBase64(file);
      next.push({
        type: isPreviewableImageMime(file.type) ? "image" : "file",
        filename: file.name.slice(0, CHAT_LIMITS.filename),
        mime_type: file.type,
        base64,
      });
    }
    setAttachments((current) => [...current, ...next]);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.nativeEvent.isComposing || event.key === "Process" || event.key !== "Enter" || event.shiftKey) return;
    event.preventDefault();
    submit();
  };

  return (
    <div className="rounded-lg border border-line bg-white px-2 py-1.5 shadow-[0_1px_2px_rgba(15,15,15,0.04)] transition focus-within:border-line-strong focus-within:bg-white">
      <AnimatePresence initial={false}>
      {attachments.length ? (
        <div className="mb-1.5 flex flex-wrap gap-2 border-b border-line pb-1.5">
          {attachments.map((attachment, index) => (
            <motion.div
              key={`${attachment.filename}-${index}`}
              className="group flex max-w-full items-center gap-2 rounded-md border border-line bg-surface px-2 py-1.5 text-xs text-steel"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.18 }}
            >
              <AttachmentPreviewIcon attachment={attachment} />
              <span className="max-w-[190px] truncate">{attachment.filename}</span>
              <button
                type="button"
                onClick={() => setAttachments((current) => current.filter((_, itemIndex) => itemIndex !== index))}
                className="dt-interactive rounded-md p-1 text-steel hover:bg-white hover:text-brand-red"
                title="点击移除"
              >
                <X size={13} />
              </button>
            </motion.div>
          ))}
        </div>
      ) : null}
      </AnimatePresence>
      {attachmentError ? <p className="mb-1.5 rounded-md bg-red-50 px-2.5 py-1.5 text-xs text-brand-red">{attachmentError}</p> : null}
      <div className="flex items-end gap-1.5">
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(event) => void handleFiles(event.target.files)}
        />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={attachments.length >= CHAT_LIMITS.attachments}
          aria-label="添加附件"
          title="添加附件"
          className="dt-interactive inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-steel hover:bg-surface hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Paperclip size={17} />
        </button>
        <textarea
          ref={textareaRef}
          rows={1}
          value={content}
          onChange={(event) => setContent(event.target.value)}
          maxLength={CHAT_LIMITS.message}
          onKeyDown={handleKeyDown}
          placeholder="输入你想解决的问题..."
          className="max-h-32 min-h-9 min-w-0 flex-1 resize-none overflow-y-auto bg-transparent px-1.5 py-2 text-sm leading-5 text-ink outline-none placeholder:text-steel"
        />
        {disabled ? (
          <button
            type="button"
            data-testid="chat-cancel"
            onClick={onCancel}
            aria-label="停止生成"
            title="停止生成"
            className="dt-interactive inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-red-200 text-brand-red hover:bg-red-50"
          >
            <Square size={14} />
          </button>
        ) : null}
        <button
          type="button"
          data-testid="chat-send"
          onClick={submit}
          disabled={!content.trim() || disabled}
          aria-label="发送"
          title="发送"
          className="dt-interactive inline-flex h-9 shrink-0 items-center justify-center gap-1.5 rounded-md bg-ink px-2.5 text-sm font-medium text-white hover:bg-charcoal disabled:cursor-not-allowed disabled:bg-[#bbb8b1] sm:px-3"
        >
          <SendHorizontal size={16} />
          <span className="hidden sm:inline">发送</span>
        </button>
      </div>
    </div>
  );
}

function AttachmentPreviewIcon({ attachment }: { attachment: ChatAttachment }) {
  const previewUrl = getAttachmentPreviewDataUrl(attachment);
  if (previewUrl) {
    return (
      <img
        src={previewUrl}
        alt={attachment.filename}
        className="h-8 w-8 rounded-md border border-line bg-white object-cover"
      />
    );
  }

  return (
    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-line bg-white text-brand-blue">
      <FileText size={15} />
    </span>
  );
}

function readFileBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const value = String(reader.result || "");
      resolve(value.includes(",") ? value.split(",")[1] : value);
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}
