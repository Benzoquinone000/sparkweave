import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, GitBranch, LayoutList, Loader2, PlugZap, RefreshCw, RotateCcw, Rocket, Save, Settings2, XCircle } from "lucide-react";
import { useLocation } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FieldShell, SelectInput, TextArea, TextInput } from "@/components/ui/Field";
import {
  cancelSettingsServiceTest,
  completeSetupTour,
  getApiBase,
  openSettingsServiceTestEvents,
  startSettingsServiceTest,
} from "@/lib/api";
import type {
  EndpointProfile,
  ModelCatalog,
  ProviderChoice,
  RuntimeTopology,
  ServiceCatalog,
  SettingsResponse,
  SetupTourReopenResponse,
  SetupTourStatus,
  SidebarSettings,
  SystemStatus,
  SystemTestResponse,
} from "@/lib/types";
import {
  useReopenSetupTour,
  useRuntimeTopology,
  useServiceTest,
  useSettings,
  useSettingsCatalog,
  useSettingsMutations,
  useSetupTourStatus,
  useSidebarSettings,
  useSystemStatus,
  useThemes,
} from "@/hooks/useApiQueries";

const SERVICES = [
  { id: "llm" as const, label: "问答模型" },
  { id: "embedding" as const, label: "向量模型" },
  { id: "search" as const, label: "联网搜索" },
];

const CUSTOM_MODEL_VALUE = "__sparkweave_custom_model__";

const SYSTEM_PROBES = [
  { id: "llm" as const, label: "问答模型", detail: "测试问答模型" },
  { id: "embeddings" as const, label: "向量模型", detail: "测试向量模型" },
  { id: "search" as const, label: "联网搜索", detail: "测试搜索服务" },
];

type ServiceId = (typeof SERVICES)[number]["id"];
type SystemProbeId = (typeof SYSTEM_PROBES)[number]["id"];
type TestStatus = "idle" | "running" | "completed" | "failed" | "cancelled";
type IflytekLlmAuthMode = "api_password" | "ak_sk";

type LlmForm = {
  binding: string;
  baseUrl: string;
  apiKey: string;
  model: string;
  iflytekAuthMode: IflytekLlmAuthMode;
  iflytekAppId: string;
  iflytekApiSecret: string;
};

type EmbeddingForm = LlmForm & {
  dimension: string;
  iflytekAppId: string;
  iflytekApiSecret: string;
  iflytekDomain: string;
};

type SearchForm = {
  provider: string;
  baseUrl: string;
  apiKey: string;
};

