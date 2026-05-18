import { Badge } from "@/components/ui/Badge";
import type { GuideV2StudyPlan, GuideV2Task } from "@/lib/types";
import { GuideCourseSyllabusPanel } from "./GuideCourseSyllabusPanel";
import { GuideKnowledgeMapPanel, GuideTaskRow } from "./GuideKnowledgeMapPanel";
import { GuideStudyPlanPanel } from "./GuideStudyPlanPanel";
import { GuideSubPageFrame } from "./GuideSubPageFrame";

export function GuideRouteMapPage({
  plan,
  loading,
  metadata,
  highlightedSectionId,
  nodes,
  mastery,
  tasks,
  currentTask,
  onBack,
}: {
  plan: GuideV2StudyPlan | null;
  loading: boolean;
  metadata: Record<string, unknown>;
  highlightedSectionId: string | null;
  nodes: Array<Record<string, unknown>>;
  mastery: Record<string, Record<string, unknown>>;
  tasks: GuideV2Task[];
  currentTask: GuideV2Task | null;
  onBack: () => void;
}) {
  return (
    <GuideSubPageFrame
      eyebrow="完整路线"
      title="学习路线与任务队列"
      description="这里集中查看路径、知识地图和所有任务。主页面只保留当前动作。"
      onBack={onBack}
    >
      <GuideStudyPlanPanel plan={plan} loading={loading} />
      <GuideCourseSyllabusPanel metadata={metadata} />
      <section
        id="guide-route-map-section"
        className={`rounded-lg border bg-white p-5 transition-all duration-500 ${
          highlightedSectionId === "guide-route-map-section"
            ? "border-brand-purple ring-2 ring-brand-purple-300"
            : "border-line"
        }`}
      >
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-ink">知识地图</h2>
            <p className="mt-1 text-sm text-slate-500">按学习顺序展示知识点、当前所在位置和每个节点的任务。</p>
          </div>
          <Badge tone="neutral">{nodes.length} 节点</Badge>
        </div>
        <GuideKnowledgeMapPanel
          nodes={nodes}
          mastery={mastery}
          tasks={tasks}
          currentTask={currentTask}
        />
      </section>
      <section className="rounded-lg border border-line bg-white p-5">
        <h2 className="text-base font-semibold text-ink">任务队列</h2>
        <div className="mt-4 space-y-2">
          {tasks.map((task) => (
            <GuideTaskRow key={task.task_id} task={task} active={task.task_id === currentTask?.task_id} />
          ))}
          {!tasks.length ? <p className="rounded-lg bg-canvas p-4 text-sm text-slate-500">暂无任务。</p> : null}
        </div>
      </section>
    </GuideSubPageFrame>
  );
}
