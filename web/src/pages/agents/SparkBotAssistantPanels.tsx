import { Bot, Loader2, Play, RefreshCw, Square, Trash2 } from "lucide-react";
import type { FormEvent } from "react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FieldShell, TextArea, TextInput } from "@/components/ui/Field";
import type { SparkBotSummary } from "@/lib/types";

const DEFAULT_BOT_ID = "sparkbot-assistant";
const DEFAULT_PERSONA = `# 课程助教

你是长期运行的课程助教。

工作重点：
- 结合课程资料、最近学习记录和课程资料文件处理问题。
- 面向飞书、QQ、Slack、Discord 等消息入口处理消息。
- 通过定时任务主动巡检、日报、复盘和提醒。
- 默认给出可执行结果，只在必要时解释过程。`;

type BotRailProps = {
  bots: SparkBotSummary[];
  activeBotId: string | null;
  loading: boolean;
  onSelect: (botId: string) => void;
  onOpenBots: () => void;
};

export function BotRail({ bots, activeBotId, loading, onSelect, onOpenBots }: BotRailProps) {
  return (
    <div className="rounded-lg border border-line bg-canvas p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold text-ink">当前助教</p>
        <Button tone="quiet" className="min-h-8 px-2 text-xs" onClick={onOpenBots}>
          管理
        </Button>
      </div>
      <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
        {bots.map((bot) => {
          const active = activeBotId === bot.bot_id;
          return (
            <button
              key={bot.bot_id}
              type="button"
              onClick={() => onSelect(bot.bot_id)}
              className={`min-w-[180px] rounded-lg border px-3 py-2 text-left transition ${
                active ? "border-brand-purple-300 bg-white" : "border-line bg-white/70 hover:border-brand-purple-300"
              }`}
              data-testid={`sparkbot-rail-${bot.bot_id}`}
            >
              <span className="flex items-start justify-between gap-2">
                <span className="min-w-0">
                  <span className="block truncate text-sm font-semibold text-ink">{bot.name || bot.bot_id}</span>
                  <span className="mt-1 block truncate text-xs text-slate-500">{bot.bot_id}</span>
                </span>
                <Badge tone={bot.running ? "success" : "neutral"}>{bot.running ? "在线" : "停止"}</Badge>
              </span>
            </button>
          );
        })}
        {!bots.length ? (
          <button
            type="button"
            onClick={onOpenBots}
            className="min-w-[220px] rounded-lg border border-dashed border-line bg-white px-3 py-2 text-left text-sm text-slate-500"
          >
            {loading ? "正在读取助教..." : "创建一个助教后开始配置定时提醒。"}
          </button>
        ) : null}
      </div>
    </div>
  );
}

type AssistantStatsProps = {
  bot?: SparkBotSummary;
  running: number;
  jobs: number;
  files: number;
};

export function AssistantStats({ bot, running, jobs, files }: AssistantStatsProps) {
  return (
    <div className="grid gap-2 text-sm">
      <AssistantFact label="当前助教" value={bot?.name || bot?.bot_id || "未选择"} />
      <AssistantFact label="运行状态" value={running ? `${running} 个在线` : "未启动"} />
      <AssistantFact label="提醒任务" value={`${jobs} 个`} />
      <AssistantFact label="资料文件" value={`${files} 个`} />
    </div>
  );
}

function AssistantFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-line bg-white px-3 py-2">
      <span className="block text-xs font-medium text-slate-500">{label}</span>
      <span className="mt-1 block truncate font-semibold text-ink">{value}</span>
    </div>
  );
}

export function NoBotCallout({ onCreate }: { onCreate: () => void }) {
  return (
    <section className="rounded-lg border border-dashed border-line bg-white p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-ink">还没有课程助教</h2>
          <p className="mt-1 text-sm leading-6 text-slate-500">先创建助教，再配置提醒、消息入口和资料工作区。</p>
        </div>
        <Button tone="primary" onClick={onCreate}>
          <Bot size={16} />
          创建助教
        </Button>
      </div>
    </section>
  );
}

