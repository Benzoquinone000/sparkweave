import type { SystemStatus } from "@/lib/types";

import { friendlyServiceError, LEGACY_TEXT_SEPARATOR } from "./settingsDiagnosticsUtils";

export function InlineLegacyText({ text }: { text: string }) {
  const [visible] = text.split(LEGACY_TEXT_SEPARATOR);
  return <>{visible}</>;
}

type ServiceState = {
  status?: string;
  provider?: string | null;
  model?: string | null;
  fallback?: boolean;
  fallback_reason?: string;
  error?: string;
};

function isFallbackService(service?: ServiceState) {
  return Boolean(
    service?.fallback ||
      service?.status === "fallback" ||
      String(service?.provider || "").startsWith("offline_iflytek_fallback") ||
      String(service?.model || "").startsWith("offline_iflytek_fallback"),
  );
}

function serviceStatusLabel(service: ServiceState | undefined, fallback = "可选") {
  if (isFallbackService(service)) return "离线替补";
  return service?.provider || service?.model || service?.status || fallback;
}

export function ServiceStatusStrip({ status }: { status?: SystemStatus }) {
  const items: Array<{ label: string; value: string; ok: boolean; warning?: boolean; error?: string }> = [
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
      label: "资料理解",
      value: status?.embeddings?.model || status?.embeddings?.status || "未配置",
      ok: status?.embeddings?.status === "configured" || Boolean(status?.embeddings?.model),
      error: status?.embeddings?.error,
    },
    {
      label: "资料库",
      value: status?.rag?.provider ? "智能资料库" : status?.rag?.status || "未配置",
      ok: status?.rag?.status === "configured",
      error: status?.rag?.error,
    },
    {
      label: "搜索",
      value: status?.search?.provider || status?.search?.status || "可选",
      ok: status?.search?.status === "configured" || Boolean(status?.search?.provider),
      error: status?.search?.error,
    },
    {
      label: "图片识别",
      value: serviceStatusLabel(status?.ocr),
      ok: status?.ocr?.status === "configured" || Boolean(status?.ocr?.provider),
      warning: isFallbackService(status?.ocr),
      error: status?.ocr?.error,
    },
    {
      label: "公式识别",
      value: serviceStatusLabel(status?.formula_ocr),
      ok: status?.formula_ocr?.status === "configured" || Boolean(status?.formula_ocr?.provider),
      warning: isFallbackService(status?.formula_ocr),
      error: status?.formula_ocr?.error,
    },
    {
      label: "图片理解",
      value: serviceStatusLabel(status?.image_understanding),
      ok:
        status?.image_understanding?.status === "configured" ||
        Boolean(status?.image_understanding?.provider),
      warning: isFallbackService(status?.image_understanding),
      error: status?.image_understanding?.error,
    },
    {
      label: "语音讲解",
      value: serviceStatusLabel(status?.tts),
      ok: status?.tts?.status === "configured" || Boolean(status?.tts?.provider),
      warning: isFallbackService(status?.tts),
      error: status?.tts?.error,
    },
    {
      label: "语音输入",
      value: serviceStatusLabel(status?.asr),
      ok: status?.asr?.status === "configured" || Boolean(status?.asr?.provider),
      warning: isFallbackService(status?.asr),
      error: status?.asr?.error,
    },
    {
      label: "口语评测",
      value: serviceStatusLabel(status?.speech_eval),
      ok: status?.speech_eval?.status === "configured" || Boolean(status?.speech_eval?.provider),
      warning: isFallbackService(status?.speech_eval),
      error: status?.speech_eval?.error,
    },
  ];

  return (
    <section className="px-1" data-testid="settings-status-strip">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
        {items.map((item) => {
          const displayValue = item.error && !item.warning ? friendlyServiceError(String(item.error)) : item.value;
          return (
            <div key={item.label} className="flex min-w-0 items-center gap-1.5 text-xs">
              <span
                className={`h-1.5 w-1.5 shrink-0 rounded-sm ${
                  item.error && !item.warning ? "bg-brand-red" : item.warning ? "bg-amber-400" : item.ok ? "bg-emerald-500" : "bg-slate-300"
                }`}
              />
              <span className="shrink-0 text-slate-500">{item.label}</span>
              <span className="max-w-[180px] truncate font-medium text-ink" title={item.error || item.value}>
                {displayValue}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
