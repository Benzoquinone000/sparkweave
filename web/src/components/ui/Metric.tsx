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
    <div className="dt-soft-enter inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-md border border-line bg-white px-2 py-1 text-xs">
      {icon ? <span className="shrink-0 text-charcoal">{icon}</span> : null}
      <span className="shrink-0 text-steel">{label}</span>
      <span className="min-w-0 truncate font-semibold text-ink">{value}</span>
      {detail ? <span className="hidden min-w-0 truncate text-steel sm:inline">· {detail}</span> : null}
    </div>
  );
}
