import type { MathAnimatorArtifact, MathAnimatorResult, VisualizeResult } from "@/lib/types";

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

export function extractMathAnimatorResult(resultMetadata: Record<string, unknown> | undefined): MathAnimatorResult | null {
  if (!resultMetadata) return null;
  const artifacts = Array.isArray(resultMetadata.artifacts)
    ? resultMetadata.artifacts.filter((item): item is MathAnimatorArtifact => {
        if (!item || typeof item !== "object") return false;
        const record = item as Record<string, unknown>;
        return (
          (record.type === "video" || record.type === "image") &&
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
  const hasOutputMode = resultMetadata.output_mode === "video" || resultMetadata.output_mode === "image";

  if (!artifacts.length && !code.content && !hasOutputMode && !Object.keys(timings).length && !Object.keys(render ?? {}).length) {
    return null;
  }

  return {
    response: String(resultMetadata.response ?? ""),
    output_mode: resultMetadata.output_mode === "image" ? "image" : "video",
    code: {
      language: String(code.language ?? "python"),
      content: cleanMathAnimatorCode(code.content),
    },
    artifacts,
    timings,
    render,
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
