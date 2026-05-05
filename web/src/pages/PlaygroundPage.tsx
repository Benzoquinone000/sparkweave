import { AnimatePresence, motion } from "framer-motion";
import {
  Beaker,
  Code2,
  Database,
  Loader2,
  Play,
  ScrollText,
  Sparkles,
  Terminal,
  Wrench,
} from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { FieldShell, TextArea } from "@/components/ui/Field";
import { MarkdownRenderer } from "@/components/ui/MarkdownRenderer";
import { Metric } from "@/components/ui/Metric";
import { NotionProductHero } from "@/components/ui/NotionProductHero";
import {
  executePluginTool,
  streamPluginCapabilityExecution,
  streamPluginToolExecution,
  type SseEventHandler,
} from "@/lib/api";
import type { PlaygroundCapability, PlaygroundTool } from "@/lib/types";
import { useKnowledgeBases, usePluginsList } from "@/hooks/useApiQueries";

const LEGACY_TEXT_SEPARATOR = "\u001F";

function withLegacyText(visible: string, legacy: string) {
  return `${visible}${LEGACY_TEXT_SEPARATOR}${legacy}`;
}

function parseJsonObject(value: string) {
  const parsed = JSON.parse(value) as unknown;
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("请输入 JSON 对象，例如 {\"query\":\"...\"}");
  }
  return parsed as Record<string, unknown>;
}

function defaultParams(tool: PlaygroundTool) {
  const params: Record<string, unknown> = {};
  for (const parameter of tool.parameters ?? []) {
    if (parameter.default !== undefined && parameter.default !== null) {
      params[parameter.name] = parameter.default;
    } else if (parameter.type === "string") {
      params[parameter.name] = "";
    } else if (parameter.type === "integer" || parameter.type === "number") {
      params[parameter.name] = 0;
    } else if (parameter.type === "boolean") {
      params[parameter.name] = false;
    }
  }
  return JSON.stringify(params, null, 2);
}

