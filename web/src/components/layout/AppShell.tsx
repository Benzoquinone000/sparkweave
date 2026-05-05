import { Link, useLocation } from "@tanstack/react-router";
import {
  Activity,
  FlaskConical,
  History,
  Menu,
  MoreHorizontal,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  RefreshCw,
  Search,
  Settings,
  X,
  type LucideIcon,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { Inspector } from "@/components/layout/Inspector";
import { useSessions, useSystemStatus } from "@/hooks/useApiQueries";
import { getApiBase } from "@/lib/api";
import { getNavAccentByPath, isActivePath, NAV_GROUPS, NAV_ITEMS } from "@/lib/navigation";
import type { SessionSummary } from "@/lib/types";

type SidebarRoute =
  | "/chat"
  | "/guide"
  | "/memory"
  | "/knowledge"
  | "/notebook"
  | "/question"
  | "/co-writer"
  | "/vision"
  | "/agents"
  | "/playground"
  | "/settings";

const SIDEBAR_DOCK_ITEMS: Array<{
  to?: SidebarRoute;
  label: string;
  icon: LucideIcon;
  testId?: string;
}> = [
  { label: "动态", icon: History, testId: "open-inspector" },
  { to: "/playground", label: "能力实验室", icon: FlaskConical },
  { to: "/settings", label: "设置", icon: Settings },
];

const PRIMARY_SIDEBAR_ITEMS = [
  { to: "/chat", label: "当前对话" },
  { to: "/guide", label: "导学路线" },
  { to: "/memory", label: "学习画像" },
  { to: "/knowledge", label: "知识库" },
  { to: "/agents", label: "助教" },
] satisfies Array<{ to: SidebarRoute; label: string }>;

const MORE_FEATURE_PATHS = new Set(["/notebook", "/question", "/co-writer", "/vision"]);

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
            sidebarCollapsed ? "w-[68px]" : "w-[284px]"
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
          <header className="flex h-12 shrink-0 items-center justify-between border-b border-line bg-white px-3 lg:hidden">
            <div className="flex min-w-0 items-center gap-3">
              <button
                type="button"
                onClick={() => setMobileNavOpen(true)}
                className="dt-interactive inline-flex h-9 w-9 items-center justify-center rounded-lg border border-line text-steel hover:text-ink"
                aria-label="打开导航"
              >
                <Menu size={18} />
              </button>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-ink">{currentItem?.label || "对话"}</p>
                <p className="truncate text-xs text-steel">SparkWeave</p>
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
                className="dt-interactive inline-flex h-9 w-9 items-center justify-center rounded-lg border border-line bg-white text-steel hover:border-[#c8c4be] hover:text-ink"
                aria-label="动态"
              >
                <Activity size={16} />
              </button>
            </div>
          </header>

          <main className="dt-page-canvas min-h-0 min-w-0 flex-1 overflow-hidden">{children}</main>
        </div>
      </div>

      <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-4 border-t border-line bg-white px-2 py-2 shadow-panel lg:hidden">
        {NAV_ITEMS.slice(0, 4).map((item) => {
          const active = isActivePath(location.pathname, item.to);
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
              className="dt-sidebar-paper flex h-full w-[300px] max-w-[92vw] flex-col border-r border-line shadow-panel"
              initial={{ x: -320 }}
              animate={{ x: 0 }}
              exit={{ x: -320 }}
              transition={{ duration: 0.22, ease: "easeOut" }}
              onClick={(event) => event.stopPropagation()}
            >
              <div className="flex items-center justify-between border-b border-line p-4">
                <BrandInline backendOnline={backendOnline} statusTestId={!isDesktop ? "runtime-status" : undefined} />
                <button
                  type="button"
                  className="dt-interactive rounded-lg border border-line bg-white p-2 text-steel hover:text-ink"
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

function ExpandedSidebar({
  currentPath,
  backendOnline,
  sessions,
  sessionsLoading,
  onCollapse,
  onOpenInspector,
  onOpenMore,
  statusTestId,
}: {
  currentPath: string;
  backendOnline: boolean;
  sessions: SessionSummary[];
  sessionsLoading: boolean;
  onCollapse: () => void;
  onOpenInspector: () => void;
  onOpenMore: () => void;
  statusTestId?: string;
}) {
  const [searchQuery, setSearchQuery] = useState("");

  return (
    <>
      <div className="px-4 pb-3 pt-5">
        <div className="flex items-start justify-between gap-3">
          <BrandInline backendOnline={backendOnline} statusTestId={statusTestId} />
          <button
            type="button"
            onClick={onCollapse}
            className="dt-interactive mt-1 rounded-md p-1.5 text-steel hover:bg-white hover:text-ink"
            aria-label="折叠侧栏"
          >
            <PanelLeftClose size={16} />
          </button>
        </div>
      </div>

      <div className="space-y-3 px-4">
        <Link
          to="/chat"
          onClick={requestNewChat}
          className="dt-interactive dt-sidebar-action flex min-h-11 items-center gap-3 px-4 text-sm font-semibold text-ink"
        >
          <Plus size={18} />
          新建对话
        </Link>

        <label className="dt-interactive dt-sidebar-search flex h-10 w-full items-center gap-2 px-3 text-sm text-steel">
          <Search size={16} />
          <input
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            className="min-w-0 flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-steel"
            placeholder="搜索对话"
            aria-label="搜索对话"
          />
          <span className="rounded-md bg-surface px-1.5 py-0.5 text-xs text-stone">⌘ K</span>
        </label>
      </div>

      <div className="mt-4 px-4">
        <p className="dt-sidebar-section-title mb-2 px-2">学习空间</p>
        <SidebarPrimaryLinks currentPath={currentPath} />
        <button
          type="button"
          onClick={onOpenMore}
          className="dt-interactive dt-notion-block mt-2 flex min-h-10 w-full items-center gap-3 px-3 text-left text-sm text-charcoal"
        >
          <MoreHorizontal size={16} />
          <span className="min-w-0 truncate">更多功能</span>
        </button>
      </div>

      <SidebarHistory sessions={sessions} sessionsLoading={sessionsLoading} currentPath={currentPath} searchQuery={searchQuery} />

      <SidebarDock currentPath={currentPath} onOpenInspector={onOpenInspector} />
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
  onOpenMore,
  onRetry,
  statusTestId,
}: {
  currentPath: string;
  backendOnline: boolean;
  apiBase: string;
  checking: boolean;
  onExpand: () => void;
  onOpenInspector: () => void;
  onOpenMore: () => void;
  onRetry: () => void;
  statusTestId?: string;
}) {
  return (
    <>
      <div className="flex h-20 items-center justify-center">
        <button
          type="button"
          onClick={onExpand}
          className="dt-interactive flex h-10 w-10 items-center justify-center rounded-lg bg-brand-navy text-white shadow-sm"
          aria-label="展开侧栏"
        >
          <PanelLeftOpen size={18} />
        </button>
      </div>
      <Link
        to="/chat"
        onClick={requestNewChat}
        className="dt-interactive mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-lg border border-line bg-white text-charcoal hover:border-brand-purple-300 hover:text-brand-purple"
        aria-label="新建对话"
      >
        <Plus size={17} />
      </Link>
      <nav className="flex flex-col items-center gap-1 px-2" aria-label="主要入口">
        {PRIMARY_SIDEBAR_ITEMS.map((item) => {
          const active = isActivePath(currentPath, item.to);
          const accent = getNavAccentByPath(item.to);
          return (
            <Link
              key={item.to}
              to={item.to}
              title={item.label}
              className={`dt-interactive relative flex h-10 w-10 items-center justify-center rounded-lg ${
                active ? `${accent.active} shadow-sm` : "text-steel hover:bg-white hover:text-ink"
              }`}
            >
              <span className={`h-2.5 w-2.5 ${accent.dot}`} style={{ borderRadius: "50%" }} />
            </Link>
          );
        })}
        <button
          type="button"
          onClick={onOpenMore}
          className="dt-interactive relative flex h-10 w-10 items-center justify-center rounded-lg text-steel hover:bg-white hover:text-ink"
          aria-label="更多功能"
          title="更多功能"
        >
          <MoreHorizontal size={16} />
        </button>
      </nav>
      <div className="mt-auto flex flex-col items-center gap-1 border-t border-line/70 py-3">
        {SIDEBAR_DOCK_ITEMS.map((item) => {
          if (!item.to) {
            return (
              <button
                key={item.label}
                type="button"
                onClick={onOpenInspector}
                className="dt-interactive flex h-10 w-10 items-center justify-center rounded-lg text-steel hover:bg-white hover:text-brand-purple"
                data-testid={item.testId}
                aria-label={item.label}
                title={item.label}
              >
                <item.icon size={16} />
              </button>
            );
          }

          const active = isActivePath(currentPath, item.to);
          const accent = getNavAccentByPath(item.to);
          return (
            <Link
              key={item.to}
              to={item.to}
              className={`dt-interactive flex h-10 w-10 items-center justify-center rounded-lg ${
                active ? accent.active : "text-steel hover:bg-white hover:text-ink"
              }`}
              aria-label={item.label}
              title={item.label}
            >
              <item.icon size={16} />
            </Link>
          );
        })}
        <RuntimeStatus apiBase={apiBase} backendOnline={backendOnline} checking={checking} onRetry={onRetry} testId={statusTestId} compact />
      </div>
    </>
  );
}

function SidebarPrimaryLinks({ currentPath }: { currentPath: string }) {
  return (
    <nav className="space-y-1" aria-label="核心学习入口">
      {PRIMARY_SIDEBAR_ITEMS.map((item) => {
        const active = isActivePath(currentPath, item.to);
        const accent = getNavAccentByPath(item.to);
        return (
          <Link
            key={item.to}
            to={item.to}
            className={`dt-interactive relative flex min-h-10 items-center gap-3 overflow-hidden rounded-lg px-3 text-sm ${
              active ? `font-semibold ${accent.text}` : "text-charcoal hover:bg-white"
            }`}
          >
            {active ? (
              <motion.span
                layoutId="sidebar-primary-active"
                className={`absolute inset-0 rounded-lg ${accent.bg}`}
                transition={{ duration: 0.18, ease: "easeOut" }}
              />
            ) : null}
            <span className={`relative h-2.5 w-2.5 shrink-0 ${accent.dot}`} style={{ borderRadius: "50%" }} />
            <span className="relative min-w-0 truncate">{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

function SidebarHistory({
  sessions,
  sessionsLoading,
  currentPath,
  searchQuery,
}: {
  sessions: SessionSummary[];
  sessionsLoading: boolean;
  currentPath: string;
  searchQuery: string;
}) {
  const normalizedQuery = searchQuery.trim().toLowerCase();
  const filteredSessions = useMemo(() => {
    if (!normalizedQuery) return sessions;
    return sessions.filter((session) =>
      [session.title, session.last_message, session.preferences?.capability]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(normalizedQuery)),
    );
  }, [normalizedQuery, sessions]);
  const groups = useMemo(() => groupSessionsForSidebar(filteredSessions), [filteredSessions]);

  return (
    <div className="mt-5 min-h-0 flex-1 overflow-y-auto px-4 pb-3">
      {sessionsLoading ? (
        <div className="space-y-2">
          <p className="dt-sidebar-section-title px-2">今天</p>
          {[0, 1, 2].map((item) => (
            <div key={item} className="h-14 rounded-lg bg-white/70" />
          ))}
        </div>
      ) : groups.length ? (
        <div className="space-y-5">
          {groups.map((group) => (
            <section key={group.label}>
              <p className="dt-sidebar-section-title mb-2 px-2">{group.label}</p>
              <div className="space-y-1">
                {group.items.map((session) => {
                  const active = isActivePath(currentPath, `/chat/${session.session_id}`);
                  return (
                    <Link
                      key={session.session_id}
                      to="/chat/$sessionId"
                      params={{ sessionId: session.session_id }}
                      className={`dt-interactive block rounded-md px-2.5 py-2 ${
                        active ? "border border-line bg-white shadow-[0_1px_2px_rgba(15,15,15,0.035)]" : "dt-notion-block"
                      }`}
                      title={session.title || session.last_message || "学习会话"}
                    >
                      <p className="truncate text-sm font-semibold text-charcoal">
                        {session.title || session.last_message || "未命名对话"}
                      </p>
                      <p className="mt-0.5 truncate text-xs text-steel">
                        {session.last_message ? "聊了" : formatCapabilityLabel(session.preferences?.capability)}
                        {" · "}
                        {formatSessionTime(session.updated_at || session.created_at)}
                      </p>
                    </Link>
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      ) : (
        <div className="rounded-lg border border-line bg-white/92 px-3 py-4 text-sm text-steel">
          <p className="font-semibold text-charcoal">{normalizedQuery ? "没有匹配的对话" : "还没有历史会话"}</p>
          <p className="mt-1 leading-5">{normalizedQuery ? "换个关键词试试。" : "点“新建对话”，把今天的学习问题交给 SparkWeave。"}</p>
        </div>
      )}
    </div>
  );
}

function SidebarDock({
  currentPath,
  onOpenInspector,
}: {
  currentPath: string;
  onOpenInspector: () => void;
}) {
  return (
    <div className="border-t border-line/70 px-3 py-3">
      <div className="grid grid-cols-3 gap-1 rounded-lg border border-line/70 bg-white/55 p-1">
        {SIDEBAR_DOCK_ITEMS.map((item) => {
          if (!item.to) {
            return (
              <button
                key={item.label}
                type="button"
                onClick={onOpenInspector}
                className="dt-interactive flex min-h-[52px] flex-col items-center justify-center gap-1 rounded-md text-steel hover:bg-white hover:text-brand-purple"
                data-testid={item.testId}
                aria-label={item.label}
                title={item.label}
              >
                <item.icon size={16} />
                <span className="max-w-full truncate text-[11px] leading-none">{item.label}</span>
              </button>
            );
          }

          const active = isActivePath(currentPath, item.to);
          return (
            <Link
              key={item.to}
              to={item.to}
              className={`dt-interactive flex min-h-[52px] flex-col items-center justify-center gap-1 rounded-md ${
                active ? "bg-white text-ink shadow-[0_1px_2px_rgba(15,15,15,0.04)]" : "text-steel hover:bg-white hover:text-ink"
              }`}
              aria-label={item.label}
              title={item.label}
            >
              <item.icon size={16} />
              <span className="max-w-full truncate text-[11px] leading-none">{item.label}</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

function MoreFeaturesPanel({ currentPath, onClose }: { currentPath: string; onClose: () => void }) {
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
        className="dt-interactive inline-flex h-9 w-9 items-center justify-center rounded-lg border border-line bg-white text-steel hover:border-[#c8c4be] hover:text-ink disabled:cursor-not-allowed disabled:opacity-60"
        data-testid={testId}
        title={apiBase}
        aria-label={backendOnline ? "服务在线" : checking ? "连接中" : "服务离线"}
      >
        <span className={`flex h-2.5 w-2.5 ${backendOnline ? "dt-live-dot bg-emerald-500" : "bg-brand-red"}`} style={{ borderRadius: "50%" }} />
      </button>
    );
  }

  return (
    <div className="flex min-h-9 min-w-0 items-center gap-2 rounded-lg px-3 text-steel" data-testid={testId} title={apiBase}>
      <span className={`h-2 w-2 shrink-0 ${backendOnline ? "dt-live-dot bg-emerald-500" : "bg-brand-red"}`} style={{ borderRadius: "50%" }} />
      <span className="min-w-0 flex-1 truncate text-xs font-medium text-steel">
        {backendOnline ? "服务在线" : checking ? "连接中" : "服务离线"}
      </span>
      <button
        type="button"
        onClick={onRetry}
        disabled={checking}
        className="dt-interactive flex h-7 items-center justify-center rounded-md px-1.5 text-steel hover:bg-white hover:text-brand-purple disabled:cursor-not-allowed disabled:opacity-60"
        aria-label="重试连接"
      >
        <RefreshCw size={13} className={checking ? "animate-spin" : ""} />
      </button>
    </div>
  );
}

function BrandInline({
  backendOnline,
  statusTestId,
}: {
  backendOnline: boolean;
  statusTestId?: string;
}) {
  return (
    <div className="flex min-w-0 items-center gap-3">
      <div className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-navy text-white shadow-sm">
        <Plus size={23} strokeWidth={2.2} />
        <span
          data-testid={statusTestId}
          className={`absolute -right-0.5 -top-0.5 h-2.5 w-2.5 border border-white ${
            backendOnline ? "bg-emerald-500" : "bg-brand-red"
          }`}
          style={{ borderRadius: "50%" }}
        />
      </div>
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold text-ink">SparkWeave</p>
        <p className="truncate text-xs text-steel">学习空间</p>
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

function groupSessionsForSidebar(sessions: SessionSummary[]) {
  const now = Date.now();
  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const sevenDaysAgo = now - 7 * 24 * 60 * 60 * 1000;
  const sorted = [...sessions]
    .sort((left, right) => normalizeTimestamp(right.updated_at || right.created_at) - normalizeTimestamp(left.updated_at || left.created_at))
    .slice(0, 12);
  const today: SessionSummary[] = [];
  const recent: SessionSummary[] = [];
  const older: SessionSummary[] = [];

  for (const session of sorted) {
    const timestamp = normalizeTimestamp(session.updated_at || session.created_at);
    if (timestamp >= startOfToday.getTime()) today.push(session);
    else if (timestamp >= sevenDaysAgo) recent.push(session);
    else older.push(session);
  }

  const groups: Array<{ label: string; items: SessionSummary[] }> = [];
  if (today.length) groups.push({ label: "今天", items: today.slice(0, 5) });
  if (recent.length) groups.push({ label: "最近 7 天", items: recent.slice(0, 5) });
  if (older.length) groups.push({ label: "更早", items: older.slice(0, 5) });
  return groups;
}

function normalizeTimestamp(value: number | undefined) {
  if (!value) return 0;
  return value < 1_000_000_000_000 ? value * 1000 : value;
}

function formatSessionTime(value: number | undefined) {
  const timestamp = normalizeTimestamp(value);
  if (!timestamp) return "刚刚";
  const date = new Date(timestamp);
  const now = new Date();
  const sameDay =
    date.getFullYear() === now.getFullYear() && date.getMonth() === now.getMonth() && date.getDate() === now.getDate();
  if (sameDay) {
    return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false });
  }
  return date.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
}

function formatCapabilityLabel(capability?: string) {
  if (capability === "guided_learning" || capability === "guide_v2") return "导学";
  if (capability === "deep_research") return "研究";
  if (capability === "deep_solve") return "答疑";
  if (capability === "visualize") return "图解";
  if (capability === "math_animator") return "视频";
  if (capability === "co_writer") return "写作";
  return "对话";
}

function moreFeatureHint(path: string) {
  if (path === "/question") return "生成练习和仿题";
  if (path === "/co-writer") return "润色、扩写和改写";
  if (path === "/vision") return "上传图片并解题";
  if (path === "/agents") return "管理 SparkBot";
  if (path === "/playground") return "测试各类能力";
  return "打开功能页";
}

function requestNewChat() {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem("sparkweave:new-chat-request", String(Date.now()));
  window.dispatchEvent(new CustomEvent("sparkweave:new-chat"));
}
