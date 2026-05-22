import { CheckCircle2, Loader2, Mic2, Square } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FieldShell, TextArea } from "@/components/ui/Field";
import { evaluateSpeechAudio } from "@/lib/api";
import {
  finishBrowserPcmWavRecording,
  isBrowserPcmRecordingSupported,
  startBrowserPcmRecording,
  stopBrowserPcmRecording,
  type BrowserPcmRecording,
} from "@/lib/speechRecording";
import type { GuideV2LearningFeedback, GuideV2Task, SpeechEvaluateResponse } from "@/lib/types";
import { DemoEvidenceShortcut } from "./GuideDemoCards";
import { LearningImpactSummary } from "./GuideLearningLoopSummary";
import { taskScoreOptions } from "./guideFormOptions";

export function GuideTaskCompletionPanel({
  currentTask,
  currentDemoStep,
  highlightedSectionId,
  score,
  reflection,
  learningFeedback,
  busy,
  activeSessionId,
  completing,
  onScoreChange,
  onReflectionChange,
  onCompleteTask,
}: {
  currentTask: GuideV2Task;
  currentDemoStep: Record<string, unknown> | null;
  highlightedSectionId: string | null;
  score: string;
  reflection: string;
  learningFeedback: GuideV2LearningFeedback | null;
  busy: boolean;
  activeSessionId: string | null;
  completing: boolean;
  onScoreChange: (value: string) => void;
  onReflectionChange: (value: string) => void;
  onCompleteTask: () => void;
}) {
  const successCriteria = currentTask.success_criteria?.length ? currentTask.success_criteria : ["完成任务并写下一句话总结"];

  return (
    <>
      <div
        id="guide-complete-task-section"
        className={`grid gap-4 transition-all duration-500 lg:grid-cols-[minmax(0,1fr)_280px] ${
          highlightedSectionId === "guide-complete-task-section" ? "rounded-lg ring-2 ring-brand-purple-300 ring-offset-2 ring-offset-canvas" : ""
        }`}
      >
        <div className="rounded-lg border border-line bg-canvas p-4">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-ink">完成标准</h3>
            <Badge tone="neutral">{successCriteria.length} 条</Badge>
          </div>
          <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-600">
            {successCriteria.slice(0, 3).map((item) => (
              <li key={item} className="flex gap-2">
                <CheckCircle2 size={16} className="mt-1 shrink-0 text-brand-purple" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-lg border border-line bg-white p-4">
          <DemoEvidenceShortcut
            step={currentDemoStep}
            onApply={(nextScore, nextReflection) => {
              onScoreChange(nextScore);
              onReflectionChange(nextReflection);
            }}
          />
          <FieldShell label="你现在感觉怎么样">
            <div className="grid gap-2">
              {taskScoreOptions.map((option) => {
                const active = score === option.value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    className={`min-h-12 rounded-md border px-3 text-left transition ${
                      active
                        ? "border-ink bg-ink text-white shadow-sm"
                        : "border-line bg-white text-slate-700 hover:border-brand-purple-300 hover:bg-tint-lavender"
                    }`}
                    onClick={() => onScoreChange(option.value)}
                  >
                    <span className="block text-sm font-semibold">{option.label}</span>
                    <span className="mt-0.5 block text-xs text-slate-500">{option.helper}</span>
                  </button>
                );
              })}
            </div>
          </FieldShell>
          <FieldShell label="一句话反思">
            <TextArea
              value={reflection}
              onChange={(event) => onReflectionChange(event.target.value)}
              className="min-h-20"
              placeholder="我已经理解了……还不确定的是……"
            />
          </FieldShell>
          <OralPracticeProbe
            key={currentTask.task_id}
            currentTask={currentTask}
            courseId={activeSessionId || ""}
            disabled={busy || completing}
            reflection={reflection}
            onScoreChange={onScoreChange}
            onReflectionChange={onReflectionChange}
          />
          <Button
            tone="primary"
            className="mt-3 w-full"
            data-testid="guide-submit-task-feedback"
            onClick={onCompleteTask}
            disabled={busy || !activeSessionId}
          >
            {completing ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
            完成并获得反馈
          </Button>
        </div>
      </div>
      {learningFeedback ? <LearningImpactSummary feedback={learningFeedback} /> : null}
    </>
  );
}

function OralPracticeProbe({
  currentTask,
  courseId,
  disabled,
  reflection,
  onScoreChange,
  onReflectionChange,
}: {
  currentTask: GuideV2Task;
  courseId: string;
  disabled: boolean;
  reflection: string;
  onScoreChange: (value: string) => void;
  onReflectionChange: (value: string) => void;
}) {
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<SpeechEvaluateResponse | null>(null);
  const recordingRef = useRef<BrowserPcmRecording | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const referenceText = useMemo(() => buildSpeechEvalReference(currentTask), [currentTask]);

  useEffect(() => {
    return () => {
      stopBrowserPcmRecording(recordingRef.current);
      recordingRef.current = null;
    };
  }, []);

  const applyResult = (next: SpeechEvaluateResponse) => {
    const normalizedScore = clampScore(next.normalized_score);
    if (normalizedScore !== null && !next.fallback) onScoreChange(String(normalizedScore));
    onReflectionChange(mergeSpeechReflection(reflection, buildSpeechReflectionLine(next)));
    setResult(next);
  };

  const evaluateFile = async (file: File) => {
    if (busy) return;
    if (file.size > 20 * 1024 * 1024) {
      setError("音频不能超过 20MB");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const next = await evaluateSpeechAudio({
        file,
        referenceText,
        courseId,
        nodeId: currentTask.node_id,
        taskId: currentTask.task_id,
        title: currentTask.title,
      });
      if (!next.success) {
        setError(next.error || "口语评测失败");
        return;
      }
      applyResult(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "口语评测失败");
    } finally {
      setBusy(false);
    }
  };

  const startRecording = async () => {
    if (disabled || busy || recording) return;
    if (!isBrowserPcmRecordingSupported()) {
      fileInputRef.current?.click();
      return;
    }
    setError("");
    try {
      recordingRef.current = await startBrowserPcmRecording();
      setRecording(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "无法开始录音");
    }
  };

  const stopRecording = async () => {
    const current = recordingRef.current;
    if (!current) return;
    recordingRef.current = null;
    setRecording(false);
    const recorded = await finishBrowserPcmWavRecording(current, "sparkweave-oral-practice.wav");
    if (recorded.durationMs < 800 || !recorded.chunkCount) {
      setError("录音时间太短");
      return;
    }
    await evaluateFile(recorded.file);
  };

  const scoreLabel = result ? formatSpeechScore(result) : "";
  const dimensionLabel = result ? formatSpeechDimensions(result.dimensions) : "";
  const normalizedResultScore = clampScore(result?.normalized_score);
  const resultTone: "success" | "warning" =
    result?.fallback || normalizedResultScore === null || normalizedResultScore < 0.75 ? "warning" : "success";

  return (
    <div className="mt-3 rounded-lg border border-line bg-surface px-3 py-3">
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
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-xs font-semibold leading-5 text-charcoal">口语说明</p>
            <Badge tone={result?.fallback ? "warning" : "brand"}>{result?.fallback ? "离线替补" : "讯飞"}</Badge>
          </div>
          <p className="mt-0.5 text-xs leading-5 text-steel">
            {result?.fallback ? "离线分数只作参考，不会覆盖你的自评。" : "说一下这一步怎么完成，会写入本次学习记录。"}
          </p>
        </div>
        <button
          type="button"
          onClick={() => void (recording ? stopRecording() : startRecording())}
          disabled={busy || (disabled && !recording)}
          aria-label={recording ? "停止口语评测" : "开始口语评测"}
          title={recording ? "停止口语评测" : "开始口语评测"}
          className={`dt-interactive inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md border disabled:cursor-not-allowed disabled:opacity-60 ${
            recording
              ? "border-red-200 bg-red-50 text-brand-red hover:bg-red-100"
              : "border-line-strong bg-white text-charcoal hover:border-ink hover:text-ink"
          }`}
        >
          {recording ? <Square size={14} /> : <Mic2 size={16} className={busy ? "animate-pulse" : ""} />}
        </button>
      </div>
      {result ? (
        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs leading-5 text-steel">
          <Badge tone={resultTone}>{scoreLabel}</Badge>
          {dimensionLabel ? <span>{dimensionLabel}</span> : null}
          {result.fallback_reason ? <span className="text-amber-700">原因：{result.fallback_reason}</span> : null}
        </div>
      ) : null}
      {error ? <p className="mt-2 rounded-md bg-red-50 px-2.5 py-1.5 text-xs leading-5 text-brand-red">{error}</p> : null}
    </div>
  );
}

function buildSpeechEvalReference(task: GuideV2Task) {
  const criteria = task.success_criteria?.slice(0, 3).join("；") || "";
  return [task.title, task.instruction, criteria].filter(Boolean).join("\n");
}

function buildSpeechReflectionLine(result: SpeechEvaluateResponse) {
  const score = formatSpeechScore(result);
  const dimensions = formatSpeechDimensions(result.dimensions);
  const label = result.fallback ? "口语评测（离线替补参考）" : "口语评测";
  return `${label} ${score}${dimensions ? `，${dimensions}` : ""}。`;
}

function mergeSpeechReflection(current: string, speechLine: string) {
  const trimmed = current.trim();
  if (!trimmed) return speechLine;
  if (trimmed.includes("口语评测")) {
    return trimmed.replace(/口语评测[^\n。]*。?/u, speechLine);
  }
  return `${trimmed}\n${speechLine}`;
}

function formatSpeechScore(result: SpeechEvaluateResponse) {
  if (typeof result.overall_score === "number") return `${Math.round(result.overall_score)} 分`;
  const normalized = clampScore(result.normalized_score);
  if (normalized !== null) return `${Math.round(normalized * 100)} 分`;
  return "已记录";
}

function formatSpeechDimensions(dimensions?: Record<string, number>) {
  if (!dimensions) return "";
  const labels: Record<string, string> = {
    accuracy: "准确度",
    fluency: "流畅度",
    integrity: "完整度",
    phone: "发音",
    tone: "声调",
  };
  return Object.entries(dimensions)
    .filter(([key]) => key !== "total" && key !== "score")
    .slice(0, 2)
    .map(([key, value]) => `${labels[key] || key} ${Math.round(value)}`)
    .join(" · ");
}

function clampScore(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) return null;
  return Math.max(0, Math.min(1, value));
}
