import { Link } from "@tanstack/react-router";
import { Plus } from "lucide-react";

import { requestNewChat } from "@/components/layout/AppShellModel";
import { getNavAccentByPath, isActivePath, NAV_GROUPS, NAV_ITEMS } from "@/lib/navigation";

export function MobileBottomNav({ currentPath }: { currentPath: string }) {
  return (
    <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-4 border-t border-line bg-white px-2 py-2 shadow-panel lg:hidden">
      {NAV_ITEMS.slice(0, 4).map((item) => {
        const active = isActivePath(currentPath, item.to);
        const accent = getNavAccentByPath(item.to);
        return (
          <Link
            key={item.to}
            to={item.to}
            className={`dt-interactive flex min-h-12 flex-col items-center justify-center rounded-lg text-xs ${
              active ? `${accent.active} font-medium` : "text-steel"
            }`}
          >
            <item.icon size={18} />
            <span className="mt-1">{item.shortLabel}</span>
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
    <div className="min-h-0 flex-1 overflow-y-auto p-3">
      <div className="mb-3 space-y-3">
        <Link
          to="/chat"
          onClick={() => {
            requestNewChat();
            onNavigate();
          }}
          className="dt-interactive flex min-h-11 items-center gap-3 rounded-lg border border-line bg-white px-4 text-sm font-semibold text-ink"
        >
          <Plus size={18} />
          新建对话
        </Link>
      </div>
      <div className="space-y-4">
        {NAV_GROUPS.map((group) => (
          <section key={group.label}>
            <p className="mb-2 px-1 text-xs font-semibold text-steel">{group.label}</p>
            <div className="grid grid-cols-2 gap-2">
              {group.items.map((item) => {
                const active = isActivePath(currentPath, item.to);
                const accent = getNavAccentByPath(item.to);
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    onClick={onNavigate}
                    className={`dt-interactive flex min-h-12 items-center gap-3 rounded-lg border px-3 ${
                      active ? `border-transparent ${accent.active}` : "border-line bg-white text-charcoal"
                    }`}
                  >
                    <item.icon size={18} />
                    <span className="text-sm font-medium">{item.label}</span>
                  </Link>
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
