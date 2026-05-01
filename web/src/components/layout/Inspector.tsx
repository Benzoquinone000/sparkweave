import { Activity, BookOpenCheck, ChevronRight, Cpu, Database, History, Loader2, MessageSquareText, Wrench, X } from "lucide-react";
import { motion } from "framer-motion";
import { useState, type ReactNode } from "react";

import { Badge } from "@/components/ui/Badge";
import { useDashboardActivities, useDashboardActivity, useKnowledgeBases, useSessions, useSystemStatus } from "@/hooks/useApiQueries";
import { capabilityLabel } from "@/lib/capabilities";
import { sessionDisplayTitle } from "@/lib/sessionDisplay";
import type { DashboardActivityDetail } from "@/lib/types";

export function Inspector({ onClose }: { onClose: () => void }) {
  const status = useSystemStatus();
  const knowledge = useKnowledgeBases();
  const sessions = useSessions();
  const activities = useDashboardActivities(8);
  const [selectedActivityId, setSelectedActivityId] = useState<string | null>(null);
  const activityDetail = useDashboardActivity(selectedActivityId);

  return (
    <motion.aside
      className="ml-auto flex h-full w-full max-w-[380px] flex-col border-l border-line bg-white shadow-panel"
      initial={{ x: 420 }}
      animate={{ x: 0 }}
      exit={{ x: 420 }}
      transition={{ duration: 0.24, ease: "easeOut" }}
      onClick={(event) => event.stopPropagation()}
      data-testid="inspector-drawer"
    >
      <div className="flex h-16 shrink-0 items-center justify-between border-b border-line px-5">
        <div>
          <p className="text-sm font-semibold text-ink">学习动态</p>
          <p className="mt-1 text-xs text-slate-500">最近记录和可用资料</p>
        </div>
        <button
          type="button"
          className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-line text-slate-600 transition hover:border-teal-200 hover:text-brand-teal"
          onClick={onClose}
          aria-label="关闭学习动态"
        >
          <X size={17} />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        <div className="space-y-4">
          <section className="dt-soft-enter rounded-lg border border-line bg-canvas p-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-ink">服务</h2>
              <Activity size={17} className="text-brand-blue" />
            </div>
            <div className="mt-4 grid gap-2">
              <StatusRow
                icon={<Cpu size={16} />}
                label="问答模型"
                value={status.data?.llm?.model || status.data?.llm?.status || "未检测"}
                tone={status.data?.llm?.status === "configured" ? "success" : "warning"}
              />
              <StatusRow
                icon={<Database size={16} />}
                label="向量模型"
                value={status.data?.embeddings?.model || status.data?.embeddings?.status || "未检测"}
                tone={status.data?.embeddings?.status === "configured" ? "success" : "warning"}
              />
              <StatusRow
                icon={<Wrench size={16} />}
                label="联网搜索"
                value={status.data?.search?.provider || status.data?.search?.status || "optional"}
                tone={status.data?.search?.status === "configured" ? "success" : "neutral"}
              />
            </div>
          </section>

          <section className="dt-soft-enter rounded-lg border border-line bg-canvas p-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-ink">上下文</h2>
              <BookOpenCheck size={17} className="text-brand-teal" />
            </div>
            <div className="mt-4 grid grid-cols-2 gap-2">
              <ContextMetric label="知识库" value={knowledge.data?.length ?? 0} />
              <ContextMetric label="会话" value={sessions.data?.length ?? 0} />
            </div>
          </section>

          <section className="dt-soft-enter rounded-lg border border-line bg-canvas p-3">
            <div className="flex items-center gap-2">
              <History size={17} className="text-brand-red" />
              <h2 className="text-sm font-semibold text-ink">最近任务</h2>
            </div>
            <div className="mt-4 space-y-2">
              {(activities.data ?? []).slice(0, 5).map((activity) => (
                <button
                  key={activity.id}
                  type="button"
                  onClick={() => setSelectedActivityId(activity.id)}
                  data-testid={`dashboard-activity-${activity.id}`}
                  className={`dt-interactive w-full rounded-lg border p-3 text-left hover:border-teal-200 hover:bg-white ${
                    selectedActivityId === activity.id ? "border-teal-200 bg-white" : "border-line bg-white/70"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <p className="min-w-0 flex-1 truncate text-sm font-medium text-ink">{activity.title || "未命名任务"}</p>
                    <Badge tone={activity.status === "failed" ? "danger" : activity.status === "running" ? "warning" : "neutral"}>
                      {activityTypeLabel(activity.type)}
                    </Badge>
                    <ChevronRight size={15} className="text-slate-400" />
                  </div>
                  {activity.summary ? <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-500">{activity.summary}</p> : null}
                </button>
              ))}
              {selectedActivityId ? <ActivityDetail detail={activityDetail.data} loading={activityDetail.isLoading} /> : null}
              {!activities.data?.length && sessions.data?.length
                ? (sessions.data ?? []).slice(0, 5).map((session, index) => (
                    <div key={session.session_id} className="dt-soft-enter rounded-lg border border-line bg-white px-3 py-2">
                      <p className="truncate text-sm font-medium text-ink">{sessionDisplayTitle(session, index)}</p>
                      <p className="mt-1 truncate text-xs text-slate-500">{session.message_count} 条消息</p>
                    </div>
                  ))
                : null}
              {activities.isLoading ? (
                <div className="rounded-lg bg-white p-3 text-sm leading-6 text-slate-500">正在读取最近任务...</div>
              ) : null}
              {!activities.data?.length && !sessions.data?.length && !activities.isLoading ? (
                <p className="rounded-lg bg-white p-3 text-sm leading-6 text-slate-500">还没有任务。开始一次学习对话后，这里会出现时间线。</p>
              ) : null}
            </div>
          </section>
        </div>
      </div>
    </motion.aside>
  );
}

function ActivityDetail({ detail, loading }: { detail?: DashboardActivityDetail; loading: boolean }) {
  const messages = detail?.content?.messages?.slice(-3) ?? [];
  if (loading) {
    return (
      <div className="rounded-lg border border-line bg-white p-3 text-sm text-slate-500">
        <span className="inline-flex items-center gap-2">
          <Loader2 size={15} className="animate-spin" />
          正在读取任务详情
        </span>
      </div>
    );
  }

  if (!detail) return null;

  return (
    <div className="rounded-lg border border-teal-200 bg-white p-3" data-testid="dashboard-activity-detail">
      <div className="flex items-center gap-2">
        <MessageSquareText size={16} className="text-brand-teal" />
        <h3 className="text-sm font-semibold text-ink">任务详情</h3>
        <Badge tone="brand">{formatStatusLabel(detail.content?.status || detail.type || "ready")}</Badge>
      </div>
      {detail.content?.summary ? <p className="mt-2 line-clamp-3 text-xs leading-5 text-slate-600">{detail.content.summary}</p> : null}
      <div className="mt-3 space-y-2">
        {messages.map((message, index) => (
          <div key={`${message.role || "message"}-${index}`} className="rounded-md border border-line bg-canvas px-3 py-2">
            <p className="text-[11px] font-medium uppercase text-slate-400">{formatRoleLabel(message.role || "message")}</p>
            <p className="mt-1 line-clamp-3 text-xs leading-5 text-slate-600">{message.content || "空消息"}</p>
          </div>
        ))}
        {!messages.length ? <p className="rounded-md bg-canvas px-3 py-2 text-xs text-slate-500">这条任务还没有可展示的消息。</p> : null}
      </div>
    </div>
  );
}

function ContextMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-line bg-white px-3 py-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-semibold text-ink">{value}</p>
    </div>
  );
}

function StatusRow({
  icon,
  label,
  value,
  tone,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  tone: "neutral" | "success" | "warning" | "danger" | "brand";
}) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-line bg-white px-3 py-2">
      <span className="text-slate-500">{icon}</span>
      <span className="min-w-0 flex-1">
        <span className="block text-xs text-slate-500">{label}</span>
        <span className="block truncate text-sm font-medium text-ink">{value}</span>
      </span>
      <Badge tone={tone}>{formatToneLabel(tone)}</Badge>
    </div>
  );
}

function formatToneLabel(tone: "neutral" | "success" | "warning" | "danger" | "brand") {
  return {
    neutral: "待确认",
    success: "可用",
    warning: "需检查",
    danger: "异常",
    brand: "运行中",
  }[tone];
}

function formatStatusLabel(status: string) {
  return (
    {
      ready: "就绪",
      running: "运行中",
      completed: "已完成",
      failed: "失败",
      chat: "对话",
      guide: "导学",
      knowledge: "资料库",
      notebook: "笔记",
      question: "题目",
    }[status] || status
  );
}

function activityTypeLabel(type: string | undefined) {
  const value = String(type || "chat");
  const labels: Record<string, string> = {
    chat: "即时答疑",
    guide: "导学",
    knowledge: "资料库",
    notebook: "笔记",
    question: "题目",
    visual: "图解",
    video: "视频",
  };
  return labels[value] || capabilityLabel(value);
}

function formatRoleLabel(role: string) {
  return (
    {
      user: "我",
      assistant: "助手",
      system: "系统",
      message: "消息",
    }[role] || role
  );
}
