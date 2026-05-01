import { expect, test, type Page } from "@playwright/test";

test("guide start page exposes full course templates", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "course template picker runs once");

  await installMockGuideV2ResourceEventSource(page);
  await mockGuideV2StableDemoApis(page);

  await page.goto("/guide");
  await expect(page.getByTestId("guide-course-template-robotics_ros_foundations")).toBeVisible();
  await expect(page.getByTestId("guide-course-template-higher_math_limits_derivatives")).toBeVisible();
  await page.getByTestId("guide-course-template-robotics_ros_foundations").click();

  await expect(page.getByTestId("guide-goal-input")).toHaveValue(/ROS|机器人|robot/i);

  await page.getByTestId("guide-course-template-higher_math_limits_derivatives").click();
  await expect(page.getByTestId("guide-goal-input")).toHaveValue(/极限|导数|高等数学/i);
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
  await expect.poll(() => guide.resourcePayload?.prompt).toContain("gradient descent");
  await expect(page.getByTestId("guide-artifact-agent-route")).toContainText("智能体接力");
  await expect(page.getByTestId("guide-artifact-agent-route")).toContainText("画像");
  await expect(page.getByTestId("guide-artifact-agent-route")).toContainText("图解");

  await page.getByTestId("guide-open-complete-task").click();
  await page.getByTestId("guide-demo-apply-feedback").click();
  await page.getByTestId("guide-submit-task-feedback").click();

  await expect.poll(() => guide.completePayload?.score ?? -1).toBeCloseTo(0.7, 2);
  await expect(page.getByTestId("guide-demo-recording-cue")).toContainText("看产出包");
  await expect(page.getByTestId("guide-demo-wrap-up")).toBeVisible();

  await page.getByTestId("guide-demo-open-course-package").click();
  await expect(page.getByTestId("guide-course-package-panel")).toBeVisible();
  await expect(page.getByTestId("guide-course-package-panel")).toContainText("稳定演示产出包");
  await expect(page.getByTestId("guide-course-package-panel")).not.toContainText("Stable demo course package");
  await expect(page.getByTestId("guide-demo-preflight-card")).toBeVisible();
  await expect(page.getByTestId("guide-demo-preflight-card")).toContainText("赛前一键检查");
  await expect(page.getByTestId("guide-demo-preflight-card")).toContainText("先补");
  await expect(page.getByTestId("guide-demo-recording-checklist")).toBeVisible();
  await expect(page.getByTestId("guide-demo-recording-checklist")).toContainText("7 分钟演示路线");
  await expect(page.getByTestId("guide-demo-recording-checklist")).toContainText("录屏前先打开导学路线。");
  await expect(page.getByTestId("guide-demo-recording-checklist")).not.toContainText("7-minute demo route");
  await expect(page.getByTestId("guide-recording-script-cue")).toContainText("讲稿");
  await expect(page.getByTestId("guide-presentation-outline-card")).toBeVisible();
  await expect(page.getByTestId("guide-presentation-outline-card")).toContainText("演示 PPT 骨架");
  await expect(page.getByTestId("guide-presentation-outline-card")).toContainText("项目价值");
  await expect(page.getByTestId("guide-competition-alignment-card")).toBeVisible();
  await expect(page.getByTestId("guide-competition-alignment-card")).toContainText("赛题五项对齐");
  await expect(page.getByTestId("guide-competition-alignment-card")).toContainText("多智能体协同");
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

  await expect(page.getByText("系统建议先做这个")).toBeVisible();
  await expect(page.getByTestId("guide-open-resource-choice")).toContainText("换一种材料");
  await expect(page.getByTestId("guide-resource-choice-quiz")).toHaveCount(0);

  await page.getByTestId("guide-open-resource-choice").click();
  await expect(page.getByText("选择一种学习材料")).toBeVisible();
  await expect(page.getByTestId("guide-resource-choice-visual")).toContainText("推荐");
  await expect(page.getByTestId("guide-resource-choice-quiz")).toContainText("练习");

  await page.getByTestId("guide-resource-choice-quiz").click();
  await expect.poll(() => guide.resourcePayload?.resource_type).toBe("quiz");
  await expect(page.getByText("系统建议先做这个")).toBeVisible();
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
  await expect(page.getByText("系统建议先做这个")).toBeVisible();
  await expect(page.getByTestId("guide-resource-choice-quiz")).toHaveCount(0);

  await page.getByTestId("guide-open-resource-choice").click();
  await expect(page.getByText("选择一种学习材料")).toBeVisible();
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
      source_action?: { source?: string };
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
      current_focus: "Understand gradient descent intuitively",
      preferred_time_budget_minutes: 45,
      summary: "Demo learner is ready for a guided machine learning route.",
    },
    stable_profile: {
      goals: ["Build a visible ML learning loop"],
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
    title: "Stable ML foundations demo",
    scenario: "A beginner learner moves from profile to resource and feedback.",
    persona: {
      name: "Demo learner",
      level: "beginner",
      goal: "Understand gradient descent",
      weak_points: ["Concept boundaries", "Formula intuition"],
      preferences: ["visual", "practice"],
    },
    task_chain: [
      {
        task_id: "T4",
        title: "Gradient descent intuition",
        stage: "T4 visual",
        show: "Generate a compact visual explanation.",
        resource_type: "visual",
        prompt: "Create a visual explanation for gradient descent intuition.",
        sample_score: 0.7,
        sample_reflection: "I understand gradient descent as moving downhill step by step, but I still need practice choosing the step size.",
      },
      {
        task_id: "T6",
        title: "Model evaluation practice",
        stage: "T6 practice",
        show: "Use a short quiz to validate understanding.",
        resource_type: "quiz",
        prompt: "Create a short quiz about model evaluation.",
        sample_score: 0.85,
        sample_reflection: "I can distinguish accuracy and overfitting with examples.",
      },
    ],
    resource_prompts: [
      {
        type: "visual",
        title: "Gradient descent visual",
        prompt: "Create a visual explanation for gradient descent intuition.",
      },
    ],
    rehearsal_notes: ["Keep the route short and show the feedback loop."],
    report_anchor: { score: 72, readiness: "demo_ready", action: "Open route and course package." },
  };

  const task = {
    task_id: "T4",
    node_id: "N2",
    type: "resource",
    title: "Gradient descent intuition",
    instruction: "Use a visual explanation, then submit a short reflection.",
    status: "pending",
    estimated_minutes: 10,
    success_criteria: ["Explain gradient descent as iterative improvement.", "Name one remaining uncertainty."],
    artifact_refs: [],
    metadata: {},
  };

  const visualArtifact = {
    id: "artifact-visual",
    type: "visual",
    capability: "visualize",
    title: "Gradient descent visual",
    created_at: 1_700_000_120,
    result: {
      response: "Use the slope as a direction hint, then move step by step toward a lower loss.",
      render_type: "mermaid",
      code: {
        content: "graph LR\nA[Current point] --> B[Compute slope]\nB --> C[Take one step]\nC --> D[Lower loss]",
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
    title: "Gradient descent quick check",
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
          question: "What does gradient descent use to decide the next direction?",
          options: {
            A: "A random label",
            B: "The gradient of the loss",
            C: "The largest feature value",
            D: "The test accuracy",
          },
          correct_answer: "B",
          explanation: "The gradient gives the local direction for reducing the loss.",
          concepts: ["gradient_descent"],
        },
        {
          question_id: "q2",
          question_type: "true_false",
          question: "A smaller learning rate can make each update more cautious.",
          correct_answer: "True",
          explanation: "A smaller step usually changes parameters more conservatively.",
          concepts: ["learning_rate"],
        },
      ],
    },
  };

  const externalVideoArtifact = {
    id: "artifact-external-video",
    type: "external_video",
    capability: "external_video_search",
    title: "Gradient descent public videos",
    created_at: 1_700_000_140,
    result: {
      response: "Pick one short public video, then return to the task.",
      videos: [
        {
          title: "Gradient descent intuition",
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
    goal: "Stable demo route",
    status: "learning",
    created_at: 1_700_000_000,
    updated_at: 1_700_000_100,
    profile: {
      preferences: ["visual", "practice"],
      weak_points: ["Concept boundaries"],
      source_context_summary: "Unified learner profile included.",
    },
    course_map: {
      title: "Machine Learning Foundations",
      nodes: [
        { node_id: "N1", title: "ML overview", description: "Frame the course.", status: "completed" },
        { node_id: "N2", title: "Optimization", description: "Understand gradient descent.", status: "learning" },
      ],
      edges: [{ source: "N1", target: "N2" }],
      metadata: {
        course_id: "ML101",
        course_name: "Machine Learning Foundations",
        suggested_weeks: 1,
        credits: 1,
        source_action: { source: "demo_seed" },
        created_from: "demo_seed",
        demo_seed: demoSeed,
      },
    },
    tasks: [task],
    current_task: task,
    evidence: [],
    mastery: { N2: { score: 0.48, status: "developing" } },
    recommendations: ["Generate one visual resource."],
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
            id: "ml_foundations",
            title: "Machine Learning Foundations",
            course_id: "ML101",
            course_name: "Machine Learning Foundations",
            level: "beginner",
            suggested_weeks: 1,
            default_goal: "Understand ML foundations.",
            default_preferences: ["visual", "practice"],
            default_time_budget_minutes: 45,
            demo_seed: demoSeed,
          },
          {
            id: "robotics_ros_foundations",
            title: "智能机器人与 ROS 基础",
            course_id: "ROBOT101",
            course_name: "智能机器人与 ROS 基础",
            description: "从机器人系统组成、ROS 通信到小项目实践，适合做一门可演示的完整课程。",
            level: "beginner",
            suggested_weeks: 4,
            credits: 2,
            estimated_minutes: 720,
            default_goal: "系统学习智能机器人与 ROS 基础，完成话题通信、服务调用和导航入门实践。",
            default_preferences: ["visual", "practice", "project"],
            default_time_budget_minutes: 60,
            tags: ["机器人", "ROS", "项目实践"],
          },
          {
            id: "higher_math_limits_derivatives",
            title: "高等数学极限与导数",
            course_id: "MATH101",
            course_name: "高等数学极限与导数",
            description: "从函数直觉、极限定义到导数几何意义，适合展示公式、图解和 Manim 动画。",
            level: "beginner",
            suggested_weeks: 6,
            credits: 2,
            estimated_minutes: 420,
            default_goal: "系统学习高等数学中的极限、连续和导数，并能用图像直觉解释典型题。",
            default_preferences: ["visual", "practice", "video"],
            default_time_budget_minutes: 40,
            tags: ["高等数学", "极限", "导数"],
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
          ? [{ session_id: "guide-demo", goal: "Stable demo route", status: "learning", updated_at: 1_700_000_100, progress: 35 }]
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
        blocks: [{ id: "B1", title: "Demo block", status: "learning", task_ids: ["T4"], tasks: [task] }],
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
        node_cards: [{ node_id: "N2", title: "Optimization", mastery_score: 62, suggestion: "Do one short retest." }],
        feedback_digest: { count: state.completePayload ? 1 : 0, latest: { title: "Feedback recorded", summary: "Profile updated." } },
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
        title: "Stable demo course package",
        summary: "Stable demo course package for a 7-minute recording.",
        course_metadata: { course_id: "ML101", course_name: "Machine Learning Foundations" },
        capstone_project: {
          title: "Explain gradient descent",
          scenario: "Build one visual resource and one feedback loop.",
          deliverables: ["Route", "Visual", "Feedback"],
          steps: ["Create route", "Generate visual", "Submit feedback"],
          estimated_minutes: 45,
        },
        rubric: [{ criterion: "Closed loop", weight: 60, baseline: "Shows profile to feedback." }],
        portfolio: [],
        review_plan: [{ node_id: "N2", title: "Optimization", priority: "high", action: "Retest gradient descent." }],
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
          assets: [{ type: "visual", title: "Gradient descent visual", status: "ready", show: "Use saved visual." }],
          checklist: ["Open guide route before recording."],
        },
        demo_seed_pack: demoSeed,
        demo_preflight: {
          title: "赛前一键检查",
          summary: "围绕机器学习基础检查录屏、答辩和提交材料是否成链。",
          status: "needs_attention",
          score: 75,
          ready_count: 5,
          seed_count: 2,
          total_count: 8,
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
          ],
        },
        presentation_outline: {
          title: "演示 PPT 骨架",
          summary: "按赛题评分点生成 7 页答辩大纲。",
          course_name: "Machine Learning Foundations",
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
              title: "多智能体协同资源",
              purpose: "说明智能体接力。",
              evidence: "画像、图解、出题和评估智能体协同。",
              speaker_note: "展示资源卡片。",
            },
          ],
        },
        competition_submission: {
          title: "比赛提交清单",
          summary: "按赛题提交物检查当前课程产出。",
          course_name: "Machine Learning Foundations",
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
              item: "完整高校课程样例",
              status: "ready",
              evidence: "课程模板包含目标、任务和评价方式。",
              action: "随项目一并提交课程数据。",
            },
          ],
        },
        competition_alignment: {
          title: "赛题五项对齐",
          summary: "围绕机器学习课程把画像、路径、资源、辅导和评估映射成可录屏证据。",
          course_name: "Machine Learning Foundations",
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
              narration: "先说明学习者目标，再展示当前任务。",
              backup: "使用稳定 Demo 画像。",
            },
          ],
        },
        ai_coding_statement: {
          title: "AI Coding 工具说明",
          summary: "开发过程中使用 AI 编程助手辅助调研、重构、实现、测试和文档整理；最终提交由项目维护者复核。",
          course_name: "Machine Learning Foundations",
          usage_scope: ["辅助实现导学、画像、资源生成和测试。"],
          human_review: ["人工阅读 diff 并运行测试。"],
          privacy_boundary: ["真实密钥不写入仓库。"],
          evidence: ["GitHub 提交历史。"],
          next_action: "提交材料中附上 docs/ai-coding-statement.md。",
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
  await page.route("**/api/v1/guide/v2/sessions/guide-demo/tasks/T4/resources/jobs", async (route) => {
    state.resourcePayload = route.request().postDataJSON() as typeof state.resourcePayload;
    await route.fulfill({
      json: { task_id: "job-visual", session_id: "guide-demo", learning_task_id: "T4", resource_type: state.resourcePayload?.resource_type },
    });
  });
  await page.route("**/api/v1/guide/v2/sessions/guide-demo/tasks/T4/artifacts/artifact-quiz/quiz-results", async (route) => {
    state.quizPayload = route.request().postDataJSON() as typeof state.quizPayload;
    const answers = state.quizPayload?.answers ?? [];
    const scoreValue = answers.length ? answers.filter((answer) => answer.is_correct).length / answers.length : 0;
    await route.fulfill({
      json: {
        success: true,
        session: sessionForRoute(),
        attempt: { score: scoreValue, answer_count: answers.length },
        evidence: { evidence_id: "ev-quiz", task_id: "T4", score: scoreValue },
        learning_feedback: {
          title: "练习已回写",
          summary: "系统已把答题结果写回学习画像和导学路线。",
          tone: "brand",
          score_percent: Math.round(scoreValue * 100),
          task_id: "T4",
          task_title: "Gradient descent intuition",
          next_task_title: "Review weak answers or continue.",
          resource_actions: [],
        },
        question_notebook: { saved: true, count: answers.length, session_id: "guide_v2_guide-demo" },
        learner_evidence: { appended: answers.length + 1 },
      },
    });
  });
  await page.route("**/api/v1/guide/v2/sessions/guide-demo/tasks/T4/complete", async (route) => {
    state.completePayload = route.request().postDataJSON() as typeof state.completePayload;
    await route.fulfill({
      json: {
        success: true,
        session: completedSession,
        completed_task: { ...task, status: "completed" },
        evidence: { evidence_id: "ev-demo", task_id: "T4", score: state.completePayload?.score },
        next_task: null,
        learning_feedback: {
          title: "Feedback recorded",
          summary: "The reflection has been written back to the learner profile.",
          tone: "brand",
          score_percent: Math.round(Number(state.completePayload?.score ?? 0) * 100),
          task_id: "T4",
          task_title: "Gradient descent intuition",
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
      current_focus: "Understand derivative intuition",
      preferred_time_budget_minutes: 30,
      summary: "External course learner needs a short visual route.",
    },
    stable_profile: {
      goals: ["Build calculus intuition"],
      preferences: ["visual", "video"],
      strengths: ["Can read graphs"],
      constraints: ["Short study window"],
    },
    learning_state: {
      weak_points: [{ label: "Formula intuition", confidence: 0.72, evidence_count: 2 }],
      mastery: [],
    },
    recommendations: ["Use a compact Manim explanation."],
    sources: [],
    evidence_preview: [],
    data_quality: { source_count: 2, evidence_count: 3 },
  };

  const task = {
    task_id: "M4",
    node_id: "M2",
    type: "resource",
    title: "Derivative as instantaneous rate",
    instruction: "Watch one compact animation, then explain the tangent slope in your own words.",
    status: "pending",
    estimated_minutes: 10,
    success_criteria: ["Explain derivative as a tangent slope.", "Connect rate of change with a graph."],
    artifact_refs: [],
    metadata: {},
  };

  const demoSeed = {
    title: "Calculus external template demo",
    task_chain: ["M4"],
    resource_prompts: {
      M4: "Create a Manim animation explaining derivatives as tangent slope and instantaneous rate of change.",
    },
    sample_reflection: {
      score: 0.74,
      reflection: "I can see derivative as a tangent slope, but I still confuse average and instantaneous rate.",
    },
  };

  const session = {
    session_id: "math-demo",
    goal: "Learn derivative intuition",
    status: "learning",
    created_at: 1_700_000_000,
    updated_at: 1_700_000_100,
    profile: {
      preferences: ["visual", "video"],
      weak_points: ["Formula intuition"],
      source_context_summary: "Unified learner profile included.",
    },
    course_map: {
      title: "Higher Math Limits and Derivatives",
      nodes: [
        { node_id: "M1", title: "Limits", description: "Build limit intuition.", status: "completed" },
        { node_id: "M2", title: "Derivatives", description: "Understand tangent slope.", status: "learning" },
      ],
      edges: [{ source: "M1", target: "M2" }],
      metadata: {
        course_id: "MATH101",
        course_name: "Higher Math Limits and Derivatives",
        source_action: { source: "demo_seed" },
        created_from: "demo_seed",
        demo_seed: demoSeed,
      },
    },
    tasks: [task],
    current_task: task,
    evidence: [],
    mastery: { M2: { score: 0.5, status: "developing" } },
    recommendations: ["Generate one short animation."],
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
            id: "higher_math_limits_derivatives",
            title: "Higher Math Limits and Derivatives",
            course_id: "MATH101",
            course_name: "Higher Math Limits and Derivatives",
            level: "beginner",
            suggested_weeks: 6,
            default_goal: "Build calculus intuition.",
            default_preferences: ["visual", "video"],
            default_time_budget_minutes: 30,
            demo_seed: demoSeed,
          },
        ],
      },
    }),
  );
  await page.route(/\/api\/v1\/guide\/v2\/sessions(?:\?.*)?$/, (route) =>
    route.fulfill({
      json: {
        sessions: [{ session_id: "math-demo", goal: "Learn derivative intuition", status: "learning", updated_at: 1_700_000_100, progress: 30 }],
      },
    }),
  );
  await page.route(/\/api\/v1\/guide\/v2\/sessions\/math-demo$/, (route) => route.fulfill({ json: session }));
  await page.route("**/api/v1/guide/v2/sessions/math-demo/study-plan", (route) =>
    route.fulfill({
      json: {
        success: true,
        session_id: "math-demo",
        summary: "Follow one focused calculus task.",
        blocks: [{ id: "B1", title: "Derivative intuition", status: "learning", task_ids: ["M4"], tasks: [task] }],
        checkpoints: [],
      },
    }),
  );
  await page.route("**/api/v1/guide/v2/sessions/math-demo/diagnostic", (route) =>
    route.fulfill({ json: { success: true, session_id: "math-demo", status: "completed", summary: "Already calibrated.", questions: [] } }),
  );
  await page.route("**/api/v1/guide/v2/sessions/math-demo/report", (route) =>
    route.fulfill({
      json: {
        success: true,
        session_id: "math-demo",
        title: "Calculus learning report",
        summary: "The learner is ready for a focused animation.",
        overview: { overall_score: 68, progress: 30, completed_tasks: 0, total_tasks: 1 },
        node_cards: [],
        feedback_digest: { count: 0 },
        action_brief: {
          title: "Generate the current animation",
          summary: "Use the stable prompt from the external template.",
          primary_action: { kind: "resource", label: "Generate video", target_task_id: "M4", resource_type: "video", prompt: demoSeed.resource_prompts.M4 },
          secondary_actions: [],
          signals: [],
        },
      },
    }),
  );
  await page.route("**/api/v1/guide/v2/sessions/math-demo/course-package", (route) =>
    route.fulfill({
      json: {
        success: true,
        session_id: "math-demo",
        title: "Calculus package",
        summary: "External template package.",
        course_metadata: { course_id: "MATH101", course_name: "Higher Math Limits and Derivatives" },
        portfolio: [],
        review_plan: [],
        demo_seed_pack: demoSeed,
      },
    }),
  );
  await page.route("**/api/v1/guide/v2/sessions/math-demo/tasks/M4/resources/jobs", async (route) => {
    state.resourcePayload = route.request().postDataJSON() as typeof state.resourcePayload;
    await route.fulfill({
      json: { task_id: "job-video", session_id: "math-demo", learning_task_id: "M4", resource_type: state.resourcePayload?.resource_type },
    });
  });

  return state;
}
