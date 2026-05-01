import { expect, test } from "@playwright/test";

test("renders the redesigned learning workbench", async ({ page }) => {
  await mockReferenceApis(page);
  await page.goto("/chat");
  await expect(page.getByRole("heading", { name: "AI 学习工作台" })).toBeVisible();
  await expect(page.getByTestId("runtime-status")).toBeVisible();
  await expect(page.getByText("SparkWeave Workbench")).toBeVisible();
  await expect(page.getByTestId("chat-profile-starter")).toContainText("今天先做这一步");
  await expect(page.getByTestId("chat-profile-guide")).toBeVisible();
  await expect(page.getByRole("button", { name: /发送/ })).toBeVisible();
});

test("chat profile starter turns learner profile into one-click actions", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "profile starter smoke runs once");
  const consoleDomErrors: string[] = [];
  page.on("pageerror", (error) => consoleDomErrors.push(error.message));
  page.on("console", (message) => {
    const text = message.text();
    if (text.includes("insertBefore") || text.includes("Failed to execute")) {
      consoleDomErrors.push(text);
    }
  });

  await mockReferenceApis(page);
  await installMockWebSocket(page, { resultOnlyContent: "已生成一组练习。" });
  await page.goto("/chat");

  await expect(page.getByTestId("chat-profile-starter")).toContainText("梯度下降的直观理解");
  const guideHref = await page.getByTestId("chat-profile-guide").getAttribute("href");
  expect(decodeURIComponent(guideHref ?? "")).toContain("梯度下降的直观理解");
  expect(decodeURIComponent(guideHref ?? "")).toContain("source_label=概念边界不清");
  expect(guideHref).toContain("estimated_minutes=10");

  await page.getByTestId("chat-profile-action-practice").click();
  await expect
    .poll(() =>
      page.evaluate(() => {
        const messages = (window as typeof window & { __sparkWeaveWsMessages?: Array<Record<string, unknown>> }).__sparkWeaveWsMessages ?? [];
        return messages[messages.length - 1] ?? {};
      }),
    )
    .toEqual(
      expect.objectContaining({
        capability: "deep_question",
        config: expect.objectContaining({ question_type: "mixed", num_questions: 5, topic: "梯度下降的直观理解" }),
      }),
    );
  expect(consoleDomErrors).toEqual([]);
});

test("learner profile overview confirms current diagnosis", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "profile calibration smoke runs once");
  const reference = await mockReferenceApis(page);

  await page.goto("/memory");
  await page.getByTestId("learner-profile-confirm-overview").click();

  await expect.poll(() => reference.calibrationPayload).toEqual(
    expect.objectContaining({
      action: "confirm",
      claim_type: "profile_overview",
      source_id: "profile_overview",
    }),
  );
  await expect(page.getByText("已确认。系统会更放心地按这个方向安排学习。")).toBeVisible();
});

test("routes to core workbench areas", async ({ page }) => {
  await page.goto("/knowledge");
  await expect(page.getByRole("heading", { name: "知识库中枢" })).toBeVisible();
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "连接与服务设置" })).toBeVisible();
});

test("inspector opens dashboard activity details", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "inspector activity detail smoke runs once");
  await mockReferenceApis(page);
  await page.route("**/api/v1/dashboard/recent?**", (route) =>
    route.fulfill({
      json: [
        {
          id: "activity-1",
          type: "solve",
          capability: "deep_solve",
          title: "Derivative review",
          timestamp: 1_700_000_300,
          summary: "A recent calculus explanation.",
          message_count: 2,
          status: "idle",
        },
      ],
    }),
  );
  await page.route("**/api/v1/dashboard/activity-1", (route) =>
    route.fulfill({
      json: {
        id: "activity-1",
        type: "solve",
        capability: "deep_solve",
        title: "Derivative review",
        timestamp: 1_700_000_300,
        content: {
          status: "idle",
          summary: "A recent calculus explanation.",
          messages: [
            { role: "user", content: "Explain derivatives" },
            { role: "assistant", content: "The derivative is a rate of change." },
          ],
        },
      },
    }),
  );

  await page.goto("/chat");
  await page.getByTestId("open-inspector").click();
  await expect(page.getByTestId("inspector-drawer")).toBeVisible();
  await expect(page.getByText("Derivative review")).toBeVisible();
  await page.getByTestId("dashboard-activity-activity-1").click();
  await expect(page.getByTestId("dashboard-activity-detail")).toContainText("Explain derivatives");
  await expect(page.getByTestId("dashboard-activity-detail")).toContainText("The derivative is a rate of change.");
});

test("chat exposes capability-specific settings", async ({ page }, testInfo) => {
  await page.goto("/chat");
  await page.getByRole("button", { name: "上下文" }).click();
  await expect(page.getByRole("heading", { name: "任务快照" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "能力参数" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "引用上下文" })).toBeVisible();
  const visibleControl = (name: string) =>
    testInfo.project.name === "mobile" ? page.getByLabel(name).last() : page.getByLabel(name).first();
  await page.getByRole("button", { name: /题目生成/ }).click();
  await expect(visibleControl("题目数量")).toBeVisible();
  await page.getByRole("button", { name: /知识可视化/ }).click();
  await expect(visibleControl("渲染模式")).toBeVisible();
  await page.getByRole("button", { name: /数学动画/ }).click();
  await expect(visibleControl("风格提示")).toBeVisible();
});

test("exposes migrated phase-two work areas", async ({ page }) => {
  await mockReferenceApis(page);

  await page.goto("/knowledge");
  await expect(page.getByRole("heading", { name: "知识库中枢" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "我的资料库" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "追加资料" })).toBeVisible();

  await page.goto("/notebook");
  await expect(page.getByRole("heading", { name: "学习笔记" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "我的笔记本" })).toBeVisible();
  await expect(page.getByRole("button", { name: "新建笔记本" })).toBeVisible();

  await page.goto("/question");
  await expect(page.getByRole("heading", { name: "题目工坊" })).toBeVisible();
  await expect(page.getByRole("button", { name: /生成题目/ })).toBeVisible();

  await page.goto("/vision");
  await expect(page.getByRole("heading", { name: "图像解题" })).toBeVisible();
  await expect(page.getByRole("button", { name: /快速解析/ })).toBeVisible();

  await page.goto("/memory");
  await expect(page.getByRole("heading", { name: "系统现在怎么理解你" })).toBeVisible();
  await expect(page.getByTestId("learner-profile-overview")).toContainText("现在只做这一件事");
  await expect(page.getByTestId("learner-profile-primary-action")).toHaveAttribute("href", /\/guide\?/);

  await page.goto("/playground");
  await expect(page.getByRole("heading", { name: "能力实验室" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "注册清单" })).toBeVisible();

  await page.goto("/co-writer");
  await expect(page.getByRole("heading", { name: "编辑请求" })).toBeVisible();
  await expect(page.getByRole("button", { name: /生成修改/ })).toBeVisible();

  await page.goto("/guide");
  await expect(page.getByText("懒人导学")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1, name: "先创建一条路线" })).toBeVisible();
  await expect(page.getByRole("button", { name: "帮我安排学习" })).toBeVisible();

  await page.goto("/agents");
  await expect(page.getByRole("heading", { name: "运行时智能体矩阵" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "创建助教" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Bot 对话" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Soul 模板库" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "渠道配置" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "工作区文件" })).toBeVisible();

  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "连接与服务设置" })).toBeVisible();
  await page.getByTestId("settings-diagnostics-toggle").click();
  await expect(page.getByRole("heading", { name: "服务连通性测试" })).toBeVisible();
});

test("memory workbench saves refreshes and clears files", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "memory mutation smoke runs once");
  const memory = await mockMemoryApis(page);
  page.on("dialog", (dialog) => void dialog.accept());

  await page.goto("/memory");
  await page.getByTestId("learner-profile-tab-memory").click();
  await expect(page.getByTestId("memory-editor")).toHaveValue(/Initial summary/);

  await page.getByTestId("memory-editor").fill("## Updated summary\n- Saved from the redesigned workbench");
  await page.getByTestId("memory-save").click();
  await expect.poll(() => memory.savePayload).toEqual({
    file: "summary",
    content: "## Updated summary\n- Saved from the redesigned workbench",
  });

  await page.getByTestId("memory-refresh").click();
  await expect.poll(() => memory.refreshPayload).toEqual({
    session_id: null,
    language: "zh",
  });
  await expect(page.getByTestId("memory-editor")).toHaveValue(/Refreshed summary/);

  await page.getByTestId("memory-clear").click();
  await expect.poll(() => memory.clearPayload).toEqual({ file: "summary" });
  await expect(page.getByTestId("memory-editor")).toHaveValue("");
});

test("playground streams tool and capability executions", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "playground streaming smoke runs once");
  const playground = await mockPlaygroundApis(page);

  await page.goto("/playground");
  await page.getByTestId("playground-registry-mock_tool").click();
  await page.getByTestId("playground-tool-params").fill('{"query":"limits"}');
  await page.getByTestId("playground-tool-run").click();
  await expect.poll(() => playground.toolPayload).toEqual({ params: { query: "limits" } });
  await page.getByTestId("playground-logs-toggle").click();
  await expect(page.getByTestId("playground-logs")).toContainText("tool log received");
  await expect(page.getByTestId("playground-result")).toContainText("tool result");

  await page.getByTestId("playground-tool-run-sync").click();
  await expect.poll(() => playground.syncToolPayload).toEqual({ params: { query: "limits" } });
  await expect(page.getByTestId("playground-logs")).toContainText("sync: /api/v1/plugins/tools/mock_tool/execute");
  await expect(page.getByTestId("playground-result")).toContainText("sync tool result");

  await page.getByTestId("playground-mode-capability").click();
  await page.getByTestId("playground-tool-toggle-mock_tool").click();
  await page.getByTestId("playground-kb-toggle-calc_kb").click();
  await page.getByTestId("playground-capability-content").fill("Explain derivatives");
  await page.getByTestId("playground-capability-run").click();
  await expect.poll(() => playground.capabilityPayload).toEqual(
    expect.objectContaining({
      content: "Explain derivatives",
      tools: ["mock_tool"],
      knowledge_bases: ["calc_kb"],
      language: "zh",
      config: {},
      attachments: [],
    }),
  );
  await expect(page.getByTestId("playground-logs")).toContainText("stream");
  await expect(page.getByTestId("playground-result")).toContainText("capability done");
});

test("knowledge creation listens to named SSE task logs", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "knowledge stream smoke runs once");
  const knowledge = await mockKnowledgeApis(page);
  await installMockKnowledgeProgressWebSocket(page);

  await page.goto("/knowledge");
  await page.getByRole("button", { name: "新建", exact: true }).click();
  await page.getByRole("textbox", { name: "资料库名称" }).fill("calculus_mock");
  await page.getByTestId("knowledge-create-files").first().setInputFiles({
    name: "limits.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("# Limits\nUse notebook context."),
  });
  await page.getByRole("button", { name: /创建并索引/ }).click();

  await expect(page.getByTestId("knowledge-task-logs")).toContainText("Saved 1 file, preparing index");
  await expect(page.getByTestId("knowledge-task-logs")).toContainText("complete: Knowledge base created");
  await expect(page.getByTestId("knowledge-task-logs")).toContainText("ws: parsing 55% WS parsing files");
  await expect(page.getByTestId("knowledge-task-logs")).toContainText("进度更新：heartbeat");
  await expect(page.getByTestId("knowledge-task-logs")).not.toContainText("debug");
  await expect(page.getByTestId("knowledge-task-logs")).toContainText("ws: completed 100% WS index complete");
  await expect.poll(() => knowledge.createBody?.includes('name="name"\r\n\r\ncalculus_mock')).toBe(true);
  const wsUrls = await page.evaluate(() => (window as typeof window & { __knowledgeWsUrls?: string[] }).__knowledgeWsUrls ?? []);
  expect(wsUrls.some((url) => url.includes("/api/v1/knowledge/calculus_mock/progress/ws"))).toBe(true);

  await expect(page.getByRole("heading", { name: "检索设置" })).toBeVisible();
  await page.getByLabel("模式").first().selectOption("semantic");
  await page.getByLabel("说明").first().fill("极限与连续专题资料");
  await page.getByRole("button", { name: /^保存$/ }).first().click();
  await expect.poll(() => knowledge.configBody?.includes('"search_mode":"semantic"')).toBe(true);
  await expect.poll(() => knowledge.configBody?.includes('"description":"极限与连续专题资料"')).toBe(true);
});

test("knowledge management covers upload default folders and deletion", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "knowledge management smoke runs once");
  const knowledge = await mockKnowledgeManagementApis(page);
  page.on("dialog", (dialog) => void dialog.accept());

  await page.goto("/knowledge");
  await expect(page.getByRole("heading", { name: "资料库" })).toBeVisible();
  await expect(page.getByText("/api/v1/knowledge/configs").first()).toBeVisible();
  await expect(page.getByTestId("knowledge-detail-panel")).toContainText("/api/v1/knowledge/calculus_mock");
  await page.getByRole("button", { name: "geometry_mock 就绪 选择" }).click();
  await page.getByTestId("knowledge-active-set-default").click();
  await expect.poll(() => knowledge.defaultKb).toBe("geometry_mock");
  await expect(page.getByTestId("knowledge-detail-panel")).toContainText("/api/v1/knowledge/geometry_mock");
  await expect(page.getByTestId("knowledge-detail-panel")).toContainText("Geometry vector store ready");
  await expect(page.getByTestId("knowledge-active-summary-panel")).toContainText("索引摘要");
  await expect(page.getByTestId("knowledge-active-summary-panel")).toContainText("triangles");
  await expect(page.getByTestId("knowledge-active-summary-panel")).not.toContainText("{");

  await page.getByTestId("knowledge-upload-files").first().setInputFiles({
    name: "triangles.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("# Triangles\nSimilarity and area."),
  });
  await page.getByRole("button", { name: /上传并索引/ }).click();
  await expect.poll(() => knowledge.uploadTarget).toBe("geometry_mock");
  await expect.poll(() => knowledge.uploadBody?.includes('filename="triangles.md"')).toBe(true);
  await expect(page.getByTestId("knowledge-progress-details")).toContainText("完成");
  await expect(page.getByTestId("knowledge-task-logs")).toContainText("完成：Upload complete");
  await expect(page.getByTestId("knowledge-task-logs")).not.toContainText("Progress cleared for geometry_mock");

  await page.getByTestId("knowledge-active-delete").click();
  await expect.poll(() => knowledge.deletedKb).toBe("geometry_mock");
});

test("legacy chat links restore sessions and capability aliases", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "legacy routing smoke runs once");
  await mockReferenceApis(page);
  await installMockWebSocket(page);
  await page.route("**/api/v1/sessions/session-legacy", (route) =>
    route.fulfill({
      json: {
        id: "session-legacy",
        session_id: "session-legacy",
        title: "Legacy session",
        created_at: 1_700_000_000,
        updated_at: 1_700_000_400,
        message_count: 2,
        active_turn_id: null,
        preferences: { capability: "deep_solve", tools: ["reason"], knowledge_bases: [], language: "zh" },
        messages: [
          {
            id: 1,
            role: "user",
            content: "Legacy question",
            capability: "deep_solve",
            events: [],
            attachments: [],
            created_at: 1_700_000_100,
          },
          {
            id: 2,
            role: "assistant",
            content: "Loaded assistant answer",
            capability: "deep_solve",
            events: [],
            attachments: [],
            created_at: 1_700_000_200,
          },
        ],
      },
    }),
  );

  await page.goto("/chat/session-legacy");
  await expect(page.getByText("Loaded assistant answer")).toBeVisible({ timeout: 15000 });

  await page.goto("/?session=session-legacy");
  await expect.poll(() => page.evaluate(() => window.location.pathname), { timeout: 15000 }).toContain("/chat/session-legacy");
  await expect(page.getByText("Loaded assistant answer")).toBeVisible({ timeout: 15000 });

  await page.goto("/chat?capability=deep_question");
  await expect.poll(() => page.evaluate(() => `${window.location.pathname}${window.location.search}`)).toContain(
    "/chat?capability=deep_question",
  );
  await page.locator("textarea").first().fill("Generate three questions");
  await page.getByRole("button", { name: /发送/ }).click();

  await expect
    .poll(async () =>
      page.evaluate(() => {
        const state = window as typeof window & { __sparkWeaveWsMessages?: Array<Record<string, unknown>> };
        return state.__sparkWeaveWsMessages?.find((message) => message.type === "start_turn") ?? null;
      }),
    )
    .toEqual(expect.objectContaining({ capability: "deep_question" }));
});

test("chat session panel loads renames and deletes sessions", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "chat session management smoke runs once");
  const reference = await mockReferenceApis(page);
  page.on("dialog", (dialog) => void dialog.accept());

  await page.goto("/chat");
  await expect(page.getByTestId("chat-history-sidebar")).toHaveAttribute("data-collapsed", "false");
  await page.getByTestId("chat-sidebar-history-collapse").click();
  await expect(page.getByTestId("chat-history-sidebar")).toHaveAttribute("data-collapsed", "true");
  await expect(page.getByTestId("chat-sidebar-session-card-session-old-a")).toHaveCount(0);
  await page.getByTestId("chat-history-expand").click();
  await expect(page.getByTestId("chat-history-sidebar")).toHaveAttribute("data-collapsed", "false");
  await expect(page.getByTestId("chat-sidebar-session-card-session-old-a")).toBeVisible();
  await page.getByTestId("chat-sidebar-session-load-session-old-a").click();
  await expect(page.getByText("Loaded assistant answer")).toBeVisible();

  await page.getByTestId("chat-sidebar-session-rename-session-old-a").click();
  await page.getByTestId("chat-sidebar-session-title-session-old-a").fill("Renamed learning session");
  await page.getByTestId("chat-sidebar-session-rename-save-session-old-a").click();
  await expect.poll(() => reference.sessionRenamePayload).toEqual({
    sessionId: "session-old-a",
    title: "Renamed learning session",
  });

  await page.getByTestId("chat-sidebar-session-delete-session-old-a").click();
  await expect.poll(() => reference.sessionDeleteTarget).toBe("session-old-a");
});

test("question lab streams generated questions and saves a notebook record", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "question lab websocket smoke runs once");
  const reference = await mockReferenceApis(page);
  await installMockQuestionWebSocket(page);

  await page.goto("/question");
  await expect(page.getByRole("heading", { name: "题目工坊" })).toBeVisible();
  await page.getByLabel("知识点或出题要求").fill("函数极限");
  await page.getByRole("button", { name: /生成题目/ }).click();

  await expect
    .poll(async () =>
      page.evaluate(() => {
        const state = window as typeof window & { __questionLabWsMessages?: Array<Record<string, unknown>> };
        return state.__questionLabWsMessages?.[0] ?? null;
      }),
    )
    .toEqual(
      expect.objectContaining({
        count: 3,
        requirement: expect.objectContaining({ knowledge_point: "函数极限" }),
      }),
    );

  await expect(page.getByTestId("question-lab-events")).toContainText("生成模板");
  await expect(page.getByText("函数极限存在的充分条件是什么？")).toBeVisible();
  await page.getByRole("button", { name: /A\./ }).click();
  await page.getByRole("button", { name: /提交答案/ }).click();
  await expect(page.getByText(/参考答案：A/)).toBeVisible();

  await page.getByTestId("question-lab-save").click();
  await expect.poll(() => reference.savedPayload).toEqual(
    expect.objectContaining({
      record_type: "question",
      title: "题目生成：函数极限",
      output: expect.stringContaining("函数极限存在的充分条件是什么？"),
    }),
  );
});

test("question lab streams mimic questions from a parsed paper path", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "question lab mimic websocket smoke runs once");
  const reference = await mockReferenceApis(page);
  await installMockQuestionWebSocket(page);

  await page.goto("/question");
  await page.getByTestId("question-mode-mimic").click();
  await page.getByTestId("question-mimic-paper-path").fill("mimic_papers/exam_2024");
  await page.getByTestId("question-generate-mimic").click();

  await expect
    .poll(async () =>
      page.evaluate(() => {
        const state = window as typeof window & {
          __questionLabWsMessages?: Array<Record<string, unknown>>;
          __questionLabWsUrls?: string[];
        };
        return {
          payload: state.__questionLabWsMessages?.[0] ?? null,
          urls: state.__questionLabWsUrls ?? [],
        };
      }),
    )
    .toEqual(
      expect.objectContaining({
        payload: expect.objectContaining({
          mode: "parsed",
          paper_path: "mimic_papers/exam_2024",
          max_questions: 3,
        }),
        urls: expect.arrayContaining([expect.stringContaining("/question/mimic")]),
      }),
    );

  await expect(page.getByTestId("question-lab-events")).toContainText("mimic template ready");
  await expect(page.getByText("Mimic problem: which step preserves the same reasoning pattern?")).toBeVisible();

  await page.getByTestId("question-lab-save").click();
  await expect.poll(() => reference.savedPayload).toEqual(
    expect.objectContaining({
      record_type: "question",
      user_query: "mimic_papers/exam_2024",
      output: expect.stringContaining("Mimic problem: which step preserves the same reasoning pattern?"),
      metadata: expect.objectContaining({ mode: "mimic" }),
    }),
  );
});

test("vision lab analyzes images streams tutor guidance and saves output", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "vision websocket smoke runs once");
  const reference = await mockReferenceApis(page);
  const vision = await mockVisionApis(page);
  await installMockVisionWebSocket(page);

  await page.goto("/vision");
  await expect(page.getByRole("heading", { name: "图像解题" })).toBeVisible();
  await page.getByLabel("图片 URL").fill("https://example.com/problem.png");
  await page.getByRole("button", { name: /快速解析/ }).click();
  await expect.poll(() => vision.analyzePayload?.image_url).toBe("https://example.com/problem.png");
  await expect(page.getByTestId("vision-ggb-script")).toContainText("Circle");

  await page.getByRole("button", { name: /实时解题/ }).click();
  await expect
    .poll(async () =>
      page.evaluate(() => {
        const state = window as typeof window & { __visionWsMessages?: Array<Record<string, unknown>> };
        return state.__visionWsMessages?.[0] ?? null;
      }),
    )
    .toEqual(expect.objectContaining({ image_url: "https://example.com/problem.png" }));
  await expect(page.getByTestId("vision-events")).toContainText("bbox_complete");
  await expect(page.getByTestId("vision-answer")).toContainText("先还原几何关系");
  await expect(page.getByTestId("vision-ggb-script")).toContainText("Segment");

  await page.getByTestId("vision-save").click();
  await expect.poll(() => reference.savedPayload).toEqual(
    expect.objectContaining({
      record_type: "solve",
      title: "图像题解析",
      output: expect.stringContaining("GeoGebra 指令"),
    }),
  );
});

test("vision lab uploads local images as base64 input", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "vision local image smoke runs once");
  await mockReferenceApis(page);
  const vision = await mockVisionApis(page);

  await page.goto("/vision");
  await page.getByTestId("vision-question").fill("Analyze this uploaded sketch.");
  await page.getByTestId("vision-file-input").setInputFiles({
    name: "sketch.png",
    mimeType: "image/png",
    buffer: Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/axj4b8AAAAASUVORK5CYII=",
      "base64",
    ),
  });
  await expect(page.getByTestId("vision-image-preview")).toBeVisible();
  await page.getByTestId("vision-quick-analyze").click();

  await expect.poll(() => vision.analyzePayload).toEqual(
    expect.objectContaining({
      question: "Analyze this uploaded sketch.",
      image_url: null,
      image_base64: expect.stringContaining("iVBORw0KGgo"),
    }),
  );
  await expect(page.getByTestId("vision-ggb-script")).toContainText("Circle");
});

test("legacy sparkbot chat links select the target bot", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "legacy sparkbot route smoke runs once");
  const sparkbot = await mockSparkBotApis(page);

  await page.goto("/agents/math_bot/chat");
  await expect.poll(() => sparkbot.recentLimit).toBe(5);
  await expect(page.getByTestId("sparkbot-recent-panel")).toContainText("Last geometry reminder");
  await expect(page.getByText(/math_bot/).first()).toBeVisible();
  await expect(page.getByText(/math_bot.*运行中/).first()).toBeVisible();
  await page.getByTestId("agent-capabilities-toggle").click();
  await expect(page.getByTestId("agent-config-detail")).toContainText("Problem Solved");
  await page.getByTestId("agent-config-inspect-research").click();
  await expect.poll(() => sparkbot.agentDetailTarget).toBe("research");
  await expect(page.getByTestId("agent-config-detail")).toContainText("Research Report");
  await page.getByTestId("sparkbot-soul-toggle").click();
  await page.getByTestId("sparkbot-soul-socratic").click();
  await expect.poll(() => sparkbot.soulDetailTarget).toBe("socratic");
  await expect(page.getByTestId("sparkbot-soul-detail-source")).toContainText("/api/v1/sparkbot/souls/socratic");
  await expect(page.getByTestId("sparkbot-soul-content")).toHaveValue(/guiding question/);
  await page.getByTestId("sparkbot-recent-writing_bot").click();
  await expect(page.getByText(/writing_bot.*未运行/).first()).toBeVisible();
});

test("legacy utility sparkbot and natural aliases resolve to redesigned routes", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "alias routing smoke runs once");
  await mockReferenceApis(page);
  await mockNotebookDeepLinkApis(page);
  await mockSparkBotApis(page);

  const pathAndSearch = () => page.evaluate(() => `${window.location.pathname}${window.location.search}`);

  await page.goto("/utility/notebook");
  await expect.poll(pathAndSearch).toBe("/notebook");

  await page.goto("/sparkbot");
  await expect.poll(pathAndSearch).toBe("/agents");

  await page.goto("/sparkbot/math_bot/chat");
  await expect.poll(pathAndSearch).toBe("/agents/math_bot/chat");
  await expect(page.getByText(/math_bot/).first()).toBeVisible();

  await page.goto("/sparkbot");
  await expect.poll(pathAndSearch).toBe("/agents");

  await page.goto("/sparkbot/math_bot/chat");
  await expect.poll(pathAndSearch).toBe("/agents/math_bot/chat");
  await expect(page.getByText(/math_bot/).first()).toBeVisible();

  await page.goto("/math-animator");
  await expect.poll(pathAndSearch).toBe("/chat?capability=math_animator");

  await page.goto("/cowriter");
  await expect.poll(pathAndSearch).toBe("/co-writer");
});

test("sparkbot history renders paired backend exchanges", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "sparkbot history smoke runs once");
  await mockSparkBotApis(page);

  await page.goto("/agents/math_bot/chat");
  await expect(page.getByTestId("sparkbot-history-piece-0-0")).toContainText("How should I review limits?");
  await expect(page.getByTestId("sparkbot-history-piece-0-1")).toContainText("Start from the definition");
  await expect(page.getByTestId("sparkbot-history-piece-1-0")).toContainText("Remember to ask one guiding question");
  await expect(page.getByTestId("sparkbot-history-item-0")).toContainText("web");

  await page.getByTestId("sparkbot-recent-writing_bot").click();
  await expect(page.getByTestId("sparkbot-history-piece-0-0")).toContainText("Draft outline feedback is ready.");
});

