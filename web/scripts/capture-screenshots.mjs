import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import net from "node:net";
import path from "node:path";

import { chromium } from "@playwright/test";

const root = process.cwd();

const desktop = { width: 1440, height: 900 };
const mobile = { width: 390, height: 844, isMobile: true, hasTouch: true };

const desktopShots = [
  { route: "/chat", files: ["screenshots-chat.png", "screenshots-refined-chat.png", "screenshots-simplified-chat.png", "screenshots-simplified-shell-chat-desktop.png"] },
  { route: "/chat", files: ["screenshots-simplified-chat-drawer.png"], prepare: openChatContext },
  { route: "/knowledge", files: ["screenshots-knowledge.png", "screenshots-finalcheck-knowledge.png", "screenshots-review-knowledge.png", "screenshots-simplified-final-knowledge.png", "screenshots-simplified-knowledge-desktop.png"] },
  { route: "/notebook", files: ["screenshots-simplified-notebook.png"] },
  { route: "/question", files: ["screenshots-simplified-question.png", "screenshots-simplified-final-question.png"] },
  { route: "/vision", files: ["screenshots-simplified-vision.png", "screenshots-simplified-final-vision.png"] },
  { route: "/agents", files: ["screenshots-agents.png", "screenshots-finalcheck-agents.png", "screenshots-review-agents.png", "screenshots-simplified-agents-desktop.png"] },
  { route: "/settings", files: ["screenshots-settings.png", "screenshots-finalcheck-settings.png", "screenshots-review-settings.png", "screenshots-simplified-final-settings.png", "screenshots-simplified-settings-expanded.png", "screenshots-simplified-shell-settings-desktop.png"] },
  { route: "/settings", files: ["screenshots-simplified-settings-collapsed.png"], prepare: collapseSidebar },
];

const mobileShots = [
  { route: "/chat", files: ["screenshots-simplified-shell-chat-mobile.png"] },
  { route: "/knowledge", files: ["screenshots-simplified-knowledge-mobile.png"] },
];

async function main() {
  const port = await findOpenPort(Number(process.env.SCREENSHOT_PORT || 43782));
  const baseURL = `http://127.0.0.1:${port}`;
  const server = await startServer(port, baseURL);
  const browser = await chromium.launch();
  try {
    await captureGroup(browser, baseURL, desktop, desktopShots);
    await captureGroup(browser, baseURL, mobile, mobileShots);
  } finally {
    await browser.close();
    stopServer(server);
  }
}

async function startServer(port, baseURL) {
  const child = spawn(process.execPath, ["./scripts/dev.mjs"], {
    cwd: root,
    env: {
      ...process.env,
      FRONTEND_PORT: String(port),
      VITE_API_BASE: baseURL,
      NO_PROXY: appendNoProxy(process.env.NO_PROXY),
      no_proxy: appendNoProxy(process.env.no_proxy),
    },
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });
  child.stdout.on("data", (data) => process.stdout.write(data));
  child.stderr.on("data", (data) => process.stderr.write(data));
  await waitForServer(`${baseURL}/chat`);
  return child;
}

function stopServer(child) {
  if (!child.killed) child.kill();
}

async function waitForServer(url) {
  const started = Date.now();
  while (Date.now() - started < 120_000) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // Vite is still warming up.
    }
    await sleep(500);
  }
  throw new Error(`Timed out waiting for ${url}`);
}

async function captureGroup(browser, baseURL, viewport, shots) {
  const context = await browser.newContext({ viewport, deviceScaleFactor: 1 });
  try {
    const page = await context.newPage();
    await installApiMocks(page);
    for (const shot of shots) {
      await page.goto(`${baseURL}${shot.route}`, { waitUntil: "networkidle" });
      await page.evaluate(() => globalThis.document.fonts.ready);
      await shot.prepare?.(page);
      await page.waitForTimeout(400);
      for (const file of shot.files) {
        const target = path.join(root, file);
        await fs.mkdir(path.dirname(target), { recursive: true });
        await page.screenshot({ path: target, fullPage: false });
        console.log(`[screenshots] wrote ${file}`);
      }
    }
  } finally {
    await context.close();
  }
}

