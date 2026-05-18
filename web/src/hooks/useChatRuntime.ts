import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { defaultConfigForCapability } from "@/lib/capabilities";
import { unifiedRuntimeSocketUrl } from "@/lib/api";
import { getCapabilityFromEvent, getResultEventText } from "@/lib/chatMessages";
import type { CapabilityId, ChatAttachment, ChatMessage, NotebookReference, SessionDetail, StreamEvent } from "@/lib/types";

type RuntimeStatus = "idle" | "connecting" | "streaming" | "error";

interface SendOptions {
  content: string;
  capability: CapabilityId;
  tools: string[];
  knowledgeBases: string[];
  attachments: ChatAttachment[];
  language: "zh" | "en";
  config?: Record<string, unknown>;
  notebookReferences?: NotebookReference[];
  historyReferences?: string[];
}

const COMPLETED_STAGES = new Set(["responding", "response", "answering", "final", "done"]);
function messageId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function normalizedStage(event: StreamEvent) {
  return String(event.stage ?? "").toLowerCase();
}

function isRespondingStageEnd(event: StreamEvent) {
  return event.type === "stage_end" && COMPLETED_STAGES.has(normalizedStage(event));
}

function isAssistantDoneEvent(event: StreamEvent) {
  return event.type === "done" || event.type === "result" || isRespondingStageEnd(event);
}

function shouldCloseSocket(event: StreamEvent) {
  return event.type === "done" || event.type === "error" || isRespondingStageEnd(event);
}

export function useChatRuntime() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<RuntimeStatus>("idle");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [turnId, setTurnId] = useState<string | null>(null);
  const [lastEvent, setLastEvent] = useState<StreamEvent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const assistantIdRef = useRef<string | null>(null);

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  useEffect(() => () => disconnect(), [disconnect]);

  const appendAssistantEvent = useCallback((event: StreamEvent) => {
    const assistantId = assistantIdRef.current;
    if (!assistantId) return;
    setMessages((current) =>
      current.map((message) => {
        if (message.id !== assistantId) return message;
        const nextEvents = [...(message.events ?? []), event];
        const nextCapability = getCapabilityFromEvent(event);
        const content =
          event.type === "content"
            ? `${message.content}${event.content}`
            : event.type === "result"
              ? message.content || getResultEventText(event)
            : event.type === "error"
              ? message.content || event.content
              : message.content;
        return {
          ...message,
          capability: nextCapability ?? message.capability,
          content,
          events: nextEvents,
          status: event.type === "error" ? "error" : isAssistantDoneEvent(event) ? "done" : "streaming",
        };
      }),
    );
  }, []);

  const handleEvent = useCallback(
    (event: StreamEvent) => {
      setLastEvent(event);
      if (event.session_id) setSessionId(event.session_id);
      if (event.turn_id) setTurnId(event.turn_id);
      appendAssistantEvent(event);
      if (event.type === "error") {
        setError(event.content || "Runtime error");
        setStatus("error");
      }
      if (isAssistantDoneEvent(event)) {
        setStatus("idle");
      }
      if (shouldCloseSocket(event)) {
        wsRef.current?.close();
        wsRef.current = null;
      }
    },
    [appendAssistantEvent],
  );

  const send = useCallback(
    (options: SendOptions) => {
      const content = options.content.trim();
      if (!content || status === "connecting" || status === "streaming") return;

      disconnect();
      setError(null);
      setStatus("connecting");

      const userMessage: ChatMessage = {
        id: messageId("user"),
        role: "user",
        content,
        capability: options.capability,
        attachments: options.attachments,
        createdAt: Date.now(),
      };
      const assistantMessage: ChatMessage = {
        id: messageId("assistant"),
        role: "assistant",
        content: "",
        capability: options.capability,
        status: "streaming",
        events: [],
        createdAt: Date.now() + 1,
      };
      assistantIdRef.current = assistantMessage.id;
      setMessages((current) => [...current, userMessage, assistantMessage]);

      const socket = new WebSocket(unifiedRuntimeSocketUrl());
      wsRef.current = socket;

      socket.onopen = () => {
        setStatus("streaming");
        const config = {
          ...defaultConfigForCapability(options.capability, content),
          ...(options.config ?? {}),
        };
        if (options.capability === "deep_question" && !String(config.topic ?? "").trim()) {
          config.topic = content.slice(0, 120);
        }
        socket.send(
          JSON.stringify({
            type: "start_turn",
            content,
            capability: options.capability,
            tools: options.tools,
            knowledge_bases: options.knowledgeBases,
            notebook_references: options.notebookReferences ?? [],
            history_references: options.historyReferences ?? [],
            attachments: options.attachments,
            language: options.language,
            session_id: sessionId,
            config,
          }),
        );
      };

      socket.onmessage = (message) => {
        try {
          handleEvent(JSON.parse(message.data) as StreamEvent);
        } catch {
          setError("收到无法解析的流式事件");
        }
      };

      socket.onerror = () => {
        setError("无法连接 SparkWeave 后端");
        setStatus("error");
      };

      socket.onclose = () => {
        wsRef.current = null;
        setStatus((current) => (current === "streaming" || current === "connecting" ? "idle" : current));
      };
    },
    [disconnect, handleEvent, sessionId, status],
  );

  const cancel = useCallback(() => {
    if (turnId && wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "cancel_turn", turn_id: turnId }));
    }
    disconnect();
    setStatus("idle");
  }, [disconnect, turnId]);

  const hydrateSession = useCallback(
    (session: SessionDetail) => {
      disconnect();
      setError(null);
      setStatus("idle");
      setLastEvent(null);
      setSessionId(session.session_id || session.id);
      setTurnId(session.active_turn_id ?? null);
      assistantIdRef.current = null;
      setMessages(
        (session.messages ?? []).map((message) => ({
          id: String(message.id),
          role: message.role,
          content: message.content,
          capability: message.capability as CapabilityId | undefined,
          events: message.events ?? [],
          attachments: message.attachments ?? [],
          status: message.role === "assistant" ? "done" : undefined,
          createdAt:
            typeof message.created_at === "number" && message.created_at < 10_000_000_000
              ? message.created_at * 1000
              : Number(message.created_at || Date.now()),
        })),
      );
    },
    [disconnect],
  );

  const newSession = useCallback(() => {
    disconnect();
    setMessages([]);
    setStatus("idle");
    setSessionId(null);
    setTurnId(null);
    setLastEvent(null);
    setError(null);
    assistantIdRef.current = null;
  }, [disconnect]);

  const runtime = useMemo(
    () => ({ messages, status, sessionId, turnId, lastEvent, error, send, cancel, hydrateSession, newSession }),
    [cancel, error, hydrateSession, lastEvent, messages, newSession, send, sessionId, status, turnId],
  );

  return runtime;
}
