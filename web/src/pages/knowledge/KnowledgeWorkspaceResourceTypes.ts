import type { FormEvent } from "react";

import type {
  KnowledgeBase,
  KnowledgeConfig,
  KnowledgeDocumentPreview,
  KnowledgeDocumentSummary,
  KnowledgeTaskStatusResponse,
  KnowledgeVectorChunk,
  LinkedFolder,
} from "@/lib/types";

import type { KnowledgeWsStatus } from "./progressFormat";

export type WorkspaceDocumentsProps = {
  documents: KnowledgeDocumentSummary[];
  documentsLoading: boolean;
  documentsError: unknown;
  selectedDocumentId: string;
  selectedDocument: KnowledgeDocumentSummary | null;
  preview: KnowledgeDocumentPreview | null;
  previewLoading: boolean;
  vectorChunks: KnowledgeVectorChunk[];
  vectorTotal: number;
  vectorsAvailable: boolean;
  vectorsError: string;
  vectorsLoading: boolean;
  deletingDocument: boolean;
  deletingChunk: boolean;
  onSelectDocument: (documentId: string) => void;
  onRefresh: () => void;
  onPreview: (documentId: string) => void;
  onDeleteDocument: (document: KnowledgeDocumentSummary) => void;
  onDeleteChunk: (chunk: KnowledgeVectorChunk) => void;
};

export type WorkspaceUploadProps = {
  bases: KnowledgeBase[];
  files: File[];
  uploading: boolean;
  error?: unknown;
  onKbChange: (kbName: string) => void;
  onFilesChange: (files: File[]) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onRecover: () => void;
};

export type WorkspaceSettingsProps = {
  activeConfig?: KnowledgeConfig;
  configFormKey: string;
  saving: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

export type WorkspaceFoldersProps = {
  folderPath: string;
  folders: LinkedFolder[];
  linking: boolean;
  syncing: boolean;
  unlinking: boolean;
  onFolderPathChange: (path: string) => void;
  onLink: (event: FormEvent<HTMLFormElement>) => void;
  onSync: (folderId: string) => void;
  onUnlink: (folderId: string) => void;
};

export type WorkspaceProgressProps = {
  progressStage: string;
  progressMessage: string;
  progressPercent: number;
  wsStatus: KnowledgeWsStatus;
  taskMilestones: string[];
  taskLogs: string[];
  taskStatus?: KnowledgeTaskStatusResponse | null;
  taskStatusLoading?: boolean;
  clearing: boolean;
  onClear: () => void;
};
