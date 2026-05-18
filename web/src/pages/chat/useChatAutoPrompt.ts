import { useEffect, useRef } from "react";

import type { CapabilityId } from "@/lib/types";
import { cleanText, isCapabilityId, knowledgeBasesFromSearchParams } from "./chatPageUtils";

type SendQuickAction = (
  content: string,
  quickCapability?: CapabilityId,
  quickConfig?: Record<string, unknown>,
  options?: { knowledgeBases?: string[] },
) => void;

export function useChatAutoPrompt({
  initialCapability,
  messageCount,
  runtimeStatus,
  resetRuntimeSession,
  sendQuickAction,
}: {
  initialCapability: CapabilityId;
  messageCount: number;
  runtimeStatus: "idle" | "connecting" | "streaming" | "error";
  resetRuntimeSession: () => void;
  sendQuickAction: SendQuickAction;
}) {
  const autoPromptKeyRef = useRef<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    if (params.get("new") !== "1") return;
    const prompt = cleanText(params.get("prompt"));
    if (!prompt || runtimeStatus !== "idle") return;
    const key = `${window.location.pathname}${window.location.search}`;
    if (autoPromptKeyRef.current === key) return;
    if (messageCount) {
      const timer = window.setTimeout(() => resetRuntimeSession(), 0);
      return () => window.clearTimeout(timer);
    }
    const requestedCapability = params.get("capability");
    const nextCapability = isCapabilityId(requestedCapability) ? requestedCapability : initialCapability;
    const requestedKnowledgeBases = knowledgeBasesFromSearchParams(params);
    const timer = window.setTimeout(() => {
      autoPromptKeyRef.current = key;
      sendQuickAction(prompt, nextCapability, undefined, {
        knowledgeBases: requestedKnowledgeBases.length ? requestedKnowledgeBases : undefined,
      });
    }, 0);
    return () => window.clearTimeout(timer);
  }, [initialCapability, messageCount, resetRuntimeSession, runtimeStatus, sendQuickAction]);
}
