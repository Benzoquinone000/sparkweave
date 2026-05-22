import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, PlugZap, Rocket, Settings2, SlidersHorizontal, type LucideIcon } from "lucide-react";
import { Link, useLocation } from "@tanstack/react-router";
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import {
  cancelSettingsServiceTest,
  completeSetupTour,
  openSettingsServiceTestEvents,
  startSettingsServiceTest,
} from "@/lib/api";
import type {
  ModelCatalog,
  SettingsResponse,
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
import {
  InlineLegacyText,
  ServiceStatusStrip,
} from "./settings/SettingsStatusStrip";
import {
  formatSettingsTestEvent,
  friendlyServiceError,
  serviceDisplayName,
  systemProbeDisplayName,
  type ServiceId,
  type SystemProbeId,
  type TestStatus,
  withLegacyText,
} from "./settings/settingsDiagnosticsUtils";
import { settingsPreferenceKey } from "./settings/settingsPreferenceUtils";

const SettingsCatalogEditor = lazy(() =>
  import("./settings/SettingsCatalogEditor").then((module) => ({ default: module.SettingsCatalogEditor })),
);
const SettingsDiagnosticsPanel = lazy(() =>
  import("./settings/SettingsDiagnosticsPanel").then((module) => ({ default: module.SettingsDiagnosticsPanel })),
);
const WorkbenchPreferences = lazy(() =>
  import("./settings/WorkbenchPreferences").then((module) => ({ default: module.WorkbenchPreferences })),
);

type SettingsView = "home" | "models" | "preferences" | "diagnostics";

type SettingsTask = {
  view: Exclude<SettingsView, "home">;
  to: "/settings/models" | "/settings/preferences" | "/settings/diagnostics";
  title: string;
  detail: string;
  metric: string;
  icon: LucideIcon;
  tint: string;
};

const SETTINGS_TASKS: SettingsTask[] = [
  {
    view: "models",
    to: "/settings/models",
    title: "连接服务",
    detail: "问答、资料引用、搜索、图片文字识别和语音",
    metric: "服务状态",
    icon: Settings2,
    tint: "bg-tint-sky",
  },
  {
    view: "preferences",
    to: "/settings/preferences",
    title: "工作台偏好",
    detail: "主题、语言和左侧导航",
    metric: "界面体验",
    icon: SlidersHorizontal,
    tint: "bg-tint-lavender",
  },
  {
    view: "diagnostics",
    to: "/settings/diagnostics",
    title: "连接检测",
    detail: "确认服务是否能正常使用",
    metric: "出现问题时",
    icon: PlugZap,
    tint: "bg-tint-mint",
  },
];

export function SettingsPage() {
  const location = useLocation();
  const settingsView = settingsViewFromPath(location.pathname);
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
      appendTestLog(withLegacyText("已创建检测任务，正在连接服务。", `检测任务：${payload.run_id}`));
      const source = openSettingsServiceTestEvents({ service, runId: payload.run_id });
      let finished = false;
      eventSourceRef.current = source;
      source.onmessage = (event) => {
        const data = JSON.parse(event.data) as { type?: TestStatus | string; message?: string; [key: string]: unknown };
        const kind = data.type || "info";
        appendTestLog(formatSettingsTestEvent(kind, data));
        if (kind === "completed" || kind === "failed") {
          finished = true;
          source.close();
          setTestStatus(kind);
          setLastResult(
            withLegacyText(
              `${serviceDisplayName(service)}${kind === "completed" ? "检测通过。" : "检测失败，请检查配置。"}`,
              `${service}: ${data.message || kind}`,
            ),
          );
        }
      };
      source.onerror = () => {
        if (!finished && eventSourceRef.current === source) {
          appendTestLog(withLegacyText("实时检测中断，请稍后重试。", "[error] 实时检测中断"));
          setTestStatus("failed");
        }
        source.close();
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : "测试失败";
      appendTestLog(withLegacyText(`检测失败：${friendlyServiceError(message)}`, `失败：${message}`));
      setTestStatus("failed");
      setLastResult(withLegacyText(`${serviceDisplayName(service)}检测失败，请检查配置。`, `${service}: ${message}`));
    }
  };

  const cancelTest = async () => {
    if (!activeService || !activeRunId) return;
    eventSourceRef.current?.close();
    await cancelSettingsServiceTest({ service: activeService, runId: activeRunId });
    setTestStatus("cancelled");
    appendTestLog(withLegacyText("已取消当前服务检测。", "[cancelled] 已取消当前服务检测"));
  };

  const runProbe = async (service: SystemProbeId) => {
    setActiveProbe(service);
    setLastResult("");
    try {
      const result = await serviceProbe.mutateAsync(service);
      setProbeResults((current) => ({ ...current, [service]: result }));
      setLastResult(
        withLegacyText(
          `${systemProbeDisplayName(service)}快速检测${result.success ? "通过。" : "失败，请检查配置。"}`,
          `${service}: ${result.message}`,
        ),
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : "即时探针失败";
      const result = {
        success: false,
        message,
        error: message,
      };
      setProbeResults((current) => ({ ...current, [service]: result }));
      setLastResult(withLegacyText(`${systemProbeDisplayName(service)}快速检测失败，请检查配置。`, `${service}: ${result.message}`));
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
          ocr: String(status.data?.ocr?.status || "optional"),
          tts: String(status.data?.tts?.status || "optional"),
          asr: String(status.data?.asr?.status || "optional"),
          speech_eval: String(status.data?.speech_eval?.status || "optional"),
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
    <div className="dt-dynamic-page h-full overflow-y-auto px-3.5 py-3.5 pb-20 lg:px-4 lg:pb-4">
      <div className="mx-auto max-w-[900px] space-y-4">
        {settingsView === "home" ? <SettingsHomeHero /> : <SettingsSubpageHeader view={settingsView} />}

        {isTourMode ? (
          <section className="rounded-lg border border-brand-purple-300 bg-tint-lavender p-3.5">
            <div className="flex flex-wrap items-center justify-between gap-3.5">
              <div className="flex items-start gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white text-brand-purple">
                  <Rocket size={17} />
                </div>
                <div>
                  <h2 className="font-semibold text-ink">启动向导</h2>
                  <p className="mt-1 text-xs leading-5 text-slate-600">
                    配置问答模型、资料理解和可选搜索服务，完成后会启动 SparkWeave。
                  </p>
                </div>
              </div>
              <Badge tone={tourCompleted ? "success" : "brand"}>{tourCompleted ? "已完成" : "待完成"}</Badge>
            </div>
          </section>
        ) : null}

        <ServiceStatusStrip status={status.data} />

        {settingsView === "home" ? <SettingsTaskGrid /> : null}

        {settingsView === "models" ? (
          settings.data ? (
            <Suspense fallback={<SettingsSectionLoading label="正在准备服务配置" />}>
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
                  setLastResult("配置已保存，刷新后即可使用。");
                }}
                onCompleteTour={completeTour}
              />
            </Suspense>
          ) : (
            <SettingsSectionLoading label="正在读取服务配置" />
          )
        ) : null}

        {settingsView === "preferences" ? (
          settings.data ? (
            <Suspense fallback={<SettingsSectionLoading label="正在准备工作台偏好" />}>
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
            </Suspense>
          ) : (
            <SettingsSectionLoading label="正在读取工作台偏好" />
          )
        ) : null}

        <AnimatePresence>
          {lastResult ? (
            <motion.p
              className="rounded-lg border border-brand-purple-300 bg-tint-lavender p-3 text-sm text-slate-600"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.18 }}
              data-testid="settings-result"
            >
              <InlineLegacyText text={lastResult} />
            </motion.p>
          ) : null}
        </AnimatePresence>

        {settingsView === "diagnostics" ? (
          <Suspense fallback={<SettingsSectionLoading label="正在准备检测面板" />}>
            <SettingsDiagnosticsPanel
              activeProbe={activeProbe}
              activeRunId={activeRunId}
              activeService={activeService}
              catalog={catalogSnapshot.data?.catalog}
              catalogLoading={catalogSnapshot.isLoading}
              isTourMode={isTourMode}
              onCancelTest={() => void cancelTest()}
              onRefreshCatalog={() => void catalogSnapshot.refetch()}
              onReopenTour={() => {
                void (async () => {
                  try {
                    const result = await reopenTour.mutateAsync();
                    setLastResult(`${result.message} ${result.command}`);
                  } catch (error) {
                    setLastResult(error instanceof Error ? error.message : "无法重新打开启动向导。");
                  }
                })();
              }}
              onRunProbe={(service) => void runProbe(service)}
              onRunTest={(service) => void runTest(service)}
              probePending={serviceProbe.isPending}
              probeResults={probeResults}
              reopenTourPending={reopenTour.isPending}
              reopenTourResult={reopenTour.data}
              runtimeTopology={runtimeTopology.data}
              runtimeTopologyLoading={runtimeTopology.isLoading}
              testLogs={testLogs}
              testStatus={testStatus}
              tourStatus={tourStatus.data}
              tourStatusLoading={tourStatus.isLoading}
            />
          </Suspense>
        ) : null}
      </div>
    </div>
  );
}

