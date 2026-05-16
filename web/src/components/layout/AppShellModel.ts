import { FlaskConical, History, Settings, type LucideIcon } from "lucide-react";

import type { SessionSummary } from "@/lib/types";

export type SidebarRoute =
  | "/chat"
  | "/demo"
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

export const SIDEBAR_DOCK_ITEMS: Array<{
  to?: SidebarRoute;
  label: string;
  icon: LucideIcon;
  testId?: string;
}> = [
  { label: "动态", icon: History, testId: "open-inspector" },
  { to: "/playground", label: "能力实验室", icon: FlaskConical },
  { to: "/settings", label: "设置", icon: Settings },
];

export const PRIMARY_SIDEBAR_ITEMS = [
  { to: "/chat", label: "当前对话" },
  { to: "/demo", label: "比赛演示" },
  { to: "/guide", label: "导学路线" },
  { to: "/memory", label: "学习画像" },
  { to: "/knowledge", label: "知识库" },
  { to: "/agents", label: "助教" },
] satisfies Array<{ to: SidebarRoute; label: string }>;

export const MORE_FEATURE_PATHS = new Set(["/notebook", "/question", "/co-writer", "/vision"]);

export function groupSessionsForSidebar(sessions: SessionSummary[]) {
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

export function formatSessionTime(value: number | undefined) {
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

export function formatCapabilityLabel(capability?: string) {
  if (capability === "guided_learning" || capability === "guide_v2") return "导学";
  if (capability === "deep_research") return "研究";
  if (capability === "deep_solve") return "答疑";
  if (capability === "visualize") return "图解";
  if (capability === "math_animator") return "视频";
  if (capability === "co_writer") return "写作";
  return "对话";
}

export function moreFeatureHint(path: string) {
  if (path === "/question") return "生成练习和仿题";
  if (path === "/co-writer") return "润色、扩写和改写";
  if (path === "/vision") return "上传图片并解题";
  if (path === "/agents") return "管理 SparkBot";
  if (path === "/playground") return "测试各类能力";
  return "打开功能页";
}

export function requestNewChat() {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem("sparkweave:new-chat-request", String(Date.now()));
  window.dispatchEvent(new CustomEvent("sparkweave:new-chat"));
}

function normalizeTimestamp(value: number | undefined) {
  if (!value) return 0;
  return value < 1_000_000_000_000 ? value * 1000 : value;
}
