import type { FormEvent } from "react";
import { Loader2, SlidersHorizontal } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FieldShell, SelectInput, TextInput } from "@/components/ui/Field";
import type { KnowledgeConfig } from "@/lib/types";

import { KNOWLEDGE_PANEL_CLASS } from "./styles";

export function KnowledgeSettingsPanel({
  activeKb,
  activeConfig,
  configFormKey,
  saving,
  onSubmit,
}: {
  activeKb: string;
  activeConfig?: KnowledgeConfig;
  configFormKey: string;
  saving: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <section className={KNOWLEDGE_PANEL_CLASS} data-testid="knowledge-settings-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-ink">资料查找设置</h2>
          <p className="mt-1 text-sm leading-6 text-slate-500">
            默认用混合查找即可；只有效果不理想时再调整。
          </p>
        </div>
        <Badge tone={activeKb ? "brand" : "neutral"}>{activeKb || "未选择"}</Badge>
      </div>

      {activeKb ? (
        <form key={configFormKey} className="mt-4 grid gap-3" onSubmit={onSubmit}>
          <div className="grid gap-3 md:grid-cols-[180px_minmax(0,1fr)]">
            <FieldShell label="模式">
              <SelectInput name="search_mode" defaultValue={String(activeConfig?.search_mode || "hybrid")}>
                <option value="hybrid">关键词 + 语义</option>
                <option value="semantic">只看语义</option>
                <option value="keyword">只看关键词</option>
              </SelectInput>
            </FieldShell>
            <FieldShell label="说明">
              <TextInput
                name="description"
                defaultValue={String(activeConfig?.description || "")}
                placeholder="例如：深度学习 CNN 与 Transformer 专题资料"
              />
            </FieldShell>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line bg-canvas p-3">
            <label className="inline-flex min-h-9 items-center gap-2 text-sm text-charcoal">
              <input
                name="needs_reindex"
                type="checkbox"
                defaultChecked={Boolean(activeConfig?.needs_reindex)}
                className="size-4 rounded border-line-strong text-brand-purple focus:ring-brand-purple"
              />
              保存后标记为需要重新整理资料
            </label>
            <Button tone="secondary" type="submit" disabled={saving || !activeKb} data-testid="knowledge-settings-submit">
              {saving ? <Loader2 size={16} className="animate-spin" /> : <SlidersHorizontal size={16} />}
              保存
            </Button>
          </div>
        </form>
      ) : (
        <p className="mt-4 rounded-lg bg-canvas p-3 text-sm text-slate-500">选择资料库后可调整查找方式。</p>
      )}
    </section>
  );
}
