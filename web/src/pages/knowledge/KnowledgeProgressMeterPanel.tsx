import { motion } from "framer-motion";

export function KnowledgeProgressMeter({
  progressMessage,
  progressPercent,
}: {
  progressMessage: string;
  progressPercent: number;
}) {
  return (
    <>
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-ink">{progressMessage}</span>
        <span className="text-slate-500">{progressPercent}%</span>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-sm bg-white">
        <motion.div
          className="h-full rounded-sm bg-brand-purple"
          initial={false}
          animate={{ width: `${progressPercent}%` }}
          transition={{ duration: 0.35, ease: "easeOut" }}
          style={{ width: `${progressPercent}%` }}
        />
      </div>
    </>
  );
}

export function KnowledgeProgressMilestones({ taskMilestones }: { taskMilestones: string[] }) {
  if (!taskMilestones.length) return null;

  return (
    <div className="mt-4 rounded-lg border border-brand-purple-300 bg-tint-lavender p-3" data-testid="knowledge-task-milestones">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold text-ink">关键进展</p>
        <span className="rounded bg-brand-purple-50 px-2 py-1 text-xs font-medium text-brand-purple">{taskMilestones.length} 步</span>
      </div>
      <div className="mt-3 grid gap-2">
        {taskMilestones.map((line, index) => (
          <motion.div
            key={`${line}-${index}`}
            className="flex gap-2 rounded-md bg-white px-3 py-2 text-xs leading-5 text-slate-700"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.16 }}
          >
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-sm bg-brand-purple" />
            <span>{line}</span>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
