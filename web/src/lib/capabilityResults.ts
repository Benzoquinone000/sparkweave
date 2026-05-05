import type { AudioNarrationResult, ExternalVideoResult, MathAnimatorArtifact, MathAnimatorResult, VisualizeResult } from "@/lib/types";

function stripCodeFences(source: string) {
  const trimmed = source.trim();
  const fenced = trimmed.match(/^```[\w-]*\s*([\s\S]*?)\s*```$/);
  if (fenced) return fenced[1].trim();
  if (trimmed.startsWith("```")) {
    return trimmed.split("\n").slice(1).join("\n").trim();
  }
  return trimmed;
}

function cleanMathAnimatorCode(source: unknown) {
  const stripped = stripCodeFences(String(source ?? ""));
  if (!stripped.startsWith("{")) return stripped;
  try {
    const parsed = JSON.parse(stripped) as { code?: unknown };
    return typeof parsed.code === "string" ? parsed.code.trim() : stripped;
  } catch {
    return stripped;
  }
}

function cleanVisualizeResponse(response: unknown, codeContent: string) {
  const text = String(response ?? "").trim();
  if (!text) return "";
  const stripped = stripCodeFences(text);
  if (text.startsWith("```")) return "";
  if (stripped && stripped === codeContent.trim()) return "";
  return text;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function extractLearnerProfileHints(resultMetadata: Record<string, unknown>) {
  const nested = asRecord(resultMetadata.metadata);
  return (
    asRecord(resultMetadata.learner_profile_hints) ??
    asRecord(resultMetadata.personalization) ??
    asRecord(nested?.learner_profile_hints) ??
    asRecord(nested?.personalization) ??
    undefined
  );
}

function extractStyleHint(resultMetadata: Record<string, unknown>) {
  const nested = asRecord(resultMetadata.metadata);
  const value = resultMetadata.style_hint ?? resultMetadata.visual_style ?? nested?.style_hint ?? nested?.visual_style;
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function extractAudioNarrationResult(resultMetadata: Record<string, unknown>): AudioNarrationResult | undefined {
  const narration = asRecord(resultMetadata.audio_narration);
  const audio = asRecord(narration?.audio);
  if (!narration || !audio || typeof audio.asset_url !== "string" || !audio.asset_url) return undefined;
  return {
    response: typeof narration.response === "string" ? narration.response : "",
    script_text: typeof narration.script_text === "string" ? narration.script_text : "",
    learner_profile_hints:
      asRecord(narration.learner_profile_hints) ?? extractLearnerProfileHints(resultMetadata),
    style_hint:
      (typeof narration.style_hint === "string" && narration.style_hint.trim()
        ? narration.style_hint.trim()
        : extractStyleHint(resultMetadata)),
    video: (() => {
      const video = asRecord(narration.video);
      if (!video || typeof video.asset_url !== "string" || !video.asset_url) return undefined;
      return {
        asset_url: video.asset_url,
        filename: typeof video.filename === "string" ? video.filename : undefined,
        content_type: typeof video.content_type === "string" ? video.content_type : undefined,
        label: typeof video.label === "string" ? video.label : undefined,
      };
    })(),
    audio: {
      asset_url: audio.asset_url as string,
      filename: typeof audio.filename === "string" ? audio.filename : undefined,
      content_type: typeof audio.content_type === "string" ? audio.content_type : undefined,
      encoding: typeof audio.encoding === "string" ? audio.encoding : undefined,
      sample_rate: typeof audio.sample_rate === "number" ? audio.sample_rate : undefined,
      voice: typeof audio.voice === "string" ? audio.voice : undefined,
      byte_length: typeof audio.byte_length === "number" ? audio.byte_length : undefined,
      sid: typeof audio.sid === "string" ? audio.sid : undefined,
    },
  };
}

export function extractMathAnimatorResult(resultMetadata: Record<string, unknown> | undefined): MathAnimatorResult | null {
  if (!resultMetadata) return null;
  const artifacts = Array.isArray(resultMetadata.artifacts)
    ? resultMetadata.artifacts.filter((item): item is MathAnimatorArtifact => {
        if (!item || typeof item !== "object") return false;
        const record = item as Record<string, unknown>;
        return (
          (record.type === "video" || record.type === "image" || record.type === "audio") &&
          typeof record.url === "string" &&
          typeof record.filename === "string"
        );
      })
    : [];
  const code = resultMetadata.code && typeof resultMetadata.code === "object" ? (resultMetadata.code as Record<string, unknown>) : {};
  const timings =
    resultMetadata.timings && typeof resultMetadata.timings === "object"
      ? (resultMetadata.timings as Record<string, number>)
      : {};
  const render =
    resultMetadata.render && typeof resultMetadata.render === "object"
      ? (resultMetadata.render as MathAnimatorResult["render"])
      : {};
  const audioNarration = extractAudioNarrationResult(resultMetadata);
  const hasOutputMode = resultMetadata.output_mode === "video" || resultMetadata.output_mode === "image";

  if (!artifacts.length && !code.content && !hasOutputMode && !Object.keys(timings).length && !Object.keys(render ?? {}).length && !audioNarration) {
    return null;
  }

  return {
    response: String(resultMetadata.response ?? ""),
    output_mode: resultMetadata.output_mode === "image" ? "image" : "video",
    learner_profile_hints: extractLearnerProfileHints(resultMetadata),
    style_hint: extractStyleHint(resultMetadata),
    code: {
      language: String(code.language ?? "python"),
      content: cleanMathAnimatorCode(code.content),
    },
    artifacts,
    timings,
    render,
    audio_narration: audioNarration,
  };
}

export function extractVisualizeResult(resultMetadata: Record<string, unknown> | undefined): VisualizeResult | null {
  if (!resultMetadata) return null;
  const renderType = resultMetadata.render_type;
  if (renderType !== "svg" && renderType !== "chartjs" && renderType !== "mermaid") return null;
  const metadata = resultMetadata;
  const code = metadata.code && typeof metadata.code === "object" ? (metadata.code as Record<string, unknown>) : {};
  if (!code.content) return null;
  const codeContent = stripCodeFences(String(code.content ?? ""));
  return {
    response: cleanVisualizeResponse(metadata.response, codeContent),
    render_type: renderType,
    learner_profile_hints: extractLearnerProfileHints(metadata),
    style_hint: extractStyleHint(metadata),
    code: {
      language: String(code.language ?? renderType),
      content: codeContent,
    },
    analysis:
      metadata.analysis && typeof metadata.analysis === "object"
        ? (metadata.analysis as VisualizeResult["analysis"])
        : undefined,
    review:
      metadata.review && typeof metadata.review === "object"
        ? (metadata.review as VisualizeResult["review"])
        : undefined,
  };
}

export function extractExternalVideoResult(resultMetadata: Record<string, unknown> | undefined): ExternalVideoResult | null {
  if (!resultMetadata) return null;
  if (resultMetadata.render_type !== "external_video" && !Array.isArray(resultMetadata.videos)) return null;
  const videos = Array.isArray(resultMetadata.videos)
    ? resultMetadata.videos.filter((item): item is NonNullable<ExternalVideoResult["videos"]>[number] => {
        if (!item || typeof item !== "object") return false;
        const record = item as Record<string, unknown>;
        return typeof record.title === "string" && typeof record.url === "string";
      })
    : [];
  if (!videos.length && !resultMetadata.response) return null;
  return {
    success: resultMetadata.success !== false,
    render_type: "external_video",
    response: String(resultMetadata.response ?? ""),
    learner_profile_hints: extractLearnerProfileHints(resultMetadata),
    style_hint: extractStyleHint(resultMetadata),
    videos,
    queries: Array.isArray(resultMetadata.queries) ? resultMetadata.queries.map(String) : undefined,
    search_errors: Array.isArray(resultMetadata.search_errors) ? resultMetadata.search_errors.map(String) : undefined,
    fallback_search: resultMetadata.fallback_search === true,
    agent_chain: Array.isArray(resultMetadata.agent_chain)
      ? (resultMetadata.agent_chain as ExternalVideoResult["agent_chain"])
      : undefined,
    tool_chain: Array.isArray(resultMetadata.tool_chain)
      ? (resultMetadata.tool_chain as ExternalVideoResult["tool_chain"])
      : undefined,
  };
}
