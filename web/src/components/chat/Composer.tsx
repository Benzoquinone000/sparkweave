import { AnimatePresence, motion } from "framer-motion";
import { FileText, Mic2, Paperclip, SendHorizontal, Square, X } from "lucide-react";
import { type KeyboardEvent, useEffect, useLayoutEffect, useRef, useState } from "react";

import { transcribeSpeechAudio } from "@/lib/api";
import { getAttachmentPreviewDataUrl, isPreviewableImageMime } from "@/lib/attachmentPreviews";
import { CHAT_LIMITS } from "@/lib/requestLimits";
import {
  finishBrowserPcmWavRecording,
  isBrowserPcmRecordingSupported,
  startBrowserPcmRecording,
  stopBrowserPcmRecording,
  type BrowserPcmRecording,
} from "@/lib/speechRecording";
import type { ChatAttachment } from "@/lib/types";

export function Composer({
  disabled,
  onFocusChange,
  onSend,
  onCancel,
}: {
  disabled?: boolean;
  onFocusChange?: (focused: boolean) => void;
  onSend: (content: string, attachments: ChatAttachment[]) => void;
  onCancel: () => void;
}) {
  const [content, setContent] = useState("");
  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);
  const [attachmentError, setAttachmentError] = useState("");
  const [speechLoading, setSpeechLoading] = useState(false);
  const [recording, setRecording] = useState(false);
  const [sendPulse, setSendPulse] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const audioInputRef = useRef<HTMLInputElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const recordingRef = useRef<BrowserPcmRecording | null>(null);
  const pulseTimerRef = useRef<number | null>(null);

  useLayoutEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "0px";
    textarea.style.height = `${Math.min(Math.max(textarea.scrollHeight, 34), 104)}px`;
  }, [content]);

  useEffect(() => {
    return () => {
      stopBrowserPcmRecording(recordingRef.current);
      recordingRef.current = null;
      if (pulseTimerRef.current) {
        window.clearTimeout(pulseTimerRef.current);
      }
    };
  }, []);

  const submit = () => {
    if (!content.trim() || disabled) return;
    setSendPulse(true);
    if (pulseTimerRef.current) {
      window.clearTimeout(pulseTimerRef.current);
    }
    pulseTimerRef.current = window.setTimeout(() => setSendPulse(false), 720);
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

  const transcribeAudioFile = async (file: File, audioEncoding?: string) => {
    if (speechLoading) return;
    setAttachmentError("");
    setSpeechLoading(true);
    try {
      if (file.size > 20 * 1024 * 1024) {
        setAttachmentError("语音文件不能超过 20MB");
        return;
      }
      const result = await transcribeSpeechAudio({ file, audioEncoding });
      if (!result.success || !result.text?.trim()) {
        setAttachmentError(result.error || "语音转写失败");
        return;
      }
      setContent((current) => {
        const text = result.text?.trim() || "";
        return current.trim() ? `${current.trimEnd()}\n${text}` : text;
      });
    } catch (error) {
      setAttachmentError(error instanceof Error ? error.message : "语音转写失败");
    } finally {
      setSpeechLoading(false);
    }
  };

  const handleSpeechFile = async (files: FileList | null) => {
    const file = files?.[0];
    if (!file) return;
    try {
      await transcribeAudioFile(file);
    } finally {
      if (audioInputRef.current) audioInputRef.current.value = "";
    }
  };

  const startRecording = async () => {
    if (disabled || speechLoading || recording) return;
    if (!isBrowserPcmRecordingSupported()) {
      audioInputRef.current?.click();
      return;
    }
    setAttachmentError("");
    try {
      recordingRef.current = await startBrowserPcmRecording();
      setRecording(true);
    } catch (error) {
      setAttachmentError(error instanceof Error ? error.message : "无法开始录音");
    }
  };

  const stopRecording = async () => {
    const current = recordingRef.current;
    if (!current) return;
    recordingRef.current = null;
    setRecording(false);
    const result = await finishBrowserPcmWavRecording(current);
    if (result.durationMs < 300 || !result.chunkCount) {
      setAttachmentError("录音时间太短");
      return;
    }
    await transcribeAudioFile(result.file, "raw");
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.nativeEvent.isComposing || event.key === "Process" || event.key !== "Enter" || event.shiftKey) return;
    event.preventDefault();
    submit();
  };

  return (
    <div
      className={`dt-composer-shell rounded-lg border px-2 py-1.5 shadow-[0_10px_30px_rgba(15,15,15,0.08)] ${
        disabled ? "dt-composer-shell-busy" : ""
      } ${sendPulse ? "dt-composer-shell-pulse" : ""}`}
      onFocusCapture={() => onFocusChange?.(true)}
      onBlurCapture={(event) => {
        const nextTarget = event.relatedTarget;
        if (nextTarget instanceof Node && event.currentTarget.contains(nextTarget)) return;
        onFocusChange?.(false);
      }}
    >
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
      <textarea
        ref={textareaRef}
        rows={1}
        value={content}
        onChange={(event) => setContent(event.target.value)}
        maxLength={CHAT_LIMITS.message}
        onKeyDown={handleKeyDown}
        placeholder="输入你想解决的问题..."
        className="max-h-28 min-h-9 w-full resize-none overflow-y-auto bg-transparent px-1.5 py-1.5 text-sm leading-5 text-ink outline-none placeholder:text-steel"
      />
      <div className="mt-1 flex items-center justify-between gap-2">
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(event) => void handleFiles(event.target.files)}
        />
        <input
          ref={audioInputRef}
          type="file"
          accept="audio/mpeg,audio/mp3,audio/wav,.mp3,.pcm,.wav,.speex"
          className="hidden"
          onChange={(event) => void handleSpeechFile(event.target.files)}
        />
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={attachments.length >= CHAT_LIMITS.attachments}
            aria-label="添加附件"
            title="添加附件"
            className="dt-interactive inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-steel hover:bg-surface hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Paperclip size={17} />
          </button>
          <button
            type="button"
            onClick={() => void (recording ? stopRecording() : startRecording())}
            disabled={speechLoading || (disabled && !recording)}
            aria-label="语音转文字"
            title={recording ? "停止录音并转文字" : "语音转文字"}
            className={`dt-interactive inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md disabled:cursor-not-allowed disabled:opacity-50 ${
              recording ? "bg-red-50 text-brand-red hover:bg-red-100" : "text-steel hover:bg-surface hover:text-ink"
            }`}
          >
            <Mic2 size={17} className={speechLoading || recording ? "animate-pulse" : ""} />
          </button>
        </div>
        <div className="flex items-center gap-1.5">
          {disabled ? (
            <button
              type="button"
              data-testid="chat-cancel"
              onClick={onCancel}
              aria-label="停止生成"
              title="停止生成"
              className="dt-interactive inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-red-200 text-brand-red hover:bg-red-50"
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
            className="dt-interactive inline-flex h-8 shrink-0 items-center justify-center gap-1.5 rounded-md bg-ink px-2.5 text-sm font-medium text-white hover:bg-charcoal disabled:cursor-not-allowed disabled:bg-[#bbb8b1] sm:px-3"
          >
            <SendHorizontal size={16} />
            <span className="hidden sm:inline">发送</span>
          </button>
        </div>
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
        className="h-7 w-7 rounded-md border border-line bg-white object-cover"
      />
    );
  }

  return (
    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-line bg-white text-brand-blue">
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
