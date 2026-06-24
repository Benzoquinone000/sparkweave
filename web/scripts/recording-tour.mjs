/* global document */

import { spawn } from "node:child_process";
import readline from "node:readline/promises";
import { stdin as input, stdout as output } from "node:process";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "@playwright/test";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(scriptDir, "..");

const TOUR_PROFILES = {
  short: ["/", "/guide", "/knowledge", "/chat", "/memory", "/settings", "/agents"],
  core: ["/", "/guide", "/knowledge", "/chat", "/question", "/notebook", "/memory", "/settings", "/agents", "/guide"],
  full: [
    "/",
    "/guide",
    "/knowledge",
    "/chat",
    "/question",
    "/notebook",
    "/memory",
    "/vision",
    "/co-writer",
    "/playground",
    "/settings",
    "/agents",
    "/guide",
  ],
};

const STEPS = [
  {
    route: "/",
    title: "项目首页",
    cue: "先用这一页讲清作品定位：SparkWeave 是面向高校课程的个性化学习多智能体系统。这里不是正式工作台，而是录制和答辩时的项目入口。",
    focus: ["项目定位", "进入主页面", "Agentic RAG"],
    highlights: [{ text: "进入主页面" }, { text: "Agentic RAG" }],
    after: { clickText: "进入主页面" },
  },
  {
    route: "/guide",
    title: "学习主页面",
    cue: "从真实学生视角进入：先看到课程、当前任务、学习路线和下一步动作。这里对应个性化学习路径规划，不把 Agent、RAG、画像这些工程能力堆成菜单。",
    focus: ["课程主线", "当前任务", "个性化路径"],
    highlights: [{ text: "深度学习" }, { text: "当前任务" }, { text: "学习路线" }],
    scroll: 280,
  },
  {
    route: "/knowledge",
    title: "资料与 Agentic RAG",
    cue: "这一页展示课程资料入库、资料状态、试问和来源检查。讲解重点是 Agentic RAG：复杂问题会先拆分检索，再合并证据，并保留来源链路。",
    focus: ["课程资料", "RAG 证据链", "来源检查"],
    highlights: [{ text: "资料" }, { text: "来源" }, { text: "试问" }],
    scroll: 360,
  },
  {
    route: "/chat",
    title: "问问题与智能辅导",
    cue: "这里展示学生自然语言提问入口。系统会根据问题自动调度资料检索、解题、图解、练习、视频讲解等能力；录制时可以在这里手动发送一次真实问题。",
    focus: ["智能辅导", "自动调度", "多模态资源"],
    highlights: [{ text: "本轮设置" }, { text: "资料库" }, { text: "发送" }],
    prefill:
      "请结合深度学习课程资料，用图解方式讲清楚 CNN 卷积层的作用，并给 3 道练习。",
  },
  {
    route: "/question",
    title: "练习生成",
    cue: "这一页用于展示出题和练习评估。它不是孤立题库，而是可以从当前课程、薄弱点和资料证据出发，生成适合当前学生的练习。",
    focus: ["出题智能体", "练习反馈", "效果评估"],
    highlights: [{ text: "练习" }, { text: "生成" }, { text: "题目" }],
    scroll: 240,
  },
  {
    route: "/notebook",
    title: "学习记录",
    cue: "学习产出、资料问答、练习和资源卡片可以沉淀到记录里。这里适合说明：系统后续推荐不是凭空生成，而是从学习证据继续往下走。",
    focus: ["学习产出", "错题与笔记", "资源沉淀"],
    highlights: [{ text: "记录" }, { text: "题目" }, { text: "保存" }],
    scroll: 260,
  },
  {
    route: "/memory",
    title: "学习画像",
    cue: "画像页展示目标、偏好、薄弱点和下一步建议。重点说清楚：画像是由学习记录、反馈和练习结果累积出来的，不是一次性填表。",
    focus: ["学习证据", "薄弱点", "下一步建议"],
    highlights: [{ text: "薄弱" }, { text: "偏好" }, { text: "下一步" }],
    scroll: 300,
  },
  {
    route: "/vision",
    title: "图片与公式理解",
    cue: "这里展示多模态辅导入口。遇到图片、几何图、公式或题目截图时，系统可以把视觉理解结果转成可解释的学习材料。",
    focus: ["图片理解", "公式识别", "多模态辅导"],
    highlights: [{ text: "图片" }, { text: "公式" }, { text: "识别" }],
  },
  {
    route: "/co-writer",
    title: "学习材料共写",
    cue: "这一页适合展示生成后的学习材料如何继续润色、改写和整理，便于形成课程笔记、答辩讲稿或学习总结。",
    focus: ["材料整理", "润色改写", "学习总结"],
    highlights: [{ text: "共写" }, { text: "润色" }, { text: "改写" }],
  },
  {
    route: "/playground",
    title: "能力试跑",
    cue: "这里用于演示底层能力的试跑和验证。正式讲解时不必久留，只说明工程能力都能回到学习主线中使用。",
    focus: ["能力验证", "工具试跑", "工程边界"],
    highlights: [{ text: "能力" }, { text: "工具" }, { text: "运行" }],
  },
  {
    route: "/settings",
    title: "讯飞工具链与服务配置",
    cue: "设置页用于展示星火模型、Spark Embedding、搜索、OCR、语音和工作流等入口。录制时注意不要暴露完整密钥，只展示服务类型和连接状态。",
    focus: ["星火模型", "Embedding", "OCR / 语音 / 搜索"],
    highlights: [{ text: "星火" }, { text: "Embedding" }, { text: "OCR" }],
    scroll: 320,
  },
  {
    route: "/agents",
    title: "课程助教",
    cue: "课程助教是长期运行入口：它可以保存课程资料、历史上下文、提醒任务，也可以接入 QQ 私聊、群聊等外部学习场景。",
    focus: ["长期助教", "定时提醒", "QQ 通道"],
    highlights: [{ text: "课程助教" }, { text: "提醒" }, { text: "通道" }],
    scroll: 320,
  },
  {
    route: "/guide",
    title: "学习闭环收束",
    cue: "最后回到学习页，把主线收住：学习画像影响路径，课程资料提供证据，多智能体生成资源，练习和反馈再回写到记录与画像。",
    focus: ["画像 -> 路径", "RAG -> 资源", "评估 -> 调整"],
    highlights: [{ text: "当前任务" }, { text: "学习反馈" }, { text: "下一步" }],
  },
];

