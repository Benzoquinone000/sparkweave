import { BookOpen, Bot, LibraryBig, Mic, Play, RefreshCw, Search, type LucideIcon } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import type { LearnerProfileSnapshot, LearningEffectNextAction, LearningEffectReport, SparkBotFile } from "@/lib/types";
import { assistantEvidenceRefs } from "./assistantEvidenceUtils";
import { latestAssistantReply } from "./assistantHistoryUtils";

type AssistantDemoReadinessItem = {
  id: string;
  title: string;
  detail: string;
  label: string;
  tone: "neutral" | "success" | "warning" | "brand";
  icon: LucideIcon;
};

const ASSISTANT_DEMO_REQUIRED_COURSE_FILES = ["COURSE.md", "LESSONS.md", "QUESTION_BANK.md", "RUBRIC.md", "RESOURCES.md"];

const ASSISTANT_DEMO_TIMELINE = [
  { time: "0:00", title: "今日建议", detail: "说明画像和推荐依据" },
  { time: "1:30", title: "资料答疑", detail: "展示课程来源和讲解" },
  { time: "3:10", title: "多模态资源", detail: "图解、OCR 或 TTS" },
  { time: "5:20", title: "反馈回写", detail: "形成学习效果证据" },
  { time: "6:20", title: "课程包", detail: "展示提交材料与价值" },
];

export function AssistantDemoReadinessPanel({
  report,
  profile,
  files,
  history,
  nextActions,
}: {
  report?: LearningEffectReport;
  profile?: LearnerProfileSnapshot;
  files: SparkBotFile[];
  history: Array<Record<string, unknown>>;
  nextActions: LearningEffectNextAction[];
}) {
  const readiness = assistantDemoReadinessItems({ report, profile, files, history, nextActions });
  const readyCount = readiness.filter((item) => item.tone === "success" || item.tone === "brand").length;
  const totalCount = readiness.length;

  return (
    <section className="relative overflow-hidden rounded-lg border border-brand-purple-300 bg-white p-4 shadow-[0_14px_36px_-30px_rgba(86,69,212,0.45)]" data-testid="assistant-demo-readiness">
      <div className="pointer-events-none absolute right-5 top-5 hidden h-10 w-14 rotate-2 rounded-md bg-tint-yellow opacity-70 md:block" />
      <div className="pointer-events-none absolute right-24 top-14 hidden h-8 w-12 -rotate-3 rounded-md bg-tint-sky opacity-70 md:block" />
      <div className="relative flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Play size={18} className="text-brand-purple" />
            <h2 className="text-base font-semibold text-ink">比赛演示检查</h2>
          </div>
          <p className="mt-1 text-sm leading-6 text-slate-500">把赛题要求、录屏路线和提交材料收在同一处，便于 7 分钟演示前快速核对。</p>
        </div>
        <Badge tone={readyCount === totalCount ? "success" : "warning"}>
          {readyCount}/{totalCount} 已就绪
        </Badge>
      </div>

      <div className="relative mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div>
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {readiness.map((item) => {
              const Icon = item.icon;
              return (
                <div key={item.id} className={`border p-3 ${assistantDemoCardClass(item.id)}`} style={{ borderRadius: 8 }}>
                  <div className="flex items-start justify-between gap-2">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center border border-line bg-white text-brand-purple" style={{ borderRadius: 8 }}>
                      <Icon size={15} />
                    </span>
                    <Badge tone={item.tone}>{item.label}</Badge>
                  </div>
                  <p className="mt-3 text-sm font-semibold text-ink">{item.title}</p>
                  <p className="mt-1 line-clamp-3 text-xs leading-5 text-slate-500">{item.detail}</p>
                </div>
              );
            })}
          </div>

          <div className="mt-3 grid gap-2 border-t border-line pt-3 sm:grid-cols-3">
            <div className="border border-line bg-canvas px-3 py-2" style={{ borderRadius: 8 }}>
              <p className="text-xs text-slate-500">PPT 截图</p>
              <p className="mt-1 text-sm font-semibold text-ink">助教中心 / 资料与产物</p>
            </div>
            <div className="border border-line bg-canvas px-3 py-2" style={{ borderRadius: 8 }}>
              <p className="text-xs text-slate-500">提交包</p>
              <p className="mt-1 text-sm font-semibold text-ink">dist/competition_package</p>
            </div>
            <div className="border border-line bg-canvas px-3 py-2" style={{ borderRadius: 8 }}>
              <p className="text-xs text-slate-500">AI Coding</p>
              <p className="mt-1 text-sm font-semibold text-ink">docs/ai-coding-statement.md</p>
            </div>
          </div>
        </div>

        <div className="border border-line bg-[linear-gradient(180deg,#fbfaf8_0%,#f8f5e8_100%)] p-3" style={{ borderRadius: 8 }}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-xs font-semibold text-brand-purple">7 分钟录屏路线</p>
              <h3 className="mt-1 text-sm font-semibold text-ink">按这条线收束演示</h3>
            </div>
            <Badge tone="brand">赛题映射</Badge>
          </div>
          <div className="mt-3 grid gap-2">
            {ASSISTANT_DEMO_TIMELINE.map((step) => (
              <div key={`${step.time}-${step.title}`} className="flex gap-2 border-t border-line pt-2 first:border-t-0 first:pt-0">
                <span className="w-10 shrink-0 text-xs font-semibold text-brand-purple">{step.time}</span>
                <span className="min-w-0">
                  <span className="block text-xs font-semibold text-ink">{step.title}</span>
                  <span className="block text-xs leading-5 text-slate-500">{step.detail}</span>
                </span>
              </div>
            ))}
          </div>
          <div className="mt-3 border-t border-line pt-3">
            <p className="text-xs font-semibold text-ink">导出命令</p>
            <code className="mt-2 block overflow-x-auto rounded-md border border-line bg-white px-3 py-2 text-xs text-slate-600">
              python scripts/export_competition_package.py --archive dist/sparkweave-competition-package.zip
            </code>
          </div>
        </div>
      </div>
    </section>
  );
}

