import { CalendarClock, Loader2, Pause, Play, Plus, RefreshCw, Trash2 } from "lucide-react";
import type { FormEvent } from "react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FieldShell, SelectInput, TextArea, TextInput } from "@/components/ui/Field";
import type { SparkBotCronJob, SparkBotCronResponse, SparkBotSummary } from "@/lib/types";

type CronKind = "every" | "cron" | "at";

export type CreateCronPayload = {
  name?: string;
  message: string;
  kind: CronKind;
  every_seconds?: number;
  cron_expr?: string;
  at?: string;
  tz?: string;
  deliver?: boolean;
  channel?: string | null;
  to?: string | null;
};

export function SparkBotCronPanel({
  bot,
  cron,
  loading,
  pending,
  onRefresh,
  onCreate,
  onToggle,
  onRun,
  onDelete,
}: {
  bot?: SparkBotSummary;
  cron?: SparkBotCronResponse;
  loading: boolean;
  pending: boolean;
  onRefresh: () => void;
  onCreate: (payload: CreateCronPayload) => Promise<unknown>;
  onToggle: (job: SparkBotCronJob, enabled: boolean) => Promise<unknown>;
  onRun: (job: SparkBotCronJob) => Promise<unknown>;
  onDelete: (job: SparkBotCronJob) => Promise<unknown>;
}) {
  const jobs = useMemo(() => cron?.jobs ?? [], [cron?.jobs]);
  const activeJobs = jobs.filter((job) => job.enabled).length;
  const nextJob = useMemo(
    () =>
      jobs
        .filter((job) => job.enabled && job.state?.nextRunAtMs)
        .sort((a, b) => Number(a.state?.nextRunAtMs ?? 0) - Number(b.state?.nextRunAtMs ?? 0))[0],
    [jobs],
  );

  return (
    <section className="rounded-lg border border-line bg-white p-3 shadow-[0_1px_2px_rgba(15,15,15,0.025)]" data-testid="sparkbot-cron-panel">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line pb-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <CalendarClock size={18} className="text-brand-purple" />
            <h2 className="text-base font-semibold text-ink">定时任务 Agent</h2>
          </div>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-500">
            巡检、日报、群提醒、资料同步和周期性 MCP 检查都放在这里。
          </p>
        </div>
        <Button tone="secondary" onClick={onRefresh} disabled={loading} data-testid="sparkbot-cron-refresh">
          {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
          刷新
        </Button>
      </div>

      <div className="mt-3 grid gap-2 md:grid-cols-3">
        <CronFact label="当前助教" value={bot?.name || bot?.bot_id || "未选择"} />
        <CronFact label="启用任务" value={`${activeJobs} / ${jobs.length}`} />
        <CronFact label="下次执行" value={nextJob ? formatTime(nextJob.state?.nextRunAtMs) : "暂无"} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
        <CronCreateForm disabled={!bot || pending} pending={pending} onCreate={onCreate} />
        <div className="min-w-0">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-ink">任务队列</h3>
            <Badge tone={bot?.running ? "success" : "neutral"}>{bot?.running ? "运行中" : "未启动"}</Badge>
          </div>
          <div className="mt-3 grid gap-2" data-testid="sparkbot-cron-jobs">
            {jobs.map((job) => (
              <CronJobRow
                key={job.id}
                job={job}
                running={Boolean(bot?.running)}
                pending={pending}
                onToggle={onToggle}
                onRun={onRun}
                onDelete={onDelete}
              />
            ))}
            {!jobs.length ? (
              <div className="rounded-lg border border-dashed border-line bg-canvas p-4">
                <p className="text-sm font-medium text-ink">还没有定时任务</p>
                <p className="mt-1 text-sm leading-6 text-slate-500">
                  先创建一个巡检或提醒任务，SparkBot 启动后会按队列自动执行。
                </p>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  );
}

function CronCreateForm({
  disabled,
  pending,
  onCreate,
}: {
  disabled: boolean;
  pending: boolean;
  onCreate: (payload: CreateCronPayload) => Promise<unknown>;
}) {
  const [kind, setKind] = useState<CronKind>("cron");
  const [name, setName] = useState("每日助教巡检");
  const [message, setMessage] = useState("检查 MCP 服务、skills 工作区和最近会话，生成一条需要我处理的助教任务。");
  const [everySeconds, setEverySeconds] = useState("3600");
  const [cronExpr, setCronExpr] = useState("0 9 * * *");
  const [timezone, setTimezone] = useState("Asia/Shanghai");
  const [at, setAt] = useState("");
  const [channel, setChannel] = useState("web");
  const [to, setTo] = useState("web");
  const [deliver, setDeliver] = useState(true);
  const [error, setError] = useState("");

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedMessage = message.trim();
    if (!trimmedMessage) {
      setError("任务内容不能为空。");
      return;
    }

    const payload: CreateCronPayload = {
      name: name.trim() || trimmedMessage.slice(0, 30),
      message: trimmedMessage,
      kind,
      deliver,
      channel: channel.trim() || "web",
      to: to.trim() || "web",
      ...(kind === "every" ? { every_seconds: Number(everySeconds) } : {}),
      ...(kind === "cron" ? { cron_expr: cronExpr.trim(), tz: timezone.trim() || undefined } : {}),
      ...(kind === "at" ? { at } : {}),
    };

    if (kind === "every" && (!Number.isFinite(payload.every_seconds) || Number(payload.every_seconds) <= 0)) {
      setError("间隔秒数必须大于 0。");
      return;
    }
    if (kind === "cron" && !payload.cron_expr) {
      setError("Cron 表达式不能为空。");
      return;
    }
    if (kind === "at" && !at) {
      setError("请选择一次性执行时间。");
      return;
    }

    try {
      setError("");
      await onCreate(payload);
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "保存任务失败。");
    }
  };

  return (
    <form className="grid gap-3 rounded-lg border border-line bg-canvas p-3" onSubmit={submit} data-testid="sparkbot-cron-create">
      <div className="flex items-center gap-2">
        <Plus size={16} className="text-brand-purple" />
        <h3 className="text-sm font-semibold text-ink">创建任务</h3>
      </div>

      <FieldShell label="任务名">
        <TextInput value={name} onChange={(event) => setName(event.target.value)} data-testid="sparkbot-cron-name" />
      </FieldShell>

      <FieldShell label="触发方式">
        <SelectInput value={kind} onChange={(event) => setKind(event.target.value as CronKind)} data-testid="sparkbot-cron-kind">
          <option value="cron">Cron</option>
          <option value="every">固定间隔</option>
          <option value="at">执行一次</option>
        </SelectInput>
      </FieldShell>

      {kind === "every" ? (
        <FieldShell label="间隔秒数">
          <TextInput value={everySeconds} onChange={(event) => setEverySeconds(event.target.value)} inputMode="numeric" data-testid="sparkbot-cron-every" />
        </FieldShell>
      ) : null}

      {kind === "cron" ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <FieldShell label="Cron 表达式">
            <TextInput value={cronExpr} onChange={(event) => setCronExpr(event.target.value)} data-testid="sparkbot-cron-expr" />
          </FieldShell>
          <FieldShell label="时区">
            <TextInput value={timezone} onChange={(event) => setTimezone(event.target.value)} data-testid="sparkbot-cron-tz" />
          </FieldShell>
        </div>
      ) : null}

      {kind === "at" ? (
        <FieldShell label="执行时间">
          <TextInput type="datetime-local" value={at} onChange={(event) => setAt(event.target.value)} data-testid="sparkbot-cron-at" />
        </FieldShell>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2">
        <FieldShell label="通道">
          <TextInput value={channel} onChange={(event) => setChannel(event.target.value)} data-testid="sparkbot-cron-channel" />
        </FieldShell>
        <FieldShell label="会话">
          <TextInput value={to} onChange={(event) => setTo(event.target.value)} data-testid="sparkbot-cron-to" />
        </FieldShell>
      </div>

      <FieldShell label="Agent 指令">
        <TextArea value={message} onChange={(event) => setMessage(event.target.value)} className="min-h-36" data-testid="sparkbot-cron-message" />
      </FieldShell>

      <label className="flex items-start gap-2 text-sm text-slate-600">
        <input type="checkbox" checked={deliver} onChange={(event) => setDeliver(event.target.checked)} className="mt-1" />
        <span>执行后把结果发回通道</span>
      </label>

      {error ? <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-brand-red">{error}</p> : null}

      <Button tone="primary" type="submit" disabled={disabled || pending} data-testid="sparkbot-cron-create-submit">
        {pending ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
        保存任务
      </Button>
    </form>
  );
}

function CronJobRow({
  job,
  running,
  pending,
  onToggle,
  onRun,
  onDelete,
}: {
  job: SparkBotCronJob;
  running: boolean;
  pending: boolean;
  onToggle: (job: SparkBotCronJob, enabled: boolean) => Promise<unknown>;
  onRun: (job: SparkBotCronJob) => Promise<unknown>;
  onDelete: (job: SparkBotCronJob) => Promise<unknown>;
}) {
  const status = job.state?.lastStatus || "pending";
  return (
    <article className="rounded-lg border border-line bg-white p-3" data-testid={`sparkbot-cron-job-${job.id}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="truncate text-sm font-semibold text-ink">{job.name}</h4>
            <Badge tone={job.enabled ? "success" : "neutral"}>{job.enabled ? "启用" : "暂停"}</Badge>
            <Badge tone={statusTone(status)}>{statusLabel(status)}</Badge>
            <Badge tone="neutral">{formatSchedule(job)}</Badge>
          </div>
          <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-600">{job.payload?.message || "无指令"}</p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Button
            tone="secondary"
            className="min-h-9 px-3"
            onClick={() => void onRun(job)}
            disabled={!running || pending}
            title={running ? "立即运行" : "先启动助教"}
          >
            <Play size={15} />
          </Button>
          <Button
            tone="secondary"
            className="min-h-9 px-3"
            onClick={() => void onToggle(job, !job.enabled)}
            disabled={pending}
            title={job.enabled ? "暂停" : "启用"}
          >
            {job.enabled ? <Pause size={15} /> : <Play size={15} />}
          </Button>
          <Button tone="danger" className="min-h-9 px-3" onClick={() => void onDelete(job)} disabled={pending} title="删除">
            <Trash2 size={15} />
          </Button>
        </div>
      </div>
      <div className="mt-3 grid gap-2 border-t border-line pt-3 text-xs text-slate-500 sm:grid-cols-3">
        <span>下次：{formatTime(job.state?.nextRunAtMs)}</span>
        <span>上次：{formatTime(job.state?.lastRunAtMs)}</span>
        <span>通道：{job.payload?.channel || "web"} / {job.payload?.to || "web"}</span>
      </div>
      {job.state?.lastError ? <p className="mt-2 text-xs leading-5 text-brand-red">{job.state.lastError}</p> : null}
    </article>
  );
}

function CronFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-line bg-canvas px-3 py-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-ink">{value}</p>
    </div>
  );
}

function formatSchedule(job: SparkBotCronJob) {
  const schedule = job.schedule;
  if (schedule.kind === "every") return `每 ${Math.round(Number(schedule.everyMs || 0) / 1000)} 秒`;
  if (schedule.kind === "cron") return `${schedule.expr || "cron"}${schedule.tz ? ` · ${schedule.tz}` : ""}`;
  if (schedule.kind === "at") return `一次 · ${formatTime(schedule.atMs)}`;
  return schedule.kind;
}

function formatTime(value?: number | null) {
  if (!value) return "暂无";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "暂无";
  return date.toLocaleString("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function statusLabel(status?: string | null) {
  if (status === "ok") return "成功";
  if (status === "error") return "失败";
  if (status === "skipped") return "跳过";
  return "未运行";
}

function statusTone(status?: string | null): "neutral" | "success" | "warning" | "danger" {
  if (status === "ok") return "success";
  if (status === "error") return "danger";
  if (status === "skipped") return "warning";
  return "neutral";
}
