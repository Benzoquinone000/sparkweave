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
  type KnowledgeWsMessage,
  type KnowledgeWsStatus,
} from "./progressFormat";

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
            status: "processing",
            stage: "processing",
            message: "任务已创建，等待索引进度...",
            percent: 0,
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
    const handleEvent = (event: MessageEvent<string>, label: "log" | "complete" | "failed" | "message") => {
      const payload = parseTaskPayload(event.data);
      pushTaskLog(formatTaskEvent(label, event.data));
      if (label === "complete" || label === "failed") {
        const message =
          payload?.detail || payload?.line || (label === "complete" ? "索引任务已完成" : "索引任务失败");
        const terminalProgress: KnowledgeProgress = {
          status: label === "complete" ? "completed" : "error",
          stage: label === "complete" ? "completed" : "error",
          message: String(message),
          percent: label === "complete" ? 100 : 0,
          task_id: String(payload?.task_id || taskId),
        };
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
    source.addEventListener("complete", (event) => handleEvent(event as MessageEvent<string>, "complete"));
    source.addEventListener("failed", (event) => handleEvent(event as MessageEvent<string>, "failed"));
    source.onmessage = (event) => handleEvent(event, "message");
    source.onerror = () => {
      pushTaskLog("任务流暂时不可用，继续使用资料库级别进度轮询。");
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
          if (terminalTaskRef.current === taskId && !isTerminalProgress(payload.data)) return;
          setWsProgress(payload.data);
          if (isTerminalProgress(payload.data)) terminalTaskRef.current = taskId;
          pushTaskLog(formatWsProgress(payload.data));
          if (isTerminalProgress(payload.data)) {
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
