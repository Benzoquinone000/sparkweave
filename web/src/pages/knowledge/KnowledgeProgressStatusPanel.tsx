import type { KnowledgeTaskStatusResponse } from "@/lib/types";

export function KnowledgeProgressStatusSummary({
  taskStatus,
  taskStatusLoading,
}: {
  taskStatus?: KnowledgeTaskStatusResponse | null;
  taskStatusLoading?: boolean;
}) {
  if (!taskStatus && !taskStatusLoading) return null;

  const taskMetadata = taskStatus?.metadata ?? {};
  const taskStatusText = formatTaskStatus(textValue(taskMetadata.status) || (taskStatusLoading ? "loading" : "idle"));
  const taskType = formatTaskType(textValue(taskMetadata.task_type));
  const updatedAt = formatTaskDate(textValue(taskMetadata.updated_at) || textValue(taskMetadata.finished_at));
  const latestEvent = formatLatestEvent(textValue(taskStatus?.stream?.latest_event?.event));
  const eventCount = taskStatus?.stream?.event_count ?? 0;

  return (
    <div className="mb-4 grid gap-2 rounded-lg border border-line bg-canvas p-3 text-xs sm:grid-cols-4">
      <TaskStatusFact label="任务状态" value={taskStatusText} />
      <TaskStatusFact label="任务类型" value={taskType} />
      <TaskStatusFact label="记录条数" value={String(eventCount)} />
      <TaskStatusFact label="最近事件" value={latestEvent} />
      {updatedAt ? (
        <p className="sm:col-span-4 text-slate-500">更新时间：{updatedAt}</p>
      ) : null}
    </div>
  );
}

function TaskStatusFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-white px-3 py-2">
      <p className="text-[11px] font-medium text-slate-500">{label}</p>
      <p className="mt-1 truncate text-xs font-semibold text-ink">{value}</p>
    </div>
  );
}

function textValue(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function formatTaskStatus(value: string) {
  const labels: Record<string, string> = {
    queued: "排队中",
    running: "处理中",
    processing: "处理中",
    completed: "已完成",
    complete: "已完成",
    failed: "失败",
    error: "异常",
    cancelled: "已取消",
    canceled: "已取消",
    loading: "读取中",
    idle: "暂无任务",
  };
  return labels[value.toLowerCase()] || value || "-";
}

function formatTaskType(value: string) {
  const labels: Record<string, string> = {
    kb_create: "创建资料库",
    kb_upload: "上传资料",
    kb_reindex: "重新整理资料",
    kb_sync_folder: "同步文件夹",
    kb_test: "测试任务",
  };
  return labels[value.toLowerCase()] || value || "-";
}

function formatLatestEvent(value: string) {
  const labels: Record<string, string> = {
    log: "处理记录",
    status: "状态更新",
    complete: "完成",
    failed: "失败",
    message: "消息",
    heartbeat: "保持连接",
  };
  return labels[value.toLowerCase()] || value || "-";
}

function formatTaskDate(value: string) {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}
