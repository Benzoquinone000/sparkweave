import { useCallback, useEffect, useRef, useState } from "react";

import { knowledgeProgressSocketUrl, openKnowledgeTaskStream } from "@/lib/api";
import type { KnowledgeProgress } from "@/lib/types";

import {
  formatKnowledgeWsMessage,
  formatKnowledgeWsText,
  formatTaskEvent,
  formatWsProgress,
  isTerminalProgress,
  parseTaskPayload,
  progressPercent,
  type KnowledgeWsMessage,
  type KnowledgeWsStatus,
} from "./progressFormat";

type TaskStreamLabel = "log" | "status" | "complete" | "failed" | "message";

export function useKnowledgeTaskProgress({
  activeKb,
  onTerminalProgress,
}: {
  activeKb: string;
  onTerminalProgress: () => void;
}) {
  const [taskId, setTaskId] = useState<string | null>(null);
  const [taskKbName, setTaskKbName] = useState("");
  const [taskLogs, setTaskLogs] = useState<string[]>([]);
  const [taskProgress, setTaskProgress] = useState<KnowledgeProgress | null>(null);
  const [wsProgress, setWsProgress] = useState<KnowledgeProgress | null>(null);
  const [wsStatus, setWsStatus] = useState<KnowledgeWsStatus>("idle");
  const terminalTaskRef = useRef<string | null>(null);

  const pushTaskLog = useCallback((line: string) => {
    setTaskLogs((current) => [...current.filter((item) => item !== line), line].slice(-80));
  }, []);

  const beginTask = useCallback((nextTaskId: string | null, kbName: string) => {
    setTaskId(nextTaskId);
    setTaskKbName(nextTaskId ? kbName : "");
    terminalTaskRef.current = null;
    setTaskLogs([]);
    setTaskProgress(
      nextTaskId
        ? {
            status: "queued",
            stage: "queued",
            message: "任务已创建，正在连接实时进度...",
            percent: 1,
            current: 0,
            total: 0,
            task_id: nextTaskId,
          }
        : null,
    );
    setWsProgress(null);
    setWsStatus(nextTaskId ? "connecting" : "idle");
  }, []);

  const resetTask = useCallback((logs: string[] = []) => {
    setTaskId(null);
    setTaskKbName("");
    terminalTaskRef.current = null;
    setTaskProgress(null);
    setWsProgress(null);
    setWsStatus("idle");
    setTaskLogs(logs.slice(0, 80));
  }, []);

  useEffect(() => {
    if (!taskId) return;
    const source = openKnowledgeTaskStream(taskId);
    const handleEvent = (event: MessageEvent<string>, label: TaskStreamLabel) => {
      const payload = parseTaskPayload(event.data);
      pushTaskLog(formatTaskEvent(label, event.data));
      const nextProgress = taskProgressFromEvent(label, payload, taskId);
      if (nextProgress) {
        setTaskProgress((current) => mergeTaskProgress(current, nextProgress));
      }
      if (label === "complete" || label === "failed") {
        const message =
          payload?.detail || payload?.line || (label === "complete" ? "资料处理已完成" : "资料处理失败");
        const terminalProgress = normalizeTaskProgress({
          status: label === "complete" ? "completed" : "error",
          stage: label === "complete" ? "completed" : "error",
          message: String(message),
          percent: label === "complete" ? 100 : 0,
          task_id: String(payload?.task_id || taskId),
        });
        terminalTaskRef.current = taskId;
        setTaskProgress(terminalProgress);
        setWsProgress(terminalProgress);
        setWsStatus(label === "complete" ? "closed" : "error");
        onTerminalProgress();
        source.close();
      }
    };

    window.setTimeout(() => pushTaskLog(`已连接任务流 ${taskId}`), 0);
    source.addEventListener("log", (event) => handleEvent(event as MessageEvent<string>, "log"));
    source.addEventListener("status", (event) => handleEvent(event as MessageEvent<string>, "status"));
    source.addEventListener("complete", (event) => handleEvent(event as MessageEvent<string>, "complete"));
    source.addEventListener("failed", (event) => handleEvent(event as MessageEvent<string>, "failed"));
    source.onmessage = (event) => handleEvent(event, "message");
    source.onerror = () => {
      pushTaskLog("任务流暂时不可用，继续使用资料库级别进度轮询。");
      setTaskProgress((current) =>
        mergeTaskProgress(current, {
          status: "processing",
          stage: "processing",
          message: "实时任务流暂时不可用，正在继续读取资料库进度...",
          task_id: taskId,
        }),
      );
      source.close();
    };
    return () => source.close();
  }, [onTerminalProgress, pushTaskLog, taskId]);

  useEffect(() => {
    const kbName = taskKbName || activeKb;
    if (!taskId || !kbName || typeof WebSocket === "undefined") return;
    const socket = new WebSocket(knowledgeProgressSocketUrl({ kbName, taskId }));

    socket.onopen = () => {
      if (terminalTaskRef.current === taskId) return;
      setWsStatus("live");
      pushTaskLog(`已连接资料库进度通道 ${kbName}`);
    };
    socket.onmessage = (message) => {
      try {
        const payload = JSON.parse(String(message.data)) as KnowledgeWsMessage;
        if (payload.type === "progress" && payload.data) {
          const nextProgress = normalizeTaskProgress(payload.data);
          if (terminalTaskRef.current === taskId && !isTerminalProgress(nextProgress)) return;
          setWsProgress(nextProgress);
          if (isTerminalProgress(nextProgress)) terminalTaskRef.current = taskId;
          pushTaskLog(formatWsProgress(nextProgress));
          if (isTerminalProgress(nextProgress)) {
            onTerminalProgress();
            socket.close();
          }
          return;
        }
        if (payload.type === "error") {
          setWsStatus("error");
          pushTaskLog(`进度异常：${payload.message || "进度通道异常"}`);
          return;
        }
        pushTaskLog(formatKnowledgeWsMessage(payload));
      } catch {
        pushTaskLog(formatKnowledgeWsText(String(message.data || "")));
      }
    };
    socket.onerror = () => {
      setWsStatus("error");
      pushTaskLog("实时进度暂时不可用，继续自动刷新。");
    };
    socket.onclose = () => {
      setWsStatus((current) => (current === "error" ? "error" : "closed"));
    };
    return () => socket.close();
  }, [activeKb, onTerminalProgress, pushTaskLog, taskId, taskKbName]);

  return {
    taskId,
    taskLogs,
    taskProgress,
    wsProgress,
    wsStatus,
    beginTask,
    pushTaskLog,
    resetTask,
    setTaskLogs,
  };
}