export function SettingsPage() {
  const location = useLocation();
  const status = useSystemStatus();
  const runtimeTopology = useRuntimeTopology();
  const settings = useSettings();
  const catalogSnapshot = useSettingsCatalog();
  const themes = useThemes();
  const sidebar = useSidebarSettings();
  const tourStatus = useSetupTourStatus();
  const reopenTour = useReopenSetupTour();
  const settingsMutations = useSettingsMutations();
  const serviceProbe = useServiceTest();
  const [lastResult, setLastResult] = useState<string>("");
  const [probeResults, setProbeResults] = useState<Partial<Record<SystemProbeId, SystemTestResponse>>>({});
  const [activeProbe, setActiveProbe] = useState<SystemProbeId | null>(null);
  const [testLogs, setTestLogs] = useState<string[]>([]);
  const [testStatus, setTestStatus] = useState<TestStatus>("idle");
  const [activeService, setActiveService] = useState<ServiceId | null>(null);
  const [activeRunId, setActiveRunId] = useState("");
  const [tourCompleted, setTourCompleted] = useState(false);
  const [tourPending, setTourPending] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const isTourMode = useMemo(() => {
    const search = location.search as Record<string, unknown> | string | undefined;
    if (search && typeof search === "object" && "tour" in search) {
      return String(search.tour) === "true";
    }
    if (typeof window === "undefined") return false;
    return new URLSearchParams(window.location.search).get("tour") === "true";
  }, [location.search]);

  useEffect(() => () => eventSourceRef.current?.close(), []);

  const appendTestLog = (line: string) => {
    setTestLogs((current) => [...current, line].slice(-80));
  };

  const runTest = async (service: ServiceId) => {
    eventSourceRef.current?.close();
    setActiveService(service);
    setActiveRunId("");
    setTestLogs([]);
    setTestStatus("running");
    setLastResult("");
    try {
      const payload = await startSettingsServiceTest({
        service,
        catalog: settings.data?.catalog,
      });
      setActiveRunId(payload.run_id);
      appendTestLog(`检测任务：${payload.run_id}`);
      const source = openSettingsServiceTestEvents({ service, runId: payload.run_id });
      let finished = false;
      eventSourceRef.current = source;
      source.onmessage = (event) => {
        const data = JSON.parse(event.data) as { type?: TestStatus | string; message?: string; [key: string]: unknown };
        const kind = data.type || "info";
        appendTestLog(`${formatTestEventKind(kind)}：${data.message || JSON.stringify(data)}`);
        if (kind === "completed" || kind === "failed") {
          finished = true;
          source.close();
          setTestStatus(kind);
          setLastResult(`${service}: ${data.message || kind}`);
        }
      };
      source.onerror = () => {
        if (!finished && eventSourceRef.current === source) {
          appendTestLog("[error] 实时检测中断");
          setTestStatus("failed");
        }
        source.close();
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : "测试失败";
      appendTestLog(`失败：${message}`);
      setTestStatus("failed");
      setLastResult(`${service}: ${message}`);
    }
  };

  const cancelTest = async () => {
    if (!activeService || !activeRunId) return;
    eventSourceRef.current?.close();
    await cancelSettingsServiceTest({ service: activeService, runId: activeRunId });
    setTestStatus("cancelled");
    appendTestLog("[cancelled] 已取消当前服务检测");
  };

  const runProbe = async (service: SystemProbeId) => {
    setActiveProbe(service);
    setLastResult("");
    try {
      const result = await serviceProbe.mutateAsync(service);
      setProbeResults((current) => ({ ...current, [service]: result }));
      setLastResult(`${service}: ${result.message}`);
    } catch (error) {
      const result = {
        success: false,
        message: error instanceof Error ? error.message : "即时探针失败",
        error: error instanceof Error ? error.message : "即时探针失败",
      };
      setProbeResults((current) => ({ ...current, [service]: result }));
      setLastResult(`${service}: ${result.message}`);
    } finally {
      setActiveProbe(null);
    }
  };

  const completeTour = async (catalog: ModelCatalog, ui: Partial<SettingsResponse["ui"]>) => {
    setTourPending(true);
    setLastResult("");
    try {
      const result = await completeSetupTour({
        catalog,
        test_results: {
          llm: String(status.data?.llm?.status || "pending"),
          embedding: String(status.data?.embeddings?.status || "pending"),
          search: String(status.data?.search?.status || "optional"),
        },
      });
      await settingsMutations.updateUi.mutateAsync(ui);
      setTourCompleted(true);
      void tourStatus.refetch();
      setLastResult(result.message || "启动向导已完成，SparkWeave 将很快重启。");
    } catch (error) {
      setLastResult(error instanceof Error ? error.message : "启动向导失败。");
    } finally {
      setTourPending(false);
    }
  };

  return (
    <div className="h-full overflow-y-auto px-4 py-4 pb-24 lg:px-5 lg:pb-5">
      <div className="mx-auto max-w-[960px] space-y-5">
        <motion.section
          className="dt-page-header"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22, ease: "easeOut" }}
        >
          <p className="dt-page-eyebrow">设置</p>
          <h1 className="mt-1 text-xl font-semibold text-ink" aria-label="连接与服务设置">
            服务设置
          </h1>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-600">
            管理模型、搜索和界面偏好。
            <span className="dt-test-legacy">当前 API：{getApiBase()}</span>
          </p>
        </motion.section>

        {isTourMode ? (
          <section className="rounded-lg border border-teal-200 bg-teal-50 p-4">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white text-brand-teal">
                  <Rocket size={19} />
                </div>
                <div>
                  <h2 className="font-semibold text-ink">启动向导</h2>
                  <span className="dt-test-legacy">Setup Tour</span>
                  <p className="mt-1 text-sm leading-6 text-slate-600">
                    配置问答模型、向量模型和可选搜索服务，完成后会启动 SparkWeave。
                  </p>
                </div>
              </div>
              <Badge tone={tourCompleted ? "success" : "brand"}>{tourCompleted ? "已完成" : "待完成"}</Badge>
            </div>
          </section>
        ) : null}

        <ServiceStatusStrip status={status.data} />

        {settings.data ? (
          <>
            <SettingsCatalogEditor
              settings={settings.data}
              pending={settingsMutations.saveCatalog.isPending || settingsMutations.applyCatalog.isPending || settingsMutations.updateUi.isPending}
              tourMode={isTourMode}
              tourCompleted={tourCompleted}
              tourPending={tourPending}
              onSave={async (catalog, ui) => {
                await settingsMutations.saveCatalog.mutateAsync(catalog);
                await settingsMutations.applyCatalog.mutateAsync(catalog);
                await settingsMutations.updateUi.mutateAsync(ui);
                setLastResult("配置已保存并应用到运行时。");
              }}
              onCompleteTour={completeTour}
            />
            <WorkbenchPreferences
              key={settingsPreferenceKey(settings.data, sidebar.data)}
              settings={settings.data}
              themes={themes.data?.themes ?? []}
              sidebar={sidebar.data}
              pending={
                settingsMutations.updateTheme.isPending ||
                settingsMutations.updateLanguage.isPending ||
                settingsMutations.updateSidebarDescription.isPending ||
                settingsMutations.updateSidebarNavOrder.isPending ||
                settingsMutations.resetUi.isPending
              }
              onSave={async (input) => {
                await settingsMutations.updateTheme.mutateAsync(input.theme);
                await settingsMutations.updateLanguage.mutateAsync(input.language);
                await settingsMutations.updateSidebarDescription.mutateAsync(input.description);
                await settingsMutations.updateSidebarNavOrder.mutateAsync(input.navOrder);
                setLastResult("工作台偏好已保存。");
              }}
              onReset={async () => {
                await settingsMutations.resetUi.mutateAsync();
                setLastResult("界面偏好已重置为默认值。");
              }}
            />
          </>
        ) : (
          <section className="rounded-lg border border-line bg-white p-3">
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Loader2 size={16} className="animate-spin" />
              正在读取配置
            </div>
          </section>
        )}

        <AnimatePresence>
          {lastResult ? (
            <motion.p
              className="rounded-lg border border-teal-200 bg-teal-50 p-3 text-sm text-slate-600"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.18 }}
              data-testid="settings-result"
            >
              {lastResult}
            </motion.p>
          ) : null}
        </AnimatePresence>

        <details
          className="rounded-lg border border-line bg-white p-3 [&>summary::-webkit-details-marker]:hidden"
          data-testid="settings-diagnostics"
          open={isTourMode}
        >
          <summary
            className="dt-interactive flex cursor-pointer list-none items-center justify-between gap-3 rounded-lg px-1 py-1"
            data-testid="settings-diagnostics-toggle"
          >
            <span>
              <span className="block text-base font-semibold text-ink">检测与运行信息</span>
              <span className="mt-1 block text-sm text-slate-500">模型不可用或需要排查时再打开。</span>
            </span>
            <Badge tone="neutral">按需查看</Badge>
          </summary>

          <div className="mt-4 space-y-4">
            <SystemProbePanel
              results={probeResults}
              activeProbe={activeProbe}
              pending={serviceProbe.isPending}
              onRun={(service) => void runProbe(service)}
            />

            <section className="rounded-lg border border-line bg-white p-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <PlugZap size={18} className="text-brand-blue" />
                  <h2 className="text-base font-semibold text-ink" aria-label="服务连通性测试">
                    连接测试
                  </h2>
                </div>
                {testStatus === "running" ? (
                  <Button
                    tone="danger"
                    onClick={() => void cancelTest()}
                    disabled={!activeRunId}
                    data-testid="settings-test-cancel"
                  >
                    <XCircle size={16} />
                    取消检测
                  </Button>
                ) : null}
              </div>
              <div className="mt-4 grid gap-2 md:grid-cols-3">
                {SERVICES.map((service) => (
                  <motion.button
                    key={service.id}
                    type="button"
                    onClick={() => void runTest(service.id)}
                    disabled={testStatus === "running"}
                    data-testid={`settings-test-${service.id}`}
                    className="dt-interactive flex min-h-16 items-center justify-between gap-3 rounded-lg border border-line bg-white p-3 text-left transition hover:border-teal-200 hover:bg-canvas disabled:opacity-60"
                    whileHover={testStatus === "running" ? undefined : { y: -2 }}
                    whileTap={testStatus === "running" ? undefined : { scale: 0.99 }}
                  >
                    <span className="font-semibold text-ink">{service.label}</span>
                    <span className="inline-flex shrink-0 items-center gap-2 text-sm text-slate-500">
                      {testStatus === "running" && activeService === service.id ? (
                        <Loader2 className="animate-spin" size={15} />
                      ) : (
                        <CheckCircle2 size={15} />
                      )}
                      开始检测
                    </span>
                  </motion.button>
                ))}
              </div>
              <div
                className="dt-event-feed mt-4 min-h-32 rounded-lg p-3 text-xs leading-6"
                data-testid="settings-test-logs"
              >
                {testLogs.length ? (
                  <AnimatePresence initial={false}>
                    {testLogs.map((line, index) => (
                      <motion.p
                        key={`${index}-${line.slice(0, 10)}`}
                        initial={{ opacity: 0, y: -4 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -4 }}
                        transition={{ duration: 0.16 }}
                        className="dt-event-row font-mono"
                      >
                        {line}
                      </motion.p>
                    ))}
                  </AnimatePresence>
                ) : (
                  <p className="text-slate-500">点击上方服务后，这里会显示检测进度。</p>
                )}
              </div>
            </section>

            <RuntimeTopologyPanel topology={runtimeTopology.data} loading={runtimeTopology.isLoading} />

            <CatalogSnapshotPanel
              catalog={catalogSnapshot.data?.catalog}
              loading={catalogSnapshot.isLoading}
              onRefresh={() => void catalogSnapshot.refetch()}
            />

            <SetupTourStatusPanel
              status={tourStatus.data}
              loading={tourStatus.isLoading}
              pending={reopenTour.isPending}
              result={reopenTour.data}
              onReopen={async () => {
                try {
                  const result = await reopenTour.mutateAsync();
                  setLastResult(`${result.message} ${result.command}`);
                } catch (error) {
                  setLastResult(error instanceof Error ? error.message : "无法重新打开启动向导。");
                }
              }}
            />
          </div>
        </details>
      </div>
    </div>
  );
}

