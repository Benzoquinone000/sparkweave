import { Clock3, Loader2, RefreshCw } from "lucide-react";
import { motion } from "framer-motion";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import type { SparkBotRecentItem } from "@/lib/types";

export type AgentWorkspaceView = "assistants" | "capabilities" | "workspace" | "advanced";

export function AgentWorkspaceTabs({
  value,
  bots,
  capabilities,
  files,
  onChange,
}: {
  value: AgentWorkspaceView;
  bots: number;
  capabilities: number;
  files: number;
  onChange: (value: AgentWorkspaceView) => void;
}) {
  const tabs: Array<{ id: AgentWorkspaceView; title: string; detail: string; count: number; tint: string }> = [
    { id: "assistants", title: "我的助教", detail: "对话、创建与历史", count: bots, tint: "bg-tint-lavender" },
    { id: "capabilities", title: "助教能力", detail: "解题、出题、图解", count: capabilities, tint: "bg-tint-yellow" },
    { id: "workspace", title: "资料与产物", detail: "渠道、资料、笔记", count: files, tint: "bg-tint-sky" },
    { id: "advanced", title: "渠道与高级", detail: "人格、工具、运行", count: 3, tint: "bg-tint-mint" },
  ];
  return (
    <section className="rounded-lg border border-line bg-white p-2">
      <div className="grid gap-2 md:grid-cols-4">
        {tabs.map((tab) => {
          const active = value === tab.id;
          return (
            <motion.button
              key={tab.id}
              type="button"
              className={`dt-interactive rounded-lg border p-3 text-left transition ${
                active ? "border-ink bg-ink text-white" : `border-transparent ${tab.tint} text-ink hover:border-brand-purple-300`
              }`}
              onClick={() => onChange(tab.id)}
              whileHover={{ y: -2 }}
              whileTap={{ scale: 0.99 }}
              data-testid={`agent-workspace-tab-${tab.id}`}
            >
              <span className="flex items-center justify-between gap-3">
                <span className="text-sm font-semibold">{tab.title}</span>
                <span className={`rounded-md px-2 py-0.5 text-xs ${active ? "bg-white/15 text-white" : "bg-white text-slate-600"}`}>{tab.count}</span>
              </span>
              <span className={`mt-2 block text-xs leading-5 ${active ? "text-white/75" : "text-slate-600"}`}>{tab.detail}</span>
            </motion.button>
          );
        })}
      </div>
    </section>
  );
}

export function AgentStatusStrip({
  bots,
  running,
  recent,
  capabilities,
}: {
  bots: number;
  running: number;
  recent: number;
  capabilities: number;
}) {
  const items = [
    { label: "助教", value: String(bots), ok: bots > 0 },
    { label: "运行中", value: String(running), ok: running > 0 },
    { label: "最近", value: String(recent), ok: recent > 0 },
    { label: "能力", value: String(capabilities), ok: capabilities > 0 },
  ];
  return (
    <section className="px-1">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
        {items.map((item) => (
          <div key={item.label} className="flex min-w-0 items-center gap-1.5 text-xs">
            <span className={`h-1.5 w-1.5 shrink-0 ${item.ok ? "bg-emerald-500" : "bg-slate-300"}`} style={{ borderRadius: "50%" }} />
            <span className="shrink-0 text-slate-500">{item.label}</span>
            <span className="truncate font-medium text-ink">{item.value}</span>
          </div>
        ))}
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
    <section className="rounded-lg border border-line bg-white p-3 shadow-[0_1px_2px_rgba(15,15,15,0.025)]" data-testid="sparkbot-recent-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Clock3 size={18} className="text-brand-blue" />
            <h2 className="text-base font-semibold text-ink">最近学习</h2>
          </div>
          <p className="mt-1 text-sm leading-6 text-slate-500">直接回到上次的课程助教上下文，继续未完成的问题和复盘。</p>
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
              className={`dt-interactive min-h-28 rounded-lg border p-3 text-left transition ${
                active ? "border-brand-purple-300 bg-tint-lavender" : "border-line bg-white hover:border-brand-purple-300 hover:bg-canvas"
              }`}
              data-testid={`sparkbot-recent-${item.bot_id}`}
              whileHover={{ y: -2 }}
              whileTap={{ scale: 0.99 }}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="truncate text-sm font-semibold text-ink">{item.name || item.bot_id}</h3>
                  <p className="mt-1 truncate text-xs text-slate-500">{item.bot_id}</p>
                </div>
                <Badge tone={item.running ? "success" : "neutral"}>{item.running ? "运行中" : "停止"}</Badge>
              </div>
              <p className="mt-3 line-clamp-2 text-sm leading-6 text-slate-600">{item.last_message || "还没有留下对话摘要。"}</p>
              <p className="mt-3 text-xs text-slate-500">{displayTime}</p>
            </motion.button>
          );
        })}
      </div>
      {!items.length && !loading ? (
        <p className="mt-4 rounded-lg border border-dashed border-line bg-canvas p-4 text-sm text-slate-500">暂无活跃学习记录。助教产生会话后会自动出现在这里。</p>
      ) : null}
    </section>
  );
}

function formatSparkBotTime(value?: string | number | null) {
  const timestamp = normalizeSparkBotTimestamp(value);
  if (!timestamp) return "最近";
  const date = new Date(timestamp);
  const now = Date.now();
  const diff = now - timestamp;
  if (diff >= 0 && diff < 60_000) return "刚刚";
  if (diff >= 0 && diff < 60 * 60_000) return `${Math.max(1, Math.floor(diff / 60_000))} 分钟前`;
  const today = new Date();
  const sameDay = date.getFullYear() === today.getFullYear() && date.getMonth() === today.getMonth() && date.getDate() === today.getDate();
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
