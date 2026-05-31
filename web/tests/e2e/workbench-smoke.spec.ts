import { expect, test } from "@playwright/test";

test("renders the redesigned learning workbench", async ({ page }) => {
  await mockReferenceApis(page);
  await page.goto("/chat");
  await expect(page.getByRole("heading", { name: "AI 学习工作台" })).toBeVisible();
  await expect(page.getByTestId("runtime-status")).toBeVisible();
  await expect(page.getByText("SparkWeave").first()).toBeAttached();
  await expect(page.getByTestId("chat-profile-starter")).toContainText("今天先做这一步");
  await expect(page.getByTestId("chat-profile-guide")).toBeVisible();
  await expect(page.getByRole("button", { name: /发送/ })).toBeVisible();
  await page.getByTestId("chat-context-toggle").click();
  await page.getByText("查看当前状态").click();
  await expect(page.getByTestId("chat-mobile-context-drawer")).toContainText("学习会话");
  await expect(page.getByTestId("chat-mobile-context-drawer")).toContainText("发送消息后创建");
  await expect(page.getByTestId("chat-mobile-context-drawer")).toContainText("当前回答");
  await expect(page.getByTestId("chat-mobile-context-drawer")).not.toContainText("轮次");
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

  await expect(page.getByTestId("chat-profile-starter")).toContainText("做 3 道梯度下降复测题");
  await expect(page.getByTestId("chat-profile-starter")).toContainText("按建议继续");
  await expect(page.getByTestId("chat-profile-starter")).not.toContainText("默认：chat");
  const guideHref = await page.getByTestId("chat-profile-guide").getAttribute("href");
  expect(guideHref).toBe("/knowledge/create");

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

test("chat profile starter uses a simple continue command for profile-guided handoff", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "profile guided handoff smoke runs once");
  await mockReferenceApis(page);
  await installMockWebSocket(page, { resultOnlyContent: "已按建议继续学习。" });

  await page.goto("/chat");
  await expect(page.getByTestId("chat-profile-start")).toContainText("按建议继续");
  await page.getByTestId("chat-profile-start").click();

  await expect
    .poll(async () =>
      page.evaluate(() => {
        const messages = (window as typeof window & { __sparkWeaveWsMessages?: Array<Record<string, unknown>> }).__sparkWeaveWsMessages ?? [];
        return messages.find((message) => message.type === "start_turn") ?? null;
      }),
    )
    .toEqual(
      expect.objectContaining({
        type: "start_turn",
        content: "生成 3 道梯度下降复测题，包含选择、判断和简答。",
        capability: "deep_question",
        config: expect.objectContaining({ purpose: "retest", concept: "梯度下降" }),
      }),
    );
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
  await expect(page.getByTestId("learner-profile-visual-map")).toBeVisible();
  await expect(page.getByTestId("learner-profile-primary-action")).toHaveAttribute("href", /\/guide\?/);

  await page.getByTestId("learner-profile-tab-evidence").click();
  await expect(page.getByTestId("learner-evidence-brief")).toContainText("记录小结");
  await expect(page.getByTestId("learner-evidence-brief")).toContainText("累计参考");
  await expect(page.getByRole("heading", { name: "记录来源" })).toBeVisible();
  await expect(page.getByText("请求", { exact: true })).toBeVisible();
  await expect(page.getByText("公开视频", { exact: true }).first()).toBeVisible();
});

test("memory renders the learner profile visual map", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "visual map smoke runs once");
  await mockReferenceApis(page);

  await page.goto("/memory");
  await expect(page.getByTestId("learner-profile-visual-map")).toBeVisible();
  await expect(page.getByTestId("learner-profile-decision-radar")).toBeVisible();
  await expect(page.getByTestId("learner-profile-evidence-flow")).toContainText("最近学习记录");
  await page.getByTestId("learner-profile-correction-form").scrollIntoViewIfNeeded();
  await expect(page.getByTestId("learner-profile-correction-form")).toBeVisible();
});

test("routes to core workbench areas", async ({ page }) => {
  await page.goto("/knowledge");
  await expect(page.getByRole("heading", { name: "把资料放进来，然后直接提问" })).toBeVisible();
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "需要改什么，就进对应页面" })).toBeVisible();
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
  await page.getByRole("button", { name: "资料与偏好" }).click();
  await expect(page.getByRole("heading", { name: "任务快照" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "自动导学" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "引用素材" })).toBeVisible();
  await expect(page.getByTestId("chat-advanced-settings")).toContainText("更多控制");
  const visibleControl = (name: string) =>
    testInfo.project.name === "mobile" ? page.getByLabel(name).last() : page.getByLabel(name).first();
  await page.getByTestId("chat-advanced-summary").click();
  await page.getByTestId("chat-capability-select").selectOption("deep_question");
  await expect(visibleControl("题目数量")).toBeVisible();
  await expect(page.getByRole("button", { name: /精选视频/ })).toBeVisible();
  await page.getByRole("button", { name: /精选视频/ }).click();
  await page.getByTestId("chat-capability-select").selectOption("visualize");
  await expect(visibleControl("图解形式")).toBeVisible();
  await page.getByTestId("chat-capability-select").selectOption("math_animator");
  await expect(visibleControl("风格提示")).toBeVisible();
});

test("exposes migrated phase-two work areas", async ({ page }) => {
  await mockReferenceApis(page);

  await page.goto("/knowledge");
  await expect(page.getByRole("heading", { name: "把资料放进来，然后直接提问" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "我的资料库" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "先放入一份资料" })).toBeVisible();

  await page.goto("/notebook");
  await expect(page.getByRole("heading", { name: "把学过的内容留下来" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "我的记录本" })).toBeVisible();
  await expect(page.getByRole("button", { name: "新建记录本" }).first()).toBeVisible();

  await page.goto("/question");
  await expect(page.getByRole("heading", { name: "生成一组能立刻作答的练习" })).toBeVisible();
  await expect(page.getByTestId("question-generate-topic")).toBeVisible();

  await page.goto("/vision");
  await expect(page.getByRole("heading", { name: "上传题图，直接得到讲解和作图指令" })).toBeVisible();
  await expect(page.getByRole("button", { name: /解析题图/ })).toBeVisible();

  await page.goto("/memory");
  await expect(page.getByRole("heading", { name: "先看系统建议你做什么" })).toBeVisible();
  await expect(page.getByTestId("learner-profile-overview")).toContainText("现在只做这一件事");
  await expect(page.getByTestId("learner-progress-style-card")).toContainText("你的学习推进方式");
  await expect(page.getByTestId("learner-progress-style-card")).toContainText("系统接下来会优先");
  await expect(page.getByTestId("learner-profile-primary-action")).toHaveAttribute("href", /\/guide\?/);

  await page.goto("/playground");
  await expect(page.getByRole("heading", { name: "先试一遍，再放进学习流程" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "试跑项目" })).toBeVisible();

  await page.goto("/co-writer");
  await expect(page.getByRole("heading", { name: "编辑请求" })).toBeVisible();
  await expect(page.getByRole("button", { name: /生成修改/ })).toBeVisible();

  await page.goto("/guide");
  await expect(page.getByText("今天先做")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1, name: "先创建一条路线" })).toBeVisible();
  await expect(page.getByRole("button", { name: "帮我安排学习" })).toBeVisible();

  await page.goto("/agents");
  await expect(page.getByRole("heading", { name: "让课程助教按时推进" })).toBeVisible();
  await expect(page.getByTestId("agent-workspace-tab-schedule")).toContainText("定时提醒");
  await page.getByTestId("agent-workspace-tab-assistants").click();
  await expect(page.getByRole("heading", { name: "课程助教", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "创建课程助教" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "最近运行" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "试问助教" })).toBeVisible();
  await page.getByTestId("agent-workspace-tab-workspace").click();
  await expect(page.getByRole("heading", { name: "还没有课程助教" })).toBeVisible();
  await expect(page.getByRole("button", { name: "创建助教" })).toBeVisible();

  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "需要改什么，就进对应页面" })).toBeVisible();
  await expect(page.getByTestId("settings-task-grid")).toContainText("连接服务");
  await expect(page.getByTestId("settings-task-grid")).toContainText("工作台偏好");
  await expect(page.getByTestId("settings-task-grid")).toContainText("连接检测");
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
  await expect(page.getByTestId("playground-logs")).toContainText("正在试跑：mock_tool");
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
  await page.getByRole("button", { name: /创建并整理/ }).click();

  await expect(page.getByTestId("knowledge-task-milestones")).toContainText("关键进展");
  await expect(page.getByTestId("knowledge-task-log-details")).toContainText("完整处理记录");
  await expect(page.getByTestId("knowledge-task-logs")).toContainText("资料已保存，正在准备整理");
  await expect(page.getByTestId("knowledge-task-logs")).toContainText("完成: 资料库已创建");
  await expect(page.getByTestId("knowledge-task-logs")).toContainText("进度 parsing 55% 正在解析文件");
  await expect(page.getByTestId("knowledge-task-logs")).toContainText("进度更新: 进度通道保持连接");
  await expect(page.getByTestId("knowledge-task-logs")).not.toContainText("debug");
  await expect(page.getByTestId("knowledge-task-logs")).toContainText("进度 已完成 100% 资料整理完成");
  await expect.poll(() => knowledge.createBody?.includes('name="name"\r\n\r\ncalculus_mock')).toBe(true);
  const wsUrls = await page.evaluate(() => (window as typeof window & { __knowledgeWsUrls?: string[] }).__knowledgeWsUrls ?? []);
  expect(wsUrls.some((url) => url.includes("/api/v1/knowledge/calculus_mock/progress/ws"))).toBe(true);

  await page.goto("/knowledge/settings?kb=calculus_mock");
  await expect(page.getByRole("heading", { name: "资料查找设置" })).toBeVisible();
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
  await expect(page.getByTestId("knowledge-status-strip")).toContainText("资料库");
  await expect(page.getByRole("heading", { name: "calculus_mock" })).toBeVisible();
  await page.getByTestId("knowledge-kb-select-geometry_mock").click();
  await page.locator("details", { hasText: "管理" }).locator("summary").click();
  await page.getByTestId("knowledge-active-set-default").click();
  await expect.poll(() => knowledge.defaultKb).toBe("geometry_mock");
  await expect(page.getByRole("heading", { name: "geometry_mock" })).toBeVisible();
  await expect(page.getByTestId("knowledge-user-start-panel")).toContainText("资料已经准备好");
  await expect(page.getByTestId("knowledge-active-summary-panel")).toContainText("资料细节");
  await expect(page.getByTestId("knowledge-active-summary-panel")).toContainText("triangles");
  await expect(page.getByTestId("knowledge-active-summary-panel")).not.toContainText("{");

  await page.getByTestId("knowledge-primary-upload").click();
  await page.getByTestId("knowledge-upload-files").first().setInputFiles({
    name: "triangles.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("# Triangles\nSimilarity and area."),
  });
  await page.getByRole("button", { name: /上传并整理/ }).click();
  await expect.poll(() => knowledge.uploadTarget).toBe("geometry_mock");
  await expect.poll(() => knowledge.uploadBody?.includes('filename="triangles.md"')).toBe(true);
  await expect(page.getByTestId("knowledge-progress-details")).toContainText("完成");
  await expect(page.getByTestId("knowledge-task-logs")).toContainText("完成: 上传完成");
  await expect(page.getByTestId("knowledge-task-logs")).not.toContainText("Progress cleared for geometry_mock");

  await page.goto("/knowledge?kb=geometry_mock");
  await page.locator("details", { hasText: "管理" }).locator("summary").click();
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

test("chat uses the global left sidebar for session history", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "chat session history smoke runs once");
  await mockReferenceApis(page);
  page.on("dialog", (dialog) => void dialog.accept());

  await page.goto("/chat");
  await expect(page.getByTestId("chat-history-sidebar")).toHaveCount(0);
  await expect(page.getByRole("link", { name: /旧会话 A/ })).toBeVisible();
  await page.getByRole("link", { name: /旧会话 A/ }).click();
  await expect(page.getByText("Loaded assistant answer")).toBeVisible();
  await expect.poll(() => page.evaluate(() => window.location.pathname)).toBe("/chat/session-old-a");
});

test("chat refreshes saved session history after a new websocket turn", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "new chat persistence smoke runs once");
  await mockReferenceApis(page);
  await installMockWebSocket(page, { resultOnlyContent: "这轮回答已经保存。" });

  let sessionListRequests = 0;
  await page.route(/\/api\/v1\/sessions\?/, (route) => {
    sessionListRequests += 1;
    const sessions = [
      ...(sessionListRequests > 1
        ? [
            {
              id: "session-new",
              session_id: "session-new",
              title: "检查会话保存",
              created_at: 1_700_000_500,
              updated_at: 1_700_000_600,
              message_count: 2,
              preferences: { capability: "chat", tools: [], knowledge_bases: [], language: "zh" },
            },
          ]
        : []),
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
    return route.fulfill({ json: { sessions } });
  });

  await page.goto("/chat");
  await page.locator("textarea").first().fill("检查会话保存");
  await page.locator("textarea").first().press("Enter");

  await expect.poll(() => page.evaluate(() => window.location.pathname)).toBe("/chat");
  await expect.poll(() => sessionListRequests).toBeGreaterThan(1);
  await expect(page.getByRole("link", { name: /检查会话保存/ })).toBeVisible();
});

test("question lab streams generated questions and saves a notebook record", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "question lab websocket smoke runs once");
  const reference = await mockReferenceApis(page);
  await installMockQuestionWebSocket(page);

  await page.goto("/question");
  await expect(page.getByRole("heading", { name: "生成一组能立刻作答的练习" })).toBeVisible();
  await page.getByTestId("question-topic-input").fill("函数极限");
  await page.getByTestId("question-generate-topic").click();

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

  await expect(page.getByTestId("question-lab-events")).toContainText("正在确定题型、考点和解析结构");
  await expect(page.getByTestId("question-lab-events")).not.toContainText("progress");
  await expect(page.getByText("函数极限存在的充分条件是什么？")).toBeVisible();
  await page.getByTestId("quiz-option-0-A").click();
  await page.getByTestId("quiz-submit").click();
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

