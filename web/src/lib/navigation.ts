import {
  BookOpen,
  Bot,
  Brain,
  DatabaseZap,
  FileQuestion,
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
    label: "学习",
    items: [
      { to: "/chat", label: "当前对话", shortLabel: "对话", icon: MessageSquareText, accent: "purple" },
      { to: "/guide", label: "导学路线", shortLabel: "导学", icon: GraduationCap, accent: "teal" },
      { to: "/memory", label: "学习画像", shortLabel: "画像", icon: DatabaseZap, accent: "orange" },
      { to: "/knowledge", label: "知识库", shortLabel: "知识", icon: BookOpen, accent: "blue" },
      { to: "/notebook", label: "学习笔记", shortLabel: "笔记", icon: Brain, accent: "teal" },
      { to: "/question", label: "题目生成", shortLabel: "题目", icon: FileQuestion, accent: "pink" },
    ],
  },
  {
    label: "能力",
    items: [
      { to: "/co-writer", label: "写作助手", shortLabel: "写作", icon: PenLine, accent: "orange" },
      { to: "/vision", label: "图像解题", shortLabel: "图像", icon: Image, accent: "blue" },
      { to: "/agents", label: "AI 助教", shortLabel: "助教", icon: Bot, accent: "purple" },
      { to: "/playground", label: "能力实验室", shortLabel: "实验室", icon: GraduationCap, accent: "pink" },
    ],
  },
  {
    label: "系统",
    items: [{ to: "/settings", label: "设置", shortLabel: "设置", icon: Settings, accent: "pink" }],
  },
];

export const NAV_ITEMS = NAV_GROUPS.flatMap((group) => group.items);

export function isActivePath(currentPath: string, target: string) {
  return currentPath === target || currentPath.startsWith(`${target}/`);
}

export function getNavAccentByPath(path: string) {
  const item = NAV_ITEMS.find((candidate) => isActivePath(path, candidate.to));
  return NAV_ACCENT_STYLES[item?.accent ?? "purple"];
}
