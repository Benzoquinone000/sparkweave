import { Link } from "@tanstack/react-router";
import { motion } from "framer-motion";
import {
  MoreHorizontal,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
} from "lucide-react";
import { useMemo, useState } from "react";

import {
  formatCapabilityLabel,
  formatSessionTime,
  groupSessionsForSidebar,
  PRIMARY_SIDEBAR_ITEMS,
  SIDEBAR_DOCK_ITEMS,
} from "@/components/layout/AppShellModel";
import { BrandInline, RuntimeStatus } from "@/components/layout/AppShellStatus";
import { getNavAccentByPath, isActivePath } from "@/lib/navigation";
import type { SessionSummary } from "@/lib/types";

export function ExpandedSidebar({
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
      <div className="px-3 pb-2.5 pt-4">
        <div className="flex items-start justify-between gap-2.5">
          <BrandInline backendOnline={backendOnline} statusTestId={statusTestId} />
          <button
            type="button"
            onClick={onCollapse}
            className="dt-interactive mt-1 rounded-md p-1 text-steel hover:bg-white hover:text-ink"
            aria-label="折叠侧栏"
          >
            <PanelLeftClose size={16} />
          </button>
        </div>
      </div>

      <div className="px-3">
        <label className="dt-interactive dt-sidebar-search flex h-9 w-full items-center gap-2 px-2.5 text-xs text-steel">
          <Search size={15} />
          <input
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            className="min-w-0 flex-1 bg-transparent text-xs text-ink outline-none placeholder:text-steel"
            placeholder="搜索最近问答"
            aria-label="搜索最近问答"
          />
        </label>
      </div>

      <div className="mt-3 px-3">
        <p className="dt-sidebar-section-title mb-2 px-2">开始</p>
        <SidebarPrimaryLinks currentPath={currentPath} />
        <button
          type="button"
          onClick={onOpenMore}
          className="dt-interactive dt-notion-block mt-1.5 flex min-h-9 w-full items-center gap-2.5 px-2.5 text-left text-xs text-charcoal"
        >
          <MoreHorizontal size={15} />
          <span className="min-w-0 truncate">更多工具</span>
        </button>
      </div>

      <SidebarHistory sessions={sessions} sessionsLoading={sessionsLoading} currentPath={currentPath} searchQuery={searchQuery} />

      <SidebarDock currentPath={currentPath} onOpenInspector={onOpenInspector} />
    </>
  );
}