function formatTestEventKind(kind: string) {
  return (
    {
      info: "信息",
      log: "日志",
      progress: "进度",
      completed: "完成",
      failed: "失败",
      error: "异常",
      cancelled: "已取消",
    }[kind] || kind
  );
}

function ServiceStatusStrip({ status }: { status?: SystemStatus }) {
  const items = [
    {
      label: "服务",
      value: status?.backend?.status || "未连接",
      ok: status?.backend?.status === "online",
    },
    {
      label: "问答",
      value: status?.llm?.model || status?.llm?.status || "未配置",
      ok: status?.llm?.status === "configured" || Boolean(status?.llm?.model),
      error: status?.llm?.error,
    },
    {
      label: "向量",
      value: status?.embeddings?.model || status?.embeddings?.status || "未配置",
      ok: status?.embeddings?.status === "configured" || Boolean(status?.embeddings?.model),
      error: status?.embeddings?.error,
    },
    {
      label: "搜索",
      value: status?.search?.provider || status?.search?.status || "可选",
      ok: status?.search?.status === "configured" || Boolean(status?.search?.provider),
      error: status?.search?.error,
    },
  ];
  return (
    <section className="px-1">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
        {items.map((item) => (
          <div key={item.label} className="flex min-w-0 items-center gap-1.5 text-xs">
            <span className={`h-1.5 w-1.5 shrink-0 rounded-sm ${item.error ? "bg-brand-red" : item.ok ? "bg-emerald-500" : "bg-slate-300"}`} />
            <span className="shrink-0 text-slate-500">{item.label}</span>
            <span className="max-w-[180px] truncate font-medium text-ink">{item.error || item.value}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function SystemProbePanel({
  results,
  activeProbe,
  pending,
  onRun,
}: {
  results: Partial<Record<SystemProbeId, SystemTestResponse>>;
  activeProbe: SystemProbeId | null;
  pending: boolean;
  onRun: (service: SystemProbeId) => void;
}) {
  return (
    <section className="rounded-lg border border-line bg-white p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <PlugZap size={18} className="text-brand-teal" />
            <h2 className="text-base font-semibold text-ink">快速检测</h2>
          </div>
          <p className="mt-1 text-sm leading-6 text-slate-500">
            保存配置后，用这里确认模型、向量和搜索是否可用。
          </p>
        </div>
        <Badge tone="brand">一键检测</Badge>
      </div>

      <div className="mt-4 grid gap-2">
        {SYSTEM_PROBES.map((probe) => {
          const result = results[probe.id];
          const running = pending && activeProbe === probe.id;
          return (
            <motion.div
              key={probe.id}
              className="dt-interactive grid gap-3 rounded-lg border border-line bg-white p-3 hover:border-teal-200 md:grid-cols-[minmax(0,1fr)_auto]"
              data-testid={`settings-probe-result-${probe.id}`}
              whileHover={{ y: -2 }}
              whileTap={{ scale: 0.99 }}
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="font-semibold text-ink">{probe.label}</h3>
                  <Badge tone={result ? (result.success ? "success" : "danger") : "neutral"}>
                    {running ? "检测中" : result ? (result.success ? "可用" : "失败") : "未检测"}
                  </Badge>
                </div>
                <p className="mt-1 text-xs text-slate-500">{probe.detail}</p>
                <div className="mt-2 text-sm leading-6 text-slate-600">
                  {running ? (
                    <span className="inline-flex items-center gap-2">
                      <Loader2 size={15} className="animate-spin" />
                      正在检测
                    </span>
                  ) : result ? (
                    <>
                      <p className="truncate font-medium text-ink">{result.message}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        {result.model ? `${result.model} · ` : ""}
                        {typeof result.response_time_ms === "number" ? `${result.response_time_ms} ms` : "未返回耗时"}
                      </p>
                      {result.error ? <p className="mt-1 text-xs text-red-600">{result.error}</p> : null}
                    </>
                  ) : (
                    <p>尚未检测。</p>
                  )}
                </div>
              </div>
              <Button
                tone="secondary"
                className="w-full md:w-auto"
                disabled={pending}
                onClick={() => onRun(probe.id)}
                data-testid={`settings-probe-${probe.id}`}
              >
                {running ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
                开始检测
              </Button>
            </motion.div>
          );
        })}
      </div>
    </section>
  );
}

function SettingsCatalogEditor({
  settings,
  pending,
  tourMode = false,
  tourCompleted = false,
  tourPending = false,
  onSave,
  onCompleteTour,
}: {
  settings: SettingsResponse;
  pending: boolean;
  tourMode?: boolean;
  tourCompleted?: boolean;
  tourPending?: boolean;
  onSave: (catalog: ModelCatalog, ui: Partial<SettingsResponse["ui"]>) => Promise<void>;
  onCompleteTour?: (catalog: ModelCatalog, ui: Partial<SettingsResponse["ui"]>) => Promise<void>;
}) {
  const llmProfile = activeProfile(settings.catalog.services.llm);
  const embeddingProfile = activeProfile(settings.catalog.services.embedding);
  const searchProfile = activeProfile(settings.catalog.services.search);
  const llmModel = activeModel(settings.catalog.services.llm, llmProfile);
  const embeddingModel = activeModel(settings.catalog.services.embedding, embeddingProfile);
  const initialLlmBinding = llmProfile?.binding || "openai";
  const initialLlmProvider = settings.providers.llm.find((provider) => provider.value === initialLlmBinding);
  const initialLlmKeyShape = (llmProfile?.api_key || "").includes(":") ? "ak_sk" : "api_password";
  const initialEmbeddingBinding = embeddingProfile?.binding || "openai";
  const initialEmbeddingProvider = settings.providers.embedding.find((provider) => provider.value === initialEmbeddingBinding);
  const [llm, setLlm] = useState<LlmForm>({
    binding: initialLlmBinding,
    baseUrl: llmProfile?.base_url || "",
    apiKey: "",
    model: llmModel?.model || initialLlmProvider?.default_model || initialLlmProvider?.models?.[0] || "",
    iflytekAuthMode: initialLlmKeyShape,
    iflytekAppId: llmProfile?.extra_headers?.app_id || "",
    iflytekApiSecret: "",
  });
  const [embedding, setEmbedding] = useState<EmbeddingForm>({
    binding: initialEmbeddingBinding,
    baseUrl: embeddingProfile?.base_url || "",
    apiKey: "",
    model: embeddingModel?.model || initialEmbeddingProvider?.default_model || initialEmbeddingProvider?.models?.[0] || "",
    dimension: embeddingModel?.dimension || initialEmbeddingProvider?.default_dim || "",
    iflytekAuthMode: "api_password",
    iflytekAppId: embeddingProfile?.extra_headers?.app_id || "",
    iflytekApiSecret: "",
    iflytekDomain: embeddingProfile?.extra_headers?.domain || "para",
  });
  const [search, setSearch] = useState<SearchForm>({
    provider: searchProfile?.provider || "tavily",
    baseUrl: searchProfile?.base_url || "",
    apiKey: "",
  });
  const activeLlmProvider = useMemo(
    () => settings.providers.llm.find((provider) => provider.value === llm.binding),
    [llm.binding, settings.providers.llm],
  );
  const llmModelOptions = activeLlmProvider?.models ?? [];
  const hasLlmModelOptions = llmModelOptions.length > 0;
  const llmModelIsPreset = llmModelOptions.includes(llm.model);
  const llmModelSelectValue = llmModelIsPreset ? llm.model : CUSTOM_MODEL_VALUE;
  const isIflytekLlm = llm.binding === "iflytek_spark_ws";

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextCatalog = structuredClone(settings.catalog);
    applyLlmForm(nextCatalog.services.llm, llm);
    applyEmbeddingForm(nextCatalog.services.embedding, embedding);
    applySearchForm(nextCatalog.services.search, search);
    const ui = { language: settings.ui.language, theme: settings.ui.theme };
    const submitter = (event.nativeEvent as SubmitEvent).submitter as HTMLElement | null;
    if (submitter?.dataset.action === "complete-tour" && onCompleteTour) {
      await onCompleteTour(nextCatalog, ui);
      return;
    }
    await onSave(nextCatalog, ui);
  };

  return (
    <form className="rounded-lg border border-line bg-white p-3" onSubmit={submit}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Settings2 size={18} className="text-brand-teal" />
            <h2 className="text-base font-semibold text-ink">模型配置</h2>
          </div>
          <p className="mt-1 text-sm leading-6 text-slate-500">留空密钥会沿用现有配置，保存后立即生效。</p>
        </div>
        <Button
          tone="primary"
          type="submit"
          disabled={pending || tourPending}
          data-testid="settings-save-apply"
        >
          {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
          保存并应用
        </Button>
          {tourMode ? (
            <Button
              tone="primary"
              type="submit"
              data-action="complete-tour"
              aria-label={tourCompleted ? "Tour completed" : "Complete & Launch"}
              disabled={pending || tourPending || tourCompleted}
              className="border-brand-red bg-brand-red hover:bg-red-700"
            >
              {tourPending ? <Loader2 size={16} className="animate-spin" /> : <Rocket size={16} />}
              {tourCompleted ? "已完成" : "完成并启动"}
            </Button>
          ) : null}
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-3">
        <ConfigBlock title="问答模型">
          <ProviderSelect
            label="服务提供方"
            value={llm.binding}
            providers={settings.providers.llm}
            onChange={(value, provider) =>
              setLlm((current) => ({
                ...current,
                binding: value,
                baseUrl: provider?.base_url || current.baseUrl,
                iflytekAuthMode: value === "iflytek_spark_ws" ? current.iflytekAuthMode : "api_password",
                model: chooseProviderModel(
                  current.model,
                  provider,
                  settings.providers.llm.find((item) => item.value === current.binding),
                ),
              }))
            }
          />
          <FieldShell label="服务地址">
            <TextInput
              value={llm.baseUrl}
              onChange={(event) => setLlm((current) => ({ ...current, baseUrl: event.target.value }))}
              data-testid="settings-llm-base-url"
            />
          </FieldShell>
          <FieldShell label="模型名称" hint={hasLlmModelOptions ? "按供应商预置，可切换自定义" : "输入模型 ID"}>
            {hasLlmModelOptions ? (
              <SelectInput
                value={llmModelSelectValue}
                onChange={(event) => {
                  const value = event.target.value;
                  setLlm((current) => ({
                    ...current,
                    model: value === CUSTOM_MODEL_VALUE ? current.model : value,
                  }));
                }}
                data-testid="settings-llm-model-select"
              >
                {llmModelOptions.map((model) => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))}
                <option value={CUSTOM_MODEL_VALUE}>自定义模型...</option>
              </SelectInput>
            ) : null}
            {!hasLlmModelOptions || !llmModelIsPreset ? (
              <TextInput
                className={hasLlmModelOptions ? "mt-2" : undefined}
                value={llm.model}
                onChange={(event) => setLlm((current) => ({ ...current, model: event.target.value }))}
                data-testid="settings-llm-model"
              />
            ) : null}
          </FieldShell>
          {isIflytekLlm ? (
            <>
              <FieldShell label="讯飞鉴权方式" hint="HTTP APIPassword 或 APIKey + APISecret">
                <SelectInput
                  value={llm.iflytekAuthMode}
                  onChange={(event) =>
                    setLlm((current) => ({
                      ...current,
                      iflytekAuthMode: event.target.value as IflytekLlmAuthMode,
                      apiKey: "",
                      iflytekApiSecret: "",
                    }))
                  }
                  data-testid="settings-llm-iflytek-auth-mode"
                >
                  <option value="api_password">HTTP APIPassword</option>
                  <option value="ak_sk">APIKey + APISecret</option>
                </SelectInput>
              </FieldShell>
              {llm.iflytekAuthMode === "api_password" ? (
                <FieldShell label="APIPassword" hint={llmProfile?.api_key ? "已配置，留空保留" : "填写 HTTP 协议 APIPassword"}>
                  <TextInput
                    type="password"
                    value={llm.apiKey}
                    onChange={(event) => setLlm((current) => ({ ...current, apiKey: event.target.value }))}
                    data-testid="settings-llm-api-key"
                  />
                </FieldShell>
              ) : (
                <>
                  <FieldShell label="APIKey" hint="保存时自动拼接为 APIKey:APISecret">
                    <TextInput
                      type="password"
                      value={llm.apiKey}
                      onChange={(event) => setLlm((current) => ({ ...current, apiKey: event.target.value }))}
                      data-testid="settings-llm-api-key"
                    />
                  </FieldShell>
                  <FieldShell label="APISecret" hint={llmProfile?.api_key ? "已配置，修改时请两项都填写" : "填写同一应用的 APISecret"}>
                    <TextInput
                      type="password"
                      value={llm.iflytekApiSecret}
                      onChange={(event) => setLlm((current) => ({ ...current, iflytekApiSecret: event.target.value }))}
                      data-testid="settings-llm-iflytek-api-secret"
                    />
                  </FieldShell>
                </>
              )}
            </>
          ) : (
            <FieldShell label="密钥" hint={llmProfile?.api_key ? "已配置，留空保留" : "尚未配置"}>
              <TextInput
                type="password"
                value={llm.apiKey}
                onChange={(event) => setLlm((current) => ({ ...current, apiKey: event.target.value }))}
                data-testid="settings-llm-api-key"
              />
            </FieldShell>
          )}
        </ConfigBlock>

        <ConfigBlock title="向量模型">
          <ProviderSelect
            label="服务提供方"
            value={embedding.binding}
            providers={settings.providers.embedding}
            testId="settings-embedding-provider"
            onChange={(value, provider) =>
              setEmbedding((current) => ({
                ...current,
                binding: value,
                baseUrl: provider?.base_url ?? "",
                model: provider?.default_model || provider?.models?.[0] || "",
                dimension: provider?.default_dim ?? "",
                iflytekDomain: value === "iflytek_spark" ? current.iflytekDomain || "para" : current.iflytekDomain,
              }))
            }
          />
          <FieldShell label="服务地址">
            <TextInput
              value={embedding.baseUrl}
              onChange={(event) => setEmbedding((current) => ({ ...current, baseUrl: event.target.value }))}
              data-testid="settings-embedding-base-url"
            />
          </FieldShell>
          <FieldShell label="模型名称">
            <TextInput
              value={embedding.model}
              onChange={(event) => setEmbedding((current) => ({ ...current, model: event.target.value }))}
              data-testid="settings-embedding-model"
            />
          </FieldShell>
          <FieldShell label="向量维度">
            <TextInput
              value={embedding.dimension}
              onChange={(event) => setEmbedding((current) => ({ ...current, dimension: event.target.value }))}
              data-testid="settings-embedding-dimension"
            />
          </FieldShell>
          {embedding.binding === "iflytek_spark" ? (
            <>
              <FieldShell label="讯飞 APPID" hint="Embedding 签名必填">
                <TextInput
                  value={embedding.iflytekAppId}
                  onChange={(event) => setEmbedding((current) => ({ ...current, iflytekAppId: event.target.value }))}
                  data-testid="settings-embedding-iflytek-appid"
                />
              </FieldShell>
              <FieldShell
                label="讯飞 APISecret"
                hint={embeddingProfile?.extra_headers?.api_secret ? "已配置，留空保留" : "Embedding 签名必填"}
              >
                <TextInput
                  type="password"
                  value={embedding.iflytekApiSecret}
                  onChange={(event) => setEmbedding((current) => ({ ...current, iflytekApiSecret: event.target.value }))}
                  data-testid="settings-embedding-iflytek-api-secret"
                />
              </FieldShell>
              <FieldShell label="讯飞向量域">
                <SelectInput
                  value={embedding.iflytekDomain}
                  onChange={(event) => setEmbedding((current) => ({ ...current, iflytekDomain: event.target.value }))}
                  data-testid="settings-embedding-iflytek-domain"
                >
                  <option value="para">para：资料入库</option>
                  <option value="query">query：查询向量</option>
                </SelectInput>
              </FieldShell>
            </>
          ) : null}
          <FieldShell label="密钥" hint={embeddingProfile?.api_key ? "已配置，留空保留" : "尚未配置"}>
            <TextInput
              type="password"
              value={embedding.apiKey}
              onChange={(event) => setEmbedding((current) => ({ ...current, apiKey: event.target.value }))}
              data-testid="settings-embedding-api-key"
            />
          </FieldShell>
        </ConfigBlock>

        <ConfigBlock title="联网搜索">
          <ProviderSelect
            label="服务提供方"
            value={search.provider}
            providers={settings.providers.search}
            testId="settings-search-provider"
            onChange={(value, provider) =>
              setSearch((current) => ({ ...current, provider: value, baseUrl: provider?.base_url ?? "" }))
            }
          />
          <FieldShell label="服务地址">
            <TextInput
              value={search.baseUrl}
              onChange={(event) => setSearch((current) => ({ ...current, baseUrl: event.target.value }))}
              data-testid="settings-search-base-url"
            />
          </FieldShell>
          <FieldShell label="密钥" hint={searchProfile?.api_key ? "已配置，留空保留" : "可选"}>
            <TextInput
              type="password"
              value={search.apiKey}
              onChange={(event) => setSearch((current) => ({ ...current, apiKey: event.target.value }))}
              data-testid="settings-search-api-key"
            />
          </FieldShell>
        </ConfigBlock>
      </div>
    </form>
  );
}

function ConfigBlock({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="dt-interactive rounded-lg border border-line bg-white p-3 hover:border-teal-200">
      <h3 className="font-semibold text-ink">{title}</h3>
      <div className="mt-4 grid gap-4">{children}</div>
    </section>
  );
}

function SetupTourStatusPanel({
  status,
  loading,
  pending,
  result,
  onReopen,
}: {
  status?: SetupTourStatus;
  loading: boolean;
  pending: boolean;
  result?: SetupTourReopenResponse;
  onReopen: () => Promise<void>;
}) {
  const active = Boolean(status?.active);
  return (
    <section className="rounded-lg border border-line bg-white p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Rocket size={18} className="text-brand-red" />
            <h2 className="text-base font-semibold text-ink">启动向导</h2>
          </div>
          <p className="mt-1 text-sm leading-6 text-slate-500">
            查看终端配置向导的运行状态，需要重新打开时可直接拿到启动命令。
          </p>
        </div>
        <Button
          type="button"
          tone="secondary"
          disabled={pending}
          onClick={() => void onReopen()}
          data-testid="settings-tour-reopen"
        >
          {pending ? <Loader2 size={16} className="animate-spin" /> : <RotateCcw size={16} />}
          重新打开向导
        </Button>
      </div>

      {loading ? (
        <div className="mt-5 flex items-center gap-2 rounded-lg border border-line bg-canvas p-3 text-sm text-slate-500">
          <Loader2 size={16} className="animate-spin" />
          正在读取向导状态
        </div>
      ) : (
        <div className="mt-4 grid gap-2 md:grid-cols-4">
          <div className="rounded-lg bg-canvas px-3 py-2">
            <p className="text-xs text-slate-500">状态</p>
            <div className="mt-2">
              <Badge tone={active ? "brand" : "neutral"}>{active ? "启用" : "未设置"}</Badge>
            </div>
          </div>
          <div className="rounded-lg bg-canvas px-3 py-2">
            <p className="text-xs text-slate-500">阶段</p>
            <p className="mt-2 truncate font-semibold text-ink">{status?.status || "unknown"}</p>
          </div>
          <div className="rounded-lg bg-canvas px-3 py-2">
            <p className="text-xs text-slate-500">启动时间</p>
            <p className="mt-2 truncate font-semibold text-ink">{formatTourTime(status?.launch_at)}</p>
          </div>
          <div className="rounded-lg bg-canvas px-3 py-2">
            <p className="text-xs text-slate-500">跳转时间</p>
            <p className="mt-2 truncate font-semibold text-ink">{formatTourTime(status?.redirect_at)}</p>
          </div>
        </div>
      )}

      {result ? (
        <div className="mt-4 rounded-lg border border-teal-200 bg-teal-50 p-4 text-sm leading-6 text-slate-700">
          <p>{result.message}</p>
          <code className="mt-2 block overflow-x-auto rounded-md border border-line bg-white px-3 py-2 font-mono text-xs text-ink">
            {result.command}
          </code>
        </div>
      ) : null}
    </section>
  );
}

function formatTourTime(value?: number | null) {
  if (!value) return "未计划";
  return new Date(value * 1000).toLocaleString();
}

function RuntimeTopologyPanel({ topology, loading }: { topology?: RuntimeTopology; loading: boolean }) {
  const primary = topology?.primary_runtime;
  const primaryItems = primary
    ? [
        ["连接方式", primary.transport],
        ["运行管理", primary.manager],
        ["任务编排", primary.orchestrator],
        ["会话存储", primary.session_store],
        ["能力入口", primary.capability_entry],
        ["工具入口", primary.tool_entry],
      ]
    : [];
  return (
    <section className="rounded-lg border border-line bg-white p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <GitBranch size={18} className="text-brand-blue" />
            <h2 className="text-base font-semibold text-ink" aria-label="NG 运行拓扑">运行概览</h2>
          </div>
          <p className="mt-1 text-sm leading-6 text-slate-500">
            确认当前连接的是新版学习运行时。
          </p>
        </div>
        <Badge tone={primary?.transport ? "brand" : "neutral"}>{primary?.transport || "读取中"}</Badge>
      </div>

      {loading ? (
        <div className="mt-5 flex items-center gap-2 rounded-lg border border-line bg-canvas p-3 text-sm text-slate-500">
          <Loader2 size={16} className="animate-spin" />
          正在读取运行状态
        </div>
      ) : (
        <div className="mt-4 grid gap-4">
          <div className="grid gap-2 md:grid-cols-2">
            {primaryItems.map(([label, value]) => (
              <div key={label} className="flex min-w-0 items-center justify-between gap-3 rounded-lg bg-canvas px-3 py-2">
                <p className="shrink-0 text-xs text-slate-500">{label}</p>
                <p className="min-w-0 truncate text-sm font-semibold text-ink">{value}</p>
              </div>
            ))}
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <RouteGroup title="兼容入口" routes={topology?.compatibility_routes ?? []} />
            <RouteGroup title="独立能力" routes={topology?.isolated_subsystems ?? []} />
          </div>
        </div>
      )}
    </section>
  );
}

function CatalogSnapshotPanel({
  catalog,
  loading,
  onRefresh,
}: {
  catalog?: ModelCatalog;
  loading: boolean;
  onRefresh: () => void;
}) {
  const services = catalog?.services;
  const serviceCount = services ? Object.keys(services).length : 0;
  const profileCount = services
    ? Object.values(services).reduce((total, service) => total + (service.profiles?.length ?? 0), 0)
    : 0;
  return (
    <section className="rounded-lg border border-line bg-white p-3" data-testid="settings-catalog-snapshot">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Settings2 size={18} className="text-brand-teal" />
            <h2 className="text-base font-semibold text-ink">服务配置概览</h2>
          </div>
          <p className="mt-1 text-sm leading-6 text-slate-500">
            查看当前已保存的模型与服务配置。
          </p>
        </div>
        <Button tone="secondary" type="button" className="min-h-9 text-xs" onClick={onRefresh} disabled={loading}>
          {loading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          刷新配置概览
        </Button>
        <span className="dt-test-legacy">/api/v1/settings/catalog</span>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-4">
        <CatalogFact label="来源" value="设置服务" />
        <CatalogFact label="版本" value={catalog ? String(catalog.version) : loading ? "读取中" : "-"} />
        <CatalogFact label="服务" value={String(serviceCount)} />
        <CatalogFact label="配置项" value={String(profileCount)} />
      </div>
      {services ? (
        <div className="mt-3 grid gap-2 md:grid-cols-3">
          {(["llm", "embedding", "search"] as const).map((name) => (
            <div key={name} className="rounded-lg bg-canvas p-3">
              <p className="text-sm font-semibold text-ink">{serviceDisplayName(name)}</p>
              <p className="mt-1 text-xs text-slate-500">配置：{services[name]?.active_profile_id || "-"}</p>
              <p className="mt-1 text-xs text-slate-500">模型：{services[name]?.active_model_id || "-"}</p>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function CatalogFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-lg bg-canvas px-3 py-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-ink">{value}</p>
    </div>
  );
}

function serviceDisplayName(name: string) {
  return (
    {
      llm: "问答模型",
      embedding: "向量模型",
      search: "联网搜索",
    }[name] || name
  );
}

function RouteGroup({ title, routes }: { title: string; routes: Array<{ router: string; mode: string }> }) {
  return (
    <div className="rounded-lg bg-canvas p-3">
      <p className="text-sm font-semibold text-ink">{title}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {routes.map((route) => (
          <Badge key={`${route.router}-${route.mode}`} tone="neutral">
            {route.router} · {route.mode}
          </Badge>
        ))}
        {!routes.length ? <span className="text-xs text-slate-500">暂无路由</span> : null}
      </div>
    </div>
  );
}

function WorkbenchPreferences({
  settings,
  themes,
  sidebar,
  pending,
  onSave,
  onReset,
}: {
  settings: SettingsResponse;
  themes: Array<{ id: SettingsResponse["ui"]["theme"]; name: string }>;
  sidebar?: SidebarSettings;
  pending: boolean;
  onSave: (input: {
    theme: SettingsResponse["ui"]["theme"];
    language: SettingsResponse["ui"]["language"];
    description: string;
    navOrder: SidebarSettings["nav_order"];
  }) => Promise<void>;
  onReset: () => Promise<void>;
}) {
  const currentNavOrder = useMemo(
    () => sidebar?.nav_order || normalizeNavOrder(settings.ui.sidebar_nav_order),
    [settings.ui.sidebar_nav_order, sidebar?.nav_order],
  );
  const [theme, setTheme] = useState(settings.ui.theme);
  const [language, setLanguage] = useState(settings.ui.language);
  const [description, setDescription] = useState(sidebar?.description || settings.ui.sidebar_description || "");
  const [startOrder, setStartOrder] = useState(formatRouteList(currentNavOrder.start));
  const [learnOrder, setLearnOrder] = useState(formatRouteList(currentNavOrder.learnResearch));

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await onSave({
      theme,
      language,
      description,
      navOrder: {
        start: parseRouteList(startOrder),
        learnResearch: parseRouteList(learnOrder),
      },
    });
  };

  return (
    <form className="rounded-lg border border-line bg-white p-3" onSubmit={submit}>
      <details className="[&>summary::-webkit-details-marker]:hidden">
        <summary
          className="dt-interactive flex cursor-pointer list-none flex-wrap items-start justify-between gap-3 rounded-lg px-1 py-1"
          data-testid="settings-preferences-toggle"
        >
          <div>
            <div className="flex items-center gap-2">
              <LayoutList size={18} className="text-brand-blue" />
              <h2 className="text-base font-semibold text-ink">工作台偏好</h2>
            </div>
            <p className="mt-1 text-sm leading-6 text-slate-500">
              语言、主题和侧栏顺序，演示前再调整。
            </p>
          </div>
          <Badge tone="neutral">{parseRouteList(startOrder).length + parseRouteList(learnOrder).length} 个页面</Badge>
        </summary>

        <div className="mt-4 flex flex-wrap justify-end gap-2 border-t border-line pt-4">
          <Button tone="secondary" type="button" onClick={() => void onReset()} disabled={pending}>
            {pending ? <Loader2 size={16} className="animate-spin" /> : <RotateCcw size={16} />}
            重置界面
          </Button>
          <Button tone="primary" type="submit" disabled={pending}>
            {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            保存偏好
          </Button>
        </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
        <section className="rounded-lg border border-line bg-canvas p-3">
          <h3 className="font-semibold text-ink">界面基调</h3>
          <div className="mt-4 grid gap-4">
            <FieldShell label="主题">
              <SelectInput value={theme} onChange={(event) => setTheme(event.target.value as SettingsResponse["ui"]["theme"])}>
                {(themes.length ? themes : fallbackThemes()).map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </SelectInput>
            </FieldShell>
            <FieldShell label="语言">
              <SelectInput value={language} onChange={(event) => setLanguage(event.target.value as SettingsResponse["ui"]["language"])}>
                <option value="zh">中文</option>
                <option value="en">English</option>
              </SelectInput>
            </FieldShell>
            <FieldShell label="侧栏宣言">
              <TextArea
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                className="min-h-24"
                placeholder="例如：AI 学习工作台"
              />
            </FieldShell>
          </div>
        </section>

        <section className="rounded-lg border border-line bg-canvas p-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="font-semibold text-ink">侧栏导航顺序</h3>
              <p className="mt-1 text-xs leading-5 text-slate-500">每行一个页面路径，保存后立即生效。</p>
            </div>
            <Badge tone="neutral">{parseRouteList(startOrder).length + parseRouteList(learnOrder).length} 个页面</Badge>
          </div>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <FieldShell label="顶部常用区">
              <TextArea
                value={startOrder}
                onChange={(event) => setStartOrder(event.target.value)}
                aria-label="Start 区域"
                className="min-h-48 font-mono text-xs"
              />
            </FieldShell>
            <FieldShell label="学习研究区">
              <TextArea
                value={learnOrder}
                onChange={(event) => setLearnOrder(event.target.value)}
                aria-label="Learn / Research 区域"
                className="min-h-48 font-mono text-xs"
              />
            </FieldShell>
          </div>
        </section>
      </div>
      </details>
    </form>
  );
}

function ProviderSelect({
  label,
  value,
  providers,
  onChange,
  testId,
}: {
  label: string;
  value: string;
  providers: ProviderChoice[];
  onChange: (value: string, provider?: ProviderChoice) => void;
  testId?: string;
}) {
  return (
    <FieldShell label={label}>
      <SelectInput
        value={value}
        data-testid={testId}
        onChange={(event) => {
          const provider = providers.find((item) => item.value === event.target.value);
          onChange(event.target.value, provider);
        }}
      >
        {providers.map((provider) => (
          <option key={provider.value} value={provider.value}>
            {provider.label}
          </option>
        ))}
      </SelectInput>
    </FieldShell>
  );
}

function chooseProviderModel(currentModel: string, provider?: ProviderChoice, previousProvider?: ProviderChoice) {
  const defaultModel = provider?.default_model?.trim();
  if (!defaultModel) return currentModel;
  const previousDefault = previousProvider?.default_model?.trim();
  const previousOptions = previousProvider?.models ?? [];
  const normalizedCurrent = currentModel.trim();
  if (
    !normalizedCurrent ||
    normalizedCurrent === previousDefault ||
    previousOptions.includes(normalizedCurrent) ||
    normalizedCurrent === "gpt-4o-mini"
  ) {
    return defaultModel;
  }
  return currentModel;
}

function activeProfile(service: ServiceCatalog): EndpointProfile | undefined {
  return service.profiles.find((profile) => profile.id === service.active_profile_id) || service.profiles[0];
}

function activeModel(service: ServiceCatalog, profile?: EndpointProfile) {
  return profile?.models?.find((model) => model.id === service.active_model_id) || profile?.models?.[0];
}

function ensureProfile(service: ServiceCatalog, fallbackId: string) {
  let profile = activeProfile(service);
  if (!profile) {
    profile = { id: fallbackId, name: "Default", models: [] };
    service.profiles = [profile];
    service.active_profile_id = fallbackId;
  }
  return profile;
}

function ensureModel(service: ServiceCatalog, profile: EndpointProfile, fallbackId: string) {
  profile.models = profile.models ?? [];
  let model = activeModel(service, profile);
  if (!model) {
    model = { id: fallbackId, name: "Default Model", model: "" };
    profile.models.push(model);
    service.active_model_id = fallbackId;
  }
  return model;
}

function applyLlmForm(service: ServiceCatalog, form: LlmForm) {
  const profile = ensureProfile(service, "llm-profile-default");
  const model = ensureModel(service, profile, "llm-model-default");
  profile.binding = form.binding;
  profile.base_url = form.baseUrl.trim();
  const apiKey = buildLlmApiKey(form);
  if (apiKey) profile.api_key = apiKey;
  if (form.binding === "iflytek_spark_ws" && profile.extra_headers) {
    const extraHeaders = { ...profile.extra_headers };
    delete extraHeaders.app_id;
    delete extraHeaders.appid;
    delete extraHeaders.api_secret;
    delete extraHeaders.domain;
    profile.extra_headers = extraHeaders;
  }
  model.name = form.model.trim();
  model.model = form.model.trim();
}

function buildLlmApiKey(form: LlmForm) {
  const apiKey = form.apiKey.trim();
  if (form.binding !== "iflytek_spark_ws") return apiKey;
  if (form.iflytekAuthMode === "api_password") return apiKey;
  if (apiKey.includes(":")) return apiKey;
  const apiSecret = form.iflytekApiSecret.trim();
  if (!apiKey || !apiSecret) return "";
  return `${apiKey}:${apiSecret}`;
}

function applyEmbeddingForm(service: ServiceCatalog, form: EmbeddingForm) {
  const profile = ensureProfile(service, "embedding-profile-default");
  const model = ensureModel(service, profile, "embedding-model-default");
  profile.binding = form.binding;
  profile.base_url = form.baseUrl.trim();
  if (form.apiKey.trim()) profile.api_key = form.apiKey.trim();
  if (form.binding === "iflytek_spark") {
    const extraHeaders = { ...(profile.extra_headers || {}) };
    if (form.iflytekAppId.trim()) extraHeaders.app_id = form.iflytekAppId.trim();
    if (form.iflytekApiSecret.trim()) extraHeaders.api_secret = form.iflytekApiSecret.trim();
    extraHeaders.domain = form.iflytekDomain.trim() || "para";
    profile.extra_headers = extraHeaders;
  }
  model.name = form.model.trim();
  model.model = form.model.trim();
  model.dimension = form.dimension.trim();
}

function applySearchForm(service: ServiceCatalog, form: SearchForm) {
  const profile = ensureProfile(service, "search-profile-default");
  profile.provider = form.provider;
  profile.base_url = form.baseUrl.trim();
  if (form.apiKey.trim()) profile.api_key = form.apiKey.trim();
}

function normalizeNavOrder(value: SettingsResponse["ui"]["sidebar_nav_order"] | undefined): SidebarSettings["nav_order"] {
  return {
    start: Array.isArray(value?.start) ? value.start : ["/", "/history", "/knowledge", "/notebook"],
    learnResearch: Array.isArray(value?.learnResearch)
      ? value.learnResearch
      : ["/question", "/solver", "/guide", "/research", "/co_writer"],
  };
}

function settingsPreferenceKey(settings: SettingsResponse, sidebar: SidebarSettings | undefined) {
  return JSON.stringify({
    theme: settings.ui.theme,
    language: settings.ui.language,
    description: sidebar?.description || settings.ui.sidebar_description || "",
    nav_order: sidebar?.nav_order || settings.ui.sidebar_nav_order,
  });
}

function formatRouteList(routes: string[] | undefined) {
  return (routes ?? []).join("\n");
}

function parseRouteList(value: string) {
  return value
    .split(/\r?\n|,/)
    .map((route) => route.trim())
    .filter(Boolean);
}

function fallbackThemes() {
  return [
    { id: "snow" as const, name: "Snow" },
    { id: "light" as const, name: "Light" },
    { id: "dark" as const, name: "Dark" },
    { id: "glass" as const, name: "Glass" },
  ];
}