test("sparkbot soul library creates updates and deletes templates", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "sparkbot soul CRUD smoke runs once");
  const sparkbot = await mockSparkBotApis(page);

  await page.goto("/agents/math_bot/chat");
  await page.getByTestId("sparkbot-soul-toggle").click();
  await page.getByTestId("sparkbot-soul-socratic").click();
  await expect.poll(() => sparkbot.soulDetailTarget).toBe("socratic");
  await page.getByTestId("sparkbot-soul-name").fill("Socratic Coach Plus");
  await page.getByTestId("sparkbot-soul-content").fill("Ask one question, wait, then verify the learner's reasoning.");
  await page.getByTestId("sparkbot-soul-save").click();
  await expect.poll(() => sparkbot.soulUpdatePayload).toEqual({
    soulId: "socratic",
    payload: {
      name: "Socratic Coach Plus",
      content: "Ask one question, wait, then verify the learner's reasoning.",
    },
  });

  await page.getByTestId("sparkbot-soul-new").click();
  await page.getByTestId("sparkbot-soul-id").fill("exam-coach");
  await page.getByTestId("sparkbot-soul-name").fill("Exam Coach");
  await page.getByTestId("sparkbot-soul-content").fill("Run timed exam drills and explain scoring rubrics.");
  await page.getByTestId("sparkbot-soul-save").click();
  await expect.poll(() => sparkbot.soulCreatePayload).toEqual({
    id: "exam-coach",
    name: "Exam Coach",
    content: "Run timed exam drills and explain scoring rubrics.",
  });
  await expect(page.getByTestId("sparkbot-soul-exam-coach")).toBeVisible();

  await page.getByTestId("sparkbot-soul-socratic").click();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByTestId("sparkbot-soul-delete").click();
  await expect.poll(() => sparkbot.soulDeleteTarget).toBe("socratic");
});

test("sparkbot chat streams websocket replies", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "sparkbot websocket smoke runs once");
  await mockSparkBotApis(page);
  await installMockSparkBotWebSocket(page);

  await page.goto("/agents/math_bot/chat");
  const botChat = page.locator("section", { has: page.getByRole("heading", { name: "Bot 对话" }) });
  await botChat.getByPlaceholder("向 SparkBot 提问...").fill("解释导数");
  await botChat.getByRole("button", { name: "发送" }).click();

  await expect(botChat.getByText("思考：Planning derivative hint")).toBeVisible();
  await expect(botChat.getByText("导数表示瞬时变化率。斜率是 2。")).toBeVisible();
  await expect(botChat.getByText("记得复盘切线斜率。")).toBeVisible();
  await expect.poll(() =>
    page.evaluate(() => {
      const state = window as typeof window & { __deepSparkBotWsMessages?: Array<Record<string, unknown>> };
      return state.__deepSparkBotWsMessages?.[0] ?? null;
    }),
  ).toEqual(expect.objectContaining({ content: "解释导数", chat_id: "web" }));
});

test("sparkbot channel editor saves schema driven config", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "sparkbot channel config smoke runs once");
  const sparkbot = await mockSparkBotApis(page);

  await page.goto("/agents/math_bot/chat");
  await page.getByTestId("bot-profile-toggle").click();
  await page.getByTestId("bot-profile-name").fill("Math Bot Coach");
  await page.getByTestId("bot-profile-description").fill("Updated profile");
  await page.getByTestId("bot-profile-model").fill("gpt-math");
  await page.getByTestId("bot-profile-persona").fill("Socratic math coach");
  await page.getByTestId("bot-profile-auto-start").click();
  await page.getByTestId("bot-profile-save").click();
  await expect.poll(() => sparkbot.updatePayload).toEqual(
    expect.objectContaining({
      name: "Math Bot Coach",
      description: "Updated profile",
      model: "gpt-math",
      persona: "Socratic math coach",
      auto_start: false,
    }),
  );
  await expect(page.getByText("资料已保存。")).toBeVisible();

  await page.getByTestId("sparkbot-channel-toggle").click();
  const globalChannel = page.getByTestId("sparkbot-global-channel-editor");
  await globalChannel.getByTestId("channel-field-send_tool_hints").click();
  await globalChannel.getByTestId("channel-field-transcription_api_key").fill("transcription-secret");
  await globalChannel.getByRole("button", { name: "保存全局" }).click();
  await expect.poll(() => sparkbot.updatePayload).toEqual(
    expect.objectContaining({
      channels: expect.objectContaining({
        send_progress: true,
        send_tool_hints: true,
        transcription_api_key: "transcription-secret",
        web: expect.objectContaining({ welcome_text: "Welcome" }),
      }),
    }),
  );

  await page.getByTestId("bot-tools-toggle").click();
  await page.getByTestId("bot-tools-json").fill(
    JSON.stringify(
      {
        exec: { timeout: 90, pathAppend: "custom-bin" },
        web: {
          proxy: "http://127.0.0.1:7890",
          fetchMaxChars: 1200,
          search: { provider: "jina", apiKey: "search-secret", baseUrl: "", maxResults: 3 },
        },
        restrictToWorkspace: false,
        mcpServers: { local: { command: "fake-mcp", enabledTools: ["lookup"] } },
      },
      null,
      2,
    ),
  );
  await page.getByTestId("bot-tools-save").click();
  await expect.poll(() => sparkbot.updatePayload).toEqual(
    expect.objectContaining({
      tools: expect.objectContaining({
        exec: expect.objectContaining({ timeout: 90, pathAppend: "custom-bin" }),
        restrictToWorkspace: false,
        mcpServers: expect.objectContaining({ local: expect.objectContaining({ command: "fake-mcp" }) }),
      }),
    }),
  );
  await expect(page.getByText("工具配置已保存。")).toBeVisible();

  await page.getByTestId("bot-runtime-toggle").click();
  await page.getByTestId("bot-agent-json").fill(
    JSON.stringify(
      {
        maxToolIterations: 8,
        toolCallLimit: 2,
        maxTokens: 4096,
        contextWindowTokens: 32000,
        temperature: 0.25,
        reasoningEffort: "medium",
        teamMaxWorkers: 3,
        teamWorkerMaxIterations: 7,
      },
      null,
      2,
    ),
  );
  await page.getByTestId("bot-heartbeat-json").fill(JSON.stringify({ enabled: false, intervalS: 120 }, null, 2));
  await page.getByTestId("bot-runtime-save").click();
  await expect.poll(() => sparkbot.updatePayload).toEqual(
    expect.objectContaining({
      agent: expect.objectContaining({
        maxToolIterations: 8,
        toolCallLimit: 2,
        reasoningEffort: "medium",
      }),
      heartbeat: expect.objectContaining({ enabled: false, intervalS: 120 }),
    }),
  );
  await expect(page.getByText("运行时已保存。")).toBeVisible();

  await expect(page.getByRole("heading", { name: "渠道配置" })).toBeVisible();
  await page.getByLabel("Welcome text").fill("Hello from web");
  await page.getByLabel("Rate limit").fill("9");
  await page.getByRole("button", { name: "保存渠道" }).click();

  await expect.poll(() => sparkbot.updatePayload).toEqual(
    expect.objectContaining({
      channels: expect.objectContaining({
        web: expect.objectContaining({
          enabled: true,
          welcome_text: "Hello from web",
          rate_limit: 9,
        }),
      }),
    }),
  );
});

test("sparkbot workspace files create and save through backend", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "sparkbot file editor smoke runs once");
  const sparkbot = await mockSparkBotApis(page);

  await page.goto("/agents/math_bot/chat");
  await page.getByTestId("sparkbot-files-toggle").click();
  await page.getByTestId("sparkbot-file-SOUL.md").click();
  await expect(page.getByTestId("sparkbot-file-content")).toHaveValue(/# Math Bot/);
  await page.getByTestId("sparkbot-file-content").fill("# Math Bot\n\nUpdated prompt");
  await page.getByTestId("sparkbot-file-save").click();
  await expect.poll(() => sparkbot.fileWritePayload).toEqual({
    botId: "math_bot",
    filename: "SOUL.md",
    content: "# Math Bot\n\nUpdated prompt",
  });

  await page.getByTestId("sparkbot-new-file-name").fill("NOTES.md");
  await page.getByTestId("sparkbot-new-file-create").click();
  await expect.poll(() => sparkbot.fileWritePayload).toEqual({
    botId: "math_bot",
    filename: "NOTES.md",
    content: "",
  });
  await expect(page.getByTestId("sparkbot-file-NOTES.md")).toBeVisible();
  await expect(page.getByTestId("sparkbot-file-content")).toHaveValue("");
});

test("sparkbot lifecycle buttons call start stop and destroy endpoints", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "sparkbot lifecycle smoke runs once");
  const sparkbot = await mockSparkBotApis(page);

  await page.goto("/agents/math_bot/chat");
  await page.getByTestId("sparkbot-start-writing_bot").click();
  await expect.poll(() => sparkbot.startPayload).toEqual(
    expect.objectContaining({
      bot_id: "writing_bot",
      auto_start: true,
    }),
  );

  await page.getByTestId("sparkbot-stop-math_bot").click();
  await expect.poll(() => sparkbot.stopTarget).toBe("math_bot");

  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByTestId("sparkbot-destroy-writing_bot").click();
  await expect.poll(() => sparkbot.destroyTarget).toBe("writing_bot");
});

test("legacy guide query links load the target session", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "legacy guide route smoke runs once");
  await mockGuideApis(page);
  const guideRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/v1/guide/session/guide-legacy")) {
      guideRequests.push(request.url());
    }
  });

  await page.goto("/guide?session=guide-legacy");
  await expect(page.getByText("healthy").first()).toBeVisible();
  await expect(page.getByText("/api/v1/guide/health").first()).toBeVisible();
  await expect(page.getByText("Legacy Guide Session").first()).toBeVisible();
  await expect(page.getByText("Legacy Guide Point").first()).toBeVisible();
  await expect.poll(() => guideRequests.some((url) => url.endsWith("/api/v1/guide/session/guide-legacy"))).toBe(true);
  await expect.poll(() => guideRequests.some((url) => url.endsWith("/api/v1/guide/session/guide-legacy/html"))).toBe(true);
  await expect.poll(() => guideRequests.some((url) => url.endsWith("/api/v1/guide/session/guide-legacy/pages"))).toBe(true);
});

test("guide saves the active session as a notebook record", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "guide notebook save smoke runs once");
  const guide = await mockGuideApis(page);

  await page.goto("/guide?session=guide-legacy");
  await page.getByTestId("guide-events-toggle").click();
  await page.locator("select").last().selectOption("nb1");
  await page.getByRole("button", { name: "保存" }).click();
  await expect.poll(() => guide.savedPayload).toEqual(
    expect.objectContaining({
      notebook_ids: ["nb1"],
      record_type: "guided_learning",
      output: expect.stringContaining("Legacy Guide Page"),
      metadata: expect.objectContaining({
        session_id: "guide-legacy",
        asset_kind: "导学页面 · HTML",
        output_type: "html",
        guide: expect.objectContaining({ title: "Legacy Guide Session", session_id: "guide-legacy" }),
      }),
    }),
  );
});

test("guide creates sessions with selected notebook references", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "guide notebook reference smoke runs once");
  const guide = await mockGuideApis(page);

  await page.goto("/guide");
  await page.getByTestId("guide-reference-notebook").selectOption("nb1");
  await page.getByTestId("guide-reference-record-rec-limit").click();
  await page.locator("textarea").first().fill("Guide from notebook context");
  await page.locator("form").first().locator('button[type="submit"]').click();

  await expect.poll(() => guide.createPayload).toEqual(
    expect.objectContaining({
      user_input: "Guide from notebook context",
      notebook_references: [{ notebook_id: "nb1", record_ids: ["rec-limit"] }],
    }),
  );
});

test("guide live controls use websocket channel", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "guide websocket smoke runs once");
  await mockGuideApis(page);
  await installMockGuideWebSocket(page);

  await page.goto("/guide?session=guide-legacy");
  await page.getByTestId("guide-events-toggle").click();
  const events = page.getByTestId("guide-ws-events");
  await expect(events.getByText("WebSocket 实时")).toBeVisible();
  await expect(events.getByText("ws: session_info · ready · Legacy Guide Session")).toBeVisible();

  await page.getByRole("button", { name: /^开始$/ }).click();
  await expect(events.getByText("send: 开始导学")).toBeVisible();
  await expect(events.getByText("ws: start_result · running · WS Started")).toBeVisible();
  const messages = await page.evaluate(() => (window as typeof window & { __guideWsMessages?: Array<Record<string, unknown>> }).__guideWsMessages ?? []);
  expect(messages.some((message) => message.type === "start")).toBe(true);
});

test("guide controls fall back to REST endpoints when websocket is unavailable", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "guide REST fallback smoke runs once");
  const guide = await mockGuideApis(page);
  await installUnavailableGuideWebSocket(page);

  await page.goto("/guide?session=guide-legacy");
  await page.getByTestId("guide-events-toggle").click();
  await page.getByTestId("guide-start-rest").click();
  await expect.poll(() => guide.startPayload).toEqual({ session_id: "guide-legacy" });
  await expect(page.getByTestId("guide-last-result")).toContainText("rest-start");

  await page.getByTestId("guide-retry-page-rest").click();
  await expect.poll(() => guide.retryPayload).toEqual({ session_id: "guide-legacy", page_index: 0 });

  await page.getByTestId("guide-chat-message").fill("Explain this point");
  await page.getByTestId("guide-chat-send-rest").click();
  await expect.poll(() => guide.chatPayload).toEqual({
    session_id: "guide-legacy",
    message: "Explain this point",
    knowledge_index: 0,
  });

  await page.getByTestId("guide-fix-toggle").click();
  await page.getByTestId("guide-fix-html-description").fill("Formula not visible");
  await page.getByTestId("guide-fix-html-rest").click();
  await expect.poll(() => guide.fixPayload).toEqual({
    session_id: "guide-legacy",
    bug_description: "Formula not visible",
  });

  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByTestId("guide-reset-rest").click();
  await expect.poll(() => guide.resetPayload).toEqual({ session_id: "guide-legacy" });

  await page.getByTestId("guide-complete-rest").click();
  await expect.poll(() => guide.completePayload).toEqual({ session_id: "guide-legacy" });
});

test("guide deletes the active session and falls back to another session", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "guide delete smoke runs once");
  const guide = await mockGuideApis(page);

  await page.goto("/guide?session=guide-legacy");
  await expect(page.getByText("Legacy Guide Session").first()).toBeVisible();
  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByTestId("guide-delete-session").click();
  await expect.poll(() => guide.deletedSessionId).toBe("guide-legacy");
  await expect(page.getByText("Other Guide Session").first()).toBeVisible();
});

test("co-writer streams edits and preserves notebook saving", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "co-writer streaming smoke runs once");
  const coWriter = await mockCoWriterStreamApis(page);

  await page.goto("/co-writer");
  await page.locator("textarea").first().fill("rough note");
  await page.locator("input").first().fill("polish this");
  await page.locator('button[type="submit"]').first().click();
  await expect(page.getByText("streamed polished text")).toBeVisible();
  await page.getByTestId("co-writer-stream-toggle").click();
  await expect(page.getByText("thinking: Planning edit")).toBeVisible();

  await page.getByTestId("co-writer-automark").click();
  await expect(page.getByTestId("co-writer-result")).toContainText("marked rough note");
  await expect(page.getByText("automark: /api/v1/co_writer/automark")).toBeVisible();
  await expect.poll(() => coWriter.automarkPayload).toEqual({ text: "rough note" });

  await page.getByTestId("co-writer-quick-edit").click();
  await expect(page.getByText("quick edited text")).toBeVisible();
  await expect(page.getByText("quick: /api/v1/co_writer/edit")).toBeVisible();
  await expect.poll(() => coWriter.quickEditPayload).toEqual(
    expect.objectContaining({
      text: "rough note",
      instruction: "polish this",
      action: "rewrite",
    }),
  );

  await page.locator("select").last().selectOption("nb-stream");
  await page.getByRole("button", { name: "保存" }).click();
  await expect.poll(() => coWriter.savedPayload).toEqual(
    expect.objectContaining({
      notebook_ids: ["nb-stream"],
      record_type: "co_writer",
      output: "quick edited text",
    }),
  );
});

test("co-writer audits history and exports markdown", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "co-writer history audit smoke runs once");
  const coWriter = await mockCoWriterStreamApis(page);

  await page.goto("/co-writer");
  await page.getByText("Polish proof").click();
  await page.getByTestId("co-writer-audit-toggle").click();
  const audit = page.locator("section", { has: page.getByRole("heading", { name: "操作审计" }) });
  await expect(audit.getByText("Original proof sketch")).toBeVisible();
  await expect(audit.getByText("Edited proof sketch")).toBeVisible();
  await expect(audit.getByText(/rag_search/)).toBeVisible();
  await page.getByRole("button", { name: /导出 Markdown/ }).click();
  await expect.poll(() => coWriter.exportPayload).toEqual({
    content: "Edited proof sketch",
    filename: "co-writer-op-history.md",
  });
});

test("legacy knowledge tab links land in the notebook workbench", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "legacy knowledge tab routing smoke runs once");

  await page.goto("/knowledge?tab=notebooks");
  await expect.poll(() => page.evaluate(() => `${window.location.pathname}${window.location.search}`)).toBe(
    "/notebook?tab=notebooks",
  );

  await page.goto("/knowledge?tab=questions");
  await expect.poll(() => page.evaluate(() => `${window.location.pathname}${window.location.search}`)).toBe(
    "/notebook?tab=questions",
  );
});

test("settings tour mode completes through the legacy tour endpoint", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "settings tour smoke runs once");
  const tour = await mockSettingsTourApis(page);

  await page.goto("/settings?tour=true");
  await expect(page.getByText("Setup Tour")).toBeVisible();
  await page.getByRole("button", { name: /Complete & Launch/ }).click();
  await expect.poll(() => tour.completedPayload).toEqual(
    expect.objectContaining({
      catalog: expect.objectContaining({ version: 1 }),
      test_results: expect.objectContaining({ llm: "configured", embedding: "configured" }),
    }),
  );
  await expect(page.getByRole("button", { name: "Tour completed" })).toBeDisabled();
});

test("settings saves workbench preferences", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "settings preference smoke runs once");
  const settings = await mockSettingsTourApis(page);

  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "工作台偏好" })).toBeVisible();
  await page.getByTestId("settings-preferences-toggle").click();
  await page.locator("form", { has: page.getByRole("heading", { name: "工作台偏好" }) }).getByLabel("主题").selectOption("snow");
  await page.locator("form", { has: page.getByRole("heading", { name: "工作台偏好" }) }).getByLabel("语言").selectOption("en");
  await page.getByLabel("侧栏宣言").fill("AI learning command center");
  await page.getByLabel("Start 区域").fill("/chat\n/knowledge\n/notebook");
  await page.getByLabel("Learn / Research 区域").fill("/guide\n/co-writer\n/agents");
  await page.getByRole("button", { name: "保存偏好" }).click();

  await expect.poll(() => settings.themePayload).toEqual({ theme: "snow" });
  await expect.poll(() => settings.languagePayload).toEqual({ language: "en" });
  await expect.poll(() => settings.sidebarDescriptionPayload).toEqual({ description: "AI learning command center" });
  await expect.poll(() => settings.sidebarNavPayload).toEqual({
    nav_order: {
      start: ["/chat", "/knowledge", "/notebook"],
      learnResearch: ["/guide", "/co-writer", "/agents"],
    },
  });
  await expect(page.getByText("工作台偏好已保存。")).toBeVisible();
});

test("settings shows NG runtime topology", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "settings topology smoke runs once");
  await mockSettingsTourApis(page);

  await page.goto("/settings");
  await page.getByTestId("settings-diagnostics-toggle").click();
  await expect(page.getByRole("heading", { name: "NG 运行拓扑" })).toBeVisible();
  await expect(page.getByTestId("settings-catalog-snapshot")).toContainText("/api/v1/settings/catalog");
  await expect(page.getByTestId("settings-catalog-snapshot")).toContainText("llm-profile");
  await expect(page.getByText("LangGraphTurnRuntimeManager")).toBeVisible();
  await expect(page.getByText("LangGraphRunner")).toBeVisible();
  await expect(page.getByText("CapabilityRegistry")).toBeVisible();
  await expect(page.getByText("ToolRegistry")).toBeVisible();
  await expect(page.getByText("guide · independent_subsystem")).toBeVisible();
});

test("settings shows setup tour status and reopens the guide", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "settings tour status smoke runs once");
  const settings = await mockSettingsTourApis(page);

  await page.goto("/settings");
  await page.getByTestId("settings-diagnostics-toggle").click();
  const panel = page.locator("section", { has: page.getByRole("heading", { name: "启动向导" }) });
  await expect(panel).toBeVisible();
  await expect(panel.getByText("waiting")).toBeVisible();
  await panel.getByTestId("settings-tour-reopen").click();

  await expect.poll(() => settings.reopenCalled).toBe(true);
  await expect(panel.getByText("python scripts/start_tour.py")).toBeVisible();
});

test("settings streams service checks and applies catalog", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "settings service test smoke runs once");
  const settings = await mockSettingsTourApis(page);
  await installMockSettingsEventSource(page);

  await page.goto("/settings");
  await page.getByTestId("settings-llm-base-url").fill("https://updated-llm.example/v1");
  await page.getByTestId("settings-llm-model").fill("gpt-updated");
  await page.getByTestId("settings-llm-api-key").fill("sk-updated");
  await page.getByTestId("settings-search-provider").selectOption("tavily");
  await expect(page.getByTestId("settings-search-base-url")).toHaveValue("https://api.tavily.com/search");
  await page.getByTestId("settings-embedding-provider").selectOption("cohere");
  await expect(page.getByTestId("settings-embedding-base-url")).toHaveValue("https://api.cohere.ai");
  await expect(page.getByTestId("settings-embedding-model")).toHaveValue("embed-v4.0");
  await expect(page.getByTestId("settings-embedding-dimension")).toHaveValue("1024");
  await page.getByTestId("settings-embedding-provider").selectOption("iflytek_spark");
  await expect(page.getByTestId("settings-embedding-base-url")).toHaveValue("https://emb-cn-huabei-1.xf-yun.com/");
  await expect(page.getByTestId("settings-embedding-model")).toHaveValue("llm-embedding");
  await expect(page.getByTestId("settings-embedding-dimension")).toHaveValue("2560");
  await page.getByTestId("settings-embedding-iflytek-appid").fill("iflytek-appid");
  await page.getByTestId("settings-embedding-iflytek-api-secret").fill("iflytek-secret");
  await page.getByTestId("settings-embedding-iflytek-domain").selectOption("para");
  await page.getByTestId("settings-embedding-model").fill("embedding-updated");
  await page.getByTestId("settings-embedding-dimension").fill("2048");
  await page.getByTestId("settings-save-apply").click();

  await expect.poll(() => settings.catalogPayload?.catalog?.services?.llm?.profiles?.[0]?.base_url).toBe(
    "https://updated-llm.example/v1",
  );
  await expect.poll(() => settings.catalogPayload?.catalog?.services?.llm?.profiles?.[0]?.api_key).toBe("sk-updated");
  await expect.poll(() => settings.catalogPayload?.catalog?.services?.llm?.profiles?.[0]?.models?.[0]?.model).toBe(
    "gpt-updated",
  );
  await expect.poll(() => settings.catalogPayload?.catalog?.services?.embedding?.profiles?.[0]?.models?.[0]?.dimension).toBe("2048");
  await expect.poll(() => settings.catalogPayload?.catalog?.services?.embedding?.profiles?.[0]?.extra_headers).toEqual({
    app_id: "iflytek-appid",
    api_secret: "iflytek-secret",
    domain: "para",
  });
  await expect.poll(() => settings.applyPayload?.catalog?.services?.llm?.profiles?.[0]?.models?.[0]?.model).toBe("gpt-updated");
  await expect.poll(() => settings.uiPayload).toEqual({ language: "zh", theme: "light" });
  await expect(page.getByText("配置已保存并应用到运行时。")).toBeVisible();

  await page.getByTestId("settings-diagnostics-toggle").click();
  await page.getByTestId("settings-probe-llm").click();
  await expect.poll(() => settings.systemProbeTarget).toBe("llm");
  await expect(page.getByTestId("settings-probe-result-llm")).toContainText("LLM connection successful");
  await expect(page.getByText("llm: LLM connection successful")).toBeVisible();

  await page.getByTestId("settings-test-llm").click();
  await expect.poll(() => settings.serviceStartPayload?.service).toBe("llm");
  await expect(page.getByTestId("settings-test-logs")).toContainText("LLM handshake ok");
  await expect(page.getByText("llm: LLM ready")).toBeVisible();

  await page.getByTestId("settings-test-search").click();
  await expect.poll(() => settings.serviceStartPayload?.service).toBe("search");
  await expect(page.getByTestId("settings-test-cancel")).toBeEnabled();
  await page.getByTestId("settings-test-cancel").click();
  await expect.poll(() => settings.cancelTarget).toEqual({ service: "search", runId: "run-search-cancel" });
  await expect(page.getByTestId("settings-test-logs")).toContainText("已取消当前服务检测");
});

test("notebook deep links select records and question follow-up sessions", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "notebook deep link smoke runs once");
  await mockNotebookDeepLinkApis(page);

  await page.goto("/notebook?notebook=nb-link&record=rec-chat");
  await expect(page.getByText("Deep linked notebook record")).toBeVisible();
  await expect(page.getByText("知识可视化 · mermaid")).toBeVisible();
  await expect(page.getByRole("heading", { name: "可视化资产预览" })).toBeVisible();
  await expect(page.getByTestId("mermaid-preview").locator("svg")).toBeVisible();
  await page.locator("article", { hasText: "Deep linked notebook record" }).getByRole("button").first().click();
  await expect.poll(() => page.evaluate(() => window.location.pathname)).toBe("/chat/session-from-record");

  await page.goto("/notebook?notebook=nb-link&record=rec-guide");
  await expect(page.getByTestId("notebook-record-rec-guide")).toContainText("Saved guided learning page", {
    timeout: 15_000,
  });
  await expect(page.getByRole("heading", { name: "导学页面预览" })).toBeVisible();
  await expect(page.getByTestId("guide-asset-preview")).toBeVisible();

  await page.goto("/notebook?tab=questions&entry=7");
  await expect(page.getByText("Follow-up question target").first()).toBeVisible();
  await page.locator("aside").getByRole("button").nth(1).click();
  await expect.poll(() => page.evaluate(() => window.location.pathname)).toBe("/chat/followup-session");
});

