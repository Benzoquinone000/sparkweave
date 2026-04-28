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
    <div className="dt-soft-enter rounded-lg border border-dashed border-line bg-white p-4 text-center">
      {icon ? <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-lg bg-canvas text-brand-teal">{icon}</div> : null}
      <p className="mt-3 text-sm font-semibold text-ink">{title}</p>
      <p className="mx-auto mt-1 max-w-xl text-sm leading-6 text-slate-500">{description}</p>
      {action ? <div className="mt-3">{action}</div> : null}
    </div>
  );
}
