import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addNotebookRecord,
  addNotebookRecordWithSummary,
  autoMarkText,
  chatGuideSession,
  completeGuideSession,
  createGuideSession,
  createKnowledgeBase,
  createNotebook,
  createQuestionCategory,
  createSparkBot,
  createSparkBotSoul,
  clearMemory,
  clearKnowledgeProgress,
  deleteSparkBotSoul,
  deleteKnowledgeBase,
  deleteGuideSession,
  deleteNotebook,
  deleteNotebookRecord,
  deleteQuestionCategory,
  deleteQuestionEntry,
  deleteSession,
  destroySparkBot,
  editWithCoWriter,
  editWithCoWriterBasic,
  exportCoWriterMarkdown,
  applySettingsCatalog,
  fixGuideHtml,
  getDashboardActivity,
  getCoWriterOperation,
  getCoWriterToolCalls,
  getSettings,
  getSettingsCatalog,
  getGuideHealth,
  getKnowledgeBaseDetail,
  getGuidePages,
  getGuideSession,
  getGuideHtml,
  getAgentConfig,
  getSidebarSettings,
  listAgentConfigs,
  getDefaultKnowledgeBase,
  getKnowledgeHealth,
  getKnowledgeConfig,
  getKnowledgeProgress,
  getMemory,
  getNotebook,
  getNotebookHealth,
  getNotebookStats,
  getQuestionEntry,
  getRuntimeTopology,
  getSetupTourStatus,
  getSystemStatus,
  listCoWriterHistory,
  listDashboardActivities,
  listKnowledgeConfigs,
  listGuideSessions,
  listKnowledgeBases,
  listLinkedFolders,
  listNotebooks,
  listPlugins,
  listQuestionCategories,
  listQuestionEntries,
  listRagProviders,
  listSessions,
  listSparkBotChannelSchemas,
  listSparkBotFiles,
  listSparkBotRecent,
  listSparkBotSouls,
  listSparkBots,
  listThemes,
  getSparkBot,
  getSparkBotSoul,
  getSparkBotHistory,
  setDefaultKnowledgeBase,
  linkKnowledgeFolder,
  lookupQuestionEntry,
  addQuestionEntryToCategory,
  navigateGuideSession,
  readSparkBotFile,
  refreshMemory,
  removeQuestionEntryFromCategory,
  renameQuestionCategory,
  resetUiSettings,
  resetGuideSession,
  retryGuidePage,
  reopenSetupTour,
  startGuideSession,
  stopSparkBot,
  syncKnowledgeConfigs,
  syncKnowledgeFolder,
  testService,
  updateLanguage,
  updateSettingsCatalog,
  updateSidebarDescription,
  updateSidebarNavOrder,
  updateTheme,
  updateUiSettings,
  updateMemory,
  updateKnowledgeConfig,
  updateNotebook,
  updateNotebookRecord,
  updateQuestionEntry,
  upsertQuestionEntry,
  updateSessionTitle,
  updateSparkBot,
  updateSparkBotSoul,
  unlinkKnowledgeFolder,
  uploadKnowledgeFiles,
  writeSparkBotFile,
} from "@/lib/api";
import type { MemoryFile, NotebookRecord, SettingsResponse } from "@/lib/types";

export function useSystemStatus() {
  return useQuery({
    queryKey: ["system-status"],
    queryFn: getSystemStatus,
    refetchInterval: 30_000,
  });
}

export function useRuntimeTopology() {
  return useQuery({
    queryKey: ["runtime-topology"],
    queryFn: getRuntimeTopology,
  });
}

export function useAgentConfigs() {
  return useQuery({
    queryKey: ["agent-configs"],
    queryFn: listAgentConfigs,
  });
}

export function useAgentConfigDetail(agentType: string | null) {
  return useQuery({
    queryKey: ["agent-config", agentType],
    queryFn: () => getAgentConfig(agentType || ""),
    enabled: Boolean(agentType),
  });
}

export function useSettings() {
  return useQuery({
    queryKey: ["settings"],
    queryFn: getSettings,
  });
}

export function useSettingsCatalog() {
  return useQuery({
    queryKey: ["settings-catalog"],
    queryFn: getSettingsCatalog,
  });
}

export function useThemes() {
  return useQuery({
    queryKey: ["settings-themes"],
    queryFn: listThemes,
  });
}

export function useSidebarSettings() {
  return useQuery({
    queryKey: ["settings-sidebar"],
    queryFn: getSidebarSettings,
  });
}

