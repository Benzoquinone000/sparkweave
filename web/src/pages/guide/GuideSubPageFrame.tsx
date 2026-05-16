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
      className="dt-notion-card p-5"
      initial={{ opacity: 0, x: 18 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -18 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
    >
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3 border-b border-line pb-4">
        <div>
          <p className="dt-page-eyebrow">{eyebrow}</p>
          <h2 className="mt-2 text-xl font-semibold text-ink">{title}</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-steel">{description}</p>
        </div>
        <Button tone="secondary" className="min-h-9 px-3 text-xs" onClick={onBack}>
          <ChevronLeft size={15} />
          返回主流程
        </Button>
      </div>
      <div className="space-y-4">{children}</div>
    </motion.section>
  );
}
