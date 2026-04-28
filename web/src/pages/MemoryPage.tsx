import { AnimatePresence, motion } from "framer-motion";
import { BookOpen, Brain, Eraser, Loader2, RefreshCw, Save, UserRound } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { SelectInput, TextArea } from "@/components/ui/Field";
import { MarkdownRenderer } from "@/components/ui/MarkdownRenderer";
import { Metric } from "@/components/ui/Metric";
import { useMemory, useMemoryMutations, useSessions } from "@/hooks/useApiQueries";
import type { MemoryFile, MemorySnapshot, SessionSummary } from "@/lib/types";

const MEMORY_TABS: Array<{
  key: MemoryFile;
  label: string;
  title: string;
  hint: string;
  icon: typeof Brain;
  placeholder: string;
}> = [
  {
    key: "summary",
    label: "Summary",
    title: "学习摘要",
    hint: "沉淀最近的学习目标、进展、待解决问题，可从会话自动刷新。",
    icon: BookOpen,
    placeholder: "## 当前重点\n- \n\n## 已完成\n- \n\n## 待复盘\n- ",
  },
  {
    key: "profile",
    label: "Profile",
    title: "学习画像",
    hint: "记录用户偏好、知识水平、表达风格和长期学习习惯。",
    icon: UserRound,
    placeholder: "## 身份与目标\n- \n\n## 学习偏好\n- \n\n## 知识水平\n- ",
  },
];

function formatUpdatedAt(value: string | null | undefined) {
  if (!value) return "尚未更新";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "时间未知";
  return date.toLocaleString();
}

export function MemoryPage() {
  const memory = useMemory();
  const sessions = useSessions();
  const mutations = useMemoryMutations();
  const snapshot = memory.data ?? {
    summary: "",
    profile: "",
    summary_updated_at: null,
    profile_updated_at: null,
  };
  const snapshotKey = [
    snapshot.summary_updated_at,
    snapshot.profile_updated_at,
    snapshot.summary.length,
    snapshot.profile.length,
  ].join(":");

  return (
    <MemoryWorkspace
      key={snapshotKey}
      snapshot={snapshot}
      sessions={sessions.data ?? []}
      isLoading={memory.isLoading}
      mutations={mutations}
    />
  );
}