export function useSetupTourStatus() {
  return useQuery({
    queryKey: ["setup-tour-status"],
    queryFn: getSetupTourStatus,
  });
}

export function useReopenSetupTour() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: reopenSetupTour,
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["setup-tour-status"] });
    },
  });
}

export function useSessions() {
  return useQuery({
    queryKey: ["sessions"],
    queryFn: listSessions,
  });
}

export function useSessionMutations() {
  const queryClient = useQueryClient();
  const settle = (sessionId?: string) => {
    void queryClient.invalidateQueries({ queryKey: ["sessions"] });
    if (sessionId) void queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
  };
  return {
    rename: useMutation({
      mutationFn: updateSessionTitle,
      onSettled: (_result, _error, input) => settle(input.sessionId),
    }),
    remove: useMutation({
      mutationFn: deleteSession,
      onSettled: (_result, _error, sessionId) => settle(sessionId),
    }),
  };
}

export function useKnowledgeBases() {
  return useQuery({
    queryKey: ["knowledge-bases"],
    queryFn: listKnowledgeBases,
  });
}

export function useKnowledgeBaseDetail(kbName: string | null) {
  return useQuery({
    queryKey: ["knowledge-base-detail", kbName],
    queryFn: () => getKnowledgeBaseDetail(kbName || ""),
    enabled: Boolean(kbName),
  });
}

export function useKnowledgeHealth() {
  return useQuery({
    queryKey: ["knowledge-health"],
    queryFn: getKnowledgeHealth,
  });
}

export function useDefaultKnowledgeBase() {
  return useQuery({
    queryKey: ["knowledge-default"],
    queryFn: getDefaultKnowledgeBase,
  });
}

export function useRagProviders() {
  return useQuery({
    queryKey: ["rag-providers"],
    queryFn: listRagProviders,
  });
}

export function usePluginsList() {
  return useQuery({
    queryKey: ["plugins-list"],
    queryFn: listPlugins,
  });
}

export function useDashboardActivities(limit = 20) {
  return useQuery({
    queryKey: ["dashboard-activities", limit],
    queryFn: () => listDashboardActivities(limit),
  });
}

export function useDashboardActivity(entryId: string | null) {
  return useQuery({
    queryKey: ["dashboard-activity", entryId],
    queryFn: () => getDashboardActivity(entryId || ""),
    enabled: Boolean(entryId),
  });
}

export function useKnowledgeProgress(kbName: string | null) {
  return useQuery({
    queryKey: ["knowledge-progress", kbName],
    queryFn: () => getKnowledgeProgress(kbName || ""),
    enabled: Boolean(kbName),
    refetchInterval: 2500,
  });
}

export function useKnowledgeConfig(kbName: string | null) {
  return useQuery({
    queryKey: ["knowledge-config", kbName],
    queryFn: () => getKnowledgeConfig(kbName || ""),
    enabled: Boolean(kbName),
  });
}

export function useKnowledgeConfigs() {
  return useQuery({
    queryKey: ["knowledge-configs"],
    queryFn: listKnowledgeConfigs,
  });
}

export function useLinkedFolders(kbName: string | null) {
  return useQuery({
    queryKey: ["linked-folders", kbName],
    queryFn: () => listLinkedFolders(kbName || ""),
    enabled: Boolean(kbName),
  });
}

export function useMemory() {
  return useQuery({
    queryKey: ["memory"],
    queryFn: getMemory,
  });
}

export function useNotebooks() {
  return useQuery({
    queryKey: ["notebooks"],
    queryFn: listNotebooks,
  });
}

export function useNotebookStats() {
  return useQuery({
    queryKey: ["notebook-stats"],
    queryFn: getNotebookStats,
  });
}

export function useNotebookHealth() {
  return useQuery({
    queryKey: ["notebook-health"],
    queryFn: getNotebookHealth,
    refetchInterval: 30_000,
  });
}

export function useNotebookDetail(notebookId: string | null) {
  return useQuery({
    queryKey: ["notebook", notebookId],
    queryFn: () => getNotebook(notebookId || ""),
    enabled: Boolean(notebookId),
  });
}

export function useQuestionEntries() {
  return useQuery({
    queryKey: ["question-entries"],
    queryFn: listQuestionEntries,
  });
}

export function useQuestionEntryDetail(entryId: number | null) {
  return useQuery({
    queryKey: ["question-entry", entryId],
    queryFn: () => getQuestionEntry(entryId || 0),
    enabled: Boolean(entryId),
  });
}

