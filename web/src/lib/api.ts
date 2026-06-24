import type {
  CoWriterResult,
  DashboardActivity,
  DashboardActivityDetail,
  AgentConfigMap,
  GuideHealth,
  GuideSessionSummary,
  GuidePages,
  GuideSessionDetail,
  GuideV2Session,
  GuideV2LearnerMemory,
  GuideV2SessionSummary,
  GuideV2Task,
  GuideV2Artifact,
  GuideV2CourseTemplate,
  GuideV2CoachBriefing,
  GuideV2CoursePackage,
  GuideV2Diagnostic,
  GuideV2DiagnosticAnswer,
  GuideV2DiagnosticSubmitResult,
  GuideV2Evaluation,
  GuideV2LearningTimeline,
  GuideV2MistakeReview,
  GuideV2LearningReport,
  GuideV2ProfileDialogue,
  GuideV2ProfileDialogueResult,
  GuideV2QuizSubmitResult,
  GuideV2ResourceRecommendation,
  GuideV2ResourceType,
  GuideV2StudyPlan,
  GuideV2TaskCompletionResult,
  GuideResourceAgentStep,
  KnowledgeBase,
  KnowledgeBaseDetail,
  KnowledgeDocumentDeleteResult,
  KnowledgeDocumentPreview,
  KnowledgeDocumentsResponse,
  KnowledgeVectorChunksResponse,
  KnowledgeConfig,
  KnowledgeConfigRegistry,
  KnowledgeConfigResponse,
  KnowledgeDefaultResponse,
  KnowledgeRegistryAudit,
  KnowledgeRegistryPruneResult,
  RagEvaluationRunRequest,
  RagEvaluationLatestResponse,
  RagEvaluationReport,
  RagPreflight,
  RagSearchTestRequest,
  RagSearchTestResult,
  KnowledgeHealth,
  KnowledgeProgress,
  KnowledgeTaskStatusResponse,
  KnowledgeTaskResult,
  LinkedFolder,
  LearnerEvidenceEvent,
  LearnerEvidenceListResponse,
  LearningEffectConceptListResponse,
  LearningEffectNextActionsResponse,
  LearningEffectReport,
  CompleteLearningEffectActionResponse,
  LearnerProfileCalibrationRequest,
  LearnerProfileCalibrationResponse,
  LearnerProfileEvidencePreviewResponse,
  LearnerProfileResetResponse,
  LearnerProfileSnapshot,
  MemoryFile,
  MemorySnapshot,
  NotebookDetail,
  NotebookHealth,
  NotebookRecord,
  NotebookReference,
  NotebookSummary,
  PluginsList,
  PluginToolExecutionResult,
  OcrPreviewResponse,
  QuestionCategory,
  QuestionNotebookEntry,
  QuizResultItem,
  RagDiagnostic,
  RagProvider,
  SessionDetail,
  SettingsResponse,
  SidebarSettings,
  SessionSummary,
  RuntimeTopology,
  SetupTourReopenResponse,
  SetupTourStatus,
  SpeechEvaluateResponse,
  SpeechTranscribeResponse,
  SystemStatus,
  SystemTestResponse,
  ThemeOption,
  VisionAnalyzeResponse,
} from "@/lib/types";
import {
  ApiError,
  apiUrl,
  appendApiKeyQuery,
  authorizedFetch,
  fetchJson,
  readSseResponse,
  wsUrl,
} from "@/lib/http";
import type { SseEventHandler } from "@/lib/http";

export {
  ApiError,
  apiUrl,
  authenticatedResourceUrl,
  fetchJson,
  getApiBase,
  readSseResponse,
  wsUrl,
} from "@/lib/http";
export type { SseEventHandler } from "@/lib/http";
export * from "@/lib/api/sparkbot";

export function unifiedRuntimeSocketUrl() {
  return wsUrl("/api/v1/ws");
}

export function guideSocketUrl(sessionId: string) {
  return wsUrl(`/api/v1/guide/ws/${encodeURIComponent(sessionId)}`);
}

export function questionGenerateSocketUrl() {
  return wsUrl("/api/v1/question/generate");
}

export function questionMimicSocketUrl() {
  return wsUrl("/api/v1/question/mimic");
}

export function visionSolveSocketUrl() {
  return wsUrl("/api/v1/vision/solve");
}

function jsonBody(payload: unknown): RequestInit {
  return {
    method: "POST",
    body: JSON.stringify(payload),
  };
}

export function getSystemStatus() {
  return fetchJson<SystemStatus>("/api/v1/system/status");
}

export function getRuntimeTopology() {
  return fetchJson<RuntimeTopology>("/api/v1/system/runtime-topology");
}

export function listAgentConfigs() {
  return fetchJson<AgentConfigMap>("/api/v1/agent-config/agents");
}

export function getAgentConfig(agentType: string) {
  return fetchJson<AgentConfigMap[string]>(`/api/v1/agent-config/agents/${encodeURIComponent(agentType)}`);
}

export function analyzeVisionImage(input: {
  question: string;
  image_base64?: string | null;
  image_url?: string | null;
  session_id?: string | null;
}) {
  return fetchJson<VisionAnalyzeResponse>("/api/v1/vision/analyze", jsonBody(input));
}

export function getSettings() {
  return fetchJson<SettingsResponse>("/api/v1/settings");
}

export function getSettingsCatalog() {
  return fetchJson<{ catalog: SettingsResponse["catalog"] }>("/api/v1/settings/catalog");
}

export function getSetupTourStatus() {
  return fetchJson<SetupTourStatus>("/api/v1/settings/tour/status");
}

export function updateSettingsCatalog(catalog: SettingsResponse["catalog"]) {
  return fetchJson<{ catalog: SettingsResponse["catalog"] }>("/api/v1/settings/catalog", {
    method: "PUT",
    body: JSON.stringify({ catalog }),
  });
}

export function applySettingsCatalog(catalog: SettingsResponse["catalog"]) {
  return fetchJson<{ message: string; catalog: SettingsResponse["catalog"]; env: Record<string, string> }>(
    "/api/v1/settings/apply",
    jsonBody({ catalog }),
  );
}

export function completeSetupTour(input: {
  catalog: SettingsResponse["catalog"];
  test_results?: Record<string, string>;
}) {
  return fetchJson<{ status: string; message: string; launch_at?: number; redirect_at?: number; env: Record<string, string> }>(
    "/api/v1/settings/tour/complete",
    jsonBody(input),
  );
}

export function reopenSetupTour() {
  return fetchJson<SetupTourReopenResponse>("/api/v1/settings/tour/reopen", { method: "POST" });
}

export type SettingsServiceId = "llm" | "embedding" | "search" | "ocr" | "tts" | "asr" | "speech_eval";

export function startSettingsServiceTest(input: {
  service: SettingsServiceId;
  catalog?: SettingsResponse["catalog"];
}) {
  return fetchJson<{ run_id: string }>(
    `/api/v1/settings/tests/${input.service}/start`,
    jsonBody(input.catalog ? { catalog: input.catalog } : {}),
  );
}

export function openSettingsServiceTestEvents(input: { service: SettingsServiceId; runId: string }) {
  return new EventSource(appendApiKeyQuery(apiUrl(`/api/v1/settings/tests/${input.service}/${input.runId}/events`)));
}

