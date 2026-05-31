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
    bg: "bg-accent-purple-soft",
    text: "text-accent-purple-ink",
    border: "border-accent-purple-line",
    dot: "bg-accent-purple-marker",
    active: "bg-accent-purple-active text-accent-purple-strong shadow-[0_1px_2px_rgba(15,15,15,0.035)]",
  },
  teal: {
    bg: "bg-accent-teal-soft",
    text: "text-accent-teal-ink",
    border: "border-accent-teal-line",
    dot: "bg-accent-teal-marker",
    active: "bg-accent-teal-active text-accent-teal-strong shadow-[0_1px_2px_rgba(15,15,15,0.035)]",
  },
  blue: {
    bg: "bg-accent-blue-soft",
    text: "text-accent-blue-ink",
    border: "border-accent-blue-line",
    dot: "bg-accent-blue-marker",
    active: "bg-accent-blue-active text-accent-blue-strong shadow-[0_1px_2px_rgba(15,15,15,0.035)]",
  },
  orange: {
    bg: "bg-accent-orange-soft",
    text: "text-accent-orange-ink",
    border: "border-accent-orange-line",
    dot: "bg-accent-orange-marker",
    active: "bg-accent-orange-active text-accent-orange-strong shadow-[0_1px_2px_rgba(15,15,15,0.035)]",
  },
  pink: {
    bg: "bg-accent-pink-soft",
    text: "text-accent-pink-ink",
    border: "border-accent-pink-line",
    dot: "bg-accent-pink-marker",
    active: "bg-accent-pink-active text-accent-pink-strong shadow-[0_1px_2px_rgba(15,15,15,0.035)]",
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
