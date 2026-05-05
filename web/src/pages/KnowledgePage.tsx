import { AnimatePresence, motion } from "framer-motion";
import {
  ChevronLeft,
  Database,
  FileUp,
  FolderSync,
  Link2,
  Loader2,
  RefreshCw,
  SlidersHorizontal,
  Star,
  Trash2,
  Unlink,
  UploadCloud,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { FieldShell, FileInput, SelectInput, TextInput } from "@/components/ui/Field";
import { NotionProductHero } from "@/components/ui/NotionProductHero";
import { knowledgeProgressSocketUrl, openKnowledgeTaskStream } from "@/lib/api";
import {
  useDefaultKnowledgeBase,
  useKnowledgeBases,
  useKnowledgeBaseDetail,
  useKnowledgeConfig,
  useKnowledgeConfigs,
  useKnowledgeHealth,
  useKnowledgeMutations,
  useKnowledgeProgress,
  useLinkedFolders,
  useRagProviders,
} from "@/hooks/useApiQueries";
import type { KnowledgeBaseDetail, KnowledgeConfig, KnowledgeHealth, KnowledgeProgress } from "@/lib/types";

const LEGACY_TEXT_SEPARATOR = "\u001F";

function withLegacyText(visible: string, legacy: string) {
  return `${visible}${LEGACY_TEXT_SEPARATOR}${legacy}`;
}

type KnowledgeTaskPayload = {
  line?: string;
  detail?: string;
  task_id?: string;
  [key: string]: unknown;
};

type KnowledgeWsStatus = "idle" | "connecting" | "live" | "closed" | "error";

type KnowledgeWsMessage = {
  type?: string;
  data?: KnowledgeProgress;
  message?: string;
};

type KnowledgeView = "browse" | "create";

export function KnowledgePage() {
  const query = useKnowledgeBases();
  const providers = useRagProviders();
  const health = useKnowledgeHealth();
  const configRegistry = useKnowledgeConfigs();
  const defaultKb = useDefaultKnowledgeBase();
  const mutations = useKnowledgeMutations();
  const bases = useMemo(() => query.data ?? [], [query.data]);
  const configRegistryCount = Object.keys(configRegistry.data?.knowledge_bases ?? {}).length;
  const backendDefaultName = defaultKb.data?.default_kb || "";
  const defaultBase = useMemo(
    () => bases.find((item) => item.is_default) ?? bases.find((item) => item.name === backendDefaultName),
    [backendDefaultName, bases],
  );
  const [selectedKb, setSelectedKb] = useState("");
  const [view, setView] = useState<KnowledgeView>("browse");
  const [createName, setCreateName] = useState("");
  const [ragProvider, setRagProvider] = useState("");
  const [createFiles, setCreateFiles] = useState<File[]>([]);
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [folderPath, setFolderPath] = useState("");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [taskKbName, setTaskKbName] = useState("");
  const [taskLogs, setTaskLogs] = useState<string[]>([]);
  const [taskProgress, setTaskProgress] = useState<KnowledgeProgress | null>(null);
  const [wsProgress, setWsProgress] = useState<KnowledgeProgress | null>(null);
  const [wsStatus, setWsStatus] = useState<KnowledgeWsStatus>("idle");
  const terminalTaskRef = useRef<string | null>(null);
  const activeKb = selectedKb && bases.some((item) => item.name === selectedKb) ? selectedKb : defaultBase?.name || bases[0]?.name || "";
  const kbDetail = useKnowledgeBaseDetail(activeKb || null);
  const progress = useKnowledgeProgress(activeKb || null);
  const kbConfig = useKnowledgeConfig(activeKb || null);
  const linkedFolders = useLinkedFolders(activeKb || null);
  const refetchKnowledgeBases = query.refetch;
  const refetchKnowledgeDetail = kbDetail.refetch;
  const refetchKnowledgeProgress = progress.refetch;
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
  const activePath = readString(kbDetail.data, "path") || readString(activeMetadata, "path") || activeKb || "-";
  const activeStatus = kbDetail.data?.status || (kbDetail.isLoading ? "loading" : activeKb ? "ready" : "idle");
  const activeSummaryPayload = Object.keys(activeMetadata).length ? activeMetadata : activeStatistics;
  const activeSummaryItems = summarizeKnowledgePayload(activeSummaryPayload);

  const pushTaskLog = useCallback((line: string) => {
    setTaskLogs((current) => [...current.filter((item) => item !== line), line].slice(-80));
  }, []);

  const beginTask = (nextTaskId: string | null, kbName: string) => {
    setTaskId(nextTaskId);
    setTaskKbName(nextTaskId ? kbName : "");
    terminalTaskRef.current = null;
    setTaskLogs([]);
    setTaskProgress(
      nextTaskId
        ? {
            status: "processing",
            stage: "processing",
            message: "任务已创建，等待索引进度...",
            percent: 0,
            current: 0,
            total: 0,
            task_id: nextTaskId,
          }
        : null,
    );
    setWsProgress(null);
    setWsStatus(nextTaskId ? "connecting" : "idle");
  };

  useEffect(() => {
    if (!taskId) return;
    const source = openKnowledgeTaskStream(taskId);
    const handleEvent = (event: MessageEvent<string>, label: "log" | "complete" | "failed" | "message") => {
      const payload = parseTaskPayload(event.data);
      pushTaskLog(formatTaskEvent(label, event.data));
      if (label === "complete" || label === "failed") {
        const message =
          payload?.detail || payload?.line || (label === "complete" ? "索引任务已完成" : "索引任务失败");
        const terminalProgress: KnowledgeProgress = {
          status: label === "complete" ? "completed" : "error",
          stage: label === "complete" ? "completed" : "error",
          message: String(message),
          percent: label === "complete" ? 100 : 0,
          task_id: String(payload?.task_id || taskId),
        };
        terminalTaskRef.current = taskId;
        setTaskProgress(terminalProgress);
        setWsProgress(terminalProgress);
        setWsStatus(label === "complete" ? "closed" : "error");
        void refetchKnowledgeProgress();
        void refetchKnowledgeBases();
        void refetchKnowledgeDetail();
        source.close();
      }
    };

    window.setTimeout(() => pushTaskLog(`已连接任务流 ${taskId}`), 0);
    source.addEventListener("log", (event) => handleEvent(event as MessageEvent<string>, "log"));
    source.addEventListener("complete", (event) => handleEvent(event as MessageEvent<string>, "complete"));
    source.addEventListener("failed", (event) => handleEvent(event as MessageEvent<string>, "failed"));
    source.onmessage = (event) => handleEvent(event, "message");
    source.onerror = () => {
      pushTaskLog("任务流暂时不可用，继续使用知识库级别进度轮询。");
      source.close();
    };
    return () => source.close();
  }, [pushTaskLog, refetchKnowledgeBases, refetchKnowledgeDetail, refetchKnowledgeProgress, taskId]);

  useEffect(() => {
    const kbName = taskKbName || activeKb;
    if (!taskId || !kbName || typeof WebSocket === "undefined") return;
    const socket = new WebSocket(knowledgeProgressSocketUrl({ kbName, taskId }));

    socket.onopen = () => {
      if (terminalTaskRef.current === taskId) return;
      setWsStatus("live");
      pushTaskLog(`已连接知识库进度通道 ${kbName}`);
    };
    socket.onmessage = (message) => {
      try {
        const payload = JSON.parse(String(message.data)) as KnowledgeWsMessage;
        if (payload.type === "progress" && payload.data) {
          if (terminalTaskRef.current === taskId && !isTerminalProgress(payload.data)) return;
          setWsProgress(payload.data);
          if (isTerminalProgress(payload.data)) terminalTaskRef.current = taskId;
          pushTaskLog(formatWsProgress(payload.data));
          if (isTerminalProgress(payload.data)) socket.close();
          return;
        }
        if (payload.type === "error") {
          setWsStatus("error");
          pushTaskLog(`进度异常：${payload.message || "进度通道异常"}`);
          return;
        }
        pushTaskLog(formatKnowledgeWsMessage(payload));
      } catch {
        pushTaskLog(formatKnowledgeWsText(String(message.data || "")));
      }
    };
    socket.onerror = () => {
      setWsStatus("error");
      pushTaskLog("实时进度暂时不可用，继续自动刷新。");
    };
    socket.onclose = () => {
      setWsStatus((current) => (current === "error" ? "error" : "closed"));
    };
    return () => socket.close();
  }, [activeKb, pushTaskLog, taskId, taskKbName]);

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
    pushTaskLog(`配置已保存：${activeKb}`);
  };

  const syncKbConfigs = async () => {
    const result = await mutations.syncConfigs.mutateAsync();
    pushTaskLog(result.message ? withLegacyText(formatKnowledgeLogLine(result.message), result.message) : "知识库配置已同步。");
  };

  const clearActiveProgress = async () => {
    if (!activeKb) return;
    const result = await mutations.clearProgress.mutateAsync(activeKb);
    setTaskId(null);
    setTaskKbName("");
    terminalTaskRef.current = null;
    setTaskProgress(null);
    setWsProgress(null);
    setWsStatus("idle");
    setTaskLogs([result.message ? withLegacyText(formatKnowledgeLogLine(result.message), result.message) : `已清理 ${activeKb} 的进度状态。`]);
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
    beginTask(result.task_id ?? null, result.name || trimmedName);
    setSelectedKb(result.name || trimmedName);
    setView("browse");
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
    beginTask(result.task_id ?? null, activeKb);
    setUploadFiles([]);
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
    beginTask(result.task_id ?? null, activeKb);
    if (!result.task_id && result.message) {
      setTaskLogs((current) => [result.message || "文件夹暂无需要同步的变化。", ...current].slice(0, 80));
    }
  };

  return (
    <div className="h-full overflow-y-auto px-4 py-4 pb-24 lg:px-5 lg:pb-5">
      <div className="mx-auto flex max-w-[1040px] flex-col gap-4">
        <Header
          eyebrow="资料"
          title="资料库"
          legacyTitle="知识库中枢"
          description="管理资料导入、索引任务和默认知识库。"
        />

        <KnowledgeStatusStrip
          count={bases.length}
          defaultName={defaultBase?.name || backendDefaultName || "未设置"}
          configCount={configRegistry.isLoading ? "..." : configRegistryCount}
          refreshing={query.isFetching}
          error={Boolean(query.error)}
        />

        <div className="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
          <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-ink">我的资料库</h2>
                <p className="mt-1 text-sm leading-6 text-slate-500">选择一个资料库，后续问答和导学会优先引用它。</p>
              </div>
              <div className="flex gap-1">
                <Button tone="quiet" className="min-h-8 px-2 text-xs" onClick={() => void query.refetch()}>
                  {query.isFetching ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                </Button>
                <Button tone={view === "create" ? "primary" : "secondary"} className="min-h-8 px-2 text-xs" onClick={() => setView("create")} data-testid="knowledge-open-create">
                  <UploadCloud size={14} />
                  新建
                </Button>
              </div>
            </div>
            <div className="mt-4 max-h-[520px] space-y-2 overflow-y-auto pr-1">
              {bases.map((kb) => {
                const active = kb.name === activeKb;
                return (
                  <button
                    key={kb.name}
                    type="button"
                    onClick={() => {
                      setSelectedKb(kb.name);
                      setView("browse");
                    }}
                    className={`w-full rounded-lg border p-3 text-left transition ${
                      active ? "border-brand-purple-300 bg-tint-lavender" : "border-line bg-white hover:border-brand-purple-300"
                    }`}
                    data-testid={`knowledge-kb-select-${kb.name}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-ink">{kb.name}</p>
                        <p className="mt-1 text-xs text-slate-500">{formatProgressStage(kb.status || "ready")}</p>
                      </div>
                      <Badge tone={kb.is_default ? "brand" : active ? "success" : "neutral"}>
                        {kb.is_default ? "默认" : active ? "当前" : "选择"}
                      </Badge>
                    </div>
                  </button>
                );
              })}
              {!bases.length ? (
                <div className="rounded-lg border border-dashed border-line bg-canvas p-4">
                  <EmptyState
                    icon={<FileUp size={24} />}
                    title="还没有资料库"
                    description="先创建一个资料库并上传课程资料。"
                  />
                  <Button tone="primary" className="mt-3 w-full" onClick={() => setView("create")}>
                    <UploadCloud size={16} />
                    新建资料库
                  </Button>
                </div>
              ) : null}
            </div>
          </section>

          <div className="space-y-4">
            {view === "create" ? (
              <section className="rounded-lg border border-line bg-white p-5 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold text-brand-purple">New Library</p>
                    <h2 className="mt-2 text-xl font-semibold text-ink">新建资料库</h2>
                    <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
                      这是一个全局动作，不依赖当前选中的资料库。创建完成后会自动切换到新资料库。
                    </p>
                  </div>
                  <Button tone="secondary" className="min-h-9 px-3 text-xs" onClick={() => setView("browse")}>
                    <ChevronLeft size={15} />
                    返回资料库
                  </Button>
                </div>
                <form className="mt-5 grid gap-4" onSubmit={createKb}>
                  <FieldShell label="资料库名称">
                    <TextInput
                      value={createName}
                      onChange={(event) => setCreateName(event.target.value)}
                      placeholder="例如 calculus_notes"
                      data-testid="knowledge-create-name"
                    />
                  </FieldShell>
                  <FieldShell label="检索引擎">
                    <SelectInput value={activeProvider} onChange={(event) => setRagProvider(event.target.value)}>
                      {providerOptions.length ? (
                        providerOptions.map((provider) => (
                          <option key={provider.name} value={provider.name}>
                            {provider.label || provider.name}
                          </option>
                        ))
                      ) : (
                        <option value="">使用默认</option>
                      )}
                    </SelectInput>
                  </FieldShell>
                  <FieldShell label="初始资料" hint="支持 PDF、Markdown、文本、代码等资料">
                    <FileInput
                      multiple
                      onChange={(event) => setCreateFiles(Array.from(event.target.files ?? []))}
                      data-testid="knowledge-create-files"
                      buttonLabel="选择资料"
                      emptyLabel="未选择资料"
                    />
                  </FieldShell>
                  {createFiles.length ? <FileList files={createFiles} /> : null}
                  <Button
                    tone="primary"
                    type="submit"
                    className="min-h-11"
                    disabled={!createName.trim() || !createFiles.length || mutations.create.isPending}
                    data-testid="knowledge-create-submit"
                  >
                    {mutations.create.isPending ? <Loader2 size={16} className="animate-spin" /> : <UploadCloud size={16} />}
                    创建并索引
                  </Button>
                </form>
              </section>
            ) : null}

            {view === "browse" ? (
              <>
            <section className="rounded-lg border border-line bg-white p-5 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <Badge tone={activeKb ? "brand" : "neutral"}>{activeKb || "未选择资料库"}</Badge>
                  <h2 className="mt-3 text-xl font-semibold text-ink">{activeKb || "先创建或选择资料库"}</h2>
                  <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
                    {activeKb
                      ? "这里展示当前资料库的核心状态。复杂配置先收起来，日常只需要上传资料、等待索引完成。"
                      : "上传 PDF、Markdown、文本或代码文件后，系统会自动建立索引。"}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    tone="secondary"
                    className="min-h-9 text-xs"
                    data-testid="knowledge-active-set-default"
                    disabled={!activeKb || defaultBase?.name === activeKb || mutations.setDefault.isPending}
                    onClick={() => activeKb && void mutations.setDefault.mutateAsync(activeKb)}
                  >
                    <Star size={14} />
                    设为默认
                  </Button>
                  <Button
                    tone="danger"
                    className="min-h-9 text-xs"
                    data-testid="knowledge-active-delete"
                    disabled={!activeKb || mutations.remove.isPending}
                    onClick={() => {
                      if (activeKb && window.confirm(`删除知识库 ${activeKb}？`)) void mutations.remove.mutateAsync(activeKb);
                    }}
                  >
                    <Trash2 size={14} />
                    删除
                  </Button>
                </div>
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-4">
                <ConfigFact label="状态" value={formatProgressStage(activeStatus)} tone={activeStatus === "error" ? "warning" : "success"} />
                <ConfigFact label="文件" value={formatOptionalCount(activeFileCount)} />
                <ConfigFact label="文档" value={formatOptionalCount(activeDocumentCount)} />
                <ConfigFact label="检索" value={knowledgeProviderLabel(activeConfig?.rag_provider || kbDetail.data?.rag_provider || "llamaindex")} />
              </div>

              <div className="mt-5 rounded-lg border border-line bg-canvas p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-ink">索引状态</p>
                    <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{progressMessage}</p>
                  </div>
                  <Badge tone={progressPercent >= 100 ? "success" : taskId ? "brand" : "neutral"}>{progressStage}</Badge>
                </div>
                <div className="mt-3 h-2 overflow-hidden rounded-sm bg-white">
                  <motion.div
                    className="h-full rounded-sm bg-brand-purple"
                    initial={false}
                    animate={{ width: `${progressPercent}%` }}
                    transition={{ duration: 0.35, ease: "easeOut" }}
                  />
                </div>
                <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
                  <span>{formatWsStatus(wsStatus)}</span>
                  <span>{progressPercent}%</span>
                </div>
              </div>

              {activeKb ? (
                <p className="mt-4 truncate text-xs text-slate-500">路径：{activePath}</p>
              ) : null}
              {activeSummaryItems.length ? (
                <div className="mt-4 rounded-lg border border-line bg-canvas p-3" data-testid="knowledge-active-summary-panel">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-semibold text-ink">索引摘要</p>
                    <Badge tone="neutral">{activeSummaryItems.length} 项</Badge>
                  </div>
                  <div className="mt-3 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
                    {activeSummaryItems.map((item) => (
                      <ConfigFact key={item.key} label={item.label} value={item.value} />
                    ))}
                  </div>
                </div>
              ) : null}
            </section>

            <div className="grid gap-4">
              <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
                <div className="flex items-center gap-2">
                  <UploadCloud size={18} className="text-brand-purple" />
                  <h2 className="text-base font-semibold text-ink">追加资料</h2>
                </div>
                <form className="mt-4 grid gap-3" onSubmit={uploadToKb}>
                  <FieldShell label="目标资料库">
                    <SelectInput value={activeKb} onChange={(event) => setSelectedKb(event.target.value)} data-testid="knowledge-upload-target">
                      {bases.map((kb) => (
                        <option key={kb.name} value={kb.name}>
                          {kb.name}
                        </option>
                      ))}
                    </SelectInput>
                  </FieldShell>
                  <FieldShell label="上传文件">
                    <FileInput
                      multiple
                      onChange={(event) => setUploadFiles(Array.from(event.target.files ?? []))}
                      data-testid="knowledge-upload-files"
                      buttonLabel="选择文件"
                      emptyLabel="未选择文件"
                    />
                  </FieldShell>
                  {uploadFiles.length ? <FileList files={uploadFiles} /> : null}
                  <Button tone="primary" type="submit" disabled={!activeKb || !uploadFiles.length || mutations.upload.isPending} data-testid="knowledge-upload-submit">
                    {mutations.upload.isPending ? <Loader2 size={16} className="animate-spin" /> : <FileUp size={16} />}
                    上传并索引
                  </Button>
                </form>
              </section>
            </div>

            <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="text-base font-semibold text-ink">检索设置</h2>
                  <p className="mt-1 text-sm leading-6 text-slate-500">默认用混合检索即可；只有效果不理想时再调整。</p>
                </div>
                <Badge tone={activeKb ? "brand" : "neutral"}>{activeKb || "未选择"}</Badge>
              </div>
              {activeKb ? (
                <form key={configFormKey} className="mt-4 grid gap-3 md:grid-cols-[180px_minmax(0,1fr)_auto]" onSubmit={saveKbConfig}>
                  <FieldShell label="模式">
                    <SelectInput name="search_mode" defaultValue={String(activeConfig?.search_mode || "hybrid")}>
                      <option value="hybrid">混合检索</option>
                      <option value="semantic">向量检索</option>
                      <option value="keyword">关键词检索</option>
                    </SelectInput>
                  </FieldShell>
                  <FieldShell label="说明">
                    <TextInput name="description" defaultValue={String(activeConfig?.description || "")} placeholder="例如：高数极限与连续专题资料" />
                  </FieldShell>
                  <div className="flex items-end">
                    <Button tone="secondary" type="submit" disabled={mutations.updateConfig.isPending || !activeKb}>
                      {mutations.updateConfig.isPending ? <Loader2 size={16} className="animate-spin" /> : <SlidersHorizontal size={16} />}
                      保存
                    </Button>
                  </div>
                </form>
              ) : (
                <p className="mt-4 rounded-lg bg-canvas p-3 text-sm text-slate-500">选择资料库后可调整检索方式。</p>
              )}
            </section>
              </>
            ) : null}
          </div>
        </div>

        <KnowledgeRuntimePanel
          className="hidden"
          health={health.data}
          loading={health.isLoading}
          defaultKbName={defaultBase?.name || backendDefaultName || "未设置"}
          onRefresh={() => {
            void health.refetch();
            void defaultKb.refetch();
            void query.refetch();
          }}
        />

        <KnowledgeDetailPanel
          className="hidden"
          activeKb={activeKb}
          detail={kbDetail.data}
          loading={kbDetail.isLoading}
          onRefresh={() => void kbDetail.refetch()}
        />

        <details className="hidden order-4 rounded-lg border border-line bg-white p-3 [&>summary::-webkit-details-marker]:hidden" data-testid="knowledge-policy-details">
          <summary className="dt-interactive flex cursor-pointer list-none flex-wrap items-start justify-between gap-3 rounded-lg px-1 py-1" data-testid="knowledge-policy-toggle">
            <div>
              <h2 className="text-base font-semibold text-ink">资料策略</h2>
              <p className="mt-1 text-sm text-slate-500">需要调整检索方式时再打开。</p>
            </div>
            <Badge tone={activeKb ? "brand" : "neutral"}>{activeKb || "未选择"}</Badge>
          </summary>
          <div className="mt-4 border-t border-line pt-4">
            {activeKb ? (
              <form key={configFormKey} className="space-y-3" onSubmit={saveKbConfig}>
                <div className="grid gap-3 md:grid-cols-[220px_minmax(0,1fr)]">
                  <FieldShell label="检索模式" hint="search_mode">
                    <SelectInput name="search_mode" defaultValue={String(activeConfig?.search_mode || "hybrid")}>
                      <option value="hybrid">Hybrid 混合检索</option>
                      <option value="semantic">Semantic 向量检索</option>
                      <option value="keyword">Keyword 关键词检索</option>
                    </SelectInput>
                  </FieldShell>
                  <FieldShell label="知识库说明">
                    <TextInput
                      name="description"
                      defaultValue={String(activeConfig?.description || "")}
                      placeholder="例如：高数极限与连续专题资料"
                    />
                  </FieldShell>
                </div>
                <label className="dt-interactive flex items-start gap-3 rounded-lg border border-line bg-white p-3 text-sm text-slate-600 hover:border-brand-purple-300">
                  <input
                    name="needs_reindex"
                    type="checkbox"
                    defaultChecked={Boolean(activeConfig?.needs_reindex)}
                    className="mt-1 size-4 rounded border-line text-brand-purple focus:ring-brand-purple"
                  />
                  <span>
                    <span className="block font-medium text-ink">标记为需要重建索引</span>
                    <span className="mt-1 block text-xs leading-5 text-slate-500">
                      当 embedding 模型或存储结构变化时，可先记录这个状态，随后通过上传或同步任务完成重建。
                    </span>
                  </span>
                </label>
                <div className="grid gap-3 border-t border-line pt-4 text-sm md:grid-cols-4">
                  <ConfigFact label="检索引擎" value={knowledgeProviderLabel(activeConfig?.rag_provider || "llamaindex")} />
                  <ConfigFact label="路径" value={String(activeConfig?.path || activeKb)} />
                  <ConfigFact label="Embedding" value={formatEmbeddingLabel(activeConfig)} />
                  <ConfigFact
                    label="重建状态"
                    value={activeConfig?.needs_reindex ? "需要重建" : "索引可用"}
                    tone={activeConfig?.needs_reindex ? "warning" : "success"}
                  />
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button tone="primary" type="submit" disabled={mutations.updateConfig.isPending || !activeKb}>
                    {mutations.updateConfig.isPending ? <Loader2 size={16} className="animate-spin" /> : <SlidersHorizontal size={16} />}
                    保存策略
                  </Button>
                  <Button tone="secondary" type="button" onClick={() => void syncKbConfigs()} disabled={mutations.syncConfigs.isPending}>
                    {mutations.syncConfigs.isPending ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
                    同步配置
                  </Button>
                </div>
              </form>
            ) : (
              <EmptyState
                icon={<SlidersHorizontal size={24} />}
                title="先选择一个资料库"
                description="创建或选择知识库后，可以在这里调整检索策略和重建标记。"
              />
            )}
          </div>
        </details>

        <section className="order-5 rounded-lg border border-line bg-white p-3" data-testid="knowledge-folder-details">
          <div className="flex flex-wrap items-start justify-between gap-3 rounded-lg bg-tint-mint px-3 py-3" data-testid="knowledge-folder-toggle">
            <div>
              <h2 className="text-base font-semibold text-ink">文件夹同步</h2>
              <p className="mt-1 text-sm text-slate-500">链接本地目录，按需同步新增资料。</p>
            </div>
            <Badge tone={activeKb ? "brand" : "neutral"}>{activeKb || "未选择"}</Badge>
          </div>
          <div className="mt-4 border-t border-line pt-4">
            <form className="grid gap-3 md:grid-cols-[1fr_auto]" onSubmit={linkFolder}>
              <FieldShell label="本地文件夹路径">
                <TextInput
                  value={folderPath}
                  onChange={(event) => setFolderPath(event.target.value)}
                  placeholder="例如 C:\Users\name\Documents\course"
                  data-testid="knowledge-folder-path"
                />
              </FieldShell>
              <div className="flex items-end">
                <Button
                  tone="secondary"
                  type="submit"
                  disabled={!activeKb || !folderPath.trim() || mutations.linkFolder.isPending}
                  data-testid="knowledge-folder-link"
                >
                  {mutations.linkFolder.isPending ? <Loader2 size={16} className="animate-spin" /> : <Link2 size={16} />}
                  链接
                </Button>
              </div>
            </form>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {(linkedFolders.data ?? []).map((folder) => (
                <motion.article
                  key={folder.id}
                  className="dt-interactive rounded-lg border border-line bg-white p-3 hover:border-brand-purple-300"
                  data-testid={`knowledge-folder-${folder.id}`}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2, ease: "easeOut" }}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-semibold text-ink">{folder.path}</p>
                      <p className="mt-1 text-sm text-slate-500">
                        {folder.file_count} 个文件 · {folder.added_at}
                      </p>
                    </div>
                    <Badge tone="neutral">{folder.id.slice(0, 8)}</Badge>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Button
                      tone="secondary"
                      className="min-h-9 text-xs"
                      onClick={() => void syncFolder(folder.id)}
                      disabled={mutations.syncFolder.isPending}
                      data-testid={`knowledge-folder-sync-${folder.id}`}
                    >
                      {mutations.syncFolder.isPending ? <Loader2 size={14} className="animate-spin" /> : <FolderSync size={14} />}
                      同步
                    </Button>
                    <Button
                      tone="danger"
                      className="min-h-9 text-xs"
                      data-testid={`knowledge-folder-unlink-${folder.id}`}
                      onClick={() => {
                        if (activeKb && window.confirm(`解除链接 ${folder.path}？`)) {
                          void mutations.unlinkFolder.mutateAsync({ kbName: activeKb, folderId: folder.id });
                        }
                      }}
                      disabled={mutations.unlinkFolder.isPending}
                    >
                      <Unlink size={14} />
                      解除
                    </Button>
                  </div>
                </motion.article>
              ))}
            </div>
            {activeKb && !linkedFolders.data?.length ? (
              <p className="mt-4 rounded-lg border border-dashed border-line bg-canvas p-4 text-sm leading-6 text-slate-500">
                当前知识库还没有链接文件夹。适合课程资料目录、同步盘目录或挂载卷。
              </p>
            ) : null}
          </div>
        </section>

        <section className="hidden order-3 rounded-lg border border-line bg-white p-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-ink">资料库</h2>
              <p className="mt-1 text-sm text-slate-500">为聊天、研究和题目生成提供统一上下文。</p>
            </div>
            <button
              type="button"
              onClick={() => void query.refetch()}
              className="inline-flex h-10 items-center gap-2 rounded-lg border border-line px-3 text-sm text-slate-600 hover:border-brand-purple-300 hover:text-brand-purple"
            >
              <RefreshCw size={16} />
              刷新
            </button>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {bases.map((kb) => (
              <motion.div
                key={kb.name}
                className="dt-interactive rounded-lg border border-line bg-white p-3 hover:border-brand-purple-300"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2, ease: "easeOut" }}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate font-semibold text-ink">{kb.name}</p>
                    <p className="mt-2 text-sm text-slate-500">{formatProgressStage(kb.status || "ready")}</p>
                  </div>
                  <Badge tone={kb.is_default ? "brand" : "neutral"}>{kb.is_default ? "默认" : "可选"}</Badge>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button
                    tone="secondary"
                    className="min-h-9 text-xs"
                    onClick={() => setSelectedKb(kb.name)}
                  >
                    选择
                  </Button>
                  <Button
                    tone="secondary"
                    className="min-h-9 text-xs"
                    onClick={() => void mutations.setDefault.mutateAsync(kb.name)}
                    disabled={kb.is_default || mutations.setDefault.isPending}
                  >
                    <Star size={14} />
                    设为默认
                  </Button>
                  <Button
                    tone="danger"
                    className="min-h-9 text-xs"
                    onClick={() => {
                      if (window.confirm(`删除知识库 ${kb.name}？`)) void mutations.remove.mutateAsync(kb.name);
                    }}
                    disabled={mutations.remove.isPending}
                  >
                    <Trash2 size={14} />
                    删除
                  </Button>
                </div>
              </motion.div>
            ))}
          </div>

          {!bases.length ? (
            <div className="mt-4">
              <EmptyState
                icon={<FileUp size={26} />}
                title="还没有知识库"
                description="先创建一个知识库并上传资料，聊天、研究和出题能力就能直接引用它。"
              />
            </div>
          ) : null}
        </section>

        <div className="hidden order-2 grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
          <section className="rounded-lg border border-line bg-white p-3">
            <h2 className="text-base font-semibold text-ink">创建知识库</h2>
            <form className="mt-4 grid gap-3" onSubmit={createKb}>
              <FieldShell label="知识库名称">
                <TextInput
                  value={createName}
                  onChange={(event) => setCreateName(event.target.value)}
                  placeholder="例如 calculus_notes"
                />
              </FieldShell>
              <FieldShell label="检索引擎">
                <SelectInput value={activeProvider} onChange={(event) => setRagProvider(event.target.value)}>
                  {providerOptions.length ? (
                    providerOptions.map((provider) => (
                      <option key={provider.name} value={provider.name}>
                        {provider.label || provider.name}
                      </option>
                    ))
                  ) : (
                    <option value="">使用默认</option>
                  )}
                </SelectInput>
              </FieldShell>
              <FieldShell label="初始资料" hint="支持 PDF、Markdown、文本等资料">
                <FileInput
                  multiple
                  onChange={(event) => setCreateFiles(Array.from(event.target.files ?? []))}
                  buttonLabel="选择资料"
                  emptyLabel="未选择资料"
                />
              </FieldShell>
              {createFiles.length ? <FileList files={createFiles} /> : null}
              <Button
                tone="primary"
                type="submit"
                disabled={!createName.trim() || !createFiles.length || mutations.create.isPending}
              >
                {mutations.create.isPending ? <Loader2 size={16} className="animate-spin" /> : <UploadCloud size={16} />}
                创建并索引
              </Button>
            </form>
          </section>

          <section className="rounded-lg border border-line bg-white p-3">
            <h2 className="text-base font-semibold text-ink">追加资料</h2>
            <form className="mt-4 grid gap-3" onSubmit={uploadToKb}>
              <FieldShell label="目标知识库">
                <SelectInput
                  value={activeKb}
                  onChange={(event) => setSelectedKb(event.target.value)}
                >
                  {bases.map((kb) => (
                    <option key={kb.name} value={kb.name}>
                      {kb.name}
                    </option>
                  ))}
                </SelectInput>
              </FieldShell>
              <FieldShell label="上传文件">
                <FileInput
                  multiple
                  onChange={(event) => setUploadFiles(Array.from(event.target.files ?? []))}
                  buttonLabel="选择文件"
                  emptyLabel="未选择文件"
                />
              </FieldShell>
              {uploadFiles.length ? <FileList files={uploadFiles} /> : null}
              <Button
                tone="secondary"
                type="submit"
                disabled={!activeKb || !uploadFiles.length || mutations.upload.isPending}
              >
                {mutations.upload.isPending ? <Loader2 size={16} className="animate-spin" /> : <FileUp size={16} />}
                上传并处理
              </Button>
            </form>
          </section>
        </div>

        <section
          className="order-6 rounded-lg border border-line bg-white p-3"
          data-testid="knowledge-progress-details"
        >
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-tint-lavender px-3 py-3" data-testid="knowledge-progress-toggle">
            <div>
              <h2 className="text-base font-semibold text-ink">索引进度</h2>
              <p className="mt-1 text-sm text-slate-500">导入资料后查看处理过程。</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge tone="brand">{progressStage}</Badge>
              <Badge tone={wsStatus === "live" ? "success" : wsStatus === "error" ? "danger" : "neutral"}>
                {formatWsStatus(wsStatus)}
              </Badge>
            </div>
          </div>
          <div className="mt-4 border-t border-line pt-4">
            <div className="mb-4 flex justify-end">
              <Button
                tone="secondary"
                className="min-h-9 text-xs"
                type="button"
                disabled={!activeKb || mutations.clearProgress.isPending}
                onClick={() => void clearActiveProgress()}
                data-testid="knowledge-progress-clear"
              >
                {mutations.clearProgress.isPending ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                清理进度
              </Button>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium text-ink">{progressMessage}</span>
              <span className="text-slate-500">{progressPercent}%</span>
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-sm bg-white">
              <motion.div
                className="h-full rounded-sm bg-brand-purple"
                initial={false}
                animate={{ width: `${progressPercent}%` }}
                transition={{ duration: 0.35, ease: "easeOut" }}
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>
          {taskMilestones.length ? (
            <div className="mt-4 rounded-lg border border-brand-purple-300 bg-tint-lavender p-3" data-testid="knowledge-task-milestones">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-semibold text-ink">关键进展</p>
                <Badge tone="brand">{taskMilestones.length} 步</Badge>
              </div>
              <div className="mt-3 grid gap-2">
                {taskMilestones.map((line, index) => (
                  <motion.div
                    key={`${line}-${index}`}
                    className="flex gap-2 rounded-md bg-white px-3 py-2 text-xs leading-5 text-slate-700"
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.16 }}
                  >
                    <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-sm bg-brand-purple" />
                    <span>{line}</span>
                  </motion.div>
                ))}
              </div>
            </div>
          ) : null}
          <details className="mt-4 rounded-lg border border-line bg-canvas p-3 [&>summary::-webkit-details-marker]:hidden" data-testid="knowledge-task-log-details">
            <summary className="dt-interactive flex cursor-pointer list-none items-center justify-between gap-3 rounded-md px-1 py-1 text-sm">
              <span className="font-medium text-ink">完整处理记录</span>
              <Badge tone="neutral">{taskLogs.length ? `${taskLogs.length} 条` : "暂无"}</Badge>
            </summary>
            <div className="dt-event-feed mt-3 max-h-56 overflow-y-auto rounded-lg bg-white p-3" data-testid="knowledge-task-logs">
              {taskLogs.length ? (
              <AnimatePresence initial={false}>
                {taskLogs.map((line) => (
                  <motion.p
                    key={line}
                    className="dt-event-row text-xs leading-5 text-slate-600"
                    initial={{ opacity: 0, y: -6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: 0.16 }}
                  >
                    <LogText line={line} />
                  </motion.p>
                ))}
              </AnimatePresence>
              ) : (
              <p className="text-sm text-slate-500">创建或上传资料后，任务日志会显示在这里。</p>
              )}
            </div>
          </details>
        </section>
      </div>
    </div>
  );
}

function KnowledgeStatusStrip({
  count,
  defaultName,
  configCount,
  refreshing,
  error,
}: {
  count: number;
  defaultName: string;
  configCount: string | number;
  refreshing: boolean;
  error: boolean;
}) {
  const items = [
    { label: "资料库", value: String(count), ok: count > 0 },
    { label: "默认", value: defaultName, ok: defaultName !== "未设置" },
    { label: "策略", value: String(configCount), ok: String(configCount) !== "0" },
    { label: "索引", value: refreshing ? "刷新中" : error ? "需检查" : "就绪", ok: !error },
  ];
  return (
    <section className="px-1" data-testid="knowledge-status-strip">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
        {items.map((item) => (
          <div key={item.label} className="flex min-w-0 items-center gap-1.5 text-xs">
            <span className={`h-1.5 w-1.5 shrink-0 ${item.ok ? "bg-emerald-500" : "bg-slate-300"}`} style={{ borderRadius: "50%" }} />
            <span className="shrink-0 text-slate-500">{item.label}</span>
            <span className="max-w-[190px] truncate font-medium text-ink">{item.value}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function KnowledgeDetailPanel({
  className = "",
  activeKb,
  detail,
  loading,
  onRefresh,
}: {
  className?: string;
  activeKb: string;
  detail?: KnowledgeBaseDetail;
  loading: boolean;
  onRefresh: () => void;
}) {
  const statistics = isRecord(detail?.statistics) ? detail.statistics : {};
  const metadata = isRecord(detail?.metadata) ? detail.metadata : {};
  const documentCount =
    readNumber(detail, "document_count") ??
    readNumber(statistics, "document_count") ??
    readNumber(statistics, "documents") ??
    (Array.isArray(detail?.documents) ? detail.documents.length : undefined);
  const fileCount =
    readNumber(detail, "file_count") ??
    readNumber(statistics, "file_count") ??
    readNumber(statistics, "files") ??
    (Array.isArray(detail?.files) ? detail.files.length : undefined);
  const path = readString(detail, "path") || readString(metadata, "path") || activeKb || "-";
  const status = detail?.status || (loading ? "loading" : activeKb ? "ready" : "idle");
  const summaryPayload = Object.keys(metadata).length ? metadata : statistics;
  const summaryItems = summarizeKnowledgePayload(summaryPayload);

  return (
    <details className={`rounded-lg border border-line bg-white p-3 [&>summary::-webkit-details-marker]:hidden ${className}`} data-testid="knowledge-detail-panel">
      <summary className="dt-interactive flex cursor-pointer list-none flex-wrap items-start justify-between gap-3 rounded-lg px-1 py-1">
        <div>
          <h2 className="text-base font-semibold text-ink">知识库详情</h2>
          <p className="mt-1 text-sm text-slate-500">
            文件、文档和索引状态，需要排查时再展开。
          </p>
        </div>
        <Badge tone={activeKb ? "brand" : "neutral"}>{activeKb || "未选择"}</Badge>
      </summary>
      <div className="mt-4 border-t border-line pt-4">
        <div className="flex justify-end">
          <Button tone="secondary" className="min-h-9 text-xs" type="button" disabled={!activeKb || loading} onClick={onRefresh}>
            {loading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            刷新详情
          </Button>
        </div>
        {activeKb ? (
          <>
          <div className="mt-4 grid gap-3 text-sm md:grid-cols-4">
            <ConfigFact label="资料库" value={activeKb} />
            <ConfigFact label="状态" value={formatProgressStage(status)} tone={status === "error" ? "warning" : undefined} />
            <ConfigFact label="文档数" value={formatOptionalCount(documentCount)} />
            <ConfigFact label="文件数" value={formatOptionalCount(fileCount)} />
          </div>
          <div className="mt-4 grid gap-3 border-t border-line pt-4 md:grid-cols-[minmax(0,1fr)_240px]">
            <div className="min-w-0">
              <p className="text-xs text-slate-500">路径</p>
              <p className="mt-1 truncate text-sm font-medium text-ink">{path}</p>
              {detail?.description ? <p className="mt-2 text-sm leading-6 text-slate-600">{detail.description}</p> : null}
            </div>
            <div>
              <p className="text-xs text-slate-500">检索引擎</p>
              <p className="mt-1 truncate text-sm font-medium text-ink">{knowledgeProviderLabel(detail?.rag_provider || "llamaindex")}</p>
            </div>
          </div>
          {summaryItems.length ? (
            <div className="mt-4 rounded-lg border border-line bg-canvas p-3" data-testid="knowledge-summary-panel">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-ink">索引摘要</p>
                  <p className="mt-1 text-xs text-slate-500">只展示运行所需的关键信息，完整配置留在后端文件中。</p>
                </div>
                <Badge tone="neutral">{summaryItems.length} 项</Badge>
              </div>
              <div className="mt-3 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
                {summaryItems.map((item) => (
                  <ConfigFact key={item.key} label={item.label} value={item.value} />
                ))}
              </div>
            </div>
          ) : null}
          </>
        ) : (
          <div className="mt-4">
            <EmptyState icon={<Database size={24} />} title="等待选择知识库" description="选择或创建知识库后，这里会显示文件、文档和索引状态。" />
          </div>
        )}
      </div>
    </details>
  );
}

function KnowledgeRuntimePanel({
  className = "",
  health,
  loading,
  defaultKbName,
  onRefresh,
}: {
  className?: string;
  health?: KnowledgeHealth;
  loading: boolean;
  defaultKbName: string;
  onRefresh: () => void;
}) {
  const ok = health?.status === "ok";
  return (
    <details className={`rounded-lg border border-line bg-white p-3 [&>summary::-webkit-details-marker]:hidden ${className}`}>
      <summary className="dt-interactive flex cursor-pointer list-none flex-wrap items-start justify-between gap-3 rounded-lg px-1 py-1">
        <div>
          <div className="flex items-center gap-2">
            <Database size={18} className="text-brand-purple" />
            <h2 className="text-base font-semibold text-ink">知识库运行面板</h2>
          </div>
          <p className="mt-1 text-sm leading-6 text-slate-500">
            默认资料库和检索状态，需要检查时再展开。
          </p>
        </div>
        <Badge tone={ok ? "success" : "neutral"}>{health?.status || "读取中"}</Badge>
      </summary>
      <div className="mt-4 border-t border-line pt-4">
        <div className="flex justify-end">
        <Button tone="secondary" type="button" onClick={onRefresh}>
          {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
          刷新状态
        </Button>
        </div>
      <div className="mt-4 grid gap-3 md:grid-cols-4">
        <ConfigFact label="状态" value={health?.status || "unknown"} tone={ok ? "success" : "warning"} />
        <ConfigFact label="默认知识库" value={defaultKbName} />
        <ConfigFact label="配置" value={health?.config_exists ? "已找到" : "未确认"} tone={health?.config_exists ? "success" : "warning"} />
        <ConfigFact label="目录" value={health?.base_dir_exists ? "可访问" : "未确认"} tone={health?.base_dir_exists ? "success" : "warning"} />
      </div>
      {health?.error ? (
        <p className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm leading-6 text-red-700">{health.error}</p>
      ) : null}
      {health?.base_dir || health?.config_file ? (
        <div className="mt-4 grid gap-2 text-xs leading-5 text-slate-500">
          {health.base_dir ? <p className="truncate">资料目录：{health.base_dir}</p> : null}
          {health.config_file ? <p className="truncate">配置文件：{health.config_file}</p> : null}
        </div>
      ) : null}
      </div>
    </details>
  );
}

function formatTaskEvent(label: "log" | "complete" | "failed" | "message", raw: string) {
  const payload = parseTaskPayload(raw);
  if (payload) {
    if (payload.line) return withLegacyText(formatKnowledgeLogLine(String(payload.line), label), String(payload.line));
    const labelText = formatTaskLabel(label);
    const legacyLabel = label;
    if (payload.detail) return withLegacyText(`${labelText}：${formatKnowledgeLogLine(String(payload.detail), label)}`, `${legacyLabel}: ${payload.detail}`);
    const serialized = JSON.stringify(payload);
    return withLegacyText(`${labelText}：收到任务更新`, `${legacyLabel}: ${serialized}`);
  }
  return raw ? withLegacyText(formatKnowledgeLogLine(raw, label), raw) : formatTaskLabel(label);
}

function parseTaskPayload(raw: string) {
  try {
    return JSON.parse(raw) as KnowledgeTaskPayload;
  } catch {
    return null;
  }
}

function formatTaskLabel(label: "log" | "complete" | "failed" | "message") {
  return {
    log: "日志",
    complete: "完成",
    failed: "失败",
    message: "消息",
  }[label];
}

function formatWsProgress(progress: KnowledgeProgress) {
  const rawState = progress.stage || progress.status || "progress";
  const state = formatProgressStage(rawState);
  const percent = typeof progress.percent === "number" ? ` ${clampPercent(progress.percent)}%` : "";
  const message = progress.message ? ` ${formatKnowledgeLogLine(progress.message)}` : "";
  const legacyMessage = progress.message ? ` ${progress.message}` : "";
  return withLegacyText(`进度 ${state}${percent}${message}`.trim(), `ws: ${rawState}${percent}${legacyMessage}`.trim());
}

function formatWsStatus(status: KnowledgeWsStatus) {
  return {
    idle: "轮询",
    connecting: "连接中",
    live: "实时同步",
    closed: "同步完成",
    error: "同步异常",
  }[status];
}

function LogText({ line }: { line: string }) {
  return <>{visibleKnowledgeLogText(line)}</>;
}

function visibleKnowledgeLogText(line: string) {
  const [visible] = line.split(LEGACY_TEXT_SEPARATOR);
  return visible || "";
}

function summarizeKnowledgeTaskLogs(lines: string[]) {
  const milestones: string[] = [];
  for (const line of lines) {
    const visible = visibleKnowledgeLogText(line).trim();
    if (!visible || isNoisyKnowledgeLog(visible)) continue;
    if (milestones[milestones.length - 1] !== visible) milestones.push(visible);
  }
  return milestones.slice(-4);
}

function isNoisyKnowledgeLog(value: string) {
  const lower = value.toLowerCase();
  if (lower.includes("heartbeat")) return true;
  if (/已连接.*(任务流|进度通道)/.test(value)) return true;
  if (/进度通道保持连接/.test(value)) return true;
  if (/收到(任务|进度)更新/.test(value)) return true;
  return false;
}

function formatProgressStage(stage: string | undefined) {
  const value = String(stage || "").toLowerCase();
  return (
    {
      idle: "空闲",
      not_started: "未开始",
      ready: "就绪",
      loading: "读取中",
      progress: "处理中",
      processing: "处理中",
      parsing: "解析中",
      indexing: "索引中",
      reindex: "待重建",
      complete: "完成",
      completed: "完成",
      done: "完成",
      failed: "失败",
      error: "异常",
      cancelled: "已取消",
      canceled: "已取消",
    }[value] || String(stage || "未知")
  );
}

function formatProgressMessage(progress: KnowledgeProgress | undefined | null, activeKb: string, hasTaskContext: boolean) {
  const state = String(progress?.stage || progress?.status || "").toLowerCase();
  if (!progress) return activeKb || "暂无任务";
  if (state === "not_started") return hasTaskContext ? "等待索引任务更新..." : "暂无索引任务";
  return progress.message ? formatKnowledgeLogLine(progress.message) : activeKb || "暂无任务";
}

function formatKnowledgeWsMessage(payload: KnowledgeWsMessage) {
  if (payload.data) return formatWsProgress(payload.data);
  if (payload.message) return withLegacyText(`进度更新：${formatKnowledgeLogLine(payload.message)}`, `进度更新：${payload.message}`);
  if (payload.type === "complete" || payload.type === "failed" || payload.type === "log" || payload.type === "message") {
    return `进度更新：${formatTaskLabel(payload.type)}`;
  }
  if (String(payload.type || "").toLowerCase() === "heartbeat") return "进度更新：进度通道保持连接";
  if (payload.type) return withLegacyText("进度更新：收到任务状态", `进度更新：${payload.type}`);
  return "收到进度更新";
}

function formatKnowledgeWsText(raw: string) {
  const value = raw.trim();
  if (!value) return "收到进度更新";
  if (value.startsWith("{") || value.startsWith("[")) return "收到进度更新";
  return withLegacyText(`进度更新：${formatKnowledgeLogLine(value)}`, `进度更新：${value}`);
}

function formatKnowledgeLogLine(raw: string, label?: "log" | "complete" | "failed" | "message") {
  const original = String(raw || "").trim();
  if (!original) return formatTaskLabel(label || "message");
  const text = original.replace(/^\[[^\]]+\]\s*/, "").trim();
  const lower = text.toLowerCase();
  const processed = text.match(/^successfully processed\s+(\d+)\s+files?\s+for\s+'([^']+)'/i);
  if (processed) return `完成：已处理 ${processed[1]} 个文件（${processed[2]}）`;
  const processedFiles = text.match(/^processed\s+(\d+)\s+file\(s\)\s+for\s+'([^']+)'/i);
  if (processedFiles) return `已处理 ${processedFiles[1]} 个文件：${processedFiles[2]}`;
  const processingFiles = text.match(/^processing\s+(\d+)\s+file\(s\)\s+for\s+kb\s+'([^']+)'/i);
  if (processingFiles) return `正在处理 ${processingFiles[1]} 个文件：${processingFiles[2]}`;
  const indexed = text.match(/^indexed\s+(\d+)\s+file\(s\)/i);
  if (indexed) return `已写入索引：${indexed[1]} 个文件`;
  const processedByProvider = text.match(/^processed\s+\(([^)]+)\):\s+(.+)/i);
  if (processedByProvider) return `已索引：${processedByProvider[2]}`;
  const indexing = text.match(/^indexing\s+\(([^)]+)\)\s+(.+?)(\s+\([^)]+\))?$/i);
  if (indexing) return `正在索引：${indexing[2]}${indexing[3] || ""}`;
  const staged = text.match(/^staged\s+(\d+)\s+new\s+file\(s\)/i);
  if (staged) return `已暂存 ${staged[1]} 个新文件`;
  const recovering = text.match(/^recovering staged file:\s+(.+)/i);
  if (recovering) return `恢复待处理文件：${recovering[1]}`;
  const validating = text.match(/^validating documents for\s+'([^']+)'/i);
  if (validating) return `正在校验资料：${validating[1]}`;
  const found = text.match(/^found\s+(\d+)\s+documents?,\s+starting to process/i);
  if (found) return `找到 ${found[1]} 份资料，开始处理`;
  const initializing = text.match(/^initializing knowledge base\s+'([^']+)'/i);
  if (initializing) return `正在初始化资料库：${initializing[1]}`;
  const validationFailed = text.match(/^validation failed for file\s+'([^']+)'/i);
  if (validationFailed) return `文件校验未通过：${validationFailed[1]}`;
  if (lower.includes("mime type validation failed")) return "文件类型校验未通过，请确认资料格式";
  if (lower.includes("rag pipeline returned failure")) return "索引管线处理失败，请检查资料格式或模型配置";
  if (lower.includes("initialization failed")) return "资料库初始化失败";
  if (lower.includes("document processing failed") || lower.includes("failed to process documents")) return "资料处理失败，请检查文件内容";
  if (lower.includes("error processing documents")) return "资料处理失败，请稍后重试";
  if (lower.includes("real-time progress") && lower.includes("unavailable")) return "实时进度暂时不可用，继续自动刷新";
  if (lower.includes("starting to process documents with")) return "正在调用解析与索引管线...";
  if (lower.includes("extracting numbered items")) return "正在整理题目结构...";
  if (lower.includes("skipping numbered items extraction")) return "已跳过题号提取";
  if (lower.includes("saved") && lower.includes("preparing index")) return "资料已保存，正在准备索引";
  if (lower.includes("knowledge base created")) return "资料库已创建";
  if (lower.includes("upload complete")) return "上传完成";
  if (lower.includes("folder sync complete")) return "文件夹同步完成";
  const cleared = text.match(/^progress cleared for\s+(.+)/i);
  if (cleared) return `已清理进度：${cleared[1]}`;
  if (lower.includes("ws parsing files")) return "正在解析文件";
  if (lower.includes("ws index complete")) return "索引已完成";
  if (lower === "heartbeat") return "进度通道保持连接";
  return text;
}

function isTerminalProgress(progress: KnowledgeProgress) {
  const state = String(progress.stage || progress.status || "").toLowerCase();
  return ["complete", "completed", "done", "failed", "error", "cancelled", "canceled"].includes(state);
}

function clampPercent(value: number | undefined) {
  return Math.max(0, Math.min(100, Math.round(value ?? 0)));
}

function formatEmbeddingLabel(config: KnowledgeConfig | undefined) {
  if (!config?.embedding_model && !config?.embedding_dim) return "随全局配置";
  const model = config.embedding_model ? String(config.embedding_model) : "当前模型";
  return config.embedding_dim ? `${model} / ${config.embedding_dim}D` : model;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function readNumber(record: unknown, key: string) {
  if (!isRecord(record)) return undefined;
  const value = record[key];
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function readString(record: unknown, key: string) {
  if (!isRecord(record)) return "";
  const value = record[key];
  return typeof value === "string" ? value : "";
}

function formatOptionalCount(value: number | undefined) {
  return typeof value === "number" ? String(value) : "-";
}

function knowledgeProviderLabel(value: unknown) {
  const raw = String(value || "").trim();
  if (!raw) return "智能索引";
  const normalized = raw.toLowerCase();
  if (normalized.includes("llamaindex")) return "智能索引";
  if (normalized.includes("mineru")) return "文档解析索引";
  return raw;
}

function summarizeKnowledgePayload(payload: Record<string, unknown>) {
  const preferredKeys = [
    "rag_provider",
    "provider",
    "embedding_model",
    "embedding_dim",
    "embedding_dimension",
    "chunk_count",
    "node_count",
    "document_count",
    "file_count",
    "updated_at",
    "created_at",
  ];
  const seen = new Set<string>();
  const items: Array<{ key: string; label: string; value: string }> = [];
  const add = (key: string) => {
    if (seen.has(key) || !(key in payload)) return;
    const value = key === "rag_provider" || key === "provider" ? knowledgeProviderLabel(payload[key]) : formatKnowledgeSummaryValue(payload[key]);
    if (!value) return;
    seen.add(key);
    items.push({ key, label: labelKnowledgeSummaryField(key), value });
  };
  preferredKeys.forEach(add);
  Object.keys(payload)
    .filter((key) => !seen.has(key))
    .forEach(add);
  return items.slice(0, 6);
}

function labelKnowledgeSummaryField(key: string) {
  const labels: Record<string, string> = {
    rag_provider: "检索引擎",
    provider: "检索引擎",
    embedding_model: "向量模型",
    embedding_dim: "向量维度",
    embedding_dimension: "向量维度",
    chunk_count: "切片数",
    node_count: "索引节点",
    document_count: "文档数",
    file_count: "文件数",
    updated_at: "最近更新",
    created_at: "创建时间",
    path: "路径",
  };
  return labels[key] || key.replace(/_/g, " ");
}

function formatKnowledgeSummaryValue(value: unknown) {
  if (value === null || value === undefined || value === "") return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value === "boolean") return value ? "是" : "否";
  if (Array.isArray(value)) return `${value.length} 项`;
  if (isRecord(value)) return `${Object.keys(value).length} 项`;
  return "";
}

function ConfigFact({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "success" | "warning";
}) {
  return (
    <div className="min-w-0">
      <p className="text-xs text-slate-500">{label}</p>
      <p className={tone === "warning" ? "mt-1 truncate font-semibold text-amber-700" : "mt-1 truncate font-semibold text-ink"}>
        {value}
      </p>
    </div>
  );
}

function FileList({ files }: { files: File[] }) {
  return (
    <div className="dt-event-feed rounded-lg p-3 text-xs leading-5 text-slate-600">
      {files.slice(0, 5).map((file) => (
        <p key={`${file.name}-${file.size}`} className="truncate">
          {file.name} · {formatBytes(file.size)}
        </p>
      ))}
      {files.length > 5 ? <p>还有 {files.length - 5} 个文件</p> : null}
    </div>
  );
}

function formatBytes(size: number) {
  if (size >= 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`;
  if (size >= 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${size} B`;
}

function Header({
  eyebrow,
  title,
  legacyTitle,
  description,
}: {
  eyebrow: string;
  title: string;
  legacyTitle?: string;
  description: string;
}) {
  return (
    <NotionProductHero
      eyebrow={eyebrow}
      title={title}
      legacyTitle={legacyTitle}
      description={description}
      accent="blue"
      imageSrc="/illustrations/sparkweave-workspace.svg"
      imageAlt="资料库工作台预览"
      people="notes"
      previewTitle="资料先放进来"
      previewDescription="文档会转成可引用的课程上下文，后续问答和导学会优先使用。"
      tiles={[
        { label: "导入", helper: "上传材料", tone: "sky" },
        { label: "索引", helper: "建立引用", tone: "yellow" },
        { label: "使用", helper: "问答导学共用", tone: "lavender" },
      ]}
    />
  );
}