function findOpenPort(startPort) {
  return new Promise((resolve, reject) => {
    const tryPort = (port) => {
      const server = net.createServer();
      server.unref();
      server.on("error", () => tryPort(port + 1));
      server.listen(port, "127.0.0.1", () => {
        const address = server.address();
        server.close(() => {
          if (typeof address === "object" && address?.port) resolve(address.port);
          else reject(new Error("Could not resolve an open screenshot port"));
        });
      });
    };
    tryPort(startPort);
  });
}

async function openChatContext(page) {
  const button = page.getByRole("button", { name: "上下文" }).first();
  if (await button.count()) {
    await button.click();
  }
}

async function collapseSidebar(page) {
  const button = page.getByLabel("折叠侧栏").first();
  if (await button.count()) {
    await button.click();
  }
}

async function installApiMocks(page) {
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const pathname = url.pathname;
    const method = request.method();

    if (pathname === "/api/v1/system/status") return route.fulfill({ json: systemStatus });
    if (pathname === "/api/v1/system/runtime-topology") return route.fulfill({ json: runtimeTopology });
    if (pathname === "/api/v1/agent-config/agents") return route.fulfill({ json: agentConfigs });
    if (pathname === "/api/v1/settings") return route.fulfill({ json: settings });
    if (pathname === "/api/v1/settings/catalog") return route.fulfill({ json: { catalog: settings.catalog } });
    if (pathname === "/api/v1/settings/tour/status") return route.fulfill({ json: { completed: true, needs_setup: false } });
    if (pathname === "/api/v1/settings/themes") return route.fulfill({ json: { themes: [{ id: "light", name: "浅色工作台" }] } });
    if (pathname === "/api/v1/settings/sidebar") return route.fulfill({ json: sidebarSettings });
    if (pathname.startsWith("/api/v1/system/test/")) return route.fulfill({ json: { status: "ok", message: "服务可用" } });
    if (pathname === "/api/v1/knowledge/list") return route.fulfill({ json: knowledgeBases });
    if (pathname === "/api/v1/knowledge/health") return route.fulfill({ json: { status: "healthy", provider: "llamaindex", total_knowledge_bases: 2 } });
    if (pathname === "/api/v1/knowledge/default") return route.fulfill({ json: { default_kb: "ai_textbook" } });
    if (pathname === "/api/v1/knowledge/rag-providers") return route.fulfill({ json: { default_provider: "llamaindex", providers: ragProviders } });
    if (pathname === "/api/v1/knowledge/configs") return route.fulfill({ json: knowledgeConfigs });
    if (pathname.match(/^\/api\/v1\/knowledge\/[^/]+$/)) return route.fulfill({ json: knowledgeDetail });
    if (pathname.endsWith("/progress")) return route.fulfill({ json: progress });
    if (pathname.endsWith("/config")) return route.fulfill({ json: { config: knowledgeConfigs.knowledge_bases.ai_textbook } });
    if (pathname.endsWith("/linked-folders")) return route.fulfill({ json: linkedFolders });
    if (pathname === "/api/v1/dashboard/recent") return route.fulfill({ json: dashboardActivities });
    if (pathname.startsWith("/api/v1/dashboard/")) return route.fulfill({ json: dashboardDetail });
    if (pathname === "/api/v1/sessions") return route.fulfill({ json: { sessions } });
    if (pathname.startsWith("/api/v1/sessions/")) return route.fulfill({ json: sessionDetail });
    if (pathname === "/api/v1/notebook/list") return route.fulfill({ json: { notebooks, total: notebooks.length } });
    if (pathname === "/api/v1/notebook/statistics") return route.fulfill({ json: { total_notebooks: 2, total_records: 8, total_questions: 12 } });
    if (pathname === "/api/v1/notebook/health") return route.fulfill({ json: { status: "healthy", service: "notebook" } });
    if (pathname.match(/^\/api\/v1\/notebook\/[^/]+$/)) return route.fulfill({ json: notebookDetail });
    if (pathname === "/api/v1/question-notebook/categories") return route.fulfill({ json: questionCategories });
    if (pathname === "/api/v1/question-notebook/entries") return route.fulfill({ json: { items: questionEntries, total: questionEntries.length } });
    if (pathname.startsWith("/api/v1/question-notebook/entries/")) return route.fulfill({ json: questionEntries[0] });
    if (pathname === "/api/v1/memory") return route.fulfill({ json: memory });
    if (pathname === "/api/v1/plugins/list") return route.fulfill({ json: plugins });
    if (pathname === "/api/v1/sparkbot") return route.fulfill({ json: sparkBots });
    if (pathname === "/api/v1/sparkbot/recent") return route.fulfill({ json: sparkBotRecent });
    if (pathname === "/api/v1/sparkbot/channels/schema") return route.fulfill({ json: channelSchemas });
    if (pathname === "/api/v1/sparkbot/souls") return route.fulfill({ json: souls });
    if (pathname.match(/^\/api\/v1\/sparkbot\/[^/]+\/files$/)) return route.fulfill({ json: sparkBotFiles });
    if (pathname.match(/^\/api\/v1\/sparkbot\/[^/]+\/history$/)) return route.fulfill({ json: sparkBotHistory });
    if (pathname.match(/^\/api\/v1\/sparkbot\/[^/]+$/)) return route.fulfill({ json: sparkBots[0] });
    if (pathname === "/api/v1/guide/health") return route.fulfill({ json: { status: "healthy" } });
    if (pathname === "/api/v1/guide/sessions") return route.fulfill({ json: { sessions: guideSessions } });
    if (pathname.startsWith("/api/v1/guide/session/") && pathname.endsWith("/html")) return route.fulfill({ json: { html: "<main><h1>函数极限导学</h1><p>从直觉、定义到典型题。</p></main>" } });
    if (pathname.startsWith("/api/v1/guide/session/") && pathname.endsWith("/pages")) return route.fulfill({ json: guidePages });
    if (pathname.startsWith("/api/v1/guide/session/")) return route.fulfill({ json: guideDetail });
    if (pathname === "/api/v1/co_writer/history") return route.fulfill({ json: { history: coWriterHistory, total: coWriterHistory.length } });
    if (pathname.startsWith("/api/v1/co_writer/history/")) return route.fulfill({ json: coWriterHistory[0] });
    if (pathname.startsWith("/api/v1/co_writer/tool_calls/")) return route.fulfill({ json: { calls: [] } });
    if (pathname === "/api/v1/vision/analyze") return route.fulfill({ json: visionResult });
    if (method !== "GET") return route.fulfill({ json: { success: true, status: "ok", task_id: "mock-task" } });
    return route.fulfill({ json: {} });
  });
}

