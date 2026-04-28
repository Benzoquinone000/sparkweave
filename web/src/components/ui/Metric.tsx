import type { ReactNode } from "react";

export function Metric({
  label,
  value,
  detail,
  icon,
}: {
  label: string;
  value: ReactNode;
  detail?: string;
  icon?: ReactNode;
}) {
  return (
    <div className="dt-soft-enter inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-md px-0.5 py-0.5 text-xs">
      {icon ? <span className="shrink-0 text-brand-teal/80">{icon}</span> : null}
      <span className="shrink-0 text-slate-500">{label}</span>
      <span className="min-w-0 truncate font-semibold text-ink">{value}</span>
      {detail ? <span className="hidden min-w-0 truncate text-slate-400 sm:inline">· {detail}</span> : null}
    </div>
  );
}
