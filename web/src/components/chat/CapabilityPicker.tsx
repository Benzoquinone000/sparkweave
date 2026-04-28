import { AnimatePresence, motion } from "framer-motion";

import { CAPABILITIES } from "@/lib/capabilities";
import type { CapabilityId } from "@/lib/types";

export function CapabilityPicker({
  value,
  onChange,
}: {
  value: CapabilityId;
  onChange: (value: CapabilityId) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-1.5">
      {CAPABILITIES.map((capability) => {
        const active = capability.id === value;
        return (
          <button
            key={capability.id}
            type="button"
            onClick={() => onChange(capability.id)}
            className={`dt-interactive relative flex min-h-10 items-center gap-2 rounded-lg border bg-white px-2.5 py-2 text-left ${
              active
                ? "border-teal-300 bg-teal-50/70"
                : "border-line hover:border-teal-200 hover:bg-canvas"
            }`}
          >
            <div className={`shrink-0 rounded-md p-1.5 ${active ? "bg-brand-teal text-white" : "bg-canvas text-slate-500"}`}>
              <capability.icon size={15} />
            </div>
            <p className="min-w-0 flex-1 truncate text-sm font-medium text-ink">{capability.label}</p>
            <AnimatePresence>
              {active ? (
                <motion.span
                  className="absolute right-2 top-2 h-2 w-2 rounded-sm bg-brand-red"
                  layoutId="capability-active-rail"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                />
              ) : null}
            </AnimatePresence>
          </button>
        );
      })}
    </div>
  );
}
