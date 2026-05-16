import type { SparkBotFile } from "@/lib/types";

type AssistantWorkspaceFileMeta = {
  label: string;
  detail: string;
  priority: number;
  tone: "neutral" | "success" | "warning" | "brand";
};

const ASSISTANT_WORKSPACE_FILE_META: Record<string, AssistantWorkspaceFileMeta> = {
  "COURSE.md": {
    label: "课程资料",
    detail: "课程定位、目标、项目产物",
    priority: 1,
    tone: "success",
  },
  "LESSONS.md": {
    label: "课程资料",
    detail: "8 周课程安排与课堂活动",
    priority: 2,
    tone: "success",
  },
  "QUESTION_BANK.md": {
    label: "课程资料",
    detail: "概念题、判断题、实践任务",
    priority: 3,
    tone: "success",
  },
  "RUBRIC.md": {
    label: "课程资料",
    detail: "项目评分标准与赛题映射",
    priority: 4,
    tone: "success",
  },
  "RESOURCES.md": {
    label: "课程资料",
    detail: "资源索引和讯飞工具链讲法",
    priority: 5,
    tone: "success",
  },
  "NOTES.md": {
    label: "演示笔记",
    detail: "稳定提示词与生成产物摘要",
    priority: 10,
    tone: "brand",
  },
  "SOUL.md": {
    label: "助教设定",
    detail: "人格、职责和回答方式",
    priority: 20,
    tone: "neutral",
  },
  "USER.md": {
    label: "助教设定",
    detail: "演示学习者画像和偏好",
    priority: 21,
    tone: "neutral",
  },
  "TOOLS.md": {
    label: "助教设定",
    detail: "可用工具和使用边界",
    priority: 22,
    tone: "neutral",
  },
  "AGENTS.md": {
    label: "助教设定",
    detail: "多智能体协作路线",
    priority: 23,
    tone: "neutral",
  },
  "HEARTBEAT.md": {
    label: "助教设定",
    detail: "主动提醒和录屏前检查",
    priority: 24,
    tone: "neutral",
  },
};

export function assistantWorkspaceFileMeta(filename: string): AssistantWorkspaceFileMeta {
  return (
    ASSISTANT_WORKSPACE_FILE_META[filename] ?? {
      label: "工作文件",
      detail: "助教长期参考的自定义资料",
      priority: 50,
      tone: "neutral",
    }
  );
}

export function sortAssistantWorkspaceFiles(files: SparkBotFile[]) {
  return [...files].sort((left, right) => {
    const leftMeta = assistantWorkspaceFileMeta(left.filename);
    const rightMeta = assistantWorkspaceFileMeta(right.filename);
    if (leftMeta.priority !== rightMeta.priority) return leftMeta.priority - rightMeta.priority;
    return left.filename.localeCompare(right.filename);
  });
}
