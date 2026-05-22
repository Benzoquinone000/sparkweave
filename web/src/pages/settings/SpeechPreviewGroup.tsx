import { Loader2, Mic2, Square, Upload, Volume2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { TextArea } from "@/components/ui/Field";
import { evaluateSpeechAudio, previewTts, transcribeSpeechAudio } from "@/lib/api";
import {
  finishBrowserPcmWavRecording,
  isBrowserPcmRecordingSupported,
  startBrowserPcmRecording,
  stopBrowserPcmRecording,
  type BrowserPcmRecording,
} from "@/lib/speechRecording";
import type { SpeechEvaluateResponse } from "@/lib/types";

import { friendlyServiceError } from "./settingsDiagnosticsUtils";

export function SpeechPreviewGroup() {
  return (
    <details className="group" data-testid="settings-speech-preview-group">
      <summary className="dt-interactive flex cursor-pointer list-none items-center justify-between gap-3 rounded-lg border border-line bg-white p-3 [&::-webkit-details-marker]:hidden">
        <span>
          <span className="flex items-center gap-2 text-base font-semibold text-ink">
            <Volume2 size={18} className="text-brand-red" />
            语音试听与试录
          </span>
          <span className="mt-1 block text-sm text-slate-500">
            按需试听讲解、试录转写和验证口语评测，不写入学习记录。
          </span>
        </span>
        <Badge tone="neutral">
          <span className="group-open:hidden">展开</span>
          <span className="hidden group-open:inline">收起</span>
        </Badge>
      </summary>
      <div className="mt-3 space-y-3">
        <TtsPreviewPanel />
        <AsrPreviewPanel />
        <SpeechEvalPreviewPanel />
      </div>
    </details>
  );
}

function AsrPreviewPanel() {
  const [recording, setRecording] = useState(false);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("保存语音输入配置后，可在这里录一小段测试转写。");
  const [transcript, setTranscript] = useState("");
  const [fallbackReason, setFallbackReason] = useState("");
  const recordingRef = useRef<BrowserPcmRecording | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    return () => {
      stopBrowserPcmRecording(recordingRef.current);
      recordingRef.current = null;
    };
  }, []);

  const transcribeFile = async (file: File, audioEncoding?: string) => {
    if (pending) return;
    if (file.size > 20 * 1024 * 1024) {
      setMessage("转写失败：音频不能超过 20MB");
      return;
    }
    setPending(true);
    setMessage("正在转写音频。");
    setFallbackReason("");
    try {
      const result = await transcribeSpeechAudio({ file, audioEncoding });
      const text = result.text?.trim() || "";
      if (!result.success || !text) {
        setTranscript("");
        setFallbackReason("");
        setMessage(`转写失败：${friendlyServiceError(result.error || "语音转写失败")}`);
        return;
      }
      setTranscript(text);
      if (result.fallback) {
        setFallbackReason(fallbackReasonText(result.fallback_reason, "讯飞 ASR 不可用，已使用离线替补。"));
        setMessage("转写完成：离线替补结果，请手动确认文本。");
      } else {
        setMessage(result.sid ? `转写完成：${result.sid}` : "转写完成。");
      }
    } catch (error) {
      const detail = error instanceof Error ? error.message : "语音转写失败";
      setTranscript("");
      setFallbackReason("");
      setMessage(`转写失败：${friendlyServiceError(detail)}`);
    } finally {
      setPending(false);
    }
  };

  const startRecording = async () => {
    if (pending || recording) return;
    if (!isBrowserPcmRecordingSupported()) {
      fileInputRef.current?.click();
      return;
    }
    try {
      recordingRef.current = await startBrowserPcmRecording();
      setRecording(true);
      setTranscript("");
      setMessage("正在录音，完成后会自动转写。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "无法开始录音");
    }
  };

  const stopRecording = async () => {
    const current = recordingRef.current;
    if (!current) return;
    recordingRef.current = null;
    setRecording(false);
    const result = await finishBrowserPcmWavRecording(current, "sparkweave-asr-preview.wav");
    if (result.durationMs < 500 || !result.chunkCount) {
      setMessage("录音时间太短，请再试一次。");
      return;
    }
    await transcribeFile(result.file, "raw");
  };

  return (
    <section className="rounded-lg border border-line bg-white p-3" data-testid="settings-asr-preview">
      <input
        ref={fileInputRef}
        type="file"
        accept="audio/mpeg,audio/mp3,audio/wav,.mp3,.pcm,.wav,.speex"
        className="hidden"
        onChange={(event) => {
          const file = event.currentTarget.files?.[0];
          if (file) void transcribeFile(file);
          event.currentTarget.value = "";
        }}
      />
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Mic2 size={18} className="text-brand-blue" />
            <h2 className="text-base font-semibold text-ink">语音输入试录</h2>
          </div>
          <p className="mt-1 text-sm leading-6 text-slate-500">录一小段话，确认当前讯飞 ASR 配置能转成文字。</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            tone="secondary"
            disabled={pending || recording}
            onClick={() => fileInputRef.current?.click()}
            data-testid="settings-asr-preview-upload"
          >
            <Upload size={16} />
            上传音频
          </Button>
          <Button
            type="button"
            tone={recording ? "danger" : "secondary"}
            disabled={pending}
            onClick={() => {
              void (recording ? stopRecording() : startRecording());
            }}
            data-testid="settings-asr-preview-record"
          >
            {pending ? (
              <Loader2 size={16} className="animate-spin" />
            ) : recording ? (
              <Square size={15} />
            ) : (
              <Mic2 size={16} />
            )}
            {recording ? "停止并转写" : "开始录音"}
          </Button>
        </div>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_260px]">
        <TextArea
          value={transcript}
          readOnly
          placeholder="转写结果会显示在这里"
          className="min-h-20 resize-none bg-canvas"
          data-testid="settings-asr-preview-result"
        />
        <div className="rounded-lg border border-line bg-canvas p-3">
          <p className="text-xs leading-5 text-slate-500">{message}</p>
          {fallbackReason ? <FallbackNotice reason={fallbackReason} /> : null}
          <div className="mt-3 rounded-md border border-dashed border-line px-3 py-2 text-xs leading-5 text-slate-500">
            浏览器不支持直接录音时，可以上传 WAV、MP3 或 PCM 文件。
          </div>
        </div>
      </div>
    </section>
  );
}

