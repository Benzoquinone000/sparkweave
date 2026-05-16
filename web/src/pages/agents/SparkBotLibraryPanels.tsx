import { Loader2, Play, Save, Square, Trash2, Wand2 } from "lucide-react";
import { motion } from "framer-motion";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FieldShell, TextArea, TextInput } from "@/components/ui/Field";
import type { SparkBotSoul, SparkBotSummary } from "@/lib/types";
import { useSparkBotSoulDetail } from "@/hooks/useApiQueries";

export function SoulLibrary({
  souls,
  pending,
  onUse,
  onCreate,
  onUpdate,
  onDelete,
}: {
  souls: SparkBotSoul[];
  pending: boolean;
  onUse: (soul: SparkBotSoul) => void;
  onCreate: (soul: SparkBotSoul) => Promise<unknown>;
  onUpdate: (soulId: string, payload: Partial<Pick<SparkBotSoul, "name" | "content">>) => Promise<unknown>;
  onDelete: (soulId: string) => Promise<unknown>;
}) {
  const [selectedSoulId, setSelectedSoulId] = useState("");
  const soulDetail = useSparkBotSoulDetail(selectedSoulId || null);
  const activeSoul = soulDetail.data ?? souls.find((soul) => soul.id === selectedSoulId);
  const [draftId, setDraftId] = useState("");
  const [draftName, setDraftName] = useState("");
  const [draftContent, setDraftContent] = useState("");
  const [draftEdited, setDraftEdited] = useState(false);

  const draftValues =
    !draftEdited && activeSoul
      ? { id: activeSoul.id, name: activeSoul.name, content: activeSoul.content }
      : { id: draftId, name: draftName, content: draftContent };

  const updateDraft = (patch: Partial<SparkBotSoul>) => {
    setDraftId(patch.id ?? draftValues.id);
    setDraftName(patch.name ?? draftValues.name);
    setDraftContent(patch.content ?? draftValues.content);
    setDraftEdited(true);
  };

  const loadSoul = (soul: SparkBotSoul) => {
    setSelectedSoulId(soul.id);
    setDraftId(soul.id);
    setDraftName(soul.name);
    setDraftContent(soul.content);
    setDraftEdited(false);
  };

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextId = draftValues.id.trim();
    const nextName = draftValues.name.trim();
    if (!nextId || !nextName || !draftValues.content.trim()) return;
    if (activeSoul && activeSoul.id === nextId) {
      await onUpdate(activeSoul.id, { name: nextName, content: draftValues.content });
    } else {
      await onCreate({ id: nextId, name: nextName, content: draftValues.content });
      setSelectedSoulId(nextId);
    }
    setDraftEdited(false);
  };

  return (
    <section className="rounded-lg border border-line bg-white p-3">
      <div className="flex flex-wrap items-start justify-between gap-3 rounded-lg bg-tint-yellow px-3 py-3" data-testid="sparkbot-soul-toggle">
        <div>
          <div className="flex items-center gap-2">
            <Wand2 size={18} className="text-brand-blue" />
            <h2 className="text-base font-semibold text-ink" aria-label="Soul 模板库">
              助教模板库
            </h2>
          </div>
          <p className="mt-1 text-sm text-slate-500">按需管理助教人格和提示模板。</p>
        </div>
        <Badge tone="neutral">{souls.length}</Badge>
      </div>
      <div className="mt-4 border-t border-line pt-4">
        <p className="text-xs text-slate-500" data-testid="sparkbot-soul-detail-source">
          {activeSoul ? soulDetail.isFetching ? "正在读取模板..." : <>已选择：{activeSoul.name}</> : "选择一个模板后可查看内容。"}
        </p>
        <div className="mt-3">
          <Button
            tone="quiet"
            type="button"
            className="min-h-8 px-2 text-xs"
            data-testid="sparkbot-soul-new"
            onClick={() => {
              setSelectedSoulId("");
              setDraftId("");
              setDraftName("");
              setDraftContent("");
              setDraftEdited(true);
            }}
          >
            新建模板
          </Button>
        </div>
        <div className="mt-4 flex max-h-40 flex-wrap gap-2 overflow-y-auto">
          {souls.map((soul) => (
            <button
              key={soul.id}
              type="button"
              data-testid={`sparkbot-soul-${soul.id}`}
              onClick={() => loadSoul(soul)}
              className={`rounded-lg border px-3 py-2 text-left text-sm ${
                selectedSoulId === soul.id ? "border-brand-purple-300 bg-tint-lavender text-brand-purple" : "border-line bg-white text-slate-600 hover:border-brand-purple-300"
              }`}
            >
              {soul.name}
            </button>
          ))}
        </div>
      </div>
      <form className="mt-4 grid gap-3 border-t border-line pt-4" onSubmit={submit}>
        <FieldShell label="模板标识">
          <TextInput value={draftValues.id} onChange={(event) => updateDraft({ id: event.target.value })} placeholder="physics-tutor" data-testid="sparkbot-soul-id" />
        </FieldShell>
        <FieldShell label="名称">
          <TextInput value={draftValues.name} onChange={(event) => updateDraft({ name: event.target.value })} placeholder="物理助教" data-testid="sparkbot-soul-name" />
        </FieldShell>
        <FieldShell label="内容">
          <TextArea value={draftValues.content} onChange={(event) => updateDraft({ content: event.target.value })} className="min-h-40" data-testid="sparkbot-soul-content" />
        </FieldShell>
        <div className="grid grid-cols-2 gap-2">
          <Button tone="secondary" type="button" onClick={() => activeSoul && onUse(activeSoul)} disabled={!activeSoul} data-testid="sparkbot-soul-use">
            套用
          </Button>
          <Button tone="primary" type="submit" disabled={pending || !draftValues.id.trim() || !draftValues.name.trim() || !draftValues.content.trim()} data-testid="sparkbot-soul-save">
            {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            保存模板
          </Button>
        </div>
        <Button
          tone="danger"
          type="button"
          data-testid="sparkbot-soul-delete"
          disabled={pending || !activeSoul}
          onClick={() => {
            if (activeSoul && window.confirm(`删除模板 ${activeSoul.name}？`)) void onDelete(activeSoul.id);
          }}
        >
          <Trash2 size={16} />
          删除模板
        </Button>
      </form>
    </section>
  );
}

export function BotCard({
  bot,
  active,
  pending,
  onSelect,
  onStart,
  onStop,
  onDestroy,
}: {
  bot: SparkBotSummary;
  active: boolean;
  pending: boolean;
  onSelect: () => void;
  onStart: () => void;
  onStop: () => void;
  onDestroy: () => void;
}) {
  return (
    <motion.div
      className={`dt-interactive rounded-lg border p-4 ${active ? "border-brand-purple-300 bg-tint-lavender" : "border-line bg-white hover:border-brand-purple-300"}`}
      data-testid={`sparkbot-card-${bot.bot_id}`}
      whileHover={{ y: -2 }}
      transition={{ duration: 0.18 }}
    >
      <button type="button" className="w-full text-left" onClick={onSelect}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate font-semibold text-ink">{bot.name || bot.bot_id}</p>
            <p className="mt-1 line-clamp-2 text-sm leading-6 text-slate-500">{bot.description || bot.model || "常驻学习助手"}</p>
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
    </motion.div>
  );
}
