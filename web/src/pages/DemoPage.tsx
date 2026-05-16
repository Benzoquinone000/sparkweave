import { Link } from "@tanstack/react-router";
import {
  ArrowRight,
  CheckCircle2,
  FileImage,
  GraduationCap,
  Loader2,
  MonitorPlay,
  RadioTower,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { useSystemStatus } from "@/hooks/useApiQueries";
import type { GuideTone } from "@/lib/guideDisplay";
import type { SystemStatus } from "@/lib/types";
import { CompetitionDemoDashboard } from "./guide/CompetitionDemoDashboard";
import { demoCoursePackage } from "./demo/demoCoursePackage";

type DemoRuntimeItem = {
  label: string;
  detail: string;
  status?: string;
  model?: string | null;
  icon: LucideIcon;
};

const screenshotTargets = [
  { label: "开场主图", detail: "/demo 比赛演示驾驶舱", selector: "competition-demo-dashboard" },
  { label: "多智能体", detail: "Chat 回答中的接力剧场", selector: "agent-relay-theater" },
  { label: "多模态资源", detail: "Guide 当前任务资源 Studio", selector: "guide-multimodal-resource-studio" },
  { label: "知识地图", detail: "知识掌握地铁图", selector: "guide-knowledge-transit-map" },
  { label: "动态评估", detail: "路线调整 Before/After", selector: "guide-path-adjustment-morph" },
  { label: "证据依据", detail: "RAG 证据瀑布", selector: "rag-evidence-waterfall" },
];

export function DemoPage() {
  const statusQuery = useSystemStatus();
  const runtimeItems = buildRuntimeItems(statusQuery.data);
  const script = demoCoursePackage.recording_script?.segments ?? [];
  const slides = demoCoursePackage.presentation_outline?.slides ?? [];

  return (
    <div className="h-full overflow-y-auto bg-canvas" data-testid="competition-demo-page">
      <div className="mx-auto max-w-7xl px-4 py-5 lg:px-6">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3 rounded-lg border border-line bg-white p-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="brand">比赛直达入口</Badge>
              <Badge tone="success">稳定演示包</Badge>
            </div>
            <h1 className="mt-3 text-2xl font-semibold text-ink">SparkWeave 评委演示台</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              打开后直接展示赛题五项、学习闭环、多智能体协作、讯飞能力链和提交材料证据，适合录屏开场与 PPT 截图。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link
              to="/guide"
              className="dt-interactive inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-line-strong bg-transparent px-[18px] text-sm font-medium text-ink hover:border-ink hover:bg-white"
            >
              <GraduationCap size={16} />
              进入可操作导学
            </Link>
            <Link
              to="/chat"
              className="dt-interactive inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-brand-purple bg-brand-purple px-[18px] text-sm font-medium text-white shadow-[rgba(86,69,212,0.16)_0_1px_2px] hover:bg-brand-purple-800"
            >
              <Sparkles size={16} />
              打开对话演示
            </Link>
          </div>
        </div>

        <CompetitionDemoDashboard coursePackage={demoCoursePackage} loading={false} />

        <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
          <section className="rounded-lg border border-line bg-white p-4" data-testid="demo-recording-script">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <MonitorPlay size={18} className="text-brand-purple" />
                <h2 className="text-base font-semibold text-ink">7 分钟录屏路线</h2>
              </div>
              <Badge tone="brand">{demoCoursePackage.recording_script?.total_minutes ?? 7} 分钟</Badge>
            </div>
            <div className="mt-4 grid gap-2 md:grid-cols-5">
              {script.slice(0, 5).map((item, index) => (
                <div key={`${item.minute}-${item.screen}`} className="rounded-lg border border-line bg-canvas p-3">
                  <div className="flex items-center justify-between gap-2">
                    <Badge tone="neutral">{item.minute || `0${index + 1}`}</Badge>
                    {index < script.length - 1 ? <ArrowRight size={14} className="text-slate-300" /> : <CheckCircle2 size={14} className="text-emerald-600" />}
                  </div>
                  <p className="mt-2 text-sm font-semibold text-ink">{item.screen || "演示画面"}</p>
                  <p className="mt-1 line-clamp-3 text-xs leading-5 text-slate-600">{item.narration || "按当前页面证据讲解。"}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-lg border border-line bg-white p-4" data-testid="demo-runtime-iflytek">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <RadioTower size={18} className="text-brand-purple" />
                <h2 className="text-base font-semibold text-ink">讯飞/服务状态</h2>
              </div>
              {statusQuery.isFetching ? <Loader2 size={15} className="animate-spin text-brand-purple" /> : null}
            </div>
            <div className="mt-3 space-y-2">
              {runtimeItems.map((item) => (
                <RuntimeProofRow key={item.label} item={item} />
              ))}
            </div>
            <p className="mt-3 rounded-lg border border-line bg-canvas p-2 text-xs leading-5 text-slate-600">
              服务离线时仍使用稳定演示包，正式录屏前再回到设置页完成连通性检查。
            </p>
          </section>
        </div>

        <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <section className="rounded-lg border border-line bg-white p-4" data-testid="demo-ppt-shot-list">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <FileImage size={18} className="text-brand-purple" />
                <h2 className="text-base font-semibold text-ink">PPT 截图位</h2>
              </div>
              <Badge tone="neutral">{screenshotTargets.length} 张主图</Badge>
            </div>
            <div className="mt-3 grid gap-2 md:grid-cols-2">
              {screenshotTargets.map((item) => (
                <div key={item.selector} className="rounded-lg border border-line bg-canvas p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-semibold text-ink">{item.label}</p>
                    <span className="rounded-md border border-line bg-white px-2 py-1 text-[11px] text-slate-500">
                      {item.selector}
                    </span>
                  </div>
                  <p className="mt-1 text-xs leading-5 text-slate-600">{item.detail}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-lg border border-line bg-white p-4" data-testid="demo-presentation-outline">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-base font-semibold text-ink">PPT 讲述骨架</h2>
              <Badge tone="brand">{demoCoursePackage.presentation_outline?.slide_count ?? slides.length} 页</Badge>
            </div>
            <div className="mt-3 space-y-2">
              {slides.slice(0, 4).map((slide) => (
                <div key={`${slide.slide_no}-${slide.title}`} className="rounded-lg border border-line bg-canvas p-3">
                  <p className="text-sm font-semibold text-ink">
                    P{slide.slide_no ?? "-"} · {slide.title || "演示页"}
                  </p>
                  <p className="mt-1 text-xs leading-5 text-slate-600">{slide.evidence || slide.purpose || "补充系统截图。"}</p>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function RuntimeProofRow({ item }: { item: DemoRuntimeItem }) {
  const Icon = item.icon;
  return (
    <div className="grid grid-cols-[2rem_minmax(0,1fr)_auto] items-center gap-2 rounded-lg border border-line bg-canvas px-3 py-2">
      <span className="grid h-8 w-8 place-items-center rounded-lg bg-white text-brand-purple">
        <Icon size={15} />
      </span>
      <span className="min-w-0">
        <span className="block truncate text-xs font-semibold text-ink">{item.label}</span>
        <span className="block truncate text-xs text-slate-500">{item.model || item.detail}</span>
      </span>
      <Badge tone={runtimeTone(item.status)}>{runtimeLabel(item.status)}</Badge>
    </div>
  );
}

function buildRuntimeItems(status?: SystemStatus): DemoRuntimeItem[] {
  return [
    {
      label: "讯飞星火 / LLM",
      detail: "生成讲解、资源和学习处方",
      status: status?.llm?.status,
      model: status?.llm?.model,
      icon: Sparkles,
    },
    {
      label: "Embedding / RAG",
      detail: "课程资料索引与证据检索",
      status: status?.embeddings?.status || status?.rag?.status,
      model: status?.embeddings?.model || status?.rag?.provider,
      icon: RadioTower,
    },
    {
      label: "ONE SEARCH",
      detail: "外部资料与公开视频检索",
      status: status?.search?.status,
      model: status?.search?.provider,
      icon: RadioTower,
    },
    {
      label: "OCR",
      detail: "扫描资料和图片题识别",
      status: status?.ocr?.status,
      model: status?.ocr?.provider,
      icon: FileImage,
    },
    {
      label: "TTS",
      detail: "语音讲解和短视频旁白",
      status: status?.tts?.status,
      model: status?.tts?.provider,
      icon: MonitorPlay,
    },
  ];
}

function runtimeTone(status?: string): GuideTone {
  const value = String(status || "").toLowerCase();
  if (["online", "configured", "healthy", "ready", "ok"].includes(value)) return "success";
  if (["optional", "available", "fallback"].includes(value)) return "brand";
  if (["error", "offline", "missing", "unconfigured"].includes(value)) return "warning";
  return "neutral";
}

function runtimeLabel(status?: string) {
  const value = String(status || "").toLowerCase();
  if (["online", "configured", "healthy", "ready", "ok"].includes(value)) return "可用";
  if (["optional", "available", "fallback"].includes(value)) return "可配置";
  if (["error", "offline", "missing", "unconfigured"].includes(value)) return "待检查";
  return "待连接";
}
