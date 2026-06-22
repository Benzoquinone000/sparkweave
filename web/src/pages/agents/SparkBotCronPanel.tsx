import {
  BellRing,
  CalendarClock,
  Loader2,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Trash2,
} from "lucide-react";
import type { FormEvent } from "react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FieldShell, SelectInput, TextArea, TextInput } from "@/components/ui/Field";
import type { SparkBotCronJob, SparkBotCronResponse, SparkBotSummary } from "@/lib/types";

type CronKind = "every" | "cron" | "at";
type SchedulePreset = "daily" | "weekly" | "interval" | "once" | "custom";
type CustomScheduleMode = "workdays" | "weekdays" | "monthly" | "cron";

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

const MESSAGE_TEMPLATES = [
  {
    id: "daily",
    label: "学习提醒",
    name: "每日学习提醒",
    message: "查看最近学习记录和课程资料，给学生发一条今天最应该完成的学习提醒。",
  },
  {
    id: "review",
    label: "复盘",
    name: "每周学习复盘",
    message: "整理本周学习记录、未完成事项和薄弱点，生成一条简短复盘和下周建议。",
  },
  {
    id: "materials",
    label: "资料巡检",
    name: "资料更新巡检",
    message: "检查课程资料和最近问题，列出需要补充、整理或推送给学生的内容。",
  },
  {
    id: "homework",
    label: "作业提醒",
    name: "作业提交提醒",
    message: "根据课程安排提醒学生处理作业、测试或复习任务，语气简洁明确。",
  },
];

const SCHEDULE_PRESETS: Array<{ id: SchedulePreset; title: string; detail: string }> = [
  { id: "daily", title: "每天", detail: "适合学习提醒" },
  { id: "weekly", title: "每周", detail: "适合周复盘" },
  { id: "interval", title: "每隔一段", detail: "适合巡检" },
  { id: "once", title: "指定时间", detail: "只执行一次" },
  { id: "custom", title: "自定义", detail: "工作日/多选/每月" },
];

const CUSTOM_RULES: Array<{ id: CustomScheduleMode; title: string; detail: string }> = [
  { id: "workdays", title: "工作日", detail: "周一到周五" },
  { id: "weekdays", title: "指定星期", detail: "可多选" },
  { id: "monthly", title: "每月", detail: "固定日期" },
  { id: "cron", title: "Cron", detail: "专业规则" },
];

const WEEKDAY_OPTIONS = [
  { value: "1", label: "周一" },
  { value: "2", label: "周二" },
  { value: "3", label: "周三" },
  { value: "4", label: "周四" },
  { value: "5", label: "周五" },
  { value: "6", label: "周六" },
  { value: "0", label: "周日" },
];

