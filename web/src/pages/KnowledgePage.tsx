import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "@tanstack/react-router";
import {
  AlertCircle,
  CheckCircle2,
  FileText,
  Loader2,
  MessageCircleQuestion,
  RefreshCw,
  Search,
  Send,
  UploadCloud,
} from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { FieldShell, FileInput, TextArea } from "@/components/ui/Field";
import {
  useDefaultKnowledgeBase,
  useKnowledgeBaseDetail,
  useKnowledgeBases,
  useKnowledgeDiagnostics,
  useKnowledgeDocuments,
  useKnowledgeMutations,
  useKnowledgeProgress,
  useRagProviders,
} from "@/hooks/useApiQueries";
import type {
  KnowledgeBase,
  KnowledgeDocumentSummary,
  KnowledgeProgress,
  RagSearchSource,
  RagSearchTestResult,
} from "@/lib/types";

import { FileList } from "./knowledge/FileList";
import { formatBytes, formatDocDate, formatErrorMessage, formatProgressStage, formatRagDiagnosticStatus, knowledgeProviderLabel } from "./knowledge/format";
import { KnowledgeCreatePanel } from "./knowledge/KnowledgeCreatePanel";
import { KnowledgeLibrarySidebar } from "./knowledge/KnowledgeLibrarySidebar";
import { formatKnowledgeLogLine, progressPercent as readProgressPercent } from "./knowledge/progressFormat";
import { useKnowledgeTaskProgress } from "./knowledge/useKnowledgeTaskProgress";

type KnowledgeView = "browse" | "create";

