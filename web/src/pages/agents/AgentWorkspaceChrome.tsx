import {
  Bot,
  CalendarClock,
  Clock3,
  Loader2,
  PlugZap,
  RefreshCw,
  Settings2,
  type LucideIcon,
} from "lucide-react";
import { motion } from "framer-motion";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import type { SparkBotRecentItem } from "@/lib/types";

export type AgentWorkspaceView = "schedule" | "assistants" | "workspace" | "advanced";

export function AgentWorkspaceTabs({
  value,
  bots,
  jobs,
  files,
  onChange,
}: {
  value: AgentWorkspaceView;
  bots: number;
  jobs: number;
  files: number;
  onChange: (value: AgentWorkspaceView) => void;
}) {
  const tabs: Array<{
    id: AgentWorkspaceView;
    title: string;
    detail: string;
    count: number;
    icon: LucideIcon;
  }> = [
    { id: "schedule", title: "定时提醒", detail: "主动跟进", count: jobs, icon: CalendarClock },
    { id: "assistants", title: "我的助教", detail: "选择与启用", count: bots, icon: Bot },
    { id: "workspace", title: "资料与群聊", detail: "资料和消息入口", count: files, icon: PlugZap },
    { id: "advanced", title: "少用设置", detail: "必要时再改", count: 3, icon: Settings2 },
  ];

  return (
    <section className="dt-dynamic-card rounded-lg border border-line bg-white p-1.5 shadow-[0_1px_2px_rgba(15,15,15,0.025)]">
      <div className="grid gap-1.5 md:grid-cols-4">
        {tabs.map((tab) => {
          const active = value === tab.id;
          const Icon = tab.icon;
          return (
            <motion.button
              key={tab.id}
              type="button"
              className={`dt-interactive dt-dynamic-result rounded-md border px-3 py-2 text-left transition ${
                active
                  ? "border-brand-purple-300 bg-tint-lavender text-brand-purple shadow-[0_1px_2px_rgba(15,23,42,0.04)]"
                  : "border-transparent bg-white text-ink hover:border-line hover:bg-canvas"
              }`}
              onClick={() => onChange(tab.id)}
              whileHover={{ y: -0.5 }}
              whileTap={{ scale: 0.99 }}
              data-testid={`agent-workspace-tab-${tab.id}`}
            >
              <span className="flex items-center justify-between gap-3">
                <span className="flex min-w-0 items-center gap-2">
                  <Icon size={16} className="text-brand-purple" />
                  <span className="truncate text-sm font-semibold">{tab.title}</span>
                </span>
                <span className={`rounded-md px-2 py-0.5 text-xs ${active ? "bg-white/70 text-brand-purple" : "bg-canvas text-slate-600"}`}>
                  {tab.count}
                </span>
              </span>
              <span className="mt-2 block text-xs leading-5 text-slate-600">
                {tab.detail}
              </span>
            </motion.button>
          );
        })}
      </div>
    </section>
  );
}

export function SparkBotRecentPanel({
  items,
  activeBotId,
  loading,
  onRefresh,
  onSelect,
}: {
  items: SparkBotRecentItem[];
  activeBotId: string | null;
  loading: boolean;
  onRefresh: () => void;
  onSelect: (botId: string) => void;
}) {
  return (
    <section className="dt-dynamic-card rounded-lg border border-line bg-white p-3 shadow-[0_1px_2px_rgba(15,15,15,0.025)]" data-testid="sparkbot-recent-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Clock3 size={18} className="text-brand-blue" />
          <h2 className="text-base font-semibold text-ink">最近运行</h2>
        </div>
        <Button tone="secondary" onClick={onRefresh} disabled={loading} data-testid="sparkbot-recent-refresh">
          {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
          刷新
        </Button>
      </div>

      <div className="mt-4 grid gap-2 md:grid-cols-3">
        {items.map((item) => {
          const active = activeBotId === item.bot_id;
          const displayTime = formatSparkBotTime(item.updated_at);
          return (
            <motion.button
              key={item.bot_id}
              type="button"
              onClick={() => onSelect(item.bot_id)}
              aria-pressed={active}
              className={`dt-interactive dt-dynamic-result min-h-28 rounded-lg border p-3 text-left transition ${
                active
                  ? "border-brand-purple-300 bg-tint-lavender"
                  : "border-line bg-white hover:border-brand-purple-300 hover:bg-canvas"
              }`}
              data-testid={`sparkbot-recent-${item.bot_id}`}
              whileHover={{ y: -0.5 }}
              whileTap={{ scale: 0.99 }}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="truncate text-sm font-semibold text-ink">{item.name || item.bot_id}</h3>
                  <p className="mt-1 truncate text-xs text-slate-500">{item.bot_id}</p>
                </div>
                <Badge tone={item.running ? "success" : "neutral"}>{item.running ? "运行中" : "停止"}</Badge>
              </div>
              <p className="mt-3 line-clamp-2 text-sm leading-6 text-slate-600">{item.last_message || "暂无运行记录"}</p>
              <p className="mt-3 text-xs text-slate-500">{displayTime}</p>
            </motion.button>
          );
        })}
      </div>

      {!items.length && !loading ? (
        <p className="dt-dynamic-empty mt-4 rounded-lg border border-dashed border-line bg-canvas p-4 text-sm text-slate-500">
          暂无最近运行记录。启动助教或执行提醒后会出现在这里。
        </p>
      ) : null}
    </section>
  );
}

function formatSparkBotTime(value?: string | number | null) {
  const timestamp = normalizeSparkBotTimestamp(value);
  if (!timestamp) return "暂无";
  const date = new Date(timestamp);
  const now = Date.now();
  const diff = now - timestamp;
  if (diff >= 0 && diff < 60_000) return "刚刚";
  if (diff >= 0 && diff < 60 * 60_000) return `${Math.max(1, Math.floor(diff / 60_000))} 分钟前`;
  const today = new Date();
  const sameDay =
    date.getFullYear() === today.getFullYear() &&
    date.getMonth() === today.getMonth() &&
    date.getDate() === today.getDate();
  if (sameDay) return `今天 ${date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false })}`;
  return date.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
}

function normalizeSparkBotTimestamp(value?: string | number | null) {
  if (value === null || value === undefined || value === "") return 0;
  const numericValue = typeof value === "number" ? value : Number(value);
  const timestamp = Number.isFinite(numericValue)
    ? numericValue < 1_000_000_000_000
      ? numericValue * 1000
      : numericValue
    : new Date(value).getTime();
  if (!Number.isFinite(timestamp) || timestamp <= 0) return 0;
  const date = new Date(timestamp);
  if (date.getFullYear() < 2023) return 0;
  return timestamp;
}