export function PlaygroundPage() {
  const plugins = usePluginsList();
  const knowledge = useKnowledgeBases();
  const tools = plugins.data?.tools ?? [];
  const capabilities = plugins.data?.capabilities ?? [];
  const pluginManifests = plugins.data?.plugins ?? [];
  const [mode, setMode] = useState<"tool" | "capability">("tool");
  const [selectedToolName, setSelectedToolName] = useState("");
  const [selectedCapabilityName, setSelectedCapabilityName] = useState("");
  const [paramsJson, setParamsJson] = useState("{}");
  const [content, setContent] = useState("请用两三句话解释为什么分步骤学习更有效。");
  const [enabledTools, setEnabledTools] = useState<string[]>([]);
  const [selectedKbs, setSelectedKbs] = useState<string[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false);

  const activeTool = tools.find((tool) => tool.name === selectedToolName) ?? tools[0];
  const activeCapability =
    capabilities.find((capability) => capability.name === selectedCapabilityName) ?? capabilities[0];
  const visibleLogs = logs.slice(-80);

  const selectedToolParams = useMemo(
    () => (activeTool ? JSON.stringify(activeTool.parameters ?? [], null, 2) : "[]"),
    [activeTool],
  );

  const resetOutput = () => {
    setLogs([]);
    setResult("");
    setError("");
  };

  const handleStreamEvent: SseEventHandler = (event, payload) => {
    if (event === "log") {
      setLogs((current) => [...current, String(payload.line ?? payload.text ?? "")]);
      return;
    }
    if (event === "stream") {
      const type = String(payload.type ?? "stream");
      const stage = String(payload.stage ?? payload.source ?? "");
      const text = String(payload.content ?? "");
      setLogs((current) => [...current, [type, stage, text].filter(Boolean).join(" · ")]);
      return;
    }
    if (event === "result") {
      setResult(JSON.stringify(payload, null, 2));
      return;
    }
    if (event === "error") {
      setError(String(payload.detail ?? payload.text ?? "执行失败"));
    }
  };

  const executeTool = async () => {
    if (!activeTool) return;
    resetOutput();
    setRunning(true);
    try {
      const params = parseJsonObject(paramsJson);
      await streamPluginToolExecution({
        toolName: activeTool.name,
        params,
        onEvent: handleStreamEvent,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "执行失败");
    } finally {
      setRunning(false);
    }
  };

  const executeToolSync = async () => {
    if (!activeTool) return;
    resetOutput();
    setRunning(true);
    try {
      const params = parseJsonObject(paramsJson);
      setLogs([withLegacyText(`正在执行：${activeTool.name}`, `sync: /api/v1/plugins/tools/${activeTool.name}/execute`)]);
      const payload = await executePluginTool({ toolName: activeTool.name, params });
      setResult(JSON.stringify(payload, null, 2));
      setLogs((current) => [...current, payload.success === false ? "执行失败" : "执行完成"]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "执行失败");
    } finally {
      setRunning(false);
    }
  };

  const executeCapability = async () => {
    if (!activeCapability || !content.trim()) return;
    resetOutput();
    setRunning(true);
    try {
      await streamPluginCapabilityExecution({
        capabilityName: activeCapability.name,
        content,
        tools: enabledTools,
        knowledgeBases: selectedKbs,
        onEvent: handleStreamEvent,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "执行失败");
    } finally {
      setRunning(false);
    }
  };

  const toggleTool = (name: string) => {
    setEnabledTools((current) =>
      current.includes(name) ? current.filter((item) => item !== name) : [...current, name],
    );
  };

  const toggleKb = (name: string) => {
    setSelectedKbs((current) =>
      current.includes(name) ? current.filter((item) => item !== name) : [...current, name],
    );
  };

  return (
    <div className="h-full overflow-y-auto px-4 py-4 pb-24 lg:px-5 lg:pb-5">
      <div className="mx-auto max-w-6xl space-y-4">
        <NotionProductHero
          eyebrow="实验"
          title="在不打扰主流程的地方试能力"
          legacyTitle="能力实验室"
          description="试运行工具和能力，查看它们会如何响应。这里保留给调试，日常学习不用进来。"
          accent="purple"
          imageSrc="/illustrations/notion-lab-console.svg"
          imageAlt="能力实验室预览"
          people="music"
          previewTitle="调试放这里，学习页保持清爽"
          previewDescription="工具、能力和结果分开看，方便定位问题。"
          tiles={[
            { label: "工具", helper: "直接运行", tone: "yellow" },
            { label: "能力", helper: "编排调用", tone: "sky" },
            { label: "结果", helper: "即时查看", tone: "lavender" },
          ]}
          actions={
            <div className="flex rounded-lg border border-line bg-canvas p-1">
              {(["tool", "capability"] as const).map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => setMode(item)}
                  data-testid={`playground-mode-${item}`}
                  className={`min-h-9 rounded-md px-3 text-sm transition ${
                    mode === item ? "bg-white text-brand-purple shadow-[0_1px_2px_rgba(15,15,15,0.04)]" : "text-slate-500 hover:text-ink"
                  }`}
                >
                  {item === "tool" ? "工具" : "能力"}
                </button>
              ))}
            </div>
          }
        />

        <motion.div
          className="flex flex-wrap gap-x-4 gap-y-1.5"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22, delay: 0.04 }}
        >
          <Metric label="工具" value={tools.length} detail="可执行工具" icon={<Wrench size={19} />} />
          <Metric label="能力" value={capabilities.length} detail="学习能力" icon={<Sparkles size={19} />} />
          <Metric label="插件" value={pluginManifests.length} detail="扩展项" icon={<Beaker size={19} />} />
        </motion.div>

        <div className="grid gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
          <aside className="rounded-lg border border-line bg-white p-3">
            <h2 className="text-base font-semibold text-ink">注册清单</h2>
            {plugins.isLoading ? (
              <div className="mt-4 flex items-center gap-2 text-sm text-slate-500">
                <Loader2 size={16} className="animate-spin" />
                正在读取可执行项
              </div>
            ) : mode === "tool" ? (
              <RegistryList
                items={tools}
                activeName={activeTool?.name}
                onSelect={setSelectedToolName}
                icon={<Wrench size={16} />}
              />
            ) : (
              <RegistryList
                items={capabilities}
                activeName={activeCapability?.name}
                onSelect={setSelectedCapabilityName}
                icon={<Sparkles size={16} />}
              />
            )}

            <div className="mt-4">
              <h3 className="text-sm font-semibold text-ink">扩展项</h3>
              <div className="mt-3 grid gap-2">
                <AnimatePresence initial={false}>
                  {pluginManifests.slice(0, 6).map((plugin) => (
                    <motion.div
                      key={plugin.name}
                      className="dt-interactive rounded-lg border border-line bg-white p-3 hover:border-brand-purple-300"
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -6 }}
                      transition={{ duration: 0.18 }}
                    >
                    <div className="flex items-center gap-2">
                      <Badge tone="neutral">{plugin.type || "扩展"}</Badge>
                      <span className="truncate text-sm font-semibold text-ink">{plugin.name}</span>
                    </div>
                    <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-500">
                      {plugin.description || "暂无描述"}
                    </p>
                    </motion.div>
                  ))}
                </AnimatePresence>
                {!pluginManifests.length ? (
                  <p className="rounded-lg border border-dashed border-line bg-canvas p-3 text-sm text-slate-500">
                    当前没有额外扩展项。
                  </p>
                ) : null}
              </div>
            </div>
          </aside>

          <main className="space-y-4">
            {mode === "tool" ? (
              <ToolRunner
                tool={activeTool}
                paramsJson={paramsJson}
                selectedToolParams={selectedToolParams}
                running={running}
                onParams={setParamsJson}
                onUseDefault={() => activeTool && setParamsJson(defaultParams(activeTool))}
                onRun={() => void executeTool()}
                onRunSync={() => void executeToolSync()}
              />
            ) : (
              <CapabilityRunner
                capability={activeCapability}
                content={content}
                tools={tools}
                enabledTools={enabledTools}
                knowledgeBases={knowledge.data ?? []}
                selectedKbs={selectedKbs}
                running={running}
                onContent={setContent}
                onToggleTool={toggleTool}
                onToggleKb={toggleKb}
                onRun={() => void executeCapability()}
              />
            )}

            <motion.section
              className="rounded-lg border border-line bg-white p-3"
              layout
              transition={{ duration: 0.2 }}
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h2 className="text-base font-semibold text-ink">试用结果</h2>
                {running ? <Badge tone="brand">运行中</Badge> : <Badge tone="neutral">待运行</Badge>}
              </div>
              <AnimatePresence>
                {error ? (
                  <motion.p
                    className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-brand-red"
                    initial={{ opacity: 0, y: -6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: 0.16 }}
                  >
                    {error}
                  </motion.p>
                ) : null}
              </AnimatePresence>
              <div className="mt-4 grid gap-4">
                <div
                  className="dt-code-surface min-h-[260px] rounded-lg p-4"
                  data-testid="playground-result"
                >
                  <AnimatePresence mode="wait">
                    {result ? (
                      <motion.pre
                        key="result"
                        className="max-h-[360px] overflow-auto whitespace-pre-wrap text-xs leading-6 text-slate-700"
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -6 }}
                        transition={{ duration: 0.18 }}
                      >
                        {result}
                      </motion.pre>
                    ) : (
                      <motion.div
                        key="empty"
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -6 }}
                        transition={{ duration: 0.18 }}
                      >
                        <EmptyState icon={<ScrollText size={24} />} title="等待结果" description="执行完成后会展示最终结果。" />
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
                <details className="rounded-lg border border-line bg-canvas p-3 [&>summary::-webkit-details-marker]:hidden">
                  <summary
                    className="dt-interactive flex cursor-pointer list-none items-center justify-between gap-3 rounded-lg px-1 py-1"
                    data-testid="playground-logs-toggle"
                  >
                    <span>
                      <span className="block text-sm font-semibold text-ink">运行日志</span>
                      <span className="mt-1 block text-sm text-slate-500">排查执行过程时再查看。</span>
                    </span>
                    <Badge tone={visibleLogs.length ? "brand" : "neutral"}>{visibleLogs.length ? `${visibleLogs.length} 条` : "等待"}</Badge>
                  </summary>
                  <div
                    className="dt-event-feed mt-4 min-h-28 rounded-lg p-3 text-xs leading-6"
                    data-testid="playground-logs"
                  >
                    <AnimatePresence initial={false}>
                      {visibleLogs.length ? (
                        visibleLogs.map((line, index) => (
                          <motion.p
                            key={`${index}-${line.slice(0, 24)}`}
                            initial={{ opacity: 0, y: 6 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0 }}
                            transition={{ duration: 0.14 }}
                            className="dt-event-row font-mono"
                          >
                            <LogText line={line} />
                          </motion.p>
                        ))
                      ) : (
                        <motion.p className="text-slate-500" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                          运行日志会显示在这里。
                        </motion.p>
                      )}
                    </AnimatePresence>
                  </div>
                </details>
              </div>
            </motion.section>
          </main>
        </div>
      </div>
    </div>
  );
}

