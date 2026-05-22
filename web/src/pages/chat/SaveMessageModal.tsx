import { AnimatePresence, motion } from "framer-motion";
import { Loader2, Save } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FieldShell, SelectInput, TextArea, TextInput } from "@/components/ui/Field";
import type { NotebookAsset } from "@/lib/notebookAssets";
import { NOTEBOOK_LIMITS } from "@/lib/requestLimits";

export function SaveMessageModal({
  asset,
  notebooks,
  pending,
  onClose,
  onSave,
}: {
  asset: NotebookAsset;
  notebooks: Array<{ id: string; name: string }>;
  pending: boolean;
  onClose: () => void;
  onSave: (input: { notebookId: string; title: string; summary: string }) => Promise<void>;
}) {
  const [notebookId, setNotebookId] = useState(notebooks[0]?.id ?? "");
  const [title, setTitle] = useState(asset.title);
  const [summary, setSummary] = useState(asset.summary);

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/30 px-4"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        <motion.form
          className="dt-dynamic-drawer w-full max-w-xl rounded-lg border border-line bg-white p-3"
          initial={{ y: 24, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 24, opacity: 0 }}
          onSubmit={(event) => {
            event.preventDefault();
            if (notebookId) void onSave({ notebookId, title, summary });
          }}
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <Badge tone="brand">记录本</Badge>
              <h2 className="mt-3 text-lg font-semibold text-ink">保存生成结果</h2>
              <p className="mt-1 text-sm leading-6 text-slate-500">把这次回答、图表或题目沉淀到记录本，后续可用于导学和复盘。</p>
            </div>
            <Button tone="quiet" onClick={onClose}>
              关闭
            </Button>
          </div>
          <div className="dt-dynamic-result mt-5 rounded-lg border border-line bg-canvas p-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="neutral">{asset.assetKind}</Badge>
              <Badge tone="neutral">{asset.recordType}</Badge>
            </div>
            <p className="mt-3 line-clamp-4 text-sm leading-6 text-slate-600">{asset.output}</p>
          </div>
          <div className="mt-5 grid gap-4">
            <FieldShell label="目标记录本">
              <SelectInput value={notebookId} onChange={(event) => setNotebookId(event.target.value)} required>
                <option value="">请选择</option>
                {notebooks.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </SelectInput>
            </FieldShell>
            <FieldShell label="标题">
              <TextInput value={title} onChange={(event) => setTitle(event.target.value)} maxLength={NOTEBOOK_LIMITS.title} required />
            </FieldShell>
            <FieldShell label="摘要">
              <TextArea value={summary} onChange={(event) => setSummary(event.target.value)} maxLength={NOTEBOOK_LIMITS.summary} />
            </FieldShell>
          </div>
          <div className="mt-5 flex justify-end gap-3">
            <Button tone="secondary" onClick={onClose}>
              取消
            </Button>
            <Button tone="primary" type="submit" disabled={!notebookId || pending}>
              {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
              保存
            </Button>
          </div>
        </motion.form>
      </motion.div>
    </AnimatePresence>
  );
}
