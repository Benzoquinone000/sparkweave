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
    <div className="dt-soft-enter rounded-lg border border-dashed border-line bg-white/90 p-5 text-center">
      {icon ? <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-lg border border-line bg-surface text-charcoal">{icon}</div> : null}
      <p className="mt-3 text-sm font-semibold leading-6 text-ink">{title}</p>
      <p className="mx-auto mt-1 max-w-xl text-sm leading-6 text-steel">{description}</p>
      {action ? <div className="mt-3">{action}</div> : null}
    </div>
  );
}