function taskProgressFromEvent(
  label: TaskStreamLabel,
  payload: ReturnType<typeof parseTaskPayload>,
  taskId: string,
): KnowledgeProgress | null {
  if (!payload) return null;
  const embeddedProgress = payload.progress;
  if (isRecord(embeddedProgress)) {
    return normalizeTaskProgress({
      ...(embeddedProgress as KnowledgeProgress),
      task_id: String(embeddedProgress.task_id || payload.task_id || taskId),
      status: String(payload.status || embeddedProgress.status || embeddedProgress.stage || label),
    });
  }

  const message = String(payload.detail || payload.line || "").trim();
  const rawStatus = String(payload.status || "").trim().toLowerCase();
  if (!message && !rawStatus) return null;

  const stage = stageFromTaskEvent(label, rawStatus, message);
  return normalizeTaskProgress({
    status: stage,
    stage,
    message,
    percent: percentFromTaskEvent(stage, message),
    task_id: String(payload.task_id || taskId),
  });
}

function normalizeTaskProgress(progress: KnowledgeProgress): KnowledgeProgress {
  const percent = progressPercent(progress);
  return {
    ...progress,
    ...(typeof percent === "number" ? { percent } : {}),
  };
}

function mergeTaskProgress(current: KnowledgeProgress | null, next: KnowledgeProgress): KnowledgeProgress {
  if (current && isTerminalProgress(current) && !isTerminalProgress(next)) return current;
  const currentPercent = progressPercent(current);
  const nextPercent = progressPercent(next);
  const merged: KnowledgeProgress = {
    ...(current ?? {}),
    ...next,
  };
  if (typeof nextPercent === "number") {
    const shouldKeepCurrent =
      typeof currentPercent === "number" &&
      nextPercent < currentPercent &&
      !isTerminalProgress(next) &&
      ["queued", "running", "processing"].includes(String(next.stage || next.status || "").toLowerCase());
    merged.percent = shouldKeepCurrent ? currentPercent : nextPercent;
  } else if (typeof currentPercent === "number") {
    merged.percent = currentPercent;
  }
  return normalizeTaskProgress(merged);
}

function stageFromTaskEvent(label: TaskStreamLabel, status: string, message: string) {
  if (label === "complete" || status === "completed") return "completed";
  if (label === "failed" || status === "error" || status === "failed") return "error";
  if (status === "queued") return "queued";
  if (status === "running") return "running";

  const lower = message.toLowerCase();
  if (lower.includes("queued")) return "queued";
  if (lower.includes("background knowledge-base worker started")) return "running";
  if (lower.includes("embedding") || lower.includes("indexing") || lower.includes("milvus")) return "indexing";
  if (lower.includes("staged") || lower.includes("processing") || lower.includes("parsing") || lower.includes("loaded")) {
    return "processing";
  }
  if (lower.includes("finalizing") || lower.includes("metadata")) return "processing";
  return "processing";
}

function percentFromTaskEvent(stage: string, message: string) {
  const lower = message.toLowerCase();
  if (stage === "completed") return 100;
  if (stage === "error") return 0;
  if (stage === "queued") return 1;
  if (stage === "running") return 5;
  if (lower.includes("saved") || lower.includes("queued")) return 8;
  if (lower.includes("staged")) return 20;
  if (lower.includes("parsing") || lower.includes("loaded")) return 35;
  if (lower.includes("embedding")) return 55;
  if (lower.includes("indexing") || lower.includes("milvus")) return 65;
  if (lower.includes("indexed") || lower.includes("processed")) return 85;
  if (lower.includes("finalizing") || lower.includes("metadata")) return 92;
  return 10;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}
