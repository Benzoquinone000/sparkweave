import type { ReactNode } from "react";

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "success" | "warning" | "danger" | "brand";
}) {
  const toneClass = {
    neutral: "border-line bg-white text-slate-600",
    success: "border-emerald-200 bg-emerald-50 text-emerald-700",
    warning: "border-amber-200 bg-amber-50 text-amber-700",
    danger: "border-red-200 bg-red-50 text-red-700",
    brand: "border-teal-200 bg-teal-50 text-brand-teal",
  }[tone];

  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-1 text-xs font-medium transition-colors ${toneClass}`}>
      {children}
    </span>
  );
}
