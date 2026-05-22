import type { ReactNode } from "react";

export function Panel({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <section className={`dt-soft-enter dt-notion-card dt-dynamic-card p-3 ${className}`}>{children}</section>;
}

export function PanelHeader({
  title,
  description,
  action,
}: {
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-2.5 border-b border-line-soft pb-2.5">
      <div className="min-w-0">
        <h2 className="text-sm font-semibold leading-5 text-ink">{title}</h2>
        {description ? <p className="mt-1 text-xs leading-5 text-steel">{description}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}
