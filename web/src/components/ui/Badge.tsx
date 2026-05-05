import type { ReactNode } from "react";

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "success" | "warning" | "danger" | "brand";
}) {
  const toneClass = {
    neutral: "border-line bg-white text-steel",
    success: "border-emerald-200 bg-emerald-50 text-emerald-700",
    warning: "border-amber-200 bg-amber-50 text-amber-700",
    danger: "border-red-200 bg-red-50 text-red-700",
    brand: "border-transparent bg-brand-purple text-white",
  }[tone];

  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-1 text-xs font-semibold leading-5 transition-colors ${toneClass}`}>
      {children}
    </span>
  );
}
