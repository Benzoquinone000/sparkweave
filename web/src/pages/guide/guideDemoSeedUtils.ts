import { demoSeedScalar } from "@/lib/guideDisplay";
import type { GuideV2Task } from "@/lib/types";
import { asRecord, readString } from "./guideDataUtils";
import { type GuideActionResourceType, normalizeResourceType } from "./guideResourceUtils";

export function normalizeDemoSeedTaskChain(demoSeed: Record<string, unknown> | null, tasks: GuideV2Task[]): Record<string, unknown>[] {
  if (!demoSeed) return [];

  const chain = Array.isArray(demoSeed.task_chain) ? demoSeed.task_chain : [];
  const promptByTask = normalizeDemoSeedPromptMap(demoSeed.resource_prompts, tasks);
  const fallbackFeedback = normalizeDemoSeedFeedback(demoSeed.sample_reflection, demoSeed.sample_score);

  return chain
    .map<Record<string, unknown> | null>((item, index) => {
      const record = asRecord(item);
      const rawTaskId = record ? readString(record, "task_id") : demoSeedScalar(item);
      const rawTitle = record ? readString(record, "title") : "";
      const task =
        tasks.find((candidate) => candidate.task_id === rawTaskId) ??
        tasks.find((candidate) => candidate.title === rawTitle) ??
        null;
      const taskId = rawTaskId || task?.task_id || "";
      const promptEntry = promptByTask.get(taskId) ?? promptByTask.get(rawTitle) ?? (task?.title ? promptByTask.get(task.title) : undefined);
      const prompt = (record ? readString(record, "prompt") : "") || readStringFromRecord(promptEntry, "prompt");
      const resourceType = inferDemoSeedResourceType(
        (record ? readString(record, "resource_type") || readString(record, "type") : "") ||
          readStringFromRecord(promptEntry, "resource_type") ||
          readStringFromRecord(promptEntry, "type") ||
          task?.type,
        prompt,
      );

      if (!taskId && !rawTitle && !prompt) return null;
      const sampleScore = record && Object.prototype.hasOwnProperty.call(record, "sample_score") ? record.sample_score : fallbackFeedback.score;

      return {
        ...(record ?? {}),
        task_id: taskId,
        title: rawTitle || task?.title || `演示任务 ${index + 1}`,
        stage: (record ? readString(record, "stage") : "") || `演示步骤 ${index + 1}`,
        show: (record ? readString(record, "show") : "") || task?.instruction || "使用稳定提示词生成当前任务素材。",
        resource_type: resourceType,
        prompt,
        sample_score: sampleScore,
        sample_reflection: (record ? readString(record, "sample_reflection") : "") || fallbackFeedback.reflection,
      };
    })
    .filter((item): item is Record<string, unknown> => item !== null);
}

function normalizeDemoSeedPromptMap(value: unknown, tasks: GuideV2Task[]) {
  const map = new globalThis.Map<string, Record<string, unknown>>();
  const save = (key: string, entry: Record<string, unknown>) => {
    if (!key.trim()) return;
    map.set(key.trim(), entry);
  };

  if (Array.isArray(value)) {
    for (const item of value) {
      const record = asRecord(item);
      if (!record) continue;
      const taskId = readString(record, "task_id") || readString(record, "target_task_id");
      const title = readString(record, "title");
      const task =
        tasks.find((candidate) => candidate.task_id === taskId) ??
        tasks.find((candidate) => candidate.title === title) ??
        null;
      const prompt = readString(record, "prompt");
      const resourceType = inferDemoSeedResourceType(readString(record, "resource_type") || readString(record, "type") || task?.type, prompt);
      const entry = {
        ...record,
        task_id: taskId || task?.task_id || "",
        title: title || task?.title || "",
        prompt,
        resource_type: resourceType,
        type: resourceType,
      };
      save(taskId, entry);
      save(title, entry);
      if (task) {
        save(task.task_id, entry);
        save(task.title, entry);
      }
    }
    return map;
  }

  const record = asRecord(value);
  if (!record) return map;
  for (const [key, rawEntry] of Object.entries(record)) {
    const entryRecord = asRecord(rawEntry);
    const prompt = typeof rawEntry === "string" ? rawEntry : entryRecord ? readString(entryRecord, "prompt") : "";
    const task = tasks.find((candidate) => candidate.task_id === key || candidate.title === key) ?? null;
    const resourceType = inferDemoSeedResourceType(
      (entryRecord ? readString(entryRecord, "resource_type") || readString(entryRecord, "type") : "") || task?.type,
      prompt,
    );
    const entry = {
      ...(entryRecord ?? {}),
      task_id: task?.task_id || key,
      title: task?.title || key,
      prompt,
      resource_type: resourceType,
      type: resourceType,
    };
    save(key, entry);
    if (task) {
      save(task.task_id, entry);
      save(task.title, entry);
    }
  }
  return map;
}

function normalizeDemoSeedFeedback(reflectionSource: unknown, scoreSource: unknown) {
  const record = asRecord(reflectionSource);
  const reflection = typeof reflectionSource === "string" ? reflectionSource : record ? readString(record, "reflection") : "";
  const score = Number(record?.score ?? scoreSource);
  return {
    reflection,
    score: Number.isFinite(score) ? Math.max(0, Math.min(score, 1)) : 0.72,
  };
}

function inferDemoSeedResourceType(type: unknown, prompt = ""): GuideActionResourceType {
  const text = `${String(type || "")} ${prompt}`.toLowerCase();
  if (text.includes("external_video") || text.includes("public video") || text.includes("公开视频") || text.includes("精选视频")) {
    return "external_video";
  }
  if (text.includes("quiz") || text.includes("exercise") || text.includes("练习") || text.includes("题")) {
    return "quiz";
  }
  if (text.includes("audio") || text.includes("speech") || text.includes("tts") || text.includes("语音") || text.includes("音频")) {
    return "audio";
  }
  if (text.includes("video") || text.includes("manim") || text.includes("animation") || text.includes("短视频") || text.includes("动画")) {
    return "video";
  }
  return normalizeResourceType(type);
}

function readStringFromRecord(source: Record<string, unknown> | undefined, key: string) {
  return source ? readString(source, key) : "";
}