function SettingsHomeHero() {
  return (
    <section className="dt-page-header dt-page-header-accent-pink p-3.5">
      <p className="text-xs font-semibold text-steel">设置</p>
      <h1 className="mt-1 text-xl font-semibold leading-tight text-ink">需要改什么，就进对应页面</h1>
      <p className="mt-2 max-w-2xl text-xs leading-5 text-slate-600">
        常用设置只分三类：连接服务、调整工作台偏好、检查运行状态。日常只要确认它们可用。
      </p>
    </section>
  );
}

function SettingsTaskGrid() {
  return (
    <section className="grid gap-3 md:grid-cols-3" data-testid="settings-task-grid">
      {SETTINGS_TASKS.map((task) => (
        <Link
          key={task.view}
          to={task.to}
          className="dt-interactive dt-dynamic-card rounded-lg border border-line bg-white p-2.5 text-left transition hover:border-brand-purple-300 hover:shadow-sm"
          data-testid={`settings-task-${task.view}`}
        >
          <span className={`flex h-9 w-9 items-center justify-center rounded-lg border border-line ${task.tint} text-ink`}>
            <task.icon size={16} />
          </span>
          <span className="mt-3 block text-sm font-semibold text-ink">{task.title}</span>
          <span className="mt-1 block text-xs leading-5 text-slate-500">{task.detail}</span>
          <span className="mt-3 inline-flex rounded-md border border-line bg-canvas px-2 py-1 text-xs text-slate-600">
            {task.metric}
          </span>
        </Link>
      ))}
    </section>
  );
}