export function KnowledgePage() {
  const location = useLocation();
  const navigate = useNavigate();
  const view = location.pathname.split("/").filter(Boolean)[1] === "create" ? "create" : "browse";
  const routeTaskId = searchParamValue(location.search, "task");

  const query = useKnowledgeBases();
  const defaultKb = useDefaultKnowledgeBase();
  const providers = useRagProviders();
  const mutations = useKnowledgeMutations();

  const bases = useMemo(() => query.data ?? [], [query.data]);
  const backendDefaultName = defaultKb.data?.default_kb || "";
  const defaultBase = useMemo(
    () => bases.find((item) => item.is_default) ?? bases.find((item) => item.name === backendDefaultName),
    [backendDefaultName, bases],
  );
  const [selectedKb, setSelectedKb] = useState(() => knowledgeBaseNameFromSearch(location.search));
  const activeKb = selectedKb && bases.some((item) => item.name === selectedKb) ? selectedKb : defaultBase?.name || bases[0]?.name || "";
  const activeBase = bases.find((item) => item.name === activeKb);

  const kbDetail = useKnowledgeBaseDetail(activeKb || null);
  const documents = useKnowledgeDocuments(activeKb || null);
  const progress = useKnowledgeProgress(activeKb || null);
  const ragDiagnostic = useKnowledgeDiagnostics(activeKb || null, true, Boolean(activeKb));

  const providerOptions = providers.data ?? [];
  const activeProvider = providerOptions.find((item) => item.is_default)?.name || providerOptions[0]?.name || "";

  const [createName, setCreateName] = useState("");
  const [createFiles, setCreateFiles] = useState<File[]>([]);
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [uploadInputVersion, setUploadInputVersion] = useState(0);
  const [askQuery, setAskQuery] = useState("");
  const [ragResult, setRagResult] = useState<RagSearchTestResult | null>(null);
  const consumedSearchParamsRef = useRef("");

  const refetchActiveKnowledge = useCallback(() => {
    void query.refetch();
    void defaultKb.refetch();
    void kbDetail.refetch();
    void documents.refetch();
    void progress.refetch();
    void ragDiagnostic.refetch();
  }, [defaultKb, documents, kbDetail, progress, query, ragDiagnostic]);

  const { taskId, taskProgress, wsProgress, beginTask } = useKnowledgeTaskProgress({
    activeKb,
    onTerminalProgress: refetchActiveKnowledge,
  });

  const liveProgress = wsProgress ?? taskProgress ?? progress.data;
  const progressPercent = normalizePercent(readProgressPercent(liveProgress));
  const taskBusy =
    Boolean(taskId && !isTerminalProgressState(liveProgress)) ||
    mutations.create.isPending ||
    mutations.upload.isPending ||
    mutations.reindex.isPending ||
    isBusyProgress(liveProgress);

  useEffect(() => {
    if (!routeTaskId || taskId === routeTaskId) return;
    const kbName = activeKb || selectedKb;
    if (!kbName) return;
    const timer = window.setTimeout(() => beginTask(routeTaskId, kbName), 0);
    return () => window.clearTimeout(timer);
  }, [activeKb, beginTask, routeTaskId, selectedKb, taskId]);

  useEffect(() => {
    const kbName = knowledgeBaseNameFromSearch(location.search);
    if (!kbName || kbName === selectedKb) return undefined;
    const timer = window.setTimeout(() => setSelectedKb(kbName), 0);
    return () => window.clearTimeout(timer);
  }, [location.search, selectedKb]);

  useEffect(() => {
    const cacheKey = searchCacheKey(location.search);
    if (!cacheKey || consumedSearchParamsRef.current === cacheKey) return;
    const handoffQuery = searchParamValue(location.search, "query") || searchParamValue(location.search, "prompt");
    if (!handoffQuery) return;
    consumedSearchParamsRef.current = cacheKey;
    setAskQuery(handoffQuery);
  }, [location.search]);

  useEffect(() => {
    setRagResult(null);
  }, [activeKb]);

  const activeStatus = kbDetail.data?.status || activeBase?.status || (kbDetail.isLoading ? "loading" : activeKb ? "ready" : "idle");
  const documentCount = documents.data?.document_count ?? activeBase?.document_count ?? documents.data?.documents?.length ?? 0;
  const vectorCount = documents.data?.vector_count ?? readNumber(ragDiagnostic.data, "vector_row_count") ?? readNumber(activeBase?.statistics, "vector_count");
  const providerLabel = knowledgeProviderLabel(kbDetail.data?.rag_provider || activeBase?.rag_provider || ragDiagnostic.data?.provider || "milvus");
  const readinessLabel =
    ragDiagnostic.data?.readiness?.label || formatRagDiagnosticStatus(ragDiagnostic.data?.status, Boolean(ragDiagnostic.error));
  const readinessSummary = ragDiagnostic.data?.readiness?.summary || buildReadinessSummary(activeStatus, documentCount, vectorCount);
  const statusTone = knowledgeStatusTone(activeStatus, ragDiagnostic.error, ragDiagnostic.data?.status, ragDiagnostic.data?.readiness?.state);
  const latestError = mutations.create.error || mutations.upload.error || mutations.reindex.error || mutations.testRagSearch.error || documents.error;

  const navigateToOverview = useCallback(
    (kbName = activeKb, nextTaskId?: string | null) => {
      void navigate({ to: "/knowledge", search: knowledgeSearch(kbName, nextTaskId) });
    },
    [activeKb, navigate],
  );

  const navigateToCreate = useCallback(() => {
    void navigate({ to: "/knowledge/$workspace", params: { workspace: "create" }, search: knowledgeSearch(activeKb) });
  }, [activeKb, navigate]);

  const createKb = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedName = createName.trim();
    if (!trimmedName || !createFiles.length) return;
    const result = await mutations.create.mutateAsync({
      name: trimmedName,
      files: createFiles,
      ragProvider: activeProvider || undefined,
    });
    const nextKbName = result.name || trimmedName;
    const nextTaskId = result.task_id ?? null;
    setSelectedKb(nextKbName);
    setCreateName("");
    setCreateFiles([]);
    beginTask(nextTaskId, nextKbName);
    navigateToOverview(nextKbName, nextTaskId);
  };

  const uploadToKb = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!activeKb || !uploadFiles.length) return;
    const result = await mutations.upload.mutateAsync({
      kbName: activeKb,
      files: uploadFiles,
      ragProvider: activeProvider || undefined,
    });
    const nextTaskId = result.task_id ?? null;
    setUploadFiles([]);
    setUploadInputVersion((current) => current + 1);
    beginTask(nextTaskId, activeKb);
    navigateToOverview(activeKb, nextTaskId);
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
    navigateToOverview(activeKb, nextTaskId);
  };

  const askActiveKnowledge = async () => {
    const queryText = askQuery.trim();
    if (!activeKb || !queryText) return;
    setRagResult(null);
    const result = await mutations.testRagSearch.mutateAsync({
      kbName: activeKb,
      query: queryText,
      provider: kbDetail.data?.rag_provider || activeBase?.rag_provider || activeProvider || undefined,
      retrievalProfile: "auto",
      retrievalMode: "hybrid",
      agenticRag: "auto",
      topK: 5,
      candidateTopK: 15,
      reranker: "keyword",
      maxContextChars: 5000,
    });
    setRagResult(result);
  };

  const askInChat = () => {
    if (!activeKb || !askQuery.trim()) return;
    void navigate({
      to: "/chat",
      search: {
        new: "1",
        capability: "chat",
        prompt: askQuery.trim(),
        kb: activeKb,
      },
    });
  };

  return (
    <div className="dt-dynamic-page h-full overflow-y-auto px-3.5 py-3.5 pb-20 lg:px-4 lg:pb-4">
      <div className="mx-auto flex max-w-[1040px] flex-col gap-3.5">
        <Header />

        <div className="grid gap-3.5 lg:grid-cols-[270px_minmax(0,1fr)]">
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

          <main className="min-w-0 space-y-3.5">
            {view === "create" ? (
              <KnowledgeCreatePanel
                name={createName}
                files={createFiles}
                creating={mutations.create.isPending}
                error={mutations.create.error}
                onNameChange={setCreateName}
                onFilesChange={setCreateFiles}
                onSubmit={createKb}
                onBack={() => navigateToOverview()}
              />
            ) : null}

            {view === "browse" && !activeKb && !query.isLoading ? (
              <EmptyKnowledge onCreate={navigateToCreate} />
            ) : null}

            {view === "browse" && activeKb ? (
              <>
                <KnowledgeSummary
                  activeKb={activeKb}
                  activeStatus={activeStatus}
                  defaultActive={activeBase?.is_default || activeKb === backendDefaultName}
                  documentCount={documentCount}
                  vectorCount={vectorCount}
                  providerLabel={providerLabel}
                  readinessLabel={readinessLabel}
                  readinessSummary={readinessSummary}
                  statusTone={statusTone}
                  settingDefault={mutations.setDefault.isPending}
                  reindexing={mutations.reindex.isPending}
                  onSetDefault={() => void mutations.setDefault.mutateAsync(activeKb)}
                  onReindex={() => void reindexActiveKb()}
                />

                {latestError ? <ErrorNotice error={latestError} /> : null}

                <AskPanel
                  query={askQuery}
                  result={ragResult ?? mutations.testRagSearch.data ?? null}
                  running={mutations.testRagSearch.isPending}
                  activeKb={activeKb}
                  onQueryChange={setAskQuery}
                  onAsk={() => void askActiveKnowledge()}
                  onAskInChat={askInChat}
                />

                <ProgressPanel
                  progress={liveProgress}
                  percent={progressPercent}
                  busy={taskBusy}
                />

                <UploadPanel
                  key={`${activeKb}-${uploadInputVersion}`}
                  files={uploadFiles}
                  uploading={mutations.upload.isPending}
                  disabled={!activeKb}
                  onFilesChange={setUploadFiles}
                  onSubmit={uploadToKb}
                />

                <DocumentsPanel
                  documents={documents.data?.documents ?? []}
                  loading={documents.isLoading}
                  refreshing={documents.isFetching}
                  onRefresh={() => void documents.refetch()}
                />
              </>
            ) : null}
          </main>
        </div>
      </div>
    </div>
  );
}

