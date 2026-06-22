import { expect, test, type Page } from "@playwright/test";

test("guide start page exposes full course templates", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "course template picker runs once");

  await installMockGuideV2ResourceEventSource(page);
  await mockGuideV2StableDemoApis(page);

  await page.goto("/guide");
  await expect(page.getByTestId("guide-course-template-deep_learning_foundations")).toBeVisible();
  await page.getByTestId("guide-course-template-deep_learning_foundations").click();

  await expect(page.getByTestId("guide-goal-input")).toHaveValue(/深度学习|CNN|Transformer/i);
});

test("guide accepts learning effect next-action links as ready-to-start routes", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "effect action handoff runs once");

  await installMockGuideV2ResourceEventSource(page);
  const guide = await mockGuideV2StableDemoApis(page);

  await page.goto("/guide?new=1&effect_action=practice:%E6%A2%AF%E5%BA%A6%E4%B8%8B%E9%99%8D");

  await expect(page.getByTestId("guide-goal-input")).toHaveValue(/梯度下降/);
  await expect(page.getByText("效果评估接力")).toBeVisible();
  await expect(page.getByText("梯度下降").first()).toBeVisible();

  await page.getByRole("button", { name: "帮我安排学习" }).click();

  await expect.poll(() => guide.createPayload?.goal ?? "").toContain("梯度下降");
  await expect.poll(() => guide.createPayload?.source_action?.source).toBe("learning_effect");
  await expect.poll(() => guide.createPayload?.source_action?.kind).toBe("learning_effect_practice");
  await expect.poll(() => guide.createPayload?.source_action?.source_label).toBe("梯度下降");
  await expect.poll(() => guide.createPayload?.source_action?.estimated_minutes).toBe(10);
});

test("guide v2 stable demo runs from seed to wrap-up and course package", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "stable demo flow runs once");

  const consoleDomErrors: string[] = [];
  page.on("pageerror", (error) => consoleDomErrors.push(error.message));
  page.on("console", (message) => {
    const text = message.text();
    if (text.includes("insertBefore") || text.includes("Failed to execute")) {
      consoleDomErrors.push(text);
    }
  });

  await installMockGuideV2ResourceEventSource(page);
  const guide = await mockGuideV2StableDemoApis(page);

  await page.goto("/guide");
  await page.getByTestId("guide-demo-start").click();

  await expect.poll(() => guide.createPayload?.source_action?.source).toBe("demo_seed");
  await expect(page.getByTestId("guide-demo-recording-cue")).toContainText("生成稳定素材");
  await expect(page.getByTestId("guide-demo-task-shortcut")).toBeVisible();

  await page.getByTestId("guide-demo-cue-action").click();
  await expect.poll(() => guide.resourcePayload?.resource_type).toBe("visual");
  await expect.poll(() => guide.resourcePayload?.prompt).toContain("CNN");
  await expect(page.getByTestId("guide-artifact-agent-route")).toContainText("学习流程");
  await expect(page.getByTestId("guide-artifact-agent-route")).toContainText("学习记录");
  await expect(page.getByTestId("guide-artifact-agent-route")).toContainText("图解");

  await page.getByTestId("guide-open-complete-task").click();
  await page.getByTestId("guide-demo-apply-feedback").click();
  await page.getByTestId("guide-submit-task-feedback").click();

  await expect.poll(() => guide.completePayload?.score ?? -1).toBeCloseTo(0.7, 2);
  await expect(page.getByTestId("guide-learning-loop-receipt")).toBeVisible();
  await expect(page.getByTestId("guide-learning-loop-open-memory")).toBeVisible();
  await expect(page.getByTestId("guide-learning-loop-receipt-action")).toHaveAttribute("href", /capability=deep_question/);
  await expect(page.getByTestId("guide-demo-recording-cue")).toContainText("看成果");
  await expect(page.getByTestId("guide-demo-wrap-up")).toBeVisible();

  await page.getByTestId("guide-demo-open-course-package").click();
  await expect(page.getByTestId("guide-course-package-panel")).toBeVisible();
  await expect(page.getByTestId("guide-course-package-panel")).toContainText("稳定演示成果");
  await expect(page.getByTestId("guide-course-package-panel")).not.toContainText("待生成标题");
  await expect(page.getByTestId("guide-iflytek-toolchain-card")).toBeVisible();
  await expect(page.getByTestId("guide-iflytek-toolchain-card")).toContainText("科大讯飞工具链讲法");
  await expect(page.getByTestId("guide-iflytek-toolchain-card")).toContainText("OCR / 公式识别 / 图片理解");
  await expect(page.getByTestId("guide-iflytek-toolchain-card")).toContainText("星辰工作流");
  await expect(page.getByTestId("guide-demo-preflight-card")).toBeVisible();
  await expect(page.getByTestId("guide-demo-preflight-card")).toContainText("赛前一键检查");
  await expect(page.getByTestId("guide-demo-preflight-card")).toContainText("先补");
  await expect(page.getByTestId("guide-demo-recording-checklist")).toBeVisible();
  await expect(page.getByTestId("guide-demo-recording-checklist")).toContainText("7 分钟演示路线");
  await expect(page.getByTestId("guide-demo-recording-checklist")).toContainText("稳定图解素材");
  await expect(page.getByTestId("guide-demo-recording-checklist")).toContainText("录屏前先打开导学路线。");
  await expect(page.getByTestId("guide-demo-recording-checklist")).not.toContainText("7-minute demo route");
  await expect(page.getByTestId("guide-recording-script-cue")).toContainText("讲稿");
  await expect(page.getByTestId("guide-presentation-outline-card")).toBeVisible();
  await expect(page.getByTestId("guide-presentation-outline-card")).toContainText("演示 PPT 骨架");
  await expect(page.getByTestId("guide-presentation-outline-card")).toContainText("项目价值");
  await expect(page.getByTestId("guide-presentation-outline-card")).toContainText("讯飞工具链");
  await expect(page.getByTestId("guide-competition-alignment-card")).toBeVisible();
  await expect(page.getByTestId("guide-competition-alignment-card")).toContainText("赛题五项对齐");
  await expect(page.getByTestId("guide-competition-alignment-card")).toContainText("多步骤协同");
  await expect(page.getByTestId("guide-competition-alignment-card")).toContainText("学习效果评估");
  await expect(page.getByTestId("guide-competition-requirement")).toHaveCount(5);
  await expect(page.getByTestId("guide-agent-collaboration-blueprint")).toBeVisible();
  await expect(page.getByTestId("guide-agent-collaboration-blueprint")).toContainText("多步骤协作蓝图");
  await expect(page.getByTestId("guide-agent-collaboration-blueprint")).toContainText("理解任务");
  await expect(page.getByTestId("guide-defense-qa-card")).toBeVisible();
  await expect(page.getByTestId("guide-defense-qa-card")).toContainText("答辩问答预案");
  await expect(page.getByTestId("guide-defense-qa-card")).toContainText("普通聊天机器人");
  await expect(page.getByTestId("guide-course-package-download")).toBeEnabled();
  await expect(page.getByTestId("guide-course-package-download")).toContainText("下载 Markdown");
  await expect(page.getByTestId("guide-competition-submission-card")).toBeVisible();
  await expect(page.getByTestId("guide-competition-submission-card")).toContainText("比赛提交清单");
  await expect(page.getByTestId("guide-competition-submission-card")).toContainText("演示 PPT");
  await expect(page.getByTestId("guide-ai-coding-statement")).toContainText("AI Coding 工具说明");
  expect(consoleDomErrors).toEqual([]);
});