test("notebook workbench writes records and question categories", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "notebook mutation smoke runs once");
  const notebook = await mockNotebookMutationApis(page);
  page.on("dialog", (dialog) => void dialog.accept());

  await page.goto("/notebook");
  await expect(page.getByText("healthy").first()).toBeVisible();
  await expect(page.getByText("/api/v1/notebook/health").first()).toBeVisible();
  await page.getByTestId("notebook-create-toggle").click();
  await page.getByTestId("notebook-create-name").fill("Competition Review");
  await page.getByTestId("notebook-create-description").fill("Polished learning assets");
  await page.getByTestId("notebook-create-submit").click();
  await expect.poll(() => notebook.createPayload).toEqual({
    name: "Competition Review",
    description: "Polished learning assets",
    color: "#0F766E",
    icon: "book",
  });

  await page.getByTestId("notebook-manual-toggle").click();
  await page.getByTestId("notebook-manual-title").fill("Manual proof note");
  await page.getByTestId("notebook-manual-output").fill("A compact proof saved from web.");
  await page.getByTestId("notebook-manual-submit").click();
  await expect.poll(() => notebook.addRecordPayload).toEqual(
    expect.objectContaining({
      notebook_ids: ["nb-created"],
      record_type: "chat",
      title: "Manual proof note",
      output: "A compact proof saved from web.",
      metadata: { source: "web_manual", ui_language: "zh" },
    }),
  );
  await expect(page.getByTestId("notebook-manual-title")).toHaveValue("");
  await expect(page.getByTestId("notebook-manual-output")).toHaveValue("");

  await page.getByTestId("notebook-manual-title").fill("Summary proof note");
  await page.getByTestId("notebook-manual-output").fill("Long solution text that should be summarized by the notebook agent.");
  await page.getByTestId("notebook-manual-summary-submit").click();
  await expect.poll(() => notebook.addRecordSummaryPayload).toEqual(
    expect.objectContaining({
      notebook_ids: ["nb-created"],
      title: "Summary proof note",
      summary: "",
    }),
  );
  await expect(page.getByTestId("notebook-summary-preview")).toContainText("AI summary for notebook");

  await page.goto("/notebook?notebook=nb-existing");
  await page.getByTestId("notebook-meta-name").fill("Edited Notebook");
  await page.getByTestId("notebook-meta-description").fill("Edited notebook description");
  await page.getByTestId("notebook-meta-save").click();
  await expect.poll(() => notebook.updateNotebookTarget).toBe("nb-existing");
  await expect.poll(() => notebook.updateNotebookPayload).toEqual(
    expect.objectContaining({
      name: "Edited Notebook",
      description: "Edited notebook description",
    }),
  );

  await page.getByTestId("notebook-record-edit-rec-existing").click();
  await page.getByTestId("record-editor-title").fill("Edited proof note");
  await page.getByTestId("record-editor-summary").fill("Edited summary");
  await page.getByTestId("record-editor-output").fill("Edited notebook output");
  await page.getByTestId("record-editor-save").click();
  await expect.poll(() => notebook.updateRecordPayload).toEqual(
    expect.objectContaining({
      title: "Edited proof note",
      summary: "Edited summary",
      output: "Edited notebook output",
    }),
  );
  expect(notebook.updateRecordTarget).toEqual({ notebookId: "nb-existing", recordId: "rec-existing" });

  await page.getByTestId("notebook-record-delete-rec-existing").click();
  await expect.poll(() => notebook.deletedRecordTarget).toEqual({ notebookId: "nb-existing", recordId: "rec-existing" });

  await page.getByTestId("question-entry-bookmark-7").click();
  await expect.poll(() => notebook.entryUpdatePayload).toEqual({ bookmarked: true });

  await page.getByTestId("question-category-create-name").fill("Derivative traps");
  await page.getByTestId("question-category-create-submit").click();
  await expect.poll(() => notebook.categoryCreatePayload).toEqual({ name: "Derivative traps" });

  await page.getByTestId("question-quick-toggle").click();
  await page.getByTestId("question-upsert-session").fill("manual-session");
  await page.getByTestId("question-upsert-id").fill("q-manual");
  await page.getByTestId("question-upsert-question").fill("Why does factoring help before L'Hopital?");
  await page.getByTestId("question-upsert-answer").fill("It can remove a removable zero factor.");
  await page.getByTestId("question-upsert-explanation").fill("Always simplify the expression first.");
  await page.getByTestId("question-upsert-submit").click();
  await expect.poll(() => notebook.questionUpsertPayload).toEqual(
    expect.objectContaining({
      session_id: "manual-session",
      question_id: "q-manual",
      question: "Why does factoring help before L'Hopital?",
      correct_answer: "It can remove a removable zero factor.",
    }),
  );
  await expect(page.getByText("已写入题目 q-manual")).toBeVisible();
  await page.getByTestId("question-lookup-submit").click();
  await expect.poll(() => notebook.questionLookupTarget).toEqual({ sessionId: "manual-session", questionId: "q-manual" });
  await expect(page.getByText("已找到题目 q-manual")).toBeVisible();

  await page.getByTestId("question-category-rename-1").click();
  await page.getByTestId("question-category-rename-input-1").fill("Limits Review");
  await page.getByTestId("question-category-rename-save-1").click();
  await expect.poll(() => notebook.categoryRenamePayload).toEqual({ name: "Limits Review" });

  await page.getByTestId("question-detail-category-select").selectOption("2");
  await page.getByTestId("question-detail-category-add").click();
  await expect.poll(() => notebook.categoryAddPayload).toEqual({ category_id: 2 });

  await page.getByTestId("question-detail-category-remove-1").click();
  await expect.poll(() => notebook.categoryRemoveTarget).toEqual({ entryId: 7, categoryId: 1 });

  await page.getByTestId("question-entry-delete-7").click();
  await expect.poll(() => notebook.entryDeleteId).toBe(7);

  await page.getByTestId("notebook-delete").click();
  await expect.poll(() => notebook.deletedNotebookId).toBe("nb-existing");
});

test("mobile context drawer opens without DOM errors", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile drawer smoke only");
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/chat");
  await page.getByRole("button", { name: "上下文" }).click();
  await expect(page.getByRole("heading", { name: "学习方式" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "历史会话" })).toHaveCount(0);
  expect(errors).toEqual([]);
});

test("mobile navigation reaches the redesigned workspace sections", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile navigation smoke only");
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await mockReferenceApis(page);
  await mockSettingsTourApis(page);
  await mockSparkBotApis(page);

  const pathname = () => page.evaluate(() => window.location.pathname);

  await page.goto("/chat");
  await page.getByRole("button", { name: "打开导航" }).click();
  await page.getByRole("link", { name: /^设置$/ }).click();
  await expect.poll(pathname).toBe("/settings");

  await page.getByRole("button", { name: "打开导航" }).click();
  await page.getByRole("link", { name: /^助教$/ }).click();
  await expect.poll(pathname).toBe("/agents");

  await page.getByRole("navigation").getByRole("link", { name: /^资料$/ }).click();
  await expect.poll(pathname).toBe("/knowledge");
  expect(errors).toEqual([]);
});

test("mobile legacy aliases resolve into the redesigned workbench without DOM errors", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile legacy alias smoke only");
  const errors: string[] = [];
  const consoleDomErrors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (text.includes("insertBefore") || text.includes("Failed to execute")) consoleDomErrors.push(text);
  });
  await mockReferenceApis(page);
  await mockSparkBotApis(page);

  const pathAndSearch = () => page.evaluate(() => `${window.location.pathname}${window.location.search}`);

  await page.goto("/?session=session-old-a");
  await expect.poll(pathAndSearch, { timeout: 15000 }).toBe("/chat/session-old-a");
  await expect(page.getByText("Loaded assistant answer")).toBeVisible({ timeout: 15000 });

  await page.goto("/utility/notebook");
  await expect.poll(pathAndSearch).toBe("/notebook");

  await page.goto("/knowledge?tab=notebooks");
  await expect.poll(pathAndSearch).toBe("/notebook?tab=notebooks");

  await page.goto("/knowledge?tab=questions");
  await expect.poll(pathAndSearch).toBe("/notebook?tab=questions");

  await page.goto("/sparkbot/math_bot/chat");
  await expect.poll(pathAndSearch).toBe("/agents/math_bot/chat");
  await expect(page.getByText(/math_bot/).first()).toBeVisible();

  await page.goto("/math-animator");
  await expect.poll(pathAndSearch).toBe("/chat?capability=math_animator");

  await page.goto("/cowriter");
  await expect.poll(pathAndSearch).toBe("/co-writer");

  expect(errors).toEqual([]);
  expect(consoleDomErrors).toEqual([]);
});

test("mobile chat streams websocket results without DOM errors", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile chat smoke only");
  const errors: string[] = [];
  const consoleDomErrors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (text.includes("insertBefore") || text.includes("Failed to execute")) consoleDomErrors.push(text);
  });
  await mockReferenceApis(page);
  await installMockWebSocket(page, {
    resultOnlyContent: "Mobile final answer from mock runtime.",
  });

  await page.goto("/chat");
  await page.locator("textarea").first().fill("Run the mobile chat flow");
  await page.getByTestId("chat-send").click();

  await expect(page.getByText("Mobile final answer from mock runtime.")).toBeVisible();
  await page.getByTestId("chat-context-toggle").click();
  await expect(page.getByTestId("chat-mobile-context-drawer").getByText("session-new").first()).toBeVisible();
  expect(errors).toEqual([]);
  expect(consoleDomErrors).toEqual([]);
});

test("mobile chat manages sessions from the history drawer without DOM errors", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile chat session management smoke only");
  const errors: string[] = [];
  const consoleDomErrors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (text.includes("insertBefore") || text.includes("Failed to execute")) consoleDomErrors.push(text);
  });
  page.on("dialog", (dialog) => void dialog.accept());
  const reference = await mockReferenceApis(page);

  await page.goto("/chat");
  await page.getByTestId("chat-history-toggle").click();
  const drawer = page.getByTestId("chat-history-drawer");
  await expect(drawer.getByTestId("chat-session-card-session-old-a")).toBeVisible();

  await drawer.getByTestId("chat-session-load-session-old-a").click();
  await expect(page.getByText("Loaded assistant answer")).toBeVisible();
  await page.getByTestId("chat-history-toggle").click();

  await drawer.getByTestId("chat-session-rename-session-old-a").click();
  await drawer.getByTestId("chat-session-title-session-old-a").fill("Mobile renamed session");
  await drawer.getByTestId("chat-session-rename-save-session-old-a").click();
  await expect.poll(() => reference.sessionRenamePayload).toEqual({
    sessionId: "session-old-a",
    title: "Mobile renamed session",
  });

  await drawer.getByTestId("chat-session-delete-session-old-a").click();
  await expect.poll(() => reference.sessionDeleteTarget).toBe("session-old-a");
  expect(errors).toEqual([]);
  expect(consoleDomErrors).toEqual([]);
});

test("mobile knowledge creation streams task progress", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile knowledge creation smoke only");
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const knowledge = await mockKnowledgeApis(page);
  await installMockKnowledgeProgressWebSocket(page);

  await page.goto("/knowledge");
  await page.getByTestId("knowledge-create-name").fill("calculus_mock");
  await page.getByTestId("knowledge-create-files").setInputFiles({
    name: "limits.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("# Limits\nUse notebook context."),
  });
  await page.getByTestId("knowledge-create-submit").click();

  await expect(page.getByTestId("knowledge-task-logs")).toContainText("Saved 1 file, preparing index");
  await expect(page.getByTestId("knowledge-task-logs")).toContainText("complete: Knowledge base created");
  await expect(page.getByTestId("knowledge-task-logs")).toContainText("ws: completed 100% WS index complete");
  await expect.poll(() => knowledge.createBody?.includes('name="name"\r\n\r\ncalculus_mock')).toBe(true);
  await expect.poll(() => knowledge.createBody?.includes('filename="limits.md"')).toBe(true);
  const wsUrls = await page.evaluate(() => (window as typeof window & { __knowledgeWsUrls?: string[] }).__knowledgeWsUrls ?? []);
  expect(wsUrls.some((url) => url.includes("/api/v1/knowledge/calculus_mock/progress/ws"))).toBe(true);
  expect(errors).toEqual([]);
});

test("mobile knowledge manages uploads defaults folders and deletion without DOM errors", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile knowledge management smoke only");
  const errors: string[] = [];
  const consoleDomErrors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (text.includes("insertBefore") || text.includes("Failed to execute")) consoleDomErrors.push(text);
  });
  page.on("dialog", (dialog) => void dialog.accept());
  const knowledge = await mockKnowledgeManagementApis(page);

  await page.goto("/knowledge");
  await expect(page.getByTestId("knowledge-detail-panel")).toContainText("/api/v1/knowledge/calculus_mock");
  await page.getByTestId("knowledge-kb-default-geometry_mock").click();
  await expect.poll(() => knowledge.defaultKb).toBe("geometry_mock");
  await page.getByTestId("knowledge-kb-select-geometry_mock").click();
  await expect(page.getByTestId("knowledge-detail-panel")).toContainText("/api/v1/knowledge/geometry_mock");
  await expect(page.getByTestId("knowledge-detail-panel")).toContainText("Geometry vector store ready");

  await page.getByTestId("knowledge-upload-target").selectOption("geometry_mock");
  await page.getByTestId("knowledge-progress-toggle").click();
  await page.getByTestId("knowledge-progress-clear").click();
  await expect.poll(() => knowledge.clearedProgress).toBe("geometry_mock");
  await expect(page.getByTestId("knowledge-task-logs")).toContainText("Progress cleared for geometry_mock");

  await page.getByTestId("knowledge-upload-files").setInputFiles({
    name: "mobile-triangles.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("# Mobile triangles\nSimilarity and area."),
  });
  await page.getByTestId("knowledge-upload-submit").click();
  await expect.poll(() => knowledge.uploadTarget).toBe("geometry_mock");
  await expect.poll(() => knowledge.uploadBody?.includes('filename="mobile-triangles.md"')).toBe(true);
  await expect(page.getByTestId("knowledge-task-logs")).toContainText("complete: Upload complete");

  await page.getByTestId("knowledge-folder-toggle").click();
  await page.getByTestId("knowledge-folder-path").fill("C:\\course\\geometry-mobile");
  await page.getByTestId("knowledge-folder-link").click();
  await expect.poll(() => knowledge.linkPayload).toEqual({ folder_path: "C:\\course\\geometry-mobile" });

  await page.getByTestId("knowledge-folder-sync-folder-1").click();
  await expect.poll(() => knowledge.syncTarget).toEqual({ kbName: "geometry_mock", folderId: "folder-1" });
  await expect(page.getByTestId("knowledge-task-logs")).toContainText("complete: Folder sync complete");

  await page.getByTestId("knowledge-folder-unlink-folder-1").click();
  await expect.poll(() => knowledge.unlinkTarget).toEqual({ kbName: "geometry_mock", folderId: "folder-1" });

  await page.getByTestId("knowledge-kb-delete-geometry_mock").click();
  await expect.poll(() => knowledge.deletedKb).toBe("geometry_mock");
  expect(errors).toEqual([]);
  expect(consoleDomErrors).toEqual([]);
});

test("mobile notebook saves manual records without DOM errors", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile notebook smoke only");
  const errors: string[] = [];
  const consoleDomErrors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (text.includes("insertBefore") || text.includes("Failed to execute")) consoleDomErrors.push(text);
  });
  const notebook = await mockNotebookMutationApis(page);

  await page.goto("/notebook");
  await expect(page.getByText("healthy").first()).toBeVisible();

  await page.getByTestId("notebook-create-toggle").click();
  await page.getByTestId("notebook-create-name").fill("Mobile Review");
  await page.getByTestId("notebook-create-description").fill("Small screen saved notes");
  await page.getByTestId("notebook-create-submit").click();
  await expect.poll(() => notebook.createPayload).toEqual({
    name: "Mobile Review",
    description: "Small screen saved notes",
    color: "#0F766E",
    icon: "book",
  });

  await page.getByTestId("notebook-manual-toggle").click();
  await page.getByTestId("notebook-manual-title").fill("Mobile saved note");
  await page.getByTestId("notebook-manual-output").fill("A compact mobile note saved from web.");
  await page.getByTestId("notebook-manual-submit").click();
  await expect.poll(() => notebook.addRecordPayload).toEqual(
    expect.objectContaining({
      notebook_ids: ["nb-created"],
      record_type: "chat",
      title: "Mobile saved note",
      output: "A compact mobile note saved from web.",
      metadata: { source: "web_manual", ui_language: "zh" },
    }),
  );
  expect(errors).toEqual([]);
  expect(consoleDomErrors).toEqual([]);
});

test("mobile notebook edits records and question categories without DOM errors", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile notebook management smoke only");
  const errors: string[] = [];
  const consoleDomErrors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (text.includes("insertBefore") || text.includes("Failed to execute")) consoleDomErrors.push(text);
  });
  page.on("dialog", (dialog) => void dialog.accept());
  const notebook = await mockNotebookMutationApis(page);

  await page.goto("/notebook?notebook=nb-existing");
  await expect(page.getByTestId("notebook-meta-name")).toHaveValue("Existing Notebook");
  await page.getByTestId("notebook-meta-name").fill("Mobile Edited Notebook");
  await page.getByTestId("notebook-meta-description").fill("Mobile edited description");
  await page.getByTestId("notebook-meta-save").click();
  await expect.poll(() => notebook.updateNotebookTarget).toBe("nb-existing");
  await expect.poll(() => notebook.updateNotebookPayload).toEqual(
    expect.objectContaining({
      name: "Mobile Edited Notebook",
      description: "Mobile edited description",
    }),
  );

  await page.getByTestId("notebook-record-edit-rec-existing").click();
  await page.getByTestId("record-editor-title").fill("Mobile edited proof note");
  await page.getByTestId("record-editor-summary").fill("Mobile edited summary");
  await page.getByTestId("record-editor-output").fill("Mobile edited notebook output");
  await page.getByTestId("record-editor-save").click();
  await expect.poll(() => notebook.updateRecordPayload).toEqual(
    expect.objectContaining({
      title: "Mobile edited proof note",
      summary: "Mobile edited summary",
      output: "Mobile edited notebook output",
    }),
  );
  expect(notebook.updateRecordTarget).toEqual({ notebookId: "nb-existing", recordId: "rec-existing" });

  await page.getByTestId("notebook-record-delete-rec-existing").click();
  await expect.poll(() => notebook.deletedRecordTarget).toEqual({ notebookId: "nb-existing", recordId: "rec-existing" });

  await page.getByTestId("question-entry-select-7").click();
  await page.getByTestId("question-entry-bookmark-7").click();
  await expect.poll(() => notebook.entryUpdatePayload).toEqual({ bookmarked: true });

  await page.getByTestId("question-category-create-name").fill("Mobile Review Category");
  await page.getByTestId("question-category-create-submit").click();
  await expect.poll(() => notebook.categoryCreatePayload).toEqual({ name: "Mobile Review Category" });

  await page.getByTestId("question-category-rename-1").click();
  await page.getByTestId("question-category-rename-input-1").fill("Mobile Limits Review");
  await page.getByTestId("question-category-rename-save-1").click();
  await expect.poll(() => notebook.categoryRenamePayload).toEqual({ name: "Mobile Limits Review" });

  await page.getByTestId("question-detail-category-select").selectOption("2");
  await page.getByTestId("question-detail-category-add").click();
  await expect.poll(() => notebook.categoryAddPayload).toEqual({ category_id: 2 });

  await page.getByTestId("question-detail-category-remove-1").click();
  await expect.poll(() => notebook.categoryRemoveTarget).toEqual({ entryId: 7, categoryId: 1 });

  await page.getByTestId("question-entry-delete-7").click();
  await expect.poll(() => notebook.entryDeleteId).toBe(7);

  expect(errors).toEqual([]);
  expect(consoleDomErrors).toEqual([]);
});

test("mobile notebook deep links records and follow-up sessions without DOM errors", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile notebook deep link smoke only");
  const errors: string[] = [];
  const consoleDomErrors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (text.includes("insertBefore") || text.includes("Failed to execute")) consoleDomErrors.push(text);
  });
  await mockNotebookDeepLinkApis(page);

  await page.goto("/notebook?notebook=nb-link&record=rec-chat");
  await expect(page.getByText("Deep linked notebook record")).toBeVisible();
  await expect(page.getByTestId("mermaid-preview").locator("svg")).toBeVisible();
  await page.locator("article", { hasText: "Deep linked notebook record" }).getByRole("button").first().click();
  await expect.poll(() => page.evaluate(() => window.location.pathname)).toBe("/chat/session-from-record");

  await page.goto("/notebook?notebook=nb-link&record=rec-guide");
  await expect(page.getByText("Saved guided learning page")).toBeVisible();
  await expect(page.getByTestId("guide-asset-preview")).toBeVisible();

  await page.goto("/notebook?tab=questions&entry=7");
  await expect(page.getByText("Follow-up question target").first()).toBeVisible();
  await page.locator("aside").getByRole("button").nth(1).click();
  await expect.poll(() => page.evaluate(() => window.location.pathname)).toBe("/chat/followup-session");

  expect(errors).toEqual([]);
  expect(consoleDomErrors).toEqual([]);
});

test("mobile settings saves runtime config and probes services without DOM errors", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile settings smoke only");
  const errors: string[] = [];
  const consoleDomErrors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (text.includes("insertBefore") || text.includes("Failed to execute")) consoleDomErrors.push(text);
  });
  const settings = await mockSettingsTourApis(page);
  await installMockSettingsEventSource(page);

  await page.goto("/settings");
  await page.getByTestId("settings-llm-base-url").fill("https://mobile-llm.example/v1");
  await page.getByTestId("settings-llm-model").fill("gpt-mobile");
  await page.getByTestId("settings-llm-api-key").fill("sk-mobile");
  await page.getByTestId("settings-embedding-model").fill("embedding-mobile");
  await page.getByTestId("settings-embedding-dimension").fill("1536");
  await page.getByTestId("settings-save-apply").click();

  await expect.poll(() => settings.catalogPayload?.catalog?.services?.llm?.profiles?.[0]?.base_url).toBe(
    "https://mobile-llm.example/v1",
  );
  await expect.poll(() => settings.catalogPayload?.catalog?.services?.llm?.profiles?.[0]?.api_key).toBe("sk-mobile");
  await expect.poll(() => settings.catalogPayload?.catalog?.services?.llm?.profiles?.[0]?.models?.[0]?.model).toBe("gpt-mobile");
  await expect.poll(() => settings.catalogPayload?.catalog?.services?.embedding?.profiles?.[0]?.models?.[0]?.model).toBe(
    "embedding-mobile",
  );
  await expect.poll(() => settings.catalogPayload?.catalog?.services?.embedding?.profiles?.[0]?.models?.[0]?.dimension).toBe(
    "1536",
  );

  await page.getByTestId("settings-diagnostics-toggle").click();
  await page.getByTestId("settings-probe-llm").click();
  await expect.poll(() => settings.systemProbeTarget).toBe("llm");
  await expect(page.getByTestId("settings-probe-result-llm")).toContainText("LLM connection successful");

  await page.getByTestId("settings-test-llm").click();
  await expect.poll(() => settings.serviceStartPayload?.service).toBe("llm");
  await expect(page.getByTestId("settings-test-logs")).toContainText("LLM handshake ok");
  const eventSourceUrls = await page.evaluate(() => (window as typeof window & { __settingsEventSourceUrls?: string[] }).__settingsEventSourceUrls ?? []);
  expect(eventSourceUrls.some((url) => url.includes("/api/v1/settings/tests/llm/run-llm-complete/events"))).toBe(true);
  expect(errors).toEqual([]);
  expect(consoleDomErrors).toEqual([]);
});

test("mobile settings manages topology tour and cancellable checks without DOM errors", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile settings advanced smoke only");
  const errors: string[] = [];
  const consoleDomErrors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (text.includes("insertBefore") || text.includes("Failed to execute")) consoleDomErrors.push(text);
  });
  const settings = await mockSettingsTourApis(page);
  await installMockSettingsEventSource(page);

  await page.goto("/settings");
  await page.getByTestId("settings-diagnostics-toggle").click();
  await expect(page.getByTestId("settings-catalog-snapshot")).toContainText("/api/v1/settings/catalog");
  await expect(page.getByTestId("settings-catalog-snapshot")).toContainText("llm-profile");
  await expect(page.getByText("LangGraphTurnRuntimeManager")).toBeVisible();
  await expect(page.getByText("CapabilityRegistry")).toBeVisible();

  await page.getByTestId("settings-tour-reopen").click();
  await expect.poll(() => settings.reopenCalled).toBe(true);
  await expect(page.getByText("python scripts/start_tour.py", { exact: true })).toBeVisible();

  await page.getByTestId("settings-probe-search").click();
  await expect.poll(() => settings.systemProbeTarget).toBe("search");
  await expect(page.getByTestId("settings-probe-result-search")).toContainText("Search not configured");

  await page.getByTestId("settings-test-search").click();
  await expect.poll(() => settings.serviceStartPayload?.service).toBe("search");
  await expect(page.getByTestId("settings-test-cancel")).toBeEnabled();
  await page.getByTestId("settings-test-cancel").click();
  await expect.poll(() => settings.cancelTarget).toEqual({ service: "search", runId: "run-search-cancel" });

  await page.goto("/settings?tour=true");
  await page.getByRole("button", { name: /Complete & Launch/ }).click();
  await expect.poll(() => settings.completedPayload).toEqual(
    expect.objectContaining({
      catalog: expect.objectContaining({ version: 1 }),
      test_results: expect.objectContaining({ llm: "configured", embedding: "configured" }),
    }),
  );
  await expect(page.getByRole("button", { name: "Tour completed" })).toBeDisabled();

  expect(errors).toEqual([]);
  expect(consoleDomErrors).toEqual([]);
});

test("mobile settings saves and resets workbench preferences without DOM errors", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile settings preference smoke only");
  const errors: string[] = [];
  const consoleDomErrors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (text.includes("insertBefore") || text.includes("Failed to execute")) consoleDomErrors.push(text);
  });
  const settings = await mockSettingsTourApis(page);

  await page.goto("/settings");
  await page.getByTestId("settings-preferences-toggle").click();
  const preferences = page.locator("form", { has: page.getByRole("heading", { name: "工作台偏好" }) });
  await expect(preferences).toBeVisible();
  await preferences.getByLabel("主题").selectOption("snow");
  await preferences.getByLabel("语言").selectOption("en");
  await preferences.getByLabel("侧栏宣言").fill("Mobile AI learning command center");
  await preferences.getByLabel("Start 区域").fill("/chat\n/notebook\n/knowledge");
  await preferences.getByLabel("Learn / Research 区域").fill("/guide\n/agents\n/co-writer");
  await preferences.getByRole("button", { name: "保存偏好" }).click();

  await expect.poll(() => settings.themePayload).toEqual({ theme: "snow" });
  await expect.poll(() => settings.languagePayload).toEqual({ language: "en" });
  await expect.poll(() => settings.sidebarDescriptionPayload).toEqual({ description: "Mobile AI learning command center" });
  await expect.poll(() => settings.sidebarNavPayload).toEqual({
    nav_order: {
      start: ["/chat", "/notebook", "/knowledge"],
      learnResearch: ["/guide", "/agents", "/co-writer"],
    },
  });
  await expect(page.getByText("工作台偏好已保存。")).toBeVisible();

  await preferences.getByRole("button", { name: "重置界面" }).click();
  await expect.poll(() => settings.resetCalled).toBe(true);
  await expect(page.getByText("界面偏好已重置为默认值。")).toBeVisible();

  expect(errors).toEqual([]);
  expect(consoleDomErrors).toEqual([]);
});

