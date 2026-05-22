import { BookOpenCheck, Bot, Languages, SlidersHorizontal } from "lucide-react";

import { ContextReferencesPanel } from "@/components/chat/ContextReferencesPanel";
import { KnowledgeSelector } from "@/components/chat/KnowledgeSelector";
import { ToolSelector } from "@/components/chat/ToolSelector";
import {
  CAPABILITIES,
  TOOL_OPTIONS,
  capabilityLabel,
  defaultConfigForCapability,
  defaultToolsForCapability,
  getCapability,
} from "@/lib/capabilities";
import type { CapabilityId, LearnerProfileSnapshot, NotebookReference, NotebookSummary, SessionSummary } from "@/lib/types";
import { CapabilityConfigPanel } from "./CapabilityConfigPanel";
import { ProfileMiniCard } from "./ProfileMiniCard";

export function ContextPanel({
  capability,
  setCapability,
  tools,
  setTools,
  knowledgeBases,
  setKnowledgeBases,
  language,
  setLanguage,
  capabilityConfig,
  setCapabilityConfig,
  stageLabel,
  sessionId,
  turnId,
  sessions,
  notebooks,
  historyReferences,
  setHistoryReferences,
  notebookReferences,
  setNotebookReferences,
  learnerProfile,
  learnerProfileLoading,
}: {
  capability: CapabilityId;
  setCapability: (value: CapabilityId) => void;
  tools: string[];
  setTools: (value: string[]) => void;
  knowledgeBases: string[];
  setKnowledgeBases: (value: string[]) => void;
  language: "zh" | "en";
  setLanguage: (value: "zh" | "en") => void;
  capabilityConfig: Record<string, unknown>;
  setCapabilityConfig: (value: Record<string, unknown>) => void;
  stageLabel: string;
  sessionId: string | null;
  turnId: string | null;
  sessions: SessionSummary[];
  notebooks: NotebookSummary[];
  historyReferences: string[];
  setHistoryReferences: (value: string[]) => void;
  notebookReferences: NotebookReference[];
  setNotebookReferences: (value: NotebookReference[]) => void;
  learnerProfile?: LearnerProfileSnapshot;
  learnerProfileLoading: boolean;
}) {
  const readableSessionState = sessionId ? "已建立" : "发送消息后创建";
  const readableTurnState = !turnId ? "等待提问" : stageLabel === "已完成" || stageLabel === "异常" ? stageLabel : "进行中";
  const currentCapability = getCapability(capability);
  const manualCapability = capability !== "chat";
  const CurrentCapabilityIcon = manualCapability ? currentCapability.icon : Bot;
  const notebookReferenceCount = notebookReferences.reduce((total, item) => total + item.record_ids.length, 0);
  const contextReferenceCount = historyReferences.length + notebookReferenceCount;
  const applyCapability = (nextCapability: CapabilityId) => {
    setCapability(nextCapability);
    setTools(defaultToolsForCapability(nextCapability));
    setCapabilityConfig(defaultConfigForCapability(nextCapability, ""));
  };
  const selectedToolLabels = tools
    .map((tool) => TOOL_OPTIONS.find((option) => option.id === tool)?.label)
    .filter(Boolean)
    .slice(0, 3)
    .join("、");
  const toolSummary = !manualCapability ? "自动选择辅助功能" : selectedToolLabels || "未启用";

  return (
    <div className="dt-dynamic-card overflow-hidden rounded-lg border border-line bg-white">
      <ProfileMiniCard profile={learnerProfile} loading={learnerProfileLoading} />

      <div className="border-b border-line px-3 py-2">
        <a
          href="#chat-current-status"
          className="dt-interactive inline-flex min-h-8 items-center rounded-md px-2 text-xs font-medium text-slate-600 hover:bg-canvas hover:text-ink"
        >
          查看当前状态
        </a>
      </div>

      <section className="border-b border-line p-3">
        <div className="flex items-start gap-2">
          <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-canvas text-brand-blue">
            <CurrentCapabilityIcon size={16} />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-sm font-semibold text-ink">自动导学</h2>
              {manualCapability ? (
                <span className="rounded-md bg-tint-lavender px-1.5 py-0.5 text-xs font-medium text-brand-purple">
                  已指定 {capabilityLabel(capability)}
                </span>
              ) : (
                <span className="rounded-md bg-tint-sky px-1.5 py-0.5 text-xs font-medium text-brand-blue">自动</span>
              )}
            </div>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              直接描述学习目标即可。系统会自动判断是否需要查资料、深度解题、出题练习、图片/视频查找或动画生成。
            </p>
          </div>
        </div>
        <div className="dt-dynamic-panel mt-3 grid gap-1.5 rounded-lg bg-canvas px-3 py-2 text-xs leading-5 text-slate-600">
          <InfoRow label="处理方式" value={manualCapability ? "按固定流程处理" : "自动判断下一步"} />
          <InfoRow label="当前模式" value={manualCapability ? currentCapability.label : "按学习目标动态选择"} />
        </div>
      </section>

      <section className="border-b border-line p-3">
        <div className="flex items-center gap-2">
          <BookOpenCheck size={17} className="text-brand-purple" />
          <h2 className="text-sm font-semibold text-ink">资料范围</h2>
        </div>
        <p className="mt-1 text-xs leading-5 text-slate-500">选择后，本轮回答会优先引用这些资料。</p>
        <div className="mt-3">
          <KnowledgeSelector selected={knowledgeBases} onChange={setKnowledgeBases} />
        </div>
      </section>

      <ContextReferencesPanel
        sessions={sessions}
        currentSessionId={sessionId}
        notebooks={notebooks}
        historyReferences={historyReferences}
        notebookReferences={notebookReferences}
        onHistoryReferencesChange={setHistoryReferences}
        onNotebookReferencesChange={setNotebookReferences}
      />

      <section className="border-b border-line p-3">
        <div className="flex items-center gap-2">
          <Languages size={17} className="text-brand-blue" />
          <h2 className="text-sm font-semibold text-ink">回答偏好</h2>
        </div>
        <div className="mt-3 grid gap-2">
          <div className="dt-dynamic-panel flex items-center justify-between rounded-lg bg-canvas px-3 py-2 text-sm">
            <span className="text-slate-500">语言</span>
            <select
              value={language}
              onChange={(event) => setLanguage(event.target.value as "zh" | "en")}
              className="rounded-lg border border-line bg-white px-2 py-1 text-sm"
            >
              <option value="zh">中文</option>
              <option value="en">English</option>
            </select>
          </div>
          <div id="chat-current-status" className="dt-dynamic-panel rounded-lg border border-line bg-tint-sky px-3 py-2 text-sm text-slate-600">
            <div className="flex items-center justify-between gap-3">
              <span className="font-medium text-ink">当前状态</span>
              <span className="rounded-md bg-white px-2 py-0.5 text-xs text-slate-600">{stageLabel}</span>
            </div>
            <div className="mt-2 grid gap-2">
              <InfoRow label="学习会话" value={readableSessionState} />
              <InfoRow label="当前回答" value={readableTurnState} />
            </div>
          </div>
        </div>
      </section>

      <details className="group p-3" data-testid="chat-advanced-settings">
        <summary
          className="dt-interactive flex cursor-pointer list-none items-center justify-between gap-3"
          data-testid="chat-advanced-summary"
        >
          <span className="flex min-w-0 items-center gap-2">
            <SlidersHorizontal size={17} className="text-slate-500" />
            <span className="text-sm font-semibold text-ink">更多控制</span>
          </span>
          <span className="min-w-0 truncate text-xs text-slate-500">
            {toolSummary}
            {contextReferenceCount ? ` · 已引用 ${contextReferenceCount}` : ""}
          </span>
        </summary>
        <div className="mt-3 border-t border-line pt-3">
          <label className="dt-dynamic-panel flex items-center justify-between gap-3 rounded-lg bg-canvas px-3 py-2 text-sm">
            <span className="min-w-0">
              <span className="block font-medium text-ink">固定本轮流程</span>
              <span className="mt-0.5 block text-xs text-slate-500">默认保持自动，需要指定结果形态时再切换。</span>
            </span>
            <select
              aria-label="固定本轮流程"
              data-testid="chat-capability-select"
              value={capability}
              onChange={(event) => applyCapability(event.target.value as CapabilityId)}
              className="min-w-0 rounded-lg border border-line bg-white px-2 py-1 text-sm font-medium text-ink"
            >
              {CAPABILITIES.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <div className="mt-3">
            <h2 className="text-sm font-semibold text-ink">辅助功能</h2>
            <p className="mt-1 text-xs leading-5 text-slate-500">默认已按学习目标选择，需要时再手动调整。</p>
            <div className="mt-3">
              <ToolSelector selected={tools} onChange={setTools} />
            </div>
          </div>
          <CapabilityConfigPanel embedded capability={capability} config={capabilityConfig} onChange={setCapabilityConfig} />
        </div>
      </details>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="dt-dynamic-panel flex items-center justify-between gap-3 rounded-lg bg-canvas px-3 py-2 text-sm">
      <span className="text-slate-500">{label}</span>
      <span className="min-w-0 truncate font-medium text-ink">{value}</span>
    </div>
  );
}