test("question lab mirrors wrong answers without duplicating learner evidence", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "question lab practice write-back smoke runs once");
  const reference = await mockReferenceApis(page);
  await installMockQuestionWebSocket(page);

  await page.goto("/question");
  await page.getByTestId("question-topic-input").fill("函数极限");
  await page.getByTestId("question-generate-topic").click();
  await expect(page.getByTestId("quiz-viewer")).toBeVisible();

  await page.getByTestId("quiz-option-0-B").click();
  await page.getByTestId("quiz-submit").click();

  const receipt = page.getByTestId("question-lab-practice-receipt");
  await expect(receipt).toContainText("待复盘");
  await expect(receipt).toContainText("已同步学习记录");
  await expect.poll(() => reference.evidencePayload).toEqual(
    expect.objectContaining({
      id: expect.stringMatching(/_attempt_1$/),
      source: "question_lab",
      verb: "answered",
      score: 0,
      is_correct: false,
      metadata: expect.objectContaining({ question_id: "q-limit-1", attempt_count: 1 }),
    }),
  );
  await expect.poll(() => reference.questionUpsertPayload).toEqual(
    expect.objectContaining({
      session_id: "manual-question-lab",
      question_id: expect.stringMatching(/^lab_.*_q_limit_1$/),
      question: "函数极限存在的充分条件是什么？",
      user_answer: "B",
      is_correct: false,
      record_evidence: false,
    }),
  );

  await page.getByRole("button", { name: /重做本题/ }).click();
  await expect(receipt).toBeHidden();
  await page.getByTestId("quiz-option-0-A").click();
  await page.getByTestId("quiz-submit").click();

  await expect(page.getByTestId("question-lab-practice-receipt")).toContainText("得分 100%");
  await expect.poll(() => reference.evidencePayload).toEqual(
    expect.objectContaining({
      id: expect.stringMatching(/_attempt_2$/),
      source: "question_lab",
      verb: "answered",
      score: 1,
      is_correct: true,
      metadata: expect.objectContaining({ question_id: "q-limit-1", attempt_count: 2 }),
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

  await expect(page.getByTestId("question-lab-events")).toContainText("已提取原试卷的题型与推理节奏");
  await expect(page.getByTestId("question-lab-events")).not.toContainText("mimic template ready");
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
  await expect(page.getByRole("heading", { name: "上传题图，直接得到讲解和作图指令" })).toBeVisible();
  await page.getByLabel("图片 URL").fill("https://example.com/problem.png");
  await page.getByRole("button", { name: /解析题图/ }).click();
  await expect.poll(() => vision.analyzePayload?.image_url).toBe("https://example.com/problem.png");
  await expect(page.getByTestId("vision-ggb-script")).toContainText("Circle");

  await page.getByRole("button", { name: /边解边看/ }).click();
  await expect
    .poll(async () =>
      page.evaluate(() => {
        const state = window as typeof window & { __visionWsMessages?: Array<Record<string, unknown>> };
        return state.__visionWsMessages?.[0] ?? null;
      }),
    )
    .toEqual(expect.objectContaining({ image_url: "https://example.com/problem.png" }));
  await expect(page.getByTestId("vision-events")).toContainText("图形元素已定位");
  await expect(page.getByTestId("vision-events")).not.toContainText("bbox_complete");
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
  test.skip(true, "Replaced by the schedule-first SparkBot workspace smoke tests.");
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
  await expect(page.getByTestId("sparkbot-soul-detail-source")).toContainText("已选择：Socratic Coach");
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

test("sparkbot redesigned route opens schedule workspace and bot roster", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "sparkbot redesigned route smoke runs once");
  const sparkbot = await mockSparkBotApis(page);

  await page.goto("/agents/math_bot/chat");
  await expect.poll(() => sparkbot.recentLimit).toBe(5);
  await expect(page.getByTestId("sparkbot-cron-panel")).toBeVisible();
  await expect(page.getByTestId("sparkbot-rail-math_bot")).toBeVisible();
  await expect(page.getByTestId("sparkbot-rail-writing_bot")).toBeVisible();

  await page.getByTestId("agent-workspace-tab-assistants").click();
  await expect(page.getByTestId("sparkbot-recent-panel")).toContainText("Last geometry reminder");
  await expect(page.getByTestId("sparkbot-card-math_bot")).toBeVisible();
  await expect(page.getByTestId("sparkbot-card-writing_bot")).toBeVisible();
});

test("sparkbot schedule creates and runs cron jobs", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "sparkbot cron smoke runs once");
  const sparkbot = await mockSparkBotApis(page);

  await page.goto("/agents/math_bot/chat");
  await page.getByTestId("sparkbot-cron-name").fill("Morning MCP check");
  await page.getByTestId("sparkbot-cron-kind").selectOption("every");
  await page.getByTestId("sparkbot-cron-every").fill("900");
  await page.getByTestId("sparkbot-cron-message").fill("/help");
  await page.getByTestId("sparkbot-cron-create-submit").click();

  await expect.poll(() => sparkbot.cronCreatePayload).toEqual(
    expect.objectContaining({
      name: "Morning MCP check",
      message: "/help",
      kind: "every",
      every_seconds: 900,
    }),
  );
  await expect(page.getByTestId("sparkbot-cron-job-job-1")).toContainText("Morning MCP check");

  await page.getByTestId("sparkbot-cron-job-job-1").getByRole("button").first().click();
  await expect.poll(() => sparkbot.cronRunTarget).toBe("job-1");
});

test("sparkbot skills and mcp config save from workspace", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "sparkbot skills and mcp smoke runs once");
  const sparkbot = await mockSparkBotApis(page);
  const skillContent = "---\ndescription: Daily review\nalways: true\n---\n# Daily Review\n\nCheck channels and MCP tools.";

  await page.goto("/agents/math_bot/chat");
  await page.getByTestId("agent-workspace-tab-workspace").click();
  await page.getByTestId("sparkbot-skills-panel").waitFor({ state: "visible" });
  await page.getByTestId("sparkbot-skill-name").fill("daily-review");
  await page.getByTestId("sparkbot-skill-content").fill(skillContent);
  await page.getByTestId("sparkbot-skill-save").click();
  await expect.poll(() => sparkbot.skillWritePayload).toEqual({
    botId: "math_bot",
    skillName: "daily-review",
    content: skillContent,
  });

  await page.getByTestId("sparkbot-mcp-name").fill("local-files");
  await page.getByTestId("sparkbot-mcp-type").selectOption("stdio");
  await page.getByTestId("sparkbot-mcp-command").fill("npx");
  await page.getByTestId("sparkbot-mcp-args").fill("-y @modelcontextprotocol/server-filesystem .");
  await page.getByTestId("sparkbot-mcp-save").click();
  await expect.poll(() => sparkbot.updatePayload).toEqual(
    expect.objectContaining({
      tools: expect.objectContaining({
        mcpServers: expect.objectContaining({
          "local-files": expect.objectContaining({
            type: "stdio",
            command: "npx",
            args: ["-y", "@modelcontextprotocol/server-filesystem", "."],
          }),
        }),
      }),
    }),
  );
});

test("sparkbot channel debug streams websocket replies", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "sparkbot websocket smoke runs once");
  await mockSparkBotApis(page);
  await installMockSparkBotWebSocket(page);

  await page.goto("/agents/math_bot/chat");
  await page.getByTestId("agent-workspace-tab-assistants").click();
  const botChat = page.getByTestId("sparkbot-chat");
  await page.getByTestId("sparkbot-chat-input").fill("解释导数");
  await botChat.locator("button[type='submit']").click();

  await expect(botChat).not.toContainText("Planning derivative hint");
  await expect(botChat).toContainText("记得复盘切线斜率。");
  await expect.poll(() =>
    page.evaluate(() => {
      const state = window as typeof window & { __deepSparkBotWsMessages?: Array<Record<string, unknown>> };
      return state.__deepSparkBotWsMessages?.[0] ?? null;
    }),
  ).toEqual(expect.objectContaining({ content: "解释导数", chat_id: "web" }));
});

test("sparkbot profile channels and workspace files save", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "sparkbot profile and files smoke runs once");
  const sparkbot = await mockSparkBotApis(page);

  await page.goto("/agents/math_bot/chat");
  await page.getByTestId("agent-workspace-tab-advanced").click();
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

  await page.getByTestId("agent-workspace-tab-workspace").click();
  const globalChannel = page.getByTestId("sparkbot-global-channel-editor");
  await globalChannel.getByTestId("channel-field-send_tool_hints").click();
  await globalChannel.getByRole("button", { name: "保存全局" }).click();
  await expect.poll(() => sparkbot.updatePayload).toEqual(
    expect.objectContaining({
      channels: expect.objectContaining({
        send_progress: true,
        send_tool_hints: true,
      }),
    }),
  );
  await page.getByTestId("sparkbot-channel-card-web").click();
  await page.getByTestId("channel-field-welcome_text").fill("Hello from web");
  await page.getByTestId("channel-field-rate_limit").fill("9");
  await page.getByRole("button", { name: "保存渠道" }).click();
  await expect.poll(() => sparkbot.updatePayload).toEqual(
    expect.objectContaining({
      channels: expect.objectContaining({
        web: expect.objectContaining({ enabled: true, welcome_text: "Hello from web", rate_limit: 9 }),
      }),
    }),
  );

  await page.getByTestId("sparkbot-file-SOUL.md").click();
  await expect(page.getByTestId("sparkbot-file-content")).toHaveValue(/# Math Bot/);
  await page.getByTestId("sparkbot-file-content").fill("# Math Bot\n\nUpdated prompt");
  await page.getByTestId("sparkbot-file-save").click();
  await expect.poll(() => sparkbot.fileWritePayload).toEqual({
    botId: "math_bot",
    filename: "SOUL.md",
    content: "# Math Bot\n\nUpdated prompt",
  });
});

test("sparkbot simple create and lifecycle buttons call endpoints", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "sparkbot create and lifecycle smoke runs once");
  const sparkbot = await mockSparkBotApis(page);

  await page.goto("/agents/math_bot/chat");
  await page.getByTestId("agent-workspace-tab-assistants").click();
  await page.getByTestId("assistant-create-bot-id").fill("channel-agent");
  await page.getByTestId("assistant-create-name").fill("Channel Agent");
  await page.getByTestId("assistant-create-submit").click();
  await expect.poll(() => sparkbot.startPayload).toEqual(
    expect.objectContaining({
      bot_id: "channel-agent",
      name: "Channel Agent",
      auto_start: true,
      persona: expect.stringContaining("课程助教"),
    }),
  );

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

test("sparkbot history renders paired backend exchanges", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "sparkbot history smoke runs once");
  test.skip(true, "The redesigned SparkBot page keeps history behind runtime/session storage; core E2E coverage now targets cron, MCP, skills, and channel debug.");
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
  test.skip(true, "Soul library UI was removed from the focused SparkBot surface; persona editing is covered by the profile smoke test.");
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
  test.skip(true, "Replaced by the channel debug websocket smoke test for the redesigned SparkBot page.");
  const sparkbot = await mockSparkBotApis(page);
  await installMockSparkBotWebSocket(page);

  await page.goto("/agents/math_bot/chat");
  const botChat = page.locator("section", { has: page.getByRole("heading", { name: "助教对话" }) });
  await botChat.getByPlaceholder(/向助教提问/).fill("解释导数");
  await botChat.getByRole("button", { name: "发送" }).click();

  await expect(botChat).not.toContainText("Planning derivative hint");
  await expect(botChat.getByText("导数表示瞬时变化率。斜率是 2。")).toBeVisible();
  await expect(botChat.getByText("记得复盘切线斜率。")).toBeVisible();
  await botChat.getByRole("button", { name: "有帮助" }).first().click();
  await expect.poll(() => sparkbot.learningEffectEventPayload).toEqual(
    expect.objectContaining({
      source: "sparkbot",
      verb: "rated",
      object_type: "assistant_response",
      title: "助教回答反馈：有帮助",
    }),
  );
  await expect.poll(() =>
    page.evaluate(() => {
      const state = window as typeof window & { __deepSparkBotWsMessages?: Array<Record<string, unknown>> };
      return state.__deepSparkBotWsMessages?.[0] ?? null;
    }),
  ).toEqual(expect.objectContaining({ content: "解释导数", chat_id: "web" }));
});

