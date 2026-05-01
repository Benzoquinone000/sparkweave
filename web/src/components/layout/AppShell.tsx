import { Link, useLocation } from "@tanstack/react-router";
import {
  Activity,
  BookOpen,
  Bot,
  Brain,
  DatabaseZap,
  FileQuestion,
  GraduationCap,
  Image,
  Menu,
  MessageSquareText,
  PanelLeftClose,
  PanelLeftOpen,
  PenLine,
  Plus,
  RefreshCw,
  Settings,
  X,
  type LucideIcon,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState, type ReactNode } from "react";

import { Inspector } from "@/components/layout/Inspector";
import { useSystemStatus } from "@/hooks/useApiQueries";
import { getApiBase } from "@/lib/api";

interface NavItem {
  to: string;
  label: string;
  shortLabel: string;
  icon: LucideIcon;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: "学习",
    items: [
      { to: "/chat", label: "对话", shortLabel: "对话", icon: MessageSquareText },
      { to: "/knowledge", label: "资料", shortLabel: "资料", icon: BookOpen },
      { to: "/notebook", label: "笔记", shortLabel: "笔记", icon: Brain },
      { to: "/question", label: "题目", shortLabel: "题目", icon: FileQuestion },
    ],
  },
  {
    label: "能力",
    items: [
      { to: "/guide", label: "导学", shortLabel: "导学", icon: GraduationCap },
      { to: "/co-writer", label: "写作", shortLabel: "写作", icon: PenLine },
      { to: "/vision", label: "图像", shortLabel: "图像", icon: Image },
      { to: "/memory", label: "记忆", shortLabel: "记忆", icon: DatabaseZap },
    ],
  },
  {
    label: "更多",
    items: [
      { to: "/agents", label: "助教", shortLabel: "助教", icon: Bot },
      { to: "/settings", label: "设置", shortLabel: "设置", icon: Settings },
    ],
  },
];

const NAV_ITEMS = NAV_GROUPS.flatMap((group) => group.items);

export function AppShell({ children }: { children: ReactNode }) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isDesktop, setIsDesktop] = useState(() =>
    typeof window === "undefined" ? true : window.matchMedia("(min-width: 1024px)").matches,
  );
  const location = useLocation();
  const statusQuery = useSystemStatus();
  const backendOnline = statusQuery.data?.backend?.status === "online";
  const apiBase = getApiBase();
  const currentItem =
    NAV_ITEMS.find((item) => item.to === location.pathname) ??
    NAV_ITEMS.find((item) => location.pathname.startsWith(`${item.to}/`));

  useEffect(() => {
    const media = window.matchMedia("(min-width: 1024px)");
    const sync = () => setIsDesktop(media.matches);
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);

  return (
    <div className="h-screen overflow-hidden bg-canvas text-ink">
      <div className="flex h-full">
        <nav
          aria-label="主导航"
          className={`hidden shrink-0 border-r border-line bg-[#f3f7f8] transition-[width] duration-200 lg:flex lg:flex-col ${
            sidebarCollapsed ? "w-[58px]" : "w-[220px]"
          }`}
        >
          {sidebarCollapsed ? (
            <CollapsedSidebar
              currentPath={location.pathname}
              backendOnline={backendOnline}
              onExpand={() => setSidebarCollapsed(false)}
              onOpenInspector={() => setInspectorOpen(true)}
              apiBase={apiBase}
              checking={statusQuery.isLoading || statusQuery.isFetching}
              onRetry={() => void statusQuery.refetch()}
              statusTestId={isDesktop ? "runtime-status" : undefined}
            />
          ) : (
            <ExpandedSidebar
              currentPath={location.pathname}
              backendOnline={backendOnline}
              onCollapse={() => setSidebarCollapsed(true)}
              onOpenInspector={() => setInspectorOpen(true)}
              statusTestId={isDesktop ? "runtime-status" : undefined}
            />
          )}
        </nav>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-12 shrink-0 items-center justify-between border-b border-line bg-white px-3 lg:hidden">
            <div className="flex min-w-0 items-center gap-3">
              <button
                type="button"
                onClick={() => setMobileNavOpen(true)}
                className="dt-interactive inline-flex h-9 w-9 items-center justify-center rounded-lg border border-line text-slate-600"
                aria-label="打开导航"
              >
                <Menu size={18} />
              </button>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-ink">{currentItem?.label || "对话"}</p>
                <p className="truncate text-xs text-slate-500">SparkWeave</p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <RuntimeStatus
                apiBase={apiBase}
                backendOnline={backendOnline}
                checking={statusQuery.isLoading || statusQuery.isFetching}
                onRetry={() => void statusQuery.refetch()}
                testId={!isDesktop ? "runtime-status" : undefined}
                compact
              />
              <button
                type="button"
                onClick={() => setInspectorOpen(true)}
                className="dt-interactive inline-flex h-9 w-9 items-center justify-center rounded-lg border border-line bg-white text-slate-600 hover:border-teal-200 hover:text-brand-teal"
                aria-label="最近动态"
              >
                <Activity size={16} />
              </button>
            </div>
          </header>

          <main className="min-h-0 min-w-0 flex-1 overflow-hidden">{children}</main>
        </div>
      </div>

      <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-4 border-t border-line bg-white px-2 py-2 shadow-panel lg:hidden">
        {NAV_ITEMS.slice(0, 4).map((item) => {
          const active = isActivePath(location.pathname, item.to);
          return (
            <Link
              key={item.to}
              to={item.to}
              className={`dt-interactive flex min-h-12 flex-col items-center justify-center rounded-lg text-xs ${
                active ? "bg-teal-50 font-medium text-brand-teal" : "text-slate-500"
              }`}
            >
              <item.icon size={18} />
              <span className="mt-1">{item.shortLabel}</span>
            </Link>
          );
        })}
      </nav>

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
              className="flex h-full w-[280px] flex-col border-r border-line bg-white shadow-panel"
              initial={{ x: -300 }}
              animate={{ x: 0 }}
              exit={{ x: -300 }}
              transition={{ duration: 0.22, ease: "easeOut" }}
              onClick={(event) => event.stopPropagation()}
            >
              <div className="flex items-center justify-between border-b border-line p-4">
        <BrandInline backendOnline={backendOnline} />
                <button
                  type="button"
                  className="dt-interactive rounded-lg border border-line p-2 text-slate-600"
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
    </div>
  );
}

