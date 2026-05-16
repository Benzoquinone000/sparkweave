import {
  BookOpen,
  Bot,
  Clock3,
  FileText,
  Image as ImageIcon,
  LibraryBig,
  MessageSquareText,
  Mic,
  PenTool,
  RefreshCw,
  Search,
} from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import type {
  LearnerProfileSnapshot,
  LearningEffectNextAction,
  LearningEffectReport,
  SparkBotFile,
} from "@/lib/types";
import {
  ASSISTANT_QUICK_ACTIONS,
  assistantActionPrompt,
  assistantPromptForLearningAction,
} from "./assistantLearningFlow";
import { AssistantCollaborationRoutePanel, type AssistantCollaborationStep } from "./AssistantCollaborationRoutePanel";
import { assistantEvidenceRefs } from "./assistantEvidenceUtils";
import { AssistantEvidenceSummaryGrid, type AssistantArtifactCard, type AssistantKnowledgeSource } from "./AssistantEvidenceSummaryGrid";
import { AssistantMultimodalActionsPanel } from "./AssistantMultimodalActionsPanel";
import {
  latestAssistantReply,
  trimText,
} from "./assistantHistoryUtils";
import { ASSISTANT_MULTIMODAL_ACTIONS, useAssistantMultimodalPreview, type AssistantResourcePreviewState } from "./useAssistantMultimodalPreview";

export function AssistantEvidenceAndArtifactsPanel({
  report,
  profile,
  files,
  history,
  nextActions,
  onUsePrompt,
}: {
  report?: LearningEffectReport;
  profile?: LearnerProfileSnapshot;
  files: SparkBotFile[];
  history: Array<Record<string, unknown>>;
  nextActions: LearningEffectNextAction[];
  onUsePrompt: (prompt: string) => void;
}) {
  const source = assistantKnowledgeSource(report, files.length);
  const evidenceRefs = assistantEvidenceRefs(report);
  const artifacts = assistantArtifactCards({ report, files, history, nextActions });
  const multimodalPreview = useAssistantMultimodalPreview({ report, nextActions, onUsePrompt });
  const collaborationSteps = assistantCollaborationSteps({
    profile,
    report,
    files,
    history,
    nextActions,
    evidenceCount: evidenceRefs.length,
    preview: multimodalPreview.preview,
  });
  const readyCollaborationSteps = collaborationSteps.filter((step) => step.tone === "success" || step.tone === "brand").length;

  return (
    <section className="rounded-lg border border-line bg-white p-4 shadow-[0_12px_34px_-32px_rgba(15,15,15,0.32)]" data-testid="assistant-artifacts-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <LibraryBig size={18} className="text-brand-purple" />
            <h2 className="text-base font-semibold text-ink">资料来源与助教产物</h2>
          </div>
          <p className="mt-1 text-sm leading-6 text-slate-500">把学习依据、可交付产物和多模态生成入口放在同一个工作区里。</p>
        </div>
        <Badge tone={report?.knowledge_context?.ready ? "success" : files.length ? "warning" : "neutral"}>{source.status}</Badge>
      </div>

      <AssistantEvidenceSummaryGrid source={source} evidenceRefs={evidenceRefs} artifacts={artifacts} onUsePrompt={onUsePrompt} />

      <AssistantCollaborationRoutePanel steps={collaborationSteps} readyCount={readyCollaborationSteps} />

      <AssistantMultimodalActionsPanel
        actions={multimodalPreview.actions}
        preview={multimodalPreview.preview}
        onAction={(action) => void multimodalPreview.handleMultimodalAction(action)}
        onOcrFileChange={multimodalPreview.handleOcrFileChange}
        onSendOcrToAssistant={multimodalPreview.sendOcrToAssistant}
        onUsePrompt={onUsePrompt}
      />
    </section>
  );
}