test("mobile co-writer streams edits and saves output without DOM errors", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile co-writer smoke only");
  const errors: string[] = [];
  const consoleDomErrors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (text.includes("insertBefore") || text.includes("Failed to execute")) consoleDomErrors.push(text);
  });
  const coWriter = await mockCoWriterStreamApis(page);

  await page.goto("/co-writer");
  await page.getByTestId("co-writer-source-text").fill("mobile rough note");
  await page.getByTestId("co-writer-instruction").fill("polish this for a phone screen");
  await page.getByTestId("co-writer-stream-submit").click();
  await expect(page.getByTestId("co-writer-result")).toContainText("streamed polished text");
  await page.getByTestId("co-writer-stream-toggle").click();
  await expect(page.getByText("thinking: Planning edit")).toBeVisible();

  await page.getByTestId("co-writer-automark").click();
  await expect(page.getByTestId("co-writer-result")).toContainText("marked rough note");
  await expect.poll(() => coWriter.automarkPayload).toEqual({ text: "mobile rough note" });

  await page.getByTestId("co-writer-quick-edit").click();
  await expect(page.getByTestId("co-writer-result")).toContainText("quick edited text");
  await expect.poll(() => coWriter.quickEditPayload).toEqual(
    expect.objectContaining({
      text: "mobile rough note",
      instruction: "polish this for a phone screen",
      action: "rewrite",
    }),
  );

  await page.locator("select").last().selectOption("nb-stream");
  await page.getByTestId("co-writer-save").click();
  await expect.poll(() => coWriter.savedPayload).toEqual(
    expect.objectContaining({
      notebook_ids: ["nb-stream"],
      record_type: "co_writer",
      output: "quick edited text",
    }),
  );
  expect(errors).toEqual([]);
  expect(consoleDomErrors).toEqual([]);
});

test("mobile co-writer audits history and exports markdown without DOM errors", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile co-writer audit smoke only");
  const errors: string[] = [];
  const consoleDomErrors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (text.includes("insertBefore") || text.includes("Failed to execute")) consoleDomErrors.push(text);
  });
  const coWriter = await mockCoWriterStreamApis(page);

  await page.goto("/co-writer");
  await page.getByTestId("co-writer-history-op-history").click();
  await page.getByTestId("co-writer-audit-toggle").click();
  await expect(page.locator("pre").filter({ hasText: "Original proof sketch" })).toBeVisible();
  await expect(page.locator("pre").filter({ hasText: "Edited proof sketch" })).toBeVisible();
  await expect(page.locator("pre").filter({ hasText: /rag_search/ })).toBeVisible();
  await page.getByTestId("co-writer-export").click();
  await expect.poll(() => coWriter.exportPayload).toEqual({
    content: "Edited proof sketch",
    filename: "co-writer-op-history.md",
  });
  expect(errors).toEqual([]);
  expect(consoleDomErrors).toEqual([]);
});

test("mobile sparkbot streams agent replies without DOM errors", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile sparkbot smoke only");
  const errors: string[] = [];
  const consoleDomErrors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (text.includes("insertBefore") || text.includes("Failed to execute")) consoleDomErrors.push(text);
  });
  const sparkbot = await mockSparkBotApis(page);
  await installMockSparkBotWebSocket(page);

  await page.goto("/agents/math_bot/chat");
  await expect.poll(() => sparkbot.recentLimit).toBe(5);
  await expect(page.getByTestId("sparkbot-recent-panel")).toContainText("Last geometry reminder");
  await expect(page.getByTestId("sparkbot-history-piece-0-0")).toContainText("How should I review limits?");
  await expect(page.getByTestId("sparkbot-history-piece-0-1")).toContainText("Start from the definition");

  const botChat = page.getByTestId("sparkbot-chat");
  await botChat.locator("input").fill("Explain derivative on mobile");
  await botChat.locator('button[type="submit"]').click();
  await expect(botChat).toContainText("Planning derivative hint");
  await expect(botChat).toContainText("2");
  await expect
    .poll(() =>
      page.evaluate(() => {
        const state = window as typeof window & { __deepSparkBotWsMessages?: Array<Record<string, unknown>> };
        return state.__deepSparkBotWsMessages?.[0] ?? null;
      }),
    )
    .toEqual(expect.objectContaining({ content: "Explain derivative on mobile", chat_id: "web" }));

  await page.getByTestId("sparkbot-recent-writing_bot").click();
  await expect(page.getByTestId("sparkbot-history-piece-0-0")).toContainText("Draft outline feedback is ready.");
  await page.getByTestId("bot-profile-toggle").click();
  await expect(page.getByTestId("bot-profile-name")).toHaveValue("Writing Bot");
  await expect(page.getByTestId("bot-profile-model")).toHaveValue("gpt-writing");
  expect(errors).toEqual([]);
  expect(consoleDomErrors).toEqual([]);
});

test("mobile sparkbot manages profile files and lifecycle without DOM errors", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile sparkbot management smoke only");
  const errors: string[] = [];
  const consoleDomErrors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (text.includes("insertBefore") || text.includes("Failed to execute")) consoleDomErrors.push(text);
  });
  page.on("dialog", (dialog) => void dialog.accept());
  const sparkbot = await mockSparkBotApis(page);

  await page.goto("/agents/math_bot/chat");
  await expect(page.getByTestId("sparkbot-card-math_bot")).toBeVisible();

  await page.getByTestId("bot-profile-toggle").click();
  await page.getByTestId("bot-profile-name").fill("Mobile Math Bot");
  await page.getByTestId("bot-profile-description").fill("Managed from the mobile workbench");
  await page.getByTestId("bot-profile-save").click();
  await expect.poll(() => sparkbot.updatePayload).toEqual(
    expect.objectContaining({
      name: "Mobile Math Bot",
      description: "Managed from the mobile workbench",
    }),
  );

  await page.getByTestId("sparkbot-files-toggle").click();
  await page.getByTestId("sparkbot-file-SOUL.md").click();
  await expect(page.getByTestId("sparkbot-file-content")).toHaveValue(/# Math Bot/);
  await page.getByTestId("sparkbot-file-content").fill("# Math Bot\n\nMobile prompt update");
  await page.getByTestId("sparkbot-file-save").click();
  await expect.poll(() => sparkbot.fileWritePayload).toEqual({
    botId: "math_bot",
    filename: "SOUL.md",
    content: "# Math Bot\n\nMobile prompt update",
  });

  await page.getByTestId("sparkbot-start-writing_bot").click();
  await expect.poll(() => sparkbot.startPayload).toEqual(
    expect.objectContaining({
      bot_id: "writing_bot",
      auto_start: true,
    }),
  );

  await page.getByTestId("sparkbot-stop-math_bot").click();
  await expect.poll(() => sparkbot.stopTarget).toBe("math_bot");

  await page.getByTestId("sparkbot-destroy-writing_bot").click();
  await expect.poll(() => sparkbot.destroyTarget).toBe("writing_bot");
  expect(errors).toEqual([]);
  expect(consoleDomErrors).toEqual([]);
});

test("mobile sparkbot edits souls and schema channels without DOM errors", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile sparkbot advanced config smoke only");
  const errors: string[] = [];
  const consoleDomErrors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (text.includes("insertBefore") || text.includes("Failed to execute")) consoleDomErrors.push(text);
  });
  page.on("dialog", (dialog) => void dialog.accept());
  const sparkbot = await mockSparkBotApis(page);

  await page.goto("/agents/math_bot/chat");
  await page.getByTestId("sparkbot-soul-toggle").click();
  await page.getByTestId("sparkbot-soul-socratic").click();
  await expect.poll(() => sparkbot.soulDetailTarget).toBe("socratic");
  await page.getByTestId("sparkbot-soul-name").fill("Mobile Socratic Coach");
  await page.getByTestId("sparkbot-soul-content").fill("Ask one concise mobile-friendly question.");
  await page.getByTestId("sparkbot-soul-save").click();
  await expect.poll(() => sparkbot.soulUpdatePayload).toEqual({
    soulId: "socratic",
    payload: {
      name: "Mobile Socratic Coach",
      content: "Ask one concise mobile-friendly question.",
    },
  });

  await page.getByTestId("sparkbot-soul-new").click();
  await page.getByTestId("sparkbot-soul-id").fill("mobile-coach");
  await page.getByTestId("sparkbot-soul-name").fill("Mobile Coach");
  await page.getByTestId("sparkbot-soul-content").fill("Keep guidance short and ask for the learner's next step.");
  await page.getByTestId("sparkbot-soul-save").click();
  await expect.poll(() => sparkbot.soulCreatePayload).toEqual({
    id: "mobile-coach",
    name: "Mobile Coach",
    content: "Keep guidance short and ask for the learner's next step.",
  });
  await expect(page.getByTestId("sparkbot-soul-mobile-coach")).toBeVisible();

  await page.getByTestId("sparkbot-soul-socratic").click();
  await page.getByTestId("sparkbot-soul-delete").click();
  await expect.poll(() => sparkbot.soulDeleteTarget).toBe("socratic");

  await page.getByTestId("sparkbot-channel-toggle").click();
  const globalChannel = page.getByTestId("sparkbot-global-channel-editor");
  await globalChannel.getByTestId("channel-field-send_tool_hints").click();
  await globalChannel.getByTestId("channel-field-transcription_api_key").fill("mobile-transcription-secret");
  await globalChannel.getByRole("button", { name: "保存全局" }).click();
  await expect.poll(() => sparkbot.updatePayload).toEqual(
    expect.objectContaining({
      channels: expect.objectContaining({
        send_progress: true,
        send_tool_hints: true,
        transcription_api_key: "mobile-transcription-secret",
      }),
    }),
  );

  await page.getByTestId("channel-field-welcome_text").fill("Hello from mobile web");
  await page.getByTestId("channel-field-rate_limit").fill("11");
  await page.getByRole("button", { name: "保存渠道" }).click();
  await expect.poll(() => sparkbot.updatePayload).toEqual(
    expect.objectContaining({
      channels: expect.objectContaining({
        web: expect.objectContaining({
          enabled: true,
          welcome_text: "Hello from mobile web",
          rate_limit: 11,
        }),
      }),
    }),
  );
  expect(errors).toEqual([]);
  expect(consoleDomErrors).toEqual([]);
});

test("mobile guide loads sessions and uses websocket controls without DOM errors", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile guide smoke only");
  const errors: string[] = [];
  const consoleDomErrors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (text.includes("insertBefore") || text.includes("Failed to execute")) consoleDomErrors.push(text);
  });
  const guideRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/v1/guide/session/guide-legacy")) guideRequests.push(request.url());
  });
  await mockGuideApis(page);
  await installMockGuideWebSocket(page);

  await page.goto("/guide?session=guide-legacy");
  await expect(page.getByText("healthy").first()).toBeVisible();
  await expect(page.getByText("Legacy Guide Session").first()).toBeVisible();
  await expect(page.getByText("Legacy Guide Point").first()).toBeVisible();

  await page.getByTestId("guide-events-toggle").click();
  const events = page.getByTestId("guide-ws-events");
  await expect(events).toContainText("ws: session_info");
  await expect(events).toContainText("Legacy Guide Session");
  await page.getByTestId("guide-start-rest").click();
  await expect(events).toContainText("send:");
  await expect(events).toContainText("ws: start_result");
  await expect(events).toContainText("WS Started");

  await expect.poll(() => guideRequests.some((url) => url.endsWith("/api/v1/guide/session/guide-legacy"))).toBe(true);
  await expect.poll(() => guideRequests.some((url) => url.endsWith("/api/v1/guide/session/guide-legacy/html"))).toBe(true);
  await expect.poll(() => guideRequests.some((url) => url.endsWith("/api/v1/guide/session/guide-legacy/pages"))).toBe(true);
  const messages = await page.evaluate(() => (window as typeof window & { __guideWsMessages?: Array<Record<string, unknown>> }).__guideWsMessages ?? []);
  expect(messages.some((message) => message.type === "start")).toBe(true);
  const urls = await page.evaluate(() => (window as typeof window & { __guideWsUrls?: string[] }).__guideWsUrls ?? []);
  expect(urls.some((url) => url.includes("/api/v1/guide/ws/guide-legacy"))).toBe(true);
  expect(errors).toEqual([]);
  expect(consoleDomErrors).toEqual([]);
});

test("mobile guide creates saves and deletes sessions without DOM errors", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile guide management smoke only");
  const errors: string[] = [];
  const consoleDomErrors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (text.includes("insertBefore") || text.includes("Failed to execute")) consoleDomErrors.push(text);
  });
  page.on("dialog", (dialog) => void dialog.accept());
  const guide = await mockGuideApis(page);
  await installUnavailableGuideWebSocket(page);

  await page.goto("/guide");
  await page.getByTestId("guide-reference-notebook").selectOption("nb1");
  await page.getByTestId("guide-reference-record-rec-limit").click();
  await page.locator("textarea").first().fill("Guide from notebook context");
  await page.locator("form").first().locator('button[type="submit"]').click();
  await expect.poll(() => guide.createPayload).toEqual(
    expect.objectContaining({
      user_input: "Guide from notebook context",
      notebook_references: [{ notebook_id: "nb1", record_ids: ["rec-limit"] }],
    }),
  );
  await expect(page.getByText("Created Guide Session").first()).toBeVisible();

  await page.getByTestId("guide-events-toggle").click();
  const eventPanel = page.locator("section", { has: page.getByTestId("guide-last-result") });
  await eventPanel.locator("select").selectOption("nb1");
  await eventPanel.locator('button[type="button"]').first().click();
  await expect.poll(() => guide.savedPayload).toEqual(
    expect.objectContaining({
      notebook_ids: ["nb1"],
      record_type: "guided_learning",
      output: expect.stringContaining("Created Guide Page"),
      metadata: expect.objectContaining({
        session_id: "guide-created",
        output_type: "html",
        guide: expect.objectContaining({ title: "Created Guide Session", session_id: "guide-created" }),
      }),
    }),
  );

  await page.getByTestId("guide-delete-session").click();
  await expect.poll(() => guide.deletedSessionId).toBe("guide-created");
  await expect(page.getByText("Other Guide Session").first()).toBeVisible();
  expect(errors).toEqual([]);
  expect(consoleDomErrors).toEqual([]);
});

test("mobile vision uploads images streams analysis and saves output without DOM errors", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile vision smoke only");
  const errors: string[] = [];
  const consoleDomErrors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (text.includes("insertBefore") || text.includes("Failed to execute")) consoleDomErrors.push(text);
  });
  const reference = await mockReferenceApis(page);
  const vision = await mockVisionApis(page);
  await installMockVisionWebSocket(page);

  await page.goto("/vision");
  await page.getByTestId("vision-question").fill("Analyze this uploaded geometry sketch on mobile.");
  await page.getByTestId("vision-file-input").setInputFiles({
    name: "mobile-sketch.png",
    mimeType: "image/png",
    buffer: Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/axj4b8AAAAASUVORK5CYII=",
      "base64",
    ),
  });
  await expect(page.getByTestId("vision-image-preview")).toBeVisible();

  await page.getByTestId("vision-quick-analyze").click();
  await expect.poll(() => vision.analyzePayload).toEqual(
    expect.objectContaining({
      question: "Analyze this uploaded geometry sketch on mobile.",
      image_url: null,
      image_base64: expect.stringContaining("iVBORw0KGgo"),
    }),
  );
  await expect(page.getByTestId("vision-ggb-script")).toContainText("Circle");

  await page.getByTestId("vision-live-solve").click();
  await expect(page.getByTestId("vision-events")).toContainText("bbox_complete");
  await expect(page.getByTestId("vision-answer")).toContainText("先还原");
  await expect(page.getByTestId("vision-ggb-script")).toContainText("Segment");
  await expect
    .poll(() =>
      page.evaluate(() => {
        const state = window as typeof window & { __visionWsMessages?: Array<Record<string, unknown>> };
        return state.__visionWsMessages?.[0] ?? null;
      }),
    )
    .toEqual(
      expect.objectContaining({
        question: "Analyze this uploaded geometry sketch on mobile.",
        image_url: null,
        image_base64: expect.stringContaining("iVBORw0KGgo"),
      }),
    );

  await page.getByTestId("vision-save").click();
  await expect.poll(() => reference.savedPayload).toEqual(
    expect.objectContaining({
      record_type: "solve",
      user_query: "Analyze this uploaded geometry sketch on mobile.",
      output: expect.stringContaining("GeoGebra"),
    }),
  );
  expect(errors).toEqual([]);
  expect(consoleDomErrors).toEqual([]);
});

test("mobile question lab streams topic and mimic generations without DOM errors", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile question lab smoke only");
  const errors: string[] = [];
  const consoleDomErrors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (text.includes("insertBefore") || text.includes("Failed to execute")) consoleDomErrors.push(text);
  });
  const reference = await mockReferenceApis(page);
  await installMockQuestionWebSocket(page);

  await page.goto("/question");
  await page.getByTestId("question-topic-input").fill("Mobile limits practice");
  await page.getByTestId("question-generate-topic").click();
  await expect(page.getByTestId("question-lab-events")).toContainText("progress");
  await expect(page.getByTestId("quiz-viewer")).toBeVisible();
  await page.getByTestId("quiz-option-0-A").click();
  await page.getByTestId("quiz-submit").click();
  await expect(page.getByTestId("quiz-option-0-A")).toBeDisabled();

  await expect
    .poll(() =>
      page.evaluate(() => {
        const state = window as typeof window & { __questionLabWsMessages?: Array<Record<string, unknown>> };
        return state.__questionLabWsMessages?.[0] ?? null;
      }),
    )
    .toEqual(
      expect.objectContaining({
        count: 3,
        requirement: expect.objectContaining({ knowledge_point: "Mobile limits practice" }),
      }),
    );

  await page.getByTestId("question-lab-save").click();
  await expect.poll(() => reference.savedPayload).toEqual(
    expect.objectContaining({
      record_type: "question",
      user_query: "Mobile limits practice",
      output: expect.stringContaining("### 1."),
    }),
  );

  await page.getByTestId("question-mode-mimic").click();
  await page.getByTestId("question-mimic-paper-path").fill("mimic_papers/mobile_exam");
  await page.getByTestId("question-generate-mimic").click();
  await expect(page.getByTestId("question-lab-events")).toContainText("mimic template ready");
  await expect(page.getByText("Mimic problem: which step preserves the same reasoning pattern?")).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(() => {
        const state = window as typeof window & {
          __questionLabWsMessages?: Array<Record<string, unknown>>;
          __questionLabWsUrls?: string[];
        };
        return {
          payload: state.__questionLabWsMessages?.at(-1) ?? null,
          urls: state.__questionLabWsUrls ?? [],
        };
      }),
    )
    .toEqual(
      expect.objectContaining({
        payload: expect.objectContaining({
          mode: "parsed",
          paper_path: "mimic_papers/mobile_exam",
          max_questions: 3,
        }),
        urls: expect.arrayContaining([expect.stringContaining("/question/mimic")]),
      }),
    );
  await page.getByTestId("question-lab-save").click();
  await expect.poll(() => reference.savedPayload).toEqual(
    expect.objectContaining({
      record_type: "question",
      user_query: "mimic_papers/mobile_exam",
      output: expect.stringContaining("Mimic problem: which step preserves the same reasoning pattern?"),
      metadata: expect.objectContaining({ mode: "mimic" }),
    }),
  );
  expect(errors).toEqual([]);
  expect(consoleDomErrors).toEqual([]);
});

test("mobile playground streams tools and capabilities without DOM errors", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile playground smoke only");
  const errors: string[] = [];
  const consoleDomErrors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (text.includes("insertBefore") || text.includes("Failed to execute")) consoleDomErrors.push(text);
  });
  const playground = await mockPlaygroundApis(page);

  await page.goto("/playground");
  await page.getByTestId("playground-registry-mock_tool").click();
  await page.getByTestId("playground-tool-params").fill('{"query":"mobile limits"}');
  await page.getByTestId("playground-tool-run").click();
  await expect.poll(() => playground.toolPayload).toEqual({ params: { query: "mobile limits" } });
  await page.getByTestId("playground-logs-toggle").click();
  await expect(page.getByTestId("playground-logs")).toContainText("tool log received");
  await expect(page.getByTestId("playground-result")).toContainText("tool result");

  await page.getByTestId("playground-tool-run-sync").click();
  await expect.poll(() => playground.syncToolPayload).toEqual({ params: { query: "mobile limits" } });
  await expect(page.getByTestId("playground-result")).toContainText("sync tool result");

  await page.getByTestId("playground-mode-capability").click();
  await page.getByTestId("playground-tool-toggle-mock_tool").click();
  await page.getByTestId("playground-kb-toggle-calc_kb").click();
  await page.getByTestId("playground-capability-content").fill("Explain mobile derivatives");
  await page.getByTestId("playground-capability-run").click();
  await expect.poll(() => playground.capabilityPayload).toEqual(
    expect.objectContaining({
      content: "Explain mobile derivatives",
      tools: ["mock_tool"],
      knowledge_bases: ["calc_kb"],
      language: "zh",
      config: {},
      attachments: [],
    }),
  );
  await expect(page.getByTestId("playground-logs")).toContainText("stream");
  await expect(page.getByTestId("playground-result")).toContainText("capability done");
  expect(errors).toEqual([]);
  expect(consoleDomErrors).toEqual([]);
});

test("mobile memory saves refreshes and clears files without DOM errors", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile memory smoke only");
  const errors: string[] = [];
  const consoleDomErrors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (text.includes("insertBefore") || text.includes("Failed to execute")) consoleDomErrors.push(text);
  });
  page.on("dialog", (dialog) => void dialog.accept());
  const memory = await mockMemoryApis(page);

  await page.goto("/memory");
  await page.getByTestId("learner-profile-tab-memory").click();
  await expect(page.getByTestId("memory-editor")).toHaveValue(/Initial summary/);

  await page.getByTestId("memory-editor").fill("## Mobile updated summary\n- Saved from the redesigned workbench");
  await page.getByTestId("memory-save").click();
  await expect.poll(() => memory.savePayload).toEqual({
    file: "summary",
    content: "## Mobile updated summary\n- Saved from the redesigned workbench",
  });
  await expect.poll(() => memory.getCount).toBeGreaterThanOrEqual(2);
  await expect(page.getByTestId("memory-editor")).toHaveValue(/Mobile updated summary/);

  await expect(page.getByTestId("memory-refresh")).toBeEnabled({ timeout: 15_000 });
  await page.getByTestId("memory-refresh").click();
  await expect
    .poll(() => memory.refreshPayload, { timeout: 15_000 })
    .toEqual({
      session_id: null,
      language: "zh",
    });
  await expect(page.getByTestId("memory-editor")).toHaveValue(/Refreshed summary/);

  await page.getByTestId("memory-clear").click();
  await expect.poll(() => memory.clearPayload).toEqual({ file: "summary" });
  await expect(page.getByTestId("memory-editor")).toHaveValue("");
  expect(errors).toEqual([]);
  expect(consoleDomErrors).toEqual([]);
});

test("mobile chat renders mermaid visualization without DOM errors", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile visualization smoke only");
  const errors: string[] = [];
  const consoleDomErrors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (text.includes("insertBefore") || text.includes("Failed to execute")) consoleDomErrors.push(text);
  });
  await mockReferenceApis(page);
  await installMockWebSocket(page, {
    events: [
      {
        type: "result",
        stage: "final",
        content: "",
        metadata: {
          response: "Mobile Mermaid visualization ready.",
          render_type: "mermaid",
          code: {
            language: "mermaid",
            content: "flowchart TD\nA[Start] --> B[Mobile]",
          },
        },
      },
    ],
  });

  await page.goto("/chat?capability=visualize");
  await page.locator("textarea").first().fill("Render a mobile mermaid diagram");
  await page.getByTestId("chat-send").click();

  await expect(page.getByText("Mobile Mermaid visualization ready.")).toBeVisible();
  await expect(page.getByTestId("mermaid-preview").locator("svg")).toBeVisible();
  expect(errors).toEqual([]);
  expect(consoleDomErrors).toEqual([]);
});

test("mobile chat renders chartjs visualization without DOM errors", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile visualization smoke only");
  const errors: string[] = [];
  const consoleDomErrors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (text.includes("insertBefore") || text.includes("Failed to execute")) consoleDomErrors.push(text);
  });
  await mockReferenceApis(page);
  await installMockWebSocket(page, {
    events: [
      {
        type: "result",
        stage: "final",
        content: "",
        metadata: {
          response: "Mobile Chart.js visualization ready.",
          render_type: "chartjs",
          code: {
            language: "json",
            content: JSON.stringify({
              type: "bar",
              data: {
                labels: ["A", "B"],
                datasets: [
                  {
                    label: "Score",
                    data: [1, 2],
                    backgroundColor: ["#0F766E", "#2563EB"],
                  },
                ],
              },
            }),
          },
        },
      },
    ],
  });

  await page.goto("/chat?capability=visualize");
  await page.locator("textarea").first().fill("Render a mobile chart");
  await page.getByTestId("chat-send").click();

  await expect(page.getByText("Mobile Chart.js visualization ready.")).toBeVisible();
  await expect(page.getByTestId("chartjs-preview").locator("canvas")).toBeVisible();
  expect(errors).toEqual([]);
  expect(consoleDomErrors).toEqual([]);
});

test("mobile chat sends selected context and cancels turns without DOM errors", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile chat protocol smoke only");
  const errors: string[] = [];
  const consoleDomErrors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (text.includes("insertBefore") || text.includes("Failed to execute")) consoleDomErrors.push(text);
  });
  await mockReferenceApis(page);
  await installMockWebSocket(page, {
    holdOpen: true,
    events: [{ type: "progress", stage: "thinking", content: "Mobile context turn is running..." }],
  });

  await page.goto("/chat");
  await page.getByTestId("chat-context-toggle").click();
  const drawer = page.getByTestId("chat-mobile-context-drawer");
  await drawer.getByTestId("context-history-session-old-a").click();
  await drawer.getByTestId("context-record-nb1-rec-limit").click();
  await page.mouse.click(20, 20);
  await expect(drawer).not.toBeVisible();

  await page.locator("textarea").first().fill("Use the selected mobile context.");
  await page.getByTestId("chat-send").click();
  await expect
    .poll(async () =>
      page.evaluate(() => {
        const state = window as typeof window & { __sparkWeaveWsMessages?: Array<Record<string, unknown>> };
        return state.__sparkWeaveWsMessages?.find((message) => message.type === "start_turn") ?? null;
      }),
    )
    .toEqual(
      expect.objectContaining({
        type: "start_turn",
        content: "Use the selected mobile context.",
        history_references: ["session-old-a"],
        notebook_references: [{ notebook_id: "nb1", record_ids: ["rec-limit"] }],
      }),
    );

  await expect(page.getByTestId("chat-cancel")).toBeVisible();
  await page.getByTestId("chat-cancel").click();
  await expect
    .poll(async () =>
      page.evaluate(() => {
        const state = window as typeof window & { __sparkWeaveWsMessages?: Array<Record<string, unknown>> };
        return state.__sparkWeaveWsMessages?.find((message) => message.type === "cancel_turn") ?? null;
      }),
    )
    .toEqual(expect.objectContaining({ type: "cancel_turn", turn_id: "turn-1" }));
  expect(errors).toEqual([]);
  expect(consoleDomErrors).toEqual([]);
});

