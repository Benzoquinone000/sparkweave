import {
  BookOpen,
  Bot,
  Brain,
  DatabaseZap,
  FileQuestion,
  FlaskConical,
  GraduationCap,
  Image,
  MessageSquareText,
  PenLine,
  Settings,
  type LucideIcon,
} from "lucide-react";

export type NavAccent = "purple" | "teal" | "blue" | "orange" | "pink";

export interface NavItem {
  to: string;
  label: string;
  shortLabel: string;
  icon: LucideIcon;
  accent: NavAccent;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const NAV_ACCENT_STYLES: Record<
  NavAccent,
  {
    bg: string;
    text: string;
    border: string;
    dot: string;
    active: string;
  }
> = {
  purple: {
    bg: "bg-white",
    text: "text-ink",
    border: "border-line-strong",
    dot: "bg-slate-400",
    active: "bg-white text-ink shadow-[0_1px_2px_rgba(15,15,15,0.035)]",
  },
  teal: {
    bg: "bg-white",
    text: "text-ink",
    border: "border-line-strong",
    dot: "bg-slate-400",
    active: "bg-white text-ink shadow-[0_1px_2px_rgba(15,15,15,0.035)]",
  },
  blue: {
    bg: "bg-white",
    text: "text-ink",
    border: "border-line-strong",
    dot: "bg-slate-400",
    active: "bg-white text-ink shadow-[0_1px_2px_rgba(15,15,15,0.035)]",
  },
  orange: {
    bg: "bg-white",
    text: "text-ink",
    border: "border-line-strong",
    dot: "bg-slate-400",
    active: "bg-white text-ink shadow-[0_1px_2px_rgba(15,15,15,0.035)]",
  },
  pink: {
    bg: "bg-white",
    text: "text-ink",
    border: "border-line-strong",
    dot: "bg-slate-400",
    active: "bg-white text-ink shadow-[0_1px_2px_rgba(15,15,15,0.035)]",
  },
};

export const NAV_GROUPS: NavGroup[] = [
  {
    label: "开始",
    items: [
      { to: "/guide", label: "学习", shortLabel: "学习", icon: GraduationCap, accent: "teal" },
      { to: "/knowledge", label: "资料", shortLabel: "资料", icon: BookOpen, accent: "blue" },
      { to: "/notebook", label: "记录", shortLabel: "记录", icon: Brain, accent: "orange" },
      { to: "/settings", label: "设置", shortLabel: "设置", icon: Settings, accent: "pink" },
    ],
  },
  {
    label: "任务补充",
    items: [
      { to: "/chat", label: "问资料", shortLabel: "问答", icon: MessageSquareText, accent: "purple" },
      { to: "/question", label: "练一练", shortLabel: "练习", icon: FileQuestion, accent: "pink" },
      { to: "/memory", label: "学习状态", shortLabel: "状态", icon: DatabaseZap, accent: "orange" },
      { to: "/agents", label: "课程助教", shortLabel: "助教", icon: Bot, accent: "purple" },
    ],
  },
  {
    label: "按需入口",
    items: [
      { to: "/co-writer", label: "写作助手", shortLabel: "写作", icon: PenLine, accent: "orange" },
      { to: "/vision", label: "图像解题", shortLabel: "图像", icon: Image, accent: "blue" },
      { to: "/playground", label: "试跑区", shortLabel: "试跑", icon: FlaskConical, accent: "pink" },
    ],
  },
];

export const NAV_ITEMS = NAV_GROUPS.flatMap((group) => group.items);

export function isActivePath(currentPath: string, target: string) {
  return currentPath === target || currentPath.startsWith(`${target}/`);
}

export function getNavAccentByPath(path: string) {
  const item = NAV_ITEMS.find((candidate) => isActivePath(path, candidate.to));
  return NAV_ACCENT_STYLES[item?.accent ?? "teal"];
}