test("guide normalizes external course demo seeds into task shortcuts", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "external template shortcut smoke runs once");

  await installMockGuideV2ResourceEventSource(page);
  const guide = await mockGuideV2ExternalDemoApis(page);

  await page.goto("/guide");
  await expect(page.getByTestId("guide-demo-task-shortcut")).toBeVisible();
  await expect(page.getByTestId("guide-demo-task-shortcut")).toContainText("Manim");

  await page.getByTestId("guide-demo-generate").click();
  await expect.poll(() => guide.resourcePayload?.resource_type).toBe("video");
  await expect.poll(() => guide.resourcePayload?.prompt).toContain("Manim");
});

test("guide keeps resource alternatives on a separate page", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "resource choice smoke runs once");

  await installMockGuideV2ResourceEventSource(page);
  const guide = await mockGuideV2StableDemoApis(page);

  await page.goto("/guide");
  await page.getByTestId("guide-demo-start").click();

  await expect(page.getByText("现在先看这个")).toBeVisible();
  await expect(page.getByTestId("guide-open-resource-choice")).toContainText("换一种学法");
  await expect(page.getByTestId("guide-resource-choice-quiz")).toHaveCount(0);

  await page.getByTestId("guide-open-resource-choice").click();
  await expect(page.getByRole("heading", { name: "换一种学法" })).toBeVisible();
  await expect(page.getByTestId("guide-resource-choice-visual")).toContainText("推荐");
  await expect(page.getByTestId("guide-resource-choice-quiz")).toContainText("练习");

  await page.getByTestId("guide-resource-choice-quiz").click();
  await expect.poll(() => guide.resourcePayload?.resource_type).toBe("quiz");
  await expect(page.getByText("现在先看这个")).toBeVisible();
});

test("guide quiz shows feedback and writes the attempt back", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "quiz interaction smoke runs once");

  await installMockGuideV2ResourceEventSource(page);
  const guide = await mockGuideV2StableDemoApis(page);

  await page.goto("/guide");
  await page.getByTestId("guide-demo-start").click();

  await page.getByTestId("guide-open-resource-choice").click();
  await page.getByTestId("guide-resource-choice-quiz").click();

  await expect.poll(() => guide.resourcePayload?.resource_type).toBe("quiz");
  await expect(page.getByTestId("guide-artifact-agent-route")).toContainText("出题");
  await expect(page.getByTestId("guide-quiz-preview")).toBeVisible();

  await page.getByTestId("guide-quiz-option-0-B").click();
  await page.getByTestId("guide-quiz-submit-0").click();
  await expect(page.getByText("答对了")).toBeVisible();

  await page.getByTestId("guide-quiz-true-false-1-True").click();
  await page.getByTestId("guide-quiz-submit-1").click();
  await expect(page.getByTestId("guide-quiz-score-preview")).toContainText("2/2");

  await page.getByTestId("guide-quiz-submit-all").click();
  await expect.poll(() => guide.quizPayload?.answers?.length ?? 0).toBe(2);
  await expect(page.getByText(/练习已回写：得分 100%/)).toBeVisible();
});

test("mobile guide v2 keeps the current task flow simple", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile guide v2 smoke only");

  const consoleDomErrors: string[] = [];
  page.on("pageerror", (error) => consoleDomErrors.push(error.message));
  page.on("console", (message) => {
    const text = message.text();
    if (text.includes("insertBefore") || text.includes("Failed to execute")) {
      consoleDomErrors.push(text);
    }
  });

  await installMockGuideV2ResourceEventSource(page);
  const guide = await mockGuideV2StableDemoApis(page);

  await page.goto("/guide");
  await page.getByTestId("guide-demo-start").click();

  await expect.poll(() => guide.createPayload?.source_action?.source).toBe("demo_seed");
  await expect(page.getByText("先做这一件事")).toBeVisible();
  await expect(page.getByText("现在先看这个")).toBeVisible();
  await expect(page.getByTestId("guide-resource-choice-quiz")).toHaveCount(0);

  await page.getByTestId("guide-open-resource-choice").click();
  await expect(page.getByRole("heading", { name: "换一种学法" })).toBeVisible();
  await expect(page.getByTestId("guide-resource-choice-visual")).toContainText("推荐");
  await expect(page.getByTestId("guide-resource-choice-external_video")).toContainText("精选视频");

  await page.getByTestId("guide-resource-choice-external_video").click();
  await expect.poll(() => guide.resourcePayload?.resource_type).toBe("external_video");
  await expect(page.getByText("先做这一件事")).toBeVisible();
  expect(consoleDomErrors).toEqual([]);
});

