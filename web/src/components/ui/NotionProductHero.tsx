import { motion } from "framer-motion";
import type { ReactNode } from "react";

import { PeopleAccent, type PeopleAccentName } from "@/components/ui/PeopleAccent";

type HeroAccent = "purple" | "teal" | "blue" | "orange" | "pink";
type TileTone = "lavender" | "sky" | "yellow" | "mint" | "rose" | "peach";

type HeroTile = {
  label: string;
  helper: string;
  tone: TileTone;
};

const accentClass: Record<HeroAccent, string> = {
  purple: "dt-page-header-accent-purple",
  teal: "dt-page-header-accent-teal",
  blue: "dt-page-header-accent-blue",
  orange: "dt-page-header-accent-orange",
  pink: "dt-page-header-accent-pink",
};

const tileClass: Record<TileTone, string> = {
  lavender: "dt-feature-tile-lavender",
  sky: "dt-feature-tile-sky",
  yellow: "dt-feature-tile-yellow",
  mint: "dt-feature-tile-mint",
  rose: "dt-feature-tile-rose",
  peach: "dt-feature-tile-peach",
};

export function NotionProductHero({
  eyebrow,
  title,
  legacyTitle,
  description,
  accent = "purple",
  previewTitle,
  previewDescription,
  imageSrc,
  imageAlt,
  people,
  tiles,
  actions,
}: {
  eyebrow: string;
  title: string;
  legacyTitle?: string;
  description: string;
  accent?: HeroAccent;
  previewTitle: string;
  previewDescription: string;
  imageSrc?: string;
  imageAlt?: string;
  people?: PeopleAccentName;
  tiles: HeroTile[];
  actions?: ReactNode;
}) {
  return (
    <motion.section
      className={`dt-page-header ${accentClass[accent]}`}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: "easeOut" }}
    >
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_380px] lg:items-center">
        <div>
          <p className="dt-page-eyebrow">{eyebrow}</p>
          <h1 className="mt-1 text-2xl font-semibold leading-tight text-ink" aria-label={legacyTitle}>
            {title}
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">{description}</p>
          {actions ? <div className="mt-4 flex flex-wrap items-center gap-2">{actions}</div> : null}
        </div>
        <div className="dt-workspace-mockup">
          <div className="relative min-h-[150px] overflow-hidden border-b border-line bg-[#fbfbfa]">
            {imageSrc ? <img src={imageSrc} alt={imageAlt ?? ""} className="absolute inset-0 h-full w-full object-cover opacity-95" /> : null}
            <div className="absolute inset-y-0 left-0 w-[56%] bg-[#fbfbfa]/95" />
            <div className="absolute left-4 right-4 top-3 z-10 flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 bg-brand-orange/70" style={{ borderRadius: "50%" }} />
              <span className="h-1.5 w-1.5 bg-brand-yellow/80" style={{ borderRadius: "50%" }} />
              <span className="h-1.5 w-1.5 bg-brand-teal/70" style={{ borderRadius: "50%" }} />
              <span className="ml-auto h-2 w-16 rounded-md bg-line-soft" />
            </div>
            <div className="relative z-10 max-w-[230px] p-4 pt-9">
              <p className="text-sm font-semibold text-ink">{previewTitle}</p>
              <p className="mt-1 text-xs leading-5 text-steel">{previewDescription}</p>
              <div className="mt-3 space-y-1.5">
                <span className="block h-1.5 w-28 rounded-md bg-line-soft" />
                <span className="block h-1.5 w-20 rounded-md bg-line-soft" />
              </div>
            </div>
            {people ? <PeopleAccent name={people} className="absolute bottom-[-22px] right-[-18px] h-44 w-52 opacity-90" /> : null}
          </div>
          <div className="grid gap-2 bg-white p-3 sm:grid-cols-3">
            {tiles.map((tile) => (
              <div key={tile.label} className={`dt-feature-tile ${tileClass[tile.tone]} px-3 py-2`}>
                <p className="text-sm font-semibold text-ink">{tile.label}</p>
                <p className="mt-1 text-xs leading-5 text-steel">{tile.helper}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </motion.section>
  );
}
