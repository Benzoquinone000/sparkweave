import { spawn } from "node:child_process";
import net from "node:net";
import path from "node:path";

function appendNoProxy(value) {
  const items = new Set(
    (value || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
  );
  for (const host of ["127.0.0.1", "localhost", "::1"]) {
    items.add(host);
  }
  return Array.from(items).join(",");
}

function findFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      if (!address || typeof address === "string") {
        server.close(() => reject(new Error("Could not allocate a frontend port.")));
        return;
      }
      const port = String(address.port);
      server.close((error) => {
        if (error) {
          reject(error);
          return;
        }
        resolve(port);
      });
    });
  });
}

const port = await findFreePort();
const playwrightCli = path.resolve(process.cwd(), "node_modules", "@playwright", "test", "cli.js");
const env = {
  ...process.env,
  FRONTEND_PORT: port,
  NO_PROXY: appendNoProxy(process.env.NO_PROXY),
  PLAYWRIGHT_REUSE_SERVER: "0",
  no_proxy: appendNoProxy(process.env.no_proxy),
};
const args = [playwrightCli, "test", ...process.argv.slice(2)];

console.log(`[e2e-isolated] Running Playwright with Vite on http://127.0.0.1:${port}`);

const child = spawn(process.execPath, args, {
  stdio: "inherit",
  env,
  shell: false,
});

child.on("error", (error) => {
  console.error(error);
  process.exit(1);
});

child.on("exit", (code) => {
  process.exit(code ?? 0);
});