function LogText({ line }: { line: string }) {
  const [visible] = line.split(LEGACY_TEXT_SEPARATOR);
  return <>{visible}</>;
}

function RegistryList({
  items,
  activeName,
  onSelect,
  icon,
}: {
  items: Array<PlaygroundTool | PlaygroundCapability>;
  activeName?: string;
  onSelect: (name: string) => void;
  icon: React.ReactNode;
}) {
  if (!items.length) {
    return (
      <div className="mt-4">
        <EmptyState icon={<Terminal size={24} />} title="暂无注册项" description="还没有可执行项目。" />
      </div>
    );
  }
  return (
    <div className="mt-4 grid gap-2">
      {items.map((item) => {
        const active = activeName === item.name;
        return (
          <motion.button
            key={item.name}
            type="button"
            onClick={() => onSelect(item.name)}
            data-testid={`playground-registry-${item.name}`}
            layout
            whileHover={{ y: -1 }}
            whileTap={{ scale: 0.99 }}
            className={`dt-interactive rounded-lg border p-3 text-left transition ${
              active ? "border-brand-purple-300 bg-tint-lavender" : "border-line bg-white hover:border-brand-purple-300"
            }`}
          >
            <div className="flex items-center gap-2">
              <span className="text-brand-purple">{icon}</span>
              <span className="min-w-0 truncate text-sm font-semibold text-ink">{item.name}</span>
            </div>
            <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-500">
              {item.description || "暂无描述"}
            </p>
          </motion.button>
        );
      })}
    </div>
  );
}

