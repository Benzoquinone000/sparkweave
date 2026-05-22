import { Link } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { X } from "lucide-react";

import { MORE_FEATURE_PATHS, moreFeatureHint } from "@/components/layout/AppShellModel";
import { getNavAccentByPath, isActivePath, NAV_GROUPS } from "@/lib/navigation";

export function MoreFeaturesPanel({ currentPath, onClose }: { currentPath: string; onClose: () => void }) {
  const groups = NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => MORE_FEATURE_PATHS.has(item.to)),
  })).filter((group) => group.items.length > 0);

  return (
    <motion.aside
      className="dt-more-panel absolute bottom-3 left-3 top-3 flex w-[340px] max-w-[calc(100vw-1.5rem)] flex-col overflow-hidden rounded-lg border border-line shadow-panel"
      initial={{ opacity: 0, x: -16 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -16 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
      onClick={(event) => event.stopPropagation()}
      aria-label="更多入口"
    >
      <div className="dt-dynamic-toolbar flex items-center justify-between border-b border-line bg-white/90 px-3 py-2.5">
        <div>
          <p className="text-xs font-semibold text-ink">更多入口</p>
          <p className="mt-0.5 text-xs text-steel">先用左侧四个主入口；这里放按需补充的学习入口。</p>
        </div>
        <button
          type="button"
          className="dt-interactive rounded-lg border border-line bg-white p-1.5 text-steel hover:text-ink"
          onClick={onClose}
          aria-label="关闭更多入口"
        >
          <X size={17} />
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        <div className="space-y-4">
          {groups.map((group) => (
            <section key={group.label}>
              <p className="dt-sidebar-section-title mb-2 px-1">{moreGroupLabel(group.label)}</p>
              <div className="grid gap-1">
                {group.items.map((item) => {
                  const active = isActivePath(currentPath, item.to);
                  const accent = getNavAccentByPath(item.to);
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.to}
                      to={item.to}
                      onClick={onClose}
                    className={`dt-interactive dt-dynamic-result flex min-h-10 items-center gap-2.5 rounded-md border px-2.5 ${
                        active ? `border-transparent ${accent.active}` : "border-transparent bg-white/60 text-charcoal hover:border-line hover:bg-white"
                      }`}
                    >
                      <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md ${accent.bg} ${accent.text}`}>
                        <Icon size={15} />
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate text-xs font-semibold">{item.label}</span>
                        <span className="mt-0.5 block truncate text-xs text-steel">{moreFeatureHint(item.to)}</span>
                      </span>
                    </Link>
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      </div>
    </motion.aside>
  );
}

function moreGroupLabel(label: string) {
  return label;
}