export function cancelSettingsServiceTest(input: { service: SettingsServiceId; runId: string }) {
  return fetchJson<Record<string, unknown>>(`/api/v1/settings/tests/${input.service}/${input.runId}/cancel`, {
    method: "POST",
  });
}

export function updateUiSettings(input: Partial<SettingsResponse["ui"]>) {
  return fetchJson<SettingsResponse["ui"]>("/api/v1/settings/ui", {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export function listThemes() {
  return fetchJson<{ themes: ThemeOption[] }>("/api/v1/settings/themes");
}

export function getSidebarSettings() {
  return fetchJson<SidebarSettings>("/api/v1/settings/sidebar");
}

export function updateTheme(theme: SettingsResponse["ui"]["theme"]) {
  return fetchJson<{ theme: SettingsResponse["ui"]["theme"] }>("/api/v1/settings/theme", {
    method: "PUT",
    body: JSON.stringify({ theme }),
  });
}

export function updateLanguage(language: SettingsResponse["ui"]["language"]) {
  return fetchJson<{ language: SettingsResponse["ui"]["language"] }>("/api/v1/settings/language", {
    method: "PUT",
    body: JSON.stringify({ language }),
  });
}

export function updateSidebarDescription(description: string) {
  return fetchJson<{ description: string }>("/api/v1/settings/sidebar/description", {
    method: "PUT",
    body: JSON.stringify({ description }),
  });
}

export function updateSidebarNavOrder(navOrder: SidebarSettings["nav_order"]) {
  return fetchJson<{ nav_order: SidebarSettings["nav_order"] }>("/api/v1/settings/sidebar/nav-order", {
    method: "PUT",
    body: JSON.stringify({ nav_order: navOrder }),
  });
}

export function resetUiSettings() {
  return fetchJson<SettingsResponse["ui"]>("/api/v1/settings/reset", { method: "POST" });
}

export async function listSessions() {
  const data = await fetchJson<{ sessions: SessionSummary[] }>("/api/v1/sessions?limit=30&offset=0");
  return data.sessions ?? [];
}

export function getSession(sessionId: string) {
  return fetchJson<SessionDetail>(`/api/v1/sessions/${encodeURIComponent(sessionId)}`);
}

export function updateSessionTitle(input: { sessionId: string; title: string }) {
  return fetchJson<{ session: SessionSummary }>(`/api/v1/sessions/${encodeURIComponent(input.sessionId)}`, {
    method: "PATCH",
    body: JSON.stringify({ title: input.title }),
  });
}

export function deleteSession(sessionId: string) {
  return fetchJson<{ deleted: boolean; session_id: string }>(`/api/v1/sessions/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
  });
}

export function recordQuizResults(input: { sessionId: string; answers: QuizResultItem[] }) {
  return fetchJson<{ recorded: boolean; session_id: string; answer_count: number; notebook_count: number }>(
    `/api/v1/sessions/${encodeURIComponent(input.sessionId)}/quiz-results`,
    jsonBody({ answers: input.answers }),
  );
}

export async function listKnowledgeBases() {
  const data = await fetchJson<KnowledgeBase[] | { knowledge_bases?: KnowledgeBase[] }>(
    "/api/v1/knowledge/list",
  );
  return Array.isArray(data) ? data : data.knowledge_bases ?? [];
}

export function getKnowledgeBaseDetail(kbName: string) {
  return fetchJson<KnowledgeBaseDetail>(`/api/v1/knowledge/${encodeURIComponent(kbName)}`);
}

export function listKnowledgeDocuments(input: { kbName: string; includeVectors?: boolean }) {
  const include = input.includeVectors === false ? "?include_vectors=false" : "";
  return fetchJson<KnowledgeDocumentsResponse>(`/api/v1/knowledge/${encodeURIComponent(input.kbName)}/documents${include}`);
}

export function previewKnowledgeDocument(input: { kbName: string; documentId: string; forceRefresh?: boolean }) {
  const query = input.forceRefresh ? "?force_refresh=true" : "";
  return fetchJson<KnowledgeDocumentPreview>(
    `/api/v1/knowledge/${encodeURIComponent(input.kbName)}/documents/${encodeURIComponent(input.documentId)}/preview${query}`,
  );
}

export function listKnowledgeVectorChunks(input: {
  kbName: string;
  documentId?: string | null;
  limit?: number;
  offset?: number;
}) {
  const params = new URLSearchParams();
  if (input.documentId) params.set("document_id", input.documentId);
  if (input.limit) params.set("limit", String(input.limit));
  if (input.offset) params.set("offset", String(input.offset));
  const query = params.toString() ? `?${params.toString()}` : "";
  return fetchJson<KnowledgeVectorChunksResponse>(`/api/v1/knowledge/${encodeURIComponent(input.kbName)}/vectors${query}`);
}

export function deleteKnowledgeDocument(input: {
  kbName: string;
  documentId: string;
  removeRaw?: boolean;
  removeVectors?: boolean;
}) {
  return fetchJson<KnowledgeDocumentDeleteResult>(
    `/api/v1/knowledge/${encodeURIComponent(input.kbName)}/documents/${encodeURIComponent(input.documentId)}`,
    {
      method: "DELETE",
      body: JSON.stringify({
        remove_raw: input.removeRaw ?? true,
        remove_vectors: input.removeVectors ?? true,
      }),
    },
  );
}

export function deleteKnowledgeVectorChunk(input: { kbName: string; nodeId: string }) {
  return fetchJson<{ kb_name: string; node_id: string; deleted_vectors?: number }>(
    `/api/v1/knowledge/${encodeURIComponent(input.kbName)}/vectors/${encodeURIComponent(input.nodeId)}`,
    { method: "DELETE" },
  );
}

export function getKnowledgeHealth() {
  return fetchJson<KnowledgeHealth>("/api/v1/knowledge/health");
}

export function getKnowledgeDiagnostics(input?: { kbName?: string | null; checkConnection?: boolean }) {
  const query = input?.checkConnection === false ? "?check_connection=false" : "";
  if (input?.kbName) {
    return fetchJson<RagDiagnostic>(`/api/v1/knowledge/${encodeURIComponent(input.kbName)}/diagnostics${query}`);
  }
  return fetchJson<RagDiagnostic>(`/api/v1/knowledge/diagnostics${query}`);
}

export function getKnowledgePreflight(input?: {
  kbName?: string | null;
  checkConnection?: boolean;
  checkDocker?: boolean;
}) {
  const params = new URLSearchParams();
  if (input?.checkConnection === false) params.set("check_connection", "false");
  if (input?.checkDocker === false) params.set("check_docker", "false");
  const query = params.toString() ? `?${params.toString()}` : "";
  if (input?.kbName) {
    return fetchJson<RagPreflight>(`/api/v1/knowledge/${encodeURIComponent(input.kbName)}/preflight${query}`);
  }
  return fetchJson<RagPreflight>(`/api/v1/knowledge/preflight${query}`);
}

export function getLatestRagEvaluation(kbName: string) {
  return fetchJson<RagEvaluationLatestResponse>(`/api/v1/knowledge/${encodeURIComponent(kbName)}/rag-eval/latest`);
}

export function runRagEvaluation(input: RagEvaluationRunRequest) {
  return fetchJson<RagEvaluationReport>(
    `/api/v1/knowledge/${encodeURIComponent(input.kbName)}/rag-eval`,
    jsonBody({
      cases: input.cases,
      preset: input.preset || "default",
      provider: input.provider || undefined,
      baseline_strategy: input.baselineStrategy || "baseline",
    }),
  );
}

export function testKnowledgeRagSearch(input: RagSearchTestRequest) {
  return fetchJson<RagSearchTestResult>(
    `/api/v1/knowledge/${encodeURIComponent(input.kbName)}/rag-test`,
    jsonBody({
      query: input.query,
      provider: input.provider || undefined,
      retrieval_profile: input.retrievalProfile || undefined,
      retrieval_mode: input.retrievalMode || undefined,
      top_k: input.topK ?? 5,
      candidate_top_k: input.candidateTopK ?? undefined,
      reranker: input.reranker || undefined,
      query_transform: input.queryTransform || undefined,
      agentic_rag: input.agenticRag ?? undefined,
      agentic_max_context_chars: input.agenticMaxContextChars ?? undefined,
      agentic_max_sources: input.agenticMaxSources ?? undefined,
      agentic_min_sources: input.agenticMinSources ?? undefined,
      agentic_min_coverage_ratio: input.agenticMinCoverageRatio ?? undefined,
      agentic_min_relevant_coverage_ratio: input.agenticMinRelevantCoverageRatio ?? undefined,
      agentic_min_context_chars: input.agenticMinContextChars ?? undefined,
      agentic_min_score: input.agenticMinScore ?? undefined,
      max_context_chars: input.maxContextChars ?? 5000,
    }),
  );
}

export function getDefaultKnowledgeBase() {
  return fetchJson<KnowledgeDefaultResponse>("/api/v1/knowledge/default");
}

export async function listRagProviders() {
  const data = await fetchJson<
    RagProvider[] | { providers?: RagProvider[] | Record<string, RagProvider | string>; default_provider?: string }
  >("/api/v1/knowledge/rag-providers");
  if (Array.isArray(data)) {
    return data.map((provider) => ({
      ...provider,
      label: provider.label || provider.name,
      name: provider.id || provider.name,
    }));
  }
  const providers = data.providers;
  if (Array.isArray(providers)) {
    return providers.map((provider) => ({
      ...provider,
      label: provider.label || provider.name,
      name: provider.id || provider.name,
      is_default: provider.is_default || provider.id === data.default_provider || provider.name === data.default_provider,
    }));
  }
  return Object.entries(providers ?? {}).map(([name, value]) => ({
    name,
    label: typeof value === "string" ? value : value.label,
    description: typeof value === "string" ? "" : value.description,
    available: typeof value === "string" ? true : value.available,
    is_default: name === data.default_provider,
  }));
}

export function listPlugins() {
  return fetchJson<PluginsList>("/api/v1/plugins/list");
}

export function streamPluginToolExecution(input: {
  toolName: string;
  params: Record<string, unknown>;
  onEvent: SseEventHandler;
}) {
  return authorizedFetch(apiUrl(`/api/v1/plugins/tools/${encodeURIComponent(input.toolName)}/execute-stream`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ params: input.params }),
  }).then((response) => readSseResponse(response, input.onEvent, "Tool stream failed"));
}

export function executePluginTool(input: { toolName: string; params: Record<string, unknown> }) {
  return fetchJson<PluginToolExecutionResult>(
    `/api/v1/plugins/tools/${encodeURIComponent(input.toolName)}/execute`,
    jsonBody({ params: input.params }),
  );
}

export function streamPluginCapabilityExecution(input: {
  capabilityName: string;
  content: string;
  tools: string[];
  knowledgeBases: string[];
  language?: string;
  config?: Record<string, unknown>;
  attachments?: unknown[];
  onEvent: SseEventHandler;
}) {
  return authorizedFetch(apiUrl(`/api/v1/plugins/capabilities/${encodeURIComponent(input.capabilityName)}/execute-stream`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      content: input.content,
      tools: input.tools,
      knowledge_bases: input.knowledgeBases,
      language: input.language || "zh",
      config: input.config || {},
      attachments: input.attachments || [],
    }),
  }).then((response) => readSseResponse(response, input.onEvent, "Capability stream failed"));
}

export function listDashboardActivities(limit = 20) {
  return fetchJson<DashboardActivity[]>(`/api/v1/dashboard/recent?limit=${limit}`);
}

export function getDashboardActivity(entryId: string) {
  return fetchJson<DashboardActivityDetail>(`/api/v1/dashboard/${encodeURIComponent(entryId)}`);
}

export async function createKnowledgeBase(input: { name: string; files: File[]; ragProvider?: string }) {
  const form = new FormData();
  form.append("name", input.name);
  if (input.ragProvider) form.append("rag_provider", input.ragProvider);
  input.files.forEach((file) => form.append("files", file));
  return fetchJson<KnowledgeTaskResult>("/api/v1/knowledge/create", { method: "POST", body: form });
}

export async function uploadKnowledgeFiles(input: { kbName: string; files: File[]; ragProvider?: string }) {
  const form = new FormData();
  if (input.ragProvider) form.append("rag_provider", input.ragProvider);
  input.files.forEach((file) => form.append("files", file));
  return fetchJson<KnowledgeTaskResult>(`/api/v1/knowledge/${encodeURIComponent(input.kbName)}/upload`, {
    method: "POST",
    body: form,
  });
}

export function reindexKnowledgeBase(input: { kbName: string; ragProvider?: string; backup?: boolean }) {
  return fetchJson<KnowledgeTaskResult>(`/api/v1/knowledge/${encodeURIComponent(input.kbName)}/reindex`, {
    method: "POST",
    body: JSON.stringify({
      rag_provider: input.ragProvider,
      backup: input.backup ?? true,
    }),
  });
}

export function setDefaultKnowledgeBase(kbName: string) {
  return fetchJson<{ success?: boolean; message?: string }>(`/api/v1/knowledge/default/${encodeURIComponent(kbName)}`, {
    method: "PUT",
  });
}

export function deleteKnowledgeBase(kbName: string) {
  return fetchJson<{ success?: boolean; message?: string }>(`/api/v1/knowledge/${encodeURIComponent(kbName)}`, {
    method: "DELETE",
  });
}

export function getKnowledgeProgress(kbName: string) {
  return fetchJson<KnowledgeProgress>(`/api/v1/knowledge/${encodeURIComponent(kbName)}/progress`);
}

export function clearKnowledgeProgress(kbName: string) {
  return fetchJson<{ status: string; message?: string }>(`/api/v1/knowledge/${encodeURIComponent(kbName)}/progress/clear`, {
    method: "POST",
  });
}

export function getKnowledgeConfig(kbName: string) {
  return fetchJson<KnowledgeConfigResponse>(`/api/v1/knowledge/${encodeURIComponent(kbName)}/config`);
}

export function listKnowledgeConfigs() {
  return fetchJson<KnowledgeConfigRegistry>("/api/v1/knowledge/configs");
}

export function auditKnowledgeConfigs() {
  return fetchJson<KnowledgeRegistryAudit>("/api/v1/knowledge/configs/audit");
}

export function updateKnowledgeConfig(input: { kbName: string; config: Partial<KnowledgeConfig> }) {
  return fetchJson<KnowledgeConfigResponse>(`/api/v1/knowledge/${encodeURIComponent(input.kbName)}/config`, {
    method: "PUT",
    body: JSON.stringify(input.config),
  });
}

export function syncKnowledgeConfigs() {
  return fetchJson<{ status: string; message?: string }>("/api/v1/knowledge/configs/sync", {
    method: "POST",
  });
}

export function pruneMissingKnowledgeConfigs(input?: { dryRun?: boolean }) {
  const suffix = input?.dryRun ? "?dry_run=true" : "";
  return fetchJson<KnowledgeRegistryPruneResult>(`/api/v1/knowledge/configs/prune-missing${suffix}`, {
    method: "POST",
  });
}

export function openKnowledgeTaskStream(taskId: string) {
  return new EventSource(appendApiKeyQuery(apiUrl(`/api/v1/knowledge/tasks/${encodeURIComponent(taskId)}/stream`)));
}

export function getKnowledgeTaskStatus(taskId: string) {
  return fetchJson<KnowledgeTaskStatusResponse>(`/api/v1/knowledge/tasks/${encodeURIComponent(taskId)}`);
}

export function knowledgeProgressSocketUrl(input: { kbName: string; taskId: string }) {
  return wsUrl(
    `/api/v1/knowledge/${encodeURIComponent(input.kbName)}/progress/ws?task_id=${encodeURIComponent(input.taskId)}`,
  );
}

export function listLinkedFolders(kbName: string) {
  return fetchJson<LinkedFolder[]>(`/api/v1/knowledge/${encodeURIComponent(kbName)}/linked-folders`);
}

export function linkKnowledgeFolder(input: { kbName: string; folderPath: string }) {
  return fetchJson<LinkedFolder>(`/api/v1/knowledge/${encodeURIComponent(input.kbName)}/link-folder`, {
    method: "POST",
    body: JSON.stringify({ folder_path: input.folderPath }),
  });
}

export function unlinkKnowledgeFolder(input: { kbName: string; folderId: string }) {
  return fetchJson<{ message: string; folder_id: string }>(
    `/api/v1/knowledge/${encodeURIComponent(input.kbName)}/linked-folders/${encodeURIComponent(input.folderId)}`,
    { method: "DELETE" },
  );
}

export function syncKnowledgeFolder(input: { kbName: string; folderId: string }) {
  return fetchJson<KnowledgeTaskResult & { file_count?: number }>(
    `/api/v1/knowledge/${encodeURIComponent(input.kbName)}/sync-folder/${encodeURIComponent(input.folderId)}`,
    { method: "POST" },
  );
}

export function getMemory() {
  return fetchJson<MemorySnapshot>("/api/v1/memory");
}

export function updateMemory(input: { file: MemoryFile; content: string }) {
  return fetchJson<MemorySnapshot>("/api/v1/memory", {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export function refreshMemory(input: { sessionId?: string | null; language?: string }) {
  return fetchJson<MemorySnapshot>(
    "/api/v1/memory/refresh",
    jsonBody({
      session_id: input.sessionId || null,
      language: input.language || "zh",
    }),
  );
}

export function clearMemory(file?: MemoryFile | null) {
  return fetchJson<MemorySnapshot>("/api/v1/memory/clear", jsonBody({ file: file || null }));
}

export function getLearnerProfile() {
  return fetchJson<LearnerProfileSnapshot>("/api/v1/learner-profile");
}

export function refreshLearnerProfile(input?: { includeSources?: string[] | null; force?: boolean }) {
  return fetchJson<LearnerProfileSnapshot>(
    "/api/v1/learner-profile/refresh",
    jsonBody({
      include_sources: input?.includeSources || null,
      force: input?.force ?? true,
    }),
  );
}

export function resetLearnerProfile(input?: {
  clearMemory?: boolean;
  clearEvidence?: boolean;
  clearGuideState?: boolean;
  clearChatHistory?: boolean;
  clearQuestionNotebook?: boolean;
  clearSavedNotebookRecords?: boolean;
  clearProfileCache?: boolean;
}) {
  return fetchJson<LearnerProfileResetResponse>(
    "/api/v1/learner-profile/reset",
    jsonBody({
      clear_memory: input?.clearMemory ?? true,
      clear_evidence: input?.clearEvidence ?? true,
      clear_guide_state: input?.clearGuideState ?? true,
      clear_chat_history: input?.clearChatHistory ?? true,
      clear_question_notebook: input?.clearQuestionNotebook ?? true,
      clear_saved_notebook_records: input?.clearSavedNotebookRecords ?? true,
      clear_profile_cache: input?.clearProfileCache ?? true,
    }),
  );
}

export function getLearnerProfileEvidencePreview(input?: { source?: string | null; limit?: number }) {
  const params = new URLSearchParams();
  if (input?.source) params.set("source", input.source);
  if (input?.limit) params.set("limit", String(input.limit));
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return fetchJson<LearnerProfileEvidencePreviewResponse>(`/api/v1/learner-profile/evidence-preview${suffix}`);
}

export function calibrateLearnerProfile(input: LearnerProfileCalibrationRequest) {
  return fetchJson<LearnerProfileCalibrationResponse>(
    "/api/v1/learner-profile/calibrations",
    jsonBody({
      action: input.action,
      claim_type: input.claim_type,
      value: input.value,
      corrected_value: input.corrected_value || "",
      note: input.note || "",
      source_id: input.source_id || "",
    }),
  );
}

export function listLearnerEvidence(input?: {
  source?: string | null;
  verb?: string | null;
  objectType?: string | null;
  limit?: number;
  offset?: number;
}) {
  const params = new URLSearchParams();
  if (input?.source) params.set("source", input.source);
  if (input?.verb) params.set("verb", input.verb);
  if (input?.objectType) params.set("object_type", input.objectType);
  if (input?.limit) params.set("limit", String(input.limit));
  if (input?.offset) params.set("offset", String(input.offset));
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return fetchJson<LearnerEvidenceListResponse>(`/api/v1/learner-profile/evidence${suffix}`);
}

export function appendLearnerEvidence(input: Partial<LearnerEvidenceEvent>) {
  return fetchJson<{ event: LearnerEvidenceEvent }>("/api/v1/learner-profile/evidence", jsonBody(input));
}

export function appendLearnerEvidenceBatch(input: {
  events: Array<Partial<LearnerEvidenceEvent>>;
  dedupe?: boolean;
}) {
  return fetchJson<{ added: number; skipped: number; events: LearnerEvidenceEvent[] }>(
    "/api/v1/learner-profile/evidence/batch",
    jsonBody({
      events: input.events,
      dedupe: input.dedupe ?? true,
    }),
  );
}

export function rebuildLearnerEvidence(input?: { clear?: boolean }) {
  return fetchJson<{ added: number; skipped: number; events: LearnerEvidenceEvent[] }>(
    "/api/v1/learner-profile/evidence/rebuild",
    jsonBody({ clear: input?.clear ?? false }),
  );
}

export type LearningEffectEventInput = Partial<LearnerEvidenceEvent> & {
  concept_ids?: string[];
  result?: Record<string, unknown>;
  signals?: Record<string, unknown>;
  };

export function getLearningEffectHealth() {
  return fetchJson<Record<string, unknown>>("/api/v1/learning-effect/health");
}

export function getLearningEffectReport(input?: { courseId?: string | null; window?: string }) {
  const params = new URLSearchParams();
  if (input?.courseId) params.set("course_id", input.courseId);
  if (input?.window) params.set("window", input.window);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return fetchJson<LearningEffectReport>(`/api/v1/learning-effect/report${suffix}`);
}

export function getLearningEffectDemoSummary(input?: { courseId?: string | null; window?: string }) {
  const params = new URLSearchParams();
  if (input?.courseId) params.set("course_id", input.courseId);
  if (input?.window) params.set("window", input.window);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return fetchJson<Record<string, unknown>>(`/api/v1/learning-effect/demo-summary${suffix}`);
}

export function listLearningEffectConcepts(input?: { courseId?: string | null; window?: string; limit?: number }) {
  const params = new URLSearchParams();
  if (input?.courseId) params.set("course_id", input.courseId);
  if (input?.window) params.set("window", input.window);
  if (input?.limit) params.set("limit", String(input.limit));
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return fetchJson<LearningEffectConceptListResponse>(`/api/v1/learning-effect/concepts${suffix}`);
}

export function listLearningEffectNextActions(input?: { courseId?: string | null; window?: string; limit?: number }) {
  const params = new URLSearchParams();
  if (input?.courseId) params.set("course_id", input.courseId);
  if (input?.window) params.set("window", input.window);
  if (input?.limit) params.set("limit", String(input.limit));
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return fetchJson<LearningEffectNextActionsResponse>(`/api/v1/learning-effect/next-actions${suffix}`);
}

export function appendLearningEffectEvent(input: LearningEffectEventInput) {
  return fetchJson<{ event: LearnerEvidenceEvent }>("/api/v1/learning-effect/events", jsonBody(input));
}

export function completeLearningEffectAction(input: {
  actionId: string;
  note?: string;
  score?: number | null;
  courseId?: string | null;
  conceptIds?: string[];
}) {
  return fetchJson<CompleteLearningEffectActionResponse>(
    `/api/v1/learning-effect/actions/${encodeURIComponent(input.actionId)}/complete`,
    jsonBody({
      note: input.note || "",
      score: input.score ?? null,
      course_id: input.courseId || "",
      concept_ids: input.conceptIds || [],
    }),
  );
}

export async function listNotebooks() {
  const data = await fetchJson<{ notebooks: NotebookSummary[]; total: number }>("/api/v1/notebook/list");
  return data.notebooks ?? [];
}

export async function getNotebookStats() {
  return fetchJson<Record<string, unknown>>("/api/v1/notebook/statistics");
}

export function getNotebookHealth() {
  return fetchJson<NotebookHealth>("/api/v1/notebook/health");
}

export function createNotebook(input: { name: string; description?: string; color?: string; icon?: string }) {
  return fetchJson<{ success: boolean; notebook: NotebookSummary }>("/api/v1/notebook/create", jsonBody(input));
}

export function getNotebook(notebookId: string) {
  return fetchJson<NotebookDetail>(`/api/v1/notebook/${encodeURIComponent(notebookId)}`);
}

export function updateNotebook(input: {
  notebookId: string;
  name?: string;
  description?: string;
  color?: string;
  icon?: string;
}) {
  const { notebookId, ...payload } = input;
  return fetchJson<{ success: boolean; notebook: NotebookSummary }>(`/api/v1/notebook/${encodeURIComponent(notebookId)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function deleteNotebook(notebookId: string) {
  return fetchJson<{ success: boolean; message?: string }>(`/api/v1/notebook/${encodeURIComponent(notebookId)}`, {
    method: "DELETE",
  });
}

export type NotebookRecordInput = {
  notebook_ids: string[];
  record_type: NotebookRecord["record_type"];
  title: string;
  summary?: string;
  user_query: string;
  output: string;
  metadata?: Record<string, unknown>;
  kb_name?: string | null;
};

export function addNotebookRecord(input: NotebookRecordInput) {
  return fetchJson<{ success: boolean; summary?: string; record?: NotebookRecord; added_to_notebooks?: string[] }>(
    "/api/v1/notebook/add_record",
    jsonBody(input),
  );
}

export async function addNotebookRecordWithSummary(input: NotebookRecordInput & { onEvent?: SseEventHandler }) {
  const { onEvent, ...payload } = input;
  let finalResult: { success: boolean; summary?: string; record?: NotebookRecord; added_to_notebooks?: string[] } | null = null;
  const chunks: string[] = [];
  const response = await authorizedFetch(apiUrl("/api/v1/notebook/add_record_with_summary"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await readSseResponse(
    response,
    (event, data) => {
      onEvent?.(event, data);
      if (data.type === "summary_chunk" && typeof data.content === "string") {
        chunks.push(data.content);
      }
      if (data.type === "result") {
        finalResult = data as typeof finalResult;
      }
      if (data.type === "error") {
        throw new ApiError(String(data.detail || "Notebook summary failed"), response.status);
      }
    },
    "Notebook summary stream failed",
  );
  if (finalResult) return finalResult;
  return { success: true, summary: chunks.join("") };
}

export function updateNotebookRecord(input: {
  notebookId: string;
  recordId: string;
  title?: string;
  summary?: string;
  user_query?: string;
  output?: string;
  metadata?: Record<string, unknown>;
  kb_name?: string | null;
}) {
  const { notebookId, recordId, ...payload } = input;
  return fetchJson<{ success: boolean; record: NotebookRecord }>(
    `/api/v1/notebook/${encodeURIComponent(notebookId)}/records/${encodeURIComponent(recordId)}`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
    },
  );
}

export function deleteNotebookRecord(input: { notebookId: string; recordId: string }) {
  return fetchJson<{ success: boolean; message?: string }>(
    `/api/v1/notebook/${encodeURIComponent(input.notebookId)}/records/${encodeURIComponent(input.recordId)}`,
    { method: "DELETE" },
  );
}

export async function listQuestionEntries() {
  const data = await fetchJson<{ items: QuestionNotebookEntry[]; total: number }>(
    "/api/v1/question-notebook/entries?limit=30&offset=0",
  );
  return data.items ?? [];
}

export function getQuestionEntry(entryId: number) {
  return fetchJson<QuestionNotebookEntry>(`/api/v1/question-notebook/entries/${entryId}`);
}

export function listQuestionCategories() {
  return fetchJson<QuestionCategory[]>("/api/v1/question-notebook/categories");
}

export function createQuestionCategory(name: string) {
  return fetchJson<QuestionCategory>("/api/v1/question-notebook/categories", jsonBody({ name }));
}

export function updateQuestionEntry(input: { entryId: number; bookmarked?: boolean; followup_session_id?: string | null }) {
  const { entryId, ...payload } = input;
  return fetchJson<{ updated: boolean; id: number }>(`/api/v1/question-notebook/entries/${entryId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function lookupQuestionEntry(input: { sessionId: string; questionId: string }) {
  const params = new URLSearchParams({ session_id: input.sessionId, question_id: input.questionId });
  return fetchJson<QuestionNotebookEntry>(`/api/v1/question-notebook/entries/lookup/by-question?${params.toString()}`);
}

export function upsertQuestionEntry(input: {
  session_id: string;
  question_id: string;
  question: string;
  question_type?: string;
  options?: Record<string, string>;
  correct_answer?: string;
  explanation?: string;
  difficulty?: string;
  concepts?: string[];
  knowledge_points?: string[];
  user_answer?: string;
  is_correct?: boolean;
  record_evidence?: boolean;
}) {
  return fetchJson<QuestionNotebookEntry>("/api/v1/question-notebook/entries/upsert", jsonBody(input));
}

export function deleteQuestionEntry(entryId: number) {
  return fetchJson<{ deleted: boolean; id: number }>(`/api/v1/question-notebook/entries/${entryId}`, {
    method: "DELETE",
  });
}

export function renameQuestionCategory(input: { categoryId: number; name: string }) {
  return fetchJson<{ updated: boolean; id: number; name: string }>(
    `/api/v1/question-notebook/categories/${input.categoryId}`,
    {
      method: "PATCH",
      body: JSON.stringify({ name: input.name }),
    },
  );
}

export function deleteQuestionCategory(categoryId: number) {
  return fetchJson<{ deleted: boolean; id: number }>(`/api/v1/question-notebook/categories/${categoryId}`, {
    method: "DELETE",
  });
}

export function addQuestionEntryToCategory(input: { entryId: number; categoryId: number }) {
  return fetchJson<{ added: boolean; entry_id: number; category_id: number }>(
    `/api/v1/question-notebook/entries/${input.entryId}/categories`,
    jsonBody({ category_id: input.categoryId }),
  );
}

export function removeQuestionEntryFromCategory(input: { entryId: number; categoryId: number }) {
  return fetchJson<{ removed: boolean; entry_id: number; category_id: number }>(
    `/api/v1/question-notebook/entries/${input.entryId}/categories/${input.categoryId}`,
    { method: "DELETE" },
  );
}

export function getGuideHealth() {
  return fetchJson<GuideHealth>("/api/v1/guide/health");
}

export async function listGuideSessions() {
  const data = await fetchJson<{ sessions: GuideSessionSummary[] }>("/api/v1/guide/sessions");
  return data.sessions ?? [];
}

export type CreateGuideSessionInput =
  | string
  | {
      userInput: string;
      notebookReferences?: NotebookReference[];
    };

export function createGuideSession(input: CreateGuideSessionInput) {
  const userInput = typeof input === "string" ? input : input.userInput;
  const notebookReferences = typeof input === "string" ? [] : input.notebookReferences ?? [];
  return fetchJson<Record<string, unknown>>(
    "/api/v1/guide/create_session",
    jsonBody({
      user_input: userInput,
      ...(notebookReferences.length ? { notebook_references: notebookReferences } : {}),
    }),
  );
}

export function getGuideSession(sessionId: string) {
  return fetchJson<GuideSessionDetail>(`/api/v1/guide/session/${encodeURIComponent(sessionId)}`);
}

export function startGuideSession(sessionId: string) {
  return fetchJson<Record<string, unknown>>("/api/v1/guide/start", jsonBody({ session_id: sessionId }));
}

export function navigateGuideSession(input: { sessionId: string; knowledgeIndex: number }) {
  return fetchJson<Record<string, unknown>>(
    "/api/v1/guide/navigate",
    jsonBody({ session_id: input.sessionId, knowledge_index: input.knowledgeIndex }),
  );
}

export function completeGuideSession(sessionId: string) {
  return fetchJson<Record<string, unknown>>("/api/v1/guide/complete", jsonBody({ session_id: sessionId }));
}

export function chatGuideSession(input: { sessionId: string; message: string; knowledgeIndex?: number | null }) {
  return fetchJson<Record<string, unknown>>(
    "/api/v1/guide/chat",
    jsonBody({ session_id: input.sessionId, message: input.message, knowledge_index: input.knowledgeIndex ?? null }),
  );
}

export function fixGuideHtml(input: { sessionId: string; bugDescription: string }) {
  return fetchJson<Record<string, unknown>>(
    "/api/v1/guide/fix_html",
    jsonBody({ session_id: input.sessionId, bug_description: input.bugDescription }),
  );
}

export function retryGuidePage(input: { sessionId: string; pageIndex: number }) {
  return fetchJson<Record<string, unknown>>(
    "/api/v1/guide/retry_page",
    jsonBody({ session_id: input.sessionId, page_index: input.pageIndex }),
  );
}

export function resetGuideSession(sessionId: string) {
  return fetchJson<Record<string, unknown>>("/api/v1/guide/reset", jsonBody({ session_id: sessionId }));
}

export function deleteGuideSession(sessionId: string) {
  return fetchJson<Record<string, unknown>>(`/api/v1/guide/session/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
  });
}

export function getGuideHtml(sessionId: string) {
  return fetchJson<{ html: string }>(`/api/v1/guide/session/${encodeURIComponent(sessionId)}/html`);
}

export function getGuidePages(sessionId: string) {
  return fetchJson<GuidePages>(`/api/v1/guide/session/${encodeURIComponent(sessionId)}/pages`);
}

export type CreateGuideV2SessionInput = {
  goal: string;
  level?: string;
  timeBudgetMinutes?: number | null;
  horizon?: string;
  preferences?: string[];
  weakPoints?: string[];
  notebookContext?: string;
  courseTemplateId?: string;
  notebookReferences?: NotebookReference[];
  useMemory?: boolean;
  sourceAction?: Record<string, unknown>;
};

export function getGuideV2Health() {
  return fetchJson<GuideHealth>("/api/v1/guide/v2/health");
}

export async function listGuideV2Sessions() {
  const data = await fetchJson<{ sessions: GuideV2SessionSummary[] }>("/api/v1/guide/v2/sessions");
  return data.sessions ?? [];
}

export async function listGuideV2Templates() {
  const data = await fetchJson<{ templates: GuideV2CourseTemplate[] }>("/api/v1/guide/v2/templates");
  return data.templates ?? [];
}

export function createGuideV2Session(input: CreateGuideV2SessionInput) {
  return fetchJson<{ success: boolean; session: GuideV2Session }>(
    "/api/v1/guide/v2/sessions",
    jsonBody({
      goal: input.goal,
      level: input.level || "",
      time_budget_minutes: input.timeBudgetMinutes ?? null,
      horizon: input.horizon || "",
      preferences: input.preferences ?? [],
      weak_points: input.weakPoints ?? [],
      notebook_context: input.notebookContext || "",
      course_template_id: input.courseTemplateId || "",
      notebook_references: input.notebookReferences ?? [],
      use_memory: input.useMemory ?? true,
      source_action: input.sourceAction ?? {},
    }),
  );
}

export function getGuideV2LearnerMemory() {
  return fetchJson<GuideV2LearnerMemory>("/api/v1/guide/v2/learner-memory");
}

export function getGuideV2Session(sessionId: string) {
  return fetchJson<GuideV2Session>(`/api/v1/guide/v2/sessions/${encodeURIComponent(sessionId)}`);
}

export function getGuideV2Evaluation(sessionId: string) {
  return fetchJson<GuideV2Evaluation>(`/api/v1/guide/v2/sessions/${encodeURIComponent(sessionId)}/evaluation`);
}

export function getGuideV2StudyPlan(sessionId: string) {
  return fetchJson<GuideV2StudyPlan>(`/api/v1/guide/v2/sessions/${encodeURIComponent(sessionId)}/study-plan`);
}

export function getGuideV2LearningTimeline(sessionId: string) {
  return fetchJson<GuideV2LearningTimeline>(`/api/v1/guide/v2/sessions/${encodeURIComponent(sessionId)}/learning-timeline`);
}

export function getGuideV2CoachBriefing(sessionId: string) {
  return fetchJson<GuideV2CoachBriefing>(`/api/v1/guide/v2/sessions/${encodeURIComponent(sessionId)}/coach-briefing`);
}

export function getGuideV2MistakeReview(sessionId: string) {
  return fetchJson<GuideV2MistakeReview>(`/api/v1/guide/v2/sessions/${encodeURIComponent(sessionId)}/mistake-review`);
}

export function getGuideV2Diagnostic(sessionId: string) {
  return fetchJson<GuideV2Diagnostic>(`/api/v1/guide/v2/sessions/${encodeURIComponent(sessionId)}/diagnostic`);
}

export function submitGuideV2Diagnostic(input: {
  sessionId: string;
  answers: GuideV2DiagnosticAnswer[];
}) {
  return fetchJson<GuideV2DiagnosticSubmitResult>(
    `/api/v1/guide/v2/sessions/${encodeURIComponent(input.sessionId)}/diagnostic`,
    jsonBody({ answers: input.answers }),
  );
}

export function getGuideV2ProfileDialogue(sessionId: string) {
  return fetchJson<GuideV2ProfileDialogue>(`/api/v1/guide/v2/sessions/${encodeURIComponent(sessionId)}/profile-dialogue`);
}

export function submitGuideV2ProfileDialogue(input: {
  sessionId: string;
  message: string;
}) {
  return fetchJson<GuideV2ProfileDialogueResult>(
    `/api/v1/guide/v2/sessions/${encodeURIComponent(input.sessionId)}/profile-dialogue`,
    jsonBody({ message: input.message }),
  );
}

export function getGuideV2LearningReport(sessionId: string) {
  return fetchJson<GuideV2LearningReport>(`/api/v1/guide/v2/sessions/${encodeURIComponent(sessionId)}/report`);
}

export function getGuideV2CoursePackage(sessionId: string) {
  return fetchJson<GuideV2CoursePackage>(`/api/v1/guide/v2/sessions/${encodeURIComponent(sessionId)}/course-package`);
}

export function getGuideV2ResourceRecommendations(sessionId: string) {
  return fetchJson<{
    success: boolean;
    session_id: string;
    generated_at?: number;
    summary?: string;
    effect_assessment?: GuideV2LearningReport["effect_assessment"];
    recommendations: GuideV2ResourceRecommendation[];
  }>(`/api/v1/guide/v2/sessions/${encodeURIComponent(sessionId)}/resource-recommendations`);
}

export function completeGuideV2Task(input: {
  sessionId: string;
  taskId: string;
  score?: number | null;
  reflection?: string;
  mistakeTypes?: string[];
}) {
  return fetchJson<GuideV2TaskCompletionResult>(
    `/api/v1/guide/v2/sessions/${encodeURIComponent(input.sessionId)}/tasks/${encodeURIComponent(input.taskId)}/complete`,
    jsonBody({
      score: input.score ?? null,
      reflection: input.reflection || "",
      mistake_types: input.mistakeTypes ?? [],
    }),
  );
}

export function generateGuideV2TaskResource(input: {
  sessionId: string;
  taskId: string;
  resourceType: GuideV2ResourceType | string;
  prompt?: string;
  quality?: "low" | "medium" | "high" | string;
}) {
  return fetchJson<{
    success: boolean;
    artifact: GuideV2Artifact;
    task: GuideV2Task;
    session: GuideV2Session;
  }>(
    `/api/v1/guide/v2/sessions/${encodeURIComponent(input.sessionId)}/tasks/${encodeURIComponent(input.taskId)}/resources`,
    jsonBody({
      resource_type: input.resourceType,
      prompt: input.prompt || "",
      quality: input.quality || "medium",
    }),
  );
}

export function startGuideV2TaskResourceJob(input: {
  sessionId: string;
  taskId: string;
  resourceType: GuideV2ResourceType | string;
  prompt?: string;
  quality?: "low" | "medium" | "high" | string;
}) {
  return fetchJson<{
    task_id: string;
    session_id: string;
    learning_task_id: string;
    resource_type: string;
    agent_steps?: GuideResourceAgentStep[];
  }>(
    `/api/v1/guide/v2/sessions/${encodeURIComponent(input.sessionId)}/tasks/${encodeURIComponent(input.taskId)}/resources/jobs`,
    jsonBody({
      resource_type: input.resourceType,
      prompt: input.prompt || "",
      quality: input.quality || "medium",
    }),
  );
}

export function openGuideV2ResourceJobEvents(jobId: string) {
  return new EventSource(appendApiKeyQuery(apiUrl(`/api/v1/guide/v2/resource-jobs/${encodeURIComponent(jobId)}/events`)));
}

export function saveGuideV2Artifact(input: {
  sessionId: string;
  taskId: string;
  artifactId: string;
  notebookIds?: string[];
  title?: string;
  summary?: string;
  saveQuestions?: boolean;
}) {
  return fetchJson<{
    success: boolean;
    artifact_id: string;
    notebook?: {
      record?: NotebookRecord | null;
      added_to_notebooks?: string[];
    };
    question_notebook?: {
      saved?: boolean;
      count?: number;
      session_id?: string;
    };
  }>(
    `/api/v1/guide/v2/sessions/${encodeURIComponent(input.sessionId)}/tasks/${encodeURIComponent(input.taskId)}/artifacts/${encodeURIComponent(input.artifactId)}/save`,
    jsonBody({
      notebook_ids: input.notebookIds ?? [],
      title: input.title || "",
      summary: input.summary || "",
      save_questions: input.saveQuestions ?? true,
    }),
  );
}

export function guideV2ArtifactAssetUrl(input: {
  sessionId: string;
  taskId: string;
  artifactId: string;
}) {
  return apiUrl(
    `/api/v1/guide/v2/sessions/${encodeURIComponent(input.sessionId)}/tasks/${encodeURIComponent(input.taskId)}/artifacts/${encodeURIComponent(input.artifactId)}/asset`,
  );
}

export function submitGuideV2QuizResults(input: {
  sessionId: string;
  taskId: string;
  artifactId: string;
  answers: QuizResultItem[];
  saveQuestions?: boolean;
}) {
  return fetchJson<GuideV2QuizSubmitResult>(
    `/api/v1/guide/v2/sessions/${encodeURIComponent(input.sessionId)}/tasks/${encodeURIComponent(input.taskId)}/artifacts/${encodeURIComponent(input.artifactId)}/quiz-results`,
    jsonBody({
      answers: input.answers,
      save_questions: input.saveQuestions ?? true,
    }),
  );
}

export function saveGuideV2Report(input: {
  sessionId: string;
  notebookIds?: string[];
  title?: string;
  summary?: string;
}) {
  return fetchJson<{
    success: boolean;
    session_id: string;
    notebook?: {
      record?: NotebookRecord | null;
      added_to_notebooks?: string[];
    };
  }>(
    `/api/v1/guide/v2/sessions/${encodeURIComponent(input.sessionId)}/report/save`,
    jsonBody({
      notebook_ids: input.notebookIds ?? [],
      title: input.title || "",
      summary: input.summary || "",
    }),
  );
}

export function saveGuideV2CoursePackage(input: {
  sessionId: string;
  notebookIds?: string[];
  title?: string;
  summary?: string;
}) {
  return fetchJson<{
    success: boolean;
    session_id: string;
    notebook?: {
      record?: NotebookRecord | null;
      added_to_notebooks?: string[];
    };
  }>(
    `/api/v1/guide/v2/sessions/${encodeURIComponent(input.sessionId)}/course-package/save`,
    jsonBody({
      notebook_ids: input.notebookIds ?? [],
      title: input.title || "",
      summary: input.summary || "",
    }),
  );
}

export function refreshGuideV2Recommendations(sessionId: string) {
  return fetchJson<{ success: boolean; recommendations: string[] }>(
    `/api/v1/guide/v2/sessions/${encodeURIComponent(sessionId)}/recommendations/refresh`,
    { method: "POST" },
  );
}

export function deleteGuideV2Session(sessionId: string) {
  return fetchJson<Record<string, unknown>>(`/api/v1/guide/v2/sessions/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
  });
}

export async function listCoWriterHistory() {
  const data = await fetchJson<{ history: Array<Record<string, unknown>>; total: number }>("/api/v1/co_writer/history");
  return data.history ?? [];
}

export function getCoWriterOperation(operationId: string) {
  return fetchJson<Record<string, unknown>>(`/api/v1/co_writer/history/${encodeURIComponent(operationId)}`);
}

export function getCoWriterToolCalls(operationId: string) {
  return fetchJson<Record<string, unknown>>(`/api/v1/co_writer/tool_calls/${encodeURIComponent(operationId)}`);
}

export async function exportCoWriterMarkdown(input: { content: string; filename: string }) {
  const response = await authorizedFetch(apiUrl("/api/v1/co_writer/export/markdown"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw new ApiError((await response.text()) || "Markdown export failed", response.status);
  return response.text();
}

export function editWithCoWriter(input: {
  selected_text: string;
  instruction?: string;
  mode?: "rewrite" | "shorten" | "expand" | "none";
  tools?: string[];
  kb_name?: string | null;
}) {
  return fetchJson<CoWriterResult>("/api/v1/co_writer/edit_react", jsonBody(input));
}

export function editWithCoWriterBasic(input: {
  text: string;
  instruction: string;
  action: "rewrite" | "shorten" | "expand";
  source?: "rag" | "web" | null;
  kb_name?: string | null;
}) {
  return fetchJson<CoWriterResult>("/api/v1/co_writer/edit", jsonBody(input));
}

export type CoWriterStreamEvent = {
  type?: string;
  source?: string;
  stage?: string;
  content?: string;
  metadata?: Record<string, unknown>;
};

export async function streamCoWriterEdit(
  input: {
    selected_text: string;
    instruction?: string;
    mode?: "rewrite" | "shorten" | "expand" | "none";
    tools?: string[];
    kb_name?: string | null;
  },
  callbacks: {
    signal?: AbortSignal;
    onEvent?: (event: CoWriterStreamEvent) => void;
    onContent?: (chunk: string) => void;
  } = {},
): Promise<CoWriterResult> {
  const response = await authorizedFetch(apiUrl("/api/v1/co_writer/edit_react/stream"), {
    method: "POST",
    signal: callbacks.signal,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw new ApiError((await response.text()) || "Co-Writer stream failed", response.status);
  if (!response.body) throw new ApiError("Co-Writer stream did not return a response body");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let streamedText = "";
  let finalResult: CoWriterResult | null = null;

  const processEvent = (raw: string) => {
    const lines = raw.split(/\r?\n/);
    let eventName = "message";
    const dataLines: string[] = [];
    for (const line of lines) {
      if (line.startsWith("event:")) eventName = line.slice(6).trim();
      if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
    }
    if (!dataLines.length) return;
    const payload = JSON.parse(dataLines.join("\n")) as CoWriterStreamEvent | CoWriterResult | { detail?: string };
    if (eventName === "error") {
      throw new ApiError(String((payload as { detail?: string }).detail || "Co-Writer stream failed"));
    }
    if (eventName === "result") {
      finalResult = payload as CoWriterResult;
      return;
    }
    if (eventName !== "stream") return;

    const event = payload as CoWriterStreamEvent;
    callbacks.onEvent?.(event);
    if (event.type === "content" && event.content) {
      streamedText += event.content;
      callbacks.onContent?.(event.content);
    }
    if (event.type === "result" && event.metadata) {
      finalResult = event.metadata as CoWriterResult;
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    while (true) {
      const index = buffer.indexOf("\n\n");
      if (index === -1) break;
      const raw = buffer.slice(0, index);
      buffer = buffer.slice(index + 2);
      processEvent(raw);
    }
  }
  buffer += decoder.decode();
  if (buffer.trim()) processEvent(buffer.trim());

  return finalResult || { edited_text: streamedText };
}

export function autoMarkText(text: string) {
  return fetchJson<CoWriterResult>("/api/v1/co_writer/automark", jsonBody({ text }));
}

export async function testService(
  service:
    | "llm"
    | "embeddings"
    | "search"
    | "ocr"
    | "tts"
    | "asr"
    | "speech_eval"
    | "iflytek_workflow"
    | "formula_ocr"
    | "image_understanding",
) {
  return fetchJson<SystemTestResponse>(`/api/v1/system/test/${service}`, { method: "POST" });
}

export async function previewTts(text: string) {
  const response = await authorizedFetch(apiUrl("/api/v1/system/tts-preview"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!response.ok) {
    throw new ApiError((await response.text()) || "TTS preview failed", response.status);
  }
  return {
    blob: await response.blob(),
    contentType: response.headers.get("content-type") || "audio/mpeg",
    voice: response.headers.get("x-sparkweave-tts-voice") || "",
    fallback: response.headers.get("x-sparkweave-tts-fallback") === "true",
    fallbackReason: response.headers.get("x-sparkweave-tts-fallback-reason") || "",
  };
}

export function previewOcrImage(input: { image_base64: string; encoding?: string }) {
  return fetchJson<OcrPreviewResponse>("/api/v1/system/ocr-preview", jsonBody(input));
}

export function transcribeSpeechAudio(input: { file: File; audioEncoding?: string }) {
  const form = new FormData();
  form.append("file", input.file);
  if (input.audioEncoding?.trim()) form.append("audio_encoding", input.audioEncoding.trim());
  return fetchJson<SpeechTranscribeResponse>("/api/v1/speech/transcribe", {
    method: "POST",
    body: form,
  });
}

export function evaluateSpeechAudio(input: {
  file: File;
  referenceText: string;
  courseId?: string;
  nodeId?: string;
  taskId?: string;
  title?: string;
  persistEvidence?: boolean;
}) {
  const form = new FormData();
  form.append("file", input.file);
  form.append("reference_text", input.referenceText);
  if (input.courseId?.trim()) form.append("course_id", input.courseId.trim());
  if (input.nodeId?.trim()) form.append("node_id", input.nodeId.trim());
  if (input.taskId?.trim()) form.append("task_id", input.taskId.trim());
  if (input.title?.trim()) form.append("title", input.title.trim());
  if (typeof input.persistEvidence === "boolean") form.append("persist_evidence", String(input.persistEvidence));
  return fetchJson<SpeechEvaluateResponse>("/api/v1/speech/evaluate", {
    method: "POST",
    body: form,
  });
}