async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.help) {
    printHelp();
    return;
  }

  const tour = buildTour(options.profile);
  if (!tour.length) {
    throw new Error(`Unknown recording profile: ${options.profile}`);
  }

  const runtime = await ensureFrontend(options);
  let browser;
  let context;
  const rl = readline.createInterface({ input, output });

  const stop = () => stopServer(runtime.server);
  process.once("SIGINT", () => {
    stop();
    process.exit(130);
  });

  try {
    browser = await chromium.launch({
      headless: options.headless,
      slowMo: options.slowMo,
      args: [`--window-size=${options.width},${options.height}`, "--force-device-scale-factor=1"],
    });
    context = await browser.newContext({
      viewport: { width: options.width, height: options.height },
      deviceScaleFactor: 1,
      locale: "zh-CN",
      colorScheme: "light",
    });
    const page = await context.newPage();

    console.log(`[recording-tour] using ${runtime.baseURL}`);
    console.log(`[recording-tour] profile=${options.profile}, steps=${tour.length}`);

    for (let index = 0; index < tour.length; index += 1) {
      const step = tour[index];
      await visitStep(page, runtime.baseURL, step);
      await prepareStep(page, step);
      await showCue(page, step, index + 1, tour.length, options);
      await highlightStep(page, step);

      if (options.manual) {
        await rl.question(`\n[${index + 1}/${tour.length}] ${step.title}：讲完按 Enter 继续...`);
      } else {
        await waitWithMotion(page, step, options.stepMs);
      }

      await runAfterAction(page, step);
    }

    await clearTourUi(page);
    console.log("\n[recording-tour] 导览完成。");
    if (options.keepOpen && !options.headless) {
      await rl.question("[recording-tour] 浏览器会保持在最后一页，停止录屏后按 Enter 关闭...");
    }
  } finally {
    rl.close();
    await context?.close().catch(() => {});
    await browser?.close().catch(() => {});
    stop();
  }
}