function assistantDemoReadinessItems({
  report,
  profile,
  files,
  history,
  nextActions,
}: {
  report?: LearningEffectReport;
  profile?: LearnerProfileSnapshot;
  files: SparkBotFile[];
  history: Array<Record<string, unknown>>;
  nextActions: LearningEffectNextAction[];
}): AssistantDemoReadinessItem[] {
  const filenames = new Set(files.map((file) => file.filename));
  const courseFileCount = ASSISTANT_DEMO_REQUIRED_COURSE_FILES.filter((filename) => filenames.has(filename)).length;
  const hasAgentRoute = filenames.has("AGENTS.md");
  const hasToolNotes = filenames.has("TOOLS.md") || filenames.has("RESOURCES.md");
  const sourceReady = Boolean(report?.knowledge_context?.ready || report?.study_brief?.knowledge_evidence?.ready || courseFileCount);
  const eventCount = report?.summary?.event_count ?? 0;
  const evidenceCount = assistantEvidenceRefs(report).length;
  const hasAssistantReply = Boolean(latestAssistantReply(history));

  return [
    {
      id: "course",
      title: "完整高校课程",
      detail: `${courseFileCount}/${ASSISTANT_DEMO_REQUIRED_COURSE_FILES.length} 个课程资料文件已在工作区，可展示大纲、课时、题库、Rubric 和资源索引。`,
      label: courseFileCount >= ASSISTANT_DEMO_REQUIRED_COURSE_FILES.length ? "可展示" : "待补齐",
      tone: courseFileCount >= ASSISTANT_DEMO_REQUIRED_COURSE_FILES.length ? "success" : "warning",
      icon: BookOpen,
    },
    {
      id: "profile-path",
      title: "画像与路径推荐",
      detail: profile && nextActions.length ? `${profile.overview?.current_focus || "已读取画像"}，并给出 ${nextActions.length} 个下一步行动。` : "等待学习画像或 next action 数据。",
      label: profile && nextActions.length ? "已连接" : profile || nextActions.length ? "部分就绪" : "待建立",
      tone: profile && nextActions.length ? "success" : profile || nextActions.length ? "warning" : "neutral",
      icon: Bot,
    },
    {
      id: "grounding",
      title: "课程资料智能辅导",
      detail: sourceReady ? report?.knowledge_context?.summary || report?.study_brief?.knowledge_evidence?.summary || "回答可基于课程资料和工作区文件组织。" : "还没有可追溯来源。",
      label: sourceReady ? "可追溯" : "待接入",
      tone: sourceReady ? "success" : "warning",
      icon: Search,
    },
    {
      id: "multi-agent",
      title: "多智能体资源生成",
      detail: hasAgentRoute ? "AGENTS.md 已描述画像、检索、讲解、练习和评估协作路线。" : "建议补充 AGENTS.md 作为答辩时的协作路线证据。",
      label: hasAgentRoute ? "有路线" : "待补充",
      tone: hasAgentRoute ? "success" : "warning",
      icon: LibraryBig,
    },
    {
      id: "iflytek",
      title: "讯飞多模态工具",
      detail: hasToolNotes ? "TOOLS.md 或 RESOURCES.md 已说明星火、OCR、语音听写和 TTS 的接入讲法。" : "可先用页面多模态入口演示降级流程。",
      label: hasToolNotes ? "可讲清" : "需说明",
      tone: hasToolNotes ? "success" : "warning",
      icon: Mic,
    },
    {
      id: "effect",
      title: "学习效果评估闭环",
      detail: eventCount || evidenceCount || hasAssistantReply ? `${eventCount || evidenceCount || 1} 条学习证据可用于说明反馈、错因和动态调整。` : "完成一次反馈后即可点亮评估闭环。",
      label: eventCount || evidenceCount || hasAssistantReply ? "已闭环" : "待回写",
      tone: eventCount || evidenceCount || hasAssistantReply ? "success" : "neutral",
      icon: RefreshCw,
    },
  ];
}

function assistantDemoCardClass(id: string) {
  if (id === "course") return "border-line bg-tint-yellow";
  if (id === "profile-path") return "border-line bg-tint-lavender";
  if (id === "grounding") return "border-line bg-tint-sky";
  if (id === "multi-agent") return "border-line bg-tint-mint";
  if (id === "iflytek") return "border-line bg-tint-rose";
  if (id === "effect") return "border-line bg-tint-peach";
  return "border-line bg-canvas";
}