function assistantCollaborationSteps({
  profile,
  report,
  files,
  history,
  nextActions,
  evidenceCount,
  preview,
}: {
  profile?: LearnerProfileSnapshot;
  report?: LearningEffectReport;
  files: SparkBotFile[];
  history: Array<Record<string, unknown>>;
  nextActions: LearningEffectNextAction[];
  evidenceCount: number;
  preview: AssistantResourcePreviewState;
}): AssistantCollaborationStep[] {
  const knowledgeReady = Boolean(report?.knowledge_context?.ready || report?.study_brief?.knowledge_evidence?.ready || files.length);
  const latestReply = latestAssistantReply(history);
  const eventCount = report?.summary?.event_count ?? 0;
  return [
    {
      id: "profile",
      title: "学习画像",
      detail: profile?.overview?.current_focus || profile?.next_action?.title || "等待一次学习反馈后补全画像。",
      label: profile ? "已读取" : "待建立",
      tone: profile ? "success" : "neutral",
      icon: Bot,
    },
    {
      id: "knowledge",
      title: "课程资料检索",
      detail: report?.knowledge_context?.summary || report?.study_brief?.knowledge_evidence?.summary || (files.length ? `${files.length} 个工作文件可作为上下文。` : "等待绑定课程资料。"),
      label: knowledgeReady ? "可追溯" : "待接入",
      tone: knowledgeReady ? "success" : "warning",
      icon: Search,
    },
    {
      id: "explain",
      title: "讲解智能体",
      detail: latestReply ? trimText(latestReply, 72) : "可从讲解卡或对话区生成分层讲解。",
      label: latestReply ? "已产出" : "待对话",
      tone: latestReply ? "success" : "neutral",
      icon: MessageSquareText,
    },
    {
      id: "practice",
      title: "练习智能体",
      detail: nextActions[0]?.reason || nextActions[0]?.title || "可围绕薄弱点生成短测和复测。",
      label: nextActions.length ? "已推荐" : "可生成",
      tone: nextActions.length ? "success" : "neutral",
      icon: PenTool,
    },
    {
      id: "multimodal",
      title: "讯飞多模态",
      detail: preview.message || "图解、OCR、TTS 和短视频脚本可从同一问题继续生成。",
      label: preview.status === "running" ? "生成中" : preview.status === "success" ? "已预览" : preview.status === "error" ? "待配置" : "可生成",
      tone: preview.status === "running" ? "brand" : preview.status === "success" ? "success" : preview.status === "error" ? "warning" : "neutral",
      icon: Mic,
    },
    {
      id: "effect",
      title: "评估回写",
      detail: eventCount || evidenceCount ? `${eventCount || evidenceCount} 条学习证据用于更新下一步。` : "反馈、完成动作和错因会写入学习效果评估。",
      label: eventCount || evidenceCount ? "已闭环" : "待回写",
      tone: eventCount || evidenceCount ? "success" : "neutral",
      icon: RefreshCw,
    },
  ];
}

function assistantKnowledgeSource(report: LearningEffectReport | undefined, fileCount: number): AssistantKnowledgeSource {
  const evidence = report?.study_brief?.knowledge_evidence ?? null;
  const context = report?.knowledge_context ?? null;
  const rawMetrics = evidence?.metrics ?? [];
  const metrics = rawMetrics
    .map((item) => ({
      label: item.label || "指标",
      value: item.value || "-",
    }))
    .filter((item) => item.label && item.value);
  if (!metrics.length) {
    metrics.push(
      { label: "工作文件", value: `${fileCount} 个` },
      { label: "资料库", value: context?.kb_name || "待选择" },
      { label: "状态", value: evidence?.status_label || context?.status_label || (fileCount ? "可参考笔记" : "待接入") },
    );
  }
  return {
    title: evidence?.title || (context?.kb_name ? `资料库：${context.kb_name}` : "课程资料来源"),
    status: evidence?.status_label || context?.status_label || (fileCount ? "工作区资料" : "待接入"),
    actionLabel: evidence?.action_label || context?.action_label,
    actionHref: evidence?.action_href || context?.action_href,
    summary:
      evidence?.summary ||
      context?.summary ||
      (fileCount
        ? "当前助教会优先参考工作区文件和长期笔记，回答后可继续沉淀到学习证据。"
        : "还没有可引用的资料。先上传课程资料或写入 NOTES.md，助教回答会更稳。"),
    focusQuery: evidence?.focus_query || context?.focus_query || report?.study_brief?.focus?.title || "当前学习目标",
    metrics: metrics.slice(0, 3),
  };
}