function Header() {
  return (
    <section className="dt-page-header dt-page-header-accent-blue px-3.5 py-3.5">
      <p className="text-xs font-semibold text-steel">资料</p>
      <h1 className="mt-1 text-xl font-semibold leading-tight text-ink">上传资料，然后直接提问</h1>
      <p className="mt-2 text-xs leading-5 text-slate-600">默认只保留学习会用到的入口：选资料库、问资料、上传新资料。</p>
    </section>
  );
}

function EmptyKnowledge({ onCreate }: { onCreate: () => void }) {
  return (
    <section className="rounded-lg border border-line bg-white p-5">
      <EmptyState
        align="left"
        tone="knowledge"
        icon={<UploadCloud size={22} />}
        eyebrow="开始"
        title="先放入一份资料"
        description="创建资料库并上传课件、论文或笔记，整理完成后就可以围绕资料提问。"
        action={
          <Button tone="primary" onClick={onCreate}>
            <UploadCloud size={16} />
            新建资料库
          </Button>
        }
      />
    </section>
  );
}

function KnowledgeSummary({
  activeKb,
  activeStatus,
  defaultActive,
  documentCount,
  vectorCount,
  providerLabel,
  readinessLabel,
  readinessSummary,
  statusTone,
  settingDefault,
  reindexing,
  onSetDefault,
  onReindex,
}: {
  activeKb: string;
  activeStatus: string;
  defaultActive: boolean;
  documentCount: number;
  vectorCount?: number;
  providerLabel: string;
  readinessLabel: string;
  readinessSummary: string;
  statusTone: "neutral" | "success" | "warning" | "danger" | "brand";
  settingDefault: boolean;
  reindexing: boolean;
  onSetDefault: () => void;
  onReindex: () => void;
}) {
  return (
    <section className="rounded-lg border border-line bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="truncate text-lg font-semibold leading-tight text-ink">{activeKb}</h2>
            <Badge tone={statusTone}>{readinessLabel}</Badge>
            {defaultActive ? <Badge tone="brand">默认</Badge> : null}
          </div>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">{readinessSummary}</p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          {!defaultActive ? (
            <Button tone="secondary" className="min-h-9 px-3 text-xs" disabled={settingDefault} onClick={onSetDefault}>
              {settingDefault ? <Loader2 size={15} className="animate-spin" /> : <CheckCircle2 size={15} />}
              设为默认
            </Button>
          ) : null}
          <Button tone="secondary" className="min-h-9 px-3 text-xs" disabled={reindexing} onClick={onReindex}>
            {reindexing ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
            重新整理
          </Button>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-600">
        <span className="rounded-md bg-canvas px-2.5 py-1.5">状态：{formatProgressStage(activeStatus)}</span>
        <span className="rounded-md bg-canvas px-2.5 py-1.5">文档：{documentCount}</span>
        <span className="rounded-md bg-canvas px-2.5 py-1.5">引用片段：{typeof vectorCount === "number" ? vectorCount : "待整理"}</span>
        <span className="rounded-md bg-canvas px-2.5 py-1.5">服务：{providerLabel}</span>
      </div>
    </section>
  );
}

