import { lazy, Suspense } from "react";

import type { KnowledgeWorkspaceRoutePanelsProps } from "./KnowledgeWorkspaceContentTypes";

const KnowledgeDocumentManager = lazy(() =>
  import("./KnowledgeDocumentManager").then((module) => ({ default: module.KnowledgeDocumentManager })),
);
const KnowledgeFoldersPanel = lazy(() =>
  import("./KnowledgeFoldersPanel").then((module) => ({ default: module.KnowledgeFoldersPanel })),
);
const KnowledgeProgressPanel = lazy(() =>
  import("./KnowledgeProgressPanel").then((module) => ({ default: module.KnowledgeProgressPanel })),
);
const KnowledgeSettingsPanel = lazy(() =>
  import("./KnowledgeSettingsPanel").then((module) => ({ default: module.KnowledgeSettingsPanel })),
);
const KnowledgeUploadPanel = lazy(() =>
  import("./KnowledgeUploadPanel").then((module) => ({ default: module.KnowledgeUploadPanel })),
);

export function KnowledgeWorkspaceResourceRoutePanels({
  activeKb,
  workspace,
  documents,
  upload,
  settings,
  folders,
  progress,
}: KnowledgeWorkspaceRoutePanelsProps) {
  return (
    <>
      {activeKb && workspace === "documents" ? (
        <Suspense fallback={<ResourceRouteLoading label="正在准备文档管理" />}>
          <KnowledgeDocumentManager
            documents={documents.documents}
            documentsLoading={documents.documentsLoading}
            documentsError={documents.documentsError}
            selectedDocumentId={documents.selectedDocumentId}
            selectedDocument={documents.selectedDocument}
            onSelectDocument={documents.onSelectDocument}
            onRefresh={documents.onRefresh}
            onPreview={documents.onPreview}
            preview={documents.preview}
            previewLoading={documents.previewLoading}
            vectorChunks={documents.vectorChunks}
            vectorTotal={documents.vectorTotal}
            vectorsAvailable={documents.vectorsAvailable}
            vectorsError={documents.vectorsError}
            vectorsLoading={documents.vectorsLoading}
            onDeleteDocument={documents.onDeleteDocument}
            onDeleteChunk={documents.onDeleteChunk}
            deletingDocument={documents.deletingDocument}
            deletingChunk={documents.deletingChunk}
          />
        </Suspense>
      ) : null}

      {workspace === "upload" ? (
        <Suspense fallback={<ResourceRouteLoading label="正在准备上传入口" />}>
          <KnowledgeUploadPanel
            activeKb={activeKb}
            bases={upload.bases}
            files={upload.files}
            uploading={upload.uploading}
            error={upload.error}
            onKbChange={upload.onKbChange}
            onFilesChange={upload.onFilesChange}
            onSubmit={upload.onSubmit}
            onRecover={upload.onRecover}
          />
        </Suspense>
      ) : null}

      {workspace === "settings" ? (
        <Suspense fallback={<ResourceRouteLoading label="正在准备资料库设置" />}>
          <KnowledgeSettingsPanel
            activeKb={activeKb}
            activeConfig={settings.activeConfig}
            configFormKey={settings.configFormKey}
            saving={settings.saving}
            onSubmit={settings.onSubmit}
          />
        </Suspense>
      ) : null}

      {workspace === "folders" ? (
        <Suspense fallback={<ResourceRouteLoading label="正在准备同步文件夹" />}>
          <KnowledgeFoldersPanel
            activeKb={activeKb}
            folderPath={folders.folderPath}
            folders={folders.folders}
            linking={folders.linking}
            syncing={folders.syncing}
            unlinking={folders.unlinking}
            onFolderPathChange={folders.onFolderPathChange}
            onLink={folders.onLink}
            onSync={folders.onSync}
            onUnlink={folders.onUnlink}
          />
        </Suspense>
      ) : null}

      {workspace === "progress" ? (
        <Suspense fallback={<ResourceRouteLoading label="正在准备处理进度" />}>
          <KnowledgeProgressPanel
            visible
            activeKb={activeKb}
            progressStage={progress.progressStage}
            progressMessage={progress.progressMessage}
            progressPercent={progress.progressPercent}
            wsStatus={progress.wsStatus}
            taskMilestones={progress.taskMilestones}
            taskLogs={progress.taskLogs}
            taskStatus={progress.taskStatus}
            taskStatusLoading={progress.taskStatusLoading}
            clearing={progress.clearing}
            onClear={progress.onClear}
          />
        </Suspense>
      ) : null}
    </>
  );
}

function ResourceRouteLoading({ label }: { label: string }) {
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
