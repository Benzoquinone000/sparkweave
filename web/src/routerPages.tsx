import { lazy, type ComponentType } from "react";

type PageModule<TExport extends string> = Record<TExport, ComponentType>;

function lazyPage<TExport extends string>(
  loader: () => Promise<PageModule<TExport>>,
  exportName: TExport,
) {
  return lazy(() => loader().then((module) => ({ default: module[exportName] })));
}

const AgentsPageView = lazyPage(() => import("@/pages/AgentsPage"), "AgentsPage");
const ChatPageView = lazyPage(() => import("@/pages/ChatPage"), "ChatPage");
const CoWriterPageView = lazyPage(() => import("@/pages/CoWriterPage"), "CoWriterPage");
const GuidePageView = lazyPage(() => import("@/pages/GuidePage"), "GuidePage");
const KnowledgePageView = lazyPage(() => import("@/pages/KnowledgePage"), "KnowledgePage");
const MemoryPageView = lazyPage(() => import("@/pages/MemoryPage"), "MemoryPage");
const NotebookPageView = lazyPage(() => import("@/pages/NotebookPage"), "NotebookPage");
const PlaygroundPageView = lazyPage(() => import("@/pages/PlaygroundPage"), "PlaygroundPage");
const QuestionLabPageView = lazyPage(() => import("@/pages/QuestionLabPage"), "QuestionLabPage");
const SettingsPageView = lazyPage(() => import("@/pages/SettingsPage"), "SettingsPage");
const VisionPageView = lazyPage(() => import("@/pages/VisionPage"), "VisionPage");

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
