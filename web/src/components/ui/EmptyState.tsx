import type { ReactNode } from "react";

type EmptyStateTone = "neutral" | "guide" | "knowledge" | "practice" | "record" | "settings";
type EmptyStateAlign = "center" | "left";

const toneClass: Record<
  EmptyStateTone,
  {
    panel: string;
    icon: string;
    eyebrow: string;
    marker: string;
  }
> = {
  neutral: {
    panel: "border-line bg-white/90",
    icon: "border-line bg-surface text-charcoal",
    eyebrow: "text-steel",
    marker: "bg-stone",
  },
  guide: {
    panel: "border-accent-purple-line bg-accent-purple-active/80",
    icon: "border-accent-purple-line bg-white text-accent-purple-ink",
    eyebrow: "text-accent-purple-ink",
    marker: "bg-accent-purple-marker",
  },
  knowledge: {
    panel: "border-accent-blue-line bg-accent-blue-active/85",
    icon: "border-accent-blue-line bg-white text-accent-blue-ink",
    eyebrow: "text-accent-blue-ink",
    marker: "bg-accent-blue-marker",
  },
  practice: {
    panel: "border-accent-pink-line bg-accent-pink-active/85",
    icon: "border-accent-pink-line bg-white text-accent-pink-ink",
    eyebrow: "text-accent-pink-ink",
    marker: "bg-accent-pink-marker",
  },
  record: {
    panel: "border-accent-orange-line bg-accent-orange-active/85",
    icon: "border-accent-orange-line bg-white text-accent-orange-ink",
    eyebrow: "text-accent-orange-ink",
    marker: "bg-accent-orange-marker",
  },
  settings: {
    panel: "border-accent-teal-line bg-accent-teal-active/85",
    icon: "border-accent-teal-line bg-white text-accent-teal-ink",
    eyebrow: "text-accent-teal-ink",
    marker: "bg-accent-teal-marker",
  },
};

const alignClass: Record<
  EmptyStateAlign,
  {
    panel: string;
    icon: string;
    description: string;
    actions: string;
  }
> = {
  center: {
    panel: "items-center text-center",
    icon: "mx-auto",
    description: "mx-auto",
    actions: "justify-center",
  },
  left: {
    panel: "items-start text-left",
    icon: "",
    description: "",
    actions: "justify-start",
  },
};

export function EmptyState({
  icon,
  eyebrow,
  title,
  description,
  action,
  secondaryAction,
  tone = "neutral",
  align = "center",
}: {
  icon?: ReactNode;
  eyebrow?: string;
  title: string;
  description: string;
  action?: ReactNode;
  secondaryAction?: ReactNode;
  tone?: EmptyStateTone;
  align?: EmptyStateAlign;
}) {
  const toneStyles = toneClass[tone];
  const alignStyles = alignClass[align];

  return (
    <div className={`dt-soft-enter flex flex-col rounded-lg border border-dashed p-4 ${toneStyles.panel} ${alignStyles.panel}`}>
      <span className={`mb-3 block h-1 w-10 rounded-sm ${toneStyles.marker}`} aria-hidden="true" />
      {icon ? (
        <div className={`flex h-9 w-9 items-center justify-center rounded-lg border ${toneStyles.icon} ${alignStyles.icon}`}>{icon}</div>
      ) : null}
      {eyebrow ? <p className={`mt-2 text-[11px] font-semibold uppercase ${toneStyles.eyebrow}`}>{eyebrow}</p> : null}
      <p className={`${icon || eyebrow ? "mt-1.5" : ""} text-sm font-semibold leading-5 text-ink`}>{title}</p>
      <p className={`${alignStyles.description} mt-1 max-w-lg text-xs leading-5 text-steel`}>{description}</p>
      {action || secondaryAction ? (
        <div className={`mt-3 flex flex-wrap gap-2 ${alignStyles.actions}`}>
          {action}
          {secondaryAction}
        </div>
      ) : null}
    </div>
  );
}