test("sparkbot channel editor saves schema driven config", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "sparkbot channel config smoke runs once");
  test.skip(true, "Replaced by focused channel JSON and MCP configuration smoke tests.");
  const sparkbot = await mockSparkBotApis(page);

  await page.goto("/agents/math_bot/chat");
  await page.getByTestId("agent-workspace-tab-advanced").click();
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

  await page.getByTestId("agent-workspace-tab-workspace").click();
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

  await page.getByTestId("agent-workspace-tab-advanced").click();
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
  await expect(page.getByText("运行设置已保存。")).toBeVisible();

  await page.getByTestId("agent-workspace-tab-workspace").click();
  await expect(page.getByRole("heading", { name: "发布渠道" })).toBeVisible();
  await page.getByLabel("Welcome text").fill("Hello from web");
  await page.getByLabel("Rate limit").fill("9");
  await page.getByRole("button", { name: "保存入口" }).click();

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
  test.skip(true, "Replaced by the focused workspace file editor smoke test.");
  const sparkbot = await mockSparkBotApis(page);

  await page.goto("/agents/math_bot/chat");
  await page.getByTestId("agent-workspace-tab-workspace").click();
  await expect(page.getByTestId("assistant-artifacts-panel")).toBeVisible();
  await expect(page.getByTestId("assistant-artifacts-panel")).toContainText("高等数学资料库");
  await expect(page.getByTestId("assistant-artifacts-panel")).toContainText("导数小测");
  await expect(page.getByTestId("assistant-collaboration-route")).toContainText("学习记录");
  await expect(page.getByTestId("assistant-collaboration-route")).toContainText("讯飞多模态");
  await expect(page.getByTestId("assistant-collaboration-route")).toContainText("评估回写");
  await expect(page.getByTestId("assistant-demo-readiness")).toContainText("比赛演示检查");
  await expect(page.getByTestId("assistant-demo-readiness")).toContainText("完整高校课程");
  await expect(page.getByTestId("assistant-demo-readiness")).toContainText("7 分钟录屏路线");
  await expect(page.getByTestId("assistant-demo-readiness")).toContainText("AI Coding");
  await page.getByTestId("assistant-multimodal-action-visual").click();
  await expect(page.getByTestId("sparkbot-chat-input")).toHaveValue(/图解方案/);

  await page.getByTestId("agent-workspace-tab-workspace").click();
  await page.getByTestId("assistant-multimodal-action-tts_script").click();
  await expect(page.getByTestId("assistant-resource-preview")).toContainText("已生成一段可试听语音");
  await expect(page.getByTestId("assistant-tts-preview").locator("audio")).toBeVisible();

  await page.getByTestId("assistant-multimodal-action-ocr").click();
  await page.getByTestId("assistant-ocr-file-input").setInputFiles({
    name: "derivative-note.png",
    mimeType: "image/png",
    buffer: Buffer.from("fake-png"),
  });
  await expect(page.getByTestId("assistant-ocr-preview")).toContainText("识别出的导数讲义内容");
  await page.getByTestId("assistant-ocr-send").click();
  await expect(page.getByTestId("sparkbot-chat-input")).toHaveValue(/识别出的导数讲义内容/);
  await page.getByTestId("agent-workspace-tab-workspace").click();
  await page.getByTestId("sparkbot-files-toggle").click();
  await expect(page.getByTestId("sparkbot-files-toggle")).toContainText("课程资料");
  await expect(page.getByTestId("sparkbot-file-content")).toHaveValue(/高等数学：极限与导数/);
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

test("sparkbot create wizard builds a course assistant preset", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "sparkbot create wizard smoke runs once");
  test.skip(true, "Course assistant wizard was removed from the focused SparkBot surface; simple SparkBot creation is covered separately.");
  const sparkbot = await mockSparkBotApis(page);

  await page.goto("/agents/math_bot/chat");
  await expect(page.getByTestId("assistant-create-step-0")).toContainText("大模型与智能学习系统");
  await page.getByTestId("assistant-course-higher_math_limits_derivatives").click();
  await page.getByTestId("assistant-create-next-style").click();
  await page.getByTestId("assistant-style-practice").click();
  await page.getByTestId("assistant-create-next-confirm").click();
  await expect(page.getByTestId("assistant-create-bot-id")).toHaveValue("higher_math_derivatives_tutor");
  await expect(page.getByTestId("assistant-create-name")).toHaveValue("高数导数助教");
  await expect(page.getByTestId("assistant-create-persona")).toHaveValue(/短练习/);
  await page.getByTestId("assistant-create-submit").click();

  await expect.poll(() => sparkbot.startPayload).toEqual(
    expect.objectContaining({
      bot_id: "higher_math_derivatives_tutor",
      name: "高数导数助教",
      description: expect.stringContaining("错因复盘"),
      auto_start: true,
      persona: expect.stringContaining("高等数学：极限与导数"),
    }),
  );
});

test("sparkbot lifecycle buttons call start stop and destroy endpoints", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "sparkbot lifecycle smoke runs once");
  test.skip(true, "Replaced by the redesigned SparkBot lifecycle smoke test.");
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
  test.skip(true, "Guide V1 query route was replaced by the Guide V2 task flow; see guide-v2-demo.spec.ts.");
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
  test.skip(true, "Guide V1 notebook save UI was replaced by Guide V2 artifact saving; see guide-v2-demo.spec.ts.");
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
  test.skip(true, "Guide V1 session creation UI was replaced by Guide V2 setup; see guide-v2-demo.spec.ts.");
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
  test.skip(true, "Guide V1 live controls were removed to keep Guide V2 learner-facing and simple.");
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
  test.skip(true, "Guide V1 REST control panel was removed; Guide V2 resource jobs are covered separately.");
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
  test.skip(true, "Guide V1 management flow was retired after the Guide V2 redesign.");
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
  await page.getByTestId("co-writer-source-text").fill("rough note");
  await page.getByTestId("co-writer-instruction").fill("polish this");
  await page.getByTestId("co-writer-stream-submit").click();
  await expect(page.getByText("streamed polished text")).toBeVisible();
  await page.getByTestId("co-writer-stream-toggle").click();
  await expect(page.getByText("规划修改：正在分析原文和修改要求")).toBeVisible();

  await page.getByTestId("co-writer-automark").click();
  await expect(page.getByTestId("co-writer-result")).toContainText("marked rough note");
  await expect(page.getByText("正在自动标注")).toBeVisible();
  await expect.poll(() => coWriter.automarkPayload).toEqual({ text: "rough note" });

  await page.getByTestId("co-writer-quick-edit").click();
  await expect(page.getByText("quick edited text")).toBeVisible();
  await expect(page.getByText("正在快速编辑")).toBeVisible();
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
  const audit = page.locator("section", { has: page.getByRole("heading", { name: "修改记录" }) });
  await expect(audit.getByText("Original proof sketch")).toBeVisible();
  await expect(audit.getByText("Edited proof sketch")).toBeVisible();
  await expect(audit.getByText(/资料查找/)).toBeVisible();
  await page.getByRole("button", { name: /导出文稿/ }).click();
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

  await page.goto("/settings/models?tour=true");
  await expect(page.getByRole("heading", { name: "启动向导" }).first()).toBeVisible();
  await page.getByRole("button", { name: /完成并启动/ }).click();
  await expect.poll(() => tour.completedPayload).toEqual(
    expect.objectContaining({
      catalog: expect.objectContaining({ version: 1 }),
      test_results: expect.objectContaining({ llm: "configured", embedding: "configured" }),
    }),
  );
  await expect(page.getByRole("button", { name: "启动向导已完成" })).toBeDisabled();
});

test("settings saves workbench preferences", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "settings preference smoke runs once");
  const settings = await mockSettingsTourApis(page);

  await page.goto("/settings/preferences");
  await expect(page.getByRole("heading", { name: "工作台偏好" })).toBeVisible();
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

  await page.goto("/settings/diagnostics");
  await page.getByTestId("settings-diagnostics-toggle").click();
  await expect(page.getByRole("heading", { name: "运行概览" })).toBeVisible();
  await expect(page.getByTestId("settings-catalog-snapshot")).toContainText("服务配置概览");
  await expect(page.getByTestId("settings-catalog-snapshot")).toContainText("问答模型");
  await expect(page.getByTestId("settings-catalog-snapshot")).toContainText("gpt-mock");
  await expect(page.getByText("学习服务管理")).toBeVisible();
  await expect(page.getByText("学习流程执行")).toBeVisible();
  await expect(page.getByText("学习入口")).toBeVisible();
  await expect(page.getByText("辅助入口")).toBeVisible();
  await expect(page.getByText("学习向导 · 独立学习服务")).toBeVisible();
});

test("settings shows setup tour status and reopens the guide", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "settings tour status smoke runs once");
  const settings = await mockSettingsTourApis(page);

  await page.goto("/settings/diagnostics");
  await page.getByTestId("settings-diagnostics-toggle").click();
  const panel = page.locator("section", { has: page.getByRole("heading", { name: "启动向导" }) });
  await expect(panel).toBeVisible();
  await expect(panel.getByText("waiting")).toBeVisible();
  await panel.getByTestId("settings-tour-reopen").click();

  await expect.poll(() => settings.reopenCalled).toBe(true);
  await expect(panel.getByText("docker compose up -d --build")).toBeVisible();
});

test("settings streams service checks and applies catalog", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "settings service test smoke runs once");
  const settings = await mockSettingsTourApis(page);
  await installMockSettingsEventSource(page);
  await page.route("**/api/v1/system/status", (route) =>
    route.fulfill({
      json: {
        backend: { status: "online" },
        llm: {
          status: "error",
          error: "Error code: 401 - {'message': 'HMAC secret key does not match'}",
        },
        embeddings: { status: "configured", model: "embedding-mock" },
        search: {
          status: "error",
          error: "Error code: 504 - {'message': 'The upstream server is timing out'}",
        },
        ocr: { status: "optional", provider: "iflytek" },
      },
    }),
  );

  await page.goto("/settings/models");
  await expect(page.getByTestId("settings-status-strip")).toContainText("密钥或鉴权信息不正确");
  await expect(page.getByTestId("settings-status-strip")).toContainText("服务响应超时");
  await expect(page.getByTestId("settings-status-strip")).not.toContainText("HMAC");
  await expect(page.getByTestId("settings-status-strip")).not.toContainText("upstream");
  await page.getByTestId("settings-llm-base-url").fill("https://updated-llm.example/v1");
  await page.getByTestId("settings-llm-model").fill("gpt-updated");
  await page.getByTestId("settings-llm-api-key").fill("sk-updated");
  await page.getByTestId("settings-config-section-search").click();
  await page.getByTestId("settings-search-provider").selectOption("tavily");
  await expect(page.getByTestId("settings-search-base-url")).toHaveValue("https://api.tavily.com/search");
  await page.getByTestId("settings-config-section-embedding").click();
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
  await expect(page.getByText("配置已保存，刷新后即可使用。")).toBeVisible();

  await page.goto("/settings/diagnostics");
  await page.getByTestId("settings-diagnostics-toggle").click();
  await page.getByTestId("settings-probe-llm").click();
  await expect.poll(() => settings.systemProbeTarget).toBe("llm");
  await expect(page.getByTestId("settings-probe-result-llm")).toContainText("连接正常，可以使用");
  await expect(page.getByText("问答模型快速检测通过。")).toBeVisible();

  await page.getByTestId("settings-test-llm").click();
  await expect.poll(() => settings.serviceStartPayload?.service).toBe("llm");
  await expect(page.getByTestId("settings-test-logs")).toContainText("服务响应正常");
  await expect(page.getByText("问答模型检测通过。")).toBeVisible();

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

  await page.goto("/notebook?notebook=nb-link&record=rec-video");
  await expect(page.getByTestId("notebook-record-rec-video")).toContainText("Saved external video asset");
  await expect(page.getByRole("heading", { name: "精选视频资产预览" })).toBeVisible();
  await expect(page.getByTestId("external-video-viewer")).toContainText("梯度下降直观讲解");
  await expect(page.getByTestId("personalization-brief")).toContainText("概念边界不清");
  await expect(page.getByTestId("external-video-watch-plan")).toContainText("先看第一个视频");

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
  await expect(page.getByRole("heading", { name: "把学过的内容留下来" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "我的记录本" })).toBeVisible();
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
  await expect(page.getByTestId("notebook-manual-title")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Competition Review" })).toBeVisible();

  await page.getByTestId("notebook-manual-toggle").click();
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

  await page.getByTestId("notebook-record-management-rec-existing").click();
  await page.getByTestId("notebook-record-delete-rec-existing").click();
  await expect.poll(() => notebook.deletedRecordTarget).toEqual({ notebookId: "nb-existing", recordId: "rec-existing" });

  await page.getByRole("button", { name: "错题本" }).first().click();
  await page.getByTestId("question-entry-bookmark-7").click();
  await expect.poll(() => notebook.entryUpdatePayload).toEqual({ bookmarked: true });
  await expect(page.getByTestId("question-entry-7")).toContainText("中等");

  await page.getByTestId("question-category-create-name").fill("Derivative traps");
  await page.getByTestId("question-category-create-submit").click();
  await expect.poll(() => notebook.categoryCreatePayload).toEqual({ name: "Derivative traps" });

  await expect(page.getByText("如果你从聊天或题目生成结果里复制了记录编号")).toBeVisible();
  await expect(page.getByLabel("答题记录")).toBeVisible();
  await expect(page.getByLabel("题目编号")).toBeVisible();
  await expect(page.getByTestId("question-upsert-difficulty")).toContainText("中等");
  await expect(page.getByText("session_id")).toHaveCount(0);
  await expect(page.getByText("question_id")).toHaveCount(0);
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
  await expect(page.getByText("已写入：Why does factoring help before L'Hopital?")).toBeVisible();
  await page.getByTestId("question-lookup-submit").click();
  await expect.poll(() => notebook.questionLookupTarget).toEqual({ sessionId: "manual-session", questionId: "q-manual" });
  await expect(page.getByText("已找到：Why does factoring help before L'Hopital?")).toBeVisible();

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

  await page.goto("/notebook?notebook=nb-existing");
  await page.getByTestId("notebook-management-toggle").click();
  await page.getByTestId("notebook-delete").click();
  await expect.poll(() => notebook.deletedNotebookId).toBe("nb-existing");
});