test("mobile chat renders result-only websocket responses without DOM errors", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile chat result-only smoke only");
  const errors: string[] = [];
  const consoleDomErrors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (text.includes("insertBefore") || text.includes("Failed to execute")) consoleDomErrors.push(text);
  });
  await mockReferenceApis(page);
  await installMockWebSocket(page, {
    resultOnlyContent: "Mobile result-only final answer from metadata.",
  });

  await page.goto("/chat");
  await page.locator("textarea").first().fill("Return a mobile final result only");
  await page.getByTestId("chat-send").click();

  await expect(page.getByText("Mobile result-only final answer from metadata.")).toBeVisible();
  expect(errors).toEqual([]);
  expect(consoleDomErrors).toEqual([]);
});

test("mobile chat records deep question quiz answers without DOM errors", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile quiz result smoke only");
  const errors: string[] = [];
  const consoleDomErrors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (text.includes("insertBefore") || text.includes("Failed to execute")) consoleDomErrors.push(text);
  });
  const reference = await mockReferenceApis(page);
  await installMockWebSocket(page, {
    events: [
      {
        type: "result",
        stage: "final",
        content: "",
        metadata: {
          response: "Mobile quiz ready.",
          summary: {
            success: true,
            completed: 3,
            failed: 0,
            results: [
              {
                success: true,
                qa_pair: {
                  question_id: "mobile-quiz-1",
                  question_type: "choice",
                  question: "Which method should be checked before L'Hopital?",
                  options: { A: "Factorization", B: "Random guessing" },
                  correct_answer: "A",
                  explanation: "Algebraic simplification should be checked first.",
                  difficulty: "medium",
                },
              },
              {
                success: true,
                qa_pair: {
                  question_id: "quiz-2",
                  question_type: "true_false",
                  question: "Gradient descent always finds the global optimum.",
                  options: { True: "Correct", False: "Incorrect" },
                  correct_answer: "False",
                  explanation: "Non-convex objectives can converge to local optima.",
                  difficulty: "easy",
                },
              },
              {
                success: true,
                qa_pair: {
                  question_id: "quiz-3",
                  question_type: "fill_blank",
                  question: "Backpropagation computes ____ using the chain rule.",
                  correct_answer: "gradients",
                  explanation: "Backpropagation propagates gradients layer by layer.",
                  difficulty: "medium",
                },
              },
            ],
          },
        },
      },
    ],
  });

  await page.goto("/chat?capability=deep_question");
  await page.locator("textarea").first().fill("Generate a mobile quiz");
  await page.getByTestId("chat-send").click();

  await expect(page.getByTestId("quiz-viewer")).toBeVisible();
  await page.getByTestId("quiz-option-0-A").click();
  await page.getByTestId("quiz-submit").click();
  await page.getByTestId("quiz-next").click();
  await page.getByTestId("quiz-true-false-1-False").click();
  await page.getByTestId("quiz-submit").click();
  await page.getByTestId("quiz-next").click();
  await page.getByTestId("quiz-fill-blank-input").fill("Gradients");
  await page.getByTestId("quiz-submit").click();

  await expect(page.getByTestId("quiz-recorded")).toBeAttached();
  await expect.poll(() => reference.quizResultPayload).toEqual(
    expect.objectContaining({
      sessionId: "session-new",
      answers: expect.arrayContaining([
        expect.objectContaining({
          question_id: "mobile-quiz-1",
          question_type: "choice",
          user_answer: "A",
          correct_answer: "A",
          is_correct: true,
        }),
        expect.objectContaining({
          question_id: "quiz-2",
          question_type: "true_false",
          user_answer: "False",
          correct_answer: "False",
          is_correct: true,
        }),
        expect.objectContaining({
          question_id: "quiz-3",
          question_type: "fill_blank",
          user_answer: "Gradients",
          correct_answer: "gradients",
          is_correct: true,
        }),
      ]),
    }),
  );
  expect(errors).toEqual([]);
  expect(consoleDomErrors).toEqual([]);
});

test("chat sends selected context references through websocket", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "protocol payload smoke runs once");
  await mockReferenceApis(page);
  await installMockWebSocket(page);

  await page.goto("/chat");
  await page.getByTestId("chat-context-toggle").click();
  const references = page.locator("section", { has: page.getByRole("heading", { name: "引用上下文" }) });
  await expect(references).toBeVisible();
  await references.getByRole("button", { name: /旧会话 A/ }).click();
  await references.getByRole("button", { name: /极限错题/ }).click();
  await page.getByRole("button", { name: "关闭上下文" }).click();

  await page.locator("textarea").first().fill("请结合引用上下文总结要点");
  await page.getByRole("button", { name: /发送/ }).click();

  await expect
    .poll(async () =>
      page.evaluate(() => {
        const state = window as typeof window & { __sparkWeaveWsMessages?: Array<Record<string, unknown>> };
        return state.__sparkWeaveWsMessages?.find((message) => message.type === "start_turn") ?? null;
      }),
    )
    .toEqual(
      expect.objectContaining({
        type: "start_turn",
        content: "请结合引用上下文总结要点",
        history_references: ["session-old-a"],
        notebook_references: [{ notebook_id: "nb1", record_ids: ["rec-limit"] }],
      }),
    );
});

test("chat cancels an in-flight websocket turn", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "cancel protocol smoke runs once");
  await mockReferenceApis(page);
  await installMockWebSocket(page, {
    holdOpen: true,
    events: [{ type: "progress", stage: "thinking", content: "Working through the proof..." }],
  });

  await page.goto("/chat");
  await page.locator("textarea").first().fill("Keep solving until I stop you");
  await page.getByTestId("chat-send").click();

  await expect(page.getByTestId("chat-cancel")).toBeVisible();
  await page.getByTestId("chat-cancel").click();

  await expect
    .poll(async () =>
      page.evaluate(() => {
        const state = window as typeof window & { __sparkWeaveWsMessages?: Array<Record<string, unknown>> };
        return state.__sparkWeaveWsMessages?.find((message) => message.type === "cancel_turn") ?? null;
      }),
    )
    .toEqual(expect.objectContaining({ type: "cancel_turn", turn_id: "turn-1" }));
});

test("chat renders result-only websocket responses", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "result-only websocket smoke runs once");
  await mockReferenceApis(page);
  await installMockWebSocket(page, {
    resultOnlyContent: [
      "Result-only final answer from metadata.",
      "$$\\max_{\\pi_\\theta} \\mathbb{E}_{x \\sim D, y \\sim \\pi_\\theta(y|x)} [r(x,y)]$$ \\tag{1}",
      "$$\\begin{aligned}$$ p(y_w \\succ y_l \\mid x) $$&= \\sigma\\left(\\beta \\log \\frac{\\pi_\\theta(y_w|x)}{\\pi_{\\text{ref}}(y_w|x)} - \\beta \\log \\frac{\\pi_\\theta(y_l|x)}{\\pi_{\\text{ref}}(y_l|x)}\\right) \\\\[4pt]$$ $$&= \\sigma\\left(\\beta \\log \\frac{\\pi_\\theta(y_w|x)\\pi_{\\text{ref}}(y_l|x)}{\\pi_\\theta(y_l|x)\\pi_{\\text{ref}}(y_w|x)}\\right)$$ $$\\end{aligned}$$ \\tag{6}",
      "$$其中 $\\sigma(-u_\\theta)=1-\\sigma(u_\\theta)$。$$",
      "\\lim_{x \\to 0} \\frac{\\sin(2x) - 2x}{x^3} =",
    ].join("\n\n"),
  });

  await page.goto("/chat");
  await page.locator("textarea").first().fill("Return only a final result");
  await page.getByRole("button", { name: /发送/ }).click();

  await expect(page.getByText("Result-only final answer from metadata.")).toBeVisible();
  await expect(page.locator(".katex").first()).toBeVisible();
  await expect(page.locator(".katex-error")).toHaveCount(0);
  await expect(page.getByText("最终回答").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "保存当前结果" })).toBeVisible();
  await expect(page.getByRole("button", { name: "复制" })).toBeVisible();
});

test("chat keeps raw message trace while task snapshot shows completion", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "stage completion smoke runs once");
  await mockReferenceApis(page);
  await installMockWebSocket(page, {
    holdOpen: true,
    events: [
      {
        type: "progress",
        source: "dialogue_coordinator",
        stage: "coordinating",
        content: "Awakened Knowledge Visualization Agent.",
        metadata: { trace_kind: "agent_handoff", profile_hints_applied: true },
      },
      { type: "stage_start", stage: "thinking" },
      { type: "progress", stage: "thinking", content: "Thinking..." },
      { type: "stage_end", stage: "thinking" },
      { type: "stage_start", stage: "responding" },
      { type: "result", stage: "responding", content: "阶段完成后的最终回答。" },
      { type: "stage_end", stage: "responding" },
    ],
  });

  await page.goto("/chat");
  await page.locator("textarea").first().fill("检查阶段状态");
  await page.getByRole("button", { name: /发送/ }).click();

  const messageTrace = page.locator("article").filter({ hasText: "思考过程" }).last();
  const collaboration = page.getByTestId("agent-collaboration").last();
  await expect(collaboration).toContainText("智能体协作");
  await expect(collaboration).toContainText("画像已参与");
  await expect(collaboration).toContainText("对话协调智能体");
  await expect(collaboration).toContainText("讲解智能体");
  await expect(messageTrace).toContainText("stage_start · thinking");
  await expect(messageTrace).toContainText("progress · thinking");
  await expect(messageTrace).toContainText("Thinking...");
  await expect(messageTrace).toContainText("stage_end · responding");

  await page.getByTestId("chat-context-toggle").click();
  const snapshot = page.getByTestId("chat-task-snapshot");
  await expect(page.getByText("阶段完成后的最终回答。").first()).toBeVisible();
  await expect(snapshot).toContainText("已完成");
  await expect(snapshot).toContainText("回答完成");
  await expect(snapshot).not.toContainText("Thinking...");
  await expect(snapshot).not.toContainText("stage_start");
  await expect(snapshot).not.toContainText("· thinking");
});

test("chat renders external video results as learner-facing cards", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "external video smoke runs once");
  const reference = await mockReferenceApis(page);
  await installMockWebSocket(page, {
    events: [
      {
        type: "result",
        stage: "final",
        content: "",
        metadata: {
          success: true,
          render_type: "external_video",
          response: "已为「梯度下降」筛选 2 个公开视频，建议先看第一个。",
          videos: [
            {
              title: "梯度下降直观讲解",
              url: "https://www.bilibili.com/video/BV1gradient01",
              platform: "Bilibili",
              why_recommended: "贴合当前卡点：概念边界不清。已参考学习偏好：公开视频。",
              duration_seconds: 540,
            },
            {
              title: "Gradient Descent Explained",
              url: "https://www.youtube.com/watch?v=abc123",
              platform: "YouTube",
              duration_seconds: 720,
            },
          ],
          agent_chain: [
            { label: "画像智能体", detail: "读取学习偏好。" },
            { label: "视频检索智能体", detail: "检索公开视频。" },
            { label: "筛选智能体", detail: "排序候选。" },
          ],
        },
      },
    ],
  });

  await page.goto("/chat");
  await page.locator("textarea").first().fill("找梯度下降公开视频");
  await page.getByRole("button", { name: /发送/ }).click();

  await expect(page.getByTestId("external-video-viewer")).toBeVisible();
  await expect(page.getByTestId("external-video-watch-plan")).toContainText("先看第一个视频");
  await expect(page.getByTestId("external-video-chain")).toContainText("画像智能体");
  await expect(page.getByText("梯度下降直观讲解")).toBeVisible();
  await expect(page.getByRole("link", { name: "打开观看" }).first()).toBeVisible();

  await page.getByRole("button", { name: "保存当前结果" }).click();
  const modal = page.locator("form", { has: page.getByRole("heading", { name: "保存生成结果" }) });
  await expect(modal.getByText("精选视频 · 2 个").first()).toBeVisible();
  await modal.getByRole("button", { name: "保存" }).click();
  await expect.poll(() => reference.savedPayload).toEqual(
    expect.objectContaining({
      output: expect.stringContaining("## 精选视频"),
      metadata: expect.objectContaining({
        asset_kind: "精选视频 · 2 个",
        external_video: expect.objectContaining({
          render_type: "external_video",
          videos: expect.arrayContaining([
            expect.objectContaining({ title: "梯度下降直观讲解" }),
          ]),
        }),
      }),
    }),
  );
});

test("chat records deep question quiz answers", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "quiz result recording smoke runs once");
  const reference = await mockReferenceApis(page);
  await installMockWebSocket(page, {
    events: [
      {
        type: "result",
        stage: "final",
        content: "",
        metadata: {
          response: "Quiz ready.",
          summary: {
            success: true,
            completed: 3,
            failed: 0,
            results: [
              {
                success: true,
                qa_pair: {
                  question_id: "quiz-1",
                  question_type: "choice",
                  question: "Which method should be checked before L'Hopital?",
                  options: { A: "Factorization", B: "Random guessing" },
                  correct_answer: "A",
                  explanation: "Algebraic simplification should be checked first.",
                  difficulty: "medium",
                },
              },
              {
                success: true,
                qa_pair: {
                  question_id: "quiz-2",
                  question_type: "true_false",
                  question: "Gradient descent always finds the global optimum.",
                  options: { True: "Correct", False: "Incorrect" },
                  correct_answer: "False",
                  explanation: "Non-convex objectives can converge to local optima.",
                  difficulty: "easy",
                },
              },
              {
                success: true,
                qa_pair: {
                  question_id: "quiz-3",
                  question_type: "fill_blank",
                  question: "Backpropagation computes ____ using the chain rule.",
                  correct_answer: "gradients",
                  explanation: "Backpropagation propagates gradients layer by layer.",
                  difficulty: "medium",
                },
              },
            ],
          },
        },
      },
    ],
  });

  await page.goto("/chat?capability=deep_question");
  await page.locator("textarea").first().fill("Generate a quiz");
  await page.getByTestId("chat-send").click();

  await expect(page.getByTestId("quiz-viewer")).toBeVisible();
  await page.getByTestId("quiz-option-0-A").click();
  await page.getByTestId("quiz-submit").click();
  await page.getByTestId("quiz-next").click();
  await page.getByTestId("quiz-true-false-1-False").click();
  await page.getByTestId("quiz-submit").click();
  await page.getByTestId("quiz-next").click();
  await page.getByTestId("quiz-fill-blank-input").fill("Gradients");
  await page.getByTestId("quiz-submit").click();

  await expect(page.getByTestId("quiz-recorded")).toBeAttached();
  await expect.poll(() => reference.quizResultPayload).toEqual(
    expect.objectContaining({
      sessionId: "session-new",
      answers: expect.arrayContaining([
        expect.objectContaining({
          question_id: "quiz-1",
          question_type: "choice",
          user_answer: "A",
          correct_answer: "A",
          is_correct: true,
        }),
        expect.objectContaining({
          question_id: "quiz-2",
          question_type: "true_false",
          user_answer: "False",
          correct_answer: "False",
          is_correct: true,
        }),
        expect.objectContaining({
          question_id: "quiz-3",
          question_type: "fill_blank",
          user_answer: "Gradients",
          correct_answer: "gradients",
          is_correct: true,
        }),
      ]),
    }),
  );
});

test("chat renders mermaid visualization results", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "visualization smoke runs once");
  const references = await mockReferenceApis(page);
  await installMockWebSocket(page, {
    events: [
      {
        type: "result",
        stage: "final",
        content: "",
        metadata: {
          response: "Mermaid visualization ready.",
          render_type: "mermaid",
          code: {
            language: "mermaid",
            content: "flowchart TD\nA[Start] --> B[Finish]",
          },
        },
      },
    ],
  });

  await page.goto("/chat?capability=visualize");
  await page.locator("textarea").first().fill("把流程画成 Mermaid 图");
  await page.getByRole("button", { name: /发送/ }).click();

  await expect(page.getByText("Mermaid visualization ready.")).toBeVisible();
  await expect(page.getByTestId("mermaid-preview").locator("svg")).toBeVisible();
  await expect(page.getByRole("button", { name: "显示代码" })).toBeVisible();

  await page.getByRole("button", { name: "保存当前结果" }).click();
  const modal = page.locator("form", { has: page.getByRole("heading", { name: "保存生成结果" }) });
  await expect(modal.getByText("知识可视化 · mermaid").first()).toBeVisible();
  await modal.getByRole("button", { name: "保存" }).click();

  await expect(page.getByText("已保存为学习资产")).toBeVisible();
  await expect.poll(() => references.savedPayload).toEqual(
    expect.objectContaining({
      record_type: "chat",
      user_query: "把流程画成 Mermaid 图",
      output: expect.stringContaining("```mermaid"),
      metadata: expect.objectContaining({
        asset_kind: "知识可视化 · mermaid",
        visualize: expect.objectContaining({ render_type: "mermaid" }),
      }),
    }),
  );
});

test("chat renders chartjs visualization results", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "visualization smoke runs once");
  await mockReferenceApis(page);
  await installMockWebSocket(page, {
    events: [
      {
        type: "result",
        stage: "final",
        content: "",
        metadata: {
          response: "Chart.js visualization ready.",
          render_type: "chartjs",
          code: {
            language: "json",
            content: JSON.stringify({
              type: "bar",
              data: {
                labels: ["A", "B"],
                datasets: [
                  {
                    label: "Score",
                    data: [1, 2],
                    backgroundColor: ["#0F766E", "#2563EB"],
                  },
                ],
              },
            }),
          },
        },
      },
    ],
  });

  await page.goto("/chat?capability=visualize");
  await page.locator("textarea").first().fill("把数据画成柱状图");
  await page.getByRole("button", { name: /发送/ }).click();

  await expect(page.getByText("Chart.js visualization ready.")).toBeVisible();
  await expect(page.getByTestId("chartjs-preview").locator("canvas")).toBeVisible();
  await expect(page.getByRole("button", { name: "显示代码" })).toBeVisible();
});

async function mockKnowledgeApis(page: import("@playwright/test").Page) {
  const state: { createBody?: string; configBody?: string; created?: boolean } = {};
  await page.route("**/api/v1/system/status", (route) =>
    route.fulfill({
      json: {
        backend: { status: "online" },
        llm: { status: "configured", model: "mock-llm" },
        embeddings: { status: "configured", model: "mock-embedding" },
        search: { status: "optional" },
      },
    }),
  );
  await page.route("**/api/v1/dashboard/recent?**", (route) => route.fulfill({ json: [] }));
  await page.route(/\/api\/v1\/sessions\?/, (route) => route.fulfill({ json: { sessions: [] } }));
  await page.route("**/api/v1/knowledge/health", (route) =>
    route.fulfill({
      json: {
        status: "ok",
        config_file: "C:\\mock\\knowledge\\config.json",
        config_exists: true,
        base_dir: "C:\\mock\\knowledge",
        base_dir_exists: true,
        knowledge_bases_count: state.created ? 1 : 0,
      },
    }),
  );
  await page.route("**/api/v1/knowledge/default", (route) =>
    route.fulfill({ json: { default_kb: state.created ? "calculus_mock" : null } }),
  );
  await page.route("**/api/v1/knowledge/rag-providers", (route) =>
    route.fulfill({
      json: {
        providers: [{ name: "llamaindex", label: "LlamaIndex", available: true, is_default: true }],
        default_provider: "llamaindex",
      },
    }),
  );
  await page.route("**/api/v1/knowledge/list", (route) =>
    route.fulfill({
      json: state.created
        ? [{ name: "calculus_mock", is_default: true, status: "initializing", statistics: {}, progress: { percent: 25 } }]
        : [],
    }),
  );
  await page.route("**/api/v1/knowledge/calculus_mock/progress", (route) =>
    route.fulfill({
      json: { status: "processing", stage: "indexing", message: "Indexing calculus_mock", percent: 25, task_id: "task-create" },
    }),
  );
  await page.route("**/api/v1/knowledge/calculus_mock/progress/clear", (route) =>
    route.fulfill({ json: { status: "success", message: "Progress cleared for calculus_mock" } }),
  );
  await page.route("**/api/v1/knowledge/calculus_mock/config", async (route) => {
    const request = route.request();
    if (request.method() === "PUT") {
      state.configBody = request.postData() ?? "";
      await route.fulfill({
        json: {
          status: "success",
          kb_name: "calculus_mock",
          config: JSON.parse(state.configBody || "{}") as Record<string, unknown>,
        },
      });
      return;
    }
    await route.fulfill({
      json: {
        kb_name: "calculus_mock",
        config: {
          path: "calculus_mock",
          description: "Knowledge base: calculus_mock",
          rag_provider: "llamaindex",
          search_mode: "hybrid",
          needs_reindex: false,
          embedding_model: "text-embedding-3-small",
          embedding_dim: 1536,
        },
      },
    });
  });
  await page.route("**/api/v1/knowledge/configs", (route) =>
    route.fulfill({
      json: {
        defaults: { default_kb: state.created ? "calculus_mock" : null, search_mode: "hybrid" },
        knowledge_bases: state.created
          ? { calculus_mock: { path: "calculus_mock", description: "Knowledge base: calculus_mock" } }
          : {},
      },
    }),
  );
  await page.route("**/api/v1/knowledge/configs/sync", (route) =>
    route.fulfill({ json: { status: "success", message: "Configurations synced from metadata files" } }),
  );
  await page.route("**/api/v1/knowledge/calculus_mock", (route) =>
    route.fulfill({
      json: {
        name: "calculus_mock",
        status: "initializing",
        path: "C:\\mock\\knowledge\\calculus_mock",
        document_count: 1,
        file_count: 1,
        rag_provider: "llamaindex",
        description: "Calculus detail from /api/v1/knowledge/{kb_name}",
        metadata: { stage: "indexing" },
      },
    }),
  );
  await page.route("**/api/v1/knowledge/calculus_mock/linked-folders", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/knowledge/create", async (route) => {
    state.createBody = route.request().postData() ?? "";
    state.created = true;
    await route.fulfill({
      json: {
        message: "Knowledge base created. Processing in background.",
        name: "calculus_mock",
        files: ["limits.md"],
        task_id: "task-create",
      },
    });
  });
  await page.route("**/api/v1/knowledge/tasks/task-create/stream", (route) =>
    route.fulfill({
      status: 200,
      headers: { "Content-Type": "text/event-stream" },
      body: [
        'event: log\ndata: {"line":"Saved 1 file, preparing index","task_id":"task-create"}\n\n',
        'event: complete\ndata: {"detail":"Knowledge base created","task_id":"task-create"}\n\n',
      ].join(""),
    }),
  );
  return state;
}

async function mockKnowledgeManagementApis(page: import("@playwright/test").Page) {
  const state: {
    defaultKb?: string;
    uploadTarget?: string;
    uploadBody?: string;
    linkPayload?: Record<string, unknown>;
    syncTarget?: { kbName: string; folderId: string };
    unlinkTarget?: { kbName: string; folderId: string };
    deletedKb?: string;
    clearedProgress?: string;
  } = { defaultKb: "calculus_mock" };
  let linkedFolderAdded = false;

  const statusPayload = {
    backend: { status: "online" },
    llm: { status: "configured", model: "mock-llm" },
    embeddings: { status: "configured", model: "mock-embedding" },
    search: { status: "optional" },
  };
  const kbList = () => [
    {
      name: "calculus_mock",
      is_default: state.defaultKb === "calculus_mock",
      status: "ready",
      statistics: {},
      progress: { percent: 100, stage: "completed" },
    },
    {
      name: "geometry_mock",
      is_default: state.defaultKb === "geometry_mock",
      status: "ready",
      statistics: {},
      progress: { percent: 100, stage: "completed" },
    },
  ];

  await page.route("**/api/v1/system/status", (route) => route.fulfill({ json: statusPayload }));
  await page.route("**/api/v1/dashboard/recent?**", (route) => route.fulfill({ json: [] }));
  await page.route(/\/api\/v1\/sessions\?/, (route) => route.fulfill({ json: { sessions: [] } }));
  await page.route("**/api/v1/knowledge/health", (route) =>
    route.fulfill({
      json: {
        status: "ok",
        config_file: "C:\\mock\\knowledge\\config.json",
        config_exists: true,
        base_dir: "C:\\mock\\knowledge",
        base_dir_exists: true,
        knowledge_bases_count: 2,
      },
    }),
  );
  await page.route("**/api/v1/knowledge/default", (route) => route.fulfill({ json: { default_kb: state.defaultKb } }));
  await page.route("**/api/v1/knowledge/rag-providers", (route) =>
    route.fulfill({
      json: {
        providers: [{ name: "llamaindex", label: "LlamaIndex", available: true, is_default: true }],
        default_provider: "llamaindex",
      },
    }),
  );
  await page.route("**/api/v1/knowledge/list", (route) => route.fulfill({ json: kbList() }));
  await page.route(/\/api\/v1\/knowledge\/(calculus_mock|geometry_mock)\/progress$/, (route) =>
    route.fulfill({
      json: { status: "ready", stage: "completed", message: "Index ready", percent: 100 },
    }),
  );
  await page.route(/\/api\/v1\/knowledge\/(calculus_mock|geometry_mock)\/progress\/clear$/, async (route) => {
    const kbName = route.request().url().match(/\/knowledge\/([^/]+)\/progress\/clear$/)?.[1] ?? "";
    state.clearedProgress = kbName;
    await route.fulfill({ json: { status: "success", message: `Progress cleared for ${kbName}` } });
  });
  await page.route(/\/api\/v1\/knowledge\/(calculus_mock|geometry_mock)\/config$/, async (route) => {
    const kbName = route.request().url().match(/\/knowledge\/([^/]+)\/config$/)?.[1] ?? "geometry_mock";
    await route.fulfill({
      json: {
        kb_name: kbName,
        config: {
          path: kbName,
          description: `Knowledge base: ${kbName}`,
          rag_provider: "llamaindex",
          search_mode: "hybrid",
          needs_reindex: false,
          embedding_model: "text-embedding-3-small",
          embedding_dim: 1536,
        },
      },
    });
  });
  await page.route("**/api/v1/knowledge/configs", (route) =>
    route.fulfill({
      json: {
        defaults: { default_kb: state.defaultKb, search_mode: "hybrid" },
        knowledge_bases: {
          calculus_mock: { path: "calculus_mock", description: "Knowledge base: calculus_mock" },
          geometry_mock: { path: "geometry_mock", description: "Knowledge base: geometry_mock" },
        },
      },
    }),
  );
  await page.route("**/api/v1/knowledge/configs/sync", (route) =>
    route.fulfill({ json: { status: "success", message: "Configurations synced from metadata files" } }),
  );
  await page.route(/\/api\/v1\/knowledge\/geometry_mock\/linked-folders$/, async (route) => {
    if (route.request().method() !== "GET") {
      await route.fulfill({ status: 405, json: { detail: "Method not allowed" } });
      return;
    }
    await route.fulfill({
      json: [
        {
          id: "folder-1",
          path: "C:\\course\\geometry",
          added_at: "2026-04-20T08:00:00",
          file_count: linkedFolderAdded ? 4 : 3,
        },
      ],
    });
  });
  await page.route(/\/api\/v1\/knowledge\/calculus_mock\/linked-folders$/, (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/knowledge/geometry_mock/link-folder", async (route) => {
    state.linkPayload = route.request().postDataJSON() as Record<string, unknown>;
    linkedFolderAdded = true;
    await route.fulfill({
      json: {
        id: "folder-1",
        path: String(state.linkPayload.folder_path ?? ""),
        added_at: "2026-04-20T08:10:00",
        file_count: 4,
      },
    });
  });
  await page.route("**/api/v1/knowledge/geometry_mock/sync-folder/folder-1", async (route) => {
    state.syncTarget = { kbName: "geometry_mock", folderId: "folder-1" };
    await route.fulfill({
      json: {
        message: "Folder sync queued",
        name: "geometry_mock",
        files: [{ path: "triangles.md" }],
        task_id: "task-sync",
      },
    });
  });
  await page.route("**/api/v1/knowledge/geometry_mock/linked-folders/folder-1", async (route) => {
    if (route.request().method() !== "DELETE") {
      await route.fulfill({ status: 405, json: { detail: "Method not allowed" } });
      return;
    }
    state.unlinkTarget = { kbName: "geometry_mock", folderId: "folder-1" };
    await route.fulfill({ json: { message: "Folder unlinked", folder_id: "folder-1" } });
  });
  await page.route("**/api/v1/knowledge/default/geometry_mock", async (route) => {
    state.defaultKb = "geometry_mock";
    await route.fulfill({ json: { status: "success", default_kb: "geometry_mock" } });
  });
  await page.route("**/api/v1/knowledge/geometry_mock/upload", async (route) => {
    state.uploadTarget = "geometry_mock";
    state.uploadBody = route.request().postData() ?? "";
    await route.fulfill({
      json: {
        message: "Uploaded 1 file. Processing in background.",
        name: "geometry_mock",
        files: ["triangles.md"],
        task_id: "task-upload",
      },
    });
  });
  await page.route("**/api/v1/knowledge/tasks/task-upload/stream", (route) =>
    route.fulfill({
      status: 200,
      headers: { "Content-Type": "text/event-stream" },
      body: 'event: complete\ndata: {"detail":"Upload complete","task_id":"task-upload"}\n\n',
    }),
  );
  await page.route("**/api/v1/knowledge/tasks/task-sync/stream", (route) =>
    route.fulfill({
      status: 200,
      headers: { "Content-Type": "text/event-stream" },
      body: 'event: complete\ndata: {"detail":"Folder sync complete","task_id":"task-sync"}\n\n',
    }),
  );
  await page.route("**/api/v1/knowledge/calculus_mock", async (route) => {
    if (route.request().method() !== "GET") {
      await route.fulfill({ status: 405, json: { detail: "Method not allowed" } });
      return;
    }
    await route.fulfill({
      json: {
        name: "calculus_mock",
        status: "ready",
        path: "C:\\mock\\knowledge\\calculus_mock",
        document_count: 5,
        file_count: 2,
        rag_provider: "llamaindex",
        description: "Calculus vector store ready",
        metadata: { topic: "limits" },
      },
    });
  });
  await page.route("**/api/v1/knowledge/geometry_mock", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        json: {
          name: "geometry_mock",
          status: "ready",
          path: "C:\\mock\\knowledge\\geometry_mock",
          document_count: 8,
          file_count: linkedFolderAdded ? 4 : 3,
          rag_provider: "llamaindex",
          description: "Geometry vector store ready",
          metadata: { topic: "triangles", source: "folder sync" },
        },
      });
      return;
    }
    if (route.request().method() !== "DELETE") {
      await route.fulfill({ status: 405, json: { detail: "Method not allowed" } });
      return;
    }
    state.deletedKb = "geometry_mock";
    await route.fulfill({ json: { success: true, message: "Knowledge base deleted" } });
  });
  return state;
}

