import { lazy, Suspense } from "react";

import type { KnowledgeWorkspaceRoutePanelsProps } from "./KnowledgeWorkspaceContentTypes";
import type { KnowledgeWorkspace } from "./types";

const KnowledgeWorkspaceRagRoutePanels = lazy(() =>
  import("./KnowledgeWorkspaceRagRoutePanels").then((module) => ({ default: module.KnowledgeWorkspaceRagRoutePanels })),
);
const KnowledgeWorkspaceResourceRoutePanels = lazy(() =>
  import("./KnowledgeWorkspaceResourceRoutePanels").then((module) => ({
    default: module.KnowledgeWorkspaceResourceRoutePanels,
  })),
);

const RAG_ROUTE_WORKSPACES: readonly KnowledgeWorkspace[] = ["diagnostics", "recovery", "quality", "test"];
const RESOURCE_ROUTE_WORKSPACES: readonly KnowledgeWorkspace[] = ["documents", "upload", "settings", "progress", "folders"];

export function KnowledgeWorkspaceRoutePanels(props: KnowledgeWorkspaceRoutePanelsProps) {
  const { workspace } = props;

  return (
    <>
      {RAG_ROUTE_WORKSPACES.includes(workspace) ? (
        <Suspense fallback={<KnowledgeRouteLoading label="正在准备资料问答工作区" />}>
          <KnowledgeWorkspaceRagRoutePanels {...props} />
        </Suspense>
      ) : null}

      {RESOURCE_ROUTE_WORKSPACES.includes(workspace) ? (
        <Suspense fallback={<KnowledgeRouteLoading label="正在准备资料管理工作区" />}>
          <KnowledgeWorkspaceResourceRoutePanels {...props} />
        </Suspense>
      ) : null}
    </>
  );
}

function KnowledgeRouteLoading({ label }: { label: string }) {
  return (
    <section className="rounded-lg border border-line bg-white/90 p-4">
      <p className="text-sm font-semibold text-ink">{label}</p>
      <div className="mt-3 space-y-2">
        <span className="block h-3 w-44 max-w-full rounded bg-slate-100" />
        <span className="block h-14 rounded bg-slate-100/80" />
      </div>
    </section>
  );
}
