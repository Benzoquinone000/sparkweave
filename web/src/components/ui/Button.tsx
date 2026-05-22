import type { ButtonHTMLAttributes, ReactNode } from "react";

type ButtonTone = "primary" | "secondary" | "danger" | "quiet";

const toneClass: Record<ButtonTone, string> = {
  primary: "dt-energy-button border-ink bg-ink text-white shadow-[rgba(15,23,42,0.12)_0_1px_2px] hover:bg-charcoal",
  secondary: "dt-energy-button border-line bg-white/70 text-ink hover:border-line-strong hover:bg-white",
  danger: "dt-energy-button border-red-200 bg-white text-brand-red hover:border-brand-red hover:bg-red-50",
  quiet: "border-transparent bg-transparent text-steel hover:bg-white/65 hover:text-ink",
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
      className={`dt-interactive inline-flex min-h-9 items-center justify-center gap-1.5 rounded-lg border px-3.5 text-sm font-medium leading-[1.3] disabled:cursor-not-allowed disabled:border-line disabled:bg-line disabled:text-stone disabled:opacity-100 ${toneClass[tone]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
