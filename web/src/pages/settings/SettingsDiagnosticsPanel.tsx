import { AnimatePresence, motion } from "framer-motion";
import {
  CheckCircle2,
  GitBranch,
  Loader2,
  PlugZap,
  RefreshCw,
  Rocket,
  RotateCcw,
  Settings2,
  XCircle,
} from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import type {
  ModelCatalog,
  RuntimeTopology,
  SetupTourReopenResponse,
  SetupTourStatus,
  SystemTestResponse,
} from "@/lib/types";
import {
  friendlyServiceError,
  serviceDisplayName,
  SERVICES,
  SYSTEM_PROBES,
  type ServiceId,
  type SystemProbeId,
  type TestStatus,
  withLegacyText,
} from "./settingsDiagnosticsUtils";
import { SpeechPreviewGroup } from "./SpeechPreviewGroup";
import { InlineLegacyText } from "./SettingsStatusStrip";

export function SettingsDiagnosticsPanel({
  activeProbe,
  activeRunId,
  activeService,
  catalog,
  catalogLoading,
  isTourMode,
  onCancelTest,
  onRefreshCatalog,
  onReopenTour,
  onRunProbe,
  onRunTest,
  probePending,
  probeResults,
  reopenTourPending,
  reopenTourResult,
  runtimeTopology,
  runtimeTopologyLoading,
  testLogs,
  testStatus,
  tourStatus,
  tourStatusLoading,
}: {
  activeProbe: SystemProbeId | null;
  activeRunId: string;
  activeService: ServiceId | null;
  catalog?: ModelCatalog;
  catalogLoading: boolean;
  isTourMode: boolean;
  onCancelTest: () => void;
  onRefreshCatalog: () => void;
  onReopenTour: () => void;
  onRunProbe: (service: SystemProbeId) => void;
  onRunTest: (service: ServiceId) => void;
  probePending: boolean;
  probeResults: Partial<Record<SystemProbeId, SystemTestResponse>>;
  reopenTourPending: boolean;
  reopenTourResult?: SetupTourReopenResponse;
  runtimeTopology?: RuntimeTopology;
  runtimeTopologyLoading: boolean;
  testLogs: string[];
  testStatus: TestStatus;
  tourStatus?: SetupTourStatus;
  tourStatusLoading: boolean;
}) {
  return (
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
          <span className="block text-base font-semibold text-ink">连接检查</span>
          <span className="mt-1 block text-sm text-slate-500">模型不可用或需要确认连接时再打开。</span>
        </span>
        <Badge tone="neutral">按需查看</Badge>
      </summary>

      <div className="mt-4 space-y-4">
        <SystemProbePanel
          results={probeResults}
          activeProbe={activeProbe}
          pending={probePending}
          onRun={onRunProbe}
        />

        <SpeechPreviewGroup />

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
                onClick={onCancelTest}
                disabled={!activeRunId}
                data-testid="settings-test-cancel"
              >
                <XCircle size={16} />
                取消检测
              </Button>
            ) : null}
          </div>
          <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
            {SERVICES.map((service) => (
              <motion.button
                key={service.id}
                type="button"
                onClick={() => onRunTest(service.id)}
                disabled={testStatus === "running"}
                data-testid={`settings-test-${service.id}`}
                className="dt-interactive flex min-h-16 items-center justify-between gap-3 rounded-lg border border-line bg-white p-3 text-left transition hover:border-brand-purple-300 hover:bg-canvas disabled:opacity-60"
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
          <div className="dt-event-feed mt-4 min-h-32 rounded-lg p-3 text-xs leading-6" data-testid="settings-test-logs">
            {testLogs.length ? (
              <AnimatePresence initial={false}>
                {testLogs.map((line, index) => (
                  <motion.p
                    key={`${index}-${line.slice(0, 10)}`}
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    transition={{ duration: 0.16 }}
                    className="dt-event-row"
                  >
                    <InlineLegacyText text={line} />
                  </motion.p>
                ))}
              </AnimatePresence>
            ) : (
              <p className="text-slate-500">点击上方服务后，这里会显示检测进度。</p>
            )}
          </div>
        </section>

        <RuntimeTopologyPanel topology={runtimeTopology} loading={runtimeTopologyLoading} />

        <CatalogSnapshotPanel catalog={catalog} loading={catalogLoading} onRefresh={onRefreshCatalog} />

        <SetupTourStatusPanel
          status={tourStatus}
          loading={tourStatusLoading}
          pending={reopenTourPending}
          result={reopenTourResult}
          onReopen={onReopenTour}
        />
      </div>
    </details>
  );
}

function friendlyProbeMessage(result: SystemTestResponse) {
  if (result.success) return "连接正常，可以使用。";
  return `检测失败：${friendlyServiceError(result.error || result.message)}`;
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
            <PlugZap size={18} className="text-brand-purple" />
            <h2 className="text-base font-semibold text-ink">快速检测</h2>
          </div>
          <p className="mt-1 text-sm leading-6 text-slate-500">保存配置后，用这里确认核心服务和可选语音学习是否可用。</p>
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
              className="dt-interactive grid gap-3 rounded-lg border border-line bg-white p-3 hover:border-brand-purple-300 md:grid-cols-[minmax(0,1fr)_auto]"
              data-testid={`settings-probe-result-${probe.id}`}
              whileHover={{ y: -0.5 }}
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
                      <p className="truncate font-medium text-ink">
                        <InlineLegacyText text={withLegacyText(friendlyProbeMessage(result), result.message)} />
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        {result.model ? `${result.model} · ` : ""}
                        {typeof result.response_time_ms === "number" ? `${result.response_time_ms} ms` : "未返回耗时"}
                      </p>
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
  onReopen: () => void;
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
          <p className="mt-1 text-sm leading-6 text-slate-500">查看终端配置向导的运行状态，需要重新打开时可直接拿到启动命令。</p>
        </div>
        <Button type="button" tone="secondary" disabled={pending} onClick={onReopen} data-testid="settings-tour-reopen">
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
        <div className="mt-4 rounded-lg border border-brand-purple-300 bg-tint-lavender p-4 text-sm leading-6 text-slate-700">
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

function topologyDisplayName(value?: string | null) {
  const raw = String(value || "").trim();
  if (!raw) return "-";
  const names: Record<string, string> = {
    LangGraphTurnRuntimeManager: "学习服务管理",
    LangGraphRunner: "学习流程执行",
    SQLiteSessionStore: "本地会话存储",
    CapabilityRegistry: "学习入口",
    ToolRegistry: "辅助入口",
    ng_router: "学习服务连接",
    independent_subsystem: "独立学习服务",
    chat: "学习对话",
    solve: "解题流程",
    guide: "学习向导",
    co_writer: "共写空间",
  };
  return names[raw] ?? raw;
}

function RuntimeTopologyPanel({ topology, loading }: { topology?: RuntimeTopology; loading: boolean }) {
  const primary = topology?.primary_runtime;
  const primaryItems = primary
    ? [
        ["连接方式", primary.transport],
        ["运行管理", topologyDisplayName(primary.manager)],
        ["任务流程", topologyDisplayName(primary.orchestrator)],
        ["会话存储", topologyDisplayName(primary.session_store)],
        ["学习服务", topologyDisplayName(primary.capability_entry)],
        ["辅助服务", topologyDisplayName(primary.tool_entry)],
      ]
    : [];
  return (
    <section className="rounded-lg border border-line bg-white p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <GitBranch size={18} className="text-brand-blue" />
            <h2 className="text-base font-semibold text-ink">
              运行概览
            </h2>
          </div>
          <p className="mt-1 text-sm leading-6 text-slate-500">确认当前连接的是新版学习服务。</p>
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
            <RouteGroup title="旧入口连接" routes={topology?.compatibility_routes ?? []} />
            <RouteGroup title="独立辅助功能" routes={topology?.isolated_subsystems ?? []} />
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
  const profileCount = services
    ? Object.values(services).reduce((total, service) => total + (service?.profiles?.length ?? 0), 0)
    : 0;
  const visibleServices = services ? CATALOG_SERVICE_ORDER : [];
  return (
    <section className="rounded-lg border border-line bg-white p-3" data-testid="settings-catalog-snapshot">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Settings2 size={18} className="text-brand-purple" />
            <h2 className="text-base font-semibold text-ink">服务配置概览</h2>
          </div>
          <p className="mt-1 text-sm leading-6 text-slate-500">查看当前已保存的模型与服务配置。</p>
        </div>
        <Button tone="secondary" type="button" className="min-h-9 text-xs" onClick={onRefresh} disabled={loading}>
          {loading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          刷新配置概览
        </Button>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-4">
        <CatalogFact label="来源" value="设置服务" />
        <CatalogFact label="版本" value={catalog ? String(catalog.version) : loading ? "读取中" : "-"} />
        <CatalogFact label="服务" value={`${CATALOG_SERVICE_ORDER.length} 项`} />
        <CatalogFact label="配置项" value={String(profileCount)} />
      </div>
      {services ? (
        <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {visibleServices.map((name) => {
            const summary = summarizeCatalogService(name, services[name]);
            return (
              <div key={name} className="min-w-0 rounded-lg bg-canvas p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="truncate text-sm font-semibold text-ink">{serviceDisplayName(name)}</p>
                  <Badge tone={summary.configured ? "success" : "neutral"}>{summary.configured ? "已保存" : "未配置"}</Badge>
                </div>
                <p className="mt-2 truncate text-xs font-medium text-slate-600">{summary.primary}</p>
                <p className="mt-1 truncate text-xs text-slate-500">{summary.secondary}</p>
              </div>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}

const CATALOG_SERVICE_ORDER = [
  "llm",
  "embedding",
  "search",
  "ocr",
  "formula_ocr",
  "image_understanding",
  "tts",
  "asr",
  "speech_eval",
] as const;
type CatalogServiceName = (typeof CATALOG_SERVICE_ORDER)[number];

function summarizeCatalogService(
  name: CatalogServiceName,
  service: ModelCatalog["services"][CatalogServiceName] | undefined,
) {
  const profile = activeCatalogProfile(service);
  const model = activeCatalogModel(service, profile);
  if (!profile) return { configured: false, primary: "未选择服务", secondary: "保存配置后显示" };

  const disabled = isDisabledCatalogProfile(profile);
  const provider = providerDisplayName(profile.binding || profile.provider || profile.name);
  const base = trimUrlForDisplay(profile.base_url);
  const extra = profile.extra_headers || {};
  if (name === "tts") {
    return {
      configured: !disabled && Boolean(profile.provider || profile.binding),
      primary: provider,
      secondary: `音色 ${extra.voice || "默认"}${base ? ` · ${base}` : ""}`,
    };
  }
  if (name === "asr") {
    return {
      configured: !disabled && Boolean(profile.provider || profile.binding),
      primary: provider,
      secondary: `语言 ${extra.language || "zh_cn"}${base ? ` · ${base}` : ""}`,
    };
  }
  if (name === "speech_eval") {
    return {
      configured: !disabled && Boolean(profile.provider || profile.binding),
      primary: provider,
      secondary: `题型 ${speechCategoryLabel(extra.category)}${base ? ` · ${base}` : ""}`,
    };
  }
  if (name === "search" || name === "ocr" || name === "formula_ocr" || name === "image_understanding") {
    return {
      configured: !disabled && Boolean(profile.provider || profile.binding),
      primary: provider,
      secondary: base || "使用默认地址",
    };
  }
  return {
    configured: !disabled && Boolean(model?.model || profile.binding || profile.provider),
    primary: model?.model || provider,
    secondary: provider,
  };
}

function activeCatalogProfile(service?: { active_profile_id?: string; profiles?: Array<ModelCatalog["services"]["llm"]["profiles"][number]> }) {
  const profiles = service?.profiles ?? [];
  return profiles.find((profile) => profile.id === service?.active_profile_id) || profiles[0];
}

function activeCatalogModel(
  service: { active_model_id?: string } | undefined,
  profile?: ModelCatalog["services"]["llm"]["profiles"][number],
) {
  const models = profile?.models ?? [];
  return models.find((model) => model.id === service?.active_model_id) || models[0];
}

function isDisabledCatalogProfile(profile: ModelCatalog["services"]["llm"]["profiles"][number]) {
  const provider = String(profile.provider || "").trim().toLowerCase();
  const binding = String(profile.binding || "").trim().toLowerCase();
  return provider === "disabled" || binding === "disabled";
}

function providerDisplayName(value?: string) {
  const key = String(value || "").trim().toLowerCase().replace(/-/g, "_");
  return (
    {
      openai: "OpenAI",
      anthropic: "Anthropic",
      deepseek: "DeepSeek",
      dashscope: "通义千问",
      gemini: "Gemini",
      siliconflow: "硅基流动",
      ollama: "Ollama",
      brave: "Brave",
      tavily: "Tavily",
      jina: "Jina",
      duckduckgo: "DuckDuckGo",
      perplexity: "Perplexity",
      serper: "Serper",
      searxng: "SearXNG",
      iflytek: "科大讯飞",
      xfyun: "科大讯飞",
      xunfei: "科大讯飞",
      iflytek_spark: "讯飞星火",
      iflytek_spark_ws: "讯飞星火",
      iflytek_maas_coding: "讯飞 MaaS Coding",
      iflytek_tts: "讯飞语音合成",
      iflytek_asr: "讯飞语音听写",
      iflytek_speech_eval: "讯飞语音评测",
      disabled: "停用",
    }[key] || value || "默认服务"
  );
}

function trimUrlForDisplay(value?: string) {
  const text = String(value || "").trim();
  if (!text) return "";
  return text.replace(/^https?:\/\//, "").replace(/^wss?:\/\//, "").replace(/\/$/, "");
}

function speechCategoryLabel(value?: string) {
  return (
    {
      read_sentence: "句子朗读",
      read_chapter: "篇章朗读",
      read_word: "词语朗读",
    }[String(value || "")] || value || "句子朗读"
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

function RouteGroup({ title, routes }: { title: string; routes: Array<{ router: string; mode: string }> }) {
  return (
    <div className="rounded-lg bg-canvas p-3">
      <p className="text-sm font-semibold text-ink">{title}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {routes.map((route) => (
          <Badge key={`${route.router}-${route.mode}`} tone="neutral">
            {topologyDisplayName(route.router)} · {topologyDisplayName(route.mode)}
          </Badge>
        ))}
        {!routes.length ? <span className="text-xs text-slate-500">暂无连接</span> : null}
      </div>
    </div>
  );
}
