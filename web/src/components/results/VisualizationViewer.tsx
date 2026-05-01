import type { Chart as ChartInstance, ChartConfiguration, ChartType } from "chart.js";
import { Check, Code2, Copy, Loader2 } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { PersonalizationBrief } from "@/components/results/PersonalizationBrief";
import { ResourceEvidenceButton } from "@/components/results/ResourceEvidenceButton";
import { evidenceFingerprint } from "@/lib/evidence";
import type { VisualizeResult } from "@/lib/types";

let chartRegistered = false;
let mermaidConfigured = false;

async function loadChartRuntime() {
  const runtime = await import("chart.js");
  if (!chartRegistered) {
    runtime.Chart.register(...runtime.registerables);
    chartRegistered = true;
  }
  return runtime;
}

async function loadMermaidRuntime() {
  const runtime = await import("mermaid");
  const mermaid = runtime.default;
  ensureMermaidConfigured(mermaid);
  return mermaid;
}

function ensureMermaidConfigured(mermaid: typeof import("mermaid")["default"]) {
  if (mermaidConfigured) return;
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: "strict",
    theme: "base",
    themeVariables: {
      primaryColor: "#F7FAFC",
      primaryBorderColor: "#0F766E",
      primaryTextColor: "#111827",
      lineColor: "#2563EB",
      fontFamily: "Inter, ui-sans-serif, system-ui",
    },
  });
  mermaidConfigured = true;
}

function stripCodeFences(source: string) {
  const trimmed = source.trim();
  const fenced = trimmed.match(/^```[\w-]*\s*([\s\S]*?)\s*```$/);
  return fenced ? fenced[1].trim() : trimmed;
}

function getErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}

function ErrorPanel({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm leading-6 text-brand-red">
      <p className="font-semibold">{title}</p>
      <p className="mt-1 break-words text-red-700">{detail}</p>
    </div>
  );
}

function SvgPreview({ svg }: { svg: string }) {
  const sanitized = useMemo(() => {
    const trimmed = stripCodeFences(svg).trim();
    return trimmed.startsWith("<svg") ? trimmed : "";
  }, [svg]);

  if (!sanitized) {
    return <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-brand-red">SVG 内容无效。</p>;
  }

  return (
    <div
      data-testid="svg-preview"
      className="flex justify-center overflow-x-auto rounded-lg border border-line bg-white p-3"
      dangerouslySetInnerHTML={{ __html: sanitized }}
    />
  );
}

function MermaidPreview({ code }: { code: string }) {
  const reactId = useId();
  const previewId = useMemo(() => `mermaid-${reactId.replace(/[^a-zA-Z0-9_-]/g, "")}`, [reactId]);
  const [renderedSvg, setRenderedSvg] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function renderDiagram() {
      setLoading(true);
      setError(null);
      try {
        const mermaidRuntime = await loadMermaidRuntime();
        const diagram = stripCodeFences(code);
        const rendered = await mermaidRuntime.render(previewId, diagram);
        if (!cancelled) {
          setRenderedSvg(rendered.svg);
          setLoading(false);
        }
      } catch (renderError) {
        if (!cancelled) {
          setRenderedSvg("");
          setError(getErrorMessage(renderError));
          setLoading(false);
        }
      }
    }

    void renderDiagram();

    return () => {
      cancelled = true;
    };
  }, [code, previewId]);

  if (loading) {
    return (
      <div className="flex min-h-64 items-center justify-center rounded-lg border border-line bg-white text-sm text-slate-500">
        <Loader2 size={18} className="animate-spin text-brand-blue" />
        <span className="ml-2">正在渲染 Mermaid 图表</span>
      </div>
    );
  }

  if (error) {
    return <ErrorPanel title="Mermaid 渲染失败" detail={error} />;
  }

  return (
    <div
      data-testid="mermaid-preview"
      className="overflow-x-auto rounded-lg border border-line bg-white p-3"
      dangerouslySetInnerHTML={{ __html: renderedSvg }}
    />
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function pickChartConfig(value: unknown) {
  if (!isRecord(value)) {
    throw new Error("Chart.js 配置必须是 JSON 对象。");
  }
  if (isRecord(value.config)) return value.config;
  if (isRecord(value.chart)) return value.chart;
  return value;
}

function parseChartConfig(code: string): ChartConfiguration {
  const parsed = JSON.parse(stripCodeFences(code)) as unknown;
  const raw = pickChartConfig(parsed);
  if (typeof raw.type !== "string") {
    throw new Error("缺少 Chart.js type 字段。");
  }
  if (!isRecord(raw.data)) {
    throw new Error("缺少 Chart.js data 字段。");
  }
  const options = isRecord(raw.options) ? raw.options : {};

  return {
    ...(raw as unknown as ChartConfiguration),
    type: raw.type as ChartType,
    data: raw.data as unknown as ChartConfiguration["data"],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      ...options,
    } as ChartConfiguration["options"],
  };
}

