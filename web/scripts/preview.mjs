import { spawn } from "node:child_process";
import path from "node:path";

import { resolveApiBase, resolveFrontendPort } from "./env.mjs";

const apiBase = resolveApiBase();
const port = resolveFrontendPort();

process.env.VITE_API_BASE = apiBase;
process.env.FRONTEND_PORT = port;

console.log(`[SparkWeave Web] API ${apiBase}`);
console.log(`[SparkWeave Web] Preview http://localhost:${port}`);

const viteBin = path.resolve(process.cwd(), "node_modules", "vite", "bin", "vite.js");
const child = spawn(process.execPath, [viteBin, "preview", "--host", "0.0.0.0", "--port", port], {
  stdio: "inherit",
  env: process.env,
});

child.on("exit", (code) => process.exit(code ?? 0));
