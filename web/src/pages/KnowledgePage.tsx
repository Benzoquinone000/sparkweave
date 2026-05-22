import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "@tanstack/react-router";

import { KnowledgeLibrarySidebar } from "./knowledge/KnowledgeLibrarySidebar";
import { KnowledgeStatusStrip } from "./knowledge/KnowledgeStatusStrip";
import {
  formatProgressStage,
  formatErrorMessage,
  formatRagDiagnosticStatus,
  knowledgeProviderLabel,
  summarizeKnowledgePayload,
} from "./knowledge/format";
import {
  clampPercent,
  formatKnowledgeLogLine,
  formatProgressMessage,
  summarizeKnowledgeTaskLogs,
  withLegacyText,
} from "./knowledge/progressFormat";
import {
  RAG_TEST_PRESETS,
  matchRagTestPreset,
  type RagTestSettings,
} from "./knowledge/ragTestConfig";
import { buildQuickRagEvaluationCases } from "./knowledge/ragEvaluationCases";
import { isRecord, readNumber, readString } from "./knowledge/ragUtils";
import { buildKnowledgeRecoveryPlan, type KnowledgeRecoveryActionId } from "./knowledge/recovery";
import type { KnowledgeWorkspace } from "./knowledge/types";
import { useKnowledgeTaskProgress } from "./knowledge/useKnowledgeTaskProgress";
import {
  useDefaultKnowledgeBase,
  useKnowledgeBases,
  useKnowledgeConfigAudit,
  useKnowledgeBaseDetail,
  useKnowledgeConfig,
  useKnowledgeDiagnostics,
  useKnowledgeDocumentPreview,
  useKnowledgeDocuments,
  useKnowledgeHealth,
  useKnowledgeMutations,
  useKnowledgeProgress,
  useKnowledgePreflight,
  useKnowledgeTaskStatus,
  useKnowledgeRagEvaluation,
  useKnowledgeVectorChunks,
  useLinkedFolders,
  useRagProviders,
} from "@/hooks/useApiQueries";
import { isKnowledgeWorkspaceId, parseKnowledgeHandoffSearch, type RagTestHandoff } from "@/lib/ragHandoff";

const KnowledgeCreatePanel = lazy(() =>
  import("./knowledge/KnowledgeCreatePanel").then((module) => ({ default: module.KnowledgeCreatePanel })),
);
const KnowledgeWorkspaceContent = lazy(() =>
  import("./knowledge/KnowledgeWorkspaceContent").then((module) => ({ default: module.KnowledgeWorkspaceContent })),
);

type KnowledgeView = "browse" | "create";