function SettingsSubpageHeader({ view }: { view: Exclude<SettingsView, "home"> }) {
  const task = SETTINGS_TASKS.find((item) => item.view === view) ?? SETTINGS_TASKS[0];
  return (
    <section className="dt-page-header dt-page-header-accent-pink p-3.5">
      <Link
        to="/settings"
        className="dt-interactive inline-flex min-h-9 items-center gap-2 rounded-lg border border-line bg-canvas px-3 text-sm font-medium text-slate-600 hover:border-brand-purple-300 hover:text-brand-purple"
        data-testid="settings-back-home"
      >
        <ArrowLeft size={16} />
        返回设置
      </Link>
      <div className="mt-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm text-slate-500">设置</p>
          <h1 className="mt-1 text-xl font-semibold tracking-normal text-ink">{task.title}</h1>
          <p className="mt-2 max-w-2xl text-xs leading-5 text-slate-500">{task.detail}</p>
        </div>
        <span className={`flex h-10 w-10 items-center justify-center rounded-lg border border-line ${task.tint} text-ink`}>
          <task.icon size={18} />
        </span>
      </div>
    </section>
  );
}

function settingsViewFromPath(pathname: string): SettingsView {
  if (pathname.endsWith("/models")) return "models";
  if (pathname.endsWith("/preferences")) return "preferences";
  if (pathname.endsWith("/diagnostics")) return "diagnostics";
  return "home";
}

function SettingsSectionLoading({ label }: { label: string }) {
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