async function installMockKnowledgeProgressWebSocket(page: import("@playwright/test").Page) {
  await page.addInitScript(() => {
    const state = window as typeof window & { __knowledgeWsUrls?: string[] };
    state.__knowledgeWsUrls = [];

    class MockKnowledgeProgressWebSocket {
      static readonly CONNECTING = 0;
      static readonly OPEN = 1;
      static readonly CLOSING = 2;
      static readonly CLOSED = 3;

      readonly url: string;
      readyState = MockKnowledgeProgressWebSocket.CONNECTING;
      onopen: ((event: Event) => void) | null = null;
      onmessage: ((event: MessageEvent<string>) => void) | null = null;
      onerror: ((event: Event) => void) | null = null;
      onclose: ((event: CloseEvent) => void) | null = null;

      constructor(url: string | URL) {
        this.url = String(url);
        state.__knowledgeWsUrls?.push(this.url);
        window.setTimeout(() => {
          this.readyState = MockKnowledgeProgressWebSocket.OPEN;
          this.onopen?.(new Event("open"));
          this.onmessage?.(
            new MessageEvent("message", {
              data: JSON.stringify({ type: "heartbeat", debug: { raw: true } }),
            }),
          );
          this.emitProgress({ stage: "parsing", message: "WS parsing files", percent: 55, task_id: "task-create" });
          window.setTimeout(() => {
            this.emitProgress({ stage: "completed", message: "WS index complete", percent: 100, task_id: "task-create" });
            this.close();
          }, 0);
        }, 0);
      }

      send() {
        // The knowledge progress channel is server-push only.
      }

      close() {
        if (this.readyState === MockKnowledgeProgressWebSocket.CLOSED) return;
        this.readyState = MockKnowledgeProgressWebSocket.CLOSED;
        this.onclose?.(new CloseEvent("close"));
      }

      private emitProgress(data: Record<string, unknown>) {
        this.onmessage?.(
          new MessageEvent("message", {
            data: JSON.stringify({ type: "progress", data }),
          }),
        );
      }
    }

    window.WebSocket = MockKnowledgeProgressWebSocket as unknown as typeof WebSocket;
  });
}

async function mockPlaygroundApis(page: import("@playwright/test").Page) {
  const state: {
    toolPayload?: Record<string, unknown>;
    syncToolPayload?: Record<string, unknown>;
    capabilityPayload?: Record<string, unknown>;
  } = {};

  await page.route("**/api/v1/system/status", (route) =>
    route.fulfill({
      json: {
        backend: { status: "online" },
        llm: { status: "configured", model: "mock-llm" },
        embeddings: { status: "configured", model: "mock-embedding" },
        search: { status: "optional" },
      },
    }),
  );
  await page.route("**/api/v1/dashboard/recent?**", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/knowledge/list", (route) =>
    route.fulfill({
      json: [{ name: "calc_kb", is_default: true, file_count: 2, status: "ready" }],
    }),
  );
  await page.route("**/api/v1/plugins/list", (route) =>
    route.fulfill({
      json: {
        tools: [
          {
            name: "mock_tool",
            description: "Mock streaming tool",
            parameters: [{ name: "query", type: "string", required: true, default: "limits" }],
          },
        ],
        capabilities: [
          {
            name: "mock_capability",
            description: "Mock LangGraph capability",
            stages: ["plan", "answer"],
            tools_used: ["mock_tool"],
          },
        ],
        plugins: [{ name: "mock_plugin", type: "local", description: "Mock plugin manifest" }],
      },
    }),
  );
  await page.route("**/api/v1/plugins/tools/mock_tool/execute-stream", async (route) => {
    state.toolPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      headers: { "Content-Type": "text/event-stream" },
      body: [
        'event: log\ndata: {"line":"tool log received"}\n\n',
        'event: result\ndata: {"success":true,"content":"tool result","elapsed_ms":7}\n\n',
      ].join(""),
    });
  });
  await page.route("**/api/v1/plugins/tools/mock_tool/execute", async (route) => {
    state.syncToolPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      json: {
        success: true,
        content: "sync tool result",
        sources: [],
        metadata: { elapsed_ms: 3 },
      },
    });
  });
  await page.route("**/api/v1/plugins/capabilities/mock_capability/execute-stream", async (route) => {
    state.capabilityPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      headers: { "Content-Type": "text/event-stream" },
      body: [
        'event: stream\ndata: {"type":"progress","stage":"plan","content":"stream planning"}\n\n',
        'event: result\ndata: {"success":true,"data":{"response":"capability done"},"elapsed_ms":9}\n\n',
      ].join(""),
    });
  });
  return state;
}

async function mockMemoryApis(page: import("@playwright/test").Page) {
  const state: {
    getCount: number;
    savePayload?: Record<string, unknown>;
    refreshPayload?: Record<string, unknown>;
    clearPayload?: Record<string, unknown>;
    snapshot: {
      summary: string;
      profile: string;
      summary_updated_at: string | null;
      profile_updated_at: string | null;
    };
  } = {
    getCount: 0,
    snapshot: {
      summary: "## Initial summary\n- The learner is reviewing limits.",
      profile: "## Profile\n- Prefers short worked examples.",
      summary_updated_at: "2026-04-20T08:00:00.000Z",
      profile_updated_at: "2026-04-20T08:05:00.000Z",
    },
  };

  const setFile = (file: unknown, content: string, updatedAt: string | null) => {
    if (file === "profile") {
      state.snapshot.profile = content;
      state.snapshot.profile_updated_at = updatedAt;
      return;
    }
    state.snapshot.summary = content;
    state.snapshot.summary_updated_at = updatedAt;
  };

  const learnerProfile = {
    version: 1,
    generated_at: "2026-05-02T00:00:00.000Z",
    confidence: 0.82,
    overview: {
      current_focus: "极限概念回顾",
      preferred_time_budget_minutes: 10,
      summary: "先把极限直觉补清楚，再继续做题。",
    },
    stable_profile: {
      goals: ["高等数学复习"],
      preferences: ["短例题", "图解"],
      strengths: ["能根据步骤复盘"],
      constraints: ["希望一次只做一件事"],
    },
    learning_state: {
      weak_points: [{ label: "左右极限辨析", confidence: 0.7, evidence_count: 2, severity: "medium", source_ids: [] }],
      mastery: [],
    },
    next_action: {
      kind: "weak_point",
      title: "前测补基：左右极限辨析",
      summary: "用 10 分钟做一个小诊断，确认左右极限的判断边界。",
      primary_label: "进入导学",
      estimated_minutes: 10,
      source_type: "weak_point",
      source_label: "左右极限辨析",
      confidence: 0.8,
      suggested_prompt: "左右极限辨析",
    },
    recommendations: ["先看图解，再做两道判断题。"],
    sources: [],
    evidence_preview: [],
    data_quality: { source_count: 2, evidence_count: 4, calibration_count: 0 },
  };

  await page.route("**/api/v1/system/status", (route) =>
    route.fulfill({
      json: {
        backend: { status: "online" },
        llm: { status: "configured", model: "mock-llm" },
        embeddings: { status: "configured", model: "mock-embedding" },
        search: { status: "optional" },
      },
    }),
  );
  await page.route("**/api/v1/knowledge/list", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/dashboard/recent?**", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/learner-profile", (route) => route.fulfill({ json: learnerProfile }));
  await page.route("**/api/v1/learner-profile/refresh", (route) => route.fulfill({ json: learnerProfile }));
  await page.route(/\/api\/v1\/sessions\?/, (route) =>
    route.fulfill({
      json: {
        sessions: [
          {
            id: "session-memory",
            session_id: "session-memory",
            title: "Memory source session",
            created_at: 1_700_000_000,
            updated_at: 1_700_000_300,
            message_count: 6,
            preferences: { capability: "chat", tools: [], knowledge_bases: [], language: "zh" },
          },
        ],
      },
    }),
  );
  await page.route("**/api/v1/memory", async (route) => {
    const method = route.request().method();
    if (method === "GET") {
      state.getCount += 1;
      await route.fulfill({ json: state.snapshot });
      return;
    }
    if (method === "PUT") {
      state.savePayload = route.request().postDataJSON() as Record<string, unknown>;
      setFile(state.savePayload.file, String(state.savePayload.content ?? ""), "2026-04-20T08:10:00.000Z");
      await route.fulfill({ json: { ...state.snapshot, saved: true } });
      return;
    }
    await route.fulfill({ status: 405, json: { detail: "Method not allowed" } });
  });
  await page.route("**/api/v1/memory/refresh", async (route) => {
    state.refreshPayload = route.request().postDataJSON() as Record<string, unknown>;
    setFile("summary", "## Refreshed summary\n- Rebuilt from session-memory.", "2026-04-20T08:12:00.000Z");
    await route.fulfill({ json: { ...state.snapshot, changed: true } });
  });
  await page.route("**/api/v1/memory/clear", async (route) => {
    state.clearPayload = route.request().postDataJSON() as Record<string, unknown>;
    if (state.clearPayload.file) {
      setFile(state.clearPayload.file, "", null);
    } else {
      setFile("summary", "", null);
      setFile("profile", "", null);
    }
    await route.fulfill({ json: { ...state.snapshot, cleared: true } });
  });
  return state;
}

