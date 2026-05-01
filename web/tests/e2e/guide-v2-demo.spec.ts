import { expect, test, type Page } from "@playwright/test";

test("guide start page exposes full course templates", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "course template picker runs once");

  await installMockGuideV2ResourceEventSource(page);
  await mockGuideV2StableDemoApis(page);

  await page.goto("/guide");
  await expect(page.getByTestId("guide-course-template-robotics_ros_foundations")).toBeVisible();
  await page.getByTestId("guide-course-template-robotics_ros_foundations").click();

  await expect(page.getByTestId("guide-goal-input")).toHaveValue(/ROS|机器人|robot/i);
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
  await expect(page.getByTestId("guide-demo-recording-checklist")).toBeVisible();
  await expect(page.getByTestId("guide-demo-recording-checklist")).toContainText("7 分钟演示路线");
  await expect(page.getByTestId("guide-demo-recording-checklist")).toContainText("录屏前先打开导学路线。");
  await expect(page.getByTestId("guide-demo-recording-checklist")).not.toContainText("7-minute demo route");
  expect(consoleDomErrors).toEqual([]);
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
