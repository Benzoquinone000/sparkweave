import { spawn } from "node:child_process";
const steps = [
  ["check:design", "Visual contract"],
  ["check:api-contract", "API contract"],
  ["check:replacement", "NG replacement guard"],
  ["lint", "ESLint"],
  ["build", "Production build"],
  ["test:e2e:isolated", "Playwright isolated smoke tests"],
];

function formatDuration(startedAt) {
  const seconds = (Date.now() - startedAt) / 1000;
  return `${seconds.toFixed(1)}s`;
}

function runStep([script, label]) {
  return new Promise((resolve, reject) => {
    const startedAt = Date.now();
    console.log(`\n[verify] ${label} -> npm run ${script}`);
    const command = process.platform === "win32" ? process.env.ComSpec || "cmd.exe" : "npm";
    const args = process.platform === "win32" ? ["/d", "/s", "/c", `npm run ${script}`] : ["run", script];
    const child = spawn(command, args, {
      stdio: "inherit",
      env: process.env,
      shell: false,
    });

    child.on("error", reject);
    child.on("exit", (code) => {
      const duration = formatDuration(startedAt);
      if (code === 0) {
        console.log(`[verify] ${label} passed in ${duration}`);
        resolve();
        return;
      }
      reject(new Error(`${label} failed with exit code ${code ?? "unknown"} after ${duration}`));
    });
  });
}

for (const step of steps) {
  await runStep(step);
}

console.log("\n[verify] SparkWeave frontend verification passed.");