function ExpandedSidebar({
  currentPath,
  backendOnline,
  onCollapse,
  onOpenInspector,
  statusTestId,
}: {
  currentPath: string;
  backendOnline: boolean;
  onCollapse: () => void;
  onOpenInspector: () => void;
  statusTestId?: string;
}) {
  return (
    <>
      <div className="flex h-14 items-center justify-between px-4">
        <BrandInline backendOnline={backendOnline} compact statusTestId={statusTestId} />
        <button
          type="button"
          onClick={onCollapse}
          className="dt-interactive rounded-md p-1.5 text-slate-500 hover:bg-white hover:text-ink"
          aria-label="折叠侧栏"
        >
          <PanelLeftClose size={16} />
        </button>
      </div>

      <div className="px-3 pb-2">
        <Link
          to="/chat"
          className="dt-interactive flex min-h-10 items-center gap-2.5 rounded-lg px-3 text-sm font-medium text-slate-600 hover:bg-white hover:text-ink"
        >
          <Plus size={16} />
          新对话
        </Link>
      </div>

      <Navigation currentPath={currentPath} />

      <div className="mt-auto space-y-1.5 border-t border-line/70 px-3 py-2">
        <button
          type="button"
          onClick={onOpenInspector}
          className="dt-interactive flex min-h-9 w-full items-center gap-2 rounded-lg px-3 text-sm text-slate-600 hover:bg-white hover:text-brand-teal"
          data-testid="open-inspector"
        >
          <Activity size={16} />
          最近动态
        </button>
      </div>
    </>
  );
}