async function mockReferenceApis(page: import("@playwright/test").Page) {
  const state: {
    savedPayload?: Record<string, unknown>;
    sessionRenamePayload?: { sessionId: string; title: string };
    sessionDeleteTarget?: string;
    quizResultPayload?: { sessionId: string; answers: Array<Record<string, unknown>> };
    calibrationPayload?: Record<string, unknown>;
  } = {};
  let chatSessions = [
    {
      id: "session-old-a",
      session_id: "session-old-a",
      title: "旧会话 A",
      created_at: 1_700_000_000,
      updated_at: 1_700_000_200,
      message_count: 4,
      preferences: { capability: "chat", tools: [], knowledge_bases: [], language: "zh" },
    },
  ];
  const learnerProfile = {
    version: 1,
    generated_at: "2026-05-02T00:00:00.000Z",
    confidence: 0.86,
    overview: {
      current_focus: "梯度下降的直观理解",
      preferred_time_budget_minutes: 10,
      summary: "当前主要需要把梯度下降和优化目标之间的关系讲清楚。",
    },
    stable_profile: {
      goals: ["机器学习基础入门"],
      preferences: ["图解", "练习", "公开视频"],
      strengths: ["能跟随例题"],
      constraints: ["希望一次只做一件事"],
    },
    learning_state: {
      weak_points: [{ label: "概念边界不清", confidence: 0.78, evidence_count: 2, severity: "medium", source_ids: [] }],
      mastery: [],
    },
    next_action: {
      kind: "weak_point",
      title: "前测补基：梯度下降的直观理解",
      summary: "先用 10 分钟补齐直觉，再回到当前机器学习任务。",
      primary_label: "进入导学",
      estimated_minutes: 10,
      source_type: "weak_point",
      source_label: "概念边界不清",
      confidence: 0.84,
      suggested_prompt: "梯度下降的直观理解",
    },
    recommendations: ["先看一张图解，再做一组短练习。"],
    sources: [],
    evidence_preview: [],
    data_quality: { source_count: 3, evidence_count: 5, calibration_count: 0 },
  };
  await page.route("**/api/v1/system/status", (route) =>
    route.fulfill({
      json: {
        backend: { status: "online" },
        llm: { status: "configured", model: "mock-llm" },
        embeddings: { status: "configured", model: "mock-embedding" },
        search: { status: "optional" },
      },
    }),
  );
  await page.route("**/api/v1/knowledge/list", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/dashboard/recent?**", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/learner-profile", (route) => route.fulfill({ json: learnerProfile }));
  await page.route("**/api/v1/learner-profile/refresh", (route) => route.fulfill({ json: learnerProfile }));
  await page.route("**/api/v1/learner-profile/calibrations", async (route) => {
    state.calibrationPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      json: {
        event: { evidence_id: "calibration-1" },
        profile: {
          ...learnerProfile,
          data_quality: { ...learnerProfile.data_quality, calibration_count: 1 },
        },
      },
    });
  });
  await page.route(/\/api\/v1\/sessions\?/, (route) => route.fulfill({ json: { sessions: chatSessions } }));
  await page.route(/\/api\/v1\/sessions\/session-old-a$/, async (route) => {
    const sessionId = decodeURIComponent(route.request().url().match(/\/api\/v1\/sessions\/([^/?#]+)$/)?.[1] ?? "");
    const session = chatSessions.find((item) => item.session_id === sessionId) ?? chatSessions[0];
    if (route.request().method() === "PATCH") {
      const payload = route.request().postDataJSON() as { title?: string };
      state.sessionRenamePayload = { sessionId, title: String(payload.title ?? "") };
      chatSessions = chatSessions.map((item) =>
        item.session_id === sessionId ? { ...item, title: state.sessionRenamePayload?.title ?? item.title } : item,
      );
      await route.fulfill({ json: { session: chatSessions.find((item) => item.session_id === sessionId) ?? session } });
      return;
    }
    if (route.request().method() === "DELETE") {
      state.sessionDeleteTarget = sessionId;
      chatSessions = chatSessions.filter((item) => item.session_id !== sessionId);
      await route.fulfill({ json: { deleted: true, session_id: sessionId } });
      return;
    }
    await route.fulfill({
      json: {
        ...session,
        active_turn_id: "turn-loaded",
        messages: [
          { id: "m-user", role: "user", content: "Loaded user question", created_at: 1_700_000_010 },
          { id: "m-assistant", role: "assistant", content: "Loaded assistant answer", created_at: 1_700_000_020 },
        ],
      },
    });
  });
  await page.route("**/api/v1/notebook/list", (route) =>
    route.fulfill({
      json: {
        notebooks: [{ id: "nb1", name: "复盘本", description: "错题和推理沉淀", record_count: 1 }],
        total: 1,
      },
    }),
  );
  await page.route("**/api/v1/notebook/nb1", (route) =>
    route.fulfill({
      json: {
        id: "nb1",
        name: "复盘本",
        description: "错题和推理沉淀",
        records: [
          {
            id: "rec-limit",
            record_type: "chat",
            title: "极限错题",
            summary: "洛必达法则适用条件和常见误区。",
            user_query: "解释这道极限题",
            output: "先验证 0/0 型，再检查可导性。",
            created_at: 1_700_000_300,
          },
        ],
      },
    }),
  );
  await page.route("**/api/v1/notebook/add_record", async (route) => {
    state.savedPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      json: {
        success: true,
        added_to_notebooks: ["nb1"],
        record: { id: "saved-learning-asset", record_type: state.savedPayload.record_type, title: state.savedPayload.title },
      },
    });
  });
  await page.route(/\/api\/v1\/sessions\/([^/?#]+)\/quiz-results$/, async (route) => {
    const sessionId = decodeURIComponent(route.request().url().match(/\/api\/v1\/sessions\/([^/?#]+)\/quiz-results$/)?.[1] ?? "");
    const body = route.request().postDataJSON() as { answers?: Array<Record<string, unknown>> };
    state.quizResultPayload = { sessionId, answers: body.answers ?? [] };
    await route.fulfill({
      json: {
        recorded: true,
        session_id: sessionId,
        answer_count: state.quizResultPayload.answers.length,
        notebook_count: 1,
      },
    });
  });
  return state;
}

async function mockSparkBotApis(page: import("@playwright/test").Page) {
  const state: {
    updatePayload?: Record<string, unknown>;
    agentDetailTarget?: string;
    recentLimit?: number;
    soulDetailTarget?: string;
    soulCreatePayload?: Record<string, unknown>;
    soulUpdatePayload?: { soulId: string; payload: Record<string, unknown> };
    soulDeleteTarget?: string;
    fileWritePayload?: { botId: string; filename: string; content: string };
    startPayload?: Record<string, unknown>;
    stopTarget?: string;
    destroyTarget?: string;
  } = {};
  const mathFiles: Record<string, string> = { "SOUL.md": "# Math Bot" };
  await page.route("**/api/v1/system/status", (route) =>
    route.fulfill({
      json: {
        backend: { status: "online" },
        llm: { status: "configured", model: "mock-llm" },
        embeddings: { status: "configured", model: "mock-embedding" },
        search: { status: "optional" },
      },
    }),
  );
  await page.route("**/api/v1/knowledge/list", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/dashboard/recent?**", (route) => route.fulfill({ json: [] }));
  await page.route(/\/api\/v1\/sessions\?/, (route) => route.fulfill({ json: { sessions: [] } }));
  await page.route("**/api/v1/agent-config/agents", (route) =>
    route.fulfill({
      json: {
        solve: { icon: "HelpCircle", color: "blue", label_key: "Problem Solved" },
        question: { icon: "FileText", color: "red", label_key: "Question Generated" },
        research: { icon: "Search", color: "teal", label_key: "Research Report" },
        co_writer: { icon: "PenTool", color: "blue", label_key: "Co-Writer" },
        guide: { icon: "BookOpen", color: "teal", label_key: "Guided Learning" },
      },
    }),
  );
  await page.route(/\/api\/v1\/agent-config\/agents\/([^/]+)$/, async (route) => {
    const agentType = route.request().url().match(/\/agent-config\/agents\/([^/]+)$/)?.[1] ?? "solve";
    state.agentDetailTarget = agentType;
    const configs: Record<string, Record<string, string>> = {
      solve: { icon: "HelpCircle", color: "blue", label_key: "Problem Solved" },
      question: { icon: "FileText", color: "red", label_key: "Question Generated" },
      research: { icon: "Search", color: "teal", label_key: "Research Report" },
      co_writer: { icon: "PenTool", color: "blue", label_key: "Co-Writer" },
      guide: { icon: "BookOpen", color: "teal", label_key: "Guided Learning" },
    };
    await route.fulfill({ json: configs[agentType] ?? { error: `Agent type '${agentType}' not found` } });
  });
  await page.route(/\/api\/v1\/(?:sparkbot|sparkbot)\/channels\/schema$/, (route) =>
    route.fulfill({
      json: {
        global: {
          secret_fields: ["transcription_api_key"],
          json_schema: {
            type: "object",
            properties: {
              send_progress: { type: "boolean", title: "Send progress", default: true },
              send_tool_hints: { type: "boolean", title: "Send tool hints", default: false },
              transcription_api_key: { type: "string", title: "Transcription API key", default: "" },
            },
          },
        },
        channels: {
          web: {
            name: "web",
            display_name: "Web",
            default_config: { enabled: true, welcome_text: "Welcome", rate_limit: 3 },
            secret_fields: [],
            json_schema: {
              type: "object",
              properties: {
                enabled: { type: "boolean", title: "启用渠道", description: "Use the built-in web channel." },
                welcome_text: { type: "string", title: "Welcome text", description: "First reply shown in the web channel." },
                rate_limit: { type: "integer", title: "Rate limit", description: "Messages per minute." },
              },
            },
          },
        },
      },
    }),
  );
  let souls = [
    {
      id: "socratic",
      name: "Socratic Coach",
      content: "Ask one guiding question at a time.",
    },
  ];
  await page.route(/\/api\/v1\/(?:sparkbot|sparkbot)\/souls$/, async (route) => {
    if (route.request().method() === "POST") {
      const payload = route.request().postDataJSON() as Record<string, unknown>;
      state.soulCreatePayload = payload;
      const nextSoul = {
        id: String(payload.id ?? ""),
        name: String(payload.name ?? payload.id ?? ""),
        content: String(payload.content ?? ""),
      };
      souls = [nextSoul, ...souls.filter((soul) => soul.id !== nextSoul.id)];
      await route.fulfill({ json: nextSoul });
      return;
    }
    await route.fulfill({ json: souls });
  });
  await page.route(/\/api\/v1\/(?:sparkbot|sparkbot)\/souls\/([^/?#]+)$/, async (route) => {
    const soulId = decodeURIComponent(route.request().url().match(/\/(?:sparkbot|sparkbot)\/souls\/([^/?#]+)$/)?.[1] ?? "socratic");
    const soul = souls.find((item) => item.id === soulId) ?? { id: soulId, name: soulId, content: "" };
    state.soulDetailTarget = soulId;
    if (route.request().method() === "PUT") {
      const payload = route.request().postDataJSON() as Record<string, unknown>;
      state.soulUpdatePayload = { soulId, payload };
      const nextSoul = { ...soul, ...payload, id: soulId };
      souls = souls.map((item) => (item.id === soulId ? nextSoul : item));
      await route.fulfill({ json: nextSoul });
      return;
    }
    if (route.request().method() === "DELETE") {
      state.soulDeleteTarget = soulId;
      souls = souls.filter((item) => item.id !== soulId);
      await route.fulfill({ json: { id: soulId, deleted: true } });
      return;
    }
    await route.fulfill({ json: soul });
  });
  await page.route(/\/api\/v1\/(?:sparkbot|sparkbot)\/recent\?limit=(\d+)/, async (route) => {
    const limit = Number(route.request().url().match(/limit=(\d+)/)?.[1] ?? "0");
    state.recentLimit = limit;
    await route.fulfill({
      json: [
        {
          bot_id: "math_bot",
          name: "Math Bot",
          running: true,
          last_message: "Last geometry reminder",
          updated_at: "2026-04-26T10:00:00",
        },
        {
          bot_id: "writing_bot",
          name: "Writing Bot",
          running: false,
          last_message: "Draft feedback summary",
          updated_at: "2026-04-26T09:30:00",
        },
      ].slice(0, limit || 2),
    });
  });
  await page.route(/\/api\/v1\/(?:sparkbot|sparkbot)\/math_bot\?include_secrets=true$/, (route) =>
    route.fulfill({
      json: {
        bot_id: "math_bot",
        name: "Math Bot",
        description: "Legacy route target",
        model: "gpt-mock",
        persona: "Patient math tutor",
        auto_start: true,
        running: true,
        tools: {
          exec: { timeout: 60, pathAppend: "" },
          web: { proxy: null, fetchMaxChars: 50000, search: { provider: "brave", apiKey: "", baseUrl: "", maxResults: 5 } },
          restrictToWorkspace: true,
          mcpServers: {},
        },
        agent: {
          maxToolIterations: 4,
          toolCallLimit: 5,
          maxTokens: 8192,
          contextWindowTokens: 65536,
          temperature: 0.1,
          reasoningEffort: null,
          teamMaxWorkers: 5,
          teamWorkerMaxIterations: 25,
        },
        heartbeat: { enabled: true, intervalS: 1800 },
        channels: { send_progress: true, send_tool_hints: false, web: { enabled: true, welcome_text: "Welcome", rate_limit: 3 } },
      },
    }),
  );
  await page.route(/\/api\/v1\/(?:sparkbot|sparkbot)\/writing_bot\?include_secrets=true$/, (route) =>
    route.fulfill({
      json: {
        bot_id: "writing_bot",
        name: "Writing Bot",
        description: "Secondary bot",
        model: "gpt-writing",
        persona: "Writing feedback coach",
        auto_start: false,
        running: false,
        tools: {
          exec: { timeout: 60, pathAppend: "" },
          web: { proxy: null, fetchMaxChars: 50000, search: { provider: "brave", apiKey: "", baseUrl: "", maxResults: 5 } },
          restrictToWorkspace: true,
          mcpServers: {},
        },
        agent: {
          maxToolIterations: 4,
          toolCallLimit: 5,
          maxTokens: 8192,
          contextWindowTokens: 65536,
          temperature: 0.1,
          reasoningEffort: null,
          teamMaxWorkers: 5,
          teamWorkerMaxIterations: 25,
        },
        heartbeat: { enabled: true, intervalS: 1800 },
        channels: { send_progress: true, send_tool_hints: false, web: { enabled: true, welcome_text: "Welcome", rate_limit: 3 } },
      },
    }),
  );
  await page.route(/\/api\/v1\/(?:sparkbot|sparkbot)\/math_bot$/, async (route) => {
    if (route.request().method() === "DELETE") {
      state.stopTarget = "math_bot";
      await route.fulfill({ json: { bot_id: "math_bot", stopped: true } });
      return;
    }
    if (route.request().method() !== "PATCH") {
      await route.fallback();
      return;
    }
    state.updatePayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      json: {
        bot_id: "math_bot",
        name: "Math Bot",
        description: "Legacy route target",
        running: true,
        ...state.updatePayload,
      },
    });
  });
  await page.route(/\/api\/v1\/(?:sparkbot|sparkbot)\/writing_bot\/destroy$/, async (route) => {
    state.destroyTarget = "writing_bot";
    await route.fulfill({ json: { bot_id: "writing_bot", destroyed: true } });
  });
  await page.route(/\/api\/v1\/(?:sparkbot|sparkbot)\/math_bot\/files$/, (route) =>
    route.fulfill({
      json: Object.entries(mathFiles).map(([filename, content]) => ({ filename, content })),
    }),
  );
  await page.route(/\/api\/v1\/(?:sparkbot|sparkbot)\/math_bot\/files\/([^/?#]+)$/, async (route) => {
    const filename = decodeURIComponent(route.request().url().match(/\/files\/([^/?#]+)$/)?.[1] ?? "SOUL.md");
    if (route.request().method() === "PUT") {
      const payload = route.request().postDataJSON() as { content?: string };
      mathFiles[filename] = String(payload.content ?? "");
      state.fileWritePayload = { botId: "math_bot", filename, content: mathFiles[filename] };
      await route.fulfill({ json: { filename, saved: true } });
      return;
    }
    await route.fulfill({ json: { filename, content: mathFiles[filename] ?? "" } });
  });
  await page.route(/\/api\/v1\/(?:sparkbot|sparkbot)\/writing_bot\/files$/, (route) =>
    route.fulfill({
      json: [{ filename: "SOUL.md", content: "# Writing Bot" }],
    }),
  );
  await page.route(/\/api\/v1\/(?:sparkbot|sparkbot)\/writing_bot\/files\/SOUL\.md$/, (route) =>
    route.fulfill({
      json: { filename: "SOUL.md", content: "# Writing Bot" },
    }),
  );
  await page.route(/\/api\/v1\/(?:sparkbot|sparkbot)\/math_bot\/history\?limit=50$/, (route) =>
    route.fulfill({
      json: {
        history: [
          {
            timestamp: "2026-04-26T10:10:00",
            channel: "web",
            chat_id: "web",
            user: "How should I review limits?",
            assistant: "Start from the definition and log common mistakes.",
          },
          {
            timestamp: "2026-04-26T10:12:00",
            role: "assistant",
            content: "Remember to ask one guiding question at a time.",
            channel: "web",
          },
        ],
      },
    }),
  );
  await page.route(/\/api\/v1\/(?:sparkbot|sparkbot)\/writing_bot\/history\?limit=50$/, (route) =>
    route.fulfill({
      json: {
        messages: [
          {
            timestamp: "2026-04-26T09:35:00",
            role: "assistant",
            content: "Draft outline feedback is ready.",
            channel: "web",
          },
        ],
      },
    }),
  );
  await page.route(/\/api\/v1\/(?:sparkbot|sparkbot)$/, async (route) => {
    if (route.request().method() === "POST") {
      state.startPayload = route.request().postDataJSON() as Record<string, unknown>;
      await route.fulfill({ json: { bot_id: state.startPayload.bot_id, running: Boolean(state.startPayload.auto_start) } });
      return;
    }
    await route.fulfill({
      json: [
        {
          bot_id: "math_bot",
          name: "Math Bot",
          description: "Legacy route target",
          running: true,
        },
        {
          bot_id: "writing_bot",
          name: "Writing Bot",
          description: "Secondary bot",
          running: false,
        },
      ],
    });
  });
  return state;
}

async function installMockSparkBotWebSocket(page: import("@playwright/test").Page) {
  await page.addInitScript(() => {
    const state = window as typeof window & { __deepSparkBotWsMessages?: Array<Record<string, unknown>> };
    state.__deepSparkBotWsMessages = [];

    class MockSparkBotWebSocket {
      static readonly CONNECTING = 0;
      static readonly OPEN = 1;
      static readonly CLOSING = 2;
      static readonly CLOSED = 3;

      readonly url: string;
      readyState = MockSparkBotWebSocket.CONNECTING;
      onopen: ((event: Event) => void) | null = null;
      onmessage: ((event: MessageEvent<string>) => void) | null = null;
      onerror: ((event: Event) => void) | null = null;
      onclose: ((event: CloseEvent) => void) | null = null;

      constructor(url: string | URL) {
        this.url = String(url);
        window.setTimeout(() => {
          this.readyState = MockSparkBotWebSocket.OPEN;
          this.onopen?.(new Event("open"));
        }, 0);
      }

      send(data: string) {
        state.__deepSparkBotWsMessages?.push(JSON.parse(String(data)) as Record<string, unknown>);
        const events = [
          { type: "thinking", content: "Planning derivative hint" },
          { type: "content_delta", content: "导数表示" },
          { type: "content_delta", content: "瞬时变化率。" },
          { type: "content_delta", content: "斜率是 2。" },
          { type: "proactive", content: "记得复盘切线斜率。" },
          { type: "done" },
        ];
        events.forEach((event, index) => {
          window.setTimeout(() => {
            this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(event) }));
          }, index);
        });
      }

      close() {
        this.readyState = MockSparkBotWebSocket.CLOSED;
        this.onclose?.(new CloseEvent("close"));
      }
    }

    window.WebSocket = MockSparkBotWebSocket as unknown as typeof WebSocket;
  });
}

async function installMockGuideWebSocket(page: import("@playwright/test").Page) {
  await page.addInitScript(() => {
    const state = window as typeof window & { __guideWsMessages?: Array<Record<string, unknown>>; __guideWsUrls?: string[] };
    state.__guideWsMessages = [];
    state.__guideWsUrls = [];

    class MockGuideWebSocket {
      static readonly CONNECTING = 0;
      static readonly OPEN = 1;
      static readonly CLOSING = 2;
      static readonly CLOSED = 3;

      readonly url: string;
      readyState = MockGuideWebSocket.CONNECTING;
      onopen: ((event: Event) => void) | null = null;
      onmessage: ((event: MessageEvent<string>) => void) | null = null;
      onerror: ((event: Event) => void) | null = null;
      onclose: ((event: CloseEvent) => void) | null = null;

      constructor(url: string | URL) {
        this.url = String(url);
        state.__guideWsUrls?.push(this.url);
        window.setTimeout(() => {
          this.readyState = MockGuideWebSocket.OPEN;
          this.onopen?.(new Event("open"));
          this.emit({ type: "task_id", task_id: "guide-task-1" });
          this.emit({
            type: "session_info",
            data: {
              session_id: "guide-legacy",
              title: "Legacy Guide Session",
              status: "ready",
              current_index: 0,
              total_points: 1,
            },
          });
        }, 0);
      }

      send(data: string) {
        const payload = JSON.parse(String(data)) as Record<string, unknown>;
        state.__guideWsMessages?.push(payload);
        if (payload.type === "get_pages") {
          this.emit({
            type: "pages_info",
            data: { current_index: 0, total: 1, status: "ready", pages: [{ title: "Legacy Guide Page" }] },
          });
          return;
        }
        if (payload.type === "get_session") {
          this.emit({
            type: "session_info",
            data: { session_id: "guide-legacy", title: "Legacy Guide Session", status: "ready" },
          });
          return;
        }
        if (payload.type === "start") {
          this.emit({
            type: "start_result",
            data: { session_id: "guide-legacy", title: "WS Started", status: "running" },
          });
          return;
        }
        this.emit({ type: `${String(payload.type)}_result`, data: { status: "ok" } });
      }

      close() {
        if (this.readyState === MockGuideWebSocket.CLOSED) return;
        this.readyState = MockGuideWebSocket.CLOSED;
        this.onclose?.(new CloseEvent("close"));
      }

      private emit(payload: Record<string, unknown>) {
        this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(payload) }));
      }
    }

    window.WebSocket = MockGuideWebSocket as unknown as typeof WebSocket;
  });
}

async function installUnavailableGuideWebSocket(page: import("@playwright/test").Page) {
  await page.addInitScript(() => {
    class UnavailableGuideWebSocket {
      static readonly CONNECTING = 0;
      static readonly OPEN = 1;
      static readonly CLOSING = 2;
      static readonly CLOSED = 3;

      readonly url: string;
      readyState = UnavailableGuideWebSocket.CLOSED;
      onopen: ((event: Event) => void) | null = null;
      onmessage: ((event: MessageEvent<string>) => void) | null = null;
      onerror: ((event: Event) => void) | null = null;
      onclose: ((event: CloseEvent) => void) | null = null;

      constructor(url: string | URL) {
        this.url = String(url);
        window.setTimeout(() => {
          this.onerror?.(new Event("error"));
          this.onclose?.(new CloseEvent("close"));
        }, 0);
      }

      send() {}

      close() {
        this.onclose?.(new CloseEvent("close"));
      }
    }

    window.WebSocket = UnavailableGuideWebSocket as unknown as typeof WebSocket;
  });
}

async function mockGuideApis(page: import("@playwright/test").Page) {
  await mockReferenceApis(page);
  const state: {
    savedPayload?: Record<string, unknown>;
    createPayload?: Record<string, unknown>;
    created?: boolean;
    deletedSessionId?: string;
    startPayload?: Record<string, unknown>;
    completePayload?: Record<string, unknown>;
    retryPayload?: Record<string, unknown>;
    resetPayload?: Record<string, unknown>;
    chatPayload?: Record<string, unknown>;
    fixPayload?: Record<string, unknown>;
  } = {};
  await page.route("**/api/v1/guide/health", (route) =>
    route.fulfill({
      json: { status: "healthy", service: "guide" },
    }),
  );
  await page.route("**/api/v1/guide/create_session", async (route) => {
    state.createPayload = route.request().postDataJSON() as Record<string, unknown>;
    state.created = true;
    await route.fulfill({
      json: {
        session_id: "guide-created",
        title: "Created Guide Session",
        status: "ready",
        knowledge_points: [{ title: "Created point", description: "Created from notebook context." }],
      },
    });
  });
  await page.route("**/api/v1/guide/start", async (route) => {
    state.startPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({ json: { status: "rest-start", session_id: state.startPayload.session_id } });
  });
  await page.route("**/api/v1/guide/complete", async (route) => {
    state.completePayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({ json: { status: "rest-complete", session_id: state.completePayload.session_id } });
  });
  await page.route("**/api/v1/guide/retry_page", async (route) => {
    state.retryPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({ json: { status: "rest-retry", session_id: state.retryPayload.session_id, page_index: state.retryPayload.page_index } });
  });
  await page.route("**/api/v1/guide/reset", async (route) => {
    state.resetPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({ json: { status: "rest-reset", session_id: state.resetPayload.session_id } });
  });
  await page.route("**/api/v1/guide/chat", async (route) => {
    state.chatPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({ json: { status: "rest-chat", answer: "REST guide answer", session_id: state.chatPayload.session_id } });
  });
  await page.route("**/api/v1/guide/fix_html", async (route) => {
    state.fixPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({ json: { status: "rest-fix", fixed: true, session_id: state.fixPayload.session_id } });
  });
  await page.route("**/api/v1/guide/sessions", (route) => {
    const guideSessions = [
          ...(state.created
            ? [
                {
                  session_id: "guide-created",
                  title: "Created Guide Session",
                  user_input: "Guide from notebook context",
                  current_index: 0,
                  total_points: 1,
                  status: "ready",
                },
              ]
            : []),
          {
            session_id: "guide-other",
            title: "Other Guide Session",
            user_input: "Other topic",
            current_index: 0,
            total_points: 1,
            status: "ready",
          },
          {
            session_id: "guide-legacy",
            title: "Legacy Guide Session",
            user_input: "Legacy guide topic",
            current_index: 0,
            total_points: 1,
            status: "ready",
          },
        ].filter((session) => session.session_id !== state.deletedSessionId);
    return route.fulfill({ json: { sessions: guideSessions } });
  });
  await page.route(/\/api\/v1\/guide\/session\/guide-legacy$/, async (route) => {
    if (route.request().method() === "DELETE") {
      state.deletedSessionId = "guide-legacy";
      await route.fulfill({ json: { deleted: true, session_id: "guide-legacy" } });
      return;
    }
    await route.fulfill({
      json: {
        session_id: "guide-legacy",
        title: "Legacy Guide Session",
        user_input: "Legacy guide topic",
        current_index: 0,
        total_points: 1,
        status: "ready",
        knowledge_points: [
          {
            title: "Legacy Guide Point",
            description: "The selected query session drives this content.",
          },
        ],
      },
    });
  });
  await page.route(/\/api\/v1\/guide\/session\/guide-other$/, (route) =>
    route.fulfill({
      json: {
        session_id: "guide-other",
        title: "Other Guide Session",
        user_input: "Other topic",
        current_index: 0,
        total_points: 1,
        status: "ready",
        knowledge_points: [{ title: "Other Guide Point", description: "Fallback session after deletion." }],
      },
    }),
  );
  await page.route(/\/api\/v1\/guide\/session\/guide-created$/, async (route) => {
    if (route.request().method() === "DELETE") {
      state.deletedSessionId = "guide-created";
      await route.fulfill({ json: { deleted: true, session_id: "guide-created" } });
      return;
    }
    await route.fulfill({
      json: {
        session_id: "guide-created",
        title: "Created Guide Session",
        user_input: "Guide from notebook context",
        current_index: 0,
        total_points: 1,
        status: "ready",
        knowledge_points: [{ title: "Created point", description: "Created from notebook context." }],
      },
    });
  });
  await page.route(/\/api\/v1\/guide\/session\/guide-legacy\/html$/, (route) =>
    route.fulfill({
      json: { html: "<main><h1>Legacy Guide Page</h1><p>Loaded from the route query.</p></main>" },
    }),
  );
  await page.route(/\/api\/v1\/guide\/session\/guide-other\/html$/, (route) =>
    route.fulfill({
      json: { html: "<main><h1>Other Guide Page</h1><p>Fallback after deletion.</p></main>" },
    }),
  );
  await page.route(/\/api\/v1\/guide\/session\/guide-created\/html$/, (route) =>
    route.fulfill({
      json: { html: "<main><h1>Created Guide Page</h1><p>Created from notebook context.</p></main>" },
    }),
  );
  await page.route(/\/api\/v1\/guide\/session\/guide-legacy\/pages$/, (route) =>
    route.fulfill({
      json: {
        current_index: 0,
        total: 1,
        status: "ready",
        pages: [{ index: 0, title: "Legacy Guide Page" }],
      },
    }),
  );
  await page.route(/\/api\/v1\/guide\/session\/guide-other\/pages$/, (route) =>
    route.fulfill({
      json: {
        current_index: 0,
        total: 1,
        status: "ready",
        pages: [{ index: 0, title: "Other Guide Page" }],
      },
    }),
  );
  await page.route(/\/api\/v1\/guide\/session\/guide-created\/pages$/, (route) =>
    route.fulfill({
      json: {
        current_index: 0,
        total: 1,
        status: "ready",
        pages: [{ index: 0, title: "Created Guide Page" }],
      },
    }),
  );
  await page.route("**/api/v1/notebook/add_record", async (route) => {
    state.savedPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      json: {
        success: true,
        added_to_notebooks: ["nb1"],
        record: { id: "guide-record", record_type: "guided_learning", title: "Legacy Guide Session" },
      },
    });
  });
  return state;
}

async function mockCoWriterStreamApis(page: import("@playwright/test").Page) {
  const state: {
    savedPayload?: Record<string, unknown>;
    exportPayload?: Record<string, unknown>;
    quickEditPayload?: Record<string, unknown>;
    automarkPayload?: Record<string, unknown>;
  } = {};
  await page.route("**/api/v1/system/status", (route) =>
    route.fulfill({
      json: {
        backend: { status: "online" },
        llm: { status: "configured", model: "mock-llm" },
        embeddings: { status: "configured", model: "mock-embedding" },
        search: { status: "optional" },
      },
    }),
  );
  await page.route("**/api/v1/knowledge/list", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/dashboard/recent?**", (route) => route.fulfill({ json: [] }));
  await page.route(/\/api\/v1\/sessions\?/, (route) => route.fulfill({ json: { sessions: [] } }));
  await page.route("**/api/v1/co_writer/history/op-history", (route) =>
    route.fulfill({
      json: {
        id: "op-history",
        action: "Polish proof",
        mode: "rewrite",
        input: { selected_text: "Original proof sketch", instruction: "polish" },
        output: { edited_text: "Edited proof sketch" },
        tool_call_file: "op-history_react_tools.json",
      },
    }),
  );
  await page.route("**/api/v1/co_writer/history/op-automark", (route) =>
    route.fulfill({
      json: {
        id: "op-automark",
        action: "AutoMark",
        input: { selected_text: "rough note" },
        output: { marked_text: "marked rough note" },
      },
    }),
  );
  await page.route("**/api/v1/co_writer/tool_calls/op-history", (route) =>
    route.fulfill({
      json: {
        operation_id: "op-history",
        tool_traces: [{ tool: "rag_search", output: "Retrieved supporting theorem." }],
      },
    }),
  );
  await page.route("**/api/v1/co_writer/tool_calls/op-automark", (route) =>
    route.fulfill({
      json: { operation_id: "op-automark", tool_traces: [] },
    }),
  );
  await page.route("**/api/v1/co_writer/export/markdown", async (route) => {
    state.exportPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      headers: { "Content-Type": "text/markdown" },
      body: String(state.exportPayload.content || ""),
    });
  });
  await page.route("**/api/v1/co_writer/history", (route) =>
    route.fulfill({
      json: {
        history: [
          {
            id: "op-history",
            action: "Polish proof",
            input: { selected_text: "Original proof sketch", instruction: "polish" },
            output: { edited_text: "Edited proof sketch" },
            tool_call_file: "op-history_react_tools.json",
          },
        ],
        total: 1,
      },
    }),
  );
  await page.route("**/api/v1/notebook/list", (route) =>
    route.fulfill({
      json: {
        notebooks: [{ id: "nb-stream", name: "Stream Notebook", description: "Co-writer target", record_count: 0 }],
        total: 1,
      },
    }),
  );
  await page.route("**/api/v1/co_writer/edit_react/stream", (route) =>
    route.fulfill({
      status: 200,
      headers: { "Content-Type": "text/event-stream" },
      body: [
        'event: stream\ndata: {"type":"progress","stage":"thinking","content":"Planning edit"}\n\n',
        'event: stream\ndata: {"type":"content","stage":"responding","content":"streamed "}\n\n',
        'event: stream\ndata: {"type":"content","stage":"responding","content":"polished text"}\n\n',
        'event: result\ndata: {"edited_text":"streamed polished text","operation_id":"op-stream"}\n\n',
      ].join(""),
    }),
  );
  await page.route("**/api/v1/co_writer/edit", async (route) => {
    state.quickEditPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      json: {
        edited_text: "quick edited text",
        operation_id: "op-basic",
      },
    });
  });
  await page.route("**/api/v1/co_writer/automark", async (route) => {
    state.automarkPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      json: {
        marked_text: "marked rough note",
        operation_id: "op-automark",
      },
    });
  });
  await page.route("**/api/v1/notebook/add_record", async (route) => {
    state.savedPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      json: {
        success: true,
        added_to_notebooks: ["nb-stream"],
        record: { id: "co-writer-record", record_type: "co_writer", title: "Co-Writer stream" },
      },
    });
  });
  return state;
}

async function installMockSettingsEventSource(page: import("@playwright/test").Page) {
  await page.addInitScript(() => {
    const state = window as typeof window & { __settingsEventSourceUrls?: string[] };
    state.__settingsEventSourceUrls = [];

    class MockEventSource {
      readonly url: string;
      onmessage: ((event: MessageEvent<string>) => void) | null = null;
      onerror: ((event: Event) => void) | null = null;

      constructor(url: string | URL) {
        this.url = String(url);
        state.__settingsEventSourceUrls?.push(this.url);
        if (this.url.includes("run-llm-complete")) {
          window.setTimeout(() => {
            this.emit({ type: "log", message: "LLM handshake ok" });
            this.emit({ type: "completed", message: "LLM ready" });
          }, 0);
        }
      }

      close() {
        // The mock stream is finite unless a test intentionally cancels it.
      }

      private emit(payload: Record<string, unknown>) {
        this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(payload) }));
      }
    }

    window.EventSource = MockEventSource as unknown as typeof EventSource;
  });
}

async function mockSettingsTourApis(page: import("@playwright/test").Page) {
  await mockReferenceApis(page);
  const state: {
    completedPayload?: Record<string, unknown>;
    catalogPayload?: {
      catalog?: {
        services?: {
          llm?: { profiles?: Array<{ base_url?: string; api_key?: string; models?: Array<{ model?: string }> }> };
          embedding?: { profiles?: Array<{ models?: Array<{ model?: string; dimension?: string }> }> };
        };
      };
    };
    applyPayload?: {
      catalog?: {
        services?: {
          llm?: { profiles?: Array<{ models?: Array<{ model?: string }> }> };
        };
      };
    };
    uiPayload?: Record<string, unknown>;
    serviceStartPayload?: { service: string; catalog?: Record<string, unknown> };
    systemProbeTarget?: string;
    cancelTarget?: { service: string; runId: string };
    themePayload?: Record<string, unknown>;
    languagePayload?: Record<string, unknown>;
    sidebarDescriptionPayload?: Record<string, unknown>;
    sidebarNavPayload?: Record<string, unknown>;
    resetCalled?: boolean;
    reopenCalled?: boolean;
    tourStatus?: { active: boolean; status: string; launch_at: number | null; redirect_at: number | null };
  } = {};
  const settingsPayload = {
    ui: {
      language: "zh",
      theme: "light",
      sidebar_description: "SparkWeave Workbench",
      sidebar_nav_order: { start: ["/chat", "/knowledge"], learnResearch: ["/guide", "/co-writer"] },
    },
    catalog: {
      version: 1,
      services: {
        llm: {
          active_profile_id: "llm-profile",
          active_model_id: "llm-model",
          profiles: [
            {
              id: "llm-profile",
              name: "Mock LLM",
              binding: "openai",
              base_url: "https://llm.example/v1",
              api_key: "",
              models: [{ id: "llm-model", name: "Mock GPT", model: "gpt-mock" }],
            },
          ],
        },
        embedding: {
          active_profile_id: "embedding-profile",
          active_model_id: "embedding-model",
          profiles: [
            {
              id: "embedding-profile",
              name: "Mock Embedding",
              binding: "openai",
              base_url: "https://embedding.example/v1",
              api_key: "",
              models: [{ id: "embedding-model", name: "Mock Embedding", model: "embedding-mock", dimension: "1024" }],
            },
          ],
        },
        search: {
          active_profile_id: "search-profile",
          profiles: [{ id: "search-profile", name: "Mock Search", provider: "tavily", base_url: "", api_key: "" }],
        },
      },
    },
    providers: {
      llm: [{ value: "openai", label: "OpenAI Compatible", base_url: "https://llm.example/v1" }],
      embedding: [
        {
          value: "openai",
          label: "OpenAI Compatible",
          base_url: "https://embedding.example/v1",
          default_model: "text-embedding-3-large",
          models: ["text-embedding-3-large"],
          default_dim: "3072",
        },
        {
          value: "cohere",
          label: "Cohere",
          base_url: "https://api.cohere.ai",
          default_model: "embed-v4.0",
          models: ["embed-v4.0"],
          default_dim: "1024",
        },
        {
          value: "iflytek_spark",
          label: "iFlytek Spark Embedding",
          base_url: "https://emb-cn-huabei-1.xf-yun.com/",
          default_model: "llm-embedding",
          models: ["llm-embedding"],
          default_dim: "2560",
        },
      ],
      search: [
        { value: "tavily", label: "Tavily", base_url: "https://api.tavily.com/search" },
        { value: "jina", label: "Jina", base_url: "https://s.jina.ai" },
        { value: "perplexity", label: "Perplexity", base_url: "https://api.perplexity.ai" },
      ],
    },
  };
  state.tourStatus = { active: true, status: "waiting", launch_at: null, redirect_at: null };

  await page.route("**/api/v1/settings", (route) => route.fulfill({ json: settingsPayload }));
  await page.route("**/api/v1/system/runtime-topology", (route) =>
    route.fulfill({
      json: {
        primary_runtime: {
          transport: "/api/v1/ws",
          manager: "LangGraphTurnRuntimeManager",
          orchestrator: "LangGraphRunner",
          session_store: "SQLiteSessionStore",
          capability_entry: "CapabilityRegistry",
          tool_entry: "ToolRegistry",
        },
        compatibility_routes: [
          { router: "chat", mode: "ng_router" },
          { router: "solve", mode: "ng_router" },
        ],
        isolated_subsystems: [
          { router: "guide", mode: "independent_subsystem" },
          { router: "co_writer", mode: "independent_subsystem" },
        ],
      },
    }),
  );
  await page.route("**/api/v1/settings/catalog", async (route) => {
    if (route.request().method() === "PUT") {
      state.catalogPayload = route.request().postDataJSON() as typeof state.catalogPayload;
      if (state.catalogPayload?.catalog) settingsPayload.catalog = state.catalogPayload.catalog as typeof settingsPayload.catalog;
      await route.fulfill({ json: { catalog: settingsPayload.catalog } });
      return;
    }
    await route.fulfill({ json: { catalog: settingsPayload.catalog } });
  });
  await page.route("**/api/v1/settings/apply", async (route) => {
    state.applyPayload = route.request().postDataJSON() as typeof state.applyPayload;
    await route.fulfill({
      json: {
        message: "Catalog applied to the active .env configuration.",
        catalog: state.applyPayload?.catalog ?? settingsPayload.catalog,
        env: { LLM_MODEL: "gpt-updated", EMBEDDING_MODEL: "embedding-updated" },
      },
    });
  });
  await page.route("**/api/v1/settings/ui", async (route) => {
    if (route.request().method() === "PUT") {
      state.uiPayload = route.request().postDataJSON() as Record<string, unknown>;
      settingsPayload.ui = { ...settingsPayload.ui, ...state.uiPayload };
    }
    await route.fulfill({ json: settingsPayload.ui });
  });
  await page.route("**/api/v1/settings/themes", (route) =>
    route.fulfill({
      json: {
        themes: [
          { id: "light", name: "Light" },
          { id: "snow", name: "Snow" },
          { id: "glass", name: "Glass" },
          { id: "dark", name: "Dark" },
        ],
      },
    }),
  );
  await page.route("**/api/v1/settings/sidebar", (route) =>
    route.fulfill({
      json: {
        description: "SparkWeave Workbench",
        nav_order: { start: ["/chat", "/knowledge"], learnResearch: ["/guide", "/co-writer"] },
      },
    }),
  );
  await page.route("**/api/v1/settings/theme", async (route) => {
    state.themePayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({ json: state.themePayload });
  });
  await page.route("**/api/v1/settings/language", async (route) => {
    state.languagePayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({ json: state.languagePayload });
  });
  await page.route("**/api/v1/settings/sidebar/description", async (route) => {
    state.sidebarDescriptionPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({ json: state.sidebarDescriptionPayload });
  });
  await page.route("**/api/v1/settings/sidebar/nav-order", async (route) => {
    state.sidebarNavPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({ json: state.sidebarNavPayload });
  });
  await page.route("**/api/v1/settings/reset", async (route) => {
    state.resetCalled = true;
    await route.fulfill({ json: settingsPayload.ui });
  });
  await page.route("**/api/v1/settings/tour/status", (route) => route.fulfill({ json: state.tourStatus }));
  await page.route("**/api/v1/settings/tour/reopen", async (route) => {
    state.reopenCalled = true;
    state.tourStatus = { active: false, status: "none", launch_at: null, redirect_at: null };
    await route.fulfill({
      json: {
        message: "Run the terminal setup guide from the project root to re-open the guided setup.",
        command: "python scripts/start_tour.py",
      },
    });
  });
  await page.route(/\/api\/v1\/system\/test\/(llm|embeddings|search)$/, async (route) => {
    const service = route.request().url().match(/\/system\/test\/([^/]+)$/)?.[1] ?? "llm";
    state.systemProbeTarget = service;
    await route.fulfill({
      json: {
        success: service !== "search",
        message:
          service === "search"
            ? "Search not configured"
            : `${service === "embeddings" ? "Embeddings" : "LLM"} connection successful`,
        model: service === "llm" ? "gpt-mock" : service === "embeddings" ? "embedding-mock" : null,
        response_time_ms: service === "search" ? null : 42,
        error: service === "search" ? "Missing SEARCH_PROVIDER" : null,
      },
    });
  });
  await page.route(/\/api\/v1\/settings\/tests\/([^/]+)\/start$/, async (route) => {
    const service = route.request().url().match(/\/tests\/([^/]+)\/start$/)?.[1] ?? "llm";
    const body = route.request().postDataJSON() as { catalog?: Record<string, unknown> };
    state.serviceStartPayload = { service, catalog: body.catalog };
    await route.fulfill({ json: { run_id: service === "search" ? "run-search-cancel" : "run-llm-complete" } });
  });
  await page.route(/\/api\/v1\/settings\/tests\/([^/]+)\/([^/]+)\/cancel$/, async (route) => {
    const match = route.request().url().match(/\/tests\/([^/]+)\/([^/]+)\/cancel$/);
    state.cancelTarget = { service: match?.[1] ?? "", runId: match?.[2] ?? "" };
    await route.fulfill({ json: { message: "Cancelled" } });
  });
  await page.route("**/api/v1/settings/tour/complete", async (route) => {
    state.completedPayload = route.request().postDataJSON() as Record<string, unknown>;
    state.tourStatus = { active: true, status: "completed", launch_at: 1_700_000_003, redirect_at: 1_700_000_005 };
    await route.fulfill({
      json: {
        status: "completed",
        message: "Configuration saved. SparkWeave will restart shortly.",
        launch_at: 1_700_000_003,
        redirect_at: 1_700_000_005,
        env: { LLM_MODEL: "gpt-mock", EMBEDDING_MODEL: "embedding-mock" },
      },
    });
  });
  return state;
}