export function useQuestionCategories() {
  return useQuery({
    queryKey: ["question-categories"],
    queryFn: listQuestionCategories,
  });
}

export function useSparkBots() {
  return useQuery({
    queryKey: ["sparkbots"],
    queryFn: listSparkBots,
  });
}

export function useSparkBotRecent(limit = 5) {
  return useQuery({
    queryKey: ["sparkbot-recent", limit],
    queryFn: () => listSparkBotRecent(limit),
  });
}

export function useSparkBotDetail(botId: string | null) {
  return useQuery({
    queryKey: ["sparkbot", botId],
    queryFn: () => getSparkBot(botId || "", true),
    enabled: Boolean(botId),
  });
}

export function useSparkBotChannelSchemas() {
  return useQuery({
    queryKey: ["sparkbot-channel-schemas"],
    queryFn: listSparkBotChannelSchemas,
  });
}

export function useSparkBotSouls() {
  return useQuery({
    queryKey: ["sparkbot-souls"],
    queryFn: listSparkBotSouls,
  });
}

export function useSparkBotSoulDetail(soulId: string | null) {
  return useQuery({
    queryKey: ["sparkbot-soul", soulId],
    queryFn: () => getSparkBotSoul(soulId || ""),
    enabled: Boolean(soulId),
  });
}

export function useSparkBotFiles(botId: string | null) {
  return useQuery({
    queryKey: ["sparkbot-files", botId],
    queryFn: () => listSparkBotFiles(botId || ""),
    enabled: Boolean(botId),
  });
}

export function useSparkBotFile(botId: string | null, filename: string | null) {
  return useQuery({
    queryKey: ["sparkbot-file", botId, filename],
    queryFn: () => readSparkBotFile({ botId: botId || "", filename: filename || "" }),
    enabled: Boolean(botId && filename),
  });
}

export function useSparkBotHistory(botId: string | null) {
  return useQuery({
    queryKey: ["sparkbot-history", botId],
    queryFn: async () => {
      const data = await getSparkBotHistory(botId || "");
      return Array.isArray(data) ? data : data.history ?? data.messages ?? [];
    },
    enabled: Boolean(botId),
  });
}

export function useGuideHealth() {
  return useQuery({
    queryKey: ["guide-health"],
    queryFn: getGuideHealth,
    refetchInterval: 30_000,
  });
}

export function useGuideSessions() {
  return useQuery({
    queryKey: ["guide-sessions"],
    queryFn: listGuideSessions,
  });
}

export function useGuideSessionDetail(sessionId: string | null) {
  return useQuery({
    queryKey: ["guide-session", sessionId],
    queryFn: () => getGuideSession(sessionId || ""),
    enabled: Boolean(sessionId),
  });
}

export function useGuideHtml(sessionId: string | null) {
  return useQuery({
    queryKey: ["guide-html", sessionId],
    queryFn: () => getGuideHtml(sessionId || ""),
    enabled: Boolean(sessionId),
    retry: false,
  });
}

export function useGuidePages(sessionId: string | null) {
  return useQuery({
    queryKey: ["guide-pages", sessionId],
    queryFn: () => getGuidePages(sessionId || ""),
    enabled: Boolean(sessionId),
    retry: false,
  });
}

export function useCoWriterHistory() {
  return useQuery({
    queryKey: ["co-writer-history"],
    queryFn: listCoWriterHistory,
  });
}

export function useCoWriterOperation(operationId: string | null) {
  return useQuery({
    queryKey: ["co-writer-operation", operationId],
    queryFn: () => getCoWriterOperation(operationId || ""),
    enabled: Boolean(operationId),
  });
}

export function useCoWriterToolCalls(operationId: string | null) {
  return useQuery({
    queryKey: ["co-writer-tool-calls", operationId],
    queryFn: () => getCoWriterToolCalls(operationId || ""),
    enabled: Boolean(operationId),
    retry: false,
  });
}

export function useServiceTest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: testService,
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["system-status"] });
    },
  });
}