function parseArgs(args) {
  const options = {
    baseURL: process.env.RECORDING_BASE_URL || "http://127.0.0.1:3782",
    profile: process.env.RECORDING_PROFILE || "core",
    stepMs: Number(process.env.RECORDING_STEP_MS || 18_000),
    manual: false,
    headless: false,
    keepOpen: true,
    startServer: true,
    width: Number(process.env.RECORDING_WIDTH || 1600),
    height: Number(process.env.RECORDING_HEIGHT || 900),
    slowMo: Number(process.env.RECORDING_SLOW_MO || 0),
    help: false,
  };

  for (const arg of args) {
    if (arg === "--help" || arg === "-h") options.help = true;
    else if (arg === "--manual") options.manual = true;
    else if (arg === "--headless") {
      options.headless = true;
      options.keepOpen = false;
    } else if (arg === "--no-start-server") options.startServer = false;
    else if (arg === "--no-keep-open") options.keepOpen = false;
    else if (arg === "--keep-open") options.keepOpen = true;
    else if (arg.startsWith("--url=")) options.baseURL = arg.slice("--url=".length);
    else if (arg.startsWith("--profile=")) options.profile = arg.slice("--profile=".length);
    else if (arg.startsWith("--step-ms=")) options.stepMs = Number(arg.slice("--step-ms=".length));
    else if (arg.startsWith("--width=")) options.width = Number(arg.slice("--width=".length));
    else if (arg.startsWith("--height=")) options.height = Number(arg.slice("--height=".length));
    else if (arg.startsWith("--slow-mo=")) options.slowMo = Number(arg.slice("--slow-mo=".length));
  }

  options.baseURL = normalizeBaseURL(options.baseURL);
  if (!Number.isFinite(options.stepMs) || options.stepMs < 100) options.stepMs = 18_000;
  if (!Number.isFinite(options.width) || options.width < 800) options.width = 1600;
  if (!Number.isFinite(options.height) || options.height < 600) options.height = 900;
  return options;
}

function printHelp() {
  console.log(`SparkWeave recording tour

Usage:
  npm run record:tour
  npm run record:tour -- --manual
  npm run record:tour -- --profile=full --step-ms=22000
  npm run record:tour -- --url=http://127.0.0.1:3782 --no-start-server

Options:
  --profile=short|core|full   导览范围，默认 core
  --manual                    每一步讲完后在终端按 Enter 继续
  --step-ms=18000             自动模式每页停留时间
  --url=http://...            前端地址，默认 http://127.0.0.1:3782
  --no-start-server           前端不可访问时直接报错，不自动启动 dev server
  --width=1600 --height=900   浏览器窗口和视口尺寸
  --headless                  无界面检查脚本
  --no-keep-open              导览结束后自动关闭浏览器
`);
}

function buildTour(profile) {
  const routes = TOUR_PROFILES[profile];
  if (!routes) return [];
  const routeCounts = new Map();
  return routes.map((route) => {
    const seen = routeCounts.get(route) || 0;
    routeCounts.set(route, seen + 1);
    const matches = STEPS.filter((step) => step.route === route);
    return matches[Math.min(seen, matches.length - 1)] || matches[0];
  });
}

async function ensureFrontend(options) {
  if (await canReach(options.baseURL)) {
    return { baseURL: options.baseURL, server: null };
  }

  if (!options.startServer) {
    throw new Error(`Frontend is not reachable: ${options.baseURL}`);
  }

  const url = new URL(options.baseURL);
  const port = url.port || (url.protocol === "https:" ? "443" : "80");
  const server = spawn(process.execPath, ["./scripts/dev.mjs"], {
    cwd: webRoot,
    env: {
      ...process.env,
      FRONTEND_PORT: port,
      NO_PROXY: appendNoProxy(process.env.NO_PROXY),
      no_proxy: appendNoProxy(process.env.no_proxy),
    },
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });

  server.stdout.on("data", (data) => process.stdout.write(data));
  server.stderr.on("data", (data) => process.stderr.write(data));
  await waitForFrontend(options.baseURL);
  return { baseURL: options.baseURL, server };
}

