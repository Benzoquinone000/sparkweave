import { useCallback, useEffect, useMemo, useState } from "react";

import type { NotebookRecordInput } from "@/lib/api";
import { buildNotebookAsset } from "@/lib/notebookAssets";
import type { ChatMessage, NotebookSummary } from "@/lib/types";

type AddNotebookRecordMutation = {
  isPending: boolean;
  mutateAsync: (input: NotebookRecordInput) => Promise<unknown>;
};

export function useChatNotebookSave({
  messages,
  sessionId,
  turnId,
  language,
  knowledgeBases,
  notebooks,
  addRecord,
}: {
  messages: ChatMessage[];
  sessionId: string | null;
  turnId: string | null;
  language: "zh" | "en";
  knowledgeBases: string[];
  notebooks: NotebookSummary[];
  addRecord: AddNotebookRecordMutation;
}) {
  const [saveMessage, setSaveMessage] = useState<ChatMessage | null>(null);
  const [saveNotice, setSaveNotice] = useState<{ title: string; notebookName: string } | null>(null);
  const saveAsset = useMemo(
    () =>
      saveMessage
        ? buildNotebookAsset({
            message: saveMessage,
            messages,
            sessionId,
            turnId,
            language,
            knowledgeBase: knowledgeBases[0] ?? null,
          })
        : null,
    [knowledgeBases, language, messages, saveMessage, sessionId, turnId],
  );

  useEffect(() => {
    if (!saveNotice) return;
    const timer = window.setTimeout(() => setSaveNotice(null), 3000);
    return () => window.clearTimeout(timer);
  }, [saveNotice]);

  const closeSaveModal = useCallback(() => setSaveMessage(null), []);

  const saveToNotebook = useCallback(
    async ({ notebookId, title, summary }: { notebookId: string; title: string; summary: string }) => {
      if (!saveAsset) return;
      await addRecord.mutateAsync({
        notebook_ids: [notebookId],
        record_type: saveAsset.recordType,
        title,
        summary,
        user_query: saveAsset.userQuery,
        output: saveAsset.output,
        metadata: {
          ...saveAsset.metadata,
          edited_title: title,
          edited_summary: summary,
        },
        kb_name: knowledgeBases[0] ?? null,
      });
      const notebookName = notebooks.find((item) => item.id === notebookId)?.name || notebookId;
      setSaveNotice({ title, notebookName });
      setSaveMessage(null);
    },
    [addRecord, knowledgeBases, notebooks, saveAsset],
  );

  return {
    saveMessage,
    saveAsset,
    saveNotice,
    savePending: addRecord.isPending,
    setSaveMessage,
    closeSaveModal,
    saveToNotebook,
  };
}
