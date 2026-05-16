import { Plus, RefreshCw } from "lucide-react";

export function RuntimeStatus({
  apiBase,
  backendOnline,
  checking,
  compact = false,
  onRetry,
  testId,
}: {
  apiBase: string;
  backendOnline: boolean;
  checking: boolean;
  compact?: boolean;
  onRetry: () => void;
  testId?: string;
}) {
  if (compact) {
    return (
      <button
        type="button"
        onClick={onRetry}
        disabled={checking}
        className="dt-interactive inline-flex h-9 w-9 items-center justify-center rounded-lg border border-line bg-white text-steel hover:border-[#c8c4be] hover:text-ink disabled:cursor-not-allowed disabled:opacity-60"
        data-testid={testId}
        title={apiBase}
        aria-label={backendOnline ? "服务在线" : checking ? "连接中" : "服务离线"}
      >
        <span
          className={`flex h-2.5 w-2.5 ${backendOnline ? "dt-live-dot bg-emerald-500" : "bg-brand-red"}`}
          style={{ borderRadius: "50%" }}
        />
      </button>
    );
  }

  return (
    <div className="flex min-h-9 min-w-0 items-center gap-2 rounded-lg px-3 text-steel" data-testid={testId} title={apiBase}>
      <span
        className={`h-2 w-2 shrink-0 ${backendOnline ? "dt-live-dot bg-emerald-500" : "bg-brand-red"}`}
        style={{ borderRadius: "50%" }}
      />
      <span className="min-w-0 flex-1 truncate text-xs font-medium text-steel">
        {backendOnline ? "服务在线" : checking ? "连接中" : "服务离线"}
      </span>
      <button
        type="button"
        onClick={onRetry}
        disabled={checking}
        className="dt-interactive flex h-7 items-center justify-center rounded-md px-1.5 text-steel hover:bg-white hover:text-brand-purple disabled:cursor-not-allowed disabled:opacity-60"
        aria-label="重试连接"
      >
        <RefreshCw size={13} className={checking ? "animate-spin" : ""} />
      </button>
    </div>
  );
}

export function BrandInline({
  backendOnline,
  statusTestId,
}: {
  backendOnline: boolean;
  statusTestId?: string;
}) {
  return (
    <div className="flex min-w-0 items-center gap-3">
      <div className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-navy text-white shadow-sm">
        <Plus size={23} strokeWidth={2.2} />
        <span
          data-testid={statusTestId}
          className={`absolute -right-0.5 -top-0.5 h-2.5 w-2.5 border border-white ${
            backendOnline ? "bg-emerald-500" : "bg-brand-red"
          }`}
          style={{ borderRadius: "50%" }}
        />
      </div>
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold text-ink">SparkWeave</p>
        <p className="truncate text-xs text-steel">学习空间</p>
      </div>
    </div>
  );
}
