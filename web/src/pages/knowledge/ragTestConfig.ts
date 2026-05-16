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
    label: "快速排查",
    description: "先确认基础召回是否可用。",
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
    label: "稳妥默认",
    description: "适合日常知识库问答。",
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
    label: "深度追问",
    description: "复杂问题优先拆分检索。",
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
    setup: "提问预检",
    summary: "检索结果",
    agentic: "深度检索过程",
    context: "召回上下文",
    sources: "证据列表",
  };
  return labels[view];
}

export function formatRagTestPanelDescription(view: RagTestPanelView) {
  const labels: Record<RagTestPanelView, string> = {
    setup: "这里只检查资料库能否找到依据，不调用聊天生成。先选择方案，再查看实际召回了哪些证据。",
    summary: "这里先给出结果概览，再进入更细的过程、上下文或来源页面。",
    agentic: "查看多路检索如何拆分问题、评估质量、修复薄弱分支。",
    context: "查看最终送入模型的参考文本，判断关键证据是否真的进入回答材料。",
    sources: "逐条检查来源片段、相关度和命中关键词，定位索引或分块问题。",
  };
  return labels[view];
}