function SpeechEvalPreviewPanel() {
  const [referenceText, setReferenceText] = useState("请用一句话说明你刚刚学会的知识点。");
  const [recording, setRecording] = useState(false);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("保存口语评测配置后，可录一小段话测试评分。");
  const [result, setResult] = useState<SpeechEvaluateResponse | null>(null);
  const recordingRef = useRef<BrowserPcmRecording | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    return () => {
      stopBrowserPcmRecording(recordingRef.current);
      recordingRef.current = null;
    };
  }, []);

  const evaluateFile = async (file: File) => {
    const reference = referenceText.trim();
    if (!reference) {
      setMessage("请先填写一段参考文本。");
      return;
    }
    if (pending) return;
    if (file.size > 20 * 1024 * 1024) {
      setMessage("评测失败：音频不能超过 20MB");
      return;
    }
    setPending(true);
    setMessage("正在评测口语音频。");
    try {
      const next = await evaluateSpeechAudio({
        file,
        referenceText: reference,
        title: "设置页口语评测试录",
        taskId: "settings-speech-eval-preview",
        persistEvidence: false,
      });
      if (!next.success) {
        setResult(null);
        setMessage(`评测失败：${friendlyServiceError(next.error || "口语评测失败")}`);
        return;
      }
      setResult(next);
      setMessage(next.fallback ? "评测完成：离线替补分数仅供试录参考。" : next.sid ? `评测完成：${next.sid}` : "评测完成。");
    } catch (error) {
      const detail = error instanceof Error ? error.message : "口语评测失败";
      setResult(null);
      setMessage(`评测失败：${friendlyServiceError(detail)}`);
    } finally {
      setPending(false);
    }
  };

  const startRecording = async () => {
    if (pending || recording) return;
    if (!isBrowserPcmRecordingSupported()) {
      fileInputRef.current?.click();
      return;
    }
    try {
      recordingRef.current = await startBrowserPcmRecording();
      setRecording(true);
      setResult(null);
      setMessage("正在录音，完成后会自动评测。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "无法开始录音");
    }
  };

  const stopRecording = async () => {
    const current = recordingRef.current;
    if (!current) return;
    recordingRef.current = null;
    setRecording(false);
    const recorded = await finishBrowserPcmWavRecording(current, "sparkweave-speech-eval-preview.wav");
    if (recorded.durationMs < 800 || !recorded.chunkCount) {
      setMessage("录音时间太短，请再试一次。");
      return;
    }
    await evaluateFile(recorded.file);
  };

  const normalizedScore = formatSpeechEvalScore(result?.normalized_score);
  const dimensions = result?.dimensions ? Object.entries(result.dimensions).slice(0, 3) : [];

  return (
    <section className="rounded-lg border border-line bg-white p-3" data-testid="settings-speech-eval-preview">
      <input
        ref={fileInputRef}
        type="file"
        accept="audio/wav,.wav,.pcm"
        className="hidden"
        onChange={(event) => {
          const file = event.currentTarget.files?.[0];
          if (file) void evaluateFile(file);
          event.currentTarget.value = "";
        }}
      />
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Mic2 size={18} className="text-brand-purple" />
            <h2 className="text-base font-semibold text-ink">口语评测试录</h2>
          </div>
          <p className="mt-1 text-sm leading-6 text-slate-500">按参考文本说一小段话，只验配置，不写入学习记录。</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            tone="secondary"
            disabled={pending || recording}
            onClick={() => fileInputRef.current?.click()}
            data-testid="settings-speech-eval-preview-upload"
          >
            <Upload size={16} />
            上传音频
          </Button>
          <Button
            type="button"
            tone={recording ? "danger" : "secondary"}
            disabled={pending || !referenceText.trim()}
            onClick={() => {
              void (recording ? stopRecording() : startRecording());
            }}
            data-testid="settings-speech-eval-preview-record"
          >
            {pending ? (
              <Loader2 size={16} className="animate-spin" />
            ) : recording ? (
              <Square size={15} />
            ) : (
              <Mic2 size={16} />
            )}
            {recording ? "停止并评测" : "开始录音"}
          </Button>
        </div>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_260px]">
        <TextArea
          value={referenceText}
          onChange={(event) => setReferenceText(event.target.value)}
          maxLength={180}
          className="min-h-20 resize-none"
          data-testid="settings-speech-eval-preview-reference"
        />
        <div className="rounded-lg border border-line bg-canvas p-3">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs leading-5 text-slate-500">{message}</p>
            {result ? <Badge tone={scoreBadgeTone(result.normalized_score)}>{normalizedScore}</Badge> : null}
          </div>
          {result?.fallback ? (
            <FallbackNotice reason={fallbackReasonText(result.fallback_reason, "讯飞口语评测不可用，已使用离线启发式评分。")} />
          ) : null}
          {result ? (
            <div className="mt-3 grid gap-2">
              <p className="text-xs text-slate-500">总分：{formatRawSpeechScore(result.overall_score)}</p>
              {dimensions.length ? (
                <div className="flex flex-wrap gap-1.5">
                  {dimensions.map(([name, value]) => (
                    <Badge key={name} tone="neutral">
                      {speechDimensionLabel(name)} {formatRawSpeechScore(value)}
                    </Badge>
                  ))}
                </div>
              ) : null}
            </div>
          ) : (
            <div className="mt-3 rounded-md border border-dashed border-line px-3 py-2 text-xs leading-5 text-slate-500">
              评测结果会显示在这里。
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function TtsPreviewPanel() {
  const [text, setText] = useState("这是一段 SparkWeave 语音讲解试听。");
  const [audioUrl, setAudioUrl] = useState("");
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("保存语音配置后，可在这里试听当前音色。");
  const [fallbackReason, setFallbackReason] = useState("");
  const objectUrlRef = useRef("");

  useEffect(() => {
    return () => {
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    };
  }, []);

  const runPreview = async () => {
    const content = text.trim();
    if (!content || pending) return;
    setPending(true);
    setMessage("正在生成试听音频。");
    setFallbackReason("");
    try {
      const result = await previewTts(content);
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
      const nextUrl = URL.createObjectURL(result.blob);
      objectUrlRef.current = nextUrl;
      setAudioUrl(nextUrl);
      if (result.fallback) {
        setFallbackReason(fallbackReasonText(result.fallbackReason, "讯飞 TTS 不可用，已使用离线试听音频。"));
        setMessage("试听已生成：离线替补音频。");
      } else {
        setMessage(result.voice ? `试听已生成：${result.voice}` : "试听已生成。");
      }
    } catch (error) {
      const detail = error instanceof Error ? error.message : "语音试听失败";
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = "";
      }
      setFallbackReason("");
      setMessage(`试听失败：${friendlyServiceError(detail)}`);
      setAudioUrl("");
    } finally {
      setPending(false);
    }
  };

  return (
    <section className="rounded-lg border border-line bg-white p-3" data-testid="settings-tts-preview">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Volume2 size={18} className="text-brand-red" />
            <h2 className="text-base font-semibold text-ink">语音试听</h2>
          </div>
          <p className="mt-1 text-sm leading-6 text-slate-500">用当前已保存的讯飞 TTS 配置生成一小段讲解音频。</p>
        </div>
        <Button
          type="button"
          tone="secondary"
          disabled={pending || !text.trim()}
          onClick={() => {
            void runPreview();
          }}
          data-testid="settings-tts-preview-run"
        >
          {pending ? <Loader2 size={16} className="animate-spin" /> : <Volume2 size={16} />}
          生成试听
        </Button>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_260px]">
        <TextArea
          value={text}
          onChange={(event) => setText(event.target.value)}
          maxLength={160}
          className="min-h-20 resize-none"
          data-testid="settings-tts-preview-text"
        />
        <div className="rounded-lg border border-line bg-canvas p-3">
          <p className="text-xs leading-5 text-slate-500">{message}</p>
          {fallbackReason ? <FallbackNotice reason={fallbackReason} /> : null}
          {audioUrl ? (
            <audio
              className="mt-3 w-full"
              src={audioUrl}
              controls
              data-testid="settings-tts-preview-audio"
            />
          ) : (
            <div className="mt-3 flex min-h-10 items-center rounded-md border border-dashed border-line px-3 text-xs text-slate-500">
              暂无试听音频
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function FallbackNotice({ reason }: { reason: string }) {
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-700">
      <Badge tone="warning">离线替补</Badge>
      <span>{reason}</span>
    </div>
  );
}

function fallbackReasonText(reason: string | null | undefined, fallback: string) {
  return friendlyServiceError(reason || fallback);
}

function formatSpeechEvalScore(value?: number | null) {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  return `${Math.round(value * 100)}%`;
}

function formatRawSpeechScore(value?: number | null) {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  return String(Math.round(value));
}

function scoreBadgeTone(value?: number | null): "success" | "warning" | "neutral" {
  if (typeof value !== "number" || Number.isNaN(value)) return "neutral";
  return value >= 0.75 ? "success" : "warning";
}

function speechDimensionLabel(name: string) {
  return (
    {
      accuracy: "准确度",
      accuracy_score: "准确度",
      fluency: "流畅度",
      fluency_score: "流畅度",
      integrity: "完整度",
      integrity_score: "完整度",
      pronunciation: "发音",
      pronunciation_score: "发音",
      standard: "标准度",
      standard_score: "标准度",
    }[name] || name
  );
}