async function canReach(baseURL) {
  try {
    const response = await fetch(baseURL, { signal: AbortSignal.timeout(1800) });
    return response.ok;
  } catch {
    return false;
  }
}

async function waitForFrontend(baseURL) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < 120_000) {
    if (await canReach(baseURL)) return;
    await sleep(500);
  }
  throw new Error(`Timed out waiting for frontend: ${baseURL}`);
}

function stopServer(server) {
  if (server && !server.killed) server.kill();
}

async function visitStep(page, baseURL, step) {
  await page.goto(new URL(step.route, baseURL).href, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle", { timeout: 6_000 }).catch(() => {});
  await page.evaluate(() => globalThis.document?.fonts?.ready).catch(() => {});
  await page.waitForTimeout(500);
}

async function prepareStep(page, step) {
  if (step.prefill) {
    await prefillPrompt(page, step.prefill);
  }
  await page.mouse.move(40, 40).catch(() => {});
}

async function prefillPrompt(page, text) {
  const candidates = [
    page.locator("textarea").last(),
    page.locator("[contenteditable='true']").last(),
    page.locator("input[type='text']").last(),
  ];
  for (const locator of candidates) {
    const count = await locator.count().catch(() => 0);
    if (!count) continue;
    const visible = await locator.isVisible().catch(() => false);
    if (!visible) continue;
    await locator.fill(text).catch(async () => {
      await locator.click();
      await page.keyboard.insertText(text);
    });
    return;
  }
}

async function showCue(page, step, index, total, options) {
  await page.evaluate(
    ({ cue, focus, index: stepIndex, totalSteps, title, seconds, manual }) => {
      const oldNodes = document.querySelectorAll("[data-recording-tour]");
      oldNodes.forEach((node) => node.remove());

      const style = document.createElement("style");
      style.dataset.recordingTour = "style";
      style.textContent = `
        [data-recording-tour="cue"] {
          position: fixed;
          left: 24px;
          bottom: 24px;
          z-index: 2147483647;
          width: min(520px, calc(100vw - 48px));
          border: 1px solid rgba(45, 45, 45, 0.14);
          border-radius: 8px;
          background: rgba(255, 255, 255, 0.96);
          box-shadow: 0 18px 42px rgba(15, 23, 42, 0.16);
          color: #202124;
          font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          line-height: 1.55;
          padding: 16px;
          pointer-events: none;
        }
        [data-recording-tour="cue"] .recording-kicker {
          color: #6b7280;
          font-size: 12px;
          font-weight: 700;
          letter-spacing: 0;
          margin-bottom: 6px;
        }
        [data-recording-tour="cue"] .recording-title {
          color: #111827;
          font-size: 22px;
          font-weight: 760;
          letter-spacing: 0;
          margin: 0 0 8px;
        }
        [data-recording-tour="cue"] .recording-copy {
          color: #4b5563;
          font-size: 14px;
          margin: 0;
        }
        [data-recording-tour="cue"] .recording-focus {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
          margin-top: 12px;
        }
        [data-recording-tour="cue"] .recording-focus span {
          border: 1px solid rgba(80, 71, 54, 0.16);
          border-radius: 8px;
          background: #f8f7f4;
          color: #504736;
          font-size: 12px;
          font-weight: 700;
          padding: 4px 8px;
        }
        [data-recording-tour="spotlight"] {
          position: fixed;
          z-index: 2147483646;
          border: 2px solid rgba(81, 74, 55, 0.68);
          border-radius: 8px;
          box-shadow: 0 0 0 9999px rgba(255, 255, 255, 0.04), 0 12px 34px rgba(15, 23, 42, 0.14);
          pointer-events: none;
        }
      `;

      const card = document.createElement("aside");
      card.dataset.recordingTour = "cue";

      const kicker = document.createElement("div");
      kicker.className = "recording-kicker";
      kicker.textContent = `录制导览 ${stepIndex}/${totalSteps} · ${
        manual ? "讲完后终端按 Enter" : `自动停留约 ${seconds} 秒`
      }`;

      const heading = document.createElement("h1");
      heading.className = "recording-title";
      heading.textContent = title;

      const copy = document.createElement("p");
      copy.className = "recording-copy";
      copy.textContent = cue;

      const chips = document.createElement("div");
      chips.className = "recording-focus";
      focus.forEach((item) => {
        const chip = document.createElement("span");
        chip.textContent = item;
        chips.appendChild(chip);
      });

      card.append(kicker, heading, copy, chips);
      document.body.append(style, card);
    },
    {
      title: step.title,
      cue: step.cue,
      focus: step.focus || [],
      index,
      total,
      seconds: Math.round(options.stepMs / 1000),
      manual: options.manual,
    },
  );
}

async function highlightStep(page, step) {
  const boxes = [];
  for (const spec of step.highlights || []) {
    const locator = buildLocator(page, spec);
    const count = await locator.count().catch(() => 0);
    if (!count) continue;
    const visible = await locator.first().isVisible().catch(() => false);
    if (!visible) continue;
    const box = await locator.first().boundingBox().catch(() => null);
    if (!box || box.width < 12 || box.height < 12) continue;
    boxes.push({
      x: Math.max(4, box.x - 6),
      y: Math.max(4, box.y - 6),
      width: box.width + 12,
      height: box.height + 12,
    });
    if (boxes.length >= 3) break;
  }

  await page.evaluate((items) => {
    document.querySelectorAll('[data-recording-tour="spotlight"]').forEach((node) => node.remove());
    items.forEach((box) => {
      const marker = document.createElement("div");
      marker.dataset.recordingTour = "spotlight";
      marker.style.left = `${box.x}px`;
      marker.style.top = `${box.y}px`;
      marker.style.width = `${box.width}px`;
      marker.style.height = `${box.height}px`;
      document.body.appendChild(marker);
    });
  }, boxes);
}

function buildLocator(page, spec) {
  if (spec.css) return page.locator(spec.css);
  if (spec.role) return page.getByRole(spec.role, { name: spec.name });
  return page.getByText(spec.text, { exact: false });
}

async function waitWithMotion(page, step, stepMs) {
  const beforeScrollMs = Math.max(900, Math.floor(stepMs * 0.55));
  await page.waitForTimeout(beforeScrollMs);
  if (step.scroll) {
    await page.mouse.wheel(0, step.scroll).catch(() => {});
    await page.waitForTimeout(650);
    await page.mouse.wheel(0, Math.round(step.scroll * -0.35)).catch(() => {});
  }
  await page.waitForTimeout(Math.max(0, stepMs - beforeScrollMs));
}

async function runAfterAction(page, step) {
  if (!step.after?.clickText) return;
  const link = page.getByRole("link", { name: new RegExp(step.after.clickText) }).first();
  const button = page.getByRole("button", { name: new RegExp(step.after.clickText) }).first();
  if (await link.isVisible().catch(() => false)) {
    await link.click().catch(() => {});
  } else if (await button.isVisible().catch(() => false)) {
    await button.click().catch(() => {});
  }
  await page.waitForLoadState("domcontentloaded", { timeout: 5_000 }).catch(() => {});
  await page.waitForTimeout(700);
}

async function clearTourUi(page) {
  await page.evaluate(() => {
    document.querySelectorAll("[data-recording-tour]").forEach((node) => node.remove());
  });
}

function normalizeBaseURL(value) {
  const url = new URL(value);
  url.pathname = "/";
  url.search = "";
  url.hash = "";
  return url.toString().replace(/\/$/, "");
}

function appendNoProxy(value) {
  const items = new Set(
    (value || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
  );
  ["127.0.0.1", "localhost", "::1"].forEach((host) => items.add(host));
  return Array.from(items).join(",");
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
