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
      className="dt-more-panel absolute bottom-4 left-4 top-4 flex w-[390px] max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-lg border border-line shadow-panel"
      initial={{ opacity: 0, x: -16 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -16 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
      onClick={(event) => event.stopPropagation()}
      aria-label="更多功能"
    >
      <div className="flex items-center justify-between border-b border-line bg-white/84 px-4 py-3">
        <div>
          <p className="text-sm font-semibold text-ink">更多功能</p>
          <p className="mt-0.5 text-xs text-steel">不常用入口放在这里，主侧栏保持清爽。</p>
        </div>
        <button
          type="button"
          className="dt-interactive rounded-lg border border-line bg-white p-2 text-steel hover:text-ink"
          onClick={onClose}
          aria-label="关闭更多功能"
        >
          <X size={17} />
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        <div className="space-y-5">
          {groups.map((group) => (
            <section key={group.label}>
              <p className="dt-sidebar-section-title mb-2 px-1">{group.label}</p>
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
                      className={`dt-interactive flex min-h-12 items-center gap-3 rounded-md border px-3 ${
                        active ? `border-transparent ${accent.active}` : "border-transparent bg-white/62 text-charcoal hover:border-line hover:bg-white"
                      }`}
                    >
                      <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md ${accent.bg} ${accent.text}`}>
                        <Icon size={17} />
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-semibold">{item.label}</span>
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