type BotRosterProps = {
  bots: SparkBotSummary[];
  activeBotId: string | null;
  loading: boolean;
  pending: boolean;
  onRefresh: () => void;
  onSelect: (botId: string) => void;
  onStart: (botId: string) => Promise<unknown>;
  onStop: (botId: string) => Promise<unknown>;
  onDestroy: (botId: string) => Promise<unknown>;
};

export function BotRoster({
  bots,
  activeBotId,
  loading,
  pending,
  onRefresh,
  onSelect,
  onStart,
  onStop,
  onDestroy,
}: BotRosterProps) {
  return (
    <section className="rounded-lg border border-line bg-white p-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Bot size={18} className="text-brand-purple" />
          <h2 className="text-base font-semibold text-ink">课程助教</h2>
        </div>
        <Button tone="secondary" onClick={onRefresh} disabled={loading}>
          {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
          刷新
        </Button>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {bots.map((bot) => (
          <SparkBotCard
            key={bot.bot_id}
            bot={bot}
            active={activeBotId === bot.bot_id}
            pending={pending}
            onSelect={() => onSelect(bot.bot_id)}
            onStart={() => void onStart(bot.bot_id)}
            onStop={() => void onStop(bot.bot_id)}
            onDestroy={() => {
              if (window.confirm(`彻底删除助教 ${bot.bot_id}？`)) void onDestroy(bot.bot_id);
            }}
          />
        ))}
      </div>
      {!bots.length ? (
        <p className="mt-4 rounded-lg border border-dashed border-line bg-canvas p-4 text-sm leading-6 text-slate-500">
          还没有课程助教。右侧创建一个后，就可以配置提醒、消息入口和资料工作区。
        </p>
      ) : null}
    </section>
  );
}

type SparkBotCardProps = {
  bot: SparkBotSummary;
  active: boolean;
  pending: boolean;
  onSelect: () => void;
  onStart: () => void;
  onStop: () => void;
  onDestroy: () => void;
};

function SparkBotCard({ bot, active, pending, onSelect, onStart, onStop, onDestroy }: SparkBotCardProps) {
  return (
    <article className={`rounded-lg border p-3 ${active ? "border-brand-purple-300 bg-tint-lavender" : "border-line bg-white"}`} data-testid={`sparkbot-card-${bot.bot_id}`}>
      <button type="button" className="w-full text-left" onClick={onSelect}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate font-semibold text-ink">{bot.name || bot.bot_id}</p>
            <p className="mt-1 line-clamp-2 text-sm leading-6 text-slate-500">{bot.description || bot.model || "课程助教"}</p>
          </div>
          <Badge tone={bot.running ? "success" : "neutral"}>{bot.running ? "运行中" : "停止"}</Badge>
        </div>
      </button>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button tone="secondary" className="min-h-9 text-xs" onClick={onStart} disabled={bot.running || pending} data-testid={`sparkbot-start-${bot.bot_id}`}>
          <Play size={14} />
          启动
        </Button>
        <Button tone="secondary" className="min-h-9 text-xs" onClick={onStop} disabled={!bot.running || pending} data-testid={`sparkbot-stop-${bot.bot_id}`}>
          <Square size={14} />
          停止
        </Button>
        <Button tone="danger" className="min-h-9 text-xs" onClick={onDestroy} disabled={pending} data-testid={`sparkbot-destroy-${bot.bot_id}`}>
          <Trash2 size={14} />
          删除
        </Button>
      </div>
    </article>
  );
}

type CreateBotPanelProps = {
  existingBotIds: string[];
  pending: boolean;
  onCreate: (payload: { bot_id: string; name?: string; description?: string; persona?: string; auto_start?: boolean }) => Promise<SparkBotSummary>;
};

export function CreateBotPanel({ existingBotIds, pending, onCreate }: CreateBotPanelProps) {
  const suggestedBotId = useMemo(() => nextAvailableBotId(existingBotIds), [existingBotIds]);
  const [customBotId, setCustomBotId] = useState("");
  const [botIdEdited, setBotIdEdited] = useState(false);
  const [name, setName] = useState("课程助教");
  const [description, setDescription] = useState("支持课程资料、群聊消息和定时提醒的长期助教。");
  const [persona, setPersona] = useState(DEFAULT_PERSONA);
  const [autoStart, setAutoStart] = useState(true);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const botId = botIdEdited ? customBotId : suggestedBotId;
  const trimmedBotId = botId.trim();
  const idExists = Boolean(trimmedBotId && existingBotIds.includes(trimmedBotId));

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!trimmedBotId) return;
    if (idExists) {
      setSaved("");
      setError(`助教标识 "${trimmedBotId}" 已存在。请选择左侧卡片启动它，或换一个新的助教标识。`);
      return;
    }
    try {
      setError("");
      setSaved("");
      const created = await onCreate({
        bot_id: trimmedBotId,
        name: name.trim() || trimmedBotId,
        description: description.trim(),
        persona,
        auto_start: autoStart,
      });
      setSaved(`已创建 ${created.bot_id}。`);
      setBotIdEdited(false);
      setCustomBotId("");
    } catch (createError) {
      setSaved("");
      setError(createError instanceof Error ? createError.message : "创建助教失败。");
    }
  };

  return (
    <section className="rounded-lg border border-line bg-white p-3" data-testid="sparkbot-create-toggle">
      <div className="flex items-center gap-2">
        <Bot size={18} className="text-brand-purple" />
        <h2 className="text-base font-semibold text-ink">创建课程助教</h2>
      </div>
      <form className="mt-4 grid gap-3 border-t border-line pt-4" onSubmit={submit}>
        <FieldShell label="助教标识">
          <TextInput
            value={botId}
            onChange={(event) => {
              setBotIdEdited(true);
              setCustomBotId(event.target.value);
              setError("");
              setSaved("");
            }}
            data-testid="assistant-create-bot-id"
          />
        </FieldShell>
        {idExists ? (
          <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-700">
            这个助教标识已经存在。创建新助教请换一个标识；已有助教请在左侧列表直接启动或配置。
          </p>
        ) : null}
        <FieldShell label="名称">
          <TextInput value={name} onChange={(event) => setName(event.target.value)} data-testid="assistant-create-name" />
        </FieldShell>
        <FieldShell label="说明">
          <TextInput value={description} onChange={(event) => setDescription(event.target.value)} />
        </FieldShell>
        <label className="flex items-start gap-2 rounded-lg border border-line bg-canvas p-3 text-sm text-slate-600">
          <input type="checkbox" checked={autoStart} onChange={(event) => setAutoStart(event.target.checked)} className="mt-1" />
          <span>创建后立即启用</span>
        </label>
        <FieldShell label="助教设定">
          <TextArea value={persona} onChange={(event) => setPersona(event.target.value)} className="min-h-28" data-testid="assistant-create-persona" />
        </FieldShell>
        {error ? <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-brand-red">{error}</p> : null}
        {saved ? <p className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">{saved}</p> : null}
        <Button tone="primary" type="submit" disabled={pending || !trimmedBotId || idExists} data-testid="assistant-create-submit">
          {pending ? <Loader2 size={16} className="animate-spin" /> : <Bot size={16} />}
          创建
        </Button>
      </form>
    </section>
  );
}

function nextAvailableBotId(existingBotIds: string[]) {
  const existing = new Set(existingBotIds);
  if (!existing.has(DEFAULT_BOT_ID)) return DEFAULT_BOT_ID;
  let index = 2;
  while (existing.has(`${DEFAULT_BOT_ID}-${index}`)) index += 1;
  return `${DEFAULT_BOT_ID}-${index}`;
}
