import { spawnSync } from "node:child_process";
import path from "node:path";

import { resolveApiBase } from "./env.mjs";

process.env.VITE_API_BASE = resolveApiBase();

const viteBin = path.resolve(process.cwd(), "node_modules", "vite", "bin", "vite.js");
const result = spawnSync(process.execPath, [viteBin, "build"], {
  stdio: "inherit",
  env: process.env,
});

process.exit(result.status ?? 0);