test("mobile context drawer opens without DOM errors", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile drawer smoke only");
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/chat");
  await page.getByRole("button", { name: "资料与偏好" }).click();
  await expect(page.getByRole("heading", { name: "自动导学" })).toBeVisible();
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
  let drawer = page.getByTestId("mobile-nav-drawer");
  await drawer.getByRole("link", { name: /^设置$/ }).click();
  await expect.poll(pathname).toBe("/settings");

  await page.getByRole("button", { name: "打开导航" }).click();
  drawer = page.getByTestId("mobile-nav-drawer");
  await drawer.getByText("更多入口").click();
  await drawer.getByRole("link", { name: /课程助教/ }).click();
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
  await expect(page.getByTestId("chat-mobile-context-drawer")).toContainText("已建立");
  await expect(page.getByTestId("chat-mobile-context-drawer")).not.toContainText("session-new");
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
  await page.getByTestId("knowledge-open-create").click();
  await page.getByTestId("knowledge-create-name").fill("calculus_mock");
  await page.getByTestId("knowledge-create-files").setInputFiles({
    name: "limits.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("# Limits\nUse notebook context."),
  });
  await expect(page.getByText("limits.md", { exact: true })).toBeVisible();
  await expect(page.getByTestId("knowledge-create-submit")).toBeEnabled();
  await page.locator('[data-testid="knowledge-create-panel"] form').evaluate((form) => (form as HTMLFormElement).requestSubmit());

  await expect(page.getByTestId("knowledge-task-logs")).toContainText("资料已保存，正在准备整理");
  await expect(page.getByTestId("knowledge-task-logs")).toContainText("整理完成: 资料库已创建");
  await expect(page.getByTestId("knowledge-task-logs")).toContainText("进度 已完成 100% 资料整理完成");
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
  const openMoreKnowledgeWorkspace = async (workspace: string) => {
    const activePanelByWorkspace: Record<string, string> = {
      folders: "knowledge-folder-toggle",
      progress: "knowledge-progress-details",
      upload: "knowledge-upload-panel",
    };
    const activePanel = activePanelByWorkspace[workspace];
    if (activePanel && await page.getByTestId(activePanel).isVisible().catch(() => false)) return;
    const shortcut = page.getByTestId(`knowledge-workspace-shortcut-${workspace}`);
    if (await shortcut.isVisible().catch(() => false)) {
      await shortcut.click();
      return;
    }
    await page.getByTestId("knowledge-workspace-task-header").getByText("更多入口").click();
    const moreItem = page.getByTestId(`knowledge-workspace-more-${workspace}`);
    if (await moreItem.isVisible().catch(() => false)) {
      await moreItem.click();
      return;
    }
    if (activePanel && await page.getByTestId(activePanel).isVisible().catch(() => false)) return;
    if (await shortcut.isVisible().catch(() => false)) {
      await shortcut.click();
      return;
    }
    throw new Error(`Knowledge workspace ${workspace} is not reachable from the current task header.`);
  };

  await page.goto("/knowledge");
  await expect(page.getByTestId("knowledge-detail-panel")).toContainText("calculus_mock");
  await page.getByTestId("knowledge-kb-select-geometry_mock").click();
  await page.getByTestId("knowledge-detail-panel").getByText("管理").click();
  await page.getByTestId("knowledge-active-set-default").click();
  await expect.poll(() => knowledge.defaultKb).toBe("geometry_mock");
  await expect(page.getByTestId("knowledge-detail-panel")).toContainText("geometry_mock");
  await expect(page.getByTestId("knowledge-detail-panel")).toContainText("8 份");

  await page.getByTestId("knowledge-workspace-upload").click();
  await page.getByTestId("knowledge-upload-target").selectOption("geometry_mock");
  await openMoreKnowledgeWorkspace("progress");
  await page.getByTestId("knowledge-progress-clear").click();
  await expect.poll(() => knowledge.clearedProgress).toBe("geometry_mock");
  await expect(page.getByTestId("knowledge-task-logs")).toContainText("已清理进度: geometry_mock");

  await page.getByTestId("knowledge-workspace-shortcut-upload").click();
  await page.getByTestId("knowledge-upload-files").setInputFiles({
    name: "mobile-triangles.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("# Mobile triangles\nSimilarity and area."),
  });
  await page.getByTestId("knowledge-upload-panel").locator("form").evaluate((form) => (form as HTMLFormElement).requestSubmit());
  await expect.poll(() => knowledge.uploadTarget).toBe("geometry_mock");
  await expect.poll(() => knowledge.uploadBody?.includes('filename="mobile-triangles.md"')).toBe(true);
  await openMoreKnowledgeWorkspace("progress");
  await expect(page.getByTestId("knowledge-task-logs")).toContainText("完成: 上传完成");

  await openMoreKnowledgeWorkspace("folders");
  await page.getByTestId("knowledge-folder-toggle").click();
  await page.getByTestId("knowledge-folder-path").fill("C:\\course\\geometry-mobile");
  await page.getByTestId("knowledge-folder-link").click();
  await expect.poll(() => knowledge.linkPayload).toEqual({ folder_path: "C:\\course\\geometry-mobile" });

  await page.getByTestId("knowledge-folder-sync-folder-1").click();
  await expect.poll(() => knowledge.syncTarget).toEqual({ kbName: "geometry_mock", folderId: "folder-1" });
  await openMoreKnowledgeWorkspace("progress");
  await expect(page.getByTestId("knowledge-task-logs")).toContainText("完成: 文件夹同步完成");

  await page.goto("/knowledge/folders?kb=geometry_mock");
  await expect(page.getByTestId("knowledge-folder-toggle")).toBeVisible();
  await page.getByTestId("knowledge-folder-unlink-folder-1").click();
  await expect.poll(() => knowledge.unlinkTarget).toEqual({ kbName: "geometry_mock", folderId: "folder-1" });

  await page.getByTestId("knowledge-workspace-back").click();
  await page.getByTestId("knowledge-detail-panel").getByText("管理").click();
  await page.getByTestId("knowledge-active-delete").click();
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
  await expect(page.getByRole("heading", { name: "我的记录本" })).toBeVisible();

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

  await page.getByTestId("notebook-record-management-rec-existing").click();
  await page.getByTestId("notebook-record-delete-rec-existing").click();
  await expect.poll(() => notebook.deletedRecordTarget).toEqual({ notebookId: "nb-existing", recordId: "rec-existing" });

  await page.getByRole("button", { name: "错题本" }).first().click();
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

  await page.goto("/settings/models");
  await page.getByTestId("settings-llm-base-url").fill("https://mobile-llm.example/v1");
  await page.getByTestId("settings-llm-model").fill("gpt-mobile");
  await page.getByTestId("settings-llm-api-key").fill("sk-mobile");
  await page.getByTestId("settings-config-section-embedding").click();
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

  await page.goto("/settings/diagnostics");
  await page.getByTestId("settings-diagnostics-toggle").click();
  await page.getByTestId("settings-probe-llm").click();
  await expect.poll(() => settings.systemProbeTarget).toBe("llm");
  await expect(page.getByTestId("settings-probe-result-llm")).toContainText("连接正常，可以使用");

  await page.getByTestId("settings-test-llm").click();
  await expect.poll(() => settings.serviceStartPayload?.service).toBe("llm");
  await expect(page.getByTestId("settings-test-logs")).toContainText("服务响应正常");
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

  await page.goto("/settings/diagnostics");
  await page.getByTestId("settings-diagnostics-toggle").click();
  await expect(page.getByTestId("settings-catalog-snapshot")).toContainText("服务配置概览");
  await expect(page.getByTestId("settings-catalog-snapshot")).toContainText("问答模型");
  await expect(page.getByTestId("settings-catalog-snapshot")).toContainText("gpt-mock");
  await expect(page.getByText("学习服务管理")).toBeVisible();
  await expect(page.getByText("学习入口")).toBeVisible();

  await page.getByTestId("settings-tour-reopen").click();
  await expect.poll(() => settings.reopenCalled).toBe(true);
  await expect(page.getByText("docker compose up -d --build", { exact: true })).toBeVisible();

  await page.getByTestId("settings-probe-search").click();
  await expect.poll(() => settings.systemProbeTarget).toBe("search");
  await expect(page.getByTestId("settings-probe-result-search")).toContainText("还没有完成服务配置");

  await page.getByTestId("settings-test-search").click();
  await expect.poll(() => settings.serviceStartPayload?.service).toBe("search");
  await expect(page.getByTestId("settings-test-cancel")).toBeEnabled();
  await page.getByTestId("settings-test-cancel").click();
  await expect.poll(() => settings.cancelTarget).toEqual({ service: "search", runId: "run-search-cancel" });

  await page.goto("/settings/models?tour=true");
  await page.getByRole("button", { name: /完成并启动/ }).click();
  await expect.poll(() => settings.completedPayload).toEqual(
    expect.objectContaining({
      catalog: expect.objectContaining({ version: 1 }),
      test_results: expect.objectContaining({ llm: "configured", embedding: "configured" }),
    }),
  );
  await expect(page.getByRole("button", { name: "启动向导已完成" })).toBeDisabled();

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

  await page.goto("/settings/preferences");
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
  await expect(page.getByText("规划修改：正在分析原文和修改要求")).toBeVisible();

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
  await expect(page.locator("pre").filter({ hasText: /资料查找/ })).toBeVisible();
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
  test.skip(true, "Mobile SparkBot old chat/history assertions were replaced by the desktop core SparkBot E2E contract.");
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
  await expect(botChat).not.toContainText("Planning derivative hint");
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
  await page.getByTestId("agent-workspace-tab-advanced").click();
  await page.getByTestId("bot-profile-toggle").click();
  await expect(page.getByTestId("bot-profile-name")).toHaveValue("Writing Bot");
  await expect(page.getByTestId("bot-profile-model")).toHaveValue("gpt-writing");
  expect(errors).toEqual([]);
  expect(consoleDomErrors).toEqual([]);
});

test("mobile sparkbot manages profile files and lifecycle without DOM errors", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile sparkbot management smoke only");
  test.skip(true, "Mobile SparkBot old management assertions were replaced by the desktop core SparkBot E2E contract.");
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

  await page.getByTestId("agent-workspace-tab-advanced").click();
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

  await page.getByTestId("agent-workspace-tab-workspace").click();
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

  await page.getByTestId("agent-workspace-tab-assistants").click();
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
  test.skip(true, "Soul/schema-channel mobile UI was removed from the focused SparkBot surface.");
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
  await page.getByTestId("agent-workspace-tab-advanced").click();
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

  await page.getByTestId("agent-workspace-tab-workspace").click();
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
  test.skip(true, "Guide V1 mobile websocket controls were removed; Guide V2 demo covers the current flow.");
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
  test.skip(true, "Guide V1 mobile management flow was replaced by Guide V2 setup and artifacts.");
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
  await expect(page.getByTestId("vision-events")).toContainText("图形元素已定位");
  await expect(page.getByTestId("vision-events")).not.toContainText("bbox_complete");
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
  await expect(page.getByTestId("question-lab-events")).toContainText("正在设计题目");
  await expect(page.getByTestId("question-lab-events")).not.toContainText("progress");
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
  await expect(page.getByTestId("question-lab-events")).toContainText("已提取原试卷的题型与推理节奏");
  await expect(page.getByTestId("question-lab-events")).not.toContainText("mimic template ready");
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
  const references = page.locator("section", { has: page.getByRole("heading", { name: "引用素材" }) });
  await expect(references).toBeVisible();
  await references.getByRole("button", { name: /旧会话 A/ }).click();
  await references.getByRole("button", { name: /极限错题/ }).click();
  await page.getByRole("button", { name: "关闭资料与偏好" }).click();

  await page.locator("textarea").first().fill("请结合引用资料总结要点");
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
        content: "请结合引用资料总结要点",
        history_references: ["session-old-a"],
        notebook_references: [{ notebook_id: "nb1", record_ids: ["rec-limit"] }],
      }),
    );
});

test("chat sends an empty tool list when all helpers are disabled", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "tool policy payload smoke runs once");
  await mockReferenceApis(page);
  await installMockWebSocket(page);

  await page.goto("/chat");
  await page.getByTestId("chat-context-toggle").click();
  await page.getByTestId("chat-advanced-summary").click();
  for (const toolId of [
    "canvas",
    "rag",
    "web_search",
    "external_video_search",
    "external_image_search",
    "iflytek_workflow",
    "iflytek_formula_ocr",
    "iflytek_image_understanding",
    "paper_search",
    "code_execution",
    "reason",
  ]) {
    const toggle = page.getByTestId(`tool-toggle-${toolId}`);
    await expect(toggle).toHaveAttribute("aria-pressed", "true");
    await toggle.click();
  }
  await page.mouse.click(20, 20);
  await expect(page.getByTestId("chat-mobile-context-drawer")).not.toBeVisible();

  await page.locator("textarea").first().fill("Just answer directly without helper tools");
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
        content: "Just answer directly without helper tools",
        capability: "chat",
        tools: [],
      }),
    );
});

test("chat can disable canvas while keeping other helper tools", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "canvas tool policy payload smoke runs once");
  await mockReferenceApis(page);
  await installMockWebSocket(page);

  await page.goto("/chat");
  await page.getByTestId("chat-context-toggle").click();
  await page.getByTestId("chat-advanced-summary").click();
  await page.getByTestId("tool-toggle-canvas").click();
  await page.mouse.click(20, 20);
  await expect(page.getByTestId("chat-mobile-context-drawer")).not.toBeVisible();

  await page.locator("textarea").first().fill("Write the plan in chat, do not open canvas");
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
        content: "Write the plan in chat, do not open canvas",
        capability: "chat",
        tools: expect.arrayContaining(["rag", "web_search", "external_video_search", "external_image_search"]),
      }),
    );

  const tools = await page.evaluate(() => {
    const state = window as typeof window & { __sparkWeaveWsMessages?: Array<Record<string, unknown>> };
    const start = state.__sparkWeaveWsMessages?.find((message) => message.type === "start_turn");
    const rawTools = start ? start["tools"] : [];
    return Array.isArray(rawTools) ? rawTools : [];
  });
  expect(tools).not.toContain("canvas");
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
  await expect(page.getByRole("button", { name: "保存当前结果" })).toBeVisible();
  await expect(page.getByRole("button", { name: "复制" })).toBeVisible();
});