const CHANNEL_OPTIONS = [
  { value: "web", label: "网页" },
  { value: "qq", label: "QQ" },
  { value: "feishu", label: "飞书" },
  { value: "wecom", label: "企业微信" },
  { value: "dingtalk", label: "钉钉" },
  { value: "telegram", label: "Telegram" },
  { value: "slack", label: "Slack" },
  { value: "discord", label: "Discord" },
  { value: "email", label: "邮箱" },
];

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
    <section className="dt-dynamic-card rounded-lg border border-line bg-white p-3 shadow-[0_1px_2px_rgba(15,15,15,0.025)]" data-testid="sparkbot-cron-panel">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line pb-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <CalendarClock size={18} className="text-brand-purple" />
            <h2 className="text-base font-semibold text-ink">提醒任务</h2>
          </div>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-500">
            选择时间、消息入口和要做的事，保存后助教会自动执行。
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

      <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(320px,380px)_minmax(0,1fr)]">
        <CronCreateForm disabled={!bot || pending} pending={pending} onCreate={onCreate} />
        <div className="min-w-0">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-ink">任务队列</h3>
            <Badge tone={bot?.running ? "success" : "neutral"}>{bot?.running ? "已就绪" : "未运行"}</Badge>
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
              <div className="dt-dynamic-empty rounded-lg border border-dashed border-line bg-canvas p-4">
                <p className="text-sm font-medium text-ink">还没有提醒任务</p>
                <p className="mt-1 text-sm leading-6 text-slate-500">
                  新建一个任务后，到点会自动执行，不需要再手动点击。
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
  const [preset, setPreset] = useState<SchedulePreset>("daily");
  const [name, setName] = useState("每日学习提醒");
  const [message, setMessage] = useState("查看最近学习记录和课程资料，给学生发一条今天最应该完成的学习提醒。");
  const [time, setTime] = useState("09:00");
  const [weekday, setWeekday] = useState("1");
  const [customMode, setCustomMode] = useState<CustomScheduleMode>("workdays");
  const [customWeekdays, setCustomWeekdays] = useState<string[]>(["1", "3", "5"]);
  const [monthDay, setMonthDay] = useState("1");
  const [intervalMinutes, setIntervalMinutes] = useState("120");
  const [cronExpr, setCronExpr] = useState("0 9 * * *");
  const [timezone, setTimezone] = useState("Asia/Shanghai");
  const [at, setAt] = useState(defaultDatetimeLocal(60));
  const [channel, setChannel] = useState("web");
  const [to, setTo] = useState("web");
  const [deliver, setDeliver] = useState(true);
  const [error, setError] = useState("");

  const applyTemplate = (template: (typeof MESSAGE_TEMPLATES)[number]) => {
    setName(template.name);
    setMessage(template.message);
    setError("");
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedMessage = message.trim();
    if (!trimmedMessage) {
      setError("任务内容不能为空。");
      return;
    }

    const target = channel === "web" ? "web" : to.trim();
    if (deliver && !target) {
      setError("请填写发送对象。");
      return;
    }

    const payloadBase = {
      name: name.trim() || trimmedMessage.slice(0, 30),
      message: trimmedMessage,
      deliver,
      channel: channel.trim() || "web",
      to: target || null,
    };

    try {
      setError("");
      await onCreate({
        ...payloadBase,
        ...buildSchedulePayload(preset, {
          time,
          weekday,
          customMode,
          customWeekdays,
          monthDay,
          intervalMinutes,
          cronExpr,
          timezone,
          at,
        }),
      });
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "保存任务失败。");
    }
  };

  return (
    <form className="grid gap-3 rounded-lg border border-line bg-canvas p-3" onSubmit={submit} data-testid="sparkbot-cron-create">
      <div className="flex items-center gap-2">
        <Plus size={16} className="text-brand-purple" />
        <h3 className="text-sm font-semibold text-ink">新建提醒</h3>
      </div>

      <div className="grid gap-2">
        <p className="text-xs font-medium leading-5 text-charcoal">提醒类型</p>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-5 lg:grid-cols-2">
          {SCHEDULE_PRESETS.map((item) => {
            const active = preset === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  setPreset(item.id);
                  setError("");
                }}
                className={`rounded-lg border px-3 py-2 text-left transition ${
                  active
                    ? "border-brand-purple-300 bg-white text-brand-purple"
                    : "border-line bg-white/70 text-slate-600 hover:border-brand-purple-300"
                }`}
                data-testid={`sparkbot-schedule-preset-${item.id}`}
              >
                <span className="block text-sm font-semibold">{item.title}</span>
                <span className="mt-1 block text-xs leading-5 text-slate-500">{item.detail}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="grid gap-2">
        <p className="text-xs font-medium leading-5 text-charcoal">常用内容</p>
        <div className="flex flex-wrap gap-2">
          {MESSAGE_TEMPLATES.map((template) => (
            <button
              key={template.id}
              type="button"
              onClick={() => applyTemplate(template)}
              className="rounded-md border border-line bg-white px-2.5 py-1 text-xs font-medium text-slate-600 hover:border-brand-purple-300 hover:text-brand-purple"
            >
              {template.label}
            </button>
          ))}
        </div>
      </div>

      <FieldShell label="任务名称">
        <TextInput value={name} onChange={(event) => setName(event.target.value)} data-testid="sparkbot-cron-name" />
      </FieldShell>

      <ScheduleFields
        preset={preset}
        time={time}
        weekday={weekday}
        customMode={customMode}
        customWeekdays={customWeekdays}
        monthDay={monthDay}
        intervalMinutes={intervalMinutes}
        cronExpr={cronExpr}
        timezone={timezone}
        at={at}
        onTimeChange={setTime}
        onWeekdayChange={setWeekday}
        onCustomModeChange={setCustomMode}
        onCustomWeekdaysChange={setCustomWeekdays}
        onMonthDayChange={setMonthDay}
        onIntervalMinutesChange={setIntervalMinutes}
        onCronExprChange={setCronExpr}
        onTimezoneChange={setTimezone}
        onAtChange={setAt}
      />

      <div className="grid gap-3 sm:grid-cols-2">
        <FieldShell label="发送到">
          <SelectInput
            value={channel}
            onChange={(event) => {
              const value = event.target.value;
              setChannel(value);
              if (value === "web") setTo("web");
              else if (to === "web") setTo("");
            }}
            data-testid="sparkbot-cron-channel"
          >
            {CHANNEL_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </SelectInput>
        </FieldShell>
        <FieldShell label="对象" hint={channel === "web" ? "网页消息" : "群号 / 用户 ID / 频道 ID"}>
          <TextInput value={to} onChange={(event) => setTo(event.target.value)} disabled={channel === "web"} data-testid="sparkbot-cron-to" />
        </FieldShell>
      </div>

      <FieldShell label="要助教做什么">
        <TextArea value={message} onChange={(event) => setMessage(event.target.value)} className="min-h-24" data-testid="sparkbot-cron-message" />
      </FieldShell>

      <label className="flex items-start gap-2 rounded-lg border border-line bg-white/70 p-3 text-sm text-slate-600">
        <input type="checkbox" checked={deliver} onChange={(event) => setDeliver(event.target.checked)} className="mt-1" />
        <span>执行后把结果发回消息入口</span>
      </label>

      {error ? <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-brand-red">{error}</p> : null}

      <Button tone="primary" type="submit" disabled={disabled || pending} data-testid="sparkbot-cron-create-submit">
        {pending ? <Loader2 size={16} className="animate-spin" /> : <BellRing size={16} />}
        保存提醒
      </Button>
    </form>
  );
}

function ScheduleFields({
  preset,
  time,
  weekday,
  customMode,
  customWeekdays,
  monthDay,
  intervalMinutes,
  cronExpr,
  timezone,
  at,
  onTimeChange,
  onWeekdayChange,
  onCustomModeChange,
  onCustomWeekdaysChange,
  onMonthDayChange,
  onIntervalMinutesChange,
  onCronExprChange,
  onTimezoneChange,
  onAtChange,
}: {
  preset: SchedulePreset;
  time: string;
  weekday: string;
  customMode: CustomScheduleMode;
  customWeekdays: string[];
  monthDay: string;
  intervalMinutes: string;
  cronExpr: string;
  timezone: string;
  at: string;
  onTimeChange: (value: string) => void;
  onWeekdayChange: (value: string) => void;
  onCustomModeChange: (value: CustomScheduleMode) => void;
  onCustomWeekdaysChange: (value: string[]) => void;
  onMonthDayChange: (value: string) => void;
  onIntervalMinutesChange: (value: string) => void;
  onCronExprChange: (value: string) => void;
  onTimezoneChange: (value: string) => void;
  onAtChange: (value: string) => void;
}) {
  if (preset === "interval") {
    return (
      <FieldShell label="间隔分钟">
        <TextInput value={intervalMinutes} onChange={(event) => onIntervalMinutesChange(event.target.value)} inputMode="numeric" data-testid="sparkbot-cron-every" />
      </FieldShell>
    );
  }

  if (preset === "once") {
    return (
      <FieldShell label="执行时间">
        <TextInput type="datetime-local" value={at} onChange={(event) => onAtChange(event.target.value)} data-testid="sparkbot-cron-at" />
      </FieldShell>
    );
  }

  if (preset === "custom") {
    return (
      <div className="grid gap-3">
        <div className="grid gap-2">
          <p className="text-xs font-medium leading-5 text-charcoal">自定义规则</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {CUSTOM_RULES.map((item) => {
              const active = customMode === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onCustomModeChange(item.id)}
                  className={`rounded-lg border px-3 py-2 text-left transition ${
                    active
                      ? "border-brand-purple-300 bg-white text-brand-purple"
                      : "border-line bg-white/70 text-slate-600 hover:border-brand-purple-300"
                  }`}
                  data-testid={`sparkbot-custom-mode-${item.id}`}
                >
                  <span className="block text-sm font-semibold">{item.title}</span>
                  <span className="mt-1 block text-xs leading-5 text-slate-500">{item.detail}</span>
                </button>
              );
            })}
          </div>
        </div>

        {customMode === "weekdays" ? (
          <WeekdayPicker selected={customWeekdays} onChange={onCustomWeekdaysChange} />
        ) : null}

        {customMode === "monthly" ? (
          <FieldShell label="每月几号" hint="1-31，遇到不存在的日期会由调度库跳过">
            <TextInput value={monthDay} onChange={(event) => onMonthDayChange(event.target.value)} inputMode="numeric" data-testid="sparkbot-cron-month-day" />
          </FieldShell>
        ) : null}

        {customMode === "cron" ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <FieldShell label="Cron 规则" hint="分 时 日 月 周">
              <TextInput value={cronExpr} onChange={(event) => onCronExprChange(event.target.value)} data-testid="sparkbot-cron-expr" />
            </FieldShell>
            <FieldShell label="时区">
              <TextInput value={timezone} onChange={(event) => onTimezoneChange(event.target.value)} data-testid="sparkbot-cron-tz" />
            </FieldShell>
          </div>
        ) : null}

        {customMode !== "cron" ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <FieldShell label="时间">
              <TextInput type="time" value={time} onChange={(event) => onTimeChange(event.target.value)} data-testid="sparkbot-cron-time" />
            </FieldShell>
            <FieldShell label="时区">
              <TextInput value={timezone} onChange={(event) => onTimezoneChange(event.target.value)} data-testid="sparkbot-cron-tz" />
            </FieldShell>
          </div>
        ) : null}

        <p className="rounded-lg border border-line bg-white/70 px-3 py-2 text-xs leading-5 text-slate-600">
          {customSchedulePreview({ customMode, customWeekdays, monthDay, time, cronExpr })}
        </p>
      </div>
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {preset === "weekly" ? (
        <FieldShell label="星期">
          <SelectInput value={weekday} onChange={(event) => onWeekdayChange(event.target.value)} data-testid="sparkbot-cron-weekday">
            {WEEKDAY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </SelectInput>
        </FieldShell>
      ) : null}
      <FieldShell label="时间">
        <TextInput type="time" value={time} onChange={(event) => onTimeChange(event.target.value)} data-testid="sparkbot-cron-time" />
      </FieldShell>
      <FieldShell label="时区">
        <TextInput value={timezone} onChange={(event) => onTimezoneChange(event.target.value)} data-testid="sparkbot-cron-tz" />
      </FieldShell>
    </div>
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
    <article className="dt-dynamic-result rounded-lg border border-line bg-white p-3" data-testid={`sparkbot-cron-job-${job.id}`}>
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
        <span>发送：{channelLabel(job.payload?.channel)} / {job.payload?.to || "web"}</span>
      </div>
      {job.state?.lastError ? <p className="mt-2 text-xs leading-5 text-brand-red">{job.state.lastError}</p> : null}
    </article>
  );
}