export function useSettingsMutations() {
  const queryClient = useQueryClient();
  const settle = () => {
    void queryClient.invalidateQueries({ queryKey: ["settings"] });
    void queryClient.invalidateQueries({ queryKey: ["settings-catalog"] });
    void queryClient.invalidateQueries({ queryKey: ["system-status"] });
  };
  return {
    saveCatalog: useMutation({
      mutationFn: updateSettingsCatalog,
      onSettled: settle,
    }),
    applyCatalog: useMutation({
      mutationFn: applySettingsCatalog,
      onSettled: settle,
    }),
    updateUi: useMutation({
      mutationFn: (input: Partial<SettingsResponse["ui"]>) => updateUiSettings(input),
      onSettled: settle,
    }),
    updateTheme: useMutation({
      mutationFn: updateTheme,
      onSettled: settle,
    }),
    updateLanguage: useMutation({
      mutationFn: updateLanguage,
      onSettled: settle,
    }),
    updateSidebarDescription: useMutation({
      mutationFn: updateSidebarDescription,
      onSettled: () => {
        settle();
        void queryClient.invalidateQueries({ queryKey: ["settings-sidebar"] });
      },
    }),
    updateSidebarNavOrder: useMutation({
      mutationFn: updateSidebarNavOrder,
      onSettled: () => {
        settle();
        void queryClient.invalidateQueries({ queryKey: ["settings-sidebar"] });
      },
    }),
    resetUi: useMutation({
      mutationFn: resetUiSettings,
      onSettled: () => {
        settle();
        void queryClient.invalidateQueries({ queryKey: ["settings-sidebar"] });
      },
    }),
  };
}

export function useKnowledgeMutations() {
  const queryClient = useQueryClient();
  const settle = () => {
    void queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] });
    void queryClient.invalidateQueries({ queryKey: ["knowledge-default"] });
    void queryClient.invalidateQueries({ queryKey: ["knowledge-health"] });
  };
  return {
    create: useMutation({ mutationFn: createKnowledgeBase, onSettled: settle }),
    upload: useMutation({ mutationFn: uploadKnowledgeFiles, onSettled: settle }),
    setDefault: useMutation({ mutationFn: setDefaultKnowledgeBase, onSettled: settle }),
    remove: useMutation({ mutationFn: deleteKnowledgeBase, onSettled: settle }),
    updateConfig: useMutation({
      mutationFn: updateKnowledgeConfig,
      onSettled: (_result, _error, input) => {
        settle();
        void queryClient.invalidateQueries({ queryKey: ["knowledge-config", input?.kbName] });
      },
    }),
    clearProgress: useMutation({
      mutationFn: clearKnowledgeProgress,
      onSettled: (_result, _error, kbName) => {
        void queryClient.invalidateQueries({ queryKey: ["knowledge-progress", kbName] });
      },
    }),
    syncConfigs: useMutation({
      mutationFn: syncKnowledgeConfigs,
      onSettled: () => {
        settle();
        void queryClient.invalidateQueries({ queryKey: ["knowledge-config"] });
      },
    }),
    linkFolder: useMutation({
      mutationFn: linkKnowledgeFolder,
      onSettled: (_result, _error, input) => {
        settle();
        void queryClient.invalidateQueries({ queryKey: ["linked-folders", input?.kbName] });
      },
    }),
    unlinkFolder: useMutation({
      mutationFn: unlinkKnowledgeFolder,
      onSettled: (_result, _error, input) => {
        settle();
        void queryClient.invalidateQueries({ queryKey: ["linked-folders", input?.kbName] });
      },
    }),
    syncFolder: useMutation({
      mutationFn: syncKnowledgeFolder,
      onSettled: (_result, _error, input) => {
        settle();
        void queryClient.invalidateQueries({ queryKey: ["linked-folders", input?.kbName] });
      },
    }),
  };
}

export function useMemoryMutations() {
  const queryClient = useQueryClient();
  const settle = () => {
    void queryClient.invalidateQueries({ queryKey: ["memory"] });
  };
  return {
    save: useMutation({
      mutationFn: updateMemory,
      onSettled: settle,
    }),
    refresh: useMutation({
      mutationFn: refreshMemory,
      onSettled: settle,
    }),
    clear: useMutation({
      mutationFn: (file?: MemoryFile | null) => clearMemory(file),
      onSettled: settle,
    }),
  };
}

