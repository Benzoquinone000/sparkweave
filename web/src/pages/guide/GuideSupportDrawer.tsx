import { AnimatePresence, motion } from "framer-motion";
import { Brain, RefreshCw, Sparkles, Target, Trash2, X } from "lucide-react";

import { Button } from "@/components/ui/Button";
import type { GuideV2SessionSummary, GuideV2Task } from "@/lib/types";

export function GuideSupportDrawer({
  open,
  currentTask,
  routeUsesUnifiedProfile,
  sessions,
  activeSessionId,
  busy,
  onClose,
  onNewRoute,
  onSelectSession,
  onRefreshRecommendations,
  onDeleteActiveSession,
}: {
  open: boolean;
  currentTask: GuideV2Task | null;
  routeUsesUnifiedProfile: boolean;
  sessions: GuideV2SessionSummary[];
  activeSessionId: string | null;
  busy: boolean;
  onClose: () => void;
  onNewRoute: () => void;
  onSelectSession: (sessionId: string) => void;
  onRefreshRecommendations: () => void;
  onDeleteActiveSession: () => void;
}) {
  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-50 bg-slate-900/25"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <button
            type="button"
            className="absolute inset-0 cursor-default"
            aria-label="关闭路线面板"
            onClick={onClose}
          />
          <motion.aside
            className="absolute right-0 top-0 h-full w-full max-w-[430px] overflow-y-auto bg-canvas p-4 shadow-2xl"
            initial={{ x: 440 }}
            animate={{ x: 0 }}
            exit={{ x: 440 }}
            transition={{ type: "spring", stiffness: 280, damping: 30 }}
          >
            <div className="mb-4 flex items-center justify-between gap-3 rounded-lg border border-line bg-white p-4">
              <div>
                <p className="text-xs font-semibold text-brand-purple">当前路线</p>
                <h2 className="mt-1 text-lg font-semibold text-ink">先确认你现在学到哪一步</h2>
              </div>
              <Button tone="quiet" className="min-h-8 px-2" onClick={onClose}>
                <X size={16} />
              </Button>
            </div>

            <div className="space-y-4">
              {currentTask ? (
                <section className="rounded-lg border border-line bg-white p-4">
                  <div className="flex items-start gap-3">
                    <Target size={18} className="mt-0.5 text-brand-purple" />
                    <div>
                      <h2 className="text-base font-semibold text-ink">你现在正在这里</h2>
                      <p className="mt-1 text-sm font-semibold leading-6 text-ink">{currentTask.title}</p>
                      <p className="mt-1 line-clamp-3 text-xs leading-5 text-slate-600">{currentTask.instruction || "继续完成当前任务。"}</p>
                    </div>
                  </div>
                </section>
              ) : null}

              <section className="rounded-lg border border-line bg-white p-4">
                <div className="flex items-start gap-3">
                  <Brain size={18} className="mt-0.5 text-brand-purple" />
                  <div>
                    <h2 className="text-base font-semibold text-ink">这条路线已经参考了你的画像</h2>
                    <p className="mt-1 text-sm leading-6 text-slate-600">
                      {routeUsesUnifiedProfile
                        ? "系统已经把你的偏好和薄弱点带进当前路线。"
                        : "完成前测、练习和反思后，路线会继续跟着画像一起变准。"}
                    </p>
                  </div>
                </div>
                <a
                  href="/memory"
                  className="mt-3 inline-flex min-h-9 items-center justify-center rounded-md border border-line bg-canvas px-3 text-xs font-medium text-slate-700 transition hover:border-brand-purple-300 hover:text-brand-purple"
                >
                  查看学习画像
                </a>
              </section>

              <section className="rounded-lg border border-line bg-white p-4">
                <h2 className="text-base font-semibold text-ink">想切换或重新开始时，再看这里</h2>
                <p className="mt-1 text-xs leading-5 text-slate-500">主流程不会受影响，只有想换路线时才需要操作。</p>
                <div className="mt-4 space-y-3">
                  <Button tone="primary" className="w-full" onClick={onNewRoute}>
                    <Sparkles size={16} />
                    新建一条路线
                  </Button>
                  <div className="max-h-52 space-y-2 overflow-y-auto pr-1">
                    {sessions.slice(0, 5).map((item) => (
                      <button
                        key={item.session_id}
                        type="button"
                        onClick={() => onSelectSession(item.session_id)}
                        className={`w-full rounded-lg border p-3 text-left transition ${
                          activeSessionId === item.session_id ? "border-ink bg-ink text-white" : "border-line bg-white hover:border-brand-purple-300 hover:bg-tint-lavender"
                        }`}
                      >
                        <p className="line-clamp-2 text-sm font-semibold text-ink">{item.goal}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          {item.progress ?? 0}% · {item.task_count ?? 0} 个任务
                        </p>
                      </button>
                    ))}
                    {!sessions.length ? <p className="rounded-lg bg-canvas p-3 text-sm text-slate-500">还没有学习路线。</p> : null}
                  </div>
                </div>
              </section>

              <div className="rounded-lg border border-line bg-white p-3">
                <p className="text-xs font-semibold text-slate-500">仅在需要时使用</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  <Button
                    tone="quiet"
                    className="min-h-8 px-2 text-xs"
                    disabled={!activeSessionId || busy}
                    onClick={onRefreshRecommendations}
                  >
                    <RefreshCw size={14} />
                    重新整理
                  </Button>
                  <Button
                    tone="quiet"
                    className="min-h-8 px-2 text-xs text-brand-red hover:bg-red-50"
                    disabled={!activeSessionId || busy}
                    onClick={onDeleteActiveSession}
                  >
                    <Trash2 size={14} />
                    删除
                  </Button>
                </div>
              </div>
            </div>
          </motion.aside>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