test("chat opens editable canvas when the canvas tool is used", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "canvas smoke runs once");
  await mockReferenceApis(page);
  const documentContent = [
    "# 梯度下降学习计划",
    "## 目标",
    "- 第一阶段：用图像理解损失函数和参数更新。",
    "- 第二阶段：对照学习率大小，观察收敛速度和震荡。",
    "- 第三阶段：用一道小题复述每一步的含义。",
    "## 今日安排",
    "1. 先画出一维损失曲线，标记当前位置和负梯度方向。",
    "2. 再记录每次更新后损失值如何变化。",
    "3. 最后写下学习率过大、过小分别会出现什么现象。",
    "## 复盘问题",
    "- 为什么负梯度方向能让损失下降？",
    "- 学习率和收敛稳定性之间是什么关系？",
  ].join("\n\n");
  const documentEvents = [
    {
      type: "tool_call",
      stage: "acting",
      content: "canvas",
      metadata: {
        tool_name: "canvas",
        tool_call_id: "canvas-call-1",
        args: { title: "梯度下降学习计划", operation: "create" },
      },
    },
    {
      type: "tool_result",
      stage: "acting",
      content: "Canvas document ready: 梯度下降学习计划",
      metadata: {
        tool_name: "canvas",
        tool_call_id: "canvas-call-1",
        result_metadata: {
          render_type: "canvas_document",
          tool_name: "canvas",
          canvas_document: {
            title: "梯度下降学习计划",
            content: documentContent,
            operation: "create",
          },
        },
      },
    },
    {
      type: "result",
      stage: "final",
      content: "",
      metadata: {
        response: "已在右侧打开学习计划，可以继续编辑。",
        tool_traces: [
          {
            name: "canvas",
            metadata: {
              render_type: "canvas_document",
              tool_name: "canvas",
              canvas_document: {
                title: "梯度下降学习计划",
                content: documentContent,
                operation: "create",
              },
            },
          },
        ],
      },
    },
  ];
  await page.route(/\/api\/v1\/sessions\/session-new$/, (route) =>
    route.fulfill({
      json: {
        id: "session-new",
        session_id: "session-new",
        title: "帮我写一份梯度下降学习计划",
        active_turn_id: "turn-1",
        preferences: { capability: "chat", tools: [], knowledge_bases: [], language: "zh" },
        messages: [
          { id: "m-user-new", role: "user", content: "帮我写一份梯度下降学习计划", capability: "chat", created_at: 1_700_000_500 },
          {
            id: "m-assistant-new",
            role: "assistant",
            content: "已在右侧打开学习计划，可以继续编辑。",
            capability: "chat",
            events: documentEvents,
            created_at: 1_700_000_501,
          },
        ],
      },
    }),
  );
  await installMockWebSocket(page, {
    events: documentEvents,
  });

  await page.goto("/chat");
  await page.locator("textarea").first().fill("帮我写一份梯度下降学习计划");
  await page.getByTestId("chat-send").click();

  await expect(page.getByTestId("chat-canvas-panel")).toBeVisible();
  await expect(page.getByTestId("chat-canvas-panel")).toContainText("梯度下降学习计划");
  await expect(page.getByTestId("chat-canvas-editor")).toHaveValue(/第一阶段/);
  await expect(page).toHaveURL(/\/chat$/);
  await page.getByTestId("chat-context-toggle").click();
  await expect(page.getByTestId("chat-task-snapshot")).toContainText("准备画布");
  await expect(page.getByTestId("chat-task-snapshot")).toContainText("画布已更新");
  await expect(page.getByTestId("chat-task-snapshot")).not.toContainText("补充资料");
});

test("chat canvas preview keeps its own scroll area", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "canvas preview scroll smoke runs once");
  await mockReferenceApis(page);
  const documentContent = [
    "# Long canvas preview",
    "This document is intentionally long so the preview pane must scroll inside the canvas drawer.",
    ...Array.from({ length: 90 }, (_, index) => [
      `## Section ${index + 1}`,
      `- Learning note ${index + 1}: keep this line readable inside preview mode.`,
      `- Follow-up action ${index + 1}: review, summarize, and continue.`,
    ].join("\n")),
  ].join("\n\n");
  const documentEvents = [
    {
      type: "tool_result",
      stage: "acting",
      content: "Canvas document ready: Long canvas preview",
      metadata: {
        tool_name: "canvas",
        tool_call_id: "canvas-scroll-1",
        result_metadata: {
          render_type: "canvas_document",
          tool_name: "canvas",
          canvas_document: {
            title: "Long canvas preview",
            content: documentContent,
            operation: "create",
          },
        },
      },
    },
    {
      type: "result",
      stage: "final",
      content: "",
      metadata: {
        response: "Canvas is ready.",
        tool_traces: [
          {
            name: "canvas",
            metadata: {
              render_type: "canvas_document",
              tool_name: "canvas",
              canvas_document: {
                title: "Long canvas preview",
                content: documentContent,
                operation: "create",
              },
            },
          },
        ],
      },
    },
  ];

  await installMockWebSocket(page, { events: documentEvents });

  await page.goto("/chat");
  await page.locator("textarea").first().fill("Create a long canvas document");
  await page.getByTestId("chat-send").click();

  await expect(page.getByTestId("chat-canvas-panel")).toBeVisible();
  await page.getByTestId("chat-canvas-preview-toggle").click();
  const preview = page.getByTestId("chat-canvas-preview");
  await expect(preview).toBeVisible();
  await expect(preview).toContainText("Section 90");

  const metrics = await preview.evaluate((element) => {
    const node = element as HTMLElement;
    node.scrollTop = 0;
    node.scrollTop = node.scrollHeight;
    return {
      clientHeight: node.clientHeight,
      scrollHeight: node.scrollHeight,
      scrollTop: node.scrollTop,
    };
  });
  expect(metrics.scrollHeight).toBeGreaterThan(metrics.clientHeight + 200);
  expect(metrics.scrollTop).toBeGreaterThan(0);
});

test("chat lets learners open a normal answer in canvas manually", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "canvas manual smoke runs once");
  const reference = await mockReferenceApis(page);
  const answerContent =
    "这是一个可以继续加工的解释草稿。先说明梯度下降会沿着让损失下降最快的方向更新参数，再提醒学习率决定每一步迈多大，最后用一句话总结：方向由梯度给出，步长由学习率控制。";
  const answerEvents = [
    {
      type: "result",
      stage: "final",
      content: "",
      metadata: {
        response: answerContent,
        document: { title: "普通解释草稿", content: answerContent },
      },
    },
  ];
  await page.route(/\/api\/v1\/sessions\/session-new$/, (route) =>
    route.fulfill({
      json: {
        id: "session-new",
        session_id: "session-new",
        title: "简单解释梯度下降",
        active_turn_id: "turn-1",
        preferences: { capability: "chat", tools: [], knowledge_bases: [], language: "zh" },
        messages: [
          { id: "m-user-new", role: "user", content: "简单解释梯度下降", capability: "chat", created_at: 1_700_000_500 },
          {
            id: "m-assistant-new",
            role: "assistant",
            content: answerContent,
            capability: "chat",
            events: answerEvents,
            created_at: 1_700_000_501,
          },
        ],
      },
    }),
  );
  await installMockWebSocket(page, {
    events: answerEvents,
  });

  await page.goto("/chat");
  await page.locator("textarea").first().fill("简单解释梯度下降");
  await page.getByTestId("chat-send").click();

  await expect(page.getByTestId("chat-canvas-panel")).toHaveCount(0);
  await expect(page).toHaveURL(/\/chat$/);
  await page.getByRole("button", { name: "在画布中编辑" }).click();
  await expect(page.getByTestId("chat-canvas-panel")).toBeVisible();
  await expect(page.getByTestId("chat-canvas-editor")).toHaveValue(/解释草稿/);

  await page.getByTestId("chat-canvas-editor").fill("# 梯度下降解释草稿\n\n已手动补充：学习率控制每一步的步长。");
  await expect(page.getByTestId("chat-canvas-editor")).toHaveValue(/已手动补充/);
  await page.getByTestId("chat-canvas-save").click();
  const modal = page.locator("form", { has: page.getByRole("heading", { name: "保存生成结果" }) });
  await expect(modal).toBeVisible();
  await modal.getByRole("button", { name: "保存" }).click();
  await expect.poll(() => reference.savedPayload).toEqual(
    expect.objectContaining({
      record_type: "chat",
      user_query: "简单解释梯度下降",
      output: expect.stringContaining("已手动补充：学习率控制每一步的步长。"),
    }),
  );
});

test("chat sends the current canvas draft with the next message", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "canvas context smoke runs once");
  await mockReferenceApis(page);
  const answerContent =
    "这是一个可以继续加工的解释草稿。先说明梯度下降会沿着让损失下降最快的方向更新参数，再提醒学习率决定每一步迈多大。";
  const revisedContent = "# 梯度下降解释草稿\n\n梯度下降负责决定参数更新的方向。学习率决定每一步走多远。方向和步长配合好，损失才会稳定下降。";
  const answerEvents = [{ type: "result", stage: "final", content: "", metadata: { response: answerContent } }];
  const revisedEvents = [
    {
      type: "tool_call",
      stage: "acting",
      content: "canvas",
      metadata: {
        tool_name: "canvas",
        tool_call_id: "canvas-update-1",
        args: { title: "梯度下降解释草稿", operation: "update" },
      },
    },
    {
      type: "tool_result",
      stage: "acting",
      content: "Canvas document ready: 梯度下降解释草稿",
      metadata: {
        tool_name: "canvas",
        tool_call_id: "canvas-update-1",
        result_metadata: {
          render_type: "canvas_document",
          tool_name: "canvas",
          canvas_document: {
            title: "梯度下降解释草稿",
            content: revisedContent,
            operation: "update",
          },
        },
      },
    },
    {
      type: "result",
      stage: "final",
      content: "",
      metadata: {
        response: "已在画布中更新压缩后的草稿。",
        tool_traces: [
          {
            name: "canvas",
            metadata: {
              render_type: "canvas_document",
              tool_name: "canvas",
              canvas_document: {
                title: "梯度下降解释草稿",
                content: revisedContent,
                operation: "update",
              },
            },
          },
        ],
      },
    },
  ];
  await page.route(/\/api\/v1\/sessions\/session-new$/, (route) =>
    route.fulfill({
      json: {
        id: "session-new",
        session_id: "session-new",
        title: "简单解释梯度下降",
        active_turn_id: "turn-1",
        preferences: { capability: "chat", tools: [], knowledge_bases: [], language: "zh" },
        messages: [
          { id: "m-user-new", role: "user", content: "简单解释梯度下降", capability: "chat", created_at: 1_700_000_500 },
          {
            id: "m-assistant-new",
            role: "assistant",
            content: answerContent,
            capability: "chat",
            events: answerEvents,
            created_at: 1_700_000_501,
          },
        ],
      },
    }),
  );
  await installMockWebSocket(page, { eventsByTurn: [answerEvents, revisedEvents] });

  await page.goto("/chat");
  await page.getByPlaceholder("输入你想解决的问题...").fill("简单解释梯度下降");
  await page.getByTestId("chat-send").click();
  await expect(page).toHaveURL(/\/chat$/);

  await page.getByRole("button", { name: "在画布中编辑" }).click();
  await page.getByLabel("画布标题").fill("梯度下降解释草稿");
  await page.getByTestId("chat-canvas-editor").fill("# 梯度下降解释草稿\n\n已补充：学习率控制每一步的步长。");
  await expect(page.getByTestId("chat-canvas-context-indicator")).toContainText("梯度下降解释草稿");

  await page.getByPlaceholder("输入你想解决的问题...").fill("把这份草稿压缩成三句话");
  await page.getByTestId("chat-send").click();

  await expect
    .poll(() =>
      page.evaluate(() => {
        const messages = (window as typeof window & { __sparkWeaveWsMessages?: Array<Record<string, unknown>> }).__sparkWeaveWsMessages ?? [];
        return messages.filter((message) => message.type === "start_turn").at(-1) ?? null;
      }),
    )
    .toEqual(
      expect.objectContaining({
        content: "把这份草稿压缩成三句话",
        canvas_context: expect.objectContaining({
          title: "梯度下降解释草稿",
          content: expect.stringContaining("已补充：学习率控制每一步的步长。"),
        }),
      }),
    );
  await expect(page.getByTestId("chat-canvas-editor")).toHaveValue(/方向和步长配合好/);
});

