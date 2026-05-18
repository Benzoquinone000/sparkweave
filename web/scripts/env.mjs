import fs from "node:fs";
import path from "node:path";

export function loadProjectEnv() {
  const root = path.resolve(process.cwd(), "..");
  const candidates = [path.join(root, ".env"), path.join(process.cwd(), ".env")];
  for (const file of candidates) {
    if (!fs.existsSync(file)) continue;
    const lines = fs.readFileSync(file, "utf8").split(/\r?\n/);
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
      const index = trimmed.indexOf("=");
      const key = trimmed.slice(0, index).trim();
      const value = trimmed.slice(index + 1).trim().replace(/^['"]|['"]$/g, "");
      if (key && process.env[key] == null) {
        process.env[key] = value;
      }
    }
  }
}

export function resolveApiBase() {
  loadProjectEnv();
  const explicit =
    process.env.VITE_API_BASE ||
    process.env.NEXT_PUBLIC_API_BASE_EXTERNAL ||
    process.env.NEXT_PUBLIC_API_BASE;
  if (explicit && explicit.trim()) {
    return explicit.trim();
  }
  return `http://localhost:${process.env.BACKEND_PORT || "8001"}`;
}

export function resolveFrontendPort() {
  loadProjectEnv();
  return process.env.FRONTEND_PORT || "3782";
}
