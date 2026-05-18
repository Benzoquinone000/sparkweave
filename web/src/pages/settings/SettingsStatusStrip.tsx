import type { SystemStatus } from "@/lib/types";

import { friendlyServiceError, LEGACY_TEXT_SEPARATOR } from "./settingsDiagnosticsUtils";

export function InlineLegacyText({ text }: { text: string }) {
  const [visible] = text.split(LEGACY_TEXT_SEPARATOR);
  return <>{visible}</>;
}

export function ServiceStatusStrip({ status }: { status?: SystemStatus }) {
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
      label: "知识库",
      value: status?.rag?.provider ? "智能索引" : status?.rag?.status || "未配置",
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
      label: "OCR",
      value: status?.ocr?.provider || status?.ocr?.status || "可选",
      ok: status?.ocr?.status === "configured" || Boolean(status?.ocr?.provider),
      error: status?.ocr?.error,
    },
  ];

  return (
    <section className="px-1" data-testid="settings-status-strip">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
        {items.map((item) => {
          const displayValue = item.error ? friendlyServiceError(String(item.error)) : item.value;
          return (
            <div key={item.label} className="flex min-w-0 items-center gap-1.5 text-xs">
              <span
                className={`h-1.5 w-1.5 shrink-0 ${item.error ? "bg-brand-red" : item.ok ? "bg-emerald-500" : "bg-slate-300"}`}
                style={{ borderRadius: "50%" }}
              />
              <span className="shrink-0 text-slate-500">{item.label}</span>
              <span className="max-w-[180px] truncate font-medium text-ink">{displayValue}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
