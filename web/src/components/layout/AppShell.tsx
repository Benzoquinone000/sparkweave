import { useLocation } from "@tanstack/react-router";
import { AnimatePresence, motion } from "framer-motion";
import { Activity, Menu, X } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { Inspector } from "@/components/layout/Inspector";
import { MobileBottomNav, MobileNavigation } from "@/components/layout/AppShellMobile";
import { MoreFeaturesPanel } from "@/components/layout/AppShellMorePanel";
import { CollapsedSidebar, ExpandedSidebar } from "@/components/layout/AppShellSidebar";
import { BrandInline, RuntimeStatus } from "@/components/layout/AppShellStatus";
import { useSessions, useSystemStatus } from "@/hooks/useApiQueries";
import { getApiBase } from "@/lib/api";
import { NAV_ITEMS } from "@/lib/navigation";

export function AppShell({ children }: { children: ReactNode }) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isDesktop, setIsDesktop] = useState(() =>
    typeof window === "undefined" ? true : window.matchMedia("(min-width: 1024px)").matches,
  );
  const location = useLocation();
  const statusQuery = useSystemStatus();
  const sessionsQuery = useSessions();
  const backendOnline = statusQuery.data?.backend?.status === "online";
  const apiBase = getApiBase();
  const currentItem =
    NAV_ITEMS.find((item) => item.to === location.pathname) ??
    NAV_ITEMS.find((item) => location.pathname.startsWith(`${item.to}/`));
  const checkingRuntime = statusQuery.isLoading || statusQuery.isFetching;

  useEffect(() => {
    const media = window.matchMedia("(min-width: 1024px)");
    const sync = () => setIsDesktop(media.matches);
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);

  return (
    <div className="dt-app-root h-screen overflow-hidden text-ink">
      <div className="flex h-full">
        <nav
          aria-label="主导航"
          className={`dt-sidebar-paper hidden shrink-0 border-r border-line-soft transition-[width] duration-200 lg:flex lg:flex-col ${
            sidebarCollapsed ? "w-[60px]" : "w-[252px]"
          }`}
        >
          {sidebarCollapsed ? (
            <CollapsedSidebar
              currentPath={location.pathname}
              backendOnline={backendOnline}
              onExpand={() => setSidebarCollapsed(false)}
              onOpenInspector={() => setInspectorOpen(true)}
              apiBase={apiBase}
              checking={checkingRuntime}
              onRetry={() => void statusQuery.refetch()}
              onOpenMore={() => setMoreOpen(true)}
              statusTestId={isDesktop ? "runtime-status" : undefined}
            />
          ) : (
            <ExpandedSidebar
              currentPath={location.pathname}
              backendOnline={backendOnline}
              sessions={sessionsQuery.data ?? []}
              sessionsLoading={sessionsQuery.isLoading}
              onCollapse={() => setSidebarCollapsed(true)}
              onOpenInspector={() => setInspectorOpen(true)}
              onOpenMore={() => setMoreOpen(true)}
              statusTestId={isDesktop ? "runtime-status" : undefined}
            />
          )}
        </nav>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-11 shrink-0 items-center justify-between border-b border-line bg-white px-2.5 lg:hidden">
            <div className="flex min-w-0 items-center gap-3">
              <button
                type="button"
                onClick={() => setMobileNavOpen(true)}
                className="dt-interactive inline-flex h-8 w-8 items-center justify-center rounded-lg border border-line text-steel hover:text-ink"
                aria-label="打开导航"
              >
                <Menu size={18} />
              </button>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-ink">{currentItem?.label || "学习"}</p>
                <p className="truncate text-xs text-steel">SparkWeave</p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <RuntimeStatus
                apiBase={apiBase}
                backendOnline={backendOnline}
                checking={checkingRuntime}
                onRetry={() => void statusQuery.refetch()}
                testId={!isDesktop ? "runtime-status" : undefined}
                compact
              />
              <button
                type="button"
                onClick={() => setInspectorOpen(true)}
                className="dt-interactive inline-flex h-8 w-8 items-center justify-center rounded-lg border border-line bg-white text-steel hover:border-[#c8c4be] hover:text-ink"
                aria-label="查看动态"
              >
                <Activity size={16} />
              </button>
            </div>
          </header>

          <main className="dt-page-canvas min-h-0 min-w-0 flex-1 overflow-hidden">{children}</main>
        </div>
      </div>

      <MobileBottomNav currentPath={location.pathname} />

      <AnimatePresence>
        {mobileNavOpen ? (
          <motion.div
            className="fixed inset-0 z-40 bg-slate-950/25 lg:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setMobileNavOpen(false)}
          >
            <motion.aside
              className="dt-sidebar-paper flex h-full w-[276px] max-w-[92vw] flex-col border-r border-line shadow-panel"
              initial={{ x: -320 }}
              animate={{ x: 0 }}
              exit={{ x: -320 }}
              transition={{ duration: 0.22, ease: "easeOut" }}
              onClick={(event) => event.stopPropagation()}
            >
              <div className="flex items-center justify-between border-b border-line p-3">
                <BrandInline backendOnline={backendOnline} statusTestId={!isDesktop ? "runtime-status" : undefined} />
                <button
                  type="button"
                  className="dt-interactive rounded-lg border border-line bg-white p-1.5 text-steel hover:text-ink"
                  onClick={() => setMobileNavOpen(false)}
                  aria-label="关闭导航"
                >
                  <X size={18} />
                </button>
              </div>
              <MobileNavigation currentPath={location.pathname} onNavigate={() => setMobileNavOpen(false)} />
            </motion.aside>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <AnimatePresence>
        {inspectorOpen ? (
          <motion.div
            className="fixed inset-0 z-50 bg-slate-950/20"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setInspectorOpen(false)}
          >
            <Inspector onClose={() => setInspectorOpen(false)} />
          </motion.div>
        ) : null}
      </AnimatePresence>

      <AnimatePresence>
        {moreOpen ? (
          <motion.div
            className="fixed inset-0 z-50 bg-slate-950/20"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setMoreOpen(false)}
          >
            <MoreFeaturesPanel currentPath={location.pathname} onClose={() => setMoreOpen(false)} />
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
