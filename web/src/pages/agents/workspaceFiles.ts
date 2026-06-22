import type { SparkBotFile } from "@/lib/types";

export function orderWorkspaceFiles(files: SparkBotFile[]) {
  const priority = ["SOUL.md", "TOOLS.md", "AGENTS.md", "HEARTBEAT.md", "USER.md", "NOTES.md", "COURSE.md"];
  return [...files].sort((a, b) => {
    const ai = priority.indexOf(a.filename);
    const bi = priority.indexOf(b.filename);
    if (ai !== -1 || bi !== -1) return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
    return a.filename.localeCompare(b.filename);
  });
}
