import {
  createRootRoute,
  createRoute,
  createRouter,
  redirect,
} from "@tanstack/react-router";

import { RootLayout } from "@/components/layout/RootLayout";
import {
  AgentsRoute,
  ChatRoute,
  CoWriterRoute,
  GuideRoute,
  KnowledgeRoute,
  MemoryRoute,
  NotebookRoute,
  PlaygroundRoute,
  QuestionLabRoute,
  SettingsRoute,
  VisionRoute,
} from "@/routerPages";

const rootRoute = createRootRoute({
  component: RootLayout,
});

function searchValue(search: unknown, key: string) {
  if (typeof search === "string") {
    return new URLSearchParams(search.startsWith("?") ? search : `?${search}`).get(key) ?? "";
  }
  if (!search || typeof search !== "object" || !(key in search)) return "";
  const value = (search as Record<string, unknown>)[key];
  return value == null ? "" : String(value);
}

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  beforeLoad: ({ location }) => {
    const sessionId = searchValue(location.search, "session");
    if (sessionId) {
      throw redirect({ to: "/chat/$sessionId", params: { sessionId } });
    }
    throw redirect({ to: "/chat" });
  },
});

const chatRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/chat",
  component: ChatRoute,
});

const chatSessionRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/chat/$sessionId",
  component: ChatRoute,
});

const historyRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/history",
  beforeLoad: () => {
    throw redirect({ to: "/chat" });
  },
});

const questionRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/question",
  component: QuestionLabRoute,
});

const solverRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/solver",
  beforeLoad: () => {
    throw redirect({ to: "/chat", search: { capability: "deep_solve" } });
  },
});

const researchRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/research",
  beforeLoad: () => {
    throw redirect({ to: "/chat", search: { capability: "deep_research" } });
  },
});

const visualizeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/visualize",
  beforeLoad: () => {
    throw redirect({ to: "/chat", search: { capability: "visualize" } });
  },
});

const visionRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/vision",
  component: VisionRoute,
});

const visionSolverRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/vision-solver",
  beforeLoad: () => {
    throw redirect({ to: "/vision" });
  },
});

const geogebraRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/geogebra",
  beforeLoad: () => {
    throw redirect({ to: "/vision" });
  },
});

const mathAnimatorRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/math_animator",
  beforeLoad: () => {
    throw redirect({ to: "/chat", search: { capability: "math_animator" } });
  },
});

const mathAnimatorHyphenRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/math-animator",
  beforeLoad: () => {
    throw redirect({ to: "/chat", search: { capability: "math_animator" } });
  },
});

const legacyCoWriterRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/co_writer",
  beforeLoad: () => {
    throw redirect({ to: "/co-writer" });
  },
});

const compactCoWriterRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/cowriter",
  beforeLoad: () => {
    throw redirect({ to: "/co-writer" });
  },
});

const knowledgeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/knowledge",
  beforeLoad: ({ location }) => {
    const tab = searchValue(location.search, "tab");
    if (tab === "notebooks" || tab === "questions") {
      throw redirect({ to: "/notebook", search: { tab } });
    }
  },
  component: KnowledgeRoute,
});

const notebookRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/notebook",
  component: NotebookRoute,
});

const memoryRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/memory",
  component: MemoryRoute,
});

const playgroundRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/playground",
  component: PlaygroundRoute,
});

const guideRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/guide",
  component: GuideRoute,
});

const coWriterRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/co-writer",
  component: CoWriterRoute,
});

const agentsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/agents",
  component: AgentsRoute,
});

const agentChatRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/agents/$botId/chat",
  component: AgentsRoute,
});

const legacySparkBotRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/sparkbot",
  beforeLoad: () => {
    throw redirect({ to: "/agents" });
  },
});

const legacySparkBotChatRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/sparkbot/$botId/chat",
  beforeLoad: ({ params }) => {
    throw redirect({
      to: "/agents/$botId/chat",
      params: { botId: params.botId },
    });
  },
});

const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings",
  component: SettingsRoute,
});

const utilityKnowledgeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/utility/knowledge",
  beforeLoad: () => {
    throw redirect({ to: "/knowledge" });
  },
});

const utilityMemoryRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/utility/memory",
  beforeLoad: () => {
    throw redirect({ to: "/memory" });
  },
});

const utilityNotebookRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/utility/notebook",
  beforeLoad: () => {
    throw redirect({ to: "/notebook" });
  },
});

const utilitySettingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/utility/settings",
  beforeLoad: () => {
    throw redirect({ to: "/settings" });
  },
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  chatRoute,
  chatSessionRoute,
  historyRoute,
  questionRoute,
  solverRoute,
  researchRoute,
  visualizeRoute,
  visionRoute,
  visionSolverRoute,
  geogebraRoute,
  mathAnimatorRoute,
  mathAnimatorHyphenRoute,
  legacyCoWriterRoute,
  compactCoWriterRoute,
  knowledgeRoute,
  notebookRoute,
  memoryRoute,
  playgroundRoute,
  guideRoute,
  coWriterRoute,
  agentsRoute,
  agentChatRoute,
  legacySparkBotRoute,
  legacySparkBotChatRoute,
  settingsRoute,
  utilityKnowledgeRoute,
  utilityMemoryRoute,
  utilityNotebookRoute,
  utilitySettingsRoute,
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

