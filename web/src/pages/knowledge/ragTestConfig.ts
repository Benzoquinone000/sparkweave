export type RagTestSettings = {
  profile: string;
  mode: string;
  agentic: string;
  topK: number;
  agenticMaxContextChars: number;
  agenticMaxSources: number;
  agenticMinRelevantCoverage: number;
};

export type RagTestPreset = RagTestSettings & {
  id: "quick" | "balanced" | "deep";
  label: string;
  description: string;
};

export type RagTestPanelView = "setup" | "summary" | "agentic" | "context" | "sources";

export const RAG_TEST_PRESETS: RagTestPreset[] = [
  {
    id: "quick",
    label: "快速确认",
    description: "先看资料能否被稳定引用。",
    profile: "auto",
    mode: "hybrid",
    agentic: "off",
    topK: 5,
    agenticMaxContextChars: 3000,
    agenticMaxSources: 6,
    agenticMinRelevantCoverage: 0.5,
  },
  {
    id: "balanced",
    label: "日常问资料",
    description: "适合课件、笔记和论文问答。",
    profile: "auto",
    mode: "hybrid",
    agentic: "auto",
    topK: 5,
    agenticMaxContextChars: 5000,
    agenticMaxSources: 8,
    agenticMinRelevantCoverage: 0.67,
  },
  {
    id: "deep",
    label: "复杂问题",
    description: "自动拆分问题，再合并多路来源。",
    profile: "broad",
    mode: "hybrid",
    agentic: "force",
    topK: 8,
    agenticMaxContextChars: 8000,
    agenticMaxSources: 12,
    agenticMinRelevantCoverage: 0.8,
  },
];

export function matchRagTestPreset(settings: RagTestSettings) {
  const preset = RAG_TEST_PRESETS.find(
    (item) =>
      item.profile === settings.profile &&
      item.mode === settings.mode &&
      item.agentic === settings.agentic &&
      item.topK === settings.topK &&
      item.agenticMaxContextChars === settings.agenticMaxContextChars &&
      item.agenticMaxSources === settings.agenticMaxSources &&
      Math.abs(item.agenticMinRelevantCoverage - settings.agenticMinRelevantCoverage) < 0.001,
  );
  return preset?.id || "custom";
}

export function formatRagTestPanelTitle(view: RagTestPanelView) {
  const labels: Record<RagTestPanelView, string> = {
    setup: "先试问一次",
    summary: "查找结果",
    agentic: "来源链路",
    context: "回答材料",
    sources: "来源列表",
  };
  return labels[view];
}

export function formatRagTestPanelDescription(view: RagTestPanelView) {
  const labels: Record<RagTestPanelView, string> = {
    setup: "先输入一个真实学习问题，系统只检查能否找到来源，不生成完整回答。",
    summary: "先看来源是否够用，再进入链路、回答材料或来源页面。",
    agentic: "查看系统如何拆分问题、合并来源并补强薄弱部分。",
    context: "查看将用于回答的资料片段，判断关键来源是否真的进入回答材料。",
    sources: "逐条检查来源片段、相关度和关键词，定位资料整理或切片问题。",
  };
  return labels[view];
}