async function mockNotebookMutationApis(page: import("@playwright/test").Page) {
  const state: {
    createPayload?: Record<string, unknown>;
    addRecordPayload?: Record<string, unknown>;
    addRecordSummaryPayload?: Record<string, unknown>;
    updateNotebookPayload?: Record<string, unknown>;
    updateNotebookTarget?: string;
    updateRecordPayload?: Record<string, unknown>;
    updateRecordTarget?: { notebookId: string; recordId: string };
    deletedRecordTarget?: { notebookId: string; recordId: string };
    deletedNotebookId?: string;
    entryUpdatePayload?: Record<string, unknown>;
    entryDeleteId?: number;
    questionUpsertPayload?: Record<string, unknown>;
    questionLookupTarget?: { sessionId: string; questionId: string };
    categoryCreatePayload?: Record<string, unknown>;
    categoryRenamePayload?: Record<string, unknown>;
    categoryAddPayload?: Record<string, unknown>;
    categoryRemoveTarget?: { entryId: number; categoryId: number };
  } = {};

  const notebooks: Record<string, Record<string, unknown>> = {
    "nb-existing": {
      id: "nb-existing",
      name: "Existing Notebook",
      description: "Existing records",
      record_count: 1,
      records: [
        {
          id: "rec-existing",
          record_id: "rec-existing",
          record_type: "chat",
          title: "Existing proof note",
          summary: "Original summary",
          user_query: "Original question",
          output: "Original output",
          metadata: { session_id: "session-existing" },
        },
      ],
    },
    "nb-created": {
      id: "nb-created",
      name: "Competition Review",
      description: "Polished learning assets",
      record_count: 0,
      records: [],
    },
  };
  const categories = [
    { id: 1, name: "Limits", created_at: 1_700_000_000, entry_count: 1 },
    { id: 2, name: "Derivatives", created_at: 1_700_000_100, entry_count: 0 },
  ];
  const entry = {
    id: 7,
    session_id: "origin-session",
    session_title: "Question source",
    question_id: "q-7",
    question: "Which limit rule applies first?",
    question_type: "single_choice",
    options: { A: "L'Hopital", B: "Factorization" },
    correct_answer: "B",
    explanation: "Check algebraic simplification before differentiating.",
    difficulty: "medium",
    user_answer: "A",
    is_correct: false,
    bookmarked: false,
    followup_session_id: "followup-session",
    created_at: 1_700_000_200,
    updated_at: 1_700_000_300,
    categories: [{ id: 1, name: "Limits", created_at: 1_700_000_000, entry_count: 1 }],
  };

  await page.route("**/api/v1/system/status", (route) =>
    route.fulfill({
      json: {
        backend: { status: "online" },
        llm: { status: "configured", model: "mock-llm" },
        embeddings: { status: "configured", model: "mock-embedding" },
        search: { status: "optional" },
      },
    }),
  );
  await page.route("**/api/v1/knowledge/list", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/dashboard/recent?**", (route) => route.fulfill({ json: [] }));
  await page.route(/\/api\/v1\/sessions\?/, (route) => route.fulfill({ json: { sessions: [] } }));
  await page.route("**/api/v1/notebook/health", (route) =>
    route.fulfill({ json: { status: "healthy", service: "notebook" } }),
  );
  await page.route("**/api/v1/notebook/statistics", (route) => route.fulfill({ json: { total_records: 1 } }));
  await page.route("**/api/v1/notebook/list", (route) =>
    route.fulfill({
      json: {
        notebooks: Object.values(notebooks).map((notebook) => ({
          id: notebook.id,
          name: notebook.name,
          description: notebook.description,
          record_count: notebook.record_count,
        })),
        total: Object.keys(notebooks).length,
      },
    }),
  );
  await page.route("**/api/v1/notebook/create", async (route) => {
    state.createPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({ json: { success: true, notebook: notebooks["nb-created"] } });
  });
  await page.route("**/api/v1/notebook/add_record", async (route) => {
    state.addRecordPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      json: {
        success: true,
        summary: state.addRecordPayload.summary || "",
        added_to_notebooks: state.addRecordPayload.notebook_ids,
        record: { id: "rec-manual", record_type: "chat", title: state.addRecordPayload.title },
      },
    });
  });
  await page.route("**/api/v1/notebook/add_record_with_summary", async (route) => {
    state.addRecordSummaryPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      headers: { "Content-Type": "text/event-stream" },
      body: [
        'data: {"type":"summary_chunk","content":"AI summary "}\n\n',
        'data: {"type":"summary_chunk","content":"for notebook"}\n\n',
        'data: {"type":"result","success":true,"summary":"AI summary for notebook","added_to_notebooks":["nb-created"],"record":{"id":"rec-summary","record_type":"chat","title":"Summary proof note"}}\n\n',
      ].join(""),
    });
  });
  await page.route(/\/api\/v1\/notebook\/([^/]+)\/records\/([^/]+)$/, async (route) => {
    const match = route.request().url().match(/\/api\/v1\/notebook\/([^/]+)\/records\/([^/]+)$/);
    const notebookId = decodeURIComponent(match?.[1] ?? "");
    const recordId = decodeURIComponent(match?.[2] ?? "");
    if (route.request().method() === "PUT") {
      state.updateRecordTarget = { notebookId, recordId };
      state.updateRecordPayload = route.request().postDataJSON() as Record<string, unknown>;
      await route.fulfill({
        json: {
          success: true,
          record: { id: recordId, record_id: recordId, record_type: "chat", ...state.updateRecordPayload },
        },
      });
      return;
    }
    if (route.request().method() === "DELETE") {
      state.deletedRecordTarget = { notebookId, recordId };
      await route.fulfill({ json: { success: true, message: "Record removed successfully" } });
      return;
    }
    await route.fulfill({ status: 405, json: { detail: "Method not allowed" } });
  });
  await page.route(/\/api\/v1\/notebook\/(?!list$|statistics$|create$|add_record$|add_record_with_summary$|health$)([^/]+)$/, async (route) => {
    const notebookId = decodeURIComponent(
      route
        .request()
        .url()
        .match(/\/api\/v1\/notebook\/(?!list$|statistics$|create$|add_record$|add_record_with_summary$|health$)([^/]+)$/)?.[1] ?? "",
    );
    if (route.request().method() === "DELETE") {
      state.deletedNotebookId = notebookId;
      await route.fulfill({ json: { success: true, message: "Notebook deleted successfully" } });
      return;
    }
    if (route.request().method() === "PUT") {
      state.updateNotebookTarget = notebookId;
      state.updateNotebookPayload = route.request().postDataJSON() as Record<string, unknown>;
      notebooks[notebookId] = {
        ...(notebooks[notebookId] ?? { id: notebookId, records: [] }),
        ...state.updateNotebookPayload,
      };
      await route.fulfill({ json: { success: true, notebook: notebooks[notebookId] } });
      return;
    }
    await route.fulfill({ json: notebooks[notebookId] ?? notebooks["nb-existing"] });
  });
  await page.route("**/api/v1/question-notebook/categories", async (route) => {
    if (route.request().method() === "POST") {
      state.categoryCreatePayload = route.request().postDataJSON() as Record<string, unknown>;
      await route.fulfill({
        status: 201,
        json: { id: 3, name: String(state.categoryCreatePayload.name), created_at: 1_700_000_400, entry_count: 0 },
      });
      return;
    }
    await route.fulfill({ json: categories });
  });
  await page.route(/\/api\/v1\/question-notebook\/categories\/(\d+)$/, async (route) => {
    const categoryId = Number(route.request().url().match(/\/categories\/(\d+)$/)?.[1]);
    if (route.request().method() === "PATCH") {
      state.categoryRenamePayload = route.request().postDataJSON() as Record<string, unknown>;
      await route.fulfill({ json: { updated: true, id: categoryId, name: state.categoryRenamePayload.name } });
      return;
    }
    if (route.request().method() === "DELETE") {
      await route.fulfill({ json: { deleted: true, id: categoryId } });
      return;
    }
    await route.fulfill({ status: 405, json: { detail: "Method not allowed" } });
  });
  await page.route("**/api/v1/question-notebook/entries/upsert", async (route) => {
    state.questionUpsertPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      json: {
        ...entry,
        id: 8,
        session_id: state.questionUpsertPayload.session_id,
        question_id: state.questionUpsertPayload.question_id,
        question: state.questionUpsertPayload.question,
        correct_answer: state.questionUpsertPayload.correct_answer,
        explanation: state.questionUpsertPayload.explanation,
        difficulty: state.questionUpsertPayload.difficulty,
        categories: [],
      },
    });
  });
  await page.route("**/api/v1/question-notebook/entries/lookup/by-question?**", async (route) => {
    const url = new URL(route.request().url());
    state.questionLookupTarget = {
      sessionId: url.searchParams.get("session_id") || "",
      questionId: url.searchParams.get("question_id") || "",
    };
    await route.fulfill({
      json: {
        ...entry,
        id: 8,
        session_id: state.questionLookupTarget.sessionId,
        question_id: state.questionLookupTarget.questionId,
        question: "Why does factoring help before L'Hopital?",
        correct_answer: "It can remove a removable zero factor.",
        explanation: "Always simplify the expression first.",
        categories: [],
      },
    });
  });
  await page.route(/\/api\/v1\/question-notebook\/entries\?/, (route) =>
    route.fulfill({ json: { items: [entry], total: 1 } }),
  );
  await page.route(/\/api\/v1\/question-notebook\/entries\/(\d+)$/, async (route) => {
    const entryId = Number(route.request().url().match(/\/entries\/(\d+)$/)?.[1]);
    if (route.request().method() === "PATCH") {
      state.entryUpdatePayload = route.request().postDataJSON() as Record<string, unknown>;
      await route.fulfill({ json: { updated: true, id: entryId } });
      return;
    }
    if (route.request().method() === "DELETE") {
      state.entryDeleteId = entryId;
      await route.fulfill({ json: { deleted: true, id: entryId } });
      return;
    }
    await route.fulfill({ status: 405, json: { detail: "Method not allowed" } });
  });
  await page.route(/\/api\/v1\/question-notebook\/entries\/(\d+)\/categories$/, async (route) => {
    const entryId = Number(route.request().url().match(/\/entries\/(\d+)\/categories$/)?.[1]);
    state.categoryAddPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      json: { added: true, entry_id: entryId, category_id: state.categoryAddPayload.category_id },
    });
  });
  await page.route(/\/api\/v1\/question-notebook\/entries\/(\d+)\/categories\/(\d+)$/, async (route) => {
    const match = route.request().url().match(/\/entries\/(\d+)\/categories\/(\d+)$/);
    state.categoryRemoveTarget = {
      entryId: Number(match?.[1]),
      categoryId: Number(match?.[2]),
    };
    await route.fulfill({
      json: {
        removed: true,
        entry_id: state.categoryRemoveTarget.entryId,
        category_id: state.categoryRemoveTarget.categoryId,
      },
    });
  });
  return state;
}

async function mockNotebookDeepLinkApis(page: import("@playwright/test").Page) {
  await page.route("**/api/v1/system/status", (route) =>
    route.fulfill({
      json: {
        backend: { status: "online" },
        llm: { status: "configured", model: "mock-llm" },
        embeddings: { status: "configured", model: "mock-embedding" },
        search: { status: "optional" },
      },
    }),
  );
  await page.route("**/api/v1/knowledge/list", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/dashboard/recent?**", (route) => route.fulfill({ json: [] }));
  await page.route(/\/api\/v1\/sessions\?/, (route) => route.fulfill({ json: { sessions: [] } }));
  await page.route("**/api/v1/notebook/health", (route) =>
    route.fulfill({ json: { status: "healthy", service: "notebook" } }),
  );
  await page.route("**/api/v1/notebook/statistics", (route) => route.fulfill({ json: { total_records: 1 } }));
  await page.route("**/api/v1/notebook/list", (route) =>
    route.fulfill({
      json: {
        notebooks: [{ id: "nb-link", name: "Deep Link Notebook", description: "Direct route target", record_count: 1 }],
        total: 1,
      },
    }),
  );
  await page.route("**/api/v1/notebook/nb-link", (route) =>
    route.fulfill({
      json: {
        id: "nb-link",
        name: "Deep Link Notebook",
        description: "Direct route target",
        records: [
          {
            id: "rec-chat",
            record_id: "rec-chat",
            record_type: "chat",
            title: "Deep linked notebook record",
            summary: "This record should open its stored chat session.",
            user_query: "Open this session",
            output: "## 可视化资产\n\n```mermaid\nflowchart TD\nA[Notebook] --> B[Review]\n```",
            metadata: {
              session_id: "session-from-record",
              asset_kind: "知识可视化 · mermaid",
              visualize: {
                response: "Notebook Mermaid asset",
                render_type: "mermaid",
                code: {
                  language: "mermaid",
                  content: "flowchart TD\nA[Notebook] --> B[Review]",
                },
              },
            },
          },
          {
            id: "rec-guide",
            record_id: "rec-guide",
            record_type: "guided_learning",
            title: "Saved guided learning page",
            summary: "导学页面 · HTML",
            user_query: "Learn with a guided page",
            output: "<main><h1>Saved Guide Asset</h1><p>Notebook can preview this learning page.</p></main>",
            metadata: {
              session_id: "guide-asset-session",
              asset_kind: "导学页面 · HTML",
              output_type: "html",
              guide: {
                title: "Saved guided learning page",
                session_id: "guide-asset-session",
                current_index: 0,
                pages: [{ index: 0, title: "Saved Guide Asset" }],
              },
            },
          },
        ],
      },
    }),
  );
  await page.route("**/api/v1/question-notebook/categories", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/question-notebook/entries?**", (route) =>
    route.fulfill({
      json: {
        items: [],
        total: 0,
      },
    }),
  );
  await page.route("**/api/v1/question-notebook/entries/7", (route) =>
    route.fulfill({
      json: {
        id: 7,
        session_id: "origin-session",
        followup_session_id: "followup-session",
        question_id: "question-direct",
        question: "Follow-up question target",
        question_type: "written",
        correct_answer: "42",
        explanation: "The follow-up route should be preserved.",
        is_correct: false,
        bookmarked: true,
        categories: [],
      },
    }),
  );
}

type MockWsEvent = Record<string, unknown>;
type MockWsOptions = { resultOnlyContent?: string; events?: MockWsEvent[]; holdOpen?: boolean };

async function installMockQuestionWebSocket(page: import("@playwright/test").Page) {
  await page.addInitScript(() => {
    const state = window as typeof window & {
      __questionLabWsMessages?: Array<Record<string, unknown>>;
      __questionLabWsUrls?: string[];
    };
    state.__questionLabWsMessages = [];
    state.__questionLabWsUrls = [];

    const summary = {
      success: true,
      source: "topic",
      requested: 3,
      completed: 1,
      failed: 0,
      mode: "custom",
      results: [
        {
          success: true,
          qa_pair: {
            question_id: "q-limit-1",
            question_type: "choice",
            question: "函数极限存在的充分条件是什么？",
            options: {
              A: "左右极限都存在且相等",
              B: "函数在该点必须有定义",
              C: "函数必须单调",
              D: "函数必须连续可导",
            },
            correct_answer: "A",
            explanation: "二元判断的关键是左右极限分别存在并且相等，函数在该点是否有定义不影响极限存在。",
            difficulty: "medium",
            concentration: "函数极限",
          },
        },
      ],
    };

    const mimicSummary = {
      success: true,
      source: "mimic",
      requested: 3,
      completed: 1,
      failed: 0,
      mode: "parsed",
      results: [
        {
          success: true,
          qa_pair: {
            question_id: "mimic-1",
            question_type: "choice",
            question: "Mimic problem: which step preserves the same reasoning pattern?",
            options: {
              A: "Change every condition without checking the invariant.",
              B: "Keep the limit comparison structure and vary the surface numbers.",
              C: "Remove the target concept entirely.",
              D: "Answer directly without proving the condition.",
            },
            correct_answer: "B",
            explanation: "A good mimic item preserves the reasoning pattern while changing the context.",
            difficulty: "medium",
            concentration: "limit comparison",
          },
        },
      ],
    };

    class MockQuestionWebSocket {
      static readonly CONNECTING = 0;
      static readonly OPEN = 1;
      static readonly CLOSING = 2;
      static readonly CLOSED = 3;

      readonly url: string;
      readyState = MockQuestionWebSocket.CONNECTING;
      onopen: ((event: Event) => void) | null = null;
      onmessage: ((event: MessageEvent<string>) => void) | null = null;
      onerror: ((event: Event) => void) | null = null;
      onclose: ((event: CloseEvent) => void) | null = null;

      constructor(url: string | URL) {
        this.url = String(url);
        state.__questionLabWsUrls?.push(this.url);
        window.setTimeout(() => {
          this.readyState = MockQuestionWebSocket.OPEN;
          this.onopen?.(new Event("open"));
        }, 0);
      }

      send(data: string) {
        const payload = JSON.parse(String(data)) as Record<string, unknown>;
        const isMimic = this.url.includes("/question/mimic");
        const activeSummary = isMimic ? mimicSummary : summary;
        state.__questionLabWsMessages?.push(payload);
        window.setTimeout(() => {
          const messages = [
            { type: "task_id", task_id: "question-gen-1", content: "任务已创建" },
            { type: "progress", stage: "ideation", source: "deep_question", content: "生成模板" },
            {
              type: "result",
              stage: "generation",
              source: "deep_question",
              content: "题目生成完成",
              metadata: { summary },
            },
            { type: "batch_summary", requested: 3, completed: 1, failed: 0 },
            { type: "complete" },
          ];
          const outgoing = messages as Array<Record<string, unknown>>;
          if (isMimic) {
            outgoing[0] = { type: "task_id", task_id: "question-mimic-1", content: "mimic task created" };
            outgoing[1] = { type: "progress", stage: "mimic", source: "question_mimic", content: "mimic template ready" };
            outgoing[2] = {
              type: "result",
              stage: "generation",
              source: "question_mimic",
              content: "mimic questions ready",
              metadata: { summary: activeSummary },
            };
          } else {
            outgoing[2] = { ...outgoing[2], metadata: { summary: activeSummary } };
          }
          for (const message of outgoing) {
            this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(message) }));
          }
        }, 0);
      }

      close() {
        this.readyState = MockQuestionWebSocket.CLOSED;
        this.onclose?.(new CloseEvent("close"));
      }
    }

    window.WebSocket = MockQuestionWebSocket as unknown as typeof WebSocket;
  });
}

async function mockVisionApis(page: import("@playwright/test").Page) {
  const state: { analyzePayload?: Record<string, unknown> } = {};
  await page.route("**/api/v1/vision/analyze", async (route) => {
    state.analyzePayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      json: {
        session_id: "vision-rest-1",
        has_image: true,
        final_ggb_commands: [
          { description: "圆 O", command: "Circle(O, 3)" },
          { description: "点 A", command: "A = Point(c)" },
        ],
        ggb_script: "```ggbscript[analysis;题目图形]\n# 圆 O\nCircle(O, 3)\n# 点 A\nA = Point(c)\n```",
        analysis_summary: {
          image_is_reference: true,
          elements_count: 4,
          commands_count: 2,
        },
      },
    });
  });
  return state;
}

async function installMockVisionWebSocket(page: import("@playwright/test").Page) {
  await page.addInitScript(() => {
    const state = window as typeof window & { __visionWsMessages?: Array<Record<string, unknown>> };
    state.__visionWsMessages = [];

    class MockVisionWebSocket {
      static readonly CONNECTING = 0;
      static readonly OPEN = 1;
      static readonly CLOSING = 2;
      static readonly CLOSED = 3;

      readonly url: string;
      readyState = MockVisionWebSocket.CONNECTING;
      onopen: ((event: Event) => void) | null = null;
      onmessage: ((event: MessageEvent<string>) => void) | null = null;
      onerror: ((event: Event) => void) | null = null;
      onclose: ((event: CloseEvent) => void) | null = null;

      constructor(url: string | URL) {
        this.url = String(url);
        window.setTimeout(() => {
          this.readyState = MockVisionWebSocket.OPEN;
          this.onopen?.(new Event("open"));
        }, 0);
      }

      send(data: string) {
        const payload = JSON.parse(String(data)) as Record<string, unknown>;
        state.__visionWsMessages?.push(payload);
        window.setTimeout(() => {
          const messages = [
            { type: "session", session_id: "vision-live-1" },
            { type: "analysis_start", data: { session_id: "vision-live-1" } },
            { type: "bbox_complete", data: { stage: "bbox", elements_count: 4 } },
            { type: "analysis_complete", data: { stage: "analysis", constraints_count: 2, relations_count: 1 } },
            {
              type: "reflection_complete",
              data: {
                stage: "reflection",
                commands_count: 2,
                final_commands: [
                  { description: "线段 AB", command: "Segment(A, B)" },
                  { description: "圆 O", command: "Circle(O, A)" },
                ],
              },
            },
            {
              type: "analysis_message_complete",
              data: {
                ggb_block: {
                  page_id: "image-analysis-restore",
                  title: "题目配图还原",
                  content: "# 线段 AB\nSegment(A, B)\n# 圆 O\nCircle(O, A)",
                },
              },
            },
            { type: "answer_start", data: { has_image_analysis: true } },
            { type: "text", data: { content: "先还原几何关系，再根据半径和线段条件求解。" } },
            { type: "done", data: {} },
          ];
          for (const message of messages) {
            this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(message) }));
          }
        }, 0);
      }

      close() {
        this.readyState = MockVisionWebSocket.CLOSED;
        this.onclose?.(new CloseEvent("close"));
      }
    }

    window.WebSocket = MockVisionWebSocket as unknown as typeof WebSocket;
  });
}

async function installMockWebSocket(
  page: import("@playwright/test").Page,
  options: MockWsOptions = {},
) {
  await page.addInitScript((mockOptions: MockWsOptions) => {
    const state = window as typeof window & { __sparkWeaveWsMessages?: Array<Record<string, unknown>> };
    state.__sparkWeaveWsMessages = [];

    class MockWebSocket {
      static readonly CONNECTING = 0;
      static readonly OPEN = 1;
      static readonly CLOSING = 2;
      static readonly CLOSED = 3;

      readonly url: string;
      readyState = MockWebSocket.CONNECTING;
      onopen: ((event: Event) => void) | null = null;
      onmessage: ((event: MessageEvent<string>) => void) | null = null;
      onerror: ((event: Event) => void) | null = null;
      onclose: ((event: CloseEvent) => void) | null = null;

      constructor(url: string | URL) {
        this.url = String(url);
        window.setTimeout(() => {
          this.readyState = MockWebSocket.OPEN;
          this.onopen?.(new Event("open"));
        }, 0);
      }

      send(data: string) {
        const payload = JSON.parse(String(data)) as Record<string, unknown>;
        state.__sparkWeaveWsMessages?.push(payload);
        if (payload.type !== "start_turn") return;
        window.setTimeout(() => {
          this.onmessage?.(
            new MessageEvent("message", {
              data: JSON.stringify({
                type: "session",
                source: "mock",
                stage: "session",
                content: "",
                metadata: { session_id: "session-new", turn_id: "turn-1" },
                session_id: "session-new",
                turn_id: "turn-1",
              }),
            }),
          );
          const events = Array.isArray(mockOptions.events) ? mockOptions.events : [];
          for (const event of events) {
            this.onmessage?.(
              new MessageEvent("message", {
                data: JSON.stringify({
                  source: "mock",
                  stage: "final",
                  content: "",
                  metadata: {},
                  session_id: "session-new",
                  turn_id: "turn-1",
                  ...event,
                }),
              }),
            );
          }
          if (!events.length && mockOptions.resultOnlyContent) {
            this.onmessage?.(
              new MessageEvent("message", {
                data: JSON.stringify({
                  type: "result",
                  source: "mock",
                  stage: "final",
                  content: "",
                  metadata: { response: mockOptions.resultOnlyContent },
                  session_id: "session-new",
                  turn_id: "turn-1",
                }),
              }),
            );
          }
          if (!mockOptions.holdOpen) {
            this.onmessage?.(
              new MessageEvent("message", {
                data: JSON.stringify({
                  type: "done",
                  source: "mock",
                  stage: "done",
                  content: "",
                  metadata: {},
                  session_id: "session-new",
                  turn_id: "turn-1",
                }),
              }),
            );
          }
        }, 0);
      }

      close() {
        this.readyState = MockWebSocket.CLOSED;
        this.onclose?.(new CloseEvent("close"));
      }
    }

    window.WebSocket = MockWebSocket as unknown as typeof WebSocket;
  }, options);
}

