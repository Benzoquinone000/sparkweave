import { guideDisplayText, guideSafeFilename } from "@/lib/guideDisplay";

type GuideMarkdownDownloadInput = {
  markdown?: string | null;
  title?: unknown;
  fallbackName: string;
};

type GuideMarkdownDownloadResult =
  | { ok: true; filename: string }
  | { ok: false; reason: "empty" | "unavailable" };

export function downloadGuideMarkdown({
  markdown,
  title,
  fallbackName,
}: GuideMarkdownDownloadInput): GuideMarkdownDownloadResult {
  const content = markdown?.trim();
  if (!content) return { ok: false, reason: "empty" };
  if (typeof document === "undefined") return { ok: false, reason: "unavailable" };

  const filename = `${guideSafeFilename(guideDisplayText(title, fallbackName), fallbackName)}.md`;
  const url = URL.createObjectURL(new Blob([`${content}\n`], { type: "text/markdown;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
  return { ok: true, filename };
}
