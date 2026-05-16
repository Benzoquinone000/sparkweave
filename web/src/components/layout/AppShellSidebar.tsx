import { Link } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { MoreHorizontal, PanelLeftClose, PanelLeftOpen, Plus, Search } from "lucide-react";
import { useMemo, useState } from "react";

import {
  formatCapabilityLabel,
  formatSessionTime,
  groupSessionsForSidebar,
  PRIMARY_SIDEBAR_ITEMS,
  requestNewChat,
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