function ChartJsPreview({ code }: { code: string }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);
  const parsed = useMemo(() => {
    try {
      return { config: parseChartConfig(code), error: null };
    } catch (chartError) {
      return { config: null, error: getErrorMessage(chartError) };
    }
  }, [code]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !parsed.config) return;

    const targetCanvas = canvas;
    let cancelled = false;
    let chart: ChartInstance | null = null;

    async function renderChart() {
      try {
        const runtime = await loadChartRuntime();
        if (cancelled || !parsed.config) return;
        chart = new runtime.Chart(targetCanvas, parsed.config);
        setRuntimeError(null);
      } catch (chartError) {
        if (!cancelled) setRuntimeError(getErrorMessage(chartError));
      }
    }

    void renderChart();

    return () => {
      cancelled = true;
      chart?.destroy();
    };
  }, [parsed.config]);

  const error = parsed.error ?? runtimeError;

  return (
    <div data-testid="chartjs-preview" className="rounded-lg border border-line bg-white p-3">
      {error ? <ErrorPanel title="Chart.js 渲染失败" detail={error} /> : null}
      <div className={`h-80 min-h-64 ${error ? "hidden" : ""}`}>
        <canvas ref={canvasRef} aria-label="Chart.js visualization" />
      </div>
    </div>
  );
}

export function VisualizationViewer({ result }: { result: VisualizeResult }) {
  const [showCode, setShowCode] = useState(false);
  const [copied, setCopied] = useState(false);
  const evidencePayload = useMemo(() => {
    const fingerprint = evidenceFingerprint(`${result.render_type}:${result.code.content}`);
    const title = result.analysis?.description || result.response || `${result.render_type} 图解`;
    return {
      source: "resource",
      source_id: `visualize:${fingerprint}`,
      actor: "learner",
      verb: "viewed",
      object_type: "resource",
      object_id: `visualize:${fingerprint}`,
      title: title.slice(0, 120),
      summary: result.response || result.analysis?.rationale || result.analysis?.data_description || "",
      resource_type: "visual",
      confidence: 0.5,
      weight: 0.55,
      metadata: {
        render_type: result.render_type,
        chart_type: result.analysis?.chart_type || "",
        style_hint: result.style_hint || "",
        learner_profile_hints: result.learner_profile_hints ?? {},
      },
    };
  }, [result]);

  const copyCode = async () => {
    await navigator.clipboard.writeText(result.code.content);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="rounded-lg border border-line bg-canvas p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="brand">可视化</Badge>
        <Badge tone="neutral">{result.render_type}</Badge>
        {result.analysis?.chart_type ? <Badge tone="neutral">{result.analysis.chart_type}</Badge> : null}
      </div>

      {result.response ? <p className="mt-3 text-sm leading-6 text-slate-600">{result.response}</p> : null}
      <PersonalizationBrief hints={result.learner_profile_hints} styleHint={result.style_hint} className="mt-3" />

      <div className="mt-4">
        {result.render_type === "svg" ? (
          <SvgPreview svg={result.code.content} />
        ) : result.render_type === "mermaid" ? (
          <MermaidPreview code={result.code.content} />
        ) : (
          <ChartJsPreview code={result.code.content} />
        )}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <ResourceEvidenceButton payload={evidencePayload} testId="visualization-evidence-button" />
        <Button tone="quiet" className="min-h-8 px-2 text-xs" onClick={() => setShowCode((value) => !value)}>
          <Code2 size={14} />
          {showCode ? "隐藏代码" : "显示代码"}
        </Button>
        <Button tone="quiet" className="min-h-8 px-2 text-xs" onClick={() => void copyCode()}>
          {copied ? <Check size={14} /> : <Copy size={14} />}
          {copied ? "已复制" : "复制代码"}
        </Button>
      </div>

      {showCode ? (
        <pre className="dt-code-surface mt-4 max-h-96 overflow-auto rounded-lg p-4 text-xs leading-6">
          {result.code.content}
        </pre>
      ) : null}

      {result.review?.changed && result.review.review_notes ? (
        <p className="mt-3 text-xs leading-5 text-slate-500">检查建议：{result.review.review_notes}</p>
      ) : null}
    </div>
  );
}
