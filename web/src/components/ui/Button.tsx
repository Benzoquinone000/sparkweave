import type { ButtonHTMLAttributes, ReactNode } from "react";

type ButtonTone = "primary" | "secondary" | "danger" | "quiet";

const toneClass: Record<ButtonTone, string> = {
  primary: "border-brand-teal bg-brand-teal text-white hover:bg-teal-700",
  secondary: "border-line bg-white text-slate-700 hover:border-teal-200 hover:text-brand-teal",
  danger: "border-red-200 bg-red-50 text-brand-red hover:border-brand-red",
  quiet: "border-transparent bg-transparent text-slate-600 hover:bg-canvas hover:text-ink",
};

export function Button({
  children,
  tone = "secondary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
  tone?: ButtonTone;
}) {
  return (
    <button
      type="button"
      className={`dt-interactive inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border px-3 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-60 ${toneClass[tone]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
