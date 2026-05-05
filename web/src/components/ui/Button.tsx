import type { ButtonHTMLAttributes, ReactNode } from "react";

type ButtonTone = "primary" | "secondary" | "danger" | "quiet";

const toneClass: Record<ButtonTone, string> = {
  primary: "border-brand-purple bg-brand-purple text-white shadow-[rgba(86,69,212,0.16)_0_1px_2px] hover:bg-brand-purple-800",
  secondary: "border-line-strong bg-transparent text-ink hover:border-ink hover:bg-white",
  danger: "border-red-200 bg-red-50 text-brand-red hover:border-brand-red hover:bg-white",
  quiet: "border-transparent bg-transparent text-charcoal hover:bg-surface hover:text-ink",
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
      className={`dt-interactive inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border px-[18px] text-sm font-medium leading-[1.3] disabled:cursor-not-allowed disabled:border-line disabled:bg-line disabled:text-stone disabled:opacity-100 ${toneClass[tone]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
