import { Loader2, MessageSquareText, SendHorizontal, type LucideIcon } from "lucide-react";
import type { ChangeEvent } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FileInput } from "@/components/ui/Field";
import type { AssistantMultimodalAction, AssistantMultimodalActionId, AssistantResourcePreviewState } from "./useAssistantMultimodalPreview";

export function AssistantMultimodalActionsPanel({
  actions,
  preview,
  onAction,
  onOcrFileChange,
  onSendOcrToAssistant,
  onUsePrompt,
}: {
  actions: AssistantMultimodalAction[];
  preview: AssistantResourcePreviewState;
  onAction: (action: AssistantMultimodalAction) => void;
  onOcrFileChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onSendOcrToAssistant: () => void;
  onUsePrompt: (prompt: string) => void;
}) {
  const ttsAction = actions.find((action) => action.id === "tts_script");
  const ocrAction = actions.find((action) => action.id === "ocr");

  return (
    <div className="mt-4 border-t border-line pt-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-ink">多模态资源动作</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">先生成可审阅脚本，再接入讯飞 OCR、TTS 或视频生成流程。</p>
        </div>
        <Badge tone="brand">科大讯飞工具链</Badge>
      </div>
      <div className="mt-3 grid gap-2 md:grid-cols-4">
        {actions.map((action) => (
          <MultimodalActionButton key={action.id} action={action} onClick={() => onAction(action)} />
        ))}
      </div>
      {preview.actionId ? (
        <div className="mt-3 border border-line bg-canvas p-3" style={{ borderRadius: 8 }} data-testid="assistant-resource-preview">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs font-semibold text-brand-purple">资源预览</p>
              <h3 className="mt-1 text-sm font-semibold text-ink">{assistantResourcePreviewTitle(preview.actionId)}</h3>
              <p className="mt-1 text-xs leading-5 text-slate-500">{preview.message}</p>
            </div>
            <Badge tone={assistantPreviewBadgeTone(preview.status)}>{assistantPreviewStatusLabel(preview.status)}</Badge>
          </div>

          {preview.actionId === "tts_script" ? (
            <TtsPreview preview={preview} onUsePrompt={onUsePrompt} ttsPrompt={ttsAction?.prompt} />
          ) : null}

          {preview.actionId === "ocr" ? (
            <OcrPreview
              preview={preview}
              onOcrFileChange={onOcrFileChange}
              onSendOcrToAssistant={onSendOcrToAssistant}
              onUsePrompt={onUsePrompt}
              ocrPrompt={ocrAction?.prompt}
            />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function MultimodalActionButton({ action, onClick }: { action: AssistantMultimodalAction; onClick: () => void }) {
  const Icon: LucideIcon = action.icon;
  return (
    <button
      type="button"
      className="dt-interactive border border-line bg-canvas p-3 text-left transition hover:border-brand-purple-300 hover:bg-white"
      style={{ borderRadius: 8 }}
      onClick={onClick}
      data-testid={`assistant-multimodal-action-${action.id}`}
    >
      <Icon size={17} className="text-brand-purple" />
      <span className="mt-2 block text-sm font-semibold text-ink">{action.title}</span>
      <span className="mt-1 block text-xs leading-5 text-slate-500">{action.detail}</span>
    </button>
  );
}

function TtsPreview({
  preview,
  onUsePrompt,
  ttsPrompt,
}: {
  preview: AssistantResourcePreviewState;
  onUsePrompt: (prompt: string) => void;
  ttsPrompt?: string;
}) {
  return (
    <div className="mt-3 grid gap-3" data-testid="assistant-tts-preview">
      {preview.status === "running" ? (
        <p className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 size={15} className="animate-spin" />
          正在合成试听
        </p>
      ) : null}
      {preview.ttsUrl ? (
        <div className="grid gap-2">
          <audio controls src={preview.ttsUrl} className="w-full" />
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <Badge tone="neutral">{preview.ttsVoice || "讯飞 TTS"}</Badge>
            <span>{preview.ttsContentType || "audio/mpeg"}</span>
          </div>
        </div>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Button tone="secondary" onClick={() => ttsPrompt && onUsePrompt(ttsPrompt)} disabled={!ttsPrompt}>
          <MessageSquareText size={15} />
          发给助教优化脚本
        </Button>
      </div>
    </div>
  );
}

function OcrPreview({
  preview,
  onOcrFileChange,
  onSendOcrToAssistant,
  onUsePrompt,
  ocrPrompt,
}: {
  preview: AssistantResourcePreviewState;
  onOcrFileChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onSendOcrToAssistant: () => void;
  onUsePrompt: (prompt: string) => void;
  ocrPrompt?: string;
}) {
  return (
    <div className="mt-3 grid gap-3" data-testid="assistant-ocr-preview">
      <FileInput
        accept="image/png,image/jpeg,image/webp"
        buttonLabel="选择截图"
        emptyLabel={preview.ocrFileName || "未选择图片"}
        onChange={onOcrFileChange}
        data-testid="assistant-ocr-file-input"
      />
      {preview.status === "running" ? (
        <p className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 size={15} className="animate-spin" />
          正在识别文字
        </p>
      ) : null}
      {preview.ocrPreviewUrl || preview.ocrText ? (
        <div className="grid gap-3 md:grid-cols-[140px_minmax(0,1fr)]">
          {preview.ocrPreviewUrl ? (
            <img
              src={preview.ocrPreviewUrl}
              alt={preview.ocrFileName || "OCR 预览图"}
              className="h-28 w-full rounded-lg border border-line bg-white object-contain"
            />
          ) : null}
          <div className="min-w-0 rounded-lg bg-white px-3 py-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs font-semibold text-ink">OCR 识别结果</p>
              {preview.ocrProvider ? <Badge tone="neutral">{preview.ocrProvider}</Badge> : null}
            </div>
            <p className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap text-sm leading-6 text-slate-600">
              {preview.ocrText || "等待识别结果"}
            </p>
          </div>
        </div>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Button tone="secondary" onClick={onSendOcrToAssistant} disabled={!preview.ocrText} data-testid="assistant-ocr-send">
          <SendHorizontal size={15} />
          让助教讲解识别结果
        </Button>
        <Button tone="quiet" onClick={() => ocrPrompt && onUsePrompt(ocrPrompt)} disabled={!ocrPrompt}>
          生成 OCR 讲解流程
        </Button>
      </div>
    </div>
  );
}

function assistantResourcePreviewTitle(actionId: AssistantMultimodalActionId) {
  if (actionId === "tts_script") return "讯飞 TTS 试听";
  if (actionId === "ocr") return "讯飞 OCR 识别";
  if (actionId === "video_script") return "短视频脚本草稿";
  return "图解方案草稿";
}

function assistantPreviewStatusLabel(status: AssistantResourcePreviewState["status"]) {
  if (status === "running") return "生成中";
  if (status === "success") return "已就绪";
  if (status === "error") return "需处理";
  return "待操作";
}

function assistantPreviewBadgeTone(status: AssistantResourcePreviewState["status"]): "neutral" | "success" | "warning" | "brand" {
  if (status === "running") return "brand";
  if (status === "success") return "success";
  if (status === "error") return "warning";
  return "neutral";
}
