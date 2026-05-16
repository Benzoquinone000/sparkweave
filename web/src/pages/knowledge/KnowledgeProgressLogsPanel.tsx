import { AnimatePresence, motion } from "framer-motion";

import { Badge } from "@/components/ui/Badge";

import { visibleKnowledgeLogText } from "./progressFormat";

export function KnowledgeProgressLogs({ taskLogs }: { taskLogs: string[] }) {
  return (
    <details className="mt-4 rounded-lg border border-line bg-canvas p-3 [&>summary::-webkit-details-marker]:hidden" data-testid="knowledge-task-log-details">
      <summary className="dt-interactive flex cursor-pointer list-none items-center justify-between gap-3 rounded-md px-1 py-1 text-sm">
        <span className="font-medium text-ink">完整处理记录</span>
        <Badge tone="neutral">{taskLogs.length ? `${taskLogs.length} 条` : "暂无"}</Badge>
      </summary>
      <div className="dt-event-feed mt-3 max-h-56 overflow-y-auto rounded-lg bg-white p-3" data-testid="knowledge-task-logs">
        {taskLogs.length ? (
          <AnimatePresence initial={false}>
            {taskLogs.map((line) => (
              <motion.p
                key={line}
                className="dt-event-row text-xs leading-5 text-slate-600"
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.16 }}
              >
                {visibleKnowledgeLogText(line)}
              </motion.p>
            ))}
          </AnimatePresence>
        ) : (
          <p className="text-sm text-slate-500">创建或上传资料后，处理记录会显示在这里。</p>
        )}
      </div>
    </details>
  );
}