function CollapsedSidebar({
  currentPath,
  backendOnline,
  apiBase,
  checking,
  onExpand,
  onOpenInspector,
  onRetry,
  statusTestId,
}: {
  currentPath: string;
  backendOnline: boolean;
  apiBase: string;
  checking: boolean;
  onExpand: () => void;
  onOpenInspector: () => void;
  onRetry: () => void;
  statusTestId?: string;
}) {
  return (
    <>
      <div className="flex h-14 items-center justify-center">
        <button
          type="button"
          onClick={onExpand}
          className="dt-interactive rounded-md p-1.5 text-slate-500 hover:bg-white hover:text-ink"
          aria-label="展开侧栏"
        >
          <PanelLeftOpen size={16} />
        </button>
      </div>
      <Link
        to="/chat"
        className="dt-interactive mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-lg text-slate-500 hover:bg-white hover:text-ink"
        aria-label="新对话"
      >
        <Plus size={17} />
      </Link>
      <nav className="flex flex-col items-center gap-1 px-2">
        {NAV_ITEMS.map((item) => {
          const active = isActivePath(currentPath, item.to);
          return (
            <Link
              key={item.to}
              to={item.to}
              title={item.label}
              className={`dt-interactive relative flex h-10 w-10 items-center justify-center rounded-lg ${
                active ? "bg-white text-brand-teal shadow-sm" : "text-slate-500 hover:bg-white hover:text-ink"
              }`}
            >
              <item.icon size={17} />
              {active ? <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-sm bg-brand-red" /> : null}
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto flex flex-col items-center gap-1 border-t border-line/70 py-3">
        <button
          type="button"
          onClick={onOpenInspector}
          className="dt-interactive flex h-10 w-10 items-center justify-center rounded-lg text-slate-500 hover:bg-white hover:text-brand-teal"
          data-testid="open-inspector"
          aria-label="最近动态"
        >
          <Activity size={16} />
        </button>
        <RuntimeStatus apiBase={apiBase} backendOnline={backendOnline} checking={checking} onRetry={onRetry} testId={statusTestId} compact />
      </div>
    </>
  );
}

function RuntimeStatus({
  apiBase,
  backendOnline,
  checking,
  compact = false,
  onRetry,
  testId,
}: {
  apiBase: string;
  backendOnline: boolean;
  checking: boolean;
  compact?: boolean;
  onRetry: () => void;
  testId?: string;
}) {
  if (compact) {
    return (
      <button
        type="button"
        onClick={onRetry}
        disabled={checking}
        className="dt-interactive inline-flex h-9 w-9 items-center justify-center rounded-lg border border-line bg-white text-slate-600 hover:border-teal-200 hover:text-brand-teal disabled:cursor-not-allowed disabled:opacity-60"
        data-testid={testId}
        title={apiBase}
        aria-label={backendOnline ? "服务在线" : checking ? "连接中" : "服务离线"}
      >
        <span className={`flex h-2.5 w-2.5 rounded-sm ${backendOnline ? "dt-live-dot bg-emerald-500" : "bg-brand-red"}`} />
      </button>
    );
  }

  return (
    <div className="flex min-h-9 min-w-0 items-center gap-2 rounded-lg px-3 text-slate-600" data-testid={testId} title={apiBase}>
      <span className={`h-2 w-2 shrink-0 rounded-sm ${backendOnline ? "dt-live-dot bg-emerald-500" : "bg-brand-red"}`} />
      <span className="min-w-0 flex-1 truncate text-xs font-medium text-slate-600">
        {backendOnline ? "服务在线" : checking ? "连接中" : "服务离线"}
      </span>
      <button
        type="button"
        onClick={onRetry}
        disabled={checking}
        className="dt-interactive flex h-7 items-center justify-center rounded-md px-1.5 text-slate-500 hover:bg-white hover:text-brand-teal disabled:cursor-not-allowed disabled:opacity-60"
        aria-label="重试连接"
      >
        <RefreshCw size={13} className={checking ? "animate-spin" : ""} />
      </button>
    </div>
  );
}

function BrandInline({
  backendOnline,
  compact = false,
  statusTestId,
}: {
  backendOnline: boolean;
  compact?: boolean;
  statusTestId?: string;
}) {
  return (
    <div className="flex min-w-0 items-center gap-2.5">
      <div className="relative shrink-0">
        <img src="/logo-ver2.png" alt="SparkWeave" className="h-8 w-8 rounded-lg border border-line bg-white object-cover" />
        <span
          data-testid={statusTestId}
          className={`absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-sm border border-white ${
            backendOnline ? "bg-emerald-500" : "bg-brand-red"
          }`}
        />
      </div>
      {!compact ? (
        <div className="min-w-0">
          <p className="truncate font-semibold text-ink">SparkWeave</p>
          <p className="mt-0.5 truncate text-xs text-slate-500">{backendOnline ? "服务在线" : "等待连接"}</p>
        </div>
      ) : (
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-ink">SparkWeave</p>
          <p className="truncate text-xs text-slate-500">学习助手</p>
        </div>
      )}
    </div>
  );
}

function Navigation({ currentPath }: { currentPath: string }) {
  return (
    <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
      <div className="space-y-4">
        {NAV_GROUPS.map((group) => (
          <section key={group.label}>
            <p className="mb-1.5 px-3 text-[11px] font-medium text-slate-400">{group.label}</p>
            <div className="space-y-1">
              {group.items.map((item) => {
                const active = isActivePath(currentPath, item.to);
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    className={`dt-interactive group relative flex min-h-10 items-center gap-2.5 rounded-lg px-3 text-sm ${
                      active ? "bg-white font-medium text-ink shadow-sm" : "text-slate-600 hover:bg-white hover:text-ink"
                    }`}
                    title={item.label}
                  >
                    {active ? (
                      <motion.span
                        layoutId="active-nav-pill"
                        className="absolute inset-y-1 left-1 w-1 rounded-sm bg-brand-red"
                        transition={{ duration: 0.2, ease: "easeOut" }}
                      />
                    ) : null}
                    <item.icon size={17} className={`relative shrink-0 ${active ? "text-brand-teal" : ""}`} />
                    <span className="relative min-w-0 truncate">{item.label}</span>
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

function MobileNavigation({
  currentPath,
  onNavigate,
}: {
  currentPath: string;
  onNavigate: () => void;
}) {
  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-3">
      <div className="space-y-4">
        {NAV_GROUPS.map((group) => (
          <section key={group.label}>
            <p className="mb-2 px-1 text-xs font-semibold text-slate-500">{group.label}</p>
            <div className="grid grid-cols-2 gap-2">
              {group.items.map((item) => {
                const active = isActivePath(currentPath, item.to);
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    onClick={onNavigate}
                    className={`dt-interactive flex min-h-12 items-center gap-3 rounded-lg border px-3 ${
                      active ? "border-teal-200 bg-teal-50 text-brand-teal" : "border-line bg-white text-slate-600"
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

function isActivePath(currentPath: string, target: string) {
  return currentPath === target || currentPath.startsWith(`${target}/`);
}