function WeekdayPicker({
  selected,
  onChange,
}: {
  selected: string[];
  onChange: (value: string[]) => void;
}) {
  const selectedSet = new Set(selected);
  return (
    <div className="grid gap-2">
      <p className="text-xs font-medium leading-5 text-charcoal">选择星期</p>
      <div className="grid grid-cols-4 gap-2 sm:grid-cols-7">
        {WEEKDAY_OPTIONS.map((option) => {
          const active = selectedSet.has(option.value);
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => {
                const next = active
                  ? selected.filter((value) => value !== option.value)
                  : [...selected, option.value];
                onChange(sortWeekdays(next));
              }}
              className={`rounded-lg border px-2.5 py-2 text-sm font-medium transition ${
                active
                  ? "border-brand-purple-300 bg-white text-brand-purple"
                  : "border-line bg-white/70 text-slate-600 hover:border-brand-purple-300"
              }`}
              data-testid={`sparkbot-custom-weekday-${option.value}`}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function buildSchedulePayload(
  preset: SchedulePreset,
  values: {
    time: string;
    weekday: string;
    customMode: CustomScheduleMode;
    customWeekdays: string[];
    monthDay: string;
    intervalMinutes: string;
    cronExpr: string;
    timezone: string;
    at: string;
  },
): Pick<CreateCronPayload, "kind" | "every_seconds" | "cron_expr" | "tz" | "at"> {
  if (preset === "interval") {
    const minutes = Number(values.intervalMinutes);
    if (!Number.isFinite(minutes) || minutes <= 0) throw new Error("间隔分钟必须大于 0。");
    return { kind: "every", every_seconds: Math.round(minutes * 60) };
  }

  if (preset === "once") {
    const date = new Date(values.at);
    if (!values.at || Number.isNaN(date.getTime())) throw new Error("请选择有效的执行时间。");
    return { kind: "at", at: date.toISOString() };
  }

  if (preset === "custom") {
    return {
      kind: "cron",
      cron_expr: buildCustomCronExpr(values),
      tz: values.timezone.trim() || undefined,
    };
  }

  const { hour, minute } = parseTimeParts(values.time);
  const expr = preset === "weekly" ? `${minute} ${hour} * * ${values.weekday}` : `${minute} ${hour} * * *`;
  return { kind: "cron", cron_expr: expr, tz: values.timezone.trim() || undefined };
}

function buildCustomCronExpr(values: {
  time: string;
  customMode: CustomScheduleMode;
  customWeekdays: string[];
  monthDay: string;
  cronExpr: string;
}) {
  if (values.customMode === "cron") {
    const expr = values.cronExpr.trim();
    if (!expr) throw new Error("Cron 规则不能为空。");
    return expr;
  }

  const { hour, minute } = parseTimeParts(values.time);
  if (values.customMode === "workdays") return `${minute} ${hour} * * 1-5`;
  if (values.customMode === "weekdays") {
    const days = sortWeekdays(values.customWeekdays).join(",");
    if (!days) throw new Error("请至少选择一个星期。");
    return `${minute} ${hour} * * ${days}`;
  }
  const day = Number(values.monthDay);
  if (!Number.isInteger(day) || day < 1 || day > 31) throw new Error("每月日期必须是 1 到 31。");
  return `${minute} ${hour} ${day} * *`;
}

function customSchedulePreview(values: {
  customMode: CustomScheduleMode;
  customWeekdays: string[];
  monthDay: string;
  time: string;
  cronExpr: string;
}) {
  if (values.customMode === "cron") return `将按 Cron 规则执行：${values.cronExpr.trim() || "未填写"}`;
  const timeLabel = values.time || "未选择时间";
  if (values.customMode === "workdays") return `将在每个工作日 ${timeLabel} 执行。`;
  if (values.customMode === "weekdays") {
    const labels = sortWeekdays(values.customWeekdays)
      .map((value) => WEEKDAY_OPTIONS.find((option) => option.value === value)?.label)
      .filter(Boolean)
      .join("、");
    return labels ? `将在每周 ${labels} ${timeLabel} 执行。` : "请选择至少一个星期。";
  }
  return `将在每月 ${values.monthDay || "?"} 号 ${timeLabel} 执行。`;
}

function parseTimeParts(time: string) {
  const [hourText, minuteText] = time.split(":");
  const hour = Number(hourText);
  const minute = Number(minuteText);
  if (!Number.isInteger(hour) || !Number.isInteger(minute)) throw new Error("请选择有效的时间。");
  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) throw new Error("请选择有效的时间。");
  return { hour, minute };
}

function sortWeekdays(values: string[]) {
  const order = ["1", "2", "3", "4", "5", "6", "0"];
  return Array.from(new Set(values.filter((value) => order.includes(value)))).sort(
    (a, b) => order.indexOf(a) - order.indexOf(b),
  );
}

function CronFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="dt-dynamic-metric rounded-lg border border-line bg-canvas px-3 py-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-ink">{value}</p>
    </div>
  );
}

function formatSchedule(job: SparkBotCronJob) {
  const schedule = job.schedule;
  if (schedule.kind === "every") return `每 ${formatDuration(Number(schedule.everyMs || 0))}`;
  if (schedule.kind === "cron") return `${schedule.expr || "时间规则"}${schedule.tz ? ` · ${schedule.tz}` : ""}`;
  if (schedule.kind === "at") return `一次 · ${formatTime(schedule.atMs)}`;
  return schedule.kind;
}

function formatDuration(ms: number) {
  const seconds = Math.max(1, Math.round(ms / 1000));
  if (seconds % 3600 === 0) return `${seconds / 3600} 小时`;
  if (seconds % 60 === 0) return `${seconds / 60} 分钟`;
  return `${seconds} 秒`;
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

function defaultDatetimeLocal(minutesFromNow: number) {
  const date = new Date(Date.now() + minutesFromNow * 60_000);
  const offsetMs = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16);
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

function channelLabel(value?: string | null) {
  return CHANNEL_OPTIONS.find((option) => option.value === value)?.label || value || "网页";
}