export function useNotebookMutations() {
  const queryClient = useQueryClient();
  const settle = (notebookId?: string) => {
    void queryClient.invalidateQueries({ queryKey: ["notebooks"] });
    void queryClient.invalidateQueries({ queryKey: ["notebook-stats"] });
    if (notebookId) void queryClient.invalidateQueries({ queryKey: ["notebook", notebookId] });
  };
  return {
    create: useMutation({
      mutationFn: createNotebook,
      onSuccess: (result) => settle(result.notebook?.id),
      onSettled: () => settle(),
    }),
    remove: useMutation({
      mutationFn: deleteNotebook,
      onSettled: () => settle(),
    }),
    update: useMutation({
      mutationFn: updateNotebook,
      onSettled: (_result, _error, input) => settle(input.notebookId),
    }),
    addRecord: useMutation({
      mutationFn: addNotebookRecord,
      onSuccess: (_result, input) => input.notebook_ids.forEach((id) => settle(id)),
      onSettled: () => settle(),
    }),
    addRecordWithSummary: useMutation({
      mutationFn: addNotebookRecordWithSummary,
      onSuccess: (_result, input) => input.notebook_ids.forEach((id) => settle(id)),
      onSettled: () => settle(),
    }),
    updateRecord: useMutation({
      mutationFn: updateNotebookRecord,
      onSettled: (_result, _error, input) => settle(input.notebookId),
    }),
    deleteRecord: useMutation({
      mutationFn: deleteNotebookRecord,
      onSettled: (_result, _error, input) => settle(input.notebookId),
    }),
  };
}

export function useQuestionNotebookMutations() {
  const queryClient = useQueryClient();
  return {
    createCategory: useMutation({
      mutationFn: createQuestionCategory,
      onSettled: () => {
        void queryClient.invalidateQueries({ queryKey: ["question-categories"] });
      },
    }),
    renameCategory: useMutation({
      mutationFn: renameQuestionCategory,
      onSettled: () => {
        void queryClient.invalidateQueries({ queryKey: ["question-categories"] });
        void queryClient.invalidateQueries({ queryKey: ["question-entries"] });
      },
    }),
    deleteCategory: useMutation({
      mutationFn: deleteQuestionCategory,
      onSettled: () => {
        void queryClient.invalidateQueries({ queryKey: ["question-categories"] });
        void queryClient.invalidateQueries({ queryKey: ["question-entries"] });
      },
    }),
    updateEntry: useMutation({
      mutationFn: updateQuestionEntry,
      onSettled: () => {
        void queryClient.invalidateQueries({ queryKey: ["question-entries"] });
      },
    }),
    lookupEntry: useMutation({
      mutationFn: lookupQuestionEntry,
    }),
    upsertEntry: useMutation({
      mutationFn: upsertQuestionEntry,
      onSettled: () => {
        void queryClient.invalidateQueries({ queryKey: ["question-entries"] });
        void queryClient.invalidateQueries({ queryKey: ["question-categories"] });
      },
    }),
    deleteEntry: useMutation({
      mutationFn: deleteQuestionEntry,
      onSettled: () => {
        void queryClient.invalidateQueries({ queryKey: ["question-entries"] });
        void queryClient.invalidateQueries({ queryKey: ["question-categories"] });
      },
    }),
    addEntryToCategory: useMutation({
      mutationFn: addQuestionEntryToCategory,
      onSettled: () => {
        void queryClient.invalidateQueries({ queryKey: ["question-entries"] });
        void queryClient.invalidateQueries({ queryKey: ["question-categories"] });
      },
    }),
    removeEntryFromCategory: useMutation({
      mutationFn: removeQuestionEntryFromCategory,
      onSettled: () => {
        void queryClient.invalidateQueries({ queryKey: ["question-entries"] });
        void queryClient.invalidateQueries({ queryKey: ["question-categories"] });
      },
    }),
  };
}

