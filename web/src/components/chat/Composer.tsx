import { AnimatePresence, motion } from "framer-motion";
import { FileText, Paperclip, SendHorizontal, Square, X } from "lucide-react";
import { useRef, useState } from "react";

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
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const submit = () => {
    if (!content.trim() || disabled) return;
    onSend(content, attachments);
    setContent("");
    setAttachments([]);
  };

  const handleFiles = async (files: FileList | null) => {
    if (!files?.length) return;
    const next: ChatAttachment[] = [];
    for (const file of Array.from(files)) {
      const base64 = await readFileBase64(file);
      next.push({
        type: file.type.startsWith("image/") ? "image" : "file",
        filename: file.name,
        mime_type: file.type,
        base64,
      });
    }
    setAttachments((current) => [...current, ...next]);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  return (
    <div className="rounded-lg border border-line bg-white p-2 shadow-soft">
      <AnimatePresence initial={false}>
      {attachments.length ? (
        <div className="mb-2 flex flex-wrap gap-2">
          {attachments.map((attachment, index) => (
            <motion.div
              key={`${attachment.filename}-${index}`}
              className="group flex max-w-full items-center gap-2 rounded-lg border border-line bg-surface p-2 text-xs text-steel"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.18 }}
            >
              {attachment.type === "image" ? (
                <img
                  src={`data:${attachment.mime_type};base64,${attachment.base64}`}
                  alt={attachment.filename}
                  className="h-10 w-10 rounded-md border border-line bg-white object-cover"
                />
              ) : (
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-line bg-white text-brand-blue">
                  <FileText size={16} />
                </span>
              )}
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
      <textarea
        value={content}
        onChange={(event) => setContent(event.target.value)}
        onKeyDown={(event) => {
          if ((event.ctrlKey || event.metaKey) && event.key === "Enter") submit();
        }}
        placeholder="输入你想解决的问题..."
        className="min-h-20 w-full resize-none rounded-lg border border-transparent bg-white px-3 py-2 text-sm leading-6 text-ink outline-none transition placeholder:text-steel focus:border-[#c8c4be] focus:bg-surface"
      />
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 border-t border-line px-1 pt-2">
        <div className="flex items-center gap-2">
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
            className="dt-interactive inline-flex h-9 items-center gap-2 rounded-lg border border-line px-3 text-sm text-steel hover:border-[#c8c4be] hover:text-ink"
          >
            <Paperclip size={16} />
            附件
          </button>
          <span className="hidden text-xs text-steel sm:inline">Ctrl/⌘ + Enter</span>
        </div>
        <div className="flex items-center gap-2">
          {disabled ? (
            <button
              type="button"
              data-testid="chat-cancel"
              onClick={onCancel}
              className="dt-interactive inline-flex h-9 items-center gap-2 rounded-lg border border-red-200 px-3 text-sm font-medium text-brand-red hover:bg-red-50"
            >
              <Square size={14} />
              停止
            </button>
          ) : null}
          <button
            type="button"
            data-testid="chat-send"
            onClick={submit}
            disabled={!content.trim() || disabled}
            aria-label="发送"
            className="dt-interactive inline-flex h-9 items-center gap-2 rounded-lg bg-brand-purple px-4 text-sm font-semibold text-white hover:bg-[#4534b3] disabled:cursor-not-allowed disabled:bg-[#bbb8b1]"
          >
            <SendHorizontal size={16} />
            发送
          </button>
        </div>
      </div>
    </div>
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
