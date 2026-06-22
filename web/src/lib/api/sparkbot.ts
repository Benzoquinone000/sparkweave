import { fetchJson, wsUrl } from "@/lib/http";
import type {
  SparkBotCronJob,
  SparkBotCronResponse,
  SparkBotFile,
  SparkBotRecentItem,
  SparkBotSchemas,
  SparkBotSkill,
  SparkBotSoul,
  SparkBotSummary,
} from "@/lib/types";

const SPARKBOT_API_ROOT = "/api/v1/sparkbot";

function sparkBotApiPath(path = "") {
  return `${SPARKBOT_API_ROOT}${path}`;
}

function jsonBody(payload: unknown): RequestInit {
  return {
    method: "POST",
    body: JSON.stringify(payload),
  };
}

export function sparkBotSocketUrl(botId: string) {
  return wsUrl(sparkBotApiPath(`/${encodeURIComponent(botId)}/ws`));
}

export async function listSparkBots() {
  const data = await fetchJson<SparkBotSummary[] | { bots?: SparkBotSummary[] }>(sparkBotApiPath());
  return Array.isArray(data) ? data : data.bots ?? [];
}

export async function listSparkBotRecent(limit = 5) {
  return fetchJson<SparkBotRecentItem[]>(sparkBotApiPath(`/recent?limit=${limit}`));
}

export function getSparkBot(botId: string, includeSecrets = false) {
  const query = includeSecrets ? "?include_secrets=true" : "";
  return fetchJson<SparkBotSummary>(sparkBotApiPath(`/${encodeURIComponent(botId)}${query}`));
}

export function listSparkBotCronJobs(botId: string) {
  return fetchJson<SparkBotCronResponse>(sparkBotApiPath(`/${encodeURIComponent(botId)}/cron?include_disabled=true`));
}

export function createSparkBotCronJob(input: {
  botId: string;
  payload: {
    name?: string;
    message: string;
    kind: "every" | "cron" | "at";
    every_seconds?: number;
    cron_expr?: string;
    at?: string;
    tz?: string;
    deliver?: boolean;
    channel?: string | null;
    to?: string | null;
  };
}) {
  return fetchJson<SparkBotCronJob>(sparkBotApiPath(`/${encodeURIComponent(input.botId)}/cron`), jsonBody(input.payload));
}

export function updateSparkBotCronJob(input: { botId: string; jobId: string; enabled: boolean }) {
  return fetchJson<SparkBotCronJob>(
    sparkBotApiPath(`/${encodeURIComponent(input.botId)}/cron/${encodeURIComponent(input.jobId)}`),
    {
      method: "PATCH",
      body: JSON.stringify({ enabled: input.enabled }),
    },
  );
}

export function deleteSparkBotCronJob(input: { botId: string; jobId: string }) {
  return fetchJson<{ job_id: string; deleted: boolean }>(
    sparkBotApiPath(`/${encodeURIComponent(input.botId)}/cron/${encodeURIComponent(input.jobId)}`),
    { method: "DELETE" },
  );
}

export function runSparkBotCronJob(input: { botId: string; jobId: string }) {
  return fetchJson<{ job_id: string; ran: boolean }>(
    sparkBotApiPath(`/${encodeURIComponent(input.botId)}/cron/${encodeURIComponent(input.jobId)}/run`),
    { method: "POST" },
  );
}

export function listSparkBotChannelSchemas() {
  return fetchJson<SparkBotSchemas>(sparkBotApiPath("/channels/schema"));
}

export function listSparkBotSouls() {
  return fetchJson<SparkBotSoul[]>(sparkBotApiPath("/souls"));
}

export function getSparkBotSoul(soulId: string) {
  return fetchJson<SparkBotSoul>(sparkBotApiPath(`/souls/${encodeURIComponent(soulId)}`));
}

export function createSparkBotSoul(input: SparkBotSoul) {
  return fetchJson<SparkBotSoul>(sparkBotApiPath("/souls"), jsonBody(input));
}

export function updateSparkBotSoul(input: { soulId: string; payload: Partial<Pick<SparkBotSoul, "name" | "content">> }) {
  return fetchJson<SparkBotSoul>(sparkBotApiPath(`/souls/${encodeURIComponent(input.soulId)}`), {
    method: "PUT",
    body: JSON.stringify(input.payload),
  });
}

