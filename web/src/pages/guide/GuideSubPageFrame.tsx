import { motion } from "framer-motion";
import { ChevronLeft } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/Button";

type GuideSubPageFrameProps = {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
  onBack: () => void;
};

export function GuideSubPageFrame({
  eyebrow,
  title,
  description,
  children,
  onBack,
}: GuideSubPageFrameProps) {
  return (
    <motion.section
      className="flex h-full min-h-0 flex-col rounded-lg border border-line bg-white p-4 shadow-sm sm:p-5"
      initial={{ opacity: 0, x: 18 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -18 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
    >
      <header className="flex shrink-0 flex-wrap items-start justify-between gap-3 border-b border-line pb-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-steel">{eyebrow}</p>
          <h2 className="mt-1.5 text-xl font-semibold leading-tight text-ink">{title}</h2>
          <p className="mt-1 line-clamp-2 max-w-2xl text-sm leading-6 text-slate-500">{description}</p>
        </div>
        <Button tone="secondary" className="min-h-9 px-3 text-xs" onClick={onBack}>
          <ChevronLeft size={15} />
          返回
        </Button>
      </header>
      <div className="min-h-0 flex-1 overflow-hidden py-3">{children}</div>
    </motion.section>
  );
}