function ToolRunner({
  tool,
  paramsJson,
  selectedToolParams,
  running,
  onParams,
  onUseDefault,
  onRun,
  onRunSync,
}: {
  tool?: PlaygroundTool;
  paramsJson: string;
  selectedToolParams: string;
  running: boolean;
  onParams: (value: string) => void;
  onUseDefault: () => void;
  onRun: () => void;
  onRunSync: () => void;
}) {
  if (!tool) {
    return <EmptyState icon={<Wrench size={24} />} title="暂无工具" description="当前没有可用工具。" />;
  }
  return (
    <motion.section
      className="rounded-lg border border-line bg-white p-3"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Badge tone="brand">工具</Badge>
          <h2 className="mt-3 text-base font-semibold text-ink">{tool.name}</h2>
          <p className="mt-1 text-sm leading-6 text-slate-500">{tool.description || "暂无描述"}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button tone="secondary" onClick={onRunSync} disabled={running} data-testid="playground-tool-run-sync">
            {running ? <Loader2 size={16} className="animate-spin" /> : <Code2 size={16} />}
            同步执行
          </Button>
          <Button tone="primary" onClick={onRun} disabled={running} data-testid="playground-tool-run">
            {running ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
            执行工具
          </Button>
        </div>
      </div>

      <div className="mt-4 grid gap-3 xl:grid-cols-2">
        <FieldShell label="参数" hint="高级格式">
          <TextArea
            value={paramsJson}
            onChange={(event) => onParams(event.target.value)}
            className="min-h-72 font-mono text-xs leading-6"
            data-testid="playground-tool-params"
          />
          <Button tone="quiet" className="mt-2 min-h-8 px-2 text-xs" onClick={onUseDefault}>
            使用参数模板
          </Button>
        </FieldShell>
        <FieldShell label="参数定义">
          <pre className="dt-code-surface min-h-72 overflow-auto rounded-lg p-3 text-xs leading-6">
            {selectedToolParams}
          </pre>
        </FieldShell>
      </div>
    </motion.section>
  );
}

function CapabilityRunner({
  capability,
  content,
  tools,
  enabledTools,
  knowledgeBases,
  selectedKbs,
  running,
  onContent,
  onToggleTool,
  onToggleKb,
  onRun,
}: {
  capability?: PlaygroundCapability;
  content: string;
  tools: PlaygroundTool[];
  enabledTools: string[];
  knowledgeBases: Array<{ name: string; is_default?: boolean }>;
  selectedKbs: string[];
  running: boolean;
  onContent: (value: string) => void;
  onToggleTool: (name: string) => void;
  onToggleKb: (name: string) => void;
  onRun: () => void;
}) {
  if (!capability) {
    return <EmptyState icon={<Sparkles size={24} />} title="暂无能力" description="当前没有可用能力。" />;
  }
  return (
    <motion.section
      className="rounded-lg border border-line bg-white p-3"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Badge tone="brand">能力</Badge>
          <h2 className="mt-3 text-base font-semibold text-ink">{capability.name}</h2>
          <p className="mt-1 text-sm leading-6 text-slate-500">{capability.description || "暂无描述"}</p>
        </div>
        <Button
          tone="primary"
          onClick={onRun}
          disabled={running || !content.trim()}
          data-testid="playground-capability-run"
        >
          {running ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
          运行能力
        </Button>
      </div>

      <div className="mt-4 grid gap-3 xl:grid-cols-[minmax(0,1fr)_320px]">
        <FieldShell label="输入内容">
          <TextArea
            value={content}
            onChange={(event) => onContent(event.target.value)}
            className="min-h-72"
            data-testid="playground-capability-content"
          />
        </FieldShell>
        <div className="space-y-4">
          <div>
            <p className="text-sm font-semibold text-ink">启用工具</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {tools.slice(0, 12).map((tool) => (
                <motion.button
                  key={tool.name}
                  type="button"
                  onClick={() => onToggleTool(tool.name)}
                  data-testid={`playground-tool-toggle-${tool.name}`}
                  whileHover={{ y: -1 }}
                  whileTap={{ scale: 0.98 }}
                  className={`rounded-md border px-2 py-1 text-xs transition ${
                    enabledTools.includes(tool.name)
                      ? "border-brand-purple-300 bg-tint-lavender text-brand-purple"
                      : "border-line bg-white text-slate-600 hover:border-brand-purple-300"
                  }`}
                >
                  <Code2 size={12} className="mr-1 inline" />
                  {tool.name}
                </motion.button>
              ))}
            </div>
          </div>
          <div>
            <p className="text-sm font-semibold text-ink">知识库</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {knowledgeBases.map((kb) => (
                <motion.button
                  key={kb.name}
                  type="button"
                  onClick={() => onToggleKb(kb.name)}
                  data-testid={`playground-kb-toggle-${kb.name}`}
                  whileHover={{ y: -1 }}
                  whileTap={{ scale: 0.98 }}
                  className={`rounded-md border px-2 py-1 text-xs transition ${
                    selectedKbs.includes(kb.name)
                      ? "border-brand-purple-300 bg-tint-lavender text-brand-purple"
                      : "border-line bg-white text-slate-600 hover:border-brand-purple-300"
                  }`}
                >
                  <Database size={12} className="mr-1 inline" />
                  {kb.name}
                </motion.button>
              ))}
              {!knowledgeBases.length ? <span className="text-xs text-slate-500">暂无知识库</span> : null}
            </div>
          </div>
          {capability.stages?.length ? (
            <div>
              <p className="text-sm font-semibold text-ink">阶段</p>
              <div className="markdown-body mt-2 border-t border-line pt-3 text-sm">
                <MarkdownRenderer>{capability.stages.map((stage) => `- ${stage}`).join("\n")}</MarkdownRenderer>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </motion.section>
  );
}
