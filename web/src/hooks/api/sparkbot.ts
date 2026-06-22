import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createSparkBot,
  createSparkBotCronJob,
  createSparkBotSoul,
  deleteSparkBotCronJob,
  deleteSparkBotSoul,
  destroySparkBot,
  getSparkBot,
  getSparkBotHistory,
  getSparkBotSoul,
  listSparkBotChannelSchemas,
  listSparkBotCronJobs,
  listSparkBotFiles,
  listSparkBotRecent,
  listSparkBotSkills,
  listSparkBotSouls,
  listSparkBots,
  readSparkBotFile,
  readSparkBotSkill,
  runSparkBotCronJob,
  stopSparkBot,
  updateSparkBot,
  updateSparkBotCronJob,
  updateSparkBotSoul,
  uploadSparkBotSkill,
  writeSparkBotFile,
  writeSparkBotSkill,
} from "@/lib/api/sparkbot";

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

export function useSparkBotDetail(botId: string | null, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ["sparkbot", botId],
    queryFn: () => getSparkBot(botId || "", true),
    enabled: Boolean(botId && (options?.enabled ?? true)),
  });
}

export function useSparkBotCronJobs(botId: string | null, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ["sparkbot-cron", botId],
    queryFn: () => listSparkBotCronJobs(botId || ""),
    enabled: Boolean(botId && (options?.enabled ?? true)),
    refetchInterval: 30_000,
  });
}

export function useSparkBotChannelSchemas(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ["sparkbot-channel-schemas"],
    queryFn: listSparkBotChannelSchemas,
    enabled: options?.enabled ?? true,
  });
}

export function useSparkBotSouls(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ["sparkbot-souls"],
    queryFn: listSparkBotSouls,
    enabled: options?.enabled ?? true,
  });
}

export function useSparkBotSoulDetail(soulId: string | null) {
  return useQuery({
    queryKey: ["sparkbot-soul", soulId],
    queryFn: () => getSparkBotSoul(soulId || ""),
    enabled: Boolean(soulId),
  });
}

export function useSparkBotFiles(botId: string | null, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ["sparkbot-files", botId],
    queryFn: () => listSparkBotFiles(botId || ""),
    enabled: Boolean(botId && (options?.enabled ?? true)),
  });
}

export function useSparkBotFile(botId: string | null, filename: string | null, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ["sparkbot-file", botId, filename],
    queryFn: () => readSparkBotFile({ botId: botId || "", filename: filename || "" }),
    enabled: Boolean(botId && filename && (options?.enabled ?? true)),
  });
}

export function useSparkBotSkills(botId: string | null, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ["sparkbot-skills", botId],
    queryFn: () => listSparkBotSkills(botId || ""),
    enabled: Boolean(botId && (options?.enabled ?? true)),
  });
}

export function useSparkBotSkill(botId: string | null, skillName: string | null, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ["sparkbot-skill", botId, skillName],
    queryFn: () => readSparkBotSkill({ botId: botId || "", skillName: skillName || "" }),
    enabled: Boolean(botId && skillName && (options?.enabled ?? true)),
  });
}

export function useSparkBotHistory(botId: string | null, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ["sparkbot-history", botId],
    queryFn: async () => {
      const data = await getSparkBotHistory(botId || "");
      return Array.isArray(data) ? data : data.history ?? data.messages ?? [];
    },
    enabled: Boolean(botId && (options?.enabled ?? true)),
  });
}

export function useSparkBotMutations() {
  const queryClient = useQueryClient();
  const settle = (botId?: string) => {
    void queryClient.invalidateQueries({ queryKey: ["sparkbots"] });
    void queryClient.invalidateQueries({ queryKey: ["sparkbot-recent"] });
    if (botId) {
      void queryClient.invalidateQueries({ queryKey: ["sparkbot", botId] });
      void queryClient.invalidateQueries({ queryKey: ["sparkbot-cron", botId] });
      void queryClient.invalidateQueries({ queryKey: ["sparkbot-files", botId] });
      void queryClient.invalidateQueries({ queryKey: ["sparkbot-skills", botId] });
      void queryClient.invalidateQueries({ queryKey: ["sparkbot-history", botId] });
    }
  };
  return {
    create: useMutation({ mutationFn: createSparkBot, onSettled: (_result, _error, input) => settle(input.bot_id) }),
    update: useMutation({ mutationFn: updateSparkBot, onSettled: (_result, _error, input) => settle(input.botId) }),
    stop: useMutation({ mutationFn: stopSparkBot, onSettled: (_result, _error, botId) => settle(botId) }),
    destroy: useMutation({ mutationFn: destroySparkBot, onSettled: (_result, _error, botId) => settle(botId) }),
    createCronJob: useMutation({ mutationFn: createSparkBotCronJob, onSettled: (_result, _error, input) => settle(input.botId) }),
    updateCronJob: useMutation({ mutationFn: updateSparkBotCronJob, onSettled: (_result, _error, input) => settle(input.botId) }),
    deleteCronJob: useMutation({ mutationFn: deleteSparkBotCronJob, onSettled: (_result, _error, input) => settle(input.botId) }),
    runCronJob: useMutation({ mutationFn: runSparkBotCronJob, onSettled: (_result, _error, input) => settle(input.botId) }),
    writeFile: useMutation({
      mutationFn: writeSparkBotFile,
      onSettled: (_result, _error, input) => {
        settle(input.botId);
        void queryClient.invalidateQueries({ queryKey: ["sparkbot-file", input.botId, input.filename] });
      },
    }),
    writeSkill: useMutation({
      mutationFn: writeSparkBotSkill,
      onSettled: (_result, _error, input) => {
        settle(input.botId);
        void queryClient.invalidateQueries({ queryKey: ["sparkbot-skill", input.botId, input.skillName] });
      },
    }),
    uploadSkill: useMutation({
      mutationFn: uploadSparkBotSkill,
      onSettled: (_result, _error, input) => {
        settle(input.botId);
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