async function installMockGuideV2ResourceEventSource(page: Page) {
  await page.addInitScript(() => {
    type Listener = (event: MessageEvent<string>) => void;
    const state = window as typeof window & { __guideV2ResourceEventSourceUrls?: string[] };
    state.__guideV2ResourceEventSourceUrls = [];

    class MockEventSource {
      readonly url: string;
      onerror: ((event: Event) => void) | null = null;
      private listeners: Record<string, Listener[]> = {};

      constructor(url: string | URL) {
        this.url = String(url);
        state.__guideV2ResourceEventSourceUrls?.push(this.url);
        window.setTimeout(() => {
          this.emit("status", { message: "queued" });
          this.emit("result", { success: true, artifact_id: "artifact-visual" });
          this.emit("complete", { success: true, task_id: "job-visual" });
        }, 0);
      }

      addEventListener(type: string, listener: Listener) {
        this.listeners[type] = [...(this.listeners[type] ?? []), listener];
      }

      removeEventListener(type: string, listener: Listener) {
        this.listeners[type] = (this.listeners[type] ?? []).filter((item) => item !== listener);
      }

      close() {
        this.listeners = {};
      }

      private emit(type: string, payload: Record<string, unknown>) {
        const event = new MessageEvent(type, { data: JSON.stringify(payload) });
        for (const listener of this.listeners[type] ?? []) {
          listener(event);
        }
      }
    }

    window.EventSource = MockEventSource as unknown as typeof EventSource;
  });
}