function MemoryWorkspace({
  snapshot,
  sessions,
  isLoading,
  mutations,
}: {
  snapshot: MemorySnapshot;
  sessions: SessionSummary[];
  isLoading: boolean;
  mutations: ReturnType<typeof useMemoryMutations>;
}) {
  const [activeFile, setActiveFile] = useState<MemoryFile>("summary");
  const [viewMode, setViewMode] = useState<"edit" | "preview">("edit");
  const [sessionId, setSessionId] = useState("");
  const [drafts, setDrafts] = useState<Record<MemoryFile, string>>({
    summary: snapshot.summary || "",
    profile: snapshot.profile || "",
  });

  const activeTab = MEMORY_TABS.find((tab) => tab.key === activeFile) ?? MEMORY_TABS[0];
  const activeContent = drafts[activeFile] ?? "";
  const savedContent = snapshot[activeFile] ?? "";
  const hasChanges = activeContent !== savedContent;
  const updatedAt = activeFile === "summary" ? snapshot.summary_updated_at : snapshot.profile_updated_at;
  const wordCount = useMemo(() => activeContent.trim().split(/\s+/).filter(Boolean).length, [activeContent]);
  const busy = mutations.save.isPending || mutations.refresh.isPending || mutations.clear.isPending;

  const save = async () => {
    await mutations.save.mutateAsync({ file: activeFile, content: activeContent });
  };

  const refresh = async () => {
    await mutations.refresh.mutateAsync({ sessionId: sessionId || null, language: "zh" });
  };

  const clear = async () => {
    if (!window.confirm(`清空 ${activeTab.title}？`)) return;
    await mutations.clear.mutateAsync(activeFile);
  };

  return (
    <div className="h-full overflow-y-auto px-4 py-4 pb-24 lg:px-5 lg:pb-5">
      <div className="mx-auto max-w-6xl space-y-4">
        <motion.section
          className="dt-page-header"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.24 }}
        >
          <p className="dt-page-eyebrow">记忆</p>
          <div className="mt-1 flex flex-wrap items-start justify-between gap-3">
            <div>
              <h1 className="text-xl font-semibold text-ink" aria-label="长期记忆与学习画像">
                学习记忆
              </h1>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-600">
                管理 Summary 与 Profile，让后续学习保留上下文。
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                tone="primary"
                onClick={() => void save()}
                disabled={!hasChanges || mutations.save.isPending}
                data-testid="memory-save"
              >
                {mutations.save.isPending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                保存
              </Button>
              <Button
                tone="secondary"
                onClick={() => void refresh()}
                disabled={mutations.refresh.isPending}
                data-testid="memory-refresh"
              >
                {mutations.refresh.isPending ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
                从会话刷新
              </Button>
              <Button
                tone="danger"
                onClick={() => void clear()}
                disabled={mutations.clear.isPending}
                data-testid="memory-clear"
              >
                {mutations.clear.isPending ? <Loader2 size={16} className="animate-spin" /> : <Eraser size={16} />}
                清空
              </Button>
            </div>
          </div>
        </motion.section>

        <motion.div
          className="flex flex-wrap gap-x-4 gap-y-1.5"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22, delay: 0.04 }}
        >
          <Metric label="当前文件" value={activeTab.label} detail={activeTab.title} icon={<Brain size={19} />} />
          <Metric label="词元草稿" value={wordCount} detail={hasChanges ? "有未保存修改" : "已同步"} />
          <Metric label="更新时间" value={formatUpdatedAt(updatedAt)} detail="学习记忆" />
        </motion.div>

        <section className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
          <aside className="rounded-lg border border-line bg-white p-3">
            <h2 className="text-base font-semibold text-ink">记忆文件</h2>
            <div className="mt-4 grid gap-2">
              {MEMORY_TABS.map((tab) => {
                const Icon = tab.icon;
                const active = tab.key === activeFile;
                return (
                  <motion.button
                    key={tab.key}
                    type="button"
                    onClick={() => setActiveFile(tab.key)}
                    layout
                    whileHover={{ y: -1 }}
                    whileTap={{ scale: 0.99 }}
                    className={`rounded-lg border p-3 text-left transition ${
                      active ? "border-teal-200 bg-teal-50" : "border-line bg-canvas hover:border-teal-200"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-white text-brand-teal">
                        <Icon size={18} />
                      </span>
                      <span className="min-w-0">
                        <span className="block font-semibold text-ink">{tab.title}</span>
                        <span className="mt-1 block text-xs text-slate-500">{tab.label}</span>
                      </span>
                    </div>
                  </motion.button>
                );
              })}
            </div>

            <div className="mt-5">
              <label className="text-sm font-medium text-ink" htmlFor="memory-session">
                刷新来源
              </label>
              <SelectInput
                id="memory-session"
                value={sessionId}
                onChange={(event) => setSessionId(event.target.value)}
                className="mt-2"
                data-testid="memory-session"
              >
                <option value="">自动选择最近会话</option>
                {sessions.map((session) => (
                  <option key={session.session_id || session.id} value={session.session_id || session.id}>
                    {session.title || session.last_message || session.session_id}
                  </option>
                ))}
              </SelectInput>
              <p className="mt-2 text-xs leading-5 text-slate-500">
                会按选定会话重建摘要；不选择时使用默认上下文。
              </p>
            </div>
          </aside>

          <section className="rounded-lg border border-line bg-white p-3">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-ink">{activeTab.title}</h2>
                <p className="mt-1 text-sm text-slate-500">{activeTab.hint}</p>
              </div>
              <div className="flex rounded-lg border border-line bg-canvas p-1">
                {(["edit", "preview"] as const).map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => setViewMode(mode)}
                    className={`min-h-8 rounded-md px-3 text-sm transition ${
                      viewMode === mode ? "bg-white text-brand-teal" : "text-slate-500 hover:text-ink"
                    }`}
                  >
                    {mode === "edit" ? "编辑" : "预览"}
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-5">
              <AnimatePresence mode="wait">
                {isLoading ? (
                  <motion.div
                    key="loading"
                    className="flex min-h-[420px] items-center justify-center rounded-lg border border-line bg-canvas text-slate-500"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.18 }}
                  >
                    <Loader2 size={20} className="animate-spin" />
                  </motion.div>
                ) : viewMode === "edit" ? (
                  <motion.div
                    key={`edit-${activeFile}`}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: 0.18 }}
                  >
                    <TextArea
                      value={activeContent}
                      onChange={(event) => setDrafts((current) => ({ ...current, [activeFile]: event.target.value }))}
                      onKeyDown={(event) => {
                        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
                          event.preventDefault();
                          void save();
                        }
                      }}
                      placeholder={activeTab.placeholder}
                      spellCheck={false}
                      className="min-h-[460px] font-mono text-sm leading-7"
                      data-testid="memory-editor"
                    />
                  </motion.div>
                ) : activeContent.trim() ? (
                  <motion.div
                    key={`preview-${activeFile}`}
                    className="markdown-body min-h-[420px] rounded-lg border border-line bg-canvas p-3"
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: 0.18 }}
                  >
                    <MarkdownRenderer>{activeContent}</MarkdownRenderer>
                  </motion.div>
                ) : (
                  <motion.div
                    key="empty"
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: 0.18 }}
                  >
                    <EmptyState icon={<Brain size={24} />} title="还没有记忆内容" description="可以从会话刷新，也可以直接手动写入 Markdown。" />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500">
              <span>{hasChanges ? "存在未保存修改" : "当前内容已保存"}</span>
              <span>{busy ? "正在处理..." : "Ctrl/Cmd + S 可快速保存"}</span>
            </div>
          </section>
        </section>
      </div>
    </div>
  );
}
