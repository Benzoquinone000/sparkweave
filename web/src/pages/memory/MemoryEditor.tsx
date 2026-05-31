import { AnimatePresence, motion } from "framer-motion";
import { BookOpen, Brain, Eraser, Loader2, RefreshCw, Save, UserRound } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { TextArea } from "@/components/ui/Field";
import { MarkdownRenderer } from "@/components/ui/MarkdownRenderer";
import type { useMemoryMutations } from "@/hooks/useApiQueries";
import type { MemoryFile, MemorySnapshot } from "@/lib/types";
import { formatDate } from "./memoryDisplayUtils";

type MemoryMutations = ReturnType<typeof useMemoryMutations>;

const MEMORY_TABS: Array<{ key: MemoryFile; label: string; hint: string; icon: typeof Brain; placeholder: string }> = [
  {
    key: "summary",
    label: "学习摘要",
    hint: "记录最近在学什么、推进到哪里、还卡在什么地方。",
    icon: BookOpen,
    placeholder: "## 当前重点\n- \n\n## 已完成\n- \n\n## 待解决\n- ",
  },
  {
    key: "profile",
    label: "稳定偏好",
    hint: "记录长期目标、表达习惯和资源偏好。",
    icon: UserRound,
    placeholder: "## 目标\n- \n\n## 学习偏好\n- \n\n## 当前水平\n- ",
  },
];

export function MemoryEditor({
  snapshot,
  isLoading,
  mutations,
}: {
  snapshot: MemorySnapshot;
  isLoading: boolean;
  mutations: MemoryMutations;
}) {
  const [activeFile, setActiveFile] = useState<MemoryFile>("summary");
  const [viewMode, setViewMode] = useState<"edit" | "preview">("edit");
  const [drafts, setDrafts] = useState<Record<MemoryFile, string>>({
    summary: snapshot.summary || "",
    profile: snapshot.profile || "",
  });

  const activeTab = MEMORY_TABS.find((tab) => tab.key === activeFile) ?? MEMORY_TABS[0];
  const activeContent = drafts[activeFile] ?? "";
  const savedContent = snapshot[activeFile] ?? "";
  const hasChanges = activeContent !== savedContent;
  const wordCount = useMemo(() => activeContent.trim().split(/\s+/).filter(Boolean).length, [activeContent]);

  const save = async () => {
    await mutations.save.mutateAsync({ file: activeFile, content: activeContent });
  };

  const refresh = async () => {
    await mutations.refresh.mutateAsync({ sessionId: null, language: "zh" });
  };

  const clear = async () => {
    if (!window.confirm(`清空“${activeTab.label}”？`)) return;
    await mutations.clear.mutateAsync(activeFile);
  };

  return (
    <motion.section
      className="grid gap-4 lg:grid-cols-[240px_minmax(0,1fr)]"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      transition={{ duration: 0.22 }}
    >
      <aside className="dt-dynamic-card rounded-lg border border-line bg-white p-3">
        <h2 className="text-base font-semibold text-ink">手动补充</h2>
        <p className="mt-1 text-sm leading-5 text-slate-500">只在需要时补一句长期信息；日常先看概览即可。</p>
        <div className="mt-4 grid gap-2">
          {MEMORY_TABS.map((tab) => {
            const Icon = tab.icon;
            const active = tab.key === activeFile;
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveFile(tab.key)}
                className={`dt-dynamic-result rounded-lg border p-3 text-left transition ${
                  active ? "border-brand-purple-300 bg-tint-lavender text-brand-purple" : "border-line bg-canvas text-slate-600 hover:border-brand-purple-300"
                }`}
              >
                <span className="flex items-center gap-2 font-semibold">
                  <Icon size={16} />
                  {tab.label}
                </span>
                <span className="mt-1 block text-xs text-slate-500">
                  {formatDate(tab.key === "summary" ? snapshot.summary_updated_at : snapshot.profile_updated_at)}
                </span>
              </button>
            );
          })}
        </div>
      </aside>

      <section className="dt-dynamic-card rounded-lg border border-line bg-white p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-ink">{activeTab.label}</h2>
            <p className="mt-1 text-sm text-slate-500">{activeTab.hint}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button tone="secondary" onClick={() => void refresh()} disabled={mutations.refresh.isPending} data-testid="memory-refresh">
              {mutations.refresh.isPending ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
              从最近会话刷新
            </Button>
            <Button tone="primary" onClick={() => void save()} disabled={!hasChanges || mutations.save.isPending} data-testid="memory-save">
              {mutations.save.isPending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
              保存
            </Button>
            <Button tone="danger" onClick={() => void clear()} disabled={mutations.clear.isPending} data-testid="memory-clear">
              {mutations.clear.isPending ? <Loader2 size={16} className="animate-spin" /> : <Eraser size={16} />}
              清空
            </Button>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
          <span>{hasChanges ? "有未保存修改" : "已同步"}</span>
          <span>{wordCount} 个词</span>
          <div className="dt-dynamic-panel flex rounded-lg border border-line bg-canvas p-1">
            {(["edit", "preview"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => setViewMode(mode)}
                className={`min-h-8 rounded-md px-3 text-sm transition ${
                  viewMode === mode ? "bg-white text-brand-purple" : "text-slate-500 hover:text-ink"
                }`}
              >
                {mode === "edit" ? "编辑" : "预览"}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-4">
          <AnimatePresence mode="wait">
            {isLoading ? (
              <motion.div
                key="loading"
                className="dt-dynamic-empty flex min-h-[300px] items-center justify-center rounded-lg border border-line bg-canvas text-slate-500"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <Loader2 className="mr-2 animate-spin" size={18} />
                正在加载
              </motion.div>
            ) : viewMode === "edit" ? (
              <motion.div key="edit" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <TextArea
                  value={activeContent}
                  onChange={(event) => setDrafts((prev) => ({ ...prev, [activeFile]: event.target.value }))}
                  placeholder={activeTab.placeholder}
                  data-testid="memory-editor"
                  className="min-h-[300px] font-mono text-sm leading-6"
                />
              </motion.div>
            ) : (
              <motion.div
                key="preview"
                className="dt-dynamic-result min-h-[300px] rounded-lg border border-line bg-canvas p-4"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                {activeContent.trim() ? (
                  <MarkdownRenderer>{activeContent}</MarkdownRenderer>
                ) : (
                  <EmptyState
                    tone="record"
                    icon={<BookOpen size={22} />}
                    eyebrow="手动记忆"
                    title="暂无内容"
                    description="切回编辑页补充这部分内容，或从最近会话刷新一次。"
                  />
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </section>
    </motion.section>
  );
}