export function CollapsedSidebar({
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
      <div className="flex h-16 items-center justify-center">
        <button
          type="button"
          onClick={onExpand}
          className="dt-interactive flex h-9 w-9 items-center justify-center rounded-lg bg-brand-navy text-white shadow-sm"
          aria-label="展开侧栏"
        >
          <PanelLeftOpen size={16} />
        </button>
      </div>
      <nav className="flex flex-col items-center gap-1 px-1.5" aria-label="主要入口">
        {PRIMARY_SIDEBAR_ITEMS.map((item) => {
          const active = isActivePath(currentPath, item.to);
          const accent = getNavAccentByPath(item.to);
          return (
            <Link
              key={item.to}
              to={item.to}
              title={item.label}
              className={`dt-interactive relative flex h-9 w-9 items-center justify-center rounded-lg ${
                active ? `${accent.active} shadow-sm` : "text-steel hover:bg-white hover:text-ink"
              }`}
            >
              <span className={`h-2.5 w-2.5 rounded-sm ${accent.dot}`} />
            </Link>
          );
        })}
        <button
          type="button"
          onClick={onOpenMore}
          className="dt-interactive relative flex h-9 w-9 items-center justify-center rounded-lg text-steel hover:bg-white hover:text-ink"
          aria-label="更多工具"
          title="更多工具"
        >
        <MoreHorizontal size={15} />
        </button>
      </nav>
      <div className="mt-auto flex flex-col items-center gap-1 border-t border-line/70 py-2.5">
        {SIDEBAR_DOCK_ITEMS.map((item) => {
          if (!item.to) {
            return (
              <button
                key={item.label}
                type="button"
                onClick={onOpenInspector}
                className="dt-interactive flex h-9 w-9 items-center justify-center rounded-lg text-steel hover:bg-white hover:text-ink"
                data-testid={item.testId}
                aria-label={item.label}
                title={item.label}
              >
                <item.icon size={15} />
              </button>
            );
          }

          const active = isActivePath(currentPath, item.to);
          const accent = getNavAccentByPath(item.to);
          return (
            <Link
              key={item.to}
              to={item.to}
              className={`dt-interactive flex h-9 w-9 items-center justify-center rounded-lg ${
                active ? accent.active : "text-steel hover:bg-white hover:text-ink"
              }`}
              aria-label={item.label}
              title={item.label}
            >
              <item.icon size={15} />
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
    <nav className="space-y-0.5" aria-label="核心学习入口">
      {PRIMARY_SIDEBAR_ITEMS.map((item) => {
        const active = isActivePath(currentPath, item.to);
        const accent = getNavAccentByPath(item.to);
        return (
          <Link
            key={item.to}
            to={item.to}
            className={`dt-interactive relative flex min-h-9 items-center gap-2.5 overflow-hidden rounded-lg px-2.5 text-xs ${
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
            <span className={`relative h-2.5 w-2.5 shrink-0 rounded-sm ${accent.dot}`} />
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
    <div className="mt-4 min-h-0 flex-1 overflow-y-auto px-3 pb-2.5">
      {sessionsLoading ? (
        <div className="space-y-2">
          <p className="dt-sidebar-section-title px-2">最近问答</p>
          {[0, 1, 2].map((item) => (
            <div key={item} className="h-12 rounded-lg bg-white/70" />
          ))}
        </div>
      ) : groups.length ? (
        <div className="space-y-4">
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
                      className={`dt-interactive block rounded-md px-2.5 py-1.5 ${
                        active ? "border border-line bg-white shadow-[0_1px_2px_rgba(15,15,15,0.035)]" : "dt-notion-block"
                      }`}
                      title={session.title || session.last_message || "学习问答"}
                    >
                      <p className="truncate text-xs font-semibold text-charcoal">
                        {session.title || session.last_message || "未命名问答"}
                      </p>
                      <p className="mt-0.5 truncate text-xs text-steel">
                        {session.last_message ? "最近提问" : formatCapabilityLabel(session.preferences?.capability)}
                        {" / "}
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
        <div className="rounded-lg border border-line bg-white/90 px-3 py-3 text-xs text-steel">
          <p className="font-semibold text-charcoal">{normalizedQuery ? "没有匹配的问答" : "还没有学习记录"}</p>
          <p className="mt-1 leading-5">
            {normalizedQuery ? "换个关键词试试。" : "先打开学习，或围绕资料问一个问题。"}
          </p>
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
    <div className="border-t border-line/70 px-2.5 py-2.5">
      <div className="grid grid-cols-2 gap-1 rounded-lg border border-line/70 bg-white/50 p-1">
        {SIDEBAR_DOCK_ITEMS.map((item) => {
          if (!item.to) {
            return (
              <button
                key={item.label}
                type="button"
                onClick={onOpenInspector}
                className="dt-interactive flex min-h-11 flex-col items-center justify-center gap-1 rounded-md text-steel hover:bg-white hover:text-ink"
                data-testid={item.testId}
                aria-label={item.label}
                title={item.label}
              >
                <item.icon size={15} />
                <span className="max-w-full truncate text-[10px] leading-none">{item.label}</span>
              </button>
            );
          }

          const active = isActivePath(currentPath, item.to);
          return (
            <Link
              key={item.to}
              to={item.to}
              className={`dt-interactive flex min-h-11 flex-col items-center justify-center gap-1 rounded-md ${
                active ? "bg-white text-ink shadow-[0_1px_2px_rgba(15,15,15,0.04)]" : "text-steel hover:bg-white hover:text-ink"
              }`}
              aria-label={item.label}
              title={item.label}
            >
              <item.icon size={15} />
              <span className="max-w-full truncate text-[10px] leading-none">{item.label}</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