export function deleteSparkBotSoul(soulId: string) {
  return fetchJson<{ id: string; deleted?: boolean }>(sparkBotApiPath(`/souls/${encodeURIComponent(soulId)}`), {
    method: "DELETE",
  });
}

export function createSparkBot(input: {
  bot_id: string;
  name?: string;
  description?: string;
  persona?: string;
  model?: string;
  auto_start?: boolean;
}) {
  return fetchJson<SparkBotSummary>(sparkBotApiPath(), jsonBody(input));
}

export function updateSparkBot(input: {
  botId: string;
  payload: Partial<Pick<SparkBotSummary, "name" | "description" | "persona" | "model" | "auto_start">> & {
    channels?: Record<string, unknown>;
    tools?: Record<string, unknown>;
    agent?: Record<string, unknown>;
    heartbeat?: Record<string, unknown>;
  };
}) {
  return fetchJson<SparkBotSummary>(sparkBotApiPath(`/${encodeURIComponent(input.botId)}`), {
    method: "PATCH",
    body: JSON.stringify(input.payload),
  });
}

export function stopSparkBot(botId: string) {
  return fetchJson<{ bot_id: string; stopped: boolean }>(sparkBotApiPath(`/${encodeURIComponent(botId)}`), {
    method: "DELETE",
  });
}

export function destroySparkBot(botId: string) {
  return fetchJson<{ bot_id: string; destroyed: boolean }>(sparkBotApiPath(`/${encodeURIComponent(botId)}/destroy`), {
    method: "DELETE",
  });
}

export async function listSparkBotFiles(botId: string) {
  const data = await fetchJson<Record<string, string> | { files?: SparkBotFile[] } | SparkBotFile[]>(
    sparkBotApiPath(`/${encodeURIComponent(botId)}/files`),
  );
  if (Array.isArray(data)) return data;
  if ("files" in data && Array.isArray(data.files)) return data.files;
  return Object.entries(data).map(([filename, content]) => ({ filename, content: String(content ?? "") }));
}

export function readSparkBotFile(input: { botId: string; filename: string }) {
  return fetchJson<SparkBotFile>(
    sparkBotApiPath(`/${encodeURIComponent(input.botId)}/files/${encodeURIComponent(input.filename)}`),
  );
}

export function writeSparkBotFile(input: { botId: string; filename: string; content: string }) {
  return fetchJson<{ filename: string; saved: boolean }>(
    sparkBotApiPath(`/${encodeURIComponent(input.botId)}/files/${encodeURIComponent(input.filename)}`),
    {
      method: "PUT",
      body: JSON.stringify({ content: input.content }),
    },
  );
}

export async function listSparkBotSkills(botId: string) {
  const data = await fetchJson<{ skills?: SparkBotSkill[] } | SparkBotSkill[]>(
    sparkBotApiPath(`/${encodeURIComponent(botId)}/skills`),
  );
  return Array.isArray(data) ? data : data.skills ?? [];
}

export function readSparkBotSkill(input: { botId: string; skillName: string }) {
  return fetchJson<SparkBotSkill>(
    sparkBotApiPath(`/${encodeURIComponent(input.botId)}/skills/${encodeURIComponent(input.skillName)}`),
  );
}

export function writeSparkBotSkill(input: { botId: string; skillName: string; content: string }) {
  return fetchJson<SparkBotSkill>(
    sparkBotApiPath(`/${encodeURIComponent(input.botId)}/skills/${encodeURIComponent(input.skillName)}`),
    {
      method: "PUT",
      body: JSON.stringify({ content: input.content }),
    },
  );
}

export function uploadSparkBotSkill(input: { botId: string; file: File; skillName?: string }) {
  const form = new FormData();
  form.append("file", input.file);
  if (input.skillName?.trim()) form.append("skill_name", input.skillName.trim());
  return fetchJson<SparkBotSkill>(sparkBotApiPath(`/${encodeURIComponent(input.botId)}/skills/upload`), {
    method: "POST",
    body: form,
  });
}

export function getSparkBotHistory(botId: string) {
  return fetchJson<
    Array<Record<string, unknown>> | { history?: Array<Record<string, unknown>>; messages?: Array<Record<string, unknown>> }
  >(sparkBotApiPath(`/${encodeURIComponent(botId)}/history?limit=50`));
}