export function useSparkBotMutations() {
  const queryClient = useQueryClient();
  const settle = (botId?: string) => {
    void queryClient.invalidateQueries({ queryKey: ["sparkbots"] });
    void queryClient.invalidateQueries({ queryKey: ["sparkbot-recent"] });
    if (botId) {
      void queryClient.invalidateQueries({ queryKey: ["sparkbot", botId] });
      void queryClient.invalidateQueries({ queryKey: ["sparkbot-files", botId] });
      void queryClient.invalidateQueries({ queryKey: ["sparkbot-history", botId] });
    }
  };
  return {
    create: useMutation({ mutationFn: createSparkBot, onSettled: (_result, _error, input) => settle(input.bot_id) }),
    update: useMutation({ mutationFn: updateSparkBot, onSettled: (_result, _error, input) => settle(input.botId) }),
    stop: useMutation({ mutationFn: stopSparkBot, onSettled: (_result, _error, botId) => settle(botId) }),
    destroy: useMutation({ mutationFn: destroySparkBot, onSettled: (_result, _error, botId) => settle(botId) }),
    writeFile: useMutation({
      mutationFn: writeSparkBotFile,
      onSettled: (_result, _error, input) => {
        settle(input.botId);
        void queryClient.invalidateQueries({ queryKey: ["sparkbot-file", input.botId, input.filename] });
      },
    }),
    createSoul: useMutation({
      mutationFn: createSparkBotSoul,
      onSettled: (_result, _error, input) => {
        void queryClient.invalidateQueries({ queryKey: ["sparkbot-souls"] });
        void queryClient.invalidateQueries({ queryKey: ["sparkbot-soul", input.id] });
      },
    }),
    updateSoul: useMutation({
      mutationFn: updateSparkBotSoul,
      onSettled: (_result, _error, input) => {
        void queryClient.invalidateQueries({ queryKey: ["sparkbot-souls"] });
        void queryClient.invalidateQueries({ queryKey: ["sparkbot-soul", input.soulId] });
      },
    }),
    deleteSoul: useMutation({
      mutationFn: deleteSparkBotSoul,
      onSettled: (_result, _error, soulId) => {
        void queryClient.invalidateQueries({ queryKey: ["sparkbot-souls"] });
        void queryClient.invalidateQueries({ queryKey: ["sparkbot-soul", soulId] });
      },
    }),
  };
}

export function useGuideMutations() {
  const queryClient = useQueryClient();
  const settle = (sessionId?: string) => {
    void queryClient.invalidateQueries({ queryKey: ["guide-sessions"] });
    if (sessionId) {
      void queryClient.invalidateQueries({ queryKey: ["guide-session", sessionId] });
      void queryClient.invalidateQueries({ queryKey: ["guide-html", sessionId] });
      void queryClient.invalidateQueries({ queryKey: ["guide-pages", sessionId] });
    }
  };
  return {
    create: useMutation({
      mutationFn: createGuideSession,
      onSettled: () => {
        void queryClient.invalidateQueries({ queryKey: ["guide-sessions"] });
      },
    }),
    start: useMutation({
      mutationFn: startGuideSession,
      onSettled: (_result, _error, sessionId) => settle(sessionId),
    }),
    navigate: useMutation({
      mutationFn: navigateGuideSession,
      onSettled: (_result, _error, input) => settle(input.sessionId),
    }),
    complete: useMutation({
      mutationFn: completeGuideSession,
      onSettled: (_result, _error, sessionId) => settle(sessionId),
    }),
    chat: useMutation({
      mutationFn: chatGuideSession,
      onSettled: (_result, _error, input) => settle(input.sessionId),
    }),
    fixHtml: useMutation({
      mutationFn: fixGuideHtml,
      onSettled: (_result, _error, input) => settle(input.sessionId),
    }),
    retryPage: useMutation({
      mutationFn: retryGuidePage,
      onSettled: (_result, _error, input) => settle(input.sessionId),
    }),
    reset: useMutation({
      mutationFn: resetGuideSession,
      onSettled: (_result, _error, sessionId) => settle(sessionId),
    }),
    remove: useMutation({
      mutationFn: deleteGuideSession,
      onSettled: (_result, _error, sessionId) => settle(sessionId),
    }),
  };
}

export function useCoWriterMutations() {
  const queryClient = useQueryClient();
  return {
    edit: useMutation({
      mutationFn: editWithCoWriter,
      onSettled: () => {
        void queryClient.invalidateQueries({ queryKey: ["co-writer-history"] });
      },
    }),
    quickEdit: useMutation({
      mutationFn: editWithCoWriterBasic,
      onSettled: () => {
        void queryClient.invalidateQueries({ queryKey: ["co-writer-history"] });
      },
    }),
    automark: useMutation({
      mutationFn: autoMarkText,
      onSettled: () => {
        void queryClient.invalidateQueries({ queryKey: ["co-writer-history"] });
      },
    }),
    saveRecord: useMutation({
      mutationFn: (input: {
        notebook_ids: string[];
        title: string;
        user_query: string;
        output: string;
        summary?: string;
        metadata?: Record<string, unknown>;
      }) =>
        addNotebookRecord({
          ...input,
          record_type: "co_writer" satisfies NotebookRecord["record_type"],
        }),
      onSettled: () => {
        void queryClient.invalidateQueries({ queryKey: ["notebooks"] });
        void queryClient.invalidateQueries({ queryKey: ["notebook-stats"] });
      },
    }),
    exportMarkdown: useMutation({
      mutationFn: exportCoWriterMarkdown,
    }),
  };
}