function AskPanel({
  query,
  result,
  running,
  activeKb,
  onQueryChange,
  onAsk,
  onAskInChat,
}: {
  query: string;
  result: RagSearchTestResult | null;
  running: boolean;
  activeKb: string;
  onQueryChange: (value: string) => void;
  onAsk: () => void;
  onAskInChat: () => void;
}) {
  const answer = result?.answer || result?.content || "";
  const sources = result?.sources ?? [];

  return (
    <section className="rounded-lg border border-line bg-white p-4">
      <div className="flex items-center gap-2">
        <MessageCircleQuestion size={18} className="text-charcoal" />
        <h2 className="text-base font-semibold text-ink">问资料</h2>
      </div>
      <div className="mt-3 grid gap-3">
        <TextArea
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder={`例如：这份资料里 ${activeKb} 的核心结论是什么？`}
          className="min-h-24"
          data-testid="knowledge-ask-input"
        />
        <div className="flex flex-wrap gap-2">
          <Button tone="primary" disabled={!query.trim() || running} onClick={onAsk} data-testid="knowledge-ask-submit">
            {running ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
            查找答案
          </Button>
          <Button tone="secondary" disabled={!query.trim()} onClick={onAskInChat}>
            <Send size={16} />
            去对话中问
          </Button>
        </div>
      </div>

      {result ? (
        <div className="mt-4 border-t border-line pt-4">
          {answer ? (
            <div className="max-h-72 overflow-y-auto rounded-lg bg-canvas p-3 text-sm leading-6 text-slate-700 whitespace-pre-wrap">
              {answer}
            </div>
          ) : (
            <p className="rounded-lg bg-canvas p-3 text-sm leading-6 text-slate-600">
              找到了 {result.source_count ?? sources.length} 条相关引用，可以打开对话继续追问。
            </p>
          )}
          <SourceList sources={sources} />
        </div>
      ) : null}
    </section>
  );
}

function SourceList({ sources }: { sources: RagSearchSource[] }) {
  if (!sources.length) return null;
  return (
    <div className="mt-4">
      <p className="text-xs font-semibold text-charcoal">引用来源</p>
      <div className="mt-2 divide-y divide-line rounded-lg border border-line">
        {sources.slice(0, 5).map((source, index) => {
          const title = source.title || source.source || source.chunk_id || `引用 ${index + 1}`;
          const body = String(source.content || source.evidence_reason || "").trim();
          return (
            <div key={`${title}-${index}`} className="p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="min-w-0 truncate text-sm font-medium text-ink">{title}</p>
                <span className="text-xs text-steel">{formatSourceMeta(source)}</span>
              </div>
              {body ? <p className="mt-2 line-clamp-3 text-xs leading-5 text-slate-600">{body}</p> : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ProgressPanel({
  progress,
  percent,
  busy,
}: {
  progress?: KnowledgeProgress | null;
  percent: number;
  busy: boolean;
}) {
  if (!progress && !busy) return null;
  const label = progress?.message
    ? formatKnowledgeLogLine(progress.message)
    : busy
      ? "正在整理资料..."
      : "资料处理完成";
  const stage = formatProgressStage(progress?.stage || progress?.status || (busy ? "processing" : "ready"));

  return (
    <section className="rounded-lg border border-line bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-ink">整理进度</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">{label}</p>
        </div>
        <Badge tone={busy ? "warning" : "success"}>{stage}</Badge>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-ink transition-all" style={{ width: `${busy ? Math.max(percent, 8) : percent}%` }} />
      </div>
    </section>
  );
}

function UploadPanel({
  files,
  uploading,
  disabled,
  onFilesChange,
  onSubmit,
}: {
  files: File[];
  uploading: boolean;
  disabled: boolean;
  onFilesChange: (files: File[]) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <section className="rounded-lg border border-line bg-white p-4">
      <div className="flex items-center gap-2">
        <UploadCloud size={18} className="text-charcoal" />
        <h2 className="text-base font-semibold text-ink">上传资料</h2>
      </div>
      <form className="mt-3 grid gap-3" onSubmit={onSubmit}>
        <FieldShell label="选择文件" hint="支持 PDF、Markdown、文本和代码文件">
          <FileInput
            multiple
            disabled={disabled || uploading}
            buttonLabel="选择资料"
            emptyLabel="未选择资料"
            onChange={(event) => onFilesChange(Array.from(event.target.files ?? []))}
            data-testid="knowledge-upload-files"
          />
        </FieldShell>
        {files.length ? <FileList files={files} /> : null}
        <div>
          <Button tone="primary" type="submit" disabled={!files.length || uploading || disabled} data-testid="knowledge-upload-submit">
            {uploading ? <Loader2 size={16} className="animate-spin" /> : <UploadCloud size={16} />}
            上传并整理
          </Button>
        </div>
      </form>
    </section>
  );
}

function DocumentsPanel({
  documents,
  loading,
  refreshing,
  onRefresh,
}: {
  documents: KnowledgeDocumentSummary[];
  loading: boolean;
  refreshing: boolean;
  onRefresh: () => void;
}) {
  return (
    <section className="rounded-lg border border-line bg-white p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <FileText size={18} className="text-charcoal" />
          <h2 className="text-base font-semibold text-ink">已整理的文档</h2>
        </div>
        <Button tone="quiet" className="min-h-8 px-2 text-xs" onClick={onRefresh} title="刷新文档" aria-label="刷新文档">
          {refreshing ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
        </Button>
      </div>

      {loading ? (
        <div className="mt-4 space-y-2">
          <span className="block h-10 rounded bg-slate-100" />
          <span className="block h-10 rounded bg-slate-100/80" />
        </div>
      ) : null}

      {!loading && !documents.length ? (
        <p className="mt-3 rounded-lg bg-canvas p-3 text-sm leading-6 text-slate-600">还没有文档。先上传一份资料，整理完成后会出现在这里。</p>
      ) : null}

      {!loading && documents.length ? (
        <div className="mt-3 divide-y divide-line rounded-lg border border-line">
          {documents.slice(0, 8).map((document) => (
            <div key={document.id} className="flex items-center justify-between gap-3 p-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-ink">{document.name}</p>
                <p className="mt-1 text-xs text-steel">
                  {document.size_human || (typeof document.size === "number" ? formatBytes(document.size) : "未知大小")} ·{" "}
                  {formatDocDate(document.modified_at)}
                </p>
              </div>
              <Badge tone={document.vectors_available || document.vector_count ? "success" : "neutral"}>
                {document.vector_count ? `${document.vector_count} 片段` : document.vectors_available ? "可引用" : "待整理"}
              </Badge>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function ErrorNotice({ error }: { error: unknown }) {
  return (
    <section className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm leading-6 text-red-700">
      <div className="flex gap-2">
        <AlertCircle size={16} className="mt-0.5 shrink-0" />
        <span>{formatErrorMessage(error)}</span>
      </div>
    </section>
  );
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

function searchCacheKey(search: unknown) {
  if (typeof search === "string") return search;
  if (!search || typeof search !== "object") return "";
  return JSON.stringify(search);
}

function readNumber(source: unknown, key: string) {
  if (!source || typeof source !== "object" || !(key in source)) return undefined;
  const value = (source as Record<string, unknown>)[key];
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function normalizePercent(value: unknown) {
  const parsed = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(parsed)) return 0;
  return Math.min(100, Math.max(0, parsed));
}

function isBusyProgress(progress?: KnowledgeProgress | null) {
  const status = String(progress?.stage || progress?.status || "").toLowerCase();
  return ["queued", "init", "running", "processing", "indexing", "uploaded"].some((item) => status.includes(item));
}

function isTerminalProgressState(progress?: KnowledgeProgress | null) {
  const status = String(progress?.stage || progress?.status || "").toLowerCase();
  return ["complete", "completed", "done", "failed", "error", "cancelled", "canceled"].includes(status);
}

function knowledgeStatusTone(
  activeStatus: string,
  diagnosticError: unknown,
  diagnosticStatus?: string,
  readinessState?: string,
): "neutral" | "success" | "warning" | "danger" | "brand" {
  if (diagnosticError) return "danger";
  const readiness = String(readinessState || "").toLowerCase();
  const diagnostic = String(diagnosticStatus || "").toLowerCase();
  const status = String(activeStatus || "").toLowerCase();
  if (readiness.includes("ready") || diagnostic === "ok" || status === "ready" || status === "done" || status === "completed") return "success";
  if (diagnostic === "error" || status.includes("error") || status.includes("fail")) return "danger";
  if (diagnostic === "warning" || isBusyProgress({ status })) return "warning";
  return "neutral";
}

function buildReadinessSummary(activeStatus: string, documentCount: number, vectorCount?: number) {
  if (!documentCount) return "当前资料库还没有文档，上传后系统会自动整理为可引用内容。";
  if (typeof vectorCount === "number" && vectorCount > 0) return "资料已经整理好，可以直接提问或在对话中引用。";
  if (isBusyProgress({ status: activeStatus })) return "资料正在整理，完成后就能稳定引用。";
  return "资料已保存，如回答找不到内容，可以重新整理一次。";
}

function formatSourceMeta(source: RagSearchSource) {
  const parts: string[] = [];
  if (source.page) parts.push(`第 ${source.page} 页`);
  if (source.score !== undefined && source.score !== null) parts.push(`相关度 ${source.score}`);
  return parts.join(" · ");
}
