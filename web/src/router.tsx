import {
  createRootRoute,
  createRoute,
  createRouter,
  redirect,
  type RouteComponent,
} from "@tanstack/react-router";

import { RootLayout } from "@/components/layout/RootLayout";
import { isKnowledgeWorkspaceId } from "@/lib/ragHandoff";
import { REDIRECT_TARGETS, ROUTE_VIEWS, type RedirectTarget } from "@/routeConfig";
import { KnowledgeRoute } from "@/routerPages";

type RedirectOptions = Parameters<typeof redirect>[0];

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

function pageRoute<const TPath extends string>(path: TPath, component: RouteComponent) {
  return createRoute({
    getParentRoute: () => rootRoute,
    path,
    component,
  });
}

function redirectRoute<const TPath extends string>(path: TPath, target: RedirectTarget) {
  return createRoute({
    getParentRoute: () => rootRoute,
    path,
    beforeLoad: () => {
      throw redirect({ to: target.to, search: target.search } as RedirectOptions);
    },
  });
}

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  beforeLoad: ({ location }) => {
    const sessionId = searchValue(location.search, "session");
    if (sessionId) {
      throw redirect({ to: "/chat/$sessionId", params: { sessionId } });
    }
    throw redirect({ to: "/guide" });
  },
});

const chatRoute = pageRoute("/chat", ROUTE_VIEWS.chat);
const chatSessionRoute = pageRoute("/chat/$sessionId", ROUTE_VIEWS.chat);
const questionRoute = pageRoute("/question", ROUTE_VIEWS.question);
const visionRoute = pageRoute("/vision", ROUTE_VIEWS.vision);
const notebookRoute = pageRoute("/notebook", ROUTE_VIEWS.notebook);
const memoryRoute = pageRoute("/memory", ROUTE_VIEWS.memory);
const memoryEvidenceRoute = pageRoute("/memory/evidence", ROUTE_VIEWS.memory);
const memoryEditRoute = pageRoute("/memory/edit", ROUTE_VIEWS.memory);
const playgroundRoute = pageRoute("/playground", ROUTE_VIEWS.playground);
const guideRoute = pageRoute("/guide", ROUTE_VIEWS.guide);
const coWriterRoute = pageRoute("/co-writer", ROUTE_VIEWS.coWriter);
const agentsRoute = pageRoute("/agents", ROUTE_VIEWS.agents);
const agentChatRoute = pageRoute("/agents/$botId/chat", ROUTE_VIEWS.agents);
const settingsRoute = pageRoute("/settings", ROUTE_VIEWS.settings);
const settingsModelsRoute = pageRoute("/settings/models", ROUTE_VIEWS.settings);
const settingsPreferencesRoute = pageRoute("/settings/preferences", ROUTE_VIEWS.settings);
const settingsDiagnosticsRoute = pageRoute("/settings/diagnostics", ROUTE_VIEWS.settings);

const historyRoute = redirectRoute("/history", REDIRECT_TARGETS.history);
const solverRoute = redirectRoute("/solver", REDIRECT_TARGETS.solver);
const researchRoute = redirectRoute("/research", REDIRECT_TARGETS.research);
const visualizeRoute = redirectRoute("/visualize", REDIRECT_TARGETS.visualize);
const visionSolverRoute = redirectRoute("/vision-solver", REDIRECT_TARGETS.visionSolver);
const geogebraRoute = redirectRoute("/geogebra", REDIRECT_TARGETS.geogebra);
const mathAnimatorRoute = redirectRoute("/math_animator", REDIRECT_TARGETS.mathAnimatorLegacy);
const mathAnimatorHyphenRoute = redirectRoute("/math-animator", REDIRECT_TARGETS.mathAnimator);
const legacyCoWriterRoute = redirectRoute("/co_writer", REDIRECT_TARGETS.coWriterLegacy);
const compactCoWriterRoute = redirectRoute("/cowriter", REDIRECT_TARGETS.coWriterCompact);
const legacySparkBotRoute = redirectRoute("/sparkbot", REDIRECT_TARGETS.sparkBotLegacy);
const utilityKnowledgeRoute = redirectRoute("/utility/knowledge", REDIRECT_TARGETS.utilityKnowledge);
const utilityMemoryRoute = redirectRoute("/utility/memory", REDIRECT_TARGETS.utilityMemory);
const utilityNotebookRoute = redirectRoute("/utility/notebook", REDIRECT_TARGETS.utilityNotebook);
const utilitySettingsRoute = redirectRoute("/utility/settings", REDIRECT_TARGETS.utilitySettings);

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

const knowledgeWorkspaceRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/knowledge/$workspace",
  beforeLoad: ({ params }) => {
    if (params.workspace !== "create" && !isKnowledgeWorkspaceId(params.workspace)) {
      throw redirect({ to: "/knowledge" });
    }
  },
  component: KnowledgeRoute,
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
  knowledgeWorkspaceRoute,
  notebookRoute,
  memoryRoute,
  memoryEvidenceRoute,
  memoryEditRoute,
  playgroundRoute,
  guideRoute,
  coWriterRoute,
  agentsRoute,
  agentChatRoute,
  legacySparkBotRoute,
  legacySparkBotChatRoute,
  settingsRoute,
  settingsModelsRoute,
  settingsPreferencesRoute,
  settingsDiagnosticsRoute,
  utilityKnowledgeRoute,
  utilityMemoryRoute,
  utilityNotebookRoute,
  utilitySettingsRoute,
]);

export const router = createRouter({
  routeTree,
  defaultPreload: "intent",
  defaultPreloadDelay: 80,
  defaultPreloadStaleTime: 30_000,
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
