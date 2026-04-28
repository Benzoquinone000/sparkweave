import { lazy } from "react";

const AgentsPageView = lazy(() => import("@/pages/AgentsPage").then((module) => ({ default: module.AgentsPage })));
const ChatPageView = lazy(() => import("@/pages/ChatPage").then((module) => ({ default: module.ChatPage })));
const CoWriterPageView = lazy(() => import("@/pages/CoWriterPage").then((module) => ({ default: module.CoWriterPage })));
const GuidePageView = lazy(() => import("@/pages/GuidePage").then((module) => ({ default: module.GuidePage })));
const KnowledgePageView = lazy(() =>
  import("@/pages/KnowledgePage").then((module) => ({ default: module.KnowledgePage })),
);
const MemoryPageView = lazy(() => import("@/pages/MemoryPage").then((module) => ({ default: module.MemoryPage })));
const NotebookPageView = lazy(() => import("@/pages/NotebookPage").then((module) => ({ default: module.NotebookPage })));
const PlaygroundPageView = lazy(() =>
  import("@/pages/PlaygroundPage").then((module) => ({ default: module.PlaygroundPage })),
);
const QuestionLabPageView = lazy(() =>
  import("@/pages/QuestionLabPage").then((module) => ({ default: module.QuestionLabPage })),
);
const SettingsPageView = lazy(() => import("@/pages/SettingsPage").then((module) => ({ default: module.SettingsPage })));
const VisionPageView = lazy(() => import("@/pages/VisionPage").then((module) => ({ default: module.VisionPage })));

export function AgentsRoute() {
  return <AgentsPageView />;
}

export function ChatRoute() {
  return <ChatPageView />;
}

export function CoWriterRoute() {
  return <CoWriterPageView />;
}

export function GuideRoute() {
  return <GuidePageView />;
}

export function KnowledgeRoute() {
  return <KnowledgePageView />;
}

export function MemoryRoute() {
  return <MemoryPageView />;
}

export function NotebookRoute() {
  return <NotebookPageView />;
}

export function PlaygroundRoute() {
  return <PlaygroundPageView />;
}

export function QuestionLabRoute() {
  return <QuestionLabPageView />;
}

export function SettingsRoute() {
  return <SettingsPageView />;
}

export function VisionRoute() {
  return <VisionPageView />;
}