test("chat shows learner-facing collaboration trace while task snapshot shows completion", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "stage completion smoke runs once");
  await mockReferenceApis(page);
  const collaborationEvents = [
    {
      type: "progress",
      source: "dialogue_coordinator",
      stage: "coordinating",
      content: "Awakened Knowledge Visualization Agent.",
      metadata: {
        trace_kind: "agent_handoff",
        profile_hints_applied: true,
        profile_guided: true,
        rewritten_prompt: "围绕梯度下降安排下一步学习材料。",
        collaboration_summary: "画像先提供学习依据，协调智能体再唤醒 Knowledge Visualization Agent 接力。",
        collaboration_route: [
          { key: "profile", label: "学习画像智能体", detail: "提供薄弱点、偏好和下一步任务。" },
          { key: "coordinator", label: "对话协调智能体", detail: "识别意图并决定唤醒哪个专门智能体。" },
          { key: "design", label: "图解设计智能体", detail: "选择适合当前概念的关系图表达方式。" },
          { key: "render", label: "可视化渲染智能体", detail: "生成可展示、可保存的图解产物。" },
        ],
      },
    },
    { type: "tool_call", stage: "retrieval", metadata: { tool: "rag_search" } },
    { type: "tool_result", stage: "retrieval", metadata: { tool: "rag_search" } },
    { type: "stage_start", stage: "thinking" },
    { type: "progress", stage: "thinking", content: "Thinking..." },
    { type: "stage_end", stage: "thinking" },
    { type: "stage_start", stage: "responding" },
    { type: "result", stage: "responding", content: "阶段完成后的最终回答。" },
    { type: "stage_end", stage: "responding" },
    { type: "progress", stage: "writing", content: "Writing final polish..." },
  ];
  await page.route(/\/api\/v1\/sessions\/session-new$/, (route) =>
    route.fulfill({
      json: {
        id: "session-new",
        session_id: "session-new",
        title: "检查阶段状态",
        active_turn_id: "turn-1",
        preferences: { capability: "chat", tools: [], knowledge_bases: [], language: "zh" },
        messages: [
          { id: "m-user-new", role: "user", content: "检查阶段状态", capability: "chat", created_at: 1_700_000_500 },
          {
            id: "m-assistant-new",
            role: "assistant",
            content: "阶段完成后的最终回答。",
            capability: "chat",
            events: collaborationEvents,
            created_at: 1_700_000_501,
          },
        ],
      },
    }),
  );
  await installMockWebSocket(page, {
    holdOpen: true,
    events: collaborationEvents,
  });

  await page.goto("/chat");
  await page.locator("textarea").first().fill("检查阶段状态");
  await page.getByRole("button", { name: /发送/ }).click();

  const messageTrace = page.locator("article").filter({ hasText: "过程明细" }).last();
  const collaboration = page.getByTestId("agent-collaboration").last();
  const route = page.getByTestId("agent-collaboration-route").last();
  await expect(collaboration).toContainText("学习流程");
  await expect(collaboration).toContainText("按你情况调整");
  await expect(collaboration).toContainText("已结合记录");
  await expect(collaboration).toContainText("理解任务");
  await expect(collaboration).toContainText("资料查找");
  await expect(collaboration).toContainText("组织讲解");
  await expect(collaboration).not.toContainText("rag_search");
  await expect(collaboration).not.toContainText("智能体");
  await expect(collaboration).not.toContainText("Agent");
  await expect(collaboration).not.toContainText("画像");
  await expect(collaboration).not.toContainText("唤醒");
  await expect(collaboration).not.toContainText("接力");
  await expect(route).toContainText("处理路线");
  await expect(route).toContainText("围绕梯度下降安排下一步学习材料。");
  await expect(route).toContainText("学习记录");
  await expect(route).toContainText("理解任务");
  await expect(route).toContainText("设计图解");
  await expect(route).toContainText("生成图解");
  await expect(messageTrace).toContainText("过程明细");
  await expect(messageTrace).toContainText("按你情况调整");
  await expect(messageTrace).toContainText("识别任务");
  await expect(messageTrace).toContainText("资料查找");
  await expect(messageTrace).toContainText("已改成：围绕梯度下降安排下一步学习材料。");
  await expect(messageTrace).toContainText("形成回答");
  await expect(messageTrace).not.toContainText("rag_search");
  await expect(messageTrace).not.toContainText("智能体");
  await expect(messageTrace).not.toContainText("Agent");
  await expect(messageTrace).not.toContainText("画像");
  await expect(messageTrace).not.toContainText("唤醒");
  await expect(messageTrace).not.toContainText("接力");
  await expect(messageTrace).not.toContainText("stage_start · thinking");
  await expect(messageTrace).not.toContainText("Thinking...");
  await expect(messageTrace).not.toContainText("Writing final polish");

  await page.getByTestId("chat-context-toggle").click();
  const snapshot = page.getByTestId("chat-task-snapshot");
  await expect(page.getByText("阶段完成后的最终回答。").first()).toBeVisible();
  await expect(snapshot).toContainText("已完成");
  await expect(snapshot).toContainText("最终回答");
  await expect(snapshot).not.toContainText("Thinking...");
  await expect(snapshot).not.toContainText("Writing final polish");
  await expect(snapshot).not.toContainText("stage_start");
  await expect(snapshot).not.toContainText("· thinking");
});

test("chat renders external video results as learner-facing cards", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "external video smoke runs once");
  const reference = await mockReferenceApis(page);
  const externalVideoEvents = [
    {
      type: "result",
      stage: "final",
      content: "",
      metadata: {
        success: true,
        render_type: "external_video",
        response: "已为「梯度下降」筛选 2 个公开视频，建议先看第一个。",
        direct_tool: "external_video_search",
        selected_route: "external_video_search",
        orchestration_mode: "direct_tool",
        learner_profile_hints: {
          current_focus: "梯度下降",
          weak_points: ["概念边界不清"],
          preferences: ["公开视频", "图解"],
          time_budget_minutes: 10,
          next_action: { title: "前测补基：梯度下降的直观理解" },
        },
        videos: [
          {
            title: "梯度下降直观讲解",
            url: "https://www.bilibili.com/video/BV1gradient01",
            embed_url: "https://player.bilibili.com/player.html?bvid=BV1gradient01&page=1",
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
        watch_plan: ["先看第一个视频的直观部分", "暂停记录学习率含义", "回到导学里做一道小题"],
        reflection_prompt: "看完后，用一句话解释学习率太大会发生什么。",
        agent_chain: [
          { label: "画像智能体", detail: "读取学习偏好。" },
          { label: "视频查找", detail: "查找公开视频。" },
          { label: "筛选智能体", detail: "排序候选。" },
        ],
      },
    },
  ];
  await page.route(/\/api\/v1\/sessions\/session-new$/, (route) =>
    route.fulfill({
      json: {
        id: "session-new",
        session_id: "session-new",
        title: "找梯度下降公开视频",
        active_turn_id: "turn-1",
        preferences: { capability: "chat", tools: [], knowledge_bases: [], language: "zh" },
        messages: [
          { id: "m-user-new", role: "user", content: "找梯度下降公开视频", capability: "chat", created_at: 1_700_000_500 },
          {
            id: "m-assistant-new",
            role: "assistant",
            content: "已为「梯度下降」筛选 2 个公开视频，建议先看第一个。",
            capability: "chat",
            events: externalVideoEvents,
            created_at: 1_700_000_501,
          },
        ],
      },
    }),
  );
  await installMockWebSocket(page, {
    events: externalVideoEvents,
  });

  await page.goto("/chat");
  const composer = page.getByPlaceholder("输入你想解决的问题...");
  await expect(composer).toBeVisible();
  await composer.fill("找梯度下降公开视频");
  await expect(page.getByTestId("chat-send")).toBeEnabled();
  await page.getByTestId("chat-send").click();

  await expect(page.getByTestId("external-video-viewer")).toBeVisible();
  await expect(page.getByTestId("personalization-brief")).toContainText("按你的学习情况生成");
  await expect(page.getByTestId("personalization-brief")).toContainText("概念边界不清");
  await expect(page.getByTestId("external-video-watch-plan")).toContainText("暂停记录学习率含义");
  await expect(page.getByTestId("external-video-watch-plan")).toContainText("学习率太大会发生什么");
  await expect(page.getByTestId("external-video-chain")).toContainText("处理过程");
  await expect(page.getByTestId("external-video-chain")).toContainText("学习记录");
  await expect(page.getByTestId("external-video-chain")).toContainText("视频查找");
  await expect(page.getByTestId("external-video-chain")).not.toContainText("智能体");
  await expect(page.getByTestId("external-video-chain")).not.toContainText("工具处理");
  await expect(page.getByTestId("external-video-embed")).toBeVisible();
  await page.getByTestId("chat-context-toggle").click();
  await expect(page.getByTestId("chat-task-snapshot")).toContainText("精选视频");
  await expect(page.getByTestId("chat-task-snapshot")).toContainText("精选视频 · 2 个");
  await page.getByRole("button", { name: "关闭资料与偏好" }).click();
  await page.getByTestId("external-video-mark-viewed").click();
  await expect(page.getByText("梯度下降直观讲解")).toBeVisible();
  await expect(page.getByRole("link", { name: "打开观看" }).first()).toBeVisible();
  await expect(page.getByTestId("external-video-evidence-0")).toContainText("已记入学习记录");
  await expect(page.getByTestId("external-video-mark-viewed")).toContainText("已记入学习记录");
  await expect.poll(() => reference.evidencePayload).toEqual(
    expect.objectContaining({
      source: "resource",
      verb: "viewed",
      object_type: "resource",
      object_id: "https://www.bilibili.com/video/BV1gradient01",
      title: "梯度下降直观讲解",
      resource_type: "external_video",
      metadata: expect.objectContaining({
        rank: 1,
        platform: "Bilibili",
        learner_profile_hints: expect.objectContaining({
          current_focus: "梯度下降",
        }),
      }),
    }),
  );

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
          learner_profile_hints: expect.objectContaining({
            current_focus: "梯度下降",
            weak_points: ["概念边界不清"],
          }),
          videos: expect.arrayContaining([
            expect.objectContaining({ title: "梯度下降直观讲解" }),
          ]),
        }),
      }),
    }),
  );
  expect(String(reference.savedPayload?.output || "")).toContain("暂停记录学习率含义");
  expect(String(reference.savedPayload?.output || "")).toContain("学习率太大会发生什么");
});

test("chat renders external image results as learner-facing cards", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "external image smoke runs once");
  const reference = await mockReferenceApis(page);
  const externalImageEvents = [
    {
      type: "result",
      stage: "final",
      content: "",
      metadata: {
        success: true,
        render_type: "external_image",
        response: "已为「梯度下降」筛选 2 张图解参考，建议先看第二张结构图。",
        direct_tool: "external_image_search",
        selected_route: "external_image_search",
        orchestration_mode: "direct_tool",
        learner_profile_hints: {
          current_focus: "梯度下降",
          weak_points: ["学习率含义"],
          preferences: ["图解", "公开视频"],
          time_budget_minutes: 8,
          next_action: { title: "用图解理解梯度下降" },
        },
        images: [
          {
            title: "搜索：梯度下降示意图",
            url: "https://www.google.com/search?tbm=isch&q=gradient%20descent%20diagram",
            source: "Google Images",
            kind: "search_fallback",
            why_recommended: "补充更多同类参考。",
          },
          {
            title: "梯度下降曲面示意图",
            url: "https://example.com/gradient-diagram",
            image_url: "https://example.com/gradient-diagram.png",
            thumbnail: "https://example.com/gradient-diagram-thumb.png",
            source: "Example",
            width: 1280,
            height: 720,
            why_recommended: "能直观看到沿损失曲面下降的方向。",
          },
        ],
        view_plan: ["先看曲面上的箭头方向", "对照学习率含义找变化幅度", "回到导学里写一句自己的理解"],
        reflection_prompt: "这张图里，学习率对应箭头的哪个变化？",
        agent_chain: [
          { label: "画像智能体", detail: "读取学习偏好。" },
          { label: "图片查找", detail: "查找图解参考。" },
          { label: "筛选智能体", detail: "排序候选。" },
        ],
      },
    },
  ];
  await page.route(/\/api\/v1\/sessions\/session-new$/, (route) =>
    route.fulfill({
      json: {
        id: "session-new",
        session_id: "session-new",
        title: "找梯度下降示意图参考",
        active_turn_id: "turn-1",
        preferences: { capability: "chat", tools: [], knowledge_bases: [], language: "zh" },
        messages: [
          { id: "m-user-new", role: "user", content: "找梯度下降示意图参考", capability: "chat", created_at: 1_700_000_500 },
          {
            id: "m-assistant-new",
            role: "assistant",
            content: "已为「梯度下降」筛选 2 张图解参考，建议先看第二张结构图。",
            capability: "chat",
            events: externalImageEvents,
            created_at: 1_700_000_501,
          },
        ],
      },
    }),
  );
  await installMockWebSocket(page, {
    events: externalImageEvents,
  });

  await page.goto("/chat");
  const composer = page.getByPlaceholder("输入你想解决的问题...");
  await expect(composer).toBeVisible();
  await composer.fill("找梯度下降示意图参考");
  await expect(page.getByTestId("chat-send")).toBeEnabled();
  await page.getByTestId("chat-send").click();

  await expect(page.getByTestId("external-image-viewer")).toBeVisible();
  await expect(page.getByTestId("personalization-brief")).toContainText("按你的学习情况生成");
  await expect(page.getByTestId("personalization-brief")).toContainText("学习率含义");
  await expect(page.getByTestId("external-image-view-plan")).toContainText("对照学习率含义");
  await expect(page.getByTestId("external-image-view-plan")).toContainText("学习率对应箭头");
  await expect(page.getByTestId("external-image-chain")).toContainText("处理过程");
  await expect(page.getByTestId("external-image-chain")).toContainText("学习记录");
  await expect(page.getByTestId("external-image-chain")).toContainText("图片查找");
  await expect(page.getByTestId("external-image-chain")).not.toContainText("智能体");
  await expect(page.getByTestId("external-image-featured")).toHaveAttribute("src", "https://example.com/gradient-diagram.png");
  await page.getByTestId("chat-context-toggle").click();
  await expect(page.getByTestId("chat-task-snapshot")).toContainText("精选图片");
  await expect(page.getByTestId("chat-task-snapshot")).toContainText("精选图片 · 2 张");
  await page.getByRole("button", { name: "关闭资料与偏好" }).click();
  await page.getByTestId("external-image-mark-viewed").click();
  await expect(page.getByText("梯度下降曲面示意图")).toBeVisible();
  await expect(page.getByRole("link", { name: "打开查看" }).first()).toBeVisible();
  await expect(page.getByTestId("external-image-evidence-1")).toContainText("已记入学习记录");
  await expect(page.getByTestId("external-image-mark-viewed")).toContainText("已记入学习记录");
  await expect.poll(() => reference.evidencePayload).toEqual(
    expect.objectContaining({
      source: "resource",
      verb: "viewed",
      object_type: "resource",
      object_id: "https://example.com/gradient-diagram",
      title: "梯度下降曲面示意图",
      resource_type: "external_image",
      metadata: expect.objectContaining({
        rank: 2,
        source: "Example",
        learner_profile_hints: expect.objectContaining({
          current_focus: "梯度下降",
        }),
      }),
    }),
  );

  await page.locator("article").filter({ hasText: "梯度下降曲面示意图" }).getByRole("button", { name: "保存当前结果" }).click();
  const modal = page.locator("form", { has: page.getByRole("heading", { name: "保存生成结果" }) });
  await expect(modal.getByText("精选图片 · 2 张").first()).toBeVisible();
  await modal.getByRole("button", { name: "保存" }).click();
  await expect.poll(() => reference.savedPayload).toEqual(
    expect.objectContaining({
      output: expect.stringContaining("## 精选图片"),
      metadata: expect.objectContaining({
        asset_kind: "精选图片 · 2 张",
        external_image: expect.objectContaining({
          render_type: "external_image",
          learner_profile_hints: expect.objectContaining({
            current_focus: "梯度下降",
            weak_points: ["学习率含义"],
          }),
          images: expect.arrayContaining([
            expect.objectContaining({ title: "梯度下降曲面示意图" }),
          ]),
        }),
      }),
    }),
  );
  expect(String(reference.savedPayload?.output || "")).toContain("对照学习率含义");
  expect(String(reference.savedPayload?.output || "")).toContain("学习率对应箭头");
});