function assistantArtifactCards({
  report,
  files,
  history,
  nextActions,
}: {
  report?: LearningEffectReport;
  files: SparkBotFile[];
  history: Array<Record<string, unknown>>;
  nextActions: LearningEffectNextAction[];
}): AssistantArtifactCard[] {
  const latestAssistant = latestAssistantReply(history);
  const practiceAction = nextActions.find((action) => {
    const haystack = `${action.type} ${action.capability || ""} ${action.title}`.toLowerCase();
    return haystack.includes("question") || haystack.includes("practice") || haystack.includes("quiz") || haystack.includes("retest") || haystack.includes("练");
  });
  const notesFile = files.find((file) => file.filename.toLowerCase() === "notes.md");
  const firstFile = notesFile ?? files[0];
  const cards: AssistantArtifactCard[] = [
    {
      id: "explain-card",
      title: "讲解卡",
      detail: latestAssistant ? trimText(latestAssistant, 84) : "还没有可复用讲解。可以先让助教用课程资料讲清一个核心概念。",
      meta: latestAssistant ? "来自最近助教回答" : "可立即生成",
      prompt: latestAssistant
        ? "请把上一段助教讲解整理成一张学习讲解卡：包含概念、通俗解释、易错点、一个例子和一句复习提醒。"
        : "请基于当前课程资料生成一张学习讲解卡：包含概念、通俗解释、易错点、一个例子和一句复习提醒。",
      icon: BookOpen,
    },
    {
      id: "practice-card",
      title: practiceAction?.title || "练习卡",
      detail: practiceAction?.reason || "围绕当前薄弱点生成由易到难的小测，并把错因写回画像。",
      meta: practiceAction ? `${practiceAction.estimated_minutes || 8} 分钟` : "生成后可复盘",
      prompt: practiceAction ? assistantPromptForLearningAction(practiceAction) : ASSISTANT_QUICK_ACTIONS[1].prompt,
      icon: PenTool,
    },
    {
      id: "visual-card",
      title: "图解卡",
      detail: "把抽象概念转成结构图、流程图或知识关系图，方便演示多模态生成效果。",
      meta: "多模态草稿",
      prompt: ASSISTANT_MULTIMODAL_ACTIONS[0].prompt,
      icon: ImageIcon,
    },
    {
      id: "audio-card",
      title: "语音讲解稿",
      detail: "生成适合讯飞 TTS 合成的口语化脚本，便于移动端或课堂前复习。",
      meta: "讯飞 TTS",
      prompt: ASSISTANT_MULTIMODAL_ACTIONS[1].prompt,
      icon: Mic,
    },
  ];
  if (firstFile) {
    cards.push({
      id: "notes-card",
      title: firstFile.filename === "NOTES.md" ? "助教笔记" : "课程工作文件",
      detail: `${firstFile.filename} 可作为长期上下文，继续整理成复习提纲或答疑依据。`,
      meta: firstFile.filename,
      prompt: `请基于工作区文件 ${firstFile.filename}，整理一份本节课助教笔记：包含知识点、常见问题、需要追踪的薄弱点和下一次学习建议。`,
      icon: FileText,
    });
  } else if (report?.study_brief?.headline) {
    cards.push({
      id: "brief-card",
      title: "今日学习简报",
      detail: report.study_brief.summary || report.study_brief.headline,
      meta: `${report.study_brief.timebox_minutes || 10} 分钟`,
      prompt: assistantActionPrompt(null, report.study_brief, undefined),
      icon: Clock3,
    });
  }
  return cards.slice(0, 5);
}
