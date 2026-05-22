import { AnimatePresence, motion } from "framer-motion";
import { Check, Copy, Download, Eye, FilePenLine, Save, X } from "lucide-react";
import { useRef, useState } from "react";

import { MarkdownRenderer } from "@/components/ui/MarkdownRenderer";
import type { ChatCanvasDocument } from "@/lib/chatCanvas";
import type { ChatMessage } from "@/lib/types";

export function ChatCanvasPanel({
  document,
  open,
  onClose,
  onDocumentChange,
  onSaveMessage,
}: {
  document: ChatCanvasDocument | null;
  open: boolean;
  onClose: () => void;
  onDocumentChange?: (document: ChatCanvasDocument, dirty: boolean) => void;
  onSaveMessage: (message: ChatMessage) => void;
}) {
  const [mode, setMode] = useState<"edit" | "preview">("edit");
  const [title, setTitle] = useState(() => document?.title ?? "");
  const [draft, setDraft] = useState(() => document?.content ?? "");
  const [copied, setCopied] = useState(false);
  const [dirty, setDirty] = useState(false);
  const originalTitleRef = useRef(document?.title ?? "");
  const originalContentRef = useRef(document?.content ?? "");
  const editorRef = useRef<HTMLTextAreaElement | null>(null);

  if (!document) return null;

  const saveEditedDocument = () => {
    const content = (editorRef.current?.value ?? draft).trim();
    if (!content) return;
    const editedMessage = { ...document.sourceMessage, content };
    onSaveMessage(editedMessage);
    // The visible canvas can outlive a session URL sync for a moment; notify the active chat page too.
    window.dispatchEvent(new CustomEvent("sparkweave:canvas-save-message", { detail: editedMessage }));
  };

  const downloadDraft = () => {
    const content = editorRef.current?.value ?? draft;
    if (!content.trim()) return;
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = window.document.createElement("a");
    anchor.href = url;
    anchor.download = `${safeFileName(title || document.title || "canvas")}.md`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const copyDraft = async () => {
    await navigator.clipboard.writeText(editorRef.current?.value ?? draft);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  const emitDocumentChange = (nextTitle: string, nextDraft: string) => {
    const nextDirty = nextTitle !== originalTitleRef.current || nextDraft !== originalContentRef.current;
    setDirty(nextDirty);
    onDocumentChange?.(
      {
        ...document,
        title: nextTitle.trim() || document.title,
        content: nextDraft,
        updatedAt: Date.now(),
      },
      nextDirty,
    );
  };

  const updateTitle = (nextTitle: string) => {
    setTitle(nextTitle);
    emitDocumentChange(nextTitle, editorRef.current?.value ?? draft);
  };

  const updateDraft = (nextDraft: string) => {
    setDraft(nextDraft);
    emitDocumentChange(title, nextDraft);
  };

  return (
    <AnimatePresence>
      {open ? (
        <motion.aside
          data-testid="chat-canvas-panel"
          className="dt-dynamic-drawer fixed inset-0 z-30 flex flex-col border-l border-line bg-surface shadow-panel lg:static lg:z-auto lg:w-[clamp(460px,44vw,760px)] lg:shrink-0 lg:shadow-none"
          initial={{ x: 620, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: 620, opacity: 0 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
        >
          <div className="dt-dynamic-toolbar flex min-h-14 shrink-0 items-start justify-between gap-2.5 border-b border-line bg-white/90 px-3.5 py-2.5 backdrop-blur">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-tint-lavender text-brand-purple">
                  <FilePenLine size={14} />
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-ink">画布</p>
                  <input
                    value={title}
                    onChange={(event) => updateTitle(event.target.value)}
                    aria-label="画布标题"
                    className="block w-full min-w-0 truncate rounded border-0 bg-transparent p-0 text-xs text-slate-500 outline-none focus:text-ink"
                  />
                </div>
              </div>
              <p className="mt-1 text-xs text-stone">{dirty ? "已编辑，会随下一条消息带入" : "下一条消息可继续修改这份文档"}</p>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="关闭画布"
              className="dt-interactive inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-line text-slate-600 hover:border-brand-purple-300 hover:text-brand-purple"
            >
              <X size={15} />
            </button>
          </div>

          <div className="dt-dynamic-toolbar flex shrink-0 flex-wrap items-center gap-2 border-b border-line bg-canvas px-4 py-2.5">
            <div className="dt-dynamic-panel inline-flex rounded-lg border border-line bg-white p-0.5">
              <button
                type="button"
                aria-pressed={mode === "edit"}
                onClick={() => setMode("edit")}
                className={`dt-interactive inline-flex h-8 items-center gap-1.5 rounded-md px-2.5 text-xs font-medium transition ${
                  mode === "edit" ? "bg-ink text-white" : "text-slate-600 hover:bg-surface hover:text-ink"
                }`}
              >
                <FilePenLine size={14} />
                编辑
              </button>
              <button
                type="button"
                aria-pressed={mode === "preview"}
                onClick={() => setMode("preview")}
                className={`dt-interactive inline-flex h-8 items-center gap-1.5 rounded-md px-2.5 text-xs font-medium transition ${
                  mode === "preview" ? "bg-ink text-white" : "text-slate-600 hover:bg-surface hover:text-ink"
                }`}
              >
                <Eye size={14} />
                预览
              </button>
            </div>
            <button
              type="button"
              onClick={() => void copyDraft()}
              className="dt-interactive inline-flex h-9 items-center gap-1.5 rounded-lg border border-line bg-white px-3 text-xs font-medium text-slate-600 hover:border-brand-purple-300 hover:text-brand-purple"
            >
              {copied ? <Check size={14} /> : <Copy size={14} />}
              {copied ? "已复制" : "复制"}
            </button>
            <button
              type="button"
              onClick={downloadDraft}
              disabled={!draft.trim()}
              className="dt-interactive inline-flex h-9 items-center gap-1.5 rounded-lg border border-line bg-white px-3 text-xs font-medium text-slate-600 hover:border-brand-purple-300 hover:text-brand-purple disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Download size={14} />
              下载
            </button>
            <button
              type="button"
              data-testid="chat-canvas-save"
              onClick={saveEditedDocument}
              disabled={!draft.trim()}
              className="dt-interactive dt-energy-button ml-auto inline-flex h-9 items-center gap-1.5 rounded-lg border border-brand-purple bg-brand-purple px-3 text-xs font-medium text-white hover:bg-brand-purple-800 disabled:cursor-not-allowed disabled:border-line disabled:bg-line disabled:text-stone"
            >
              <Save size={14} />
              保存到笔记
            </button>
          </div>

          <div className="min-h-0 flex-1 overflow-hidden bg-surface">
            {mode === "edit" ? (
              <textarea
                ref={editorRef}
                data-testid="chat-canvas-editor"
                defaultValue={draft}
                onInput={(event) => updateDraft(event.currentTarget.value)}
                onChange={(event) => updateDraft(event.target.value)}
                spellCheck={false}
                className="dt-dynamic-code h-full w-full resize-none overflow-y-auto border-0 bg-surface px-4 py-4 text-sm leading-6 text-ink outline-none placeholder:text-stone lg:px-5"
                placeholder="在这里编辑这份文档..."
              />
            ) : (
              <div className="dt-dynamic-result h-full overflow-y-auto px-5 py-5 lg:px-7">
                {draft.trim() ? (
                  <MarkdownRenderer className="markdown-body">{draft}</MarkdownRenderer>
                ) : (
                  <p className="text-sm text-slate-500">暂无可预览内容。</p>
                )}
              </div>
            )}
          </div>
        </motion.aside>
      ) : null}
    </AnimatePresence>
  );
}

function safeFileName(value: string) {
  const compact = value
    .replace(/[\\/:*?"<>|]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  return (compact || "canvas").slice(0, 80);
}
