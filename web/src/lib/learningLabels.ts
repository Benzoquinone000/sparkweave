export function questionDifficultyLabel(value: string | undefined | null) {
  const normalized = String(value || "").trim().toLowerCase();
  if (!normalized) return "未设置";
  if (["easy", "basic", "beginner", "low"].includes(normalized)) return "基础";
  if (["medium", "normal", "moderate", "middle"].includes(normalized)) return "中等";
  if (["hard", "advanced", "challenge", "high"].includes(normalized)) return "挑战";
  return String(value);
}
