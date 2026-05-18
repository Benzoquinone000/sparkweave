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
    bg: "bg-tint-lavender",
    text: "text-brand-purple",
    border: "border-brand-purple-300",
    dot: "bg-brand-purple",
    active: "bg-tint-lavender text-brand-purple",
  },
  teal: {
    bg: "bg-tint-mint",
    text: "text-brand-teal",
    border: "border-brand-teal",
    dot: "bg-brand-teal",
    active: "bg-tint-mint text-brand-teal",
  },
  blue: {
    bg: "bg-tint-sky",
    text: "text-brand-blue",
    border: "border-brand-blue",
    dot: "bg-brand-blue",
    active: "bg-tint-sky text-brand-blue",
  },
  orange: {
    bg: "bg-tint-peach",
    text: "text-brand-orange",
    border: "border-brand-orange",
    dot: "bg-brand-orange",
    active: "bg-tint-peach text-brand-orange",
  },
  pink: {
    bg: "bg-tint-rose",
    text: "text-brand-pink",
    border: "border-brand-pink",
    dot: "bg-brand-pink",
    active: "bg-tint-rose text-brand-pink",
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
    label: "学习工具",
    items: [
      { to: "/chat", label: "问资料", shortLabel: "问答", icon: MessageSquareText, accent: "purple" },
      { to: "/question", label: "练一练", shortLabel: "练习", icon: FileQuestion, accent: "pink" },
      { to: "/memory", label: "学习画像", shortLabel: "画像", icon: DatabaseZap, accent: "orange" },
      { to: "/agents", label: "课程助教", shortLabel: "助教", icon: Bot, accent: "purple" },
    ],
  },
  {
    label: "高级工具",
    items: [
      { to: "/co-writer", label: "写作助手", shortLabel: "写作", icon: PenLine, accent: "orange" },
      { to: "/vision", label: "图像解题", shortLabel: "图像", icon: Image, accent: "blue" },
      { to: "/playground", label: "调试台", shortLabel: "调试", icon: FlaskConical, accent: "pink" },
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
