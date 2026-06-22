import {
  AgentsRoute,
  ChatRoute,
  CoWriterRoute,
  GuideRoute,
  MemoryRoute,
  NotebookRoute,
  PlaygroundRoute,
  QuestionLabRoute,
  SettingsRoute,
  VisionRoute,
} from "@/routerPages";

export type RedirectTarget = {
  to: string;
  search?: Record<string, string>;
};

export const ROUTE_VIEWS = {
  agents: AgentsRoute,
  chat: ChatRoute,
  coWriter: CoWriterRoute,
  guide: GuideRoute,
  memory: MemoryRoute,
  notebook: NotebookRoute,
  playground: PlaygroundRoute,
  question: QuestionLabRoute,
  settings: SettingsRoute,
  vision: VisionRoute,
} as const;

export const REDIRECT_TARGETS = {
  history: { to: "/chat" },
  solver: { to: "/chat", search: { capability: "deep_solve" } },
  research: { to: "/chat", search: { capability: "deep_research" } },
  visualize: { to: "/chat", search: { capability: "visualize" } },
  visionSolver: { to: "/vision" },
  geogebra: { to: "/vision" },
  mathAnimatorLegacy: { to: "/chat", search: { capability: "math_animator" } },
  mathAnimator: { to: "/chat", search: { capability: "math_animator" } },
  coWriterLegacy: { to: "/co-writer" },
  coWriterCompact: { to: "/co-writer" },
  sparkBotLegacy: { to: "/agents" },
  utilityKnowledge: { to: "/knowledge" },
  utilityMemory: { to: "/memory" },
  utilityNotebook: { to: "/notebook" },
  utilitySettings: { to: "/settings" },
} as const satisfies Record<string, RedirectTarget>;
