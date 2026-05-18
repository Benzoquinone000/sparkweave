import type { LearnerProfileSnapshot } from "@/lib/types";

export function buildNextActionHref(action: NonNullable<LearnerProfileSnapshot["next_action"]>) {
  const href = typeof action.href === "string" && action.href.trim() ? action.href : "/guide";
  const title = typeof action.title === "string" ? action.title.trim() : "";
  const prompt = typeof action.suggested_prompt === "string" ? action.suggested_prompt.trim() : "";
  const minutes = typeof action.estimated_minutes === "number" && Number.isFinite(action.estimated_minutes) ? Math.round(action.estimated_minutes) : null;
  const confidence = typeof action.confidence === "number" ? Math.max(0, Math.min(1, action.confidence)) : null;
  const actionParams = new URLSearchParams();
  actionParams.set("new", "1");
  if (prompt) actionParams.set("prompt", prompt);
  if (title) actionParams.set("action_title", title);
  if (typeof action.kind === "string" && action.kind.trim()) actionParams.set("action_kind", action.kind.trim());
  if (typeof action.source_type === "string" && action.source_type.trim()) actionParams.set("source_type", action.source_type.trim());
  if (typeof action.source_label === "string" && action.source_label.trim()) actionParams.set("source_label", action.source_label.trim());
  if (minutes) actionParams.set("estimated_minutes", String(minutes));
  if (confidence !== null) actionParams.set("confidence", String(confidence));
  actionParams.set("target_section", "guide-create-section");
  return `${href}${href.includes("?") ? "&" : "?"}${actionParams.toString()}`;
}

export function buildGuidePromptHref({
  prompt,
  title,
  sourceType,
  sourceLabel,
  actionKind,
  minutes,
  confidence,
}: {
  prompt: string;
  title: string;
  sourceType: string;
  sourceLabel: string;
  actionKind: string;
  minutes?: number;
  confidence?: number;
}) {
  const actionParams = new URLSearchParams();
  actionParams.set("new", "1");
  actionParams.set("prompt", prompt);
  actionParams.set("action_title", title);
  actionParams.set("action_kind", actionKind);
  actionParams.set("source_type", sourceType);
  actionParams.set("source_label", sourceLabel);
  if (typeof minutes === "number" && Number.isFinite(minutes)) actionParams.set("estimated_minutes", String(Math.round(minutes)));
  if (typeof confidence === "number" && Number.isFinite(confidence)) actionParams.set("confidence", String(Math.max(0, Math.min(1, confidence))));
  actionParams.set("target_section", "guide-create-section");
  return `/guide?${actionParams.toString()}`;
}
