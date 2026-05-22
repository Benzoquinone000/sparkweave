import { Link } from "@tanstack/react-router";
import { MoreHorizontal } from "lucide-react";

import { MORE_FEATURE_PATHS } from "@/components/layout/AppShellModel";
import { getNavAccentByPath, isActivePath, NAV_GROUPS, NAV_ITEMS } from "@/lib/navigation";

const MOBILE_MORE_FEATURE_PATHS = MORE_FEATURE_PATHS;
const PRIMARY_MOBILE_GROUPS = NAV_GROUPS.map((group) => ({
  ...group,
  items: group.items.filter((item) => !MOBILE_MORE_FEATURE_PATHS.has(item.to)),
})).filter((group) => group.items.length > 0);
const MORE_MOBILE_GROUPS = NAV_GROUPS.map((group) => ({
  ...group,
  items: group.items.filter((item) => MOBILE_MORE_FEATURE_PATHS.has(item.to)),
})).filter((group) => group.items.length > 0);

export function MobileBottomNav({ currentPath }: { currentPath: string }) {
  return (
    <nav className="dt-bottom-nav fixed inset-x-0 bottom-0 z-30 grid grid-cols-4 border-t border-line bg-white px-2 py-1.5 shadow-panel lg:hidden">
      {NAV_ITEMS.slice(0, 4).map((item) => {
        const active = isActivePath(currentPath, item.to);
        const accent = getNavAccentByPath(item.to);
        return (
          <Link
            key={item.to}
            to={item.to}
            className={`dt-interactive flex min-h-10 flex-col items-center justify-center rounded-lg text-[11px] ${
              active ? `${accent.active} font-medium` : "text-steel"
            }`}
          >
            <item.icon size={16} />
            <span className="mt-0.5">{item.shortLabel}</span>
          </Link>
        );
      })}
    </nav>
  );
}

export function MobileNavigation({
  currentPath,
  onNavigate,
}: {
  currentPath: string;
  onNavigate: () => void;
}) {
  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-2.5">
      <div className="space-y-3">
        {PRIMARY_MOBILE_GROUPS.map((group) => (
          <section key={group.label}>
            <p className="mb-2 px-1 text-xs font-semibold text-steel">{group.label}</p>
            <div className="grid grid-cols-2 gap-1.5">
              {group.items.map((item) => {
                const active = isActivePath(currentPath, item.to);
                const accent = getNavAccentByPath(item.to);
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    onClick={onNavigate}
                    className={`dt-interactive flex min-h-10 items-center gap-2.5 rounded-lg border px-2.5 ${
                      active ? `border-transparent ${accent.active}` : "border-line bg-white text-charcoal"
                    }`}
                  >
                    <item.icon size={16} />
                    <span className="text-xs font-medium">{item.label}</span>
                  </Link>
                );
              })}
            </div>
          </section>
        ))}
        <details
          className="rounded-lg border border-line bg-white px-2.5 py-1.5"
          open={MORE_MOBILE_GROUPS.some((group) => group.items.some((item) => isActivePath(currentPath, item.to)))}
        >
          <summary className="dt-interactive flex min-h-9 cursor-pointer list-none items-center gap-2 text-xs font-semibold text-charcoal [&::-webkit-details-marker]:hidden">
            <MoreHorizontal size={16} />
            更多入口
          </summary>
          <div className="mt-2.5 space-y-3 border-t border-line pt-2.5">
            {MORE_MOBILE_GROUPS.map((group) => (
              <section key={group.label}>
                <p className="mb-2 px-1 text-xs font-semibold text-steel">{group.label}</p>
                <div className="grid grid-cols-2 gap-1.5">
                  {group.items.map((item) => {
                    const active = isActivePath(currentPath, item.to);
                    const accent = getNavAccentByPath(item.to);
                    return (
                      <Link
                        key={item.to}
                        to={item.to}
                        onClick={onNavigate}
                        className={`dt-interactive flex min-h-10 items-center gap-2.5 rounded-lg border px-2.5 ${
                          active ? `border-transparent ${accent.active}` : "border-line bg-surface text-charcoal"
                        }`}
                      >
                        <item.icon size={16} />
                        <span className="text-xs font-medium">{item.label}</span>
                      </Link>
                    );
                  })}
                </div>
              </section>
            ))}
          </div>
        </details>
      </div>
    </div>
  );
}
