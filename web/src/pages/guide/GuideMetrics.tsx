import { Badge } from "@/components/ui/Badge";

export function ProgressBar({ value, className = "" }: { value: number; className?: string }) {
  return (
    <div className={`h-2 overflow-hidden rounded-sm bg-slate-100 ${className}`}>
      <div className="h-full rounded-sm bg-brand-purple transition-all" style={{ width: `${Math.max(0, Math.min(value, 100))}%` }} />
    </div>
  );
}

export function EvalMini({ label, value, suffix = "" }: { label: string; value: number | string; suffix?: string }) {
  return (
    <div className="rounded-lg border border-line bg-canvas p-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-ink">
        {value}
        {suffix}
      </p>
    </div>
  );
}

export function EvalList({
  title,
  items,
  empty,
  tone,
}: {
  title: string;
  items: string[];
  empty: string;
  tone: "success" | "warning" | "brand";
}) {
  return (
    <div className="mt-4">
      <p className="text-xs font-semibold text-slate-500">{title}</p>
      <div className="mt-2 space-y-2">
        {(items.length ? items : [empty]).slice(0, 3).map((item) => (
          <p key={item} className="rounded-lg border border-line bg-canvas p-2 text-xs leading-5 text-slate-600">
            <Badge tone={items.length ? tone : "neutral"}>{title}</Badge>
            <span className="ml-2">{item}</span>
          </p>
        ))}
      </div>
    </div>
  );
}
