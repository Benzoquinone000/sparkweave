import { useCallback, useEffect, useState } from "react";

import { getSession } from "@/lib/api";
import { defaultToolsForCapability, getCapability } from "@/lib/capabilities";
import type { CapabilityId, NotebookReference, SessionDetail, SessionSummary } from "@/lib/types";
import { isCapabilityId } from "./chatPageUtils";

type SessionMutations = {
  rename: {
    isPending: boolean;
    mutateAsync: (input: { sessionId: string; title: string }) => Promise<unknown>;
  };
  remove: {
    isPending: boolean;
    mutateAsync: (sessionId: string) => Promise<unknown>;
  };
};

export function useChatSessionActions({
  routeSessionId,
  runtimeSessionId,
  hydrateSession,
  resetRuntimeSession,
  sessionMutations,
  setCapability,
  setTools,
  setCapabilityConfig,
  setKnowledgeBases,
  setLanguage,
  setContextOpen,
  setHistoryReferences,
  setNotebookReferences,
}: {
  routeSessionId: string | null;
  runtimeSessionId: string | null;
  hydrateSession: (detail: SessionDetail) => void;
  resetRuntimeSession: () => void;
  sessionMutations: SessionMutations;
  setCapability: (value: CapabilityId) => void;
  setTools: (value: string[]) => void;
  setCapabilityConfig: (value: Record<string, unknown>) => void;
  setKnowledgeBases: (value: string[]) => void;
  setLanguage: (value: "zh" | "en") => void;
  setContextOpen: (value: boolean) => void;
  setHistoryReferences: (value: string[]) => void;
  setNotebookReferences: (value: NotebookReference[]) => void;
}) {
  const [loadingSessionId, setLoadingSessionId] = useState<string | null>(null);

  const newSession = useCallback(() => {
    resetRuntimeSession();
    setHistoryReferences([]);
    setNotebookReferences([]);
  }, [resetRuntimeSession, setHistoryReferences, setNotebookReferences]);

  const handleCapabilityChange = useCallback(
    (next: CapabilityId) => {
      setCapability(next);
      setTools(defaultToolsForCapability(next));
      setCapabilityConfig({ ...getCapability(next).config });
    },
    [setCapability, setCapabilityConfig, setTools],
  );

  const applySessionDetail = useCallback(
    (detail: SessionDetail) => {
      hydrateSession(detail);
      const pref = detail.preferences;
      if (isCapabilityId(pref?.capability)) handleCapabilityChange(pref.capability);
      if (pref?.tools) setTools(pref.tools);
      if (pref?.knowledge_bases) setKnowledgeBases(pref.knowledge_bases);
      if (pref?.language === "zh" || pref?.language === "en") setLanguage(pref.language);
      setContextOpen(false);
    },
    [handleCapabilityChange, hydrateSession, setContextOpen, setKnowledgeBases, setLanguage, setTools],
  );

  const loadSessionById = useCallback(
    async (targetSessionId: string) => {
      setLoadingSessionId(targetSessionId);
      try {
        const detail = await getSession(targetSessionId);
        applySessionDetail(detail);
      } finally {
        setLoadingSessionId(null);
      }
    },
    [applySessionDetail],
  );

  const loadSession = useCallback(
    async (session: SessionSummary) => {
      await loadSessionById(session.session_id);
    },
    [loadSessionById],
  );

  const renameSession = useCallback(
    async (sessionId: string, title: string) => {
      await sessionMutations.rename.mutateAsync({ sessionId, title });
    },
    [sessionMutations.rename],
  );

  const deleteChatSession = useCallback(
    async (sessionId: string) => {
      await sessionMutations.remove.mutateAsync(sessionId);
      if (runtimeSessionId === sessionId) resetRuntimeSession();
    },
    [resetRuntimeSession, runtimeSessionId, sessionMutations.remove],
  );

  useEffect(() => {
    if (typeof window === "undefined") return;

    const consumePendingNewChat = () => {
      if (window.sessionStorage.getItem("sparkweave:new-chat-request")) {
        window.sessionStorage.removeItem("sparkweave:new-chat-request");
        newSession();
      }
    };
    const handleNewChat = () => newSession();

    consumePendingNewChat();
    window.addEventListener("sparkweave:new-chat", handleNewChat);
    return () => window.removeEventListener("sparkweave:new-chat", handleNewChat);
  }, [newSession]);

  useEffect(() => {
    if (!routeSessionId || routeSessionId === runtimeSessionId) return;
    let cancelled = false;
    void getSession(routeSessionId)
      .then((detail) => {
        if (!cancelled) applySessionDetail(detail);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [applySessionDetail, routeSessionId, runtimeSessionId]);

  return {
    loadingSessionId,
    newSession,
    handleCapabilityChange,
    loadSession,
    renameSession,
    deleteChatSession,
    sessionActionPending: sessionMutations.rename.isPending || sessionMutations.remove.isPending,
  };
}