async function mockGuideV2StableDemoApis(page: Page) {
  const state: {
    created: boolean;
    createPayload?: {
      goal?: string;
      course_template_id?: string;
      source_action?: {
        source?: string;
        kind?: string;
        source_label?: string;
        estimated_minutes?: number;
      };
    };
    resourcePayload?: { resource_type?: string; prompt?: string };
    completePayload?: { score?: number; reflection?: string };
    quizPayload?: { answers?: Array<{ is_correct?: boolean }>; save_questions?: boolean };
  } = { created: false };

  const profile = {
    version: 1,
    generated_at: "2026-05-01T00:00:00.000Z",
    confidence: 0.82,
    overview: {
      current_focus: "理解 CNN 图像检索流程",
      preferred_time_budget_minutes: 45,
      summary: "演示学习者适合从 CNN 图解进入深度学习路线。",
    },
    stable_profile: {
      goals: ["完成一条可展示的深度学习学习闭环"],
      preferences: ["visual", "practice"],
      strengths: ["Can follow examples"],
      constraints: ["Short recording window"],
    },
    learning_state: {
      weak_points: [{ label: "Concept boundaries", confidence: 0.76, evidence_count: 2 }],
      mastery: [],
    },
    recommendations: ["Start from a compact visual explanation."],
    sources: [],
    evidence_preview: [],
    data_quality: { source_count: 2, evidence_count: 4 },
  };

  const demoSeed = {
    title: "深度学习稳定演示",
    scenario: "学习者从画像进入 CNN 图解资源，再提交反馈形成闭环。",
    persona: {
      name: "Demo learner",
      level: "beginner",
      goal: "理解 CNN 图像检索",
      weak_points: ["CNN 结构和图像检索流程容易混淆", "特征抽取和相似度排序边界不清"],
      preferences: ["visual", "practice"],
    },
    task_chain: [
      {
        task_id: "D5",
        title: "CNN 图像检索流程",
        stage: "D5 visual",
        show: "Generate a compact visual explanation.",
        resource_type: "visual",
        prompt: "Create a visual explanation for CNN image retrieval, feature extraction, similarity scoring and ranking.",
        sample_score: 0.7,
        sample_reflection: "我能看懂图像检索流程，但还需要练习区分特征抽取和分类。",
      },
      {
        task_id: "D9",
        title: "Transformer 对比练习",
        stage: "D9 practice",
        show: "Use a short quiz to validate understanding.",
        resource_type: "quiz",
        prompt: "Create a short quiz comparing CNN, attention and Transformer.",
        sample_score: 0.85,
        sample_reflection: "我能说清 CNN 和 Transformer 的主要差异。",
      },
    ],
    resource_prompts: [
      {
        type: "visual",
        title: "CNN 图像检索图解",
        prompt: "Create a visual explanation for CNN image retrieval.",
      },
    ],
    sample_artifacts: [
      {
        type: "visual",
        title: "稳定图解素材",
        preview: "损失曲线、负梯度方向和学习率对比。",
        demo_action: "现场生成较慢时直接展示这份图解结构。",
        talking_point: "证明资源生成可以沉淀为演示兜底材料。",
        status: "seed",
      },
    ],
    rehearsal_notes: ["Keep the route short and show the feedback loop."],
    report_anchor: { score: 72, readiness: "demo_ready", action: "Open route and course package." },
  };

  const task = {
    task_id: "D5",
    node_id: "DL5",
    type: "resource",
    title: "CNN 图像检索流程",
    instruction: "Use a visual explanation, then explain feature extraction and similarity ranking.",
    status: "pending",
    estimated_minutes: 10,
    success_criteria: ["Explain CNN feature extraction.", "Connect similarity ranking with retrieval results."],
    artifact_refs: [],
    metadata: {},
  };

  const visualArtifact = {
    id: "artifact-visual",
    type: "visual",
    capability: "visualize",
    title: "CNN 图像检索图解",
    created_at: 1_700_000_120,
    result: {
      response: "Use CNN features to represent images, then rank database images by similarity.",
      render_type: "mermaid",
      code: {
        content: "graph LR\nA[Query image] --> B[CNN feature extractor]\nB --> C[Feature vector]\nC --> D[Similarity ranking]\nD --> E[Retrieved images]",
      },
      learner_profile_hints: {
        weak_points: ["Concept boundaries"],
        preferences: ["visual", "practice"],
        next_action: "Review the visual, then submit one reflection.",
      },
    },
  };

  const quizArtifact = {
    id: "artifact-quiz",
    type: "quiz",
    capability: "deep_question",
    title: "CNN 图像检索小测",
    created_at: 1_700_000_130,
    result: {
      response: "Complete the questions, then submit the group to update the route.",
      learner_profile_hints: {
        weak_points: ["Concept boundaries"],
        preferences: ["practice"],
        next_action: "Use a short quiz to confirm understanding.",
      },
      questions: [
        {
          question_id: "q1",
          question_type: "choice",
          question: "In CNN image retrieval, what is usually compared first?",
          options: {
            A: "Image filenames",
            B: "Image feature vectors",
            C: "Raw upload time",
            D: "Only the final class label",
          },
          correct_answer: "B",
          explanation: "Retrieval usually ranks images by similarity between feature vectors.",
          concepts: ["cnn_retrieval"],
        },
        {
          question_id: "q2",
          question_type: "true_false",
          question: "CNN retrieval can use feature vectors rather than only class labels.",
          correct_answer: "True",
          explanation: "Feature vectors keep richer similarity information for retrieval.",
          concepts: ["cnn_features"],
        },
      ],
    },
  };

  const externalVideoArtifact = {
    id: "artifact-external-video",
    type: "external_video",
    capability: "external_video_search",
    title: "CNN 图像检索公开视频",
    created_at: 1_700_000_140,
    result: {
      response: "Pick one short public video, then return to the task.",
      videos: [
        {
          title: "CNN 图像检索入门",
          url: "https://www.bilibili.com/video/BVdemo",
          platform: "Bilibili",
          summary: "A compact explanation for beginners.",
        },
      ],
    },
  };

  const artifactForRequestedResource = () => {
    if (state.resourcePayload?.resource_type === "quiz") return quizArtifact;
    if (state.resourcePayload?.resource_type === "external_video") return externalVideoArtifact;
    return visualArtifact;
  };

  const activeTask = () => (state.resourcePayload ? { ...task, artifact_refs: [artifactForRequestedResource()] } : task);

  const session = {
    session_id: "guide-demo",
    goal: "系统学习深度学习",
    status: "learning",
    created_at: 1_700_000_000,
    updated_at: 1_700_000_100,
    profile: {
      preferences: ["visual", "practice"],
      weak_points: ["Concept boundaries"],
      source_context_summary: "Unified learner profile included.",
    },
    course_map: {
      title: "深度学习",
      nodes: [
        { node_id: "DL1", title: "深度学习绪论", description: "建立课程全景。", status: "completed" },
        { node_id: "DL5", title: "CNN 图像检索", description: "理解特征抽取和相似度排序。", status: "learning" },
      ],
      edges: [{ source: "DL1", target: "DL5" }],
      metadata: {
        course_id: "DL301",
        course_name: "深度学习",
        suggested_weeks: 14,
        credits: 3,
        source_action: { source: "demo_seed" },
        created_from: "demo_seed",
        demo_seed: demoSeed,
      },
    },
    tasks: [task],
    current_task: task,
    evidence: [],
    mastery: { DL5: { score: 0.48, status: "developing" } },
    recommendations: ["先生成一张 CNN 图像检索流程图。"],
    plan_events: [],
    progress: 35,
  };

  const completedSession = {
    ...session,
    current_task: { ...task, status: "completed" },
    tasks: [{ ...task, status: "completed" }],
    progress: 55,
  };

  const sessionForRoute = () => {
    const taskWithArtifacts = activeTask();
    return { ...session, current_task: taskWithArtifacts, tasks: [taskWithArtifacts] };
  };

  const completedSessionForRoute = () => {
    const taskWithArtifacts = activeTask();
    const completedTask = { ...taskWithArtifacts, status: "completed" };
    return { ...completedSession, current_task: completedTask, tasks: [completedTask] };
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
  await page.route("**/api/v1/notebook/list", (route) =>
    route.fulfill({ json: { notebooks: [{ id: "nb-demo", name: "Demo Notebook", record_count: 0 }], total: 1 } }),
  );
  await page.route("**/api/v1/learner-profile", (route) => route.fulfill({ json: profile }));
  await page.route("**/api/v1/learner-profile/refresh", (route) => route.fulfill({ json: profile }));
  await page.route("**/api/v1/guide/v2/templates", (route) =>
    route.fulfill({
      json: {
        templates: [
          {
            id: "deep_learning_foundations",
            title: "完整课程：深度学习",
            course_id: "DL301",
            course_name: "深度学习",
            description: "从神经网络、CNN、注意力机制到 Transformer 和大模型应用，适合展示一门完整高校专业课程。",
            level: "intermediate",
            suggested_weeks: 14,
            credits: 3,
            estimated_minutes: 980,
            default_goal: "系统学习深度学习，先补齐 CNN 图像检索、注意力机制、Transformer 和大模型应用。",
            default_preferences: ["visual", "practice", "external_video"],
            default_time_budget_minutes: 45,
            tags: ["深度学习", "CNN", "Transformer"],
            demo_seed: demoSeed,
          },
        ],
      },
    }),
  );
  await page.route(/\/api\/v1\/guide\/v2\/sessions(?:\?.*)?$/, async (route) => {
    if (route.request().method() === "POST") {
      state.createPayload = route.request().postDataJSON() as typeof state.createPayload;
      state.created = true;
      await route.fulfill({ json: { success: true, session } });
      return;
    }
    await route.fulfill({
      json: {
        sessions: state.created
          ? [{ session_id: "guide-demo", goal: "系统学习深度学习", status: "learning", updated_at: 1_700_000_100, progress: 35 }]
          : [],
      },
    });
  });
  await page.route(/\/api\/v1\/guide\/v2\/sessions\/guide-demo$/, (route) =>
    route.fulfill({ json: state.completePayload ? completedSessionForRoute() : sessionForRoute() }),
  );
  await page.route("**/api/v1/guide/v2/sessions/guide-demo/study-plan", (route) =>
    route.fulfill({
      json: {
        success: true,
        session_id: "guide-demo",
        summary: "Follow the demo route.",
        blocks: [{ id: "B1", title: "Demo block", status: "learning", task_ids: ["D5"], tasks: [task] }],
        checkpoints: [],
      },
    }),
  );
  await page.route("**/api/v1/guide/v2/sessions/guide-demo/diagnostic", (route) =>
    route.fulfill({ json: { success: true, session_id: "guide-demo", status: "completed", summary: "Already calibrated.", questions: [] } }),
  );
  await page.route("**/api/v1/guide/v2/sessions/guide-demo/report", (route) =>
    route.fulfill({
      json: {
        success: true,
        session_id: "guide-demo",
        title: "Demo learning report",
        summary: "The demo learner has a visible feedback loop.",
        overview: { overall_score: 72, progress: 55, completed_tasks: 1, total_tasks: 2 },
        node_cards: [{ node_id: "DL5", title: "CNN 图像检索", mastery_score: 62, suggestion: "先做一次 CNN 图像检索小测。" }],
        feedback_digest: { count: state.completePayload ? 1 : 0, latest: { title: "Feedback recorded", summary: "Profile updated." } },
        learning_effect_report: {
          success: true,
          generated_at: 1_700_000_200,
          course_id: "DL301",
          window: "14d",
          overall: {
            score: state.completePayload ? 72 : 58,
            label: state.completePayload ? "正在变稳" : "等待证据",
            summary: state.completePayload
              ? "本次反思已经写入画像，下一步建议用短复测确认 CNN 图像检索流程。"
              : "完成一次任务后会形成更明确的学习处方。",
          },
          dimensions: [
            { id: "mastery", label: "知识掌握", score: state.completePayload ? 72 : 58, status: "watch", evidence: "导学提交和练习证据" },
            { id: "engagement", label: "学习投入", score: 80, status: "good", evidence: "已生成图解资源" },
          ],
          concepts: [
            {
              concept_id: "cnn-retrieval",
              title: "CNN 图像检索流程",
              score: 0.72,
              status: "developing",
              confidence: 0.82,
              trend: "up",
              evidence_count: state.completePayload ? 3 : 1,
              scored_event_count: state.completePayload ? 2 : 0,
              correct_count: 1,
              incorrect_count: 1,
              open_mistake_count: 1,
              resource_count: 1,
              evidence_refs: ["ev-demo"],
              common_mistakes: ["特征抽取和分类边界不清"],
              recommendation: "进入 Transformer 前先做一次 CNN 图像检索小测。",
            },
          ],
          open_mistakes: [],
          remediation_loop: {
            total: 1,
            pending_remediation_count: state.completePayload ? 1 : 0,
            ready_for_retest_count: 0,
            closed_count: 0,
            items: [],
          },
          visualization: {
            summary: "Evidence flows into profile assessment and then into the next prescription.",
            evidence_timeline: [
              { id: "ev-demo", label: "Reflection submitted", detail: "task feedback · CNN retrieval", kind: "task", score: 70 },
            ],
          },
          next_actions: [
            {
              id: "guide-demo-retest-cnn",
              type: "retest",
              title: "做 3 道 CNN 图像检索复测题",
              reason: "用小测确认图像检索流程是否真正掌握。",
              target_concepts: ["cnn-retrieval"],
              estimated_minutes: 7,
              priority: 0.95,
              href: "/chat?new=1&capability=deep_question&prompt=CNN%20image%20retrieval%20retest",
              capability: "deep_question",
              prompt: "Generate a 3-question CNN image retrieval retest.",
              config: { purpose: "retest" },
              writes_back: ["mastery"],
            },
          ],
          evidence_refs: [],
          summary: {
            event_count: state.completePayload ? 3 : 1,
            scored_event_count: state.completePayload ? 2 : 0,
            quiz_count: 1,
            resource_count: 1,
            open_mistake_count: 1,
            average_score: state.completePayload ? 72 : null,
            accuracy: 0.7,
          },
        },
        action_brief: {
          title: "Open the route and course package",
          summary: "Use the route map and package to show the closed loop.",
          primary_action: { kind: "route_map", label: "Open route", detail: "Show the adjusted route." },
          secondary_actions: [],
          signals: [{ label: "Demo", value: "ready", tone: "brand" }],
        },
        demo_readiness: {
          score: 80,
          label: "Ready for recording",
          summary: "Profile, resource, feedback, report and package can now be shown as one chain.",
          checks: [
            { id: "profile", label: "Profile evidence", status: "ready", detail: "Profile is present." },
            { id: "resource", label: "Resource", status: "ready", detail: "Visual resource was requested." },
            { id: "feedback", label: "Feedback", status: state.completePayload ? "ready" : "partial", detail: "Feedback loop is visible." },
          ],
          next_steps: ["Open the route map, then open the course package."],
        },
      },
    }),
  );
  await page.route("**/api/v1/guide/v2/sessions/guide-demo/course-package", (route) =>
    route.fulfill({
      json: {
        success: true,
        session_id: "guide-demo",
        title: "深度学习课程产出包",
        summary: "面向 7 分钟录屏的深度学习课程产出包。",
        markdown: "# 稳定演示产出包\n\n## 赛题五项对齐\n\n- 已准备录屏和答辩材料。\n",
        course_metadata: { course_id: "DL301", course_name: "深度学习" },
        capstone_project: {
          title: "解释 CNN 图像检索流程",
          scenario: "生成一份 CNN 图解，并完成一次学习反馈闭环。",
          deliverables: ["Route", "CNN Visual", "Feedback"],
          steps: ["Create route", "Generate visual", "Submit feedback"],
          estimated_minutes: 45,
        },
        rubric: [{ criterion: "Closed loop", weight: 60, baseline: "Shows profile to feedback." }],
        portfolio: [],
        review_plan: [{ node_id: "DL5", title: "CNN 图像检索", priority: "high", action: "做一次 CNN 图像检索复测。" }],
        demo_blueprint: {
          title: "7-minute demo route",
          duration_minutes: 7,
          summary: "Show profile, route, resource, feedback, and package.",
          readiness_label: "Ready",
          readiness_score: 82,
          storyline: [{ minute: "0:30", title: "Profile", show: "Open learner profile." }],
          fallbacks: ["Use saved visuals if generation is slow."],
        },
        demo_fallback_kit: {
          title: "Recording fallback kit",
          summary: "Use stable artifacts if live generation is slow.",
          persona: demoSeed.persona,
          assets: [{ type: "visual", title: "CNN 图像检索图解", status: "ready", show: "Use saved visual." }],
          checklist: ["Open guide route before recording."],
        },
        demo_seed_pack: demoSeed,
        demo_preflight: {
          title: "赛前一键检查",
          summary: "围绕深度学习课程检查录屏、答辩和提交材料是否成链。",
          status: "needs_attention",
          score: 75,
          ready_count: 5,
          seed_count: 2,
          total_count: 9,
          next_action: "先生成一份可展示资源。",
          primary_gap: {
            id: "resource",
            label: "多智能体资源",
            status: "todo",
            evidence: "还没有沉淀可展示学习产物。",
            action: "至少生成一份图解、练习、视频或精选公开视频。",
          },
          checks: [
            { id: "profile", label: "学习画像", status: "ready" },
            { id: "route", label: "导学路线", status: "ready" },
            { id: "resource", label: "多智能体资源", status: "todo" },
            { id: "feedback", label: "练习反馈闭环", status: "seed" },
            { id: "report", label: "学习效果报告", status: "ready" },
            { id: "iflytek_toolchain", label: "讯飞工具链证明", status: "ready" },
          ],
        },
        presentation_outline: {
          title: "演示 PPT 骨架",
          summary: "按赛题评分点生成 7 页答辩大纲。",
          course_name: "深度学习",
          slide_count: 7,
          next_action: "把每页 evidence 转成截图或动图。",
          slides: [
            {
              slide_no: 1,
              title: "项目价值：从资源堆叠到学习闭环",
              purpose: "说明项目价值。",
              evidence: "展示画像、路径、资源、练习、反馈和报告闭环。",
              speaker_note: "强调用户只需要跟着当前任务学。",
            },
            {
              slide_no: 2,
              title: "对话式学习画像",
              purpose: "说明系统如何理解学习者。",
              evidence: "根据薄弱点和偏好生成下一步。",
              speaker_note: "展示画像证据。",
            },
            {
              slide_no: 3,
              title: "多智能体协同与讯飞工具链",
              purpose: "说明智能体接力和讯飞工具使用。",
              evidence: "资源链路覆盖图解；讯飞能力落点包含星火、Embedding、OCR 和语音。",
              speaker_note: "展示资源卡片，并说明讯飞能力如何进入学习链。",
            },
          ],
        },
        competition_submission: {
          title: "比赛提交清单",
          summary: "按赛题提交物检查当前课程产出。",
          course_name: "深度学习",
          ready_count: 3,
          seed_count: 1,
          total_count: 7,
          next_action: "补齐 7 分钟演示视频和配套文档说明。",
          checklist: [
            {
              item: "演示 PPT",
              status: "ready",
              evidence: "可复用课程产出包里的 7 分钟演示路线。",
              action: "整理成 5 到 7 页。",
            },
            {
              item: "可运行项目源码与部署配置",
              status: "ready",
              evidence: "包含前端、后端、CLI 和配置示例。",
              action: "提交仓库源码与 README。",
            },
            {
              item: "7 分钟智能体演示视频",
              status: "seed",
              evidence: "已有录屏路线和兜底材料。",
              action: "按录屏检查顺序录制。",
            },
            {
              item: "科大讯飞工具链证明",
              status: "ready",
              evidence: "成果包已整理讯飞能力落点和三段录屏讲法。",
              action: "打开讯飞服务接入概览，说明星火、Embedding、OCR、语音和星辰工作流如何进入学习链。",
            },
            {
              item: "完整高校课程样例",
              status: "ready",
              evidence: "课程模板包含目标、任务和评价方式。",
              action: "随项目一并提交课程数据。",
            },
          ],
        },
        iflytek_toolchain: {
          title: "科大讯飞工具链讲法",
          summary: "把讯飞能力压成一条评委能听懂的学习链：输入先结构化，资料可追溯，辅导可生成，过程可评估。",
          recording_tip: "开场讲接入，中段讲多模态输入进入 Agentic RAG 和智能辅导，收尾讲学习报告与资源推送闭环。",
          items: [
            {
              id: "spark",
              label: "星火大模型",
              landing: "LLM provider `iflytek_spark_ws`",
              demo_value: "对话式辅导、资源生成、学习处方。",
              demo_action: "展示学习页里的问答、路线和课程资源生成结果。",
            },
            {
              id: "embedding",
              label: "星火 Embedding",
              landing: "Embedding provider `iflytek_spark`",
              demo_value: "课程资料向量化，支撑私域资料问答。",
              demo_action: "展示资料库入库后，回答能带回来源证据。",
            },
            {
              id: "vision",
              label: "OCR / 公式识别 / 图片理解",
              landing: "OCR、`iflytek_formula_ocr`、`iflytek_image_understanding`",
              demo_value: "讲义截图、题图公式、板书和实验图先结构化，再进入智能辅导。",
              demo_action: "上传图片或公式题，说明识别结果如何进入解题和检索链路。",
            },
            {
              id: "workflow",
              label: "星辰工作流",
              landing: "`iflytek_workflow`",
              demo_value: "把 PPT 大纲、课程资源生成或诊断报告封装成可复用流程。",
              demo_action: "展示工作流工具调用结果，强调流程可复用、可替换。",
            },
          ],
          demo_cues: [
            {
              label: "开场",
              tone: "brand",
              detail: "打开学习页的比赛演示驾驶舱，说明讯飞能力已经接到同一条学习链。",
            },
            {
              label: "中段",
              tone: "success",
              detail: "展示资料上传、问资料、图片或公式题解析，强调多模态输入会先被讯飞能力结构化。",
            },
            {
              label: "收尾",
              tone: "success",
              detail: "展示学习报告、练习反馈或星辰工作流结果，说明过程记录如何进入效果评估。",
            },
          ],
        },
        competition_alignment: {
          title: "赛题五项对齐",
          summary: "围绕深度学习课程把画像、路径、资源、辅导和评估映射成可录屏证据。",
          course_name: "深度学习",
          coverage_score: 80,
          ready_count: 4,
          seed_count: 1,
          total_count: 5,
          next_action: "展示资源卡里的协作路线。",
          requirements: [
            {
              id: "profile",
              requirement: "对话式学习画像自主构建",
              status: "ready",
              evidence: ["学习目标和薄弱点已经进入画像。"],
              demo_action: "打开学习画像和导学入口。",
            },
            {
              id: "multi_agent",
              requirement: "多智能体协同的资源生成",
              status: "seed",
              evidence: ["画像、图解、出题和评估智能体接力。"],
              demo_action: "展示资源卡里的协作路线。",
            },
            {
              id: "path",
              requirement: "个性化学习路径规划和资源推送",
              status: "ready",
              evidence: ["当前任务和补基路线已经生成。"],
              demo_action: "展示先做这一件事。",
            },
            {
              id: "tutoring",
              requirement: "智能辅导与多模态答疑",
              status: "ready",
              evidence: ["图解、练习和精选视频围绕当前任务生成。"],
              demo_action: "打开一份资源卡片。",
            },
            {
              id: "assessment",
              requirement: "学习效果评估",
              status: "ready",
              evidence: ["提交反馈后生成学习报告和下一步处方。"],
              demo_action: "打开学习报告和课程产出包。",
            },
          ],
        },
        agent_collaboration_blueprint: {
          title: "多智能体协作蓝图",
          summary: "画像、路径、资源和评估智能体围绕当前任务接力。",
          course_name: "深度学习",
          current_task: "理解 CNN 图像检索流程",
          readiness: {
            label: "可排练展示",
            score: 80,
            detail: "赛题五项证据 4/5 已就绪。",
          },
          roles: [
            {
              id: "coordinator",
              name: "对话协调智能体",
              responsibility: "把继续学习请求改写成当前任务。",
              output: "当前任务：CNN 图像检索流程",
            },
            {
              id: "profile",
              name: "画像智能体",
              responsibility: "读取薄弱点和资源偏好。",
              output: "偏好图解和练习。",
            },
            {
              id: "resource_cluster",
              name: "资源生成智能体集群",
              responsibility: "调用图解、出题和视频查找步骤。",
              output: "生成图解、练习和精选视频。",
            },
            {
              id: "assessment",
              name: "评估智能体",
              responsibility: "根据提交反馈回写画像。",
              output: "生成下一步学习处方。",
            },
          ],
          route: [
            { from: "学习者", to: "对话协调智能体", message: "继续学习" },
            { from: "对话协调智能体", to: "画像智能体", message: "读取薄弱点" },
            { from: "画像智能体", to: "路径规划智能体", message: "选择当前任务" },
            { from: "路径规划智能体", to: "资源生成智能体集群", message: "生成资源" },
          ],
          mermaid: "graph LR\n  Learner[学习者] --> Coordinator[对话协调]",
          recording_tip: "录屏时按画像、路径、资源、评估四步讲。",
        },
        defense_qa: {
          title: "答辩问答预案",
          summary: "把评委最可能追问的问题整理成可直接讲的回答。",
          course_name: "深度学习",
          question_count: 2,
          next_action: "每个问题准备一个页面定位。",
          questions: [
            {
              question: "为什么不是普通聊天机器人？",
              answer: "系统会先形成画像，再规划路线、生成资源、收集反馈并调整下一步。",
              evidence: "画像、路线、资源、反馈和报告已经成链。",
              demo_reference: "打开导学首页和学习报告。",
            },
            {
              question: "多智能体协作体现在哪里？",
              answer: "画像、图解、出题和评估智能体会围绕当前任务接力。",
              evidence: "资源卡展示智能体接力。",
              demo_reference: "打开资源卡片。",
            },
          ],
        },
        recording_script: {
          title: "7 分钟录屏讲稿",
          summary: "把演示路线压缩成可直接照着录的分段讲稿。",
          total_minutes: 7,
          next_action: "录屏前准备截图或历史产物。",
          segments: [
            {
              minute: "0:00-0:45",
              screen: "打开学习画像和导学入口",
              narration: "先说明学习者目标，再展示当前任务和讯飞工具链讲法。",
              backup: "使用稳定 Demo 画像。",
            },
          ],
        },
        ai_coding_statement: {
          title: "AI Coding 工具说明",
          summary: "开发过程中使用 AI 编程助手辅助调研、重构、实现、测试和文档整理；最终提交由项目维护者复核。",
          course_name: "深度学习",
          usage_scope: ["辅助实现导学、画像、资源生成和测试。"],
          human_review: ["人工阅读 diff 并运行测试。"],
          privacy_boundary: ["真实密钥不写入仓库。"],
          evidence: ["GitHub 提交历史。"],
          next_action: "在演示 PPT 末页说明 AI Coding 参与范围。",
        },
        learning_report: {
          overall_score: 72,
          readiness: "recording_ready",
          progress: 55,
          behavior_summary: { resource_count: 1, quiz_attempt_count: 0 },
          behavior_tags: ["profile", "feedback"],
          demo_readiness: { score: 80, label: "Ready for recording" },
        },
      },
    }),
  );
  await page.route("**/api/v1/guide/v2/sessions/guide-demo/tasks/D5/resources/jobs", async (route) => {
    state.resourcePayload = route.request().postDataJSON() as typeof state.resourcePayload;
    await route.fulfill({
      json: { task_id: "job-visual", session_id: "guide-demo", learning_task_id: "D5", resource_type: state.resourcePayload?.resource_type },
    });
  });
  await page.route("**/api/v1/guide/v2/sessions/guide-demo/tasks/D5/artifacts/artifact-quiz/quiz-results", async (route) => {
    state.quizPayload = route.request().postDataJSON() as typeof state.quizPayload;
    const answers = state.quizPayload?.answers ?? [];
    const scoreValue = answers.length ? answers.filter((answer) => answer.is_correct).length / answers.length : 0;
    await route.fulfill({
      json: {
        success: true,
        session: sessionForRoute(),
        attempt: { score: scoreValue, answer_count: answers.length },
        evidence: { evidence_id: "ev-quiz", task_id: "D5", score: scoreValue },
        learning_feedback: {
          title: "练习已回写",
          summary: "系统已把答题结果写回学习画像和导学路线。",
          tone: "brand",
          score_percent: Math.round(scoreValue * 100),
          task_id: "D5",
          task_title: "CNN 图像检索流程",
          next_task_title: "Review weak answers or continue.",
          resource_actions: [],
        },
        question_notebook: { saved: true, count: answers.length, session_id: "guide_v2_guide-demo" },
        learner_evidence: { appended: answers.length + 1 },
      },
    });
  });
  await page.route("**/api/v1/guide/v2/sessions/guide-demo/tasks/D5/complete", async (route) => {
    state.completePayload = route.request().postDataJSON() as typeof state.completePayload;
    await route.fulfill({
      json: {
        success: true,
        session: completedSession,
        completed_task: { ...task, status: "completed" },
        evidence: { evidence_id: "ev-demo", task_id: "D5", score: state.completePayload?.score },
        next_task: null,
        learning_feedback: {
          title: "Feedback recorded",
          summary: "The reflection has been written back to the learner profile.",
          tone: "brand",
          score_percent: Math.round(Number(state.completePayload?.score ?? 0) * 100),
          task_id: "D5",
          task_title: "CNN 图像检索流程",
          next_task_title: "Open the route and course package",
          resource_actions: [],
        },
      },
    });
  });

  return state;
}

async function mockGuideV2ExternalDemoApis(page: Page) {
  const state: { resourcePayload?: { resource_type?: string; prompt?: string } } = {};

  const profile = {
    version: 1,
    generated_at: "2026-05-01T00:00:00.000Z",
    confidence: 0.78,
    overview: {
      current_focus: "Understand CNN image retrieval",
      preferred_time_budget_minutes: 45,
      summary: "External course learner needs a compact visual route.",
    },
    stable_profile: {
      goals: ["Build deep learning intuition"],
      preferences: ["visual", "practice"],
      strengths: ["Can follow model diagrams"],
      constraints: ["Short study window"],
    },
    learning_state: {
      weak_points: [{ label: "CNN feature extraction", confidence: 0.72, evidence_count: 2 }],
      mastery: [],
    },
    recommendations: ["Use one compact CNN retrieval diagram."],
    sources: [],
    evidence_preview: [],
    data_quality: { source_count: 2, evidence_count: 3 },
  };

  const task = {
    task_id: "D5",
    node_id: "DL5",
    type: "resource",
    title: "CNN image retrieval pipeline",
    instruction: "Study one compact diagram, then explain feature extraction and similarity ranking in your own words.",
    status: "pending",
    estimated_minutes: 12,
    success_criteria: ["Explain CNN feature extraction.", "Connect similarity ranking with retrieval results."],
    artifact_refs: [],
    metadata: {},
  };

  const demoSeed = {
    title: "Deep learning external template demo",
    task_chain: ["D5"],
    resource_prompts: {
      D5: "Create a visual explanation of CNN image retrieval with feature extraction, similarity scoring and ranking.",
    },
    sample_reflection: {
      score: 0.74,
      reflection: "I can follow the image retrieval pipeline, but I still confuse feature extraction and classification.",
    },
  };

  const session = {
    session_id: "deep-demo",
    goal: "Learn CNN image retrieval",
    status: "learning",
    created_at: 1_700_000_000,
    updated_at: 1_700_000_100,
    profile: {
      preferences: ["visual", "practice"],
      weak_points: ["CNN feature extraction"],
      source_context_summary: "Unified learner profile included.",
    },
    course_map: {
      title: "Deep Learning",
      nodes: [
        { node_id: "DL3", title: "Convolutional Neural Networks", description: "Understand convolution and pooling.", status: "completed" },
        { node_id: "DL5", title: "CNN Image Retrieval", description: "Understand feature retrieval workflow.", status: "learning" },
      ],
      edges: [{ source: "DL3", target: "DL5" }],
      metadata: {
        course_id: "DL301",
        course_name: "Deep Learning",
        source_action: { source: "demo_seed" },
        created_from: "demo_seed",
        demo_seed: demoSeed,
      },
    },
    tasks: [task],
    current_task: task,
    evidence: [],
    mastery: { DL5: { score: 0.5, status: "developing" } },
    recommendations: ["Generate one CNN retrieval diagram."],
    plan_events: [],
    progress: 30,
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
  await page.route("**/api/v1/notebook/list", (route) => route.fulfill({ json: { notebooks: [], total: 0 } }));
  await page.route("**/api/v1/learner-profile", (route) => route.fulfill({ json: profile }));
  await page.route("**/api/v1/learner-profile/refresh", (route) => route.fulfill({ json: profile }));
  await page.route("**/api/v1/guide/v2/templates", (route) =>
    route.fulfill({
      json: {
        templates: [
          {
            id: "deep_learning_foundations",
            title: "Deep Learning Foundations",
            course_id: "DL301",
            course_name: "Deep Learning",
            level: "intermediate",
            suggested_weeks: 14,
            default_goal: "Build deep learning intuition from CNNs to Transformers.",
            default_preferences: ["visual", "practice"],
            default_time_budget_minutes: 45,
            demo_seed: demoSeed,
          },
        ],
      },
    }),
  );
  await page.route(/\/api\/v1\/guide\/v2\/sessions(?:\?.*)?$/, (route) =>
    route.fulfill({
      json: {
        sessions: [{ session_id: "deep-demo", goal: "Learn CNN image retrieval", status: "learning", updated_at: 1_700_000_100, progress: 30 }],
      },
    }),
  );
  await page.route(/\/api\/v1\/guide\/v2\/sessions\/deep-demo$/, (route) => route.fulfill({ json: session }));
  await page.route("**/api/v1/guide/v2/sessions/deep-demo/study-plan", (route) =>
    route.fulfill({
      json: {
        success: true,
        session_id: "deep-demo",
        summary: "Follow one focused deep learning task.",
        blocks: [{ id: "B1", title: "CNN retrieval intuition", status: "learning", task_ids: ["D5"], tasks: [task] }],
        checkpoints: [],
      },
    }),
  );
  await page.route("**/api/v1/guide/v2/sessions/deep-demo/diagnostic", (route) =>
    route.fulfill({ json: { success: true, session_id: "deep-demo", status: "completed", summary: "Already calibrated.", questions: [] } }),
  );
  await page.route("**/api/v1/guide/v2/sessions/deep-demo/report", (route) =>
    route.fulfill({
      json: {
        success: true,
        session_id: "deep-demo",
        title: "Deep learning report",
        summary: "The learner is ready for a focused CNN retrieval diagram.",
        overview: { overall_score: 68, progress: 30, completed_tasks: 0, total_tasks: 1 },
        node_cards: [],
        feedback_digest: { count: 0 },
        action_brief: {
          title: "Generate the current diagram",
          summary: "Use the stable prompt from the external template.",
          primary_action: { kind: "resource", label: "Generate diagram", target_task_id: "D5", resource_type: "visual", prompt: demoSeed.resource_prompts.D5 },
          secondary_actions: [],
          signals: [],
        },
      },
    }),
  );
  await page.route("**/api/v1/guide/v2/sessions/deep-demo/course-package", (route) =>
    route.fulfill({
      json: {
        success: true,
        session_id: "deep-demo",
        title: "Deep learning package",
        summary: "External template package.",
        course_metadata: { course_id: "DL301", course_name: "Deep Learning" },
        portfolio: [],
        review_plan: [],
        demo_seed_pack: demoSeed,
      },
    }),
  );
  await page.route("**/api/v1/guide/v2/sessions/deep-demo/tasks/D5/resources/jobs", async (route) => {
    state.resourcePayload = route.request().postDataJSON() as typeof state.resourcePayload;
    await route.fulfill({
      json: { task_id: "job-visual", session_id: "deep-demo", learning_task_id: "D5", resource_type: state.resourcePayload?.resource_type },
    });
  });

  return state;
}
