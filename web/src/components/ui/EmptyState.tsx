import type { ReactNode } from "react";

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="dt-soft-enter rounded-lg border border-dashed border-line bg-white/90 p-4 text-center">
      {icon ? <div className="mx-auto flex h-9 w-9 items-center justify-center rounded-lg border border-line bg-surface text-charcoal">{icon}</div> : null}
      <p className="mt-2.5 text-sm font-semibold leading-5 text-ink">{title}</p>
      <p className="mx-auto mt-1 max-w-lg text-xs leading-5 text-steel">{description}</p>
      {action ? <div className="mt-2.5">{action}</div> : null}
    </div>
  );
}