test("chat renders external video fallback search entries clearly", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "external video fallback smoke runs once");
  const reference = await mockReferenceApis(page);
  const fallbackVideoEvents = [
    {
      type: "result",
      stage: "final",
      content: "",
      metadata: {
        success: true,
        render_type: "external_video",
        response: "暂时没有拿到稳定的视频直链，我先准备了公开视频平台搜索入口。",
        fallback_search: true,
        videos: [
          {
            title: "在 Bilibili 搜索：梯度下降",
            url: "https://search.bilibili.com/all?keyword=%E6%A2%AF%E5%BA%A6%E4%B8%8B%E9%99%8D",
            platform: "Bilibili",
            kind: "search_fallback",
            why_recommended: "这是兜底搜索入口，不是已筛好的单个视频。",
          },
          {
            title: "在 YouTube 搜索：梯度下降",
            url: "https://www.youtube.com/results?search_query=%E6%A2%AF%E5%BA%A6%E4%B8%8B%E9%99%8D",
            platform: "YouTube",
            kind: "search_fallback",
          },
        ],
        queries: ["梯度下降 入门 直观 视频 教程"],
      },
    },
  ];
  await page.route(/\/api\/v1\/sessions\/session-new$/, (route) =>
    route.fulfill({
      json: {
        id: "session-new",
        session_id: "session-new",
        title: "找梯度下降讲解视频",
        active_turn_id: "turn-1",
        preferences: { capability: "chat", tools: [], knowledge_bases: [], language: "zh" },
        messages: [
          { id: "m-user-new", role: "user", content: "找梯度下降讲解视频", capability: "chat", created_at: 1_700_000_500 },
          {
            id: "m-assistant-new",
            role: "assistant",
            content: "暂时没有拿到稳定的视频直链，我先准备了公开视频平台搜索入口。",
            capability: "chat",
            events: fallbackVideoEvents,
            created_at: 1_700_000_501,
          },
        ],
      },
    }),
  );
  await installMockWebSocket(page, {
    events: fallbackVideoEvents,
  });

  await page.goto("/chat");
  await page.getByPlaceholder("输入你想解决的问题...").fill("找梯度下降讲解视频");
  await page.getByTestId("chat-send").click();

  await expect(page.getByTestId("external-video-viewer")).toContainText("搜索入口");
  await expect(page.getByTestId("external-video-watch-plan")).toContainText("先打开一个平台搜索入口");
  await expect(page.getByText("在 Bilibili 搜索：梯度下降")).toBeVisible();
  await expect(page.getByRole("link", { name: "打开搜索" }).first()).toBeVisible();
  await page.getByTestId("chat-context-toggle").click();
  await expect(page.getByTestId("chat-task-snapshot")).toContainText("视频搜索入口 · 2 个");
  await page.getByRole("button", { name: "关闭资料与偏好" }).click();

  await page.getByTestId("external-video-open-0").evaluate((node) => {
    node.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
  });
  await expect(page.getByTestId("external-video-evidence-0")).toContainText("已记入学习记录");
  await expect.poll(() => reference.evidencePayload).toEqual(
    expect.objectContaining({
      source: "resource",
      verb: "viewed",
      object_id: "https://search.bilibili.com/all?keyword=%E6%A2%AF%E5%BA%A6%E4%B8%8B%E9%99%8D",
      resource_type: "external_video",
      metadata: expect.objectContaining({
        kind: "search_fallback",
        fallback_search: true,
      }),
    }),
  );

  await page.locator("article").filter({ hasText: "在 Bilibili 搜索：梯度下降" }).getByRole("button", { name: "保存当前结果" }).click();
  const modal = page.locator("form", { has: page.getByRole("heading", { name: "保存生成结果" }) });
  await expect(modal.getByText("视频搜索入口 · 2 个").first()).toBeVisible();
  await modal.getByRole("button", { name: "保存" }).click();
  await expect.poll(() => reference.savedPayload).toEqual(
    expect.objectContaining({
      output: expect.stringContaining("## 视频搜索入口"),
      metadata: expect.objectContaining({
        asset_kind: "视频搜索入口 · 2 个",
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
  await page.getByTestId("visualization-evidence-button").click();
  await expect(page.getByTestId("visualization-evidence-button-recorded")).toContainText("已记入学习记录");
  await expect.poll(() => references.evidencePayload).toEqual(
    expect.objectContaining({
      source: "resource",
      verb: "viewed",
      object_type: "resource",
      resource_type: "visual",
      metadata: expect.objectContaining({ render_type: "mermaid" }),
    }),
  );
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
    evidencePayload?: Record<string, unknown>;
    questionUpsertPayload?: Record<string, unknown>;
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
  const profileEvidenceItems = [
    {
      evidence_id: "evidence-video-open",
      source_id: "evidence.external_video_search",
      source_label: "external_video_search",
      title: "公开视频",
      summary: "用户请求公开视频智能体查找梯度下降资料。",
      created_at: "2026-05-02T08:00:00.000Z",
      metadata: {
        verb: "requested",
        object_type: "learning_preference",
        resource_type: "external_video",
      },
    },
  ];
  const learningEffectAction = {
    id: "nba_retest_gradient_descent",
    type: "retest",
    title: "做 3 道梯度下降复测题",
    reason: "补基后用小测确认是否真的掌握，系统会把结果写回学习画像。",
    target_concepts: ["梯度下降"],
    estimated_minutes: 7,
    priority: 0.94,
    href: "/chat?new=1&capability=deep_question&prompt=%E7%94%9F%E6%88%90%E6%A2%AF%E5%BA%A6%E4%B8%8B%E9%99%8D%E5%A4%8D%E6%B5%8B%E9%A2%98",
    capability: "deep_question",
    prompt: "生成 3 道梯度下降复测题，包含选择、判断和简答。",
    config: { purpose: "retest", concept: "梯度下降" },
    writes_back: ["mastery", "remediation_loop"],
  };
  const learningEffectReport = {
    success: true,
    generated_at: 1_700_001_000,
    course_id: "",
    window: "14d",
    overall: {
      score: 72,
      label: "正在变稳",
      summary: "最近练习显示你已经能跟住直觉解释，但还需要一次复测确认概念边界。",
    },
    dimensions: [
      { id: "mastery", label: "知识掌握", score: 72, status: "watch", evidence: "2 次练习，正确率 70%" },
      { id: "engagement", label: "学习投入", score: 81, status: "good", evidence: "最近主动使用图解和视频" },
      { id: "transfer", label: "迁移应用", score: 58, status: "watch", evidence: "简答题中公式含义解释偏弱" },
    ],
    concepts: [
      {
        concept_id: "gradient-descent",
        title: "梯度下降",
        score: 64,
        status: "watch",
        confidence: 0.82,
        trend: "up",
        evidence_count: 4,
        scored_event_count: 2,
        correct_count: 1,
        incorrect_count: 1,
        open_mistake_count: 1,
        resource_count: 1,
        last_practiced_at: 1_700_000_900,
        next_review_at: 1_700_004_000,
        evidence_refs: ["ev-quiz", "ev-video"],
        common_mistakes: ["概念边界不清"],
        recommendation: "先复测 3 题，再决定是否回到导学。",
      },
    ],
    open_mistakes: [],
    remediation_loop: {
      total: 2,
      pending_remediation_count: 1,
      ready_for_retest_count: 0,
      closed_count: 1,
      items: [
        {
          title: "梯度下降的直观理解",
          concept: "梯度下降",
          status: "pending_remediation",
          status_label: "待补救",
          reason: "概念边界不清",
          evidence_summary: "练习正确率 50%，简答对目标函数解释不稳。",
          next_step: "做 3 道复测题",
          progress_label: "已完成 1/2",
          action_label: "去复测",
          action_href: learningEffectAction.href,
          action_capability: "deep_question",
          action_prompt: learningEffectAction.prompt,
          action_config: learningEffectAction.config,
          created_at: 1_700_000_800,
        },
      ],
    },
    visualization: {
      summary: "从证据到评估再到下一步处方，系统把学习效果整理成可执行闭环。",
      nodes: [
        { id: "evidence", label: "证据流", value: "4 条", detail: "2 次练习 · 1 个资源", tone: "brand" },
        { id: "assessment", label: "效果评估", value: "72 分", detail: "正在变稳", tone: "watch" },
        { id: "dispatch", label: "动态调度", value: "1 个动作", detail: "生成复测任务", tone: "brand" },
        { id: "closed_loop", label: "闭环进度", value: "1/2", detail: "待补 1 · 待测 0", tone: "warning" },
      ],
      edges: [
        { from: "evidence", to: "assessment", label: "汇总" },
        { from: "assessment", to: "dispatch", label: "处方" },
        { from: "dispatch", to: "closed_loop", label: "回写" },
      ],
      dimension_bars: [
        { id: "mastery", label: "知识掌握", score: 72, status: "watch", evidence: "2 次练习" },
        { id: "engagement", label: "学习投入", score: 81, status: "good", evidence: "主动看视频" },
        { id: "transfer", label: "迁移应用", score: 58, status: "watch", evidence: "公式解释偏弱" },
      ],
      evidence_timeline: [
        { id: "ev-quiz", label: "梯度下降练习", detail: "练习作答 · 梯度下降", kind: "quiz", score: 72, created_at: 1_700_000_900 },
        { id: "ev-video", label: "看过精选视频", detail: "资源使用 · 视频", kind: "resource", score: null, created_at: 1_700_000_700 },
      ],
      weak_points: [
        { concept_id: "gradient-descent", title: "梯度下降", score: 64, status: "watch", recommendation: "做一次短复测" },
      ],
      loop: { total: 2, pending: 1, ready_for_retest: 0, closed: 1 },
    },
    learner_receipt: {
      headline: "当前先处理「梯度下降」，再继续推进",
      state_label: "正在变稳",
      score: 72,
      score_label: "72 分",
      confidence_label: "初步可靠",
      evidence_summary: "基于最近 4 条学习证据，其中包含 2 次作答、1 个资源行为。",
      profile_update: "画像已把「梯度下降」标记为「需要补基」，置信度约 82%。",
      next_step: learningEffectAction.title,
      reason: learningEffectAction.reason,
      action_id: learningEffectAction.id,
      action_label: "去复测",
      action_href: learningEffectAction.href,
      writes_back: ["mastery", "profile", "remediation_loop"],
      focus_concepts: [{ concept_id: "gradient-descent", title: "梯度下降", status: "needs_support", status_label: "需要补基", score: 64 }],
      loop: { pending: 1, ready_for_retest: 0, closed: 1 },
    },
    next_actions: [learningEffectAction],
    evidence_refs: [],
    summary: {
      event_count: 4,
      scored_event_count: 2,
      quiz_count: 2,
      resource_count: 1,
      open_mistake_count: 1,
      average_score: 72,
      accuracy: 0.7,
      latest_event_at: 1_700_000_900,
    },
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
  await page.route(/\/api\/v1\/learner-profile\/evidence-preview(?:[?#]|$)/, (route) =>
    route.fulfill({ json: { items: profileEvidenceItems, total: profileEvidenceItems.length } }),
  );
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
  await page.route(/\/api\/v1\/learner-profile\/evidence(?:[?#]|$)/, async (route) => {
    if (route.request().method() === "POST") {
      state.evidencePayload = route.request().postDataJSON() as Record<string, unknown>;
      await route.fulfill({
        json: {
          event: {
            id: "evidence-video-open",
            source: state.evidencePayload.source,
            source_id: state.evidencePayload.source_id,
            actor: state.evidencePayload.actor,
            verb: state.evidencePayload.verb,
            object_type: state.evidencePayload.object_type,
            object_id: state.evidencePayload.object_id,
            title: state.evidencePayload.title,
            summary: state.evidencePayload.summary,
            resource_type: state.evidencePayload.resource_type,
            duration_seconds: state.evidencePayload.duration_seconds,
            confidence: state.evidencePayload.confidence,
            mistake_types: [],
            created_at: 1_700_000_900,
            weight: state.evidencePayload.weight,
            metadata: state.evidencePayload.metadata,
          },
        },
      });
      return;
    }
    await route.fulfill({
      json: {
        items: profileEvidenceItems,
        total: profileEvidenceItems.length,
        summary: {
          event_count: 1,
          by_source: { external_video_search: 1 },
          by_verb: { requested: 1 },
          by_object_type: { learning_preference: 1 },
        },
      },
    });
  });
  await page.route(/\/api\/v1\/learning-effect\/events(?:[?#]|$)/, async (route) => {
    state.evidencePayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      json: {
        event: {
          id: "learning-effect-video-open",
          source: state.evidencePayload.source,
          source_id: state.evidencePayload.source_id,
          actor: state.evidencePayload.actor,
          verb: state.evidencePayload.verb,
          object_type: state.evidencePayload.object_type,
          object_id: state.evidencePayload.object_id,
          title: state.evidencePayload.title,
          summary: state.evidencePayload.summary,
          resource_type: state.evidencePayload.resource_type,
          duration_seconds: state.evidencePayload.duration_seconds,
          confidence: state.evidencePayload.confidence,
          created_at: 1_700_000_900,
          weight: state.evidencePayload.weight,
          metadata: state.evidencePayload.metadata,
        },
      },
    });
  });
  await page.route(/\/api\/v1\/learning-effect\/report(?:[?#]|$)/, (route) => route.fulfill({ json: learningEffectReport }));
  await page.route(/\/api\/v1\/learning-effect\/concepts(?:[?#]|$)/, (route) =>
    route.fulfill({ json: { success: true, course_id: "", window: "14d", items: learningEffectReport.concepts, total: learningEffectReport.concepts.length } }),
  );
  await page.route(/\/api\/v1\/learning-effect\/next-actions(?:[?#]|$)/, (route) =>
    route.fulfill({ json: { success: true, course_id: "", window: "14d", items: learningEffectReport.next_actions, total: learningEffectReport.next_actions.length } }),
  );
  await page.route(/\/api\/v1\/learning-effect\/actions\/([^/?#]+)\/complete$/, (route) =>
    route.fulfill({
      json: {
        success: true,
        event: { id: "learning-effect-action-completed", title: "完成复测任务" },
        report: learningEffectReport,
      },
    }),
  );
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
  await page.route("**/api/v1/question-notebook/entries/upsert", async (route) => {
    state.questionUpsertPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      json: {
        id: 18,
        ...state.questionUpsertPayload,
        categories: [],
        created_at: 1_700_000_400,
        updated_at: 1_700_000_400,
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
    learningEffectEventPayload?: Record<string, unknown>;
    learningEffectCompletedAction?: { actionId: string; payload: Record<string, unknown> };
    ocrPreviewPayload?: Record<string, unknown>;
    startPayload?: Record<string, unknown>;
    stopTarget?: string;
    destroyTarget?: string;
    cronCreatePayload?: Record<string, unknown>;
    cronRunTarget?: string;
    cronTogglePayload?: { jobId: string; enabled: boolean };
    cronDeleteTarget?: string;
    skillWritePayload?: { botId: string; skillName: string; content: string };
  } = {};
  const mathFiles: Record<string, string> = {
    "SOUL.md": "# Math Bot",
    "COURSE.md": "# 高等数学：极限与导数\n\n课程资料包用于演示助教默认打开真实课程材料。",
    "LESSONS.md": "# Lessons\n\n1. 极限直观理解\n2. 导数与切线斜率",
    "QUESTION_BANK.md": "# Question Bank\n\n1. 判断导数是否表示瞬时变化率。",
    "RUBRIC.md": "# Rubric\n\n能解释切线斜率并完成小测。",
    "RESOURCES.md": "# Resources\n\n高等数学导数章节讲义。",
  };
  const skills: Record<string, string> = {
    cron: "---\ndescription: Cron helper\n---\n# Cron\n\nUse scheduled tasks.",
  };
  const cronJobs: Array<any> = [];
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
  await page.route("**/api/v1/system/tts-preview", (route) =>
    route.fulfill({
      status: 200,
      headers: {
        "content-type": "audio/mpeg",
        "x-sparkweave-tts-voice": "mock-iflytek-voice",
      },
      body: Buffer.from([0x49, 0x44, 0x33, 0x04]),
    }),
  );
  await page.route("**/api/v1/system/ocr-preview", async (route) => {
    state.ocrPreviewPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      json: {
        success: true,
        text: "识别出的导数讲义内容：瞬时变化率等于切线斜率。",
        provider: "iflytek",
        model: "iflytek:ocr",
      },
    });
  });
  await page.route("**/api/v1/knowledge/list", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/dashboard/recent?**", (route) => route.fulfill({ json: [] }));
  await page.route(/\/api\/v1\/sessions\?/, (route) => route.fulfill({ json: { sessions: [] } }));
  await page.route("**/api/v1/learner-profile", (route) =>
    route.fulfill({
      json: {
        version: 1,
        generated_at: "2026-05-14T10:00:00",
        confidence: 0.72,
        overview: {
          current_focus: "导数与变化率",
          suggested_level: "巩固",
          preferred_time_budget_minutes: 12,
          summary: "最近适合用小练习巩固概念。",
        },
        stable_profile: { goals: ["完成高数复习"], preferences: ["图解", "小测"] },
        learning_state: { weak_points: [{ label: "切线斜率", severity: "medium", source_ids: [], evidence_count: 2, confidence: 0.7 }], mastery: [] },
        next_action: {
          title: "先做一次导数小测",
          summary: "依据最近的错题记录，先确认瞬时变化率。",
          suggested_prompt: "请带我完成一次导数小测，并在最后复盘错因。",
        },
        recommendations: [],
        sources: [],
        evidence_preview: [],
        data_quality: { source_count: 1, evidence_count: 3 },
      },
    }),
  );
  const learningActions = [
    {
      id: "le_derivative_quiz",
      type: "generate_practice",
      title: "完成导数小测",
      reason: "最近对切线斜率的解释还不稳定。",
      target_concepts: ["导数"],
      estimated_minutes: 8,
      priority: 90,
      href: "/question",
      capability: "deep_question",
      prompt: "请生成 3 道导数小测，并等我作答后分析错因。",
      writes_back: ["mastery", "mistake_review"],
    },
  ];
  await page.route(/\/api\/v1\/learning-effect\/report(?:\?.*)?$/, (route) =>
    route.fulfill({
      json: {
        success: true,
        generated_at: 1_779_000_000,
        course_id: "math",
        window: "14d",
        overall: { score: 66, label: "巩固中", summary: "最近证据显示导数概念需要再练一次。" },
        dimensions: [],
        concepts: [],
        open_mistakes: [],
        remediation_loop: { total: 0, pending_remediation_count: 0, ready_for_retest_count: 0, closed_count: 0, items: [] },
        study_brief: {
          headline: "今天先做导数小测",
          summary: "用 8 分钟确认瞬时变化率和切线斜率。",
          timebox_minutes: 8,
          agenda: [{ label: "小测", minutes: 8, detail: "完成 3 道题", prompt: "请生成 3 道导数小测，并等我作答后分析错因。" }],
          knowledge_evidence: {
            title: "高等数学资料库",
            kb_name: "calculus",
            summary: "导数章节资料已可引用，今天优先围绕切线斜率组织小测和图解。",
            status_label: "可引用",
            focus_query: "导数与变化率",
            ready: true,
            metrics: [
              { label: "资料", value: "3 份" },
              { label: "状态", value: "可引用" },
              { label: "焦点", value: "切线斜率" },
            ],
          },
        },
        knowledge_context: {
          available: true,
          ready: true,
          status: "ready",
          status_label: "可引用",
          kb_name: "calculus",
          provider: "milvus",
          document_count: 3,
          focus_query: "导数与变化率",
          summary: "导数章节资料已就绪，可以作为助教答疑和练习生成的依据。",
          action_label: "打开资料库",
          action_href: "/knowledge",
          can_ground_actions: true,
        },
        next_actions: learningActions,
        evidence_refs: [{ id: "ev-derivative-quiz", title: "导数小测", summary: "最近小测暴露切线斜率薄弱。", resource_type: "quiz" }],
        summary: { event_count: 3 },
      },
    }),
  );
  await page.route(/\/api\/v1\/learning-effect\/next-actions(?:\?.*)?$/, (route) =>
    route.fulfill({ json: { success: true, course_id: "math", window: "14d", items: learningActions, total: learningActions.length } }),
  );
  await page.route("**/api/v1/learning-effect/events", async (route) => {
    state.learningEffectEventPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      json: {
        event: {
          id: "sparkbot-feedback",
          source: state.learningEffectEventPayload.source,
          actor: "learner",
          verb: state.learningEffectEventPayload.verb,
          object_type: state.learningEffectEventPayload.object_type,
          title: state.learningEffectEventPayload.title,
          mistake_types: [],
          created_at: 1_779_000_100,
          weight: 1,
          confidence: state.learningEffectEventPayload.confidence ?? 0.7,
        },
      },
    });
  });
  await page.route(/\/api\/v1\/learning-effect\/actions\/([^/?#]+)\/complete$/, async (route) => {
    const actionId = decodeURIComponent(route.request().url().match(/\/actions\/([^/?#]+)\/complete$/)?.[1] ?? "");
    state.learningEffectCompletedAction = { actionId, payload: route.request().postDataJSON() as Record<string, unknown> };
    await route.fulfill({
      json: {
        event: { id: "completed-action", source: "learning_effect", actor: "learner", verb: "completed", object_type: "learning_action", title: actionId, mistake_types: [], created_at: 1_779_000_200, weight: 1, confidence: 0.8 },
        report: { overall: { score: 70, label: "已更新" }, dimensions: [], concepts: [], open_mistakes: [], next_actions: learningActions, evidence_refs: [], summary: { event_count: 4 } },
      },
    });
  });
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
  await page.route(/\/api\/v1\/(?:sparkbot|sparkbot)\/math_bot\/cron(?:\?include_disabled=true)?$/, async (route) => {
    if (route.request().method() === "POST") {
      const payload = route.request().postDataJSON() as Record<string, unknown>;
      state.cronCreatePayload = payload;
      const job = {
        id: "job-1",
        name: payload.name,
        enabled: true,
        schedule: {
          kind: payload.kind,
          everyMs: Number(payload.every_seconds || 0) * 1000,
          expr: payload.cron_expr ?? null,
          tz: payload.tz ?? null,
          atMs: null,
        },
        payload: {
          message: payload.message,
          deliver: payload.deliver,
          channel: payload.channel,
          to: payload.to,
        },
        state: { nextRunAtMs: 1_779_000_000_000, lastStatus: null },
      };
      cronJobs.splice(0, cronJobs.length, job);
      await route.fulfill({ json: job });
      return;
    }
    await route.fulfill({
      json: {
        status: { enabled: true, jobs: cronJobs.length, nextWakeAtMs: cronJobs[0]?.state?.nextRunAtMs ?? null },
        jobs: cronJobs,
      },
    });
  });
  await page.route(/\/api\/v1\/(?:sparkbot|sparkbot)\/math_bot\/cron\/([^/?#]+)(?:\/run)?$/, async (route) => {
    const url = route.request().url();
    const match = url.match(/\/cron\/([^/?#]+)(?:\/run)?$/);
    const jobId = decodeURIComponent(match?.[1] ?? "job-1");
    if (route.request().method() === "POST" && url.endsWith("/run")) {
      state.cronRunTarget = jobId;
      await route.fulfill({ json: { job_id: jobId, ran: true } });
      return;
    }
    if (route.request().method() === "PATCH") {
      const payload = route.request().postDataJSON() as { enabled?: boolean };
      state.cronTogglePayload = { jobId, enabled: Boolean(payload.enabled) };
      const job = cronJobs.find((item) => item.id === jobId);
      if (job) job.enabled = Boolean(payload.enabled);
      await route.fulfill({ json: job ?? { id: jobId, enabled: Boolean(payload.enabled) } });
      return;
    }
    if (route.request().method() === "DELETE") {
      state.cronDeleteTarget = jobId;
      await route.fulfill({ json: { job_id: jobId, deleted: true } });
      return;
    }
    await route.fulfill({ status: 404, json: { detail: "Cron job not found" } });
  });
  await page.route(/\/api\/v1\/(?:sparkbot|sparkbot)\/math_bot\/skills$/, async (route) => {
    await route.fulfill({
      json: {
        skills: Object.entries(skills).map(([name, content]) => ({
          name,
          source: "workspace",
          editable: true,
          available: true,
          description: name,
          always: content.includes("always: true"),
        })),
      },
    });
  });
  await page.route(/\/api\/v1\/(?:sparkbot|sparkbot)\/math_bot\/skills\/([^/?#]+)$/, async (route) => {
    const skillName = decodeURIComponent(route.request().url().match(/\/skills\/([^/?#]+)$/)?.[1] ?? "cron");
    if (route.request().method() === "PUT") {
      const payload = route.request().postDataJSON() as { content?: string };
      skills[skillName] = String(payload.content ?? "");
      state.skillWritePayload = { botId: "math_bot", skillName, content: skills[skillName] };
      await route.fulfill({
        json: {
          name: skillName,
          source: "workspace",
          editable: true,
          available: true,
          description: skillName,
          always: skills[skillName].includes("always: true"),
          content: skills[skillName],
        },
      });
      return;
    }
    await route.fulfill({
      json: {
        name: skillName,
        source: "workspace",
        editable: true,
        available: true,
        description: skillName,
        always: String(skills[skillName] ?? "").includes("always: true"),
        content: skills[skillName] ?? "",
      },
    });
  });
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
        message: "Use Docker Compose from the project root to start SparkWeave.",
        command: "docker compose up -d --build",
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
        notebooks: [{ id: "nb-link", name: "Deep Link Notebook", description: "Direct route target", record_count: 3 }],
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
          {
            id: "rec-video",
            record_id: "rec-video",
            record_type: "chat",
            title: "Saved external video asset",
            summary: "精选视频 · 2 个",
            user_query: "找梯度下降公开视频",
            output: "## 精选视频\n\n已为「梯度下降」筛选 2 个公开视频。",
            metadata: {
              session_id: "session-video-record",
              asset_kind: "精选视频 · 2 个",
              external_video: {
                success: true,
                render_type: "external_video",
                response: "已为「梯度下降」筛选 2 个公开视频，建议先看第一个。",
                learner_profile_hints: {
                  current_focus: "梯度下降",
                  weak_points: ["概念边界不清"],
                  preferences: ["公开视频", "图解"],
                  time_budget_minutes: 10,
                  next_action: { title: "前测补基：梯度下降的直观理解" },
                },
                videos: [
                  {
                    title: "梯度下降直观讲解",
                    url: "https://www.bilibili.com/video/BV1gradient01",
                    platform: "Bilibili",
                    why_recommended: "贴合当前卡点：概念边界不清。",
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
                  { label: "视频查找", detail: "查找公开视频。" },
                ],
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
type MockWsOptions = { resultOnlyContent?: string; events?: MockWsEvent[]; eventsByTurn?: MockWsEvent[][]; holdOpen?: boolean };

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
    const state = window as typeof window & { __sparkWeaveWsMessages?: Array<Record<string, unknown>>; __sparkWeaveWsTurnCount?: number };
    state.__sparkWeaveWsMessages = [];
    state.__sparkWeaveWsTurnCount = 0;

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
        const turnIndex = state.__sparkWeaveWsTurnCount ?? 0;
        state.__sparkWeaveWsTurnCount = turnIndex + 1;
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
          const turnEvents = Array.isArray(mockOptions.eventsByTurn?.[turnIndex]) ? mockOptions.eventsByTurn?.[turnIndex] : null;
          const events = Array.isArray(turnEvents) ? turnEvents : Array.isArray(mockOptions.events) ? mockOptions.events : [];
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

