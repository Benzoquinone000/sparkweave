import { defineConfig, devices } from "@playwright/test";

const frontendPort = process.env.FRONTEND_PORT || "3782";
const loopbackHosts = ["127.0.0.1", "localhost", "::1"];

function appendNoProxy(value: string | undefined) {
  const items = new Set(
    (value || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
  );
  for (const host of loopbackHosts) {
    items.add(host);
  }
  return Array.from(items).join(",");
}

process.env.NO_PROXY = appendNoProxy(process.env.NO_PROXY);
process.env.no_proxy = appendNoProxy(process.env.no_proxy);

const apiBase =
  process.env.VITE_API_BASE ||
  process.env.NEXT_PUBLIC_API_BASE_EXTERNAL ||
  process.env.NEXT_PUBLIC_API_BASE ||
  `http://127.0.0.1:${process.env.BACKEND_PORT || "8001"}`;
const baseURL = `http://127.0.0.1:${frontendPort}`;
const reuseExistingServer = process.env.PLAYWRIGHT_REUSE_SERVER !== "0" && !process.env.CI;

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  expect: { timeout: 5_000 },
  use: {
    baseURL,
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npm run dev",
    url: `${baseURL}/chat`,
    reuseExistingServer,
    timeout: 120_000,
    env: {
      FRONTEND_PORT: frontendPort,
      NO_PROXY: process.env.NO_PROXY,
      VITE_API_BASE: apiBase,
      no_proxy: process.env.no_proxy,
    },
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 980 } } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
});