function appendNoProxy(value) {
  const items = new Set((value || "").split(",").map((item) => item.trim()).filter(Boolean));
  ["127.0.0.1", "localhost", "::1"].forEach((host) => items.add(host));
  return Array.from(items).join(",");
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

const systemStatus = {
  backend: { status: "online", version: "SparkWeave" },
  llm: { status: "configured", model: "Spark Lite" },
  embeddings: { status: "configured", model: "bge-large-zh" },
  search: { status: "configured", provider: "web" },
};

const runtimeTopology = {
  coordinator: { status: "online", label: "对话协调智能体" },
  agents: [
    { id: "deep_solve", label: "求解智能体", status: "ready" },
    { id: "deep_question", label: "题目生成智能体", status: "ready" },
    { id: "visualize", label: "知识可视化智能体", status: "ready" },
    { id: "math_animator", label: "视频讲解智能体", status: "ready" },
  ],
};

const agentConfigs = {
  chat: { name: "对话协调智能体", enabled: true },
  deep_solve: { name: "深度求解", enabled: true },
  deep_question: { name: "交互式出题", enabled: true },
  visualize: { name: "知识可视化", enabled: true },
};

const modelCatalog = {
  version: 1,
  services: {
    llm: {
      active_profile_id: "spark",
      active_model_id: "spark-lite",
      profiles: [
        {
          id: "spark",
          name: "讯飞星火",
          binding: "spark",
          base_url: "https://spark-api-open.xf-yun.com",
          api_key: "configured",
          models: [{ id: "spark-lite", name: "Spark Lite", model: "spark-lite" }],
        },
      ],
    },
    embedding: {
      active_profile_id: "local-bge",
      active_model_id: "bge-large-zh",
      profiles: [
        {
          id: "local-bge",
          name: "本地向量",
          binding: "local",
          base_url: "http://127.0.0.1:8001",
          api_key: "configured",
          models: [{ id: "bge-large-zh", name: "BGE Large ZH", model: "bge-large-zh", dimension: "1024" }],
        },
      ],
    },
    search: {
      active_profile_id: "web-search",
      profiles: [
        {
          id: "web-search",
          name: "联网搜索",
          provider: "tavily",
          base_url: "https://api.tavily.com",
          api_key: "configured",
          models: [],
        },
      ],
    },
  },
};

const settings = {
  catalog: modelCatalog,
  ui: { theme: "light", language: "zh" },
  providers: {
    llm: [{ value: "spark", label: "讯飞星火", base_url: "https://spark-api-open.xf-yun.com" }],
    embedding: [{ value: "local", label: "本地向量", base_url: "http://127.0.0.1:8001", default_dim: "1024" }],
    search: [{ value: "tavily", label: "Tavily", base_url: "https://api.tavily.com" }],
  },
};

const sidebarSettings = {
  description: "面向高校课程学习的多智能体个性化学习系统",
  nav_order: [],
};

const knowledgeBases = [
  { name: "ai_textbook", display_name: "AI 课程资料", document_count: 18, is_default: true, status: "ready" },
  { name: "calculus_notes", display_name: "高等数学笔记", document_count: 12, is_default: false, status: "ready" },
];

const ragProviders = [
  { name: "llamaindex", id: "llamaindex", label: "LlamaIndex", available: true, is_default: true },
  { name: "mineru", id: "mineru", label: "MinerU PDF", available: true },
];

const knowledgeConfigs = {
  knowledge_bases: {
    ai_textbook: { name: "ai_textbook", search_mode: "hybrid", description: "人工智能导论课程资料", needs_reindex: false },
    calculus_notes: { name: "calculus_notes", search_mode: "semantic", description: "极限、导数与积分", needs_reindex: false },
  },
};

const knowledgeDetail = {
  name: "ai_textbook",
  display_name: "AI 课程资料",
  status: "ready",
  document_count: 18,
  chunks: 246,
  files: [{ name: "chapter_01_intro.pdf" }, { name: "rlhf_dpo_notes.md" }],
};

const progress = {
  status: "completed",
  stage: "completed",
  message: "索引已完成",
  percent: 100,
  current: 18,
  total: 18,
};

const linkedFolders = [
  { id: "folder-1", folder_path: "C:\\courses\\ai", status: "linked", file_count: 18 },
];

const dashboardActivities = [
  { id: "a1", type: "solve", capability: "deep_solve", title: "DPO 公式推导", summary: "完成偏好优化推导讲解", timestamp: 1_700_000_000, status: "done" },
  { id: "a2", type: "visualize", capability: "visualize", title: "神经网络结构图", summary: "生成 Mermaid 与 SVG 结果", timestamp: 1_700_000_100, status: "done" },
];

const dashboardDetail = {
  id: "a1",
  title: "DPO 公式推导",
  content: { messages: [{ role: "user", content: "讲解 DPO" }, { role: "assistant", content: "DPO 通过偏好对直接优化策略。" }] },
};

const sessions = [
  { session_id: "session-1", title: "DPO 与 RLHF 对比", message_count: 8, updated_at: 1_700_000_000 },
  { session_id: "session-2", title: "函数极限练习", message_count: 5, updated_at: 1_700_000_100 },
];

const sessionDetail = {
  id: "session-1",
  session_id: "session-1",
  title: "DPO 与 RLHF 对比",
  preferences: { capability: "deep_solve", tools: ["reason"], knowledge_bases: ["ai_textbook"], language: "zh" },
  messages: [
    { id: 1, role: "user", content: "请解释 DPO 的核心公式。", capability: "deep_solve", events: [], attachments: [] },
    { id: 2, role: "assistant", content: "DPO 将奖励函数重参数化为当前策略与参考策略的对数概率比，从而绕过单独训练奖励模型和 PPO。", capability: "deep_solve", status: "done", events: [], attachments: [] },
  ],
};

const notebooks = [
  { id: "nb-ai", name: "AI 课程复盘", description: "沉淀问答、图解和练习结果", record_count: 6 },
  { id: "nb-math", name: "高数错题盘", description: "保存极限与导数相关错题", record_count: 4 },
];

const notebookDetail = {
  id: "nb-ai",
  name: "AI 课程复盘",
  description: "沉淀问答、图解和练习结果",
  records: [
    { id: "rec-1", record_id: "rec-1", title: "DPO 推导", summary: "偏好优化核心公式", user_query: "讲解 DPO", output: "DPO 损失函数与 Bradley-Terry 模型相关。", record_type: "chat" },
  ],
};

const questionCategories = [{ id: 1, name: "函数极限" }, { id: 2, name: "AI 基础" }];
const questionEntries = [
  { id: 1, session_id: "session-2", question_id: "q1", question: "左右极限相等意味着什么？", question_type: "choice", correct_answer: "极限存在", explanation: "左右极限分别存在且相等。", bookmarked: true, is_correct: true, categories: questionCategories },
];

const memory = {
  summary: "偏好：喜欢公式推导 + 图解。薄弱点：极限定义和概率模型。",
  profile: "课程目标：掌握 AI 基础和数学推导。",
  files: [
    { filename: "summary", content: "偏好：喜欢公式推导 + 图解。" },
    { filename: "profile", content: "课程目标：掌握 AI 基础。" },
  ],
};

const plugins = {
  tools: [{ name: "knowledge_search", description: "检索课程资料" }, { name: "math_animator", description: "生成教学动画" }],
  capabilities: [{ name: "deep_solve" }, { name: "visualize" }, { name: "deep_question" }],
};

const sparkBots = [
  { bot_id: "math_bot", name: "高数助教", description: "追问、复盘和错题讲解", status: "running", auto_start: true, persona: "耐心、善于追问和归纳的学习助教。" },
];
const sparkBotRecent = [{ bot_id: "math_bot", name: "高数助教", last_message: "今天继续练习极限。", updated_at: 1_700_000_000 }];
const channelSchemas = { channels: [{ id: "web", name: "Web 对话" }] };
const souls = [{ id: "patient_tutor", name: "耐心助教", content: "以启发式追问帮助学生学习。" }];
const sparkBotFiles = [{ filename: "SKILL.md", content: "# 高数助教\n持续复盘学生薄弱点。" }];
const sparkBotHistory = [{ role: "assistant", content: "我们先从左右极限开始。" }];

const guideSessions = [{ session_id: "guide-1", title: "函数极限学习路径", status: "ready", current_index: 1 }];
const guidePages = { pages: [{ index: 0, title: "直观理解" }, { index: 1, title: "形式化定义" }, { index: 2, title: "典型题训练" }] };
const guideDetail = { session_id: "guide-1", title: "函数极限学习路径", status: "ready", current_index: 1, pages: guidePages.pages };

const coWriterHistory = [{ operation_id: "cw-1", title: "课程总结润色", selected_text: "DPO 是一种偏好优化方法。", edited_text: "DPO 是一种直接利用偏好数据优化策略的训练方法。" }];

const visionResult = {
  session_id: "vision-1",
  has_image: true,
  final_ggb_commands: [{ description: "圆 O", command: "Circle(O, 3)" }, { description: "线段 AB", command: "Segment(A, B)" }],
  ggb_script: "Circle(O, 3)\nSegment(A, B)",
  analysis_summary: { elements_count: 4, commands_count: 2 },
};

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