export function KnowledgePage() {
  const location = useLocation();
  const navigate = useNavigate();
  const routeState = useMemo(() => knowledgeRouteStateFromPath(location.pathname), [location.pathname]);
  const query = useKnowledgeBases();
  const providers = useRagProviders();
  const health = useKnowledgeHealth();
  const configAudit = useKnowledgeConfigAudit();
  const defaultKb = useDefaultKnowledgeBase();
  const mutations = useKnowledgeMutations();
  const bases = useMemo(() => query.data ?? [], [query.data]);
  const backendDefaultName = defaultKb.data?.default_kb || "";
  const defaultBase = useMemo(
    () => bases.find((item) => item.is_default) ?? bases.find((item) => item.name === backendDefaultName),
    [backendDefaultName, bases],
  );
  const [selectedKb, setSelectedKb] = useState(() => knowledgeBaseNameFromSearch(location.search));
  const routeTaskId = searchParamValue(location.search, "task");
  const view = routeState.view;
  const workspace = routeState.workspace;
  const [createName, setCreateName] = useState("");
  const [ragProvider, setRagProvider] = useState("");
  const [createFiles, setCreateFiles] = useState<File[]>([]);
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [folderPath, setFolderPath] = useState("");
  const [ragEvalPreset, setRagEvalPreset] = useState("quick_check");
  const [ragTestQuery, setRagTestQuery] = useState("");
  const [ragTestProfile, setRagTestProfile] = useState("auto");
  const [ragTestMode, setRagTestMode] = useState("hybrid");
  const [ragTestAgentic, setRagTestAgentic] = useState("auto");
  const [ragTestTopK, setRagTestTopK] = useState(5);
  const [ragTestAgenticMaxContextChars, setRagTestAgenticMaxContextChars] = useState(5000);
  const [ragTestAgenticMaxSources, setRagTestAgenticMaxSources] = useState(8);
  const [ragTestMinRelevantCoverage, setRagTestMinRelevantCoverage] = useState(0.67);
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [previewDocumentId, setPreviewDocumentId] = useState("");
  const [ragTestHandoff, setRagTestHandoff] = useState<RagTestHandoff | null>(null);
  const consumedSearchParamsRef = useRef("");
  const activeKb = selectedKb && bases.some((item) => item.name === selectedKb) ? selectedKb : defaultBase?.name || bases[0]?.name || "";
  const kbDetail = useKnowledgeBaseDetail(activeKb || null);
  const progress = useKnowledgeProgress(activeKb || null);
  const kbConfig = useKnowledgeConfig(activeKb || null);
  const ragDiagnostic = useKnowledgeDiagnostics(activeKb || null, true, false);
  const ragPreflight = useKnowledgePreflight(activeKb || null, true, false, false);
  const ragEvaluation = useKnowledgeRagEvaluation(activeKb || null);
  const documents = useKnowledgeDocuments(activeKb || null);
  const documentItems = useMemo(() => documents.data?.documents ?? [], [documents.data?.documents]);
  const effectiveSelectedDocumentId = useMemo(() => {
    if (documentItems.some((item) => item.id === selectedDocumentId)) return selectedDocumentId;
    return documentItems[0]?.id ?? "";
  }, [documentItems, selectedDocumentId]);
  const effectivePreviewDocumentId = useMemo(() => {
    if (documentItems.some((item) => item.id === previewDocumentId)) return previewDocumentId;
    return "";
  }, [documentItems, previewDocumentId]);
  const selectedDocument = useMemo(
    () => documentItems.find((item) => item.id === effectiveSelectedDocumentId) ?? null,
    [documentItems, effectiveSelectedDocumentId],
  );
  const shouldLoadVectorChunks = workspace === "documents" && Boolean(effectiveSelectedDocumentId);
  const vectorChunks = useKnowledgeVectorChunks(activeKb || null, effectiveSelectedDocumentId || null, shouldLoadVectorChunks);
  const documentPreview = useKnowledgeDocumentPreview(activeKb || null, effectivePreviewDocumentId || null, Boolean(effectivePreviewDocumentId));
  const linkedFolders = useLinkedFolders(activeKb || null);
  const refetchKnowledgeBases = query.refetch;
  const refetchKnowledgeDetail = kbDetail.refetch;
  const refetchKnowledgeProgress = progress.refetch;
  const refetchKnowledgeConfig = kbConfig.refetch;
  const refetchKnowledgeDocuments = documents.refetch;
  const refetchKnowledgeVectors = vectorChunks.refetch;
  const refetchKnowledgeDiagnostic = ragDiagnostic.refetch;
  const refetchKnowledgePreflight = ragPreflight.refetch;
  const refetchActiveKnowledgeArtifacts = useCallback(() => {
    void refetchKnowledgeProgress();
    void refetchKnowledgeBases();
    void refetchKnowledgeDetail();
    void refetchKnowledgeConfig();
    void refetchKnowledgeDocuments();
    if (shouldLoadVectorChunks) {
      void refetchKnowledgeVectors();
    }
    void refetchKnowledgeDiagnostic();
    void refetchKnowledgePreflight();
  }, [
    refetchKnowledgeBases,
    refetchKnowledgeConfig,
    refetchKnowledgeDetail,
    refetchKnowledgeDiagnostic,
    refetchKnowledgeDocuments,
    refetchKnowledgePreflight,
    refetchKnowledgeProgress,
    refetchKnowledgeVectors,
    shouldLoadVectorChunks,
  ]);
  const {
    taskId,
    taskLogs,
    taskProgress,
    wsProgress,
    wsStatus,
    beginTask,
    pushTaskLog,
    resetTask,
    setTaskLogs,
  } = useKnowledgeTaskProgress({
    activeKb,
    onTerminalProgress: refetchActiveKnowledgeArtifacts,
  });

  useEffect(() => {
    if (!routeTaskId || taskId === routeTaskId) return;
    const kbName = activeKb || selectedKb;
    if (!kbName) return;
    const timer = window.setTimeout(() => beginTask(routeTaskId, kbName), 0);
    return () => window.clearTimeout(timer);
  }, [activeKb, beginTask, routeTaskId, selectedKb, taskId]);
  const taskStatus = useKnowledgeTaskStatus(taskId);
  const activeConfig = kbConfig.data?.config;
  const liveProgress = wsProgress ?? taskProgress ?? progress.data;
  const progressPercent = clampPercent(liveProgress?.percent);
  const progressStage = formatProgressStage(liveProgress?.stage || liveProgress?.status || "idle");
  const progressMessage = formatProgressMessage(liveProgress, activeKb, Boolean(taskId || taskLogs.length));
  const taskMilestones = useMemo(() => summarizeKnowledgeTaskLogs(taskLogs), [taskLogs]);
  const activeStatistics = isRecord(kbDetail.data?.statistics) ? kbDetail.data.statistics : {};
  const activeMetadata = isRecord(kbDetail.data?.metadata) ? kbDetail.data.metadata : {};
  const activeDocumentCount =
    readNumber(kbDetail.data, "document_count") ??
    readNumber(activeStatistics, "document_count") ??
    readNumber(activeStatistics, "documents") ??
    (Array.isArray(kbDetail.data?.documents) ? kbDetail.data.documents.length : undefined);
  const activeFileCount =
    readNumber(kbDetail.data, "file_count") ??
    readNumber(activeStatistics, "file_count") ??
    readNumber(activeStatistics, "files") ??
    (Array.isArray(kbDetail.data?.files) ? kbDetail.data.files.length : undefined);
  const visibleDocumentCount = documents.data?.document_count ?? documents.data?.documents?.length ?? activeDocumentCount;
  const visibleVectorCount = documents.data?.vector_count ?? readNumber(ragDiagnostic.data, "vector_row_count");
  const activePath = readString(kbDetail.data, "path") || readString(activeMetadata, "path") || activeKb || "-";
  const activeStatus = kbDetail.data?.status || (kbDetail.isLoading ? "loading" : activeKb ? "ready" : "idle");
  const activeSummaryPayload = Object.keys(activeMetadata).length ? activeMetadata : activeStatistics;
  const activeSummaryItems = summarizeKnowledgePayload(activeSummaryPayload);
  const latestKnowledgeError =
    mutations.create.error ||
    mutations.upload.error ||
    mutations.reindex.error ||
    mutations.syncFolder.error ||
    mutations.runRagEvaluation.error ||
    mutations.testRagSearch.error ||
    ragDiagnostic.error ||
    documents.error ||
    vectorChunks.error;
  const recoveryPlan = useMemo(
    () =>
      buildKnowledgeRecoveryPlan({
        activeKb,
        documentCount: visibleDocumentCount,
        vectorCount: visibleVectorCount,
        progressStage: liveProgress?.stage || liveProgress?.status || activeStatus,
        progressMessage,
        taskActive: Boolean(taskId),
        readinessState: String(ragDiagnostic.data?.readiness?.state || ""),
        readinessLabel: String(ragDiagnostic.data?.readiness?.label || ""),
        readinessSummary: String(ragDiagnostic.data?.readiness?.summary || ""),
        readinessAction: String(ragDiagnostic.data?.readiness?.primary_action || ""),
        diagnosticStatus: ragDiagnostic.data?.readiness?.label || formatRagDiagnosticStatus(ragDiagnostic.data?.status, Boolean(ragDiagnostic.error)),
        latestError: latestKnowledgeError ? formatErrorMessage(latestKnowledgeError) : "",
      }),
    [
      activeKb,
      activeStatus,
      latestKnowledgeError,
      liveProgress?.stage,
      liveProgress?.status,
      progressMessage,
      ragDiagnostic.data,
      ragDiagnostic.error,
      taskId,
      visibleDocumentCount,
      visibleVectorCount,
    ],
  );
  const ragTestSettings = useMemo<RagTestSettings>(
    () => ({
      profile: ragTestProfile,
      mode: ragTestMode,
      agentic: ragTestAgentic,
      topK: ragTestTopK,
      agenticMaxContextChars: ragTestAgenticMaxContextChars,
      agenticMaxSources: ragTestAgenticMaxSources,
      agenticMinRelevantCoverage: ragTestMinRelevantCoverage,
    }),
    [
      ragTestAgentic,
      ragTestAgenticMaxContextChars,
      ragTestAgenticMaxSources,
      ragTestMinRelevantCoverage,
      ragTestMode,
      ragTestProfile,
      ragTestTopK,
    ],
  );
  const activeRagTestPresetId = useMemo(() => matchRagTestPreset(ragTestSettings), [ragTestSettings]);

  const navigateToOverview = useCallback(
    (kbName = activeKb) => {
      void navigate({ to: "/knowledge", search: knowledgeSearch(kbName) });
    },
    [activeKb, navigate],
  );

  const navigateToCreate = useCallback(() => {
    void navigate({ to: "/knowledge/$workspace", params: { workspace: "create" }, search: knowledgeSearch(activeKb) });
  }, [activeKb, navigate]);

  const navigateToWorkspace = useCallback(
    (nextWorkspace: KnowledgeWorkspace, kbName = activeKb, nextTaskId?: string | null) => {
      if (nextWorkspace === "overview") {
        void navigate({ to: "/knowledge", search: knowledgeSearch(kbName) });
        return;
      }
      void navigate({ to: "/knowledge/$workspace", params: { workspace: nextWorkspace }, search: knowledgeSearch(kbName, nextTaskId) });
    },
    [activeKb, navigate],
  );

  const applyRagTestPreset = useCallback((presetId: string) => {
    const preset = RAG_TEST_PRESETS.find((item) => item.id === presetId);
    if (!preset) return;
    setRagTestProfile(preset.profile);
    setRagTestMode(preset.mode);
    setRagTestAgentic(preset.agentic);
    setRagTestTopK(preset.topK);
    setRagTestAgenticMaxContextChars(preset.agenticMaxContextChars);
    setRagTestAgenticMaxSources(preset.agenticMaxSources);
    setRagTestMinRelevantCoverage(preset.agenticMinRelevantCoverage);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const intent = parseKnowledgeHandoffSearch(window.location.search);
    if (!intent || consumedSearchParamsRef.current === intent.cacheKey) return;
    consumedSearchParamsRef.current = intent.cacheKey;
    const timer = window.setTimeout(() => {
      if (intent.kbName) setSelectedKb(intent.kbName);
      if (intent.query) setRagTestQuery(intent.query);
      if (intent.handoff) setRagTestHandoff(intent.handoff);
      if (intent.presetId && RAG_TEST_PRESETS.some((item) => item.id === intent.presetId)) {
        applyRagTestPreset(intent.presetId);
      }

      if (intent.profile) setRagTestProfile(intent.profile);
      if (intent.mode) setRagTestMode(intent.mode);
      if (intent.agentic) setRagTestAgentic(intent.agentic);
      if (typeof intent.topK === "number") setRagTestTopK(intent.topK);
      if (typeof intent.agenticMaxContextChars === "number") setRagTestAgenticMaxContextChars(intent.agenticMaxContextChars);
      if (typeof intent.agenticMaxSources === "number") setRagTestAgenticMaxSources(intent.agenticMaxSources);
      if (typeof intent.agenticMinRelevantCoverage === "number") setRagTestMinRelevantCoverage(intent.agenticMinRelevantCoverage);

      if (intent.workspace) {
        navigateToWorkspace(intent.workspace, intent.kbName || activeKb);
      } else if (intent.query || intent.presetId) {
        navigateToWorkspace("test", intent.kbName || activeKb);
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, [activeKb, applyRagTestPreset, navigateToWorkspace]);

  useEffect(() => {
    const kbName = knowledgeBaseNameFromSearch(location.search);
    if (!kbName || kbName === selectedKb) return undefined;
    const timer = window.setTimeout(() => setSelectedKb(kbName), 0);
    return () => window.clearTimeout(timer);
  }, [location.search, selectedKb]);

  useEffect(() => {
    if (view === "browse" && workspace === "diagnostics" && activeKb) {
      void refetchKnowledgeDiagnostic();
      void refetchKnowledgePreflight();
    }
  }, [activeKb, refetchKnowledgeDiagnostic, refetchKnowledgePreflight, view, workspace]);

  const openDiagnostics = useCallback(() => {
    navigateToWorkspace("diagnostics");
    void refetchKnowledgeDiagnostic();
    void refetchKnowledgePreflight();
  }, [navigateToWorkspace, refetchKnowledgeDiagnostic, refetchKnowledgePreflight]);

  const providerOptions = useMemo(() => providers.data ?? [], [providers.data]);
  const activeProvider = ragProvider || providerOptions.find((item) => item.is_default)?.name || providerOptions[0]?.name || "";
  const configFormKey = [
    activeKb,
    activeConfig?.search_mode,
    activeConfig?.description,
    activeConfig?.needs_reindex ? "reindex" : "ready",
  ].join(":");

  const saveKbConfig = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!activeKb) return;
    const form = new FormData(event.currentTarget);
    await mutations.updateConfig.mutateAsync({
      kbName: activeKb,
      config: {
        search_mode: String(form.get("search_mode") || "hybrid"),
        description: String(form.get("description") || ""),
        needs_reindex: form.get("needs_reindex") === "on",
      },
    });
    pushTaskLog(`设置已保存：${activeKb}`);
  };

  const clearActiveProgress = async () => {
    if (!activeKb) return;
    const result = await mutations.clearProgress.mutateAsync(activeKb);
    resetTask([result.message ? withLegacyText(formatKnowledgeLogLine(result.message), result.message) : `已清理 ${activeKb} 的进度状态。`]);
  };

  const createKb = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedName = createName.trim();
    if (!trimmedName || !createFiles.length) return;
    const result = await mutations.create.mutateAsync({
      name: trimmedName,
      files: createFiles,
      ragProvider: activeProvider || undefined,
    });
    const nextTaskId = result.task_id ?? null;
    const nextKbName = result.name || trimmedName;
    beginTask(nextTaskId, nextKbName);
    setSelectedKb(nextKbName);
    navigateToWorkspace("progress", nextKbName, nextTaskId);
    setCreateName("");
    setCreateFiles([]);
  };

  const uploadToKb = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!activeKb || !uploadFiles.length) return;
    const result = await mutations.upload.mutateAsync({
      kbName: activeKb,
      files: uploadFiles,
      ragProvider: activeProvider || undefined,
    });
    const nextTaskId = result.task_id ?? null;
    beginTask(nextTaskId, activeKb);
    navigateToWorkspace("progress", activeKb, nextTaskId);
    setUploadFiles([]);
  };

  const reindexActiveKb = async () => {
    if (!activeKb) return;
    const result = await mutations.reindex.mutateAsync({
      kbName: activeKb,
      ragProvider: activeProvider || undefined,
      backup: true,
    });
    const nextTaskId = result.task_id ?? null;
    beginTask(nextTaskId, activeKb);
    navigateToWorkspace("progress", activeKb, nextTaskId);
  };

  const runActiveRagEvaluation = async () => {
    if (!activeKb) return;
    const report = await mutations.runRagEvaluation.mutateAsync({
      kbName: activeKb,
      preset: ragEvalPreset,
      provider: activeConfig?.rag_provider || kbDetail.data?.rag_provider || activeProvider || undefined,
      cases: buildQuickRagEvaluationCases(activeKb),
    });
    pushTaskLog(`资料质量检查已完成：${report.strategy_count ?? 0} 个方案，${report.case_count ?? 0} 个样本。`);
    await ragEvaluation.refetch();
  };

  const runActiveRagTest = async () => {
    if (!activeKb || !ragTestQuery.trim()) return;
    await mutations.testRagSearch.mutateAsync({
      kbName: activeKb,
      query: ragTestQuery.trim(),
      provider: activeConfig?.rag_provider || kbDetail.data?.rag_provider || activeProvider || undefined,
      retrievalProfile: ragTestProfile,
      retrievalMode: ragTestMode,
      agenticRag: ragTestAgentic,
      topK: ragTestTopK,
      candidateTopK: Math.max(ragTestTopK * 3, ragTestTopK),
      reranker: "keyword",
      agenticMaxContextChars: ragTestAgenticMaxContextChars,
      agenticMaxSources: ragTestAgenticMaxSources,
      agenticMinRelevantCoverageRatio: ragTestMinRelevantCoverage,
      maxContextChars: ragTestAgenticMaxContextChars,
    });
  };

  const handleRecoveryAction = (action: KnowledgeRecoveryActionId) => {
    if (action === "reindex") {
      void reindexActiveKb();
      return;
    }
    if (action === "diagnostics") {
      openDiagnostics();
      return;
    }
    if (action === "test") {
      navigateToWorkspace("test");
      return;
    }
    navigateToWorkspace(action);
  };

  const linkFolder = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!activeKb || !folderPath.trim()) return;
    await mutations.linkFolder.mutateAsync({ kbName: activeKb, folderPath: folderPath.trim() });
    setFolderPath("");
  };

  const syncFolder = async (folderId: string) => {
    if (!activeKb) return;
    const result = await mutations.syncFolder.mutateAsync({ kbName: activeKb, folderId });
    const nextTaskId = result.task_id ?? null;
    beginTask(nextTaskId, activeKb);
    if (nextTaskId) navigateToWorkspace("progress", activeKb, nextTaskId);
    if (!result.task_id && result.message) {
      setTaskLogs((current) => [result.message || "文件夹暂无需要同步的变化。", ...current].slice(0, 80));
    }
  };

  return (
    <div className="dt-dynamic-page h-full overflow-y-auto px-3.5 py-3.5 pb-20 lg:px-4 lg:pb-4">
      <div className="mx-auto flex max-w-[980px] flex-col gap-3.5">
        <Header
          eyebrow="资料"
          title="把资料放进来，然后直接提问"
          description="上传课件、笔记或论文后，系统会准备可引用内容；你可以直接围绕资料提问。"
        />

        <KnowledgeStatusStrip
          count={bases.length}
          defaultName={defaultBase?.name || backendDefaultName || "未设置"}
          staleConfigCount={configAudit.data?.missing_count ?? 0}
          rag={health.data?.rag}
          refreshing={query.isFetching}
          error={Boolean(query.error)}
          cleaning={mutations.pruneMissingConfigs.isPending}
          onCleanConfigs={() => void mutations.pruneMissingConfigs.mutateAsync({ dryRun: false })}
        />

        <div className="grid gap-3.5 lg:grid-cols-[292px_minmax(0,1fr)]">
          <KnowledgeLibrarySidebar
            bases={bases}
            activeKb={activeKb}
            createActive={view === "create"}
            refreshing={query.isFetching}
            onRefresh={() => void query.refetch()}
            onCreate={navigateToCreate}
            onSelect={(kbName) => {
              setSelectedKb(kbName);
              navigateToOverview(kbName);
            }}
          />

          <div className="space-y-4">
            {view === "create" ? (
              <Suspense
                fallback={
                  <KnowledgeWorkspaceLoading title="正在准备资料库创建页" description="上传入口和查找服务选项马上就绪。" />
                }
              >
                <KnowledgeCreatePanel
                  name={createName}
                  files={createFiles}
                  provider={activeProvider}
                  providers={providerOptions}
                  creating={mutations.create.isPending}
                  error={mutations.create.error}
                  onNameChange={setCreateName}
                  onFilesChange={setCreateFiles}
                  onProviderChange={setRagProvider}
                  onSubmit={createKb}
                  onBack={navigateToOverview}
                />
              </Suspense>
            ) : null}

            {view === "browse" ? (
              <Suspense
                fallback={
                  <KnowledgeWorkspaceLoading title="正在准备资料工作台" description="资料状态、连接检查和管理入口正在加载。" />
                }
              >
                <KnowledgeWorkspaceContent
                  activeKb={activeKb}
                  workspace={workspace}
                  overview={{
                  activeStatus,
                  activeFileCount,
                  activeDocumentCount,
                  activeSearchLabel: knowledgeProviderLabel(activeConfig?.rag_provider || kbDetail.data?.rag_provider || "milvus"),
                  activePath,
                  progressMessage,
                  progressPercent,
                  progressStage,
                  wsStatus,
                  taskActive: Boolean(taskId),
                  documentCount: visibleDocumentCount,
                  vectorCount: visibleVectorCount,
                  diagnosticStatus:
                    ragDiagnostic.data?.readiness?.label ||
                    formatRagDiagnosticStatus(ragDiagnostic.data?.status, Boolean(ragDiagnostic.error)),
                  recoveryBadge: recoveryPlan.badge,
                  recoveryNeedsAttention: recoveryPlan.needsAttention,
                  evaluationAvailable: Boolean(ragEvaluation.data?.available),
                  testSourceCount: mutations.testRagSearch.data?.source_count,
                  folderCount: linkedFolders.data?.length ?? 0,
                  summaryItems: activeSummaryItems,
                  reindexing: mutations.reindex.isPending,
                  diagnosing: ragDiagnostic.isFetching,
                  defaultActive: defaultBase?.name === activeKb,
                  settingDefault: mutations.setDefault.isPending,
                  removing: mutations.remove.isPending,
                  onReindex: () => void reindexActiveKb(),
                  onDiagnose: openDiagnostics,
                  onSetDefault: () => activeKb && void mutations.setDefault.mutateAsync(activeKb),
                  onDelete: () => {
                    if (activeKb && window.confirm(`删除资料库 ${activeKb}？`)) void mutations.remove.mutateAsync(activeKb);
                  },
                }}
                diagnostics={{
                  report: ragDiagnostic.data,
                  error: ragDiagnostic.error,
                  fetching: ragDiagnostic.isFetching,
                  preflight: ragPreflight.data,
                  preflightError: ragPreflight.error,
                  preflightFetching: ragPreflight.isFetching,
                  reindexing: mutations.reindex.isPending,
                  onRefresh: openDiagnostics,
                  onOpenRecovery: () => navigateToWorkspace("recovery"),
                  onOpenTest: () => navigateToWorkspace("test"),
                  onReindex: () => void reindexActiveKb(),
                }}
                recoveryPlan={recoveryPlan}
                quality={{
                  report: ragEvaluation.data?.report ?? null,
                  available: Boolean(ragEvaluation.data?.available),
                  loading: ragEvaluation.isLoading,
                  error: ragEvaluation.error,
                  preset: ragEvalPreset,
                  running: mutations.runRagEvaluation.isPending,
                  onRefresh: () => void ragEvaluation.refetch(),
                  onPresetChange: setRagEvalPreset,
                  onRun: () => void runActiveRagEvaluation(),
                }}
                ragTest={{
                  query: ragTestQuery,
                  profile: ragTestProfile,
                  mode: ragTestMode,
                  agentic: ragTestAgentic,
                  topK: ragTestTopK,
                  agenticMaxContextChars: ragTestAgenticMaxContextChars,
                  agenticMaxSources: ragTestAgenticMaxSources,
                  agenticMinRelevantCoverage: ragTestMinRelevantCoverage,
                  presetId: activeRagTestPresetId,
                  result: mutations.testRagSearch.data ?? null,
                  error: mutations.testRagSearch.error,
                  running: mutations.testRagSearch.isPending,
                  handoff: ragTestHandoff,
                  onQueryChange: setRagTestQuery,
                  onProfileChange: setRagTestProfile,
                  onModeChange: setRagTestMode,
                  onAgenticChange: setRagTestAgentic,
                  onTopKChange: setRagTestTopK,
                  onAgenticMaxContextCharsChange: setRagTestAgenticMaxContextChars,
                  onAgenticMaxSourcesChange: setRagTestAgenticMaxSources,
                  onAgenticMinRelevantCoverageChange: setRagTestMinRelevantCoverage,
                  onPresetApply: applyRagTestPreset,
                  onRun: () => void runActiveRagTest(),
                  onHandoffDismiss: () => setRagTestHandoff(null),
                  onOpenDiagnostics: openDiagnostics,
                }}
                documents={{
                  documents: documents.data?.documents ?? [],
                  documentsLoading: documents.isLoading,
                  documentsError: documents.error,
                  selectedDocumentId: effectiveSelectedDocumentId,
                  selectedDocument,
                  preview: documentPreview.data ?? null,
                  previewLoading: documentPreview.isLoading || documentPreview.isFetching,
                  vectorChunks: vectorChunks.data?.chunks ?? [],
                  vectorTotal: vectorChunks.data?.total ?? 0,
                  vectorsAvailable: vectorChunks.data?.available !== false,
                  vectorsError: vectorChunks.data?.error || "",
                  vectorsLoading: vectorChunks.isLoading || vectorChunks.isFetching,
                  deletingDocument: mutations.removeDocument.isPending,
                  deletingChunk: mutations.removeVectorChunk.isPending,
                  onSelectDocument: setSelectedDocumentId,
                  onRefresh: () => {
                    void documents.refetch();
                    void vectorChunks.refetch();
                  },
                  onPreview: setPreviewDocumentId,
                  onDeleteDocument: (document) => {
                    if (window.confirm(`删除资料 ${document.name}？这会同步删除对应引用片段。`)) {
                      void mutations.removeDocument.mutateAsync({
                        kbName: activeKb,
                        documentId: document.id,
                        removeRaw: true,
                        removeVectors: true,
                      });
                    }
                  },
                  onDeleteChunk: (chunk) => {
                    const nodeId = chunk.node_id || chunk.id;
                    if (nodeId && window.confirm("删除这个引用片段？")) {
                      void mutations.removeVectorChunk.mutateAsync({ kbName: activeKb, nodeId });
                    }
                  },
                }}
                upload={{
                  bases,
                  files: uploadFiles,
                  uploading: mutations.upload.isPending,
                  error: mutations.upload.error,
                  onKbChange: setSelectedKb,
                  onFilesChange: setUploadFiles,
                  onSubmit: uploadToKb,
                  onRecover: () => navigateToWorkspace("recovery"),
                }}
                settings={{
                  activeConfig,
                  configFormKey,
                  saving: mutations.updateConfig.isPending,
                  onSubmit: saveKbConfig,
                }}
                folders={{
                  folderPath,
                  folders: linkedFolders.data ?? [],
                  linking: mutations.linkFolder.isPending,
                  syncing: mutations.syncFolder.isPending,
                  unlinking: mutations.unlinkFolder.isPending,
                  onFolderPathChange: setFolderPath,
                  onLink: linkFolder,
                  onSync: (folderId) => void syncFolder(folderId),
                  onUnlink: (folderId) => {
                    if (activeKb) void mutations.unlinkFolder.mutateAsync({ kbName: activeKb, folderId });
                  },
                }}
                progress={{
                  progressStage,
                  progressMessage,
                  progressPercent,
                  wsStatus,
                  taskMilestones,
                  taskLogs,
                  taskStatus: taskStatus.data ?? null,
                  taskStatusLoading: taskStatus.isLoading || taskStatus.isFetching,
                  clearing: mutations.clearProgress.isPending,
                  onClear: () => void clearActiveProgress(),
                }}
                  onNavigate={navigateToWorkspace}
                  onRecoveryAction={handleRecoveryAction}
                />
              </Suspense>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

function KnowledgeWorkspaceLoading({ title, description }: { title: string; description: string }) {
  return (
    <section className="rounded-lg border border-line bg-white/90 p-5">
      <div className="flex flex-col gap-2">
        <span className="text-sm font-semibold text-ink">{title}</span>
        <span className="text-sm leading-6 text-slate-500">{description}</span>
      </div>
      <div className="mt-4 space-y-3">
        <span className="block h-3 w-56 max-w-full rounded bg-slate-100" />
        <span className="block h-20 rounded bg-slate-100/80" />
        <span className="block h-20 rounded bg-slate-100/60" />
      </div>
    </section>
  );
}

function Header({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <section className="dt-page-header dt-page-header-accent-blue px-3.5 py-3.5">
      <p className="text-xs font-semibold text-steel">{eyebrow}</p>
      <h1 className="mt-1 text-xl font-semibold leading-tight text-ink">
        {title}
      </h1>
      <p className="mt-2 max-w-2xl text-xs leading-5 text-slate-600">{description}</p>
    </section>
  );
}

function knowledgeRouteStateFromPath(pathname: string): { view: KnowledgeView; workspace: KnowledgeWorkspace } {
  const workspaceSlug = pathname.split("/").filter(Boolean)[1] || "";
  if (workspaceSlug === "create") {
    return { view: "create", workspace: "overview" };
  }
  if (isKnowledgeWorkspaceId(workspaceSlug)) {
    return { view: "browse", workspace: workspaceSlug };
  }
  return { view: "browse", workspace: "overview" };
}

function knowledgeSearch(kbName: string, taskId?: string | null) {
  return {
    ...(kbName ? { kb: kbName } : {}),
    ...(taskId ? { task: taskId } : {}),
  };
}

function knowledgeBaseNameFromSearch(search: unknown) {
  return (
    searchParamValue(search, "kb") ||
    searchParamValue(search, "knowledge_base") ||
    searchParamValue(search, "knowledge_bases").split(",")[0]?.trim() ||
    ""
  );
}

function searchParamValue(search: unknown, key: string) {
  if (typeof search === "string") {
    return new URLSearchParams(search.startsWith("?") ? search : `?${search}`).get(key)?.trim() ?? "";
  }
  if (!search || typeof search !== "object" || !(key in search)) return "";
  const value = (search as Record<string, unknown>)[key];
  if (Array.isArray(value)) return String(value[0] ?? "").trim();
  return value == null ? "" : String(value).trim();
}
