import { Badge } from "@/components/ui/Badge";
import { FieldShell, SelectInput, TextArea, TextInput } from "@/components/ui/Field";
import type { CapabilityId } from "@/lib/types";
import { isTruthyConfigFlag } from "./chatPageUtils";

export function CapabilityConfigPanel({
  capability,
  config,
  tools,
  onChange,
}: {
  capability: CapabilityId;
  config: Record<string, unknown>;
  tools: string[];
  onChange: (value: Record<string, unknown>) => void;
}) {
  const patch = (next: Record<string, unknown>) => onChange({ ...config, ...next });
  const ragEnabled = tools.includes("rag");
  const toggleSource = (source: string) => {
    const current = Array.isArray(config.sources) ? config.sources.map(String) : [];
    patch({ sources: current.includes(source) ? current.filter((item) => item !== source) : [...current, source] });
  };

  if (capability === "chat") {
    return (
      <section className="border-b border-line p-3">
        <h2 className="text-sm font-semibold text-ink">能力参数</h2>
        {ragEnabled ? (
          <div className="mt-3">
            <RagStrategyControls config={config} patch={patch} />
          </div>
        ) : (
          <p className="mt-2 text-sm leading-6 text-slate-500">即时答疑无需额外参数。</p>
        )}
      </section>
    );
  }

  return (
    <section className="border-b border-line p-3">
      <h2 className="text-sm font-semibold text-ink">能力参数</h2>
      <div className="mt-3 grid gap-3">
        {ragEnabled ? <RagStrategyControls config={config} patch={patch} /> : null}

        {capability === "deep_question" ? (
          <>
            <div className="grid grid-cols-2 gap-3">
              <FieldShell label="题目数量">
                <TextInput
                  type="number"
                  min={1}
                  max={50}
                  value={Number(config.num_questions ?? 5)}
                  onChange={(event) => patch({ num_questions: Math.max(1, Number(event.target.value) || 1) })}
                />
              </FieldShell>
              <FieldShell label="难度">
                <SelectInput value={String(config.difficulty ?? "medium")} onChange={(event) => patch({ difficulty: event.target.value })}>
                  <option value="auto">自动</option>
                  <option value="easy">基础</option>
                  <option value="medium">中等</option>
                  <option value="hard">挑战</option>
                </SelectInput>
              </FieldShell>
            </div>
            <FieldShell label="题型">
              <SelectInput value={String(config.question_type ?? "mixed")} onChange={(event) => patch({ question_type: event.target.value })}>
                <option value="mixed">混合</option>
                <option value="choice">选择题</option>
                <option value="true_false">判断题</option>
                <option value="fill_blank">填空题</option>
                <option value="written">主观题</option>
                <option value="coding">编程题</option>
              </SelectInput>
            </FieldShell>
            <FieldShell label="偏好">
              <TextArea
                value={String(config.preference ?? "")}
                onChange={(event) => patch({ preference: event.target.value })}
                placeholder="例如：偏重概念辨析，答案要有详细解析。"
                className="min-h-20"
              />
            </FieldShell>
          </>
        ) : null}

        {capability === "deep_research" ? (
          <>
            <div className="grid grid-cols-2 gap-3">
              <FieldShell label="模式">
                <SelectInput value={String(config.mode ?? "report")} onChange={(event) => patch({ mode: event.target.value })}>
                  <option value="report">报告</option>
                  <option value="notes">笔记</option>
                  <option value="brief">简报</option>
                </SelectInput>
              </FieldShell>
              <FieldShell label="深度">
                <SelectInput value={String(config.depth ?? "standard")} onChange={(event) => patch({ depth: event.target.value })}>
                  <option value="light">轻量</option>
                  <option value="standard">标准</option>
                  <option value="deep">深入</option>
                </SelectInput>
              </FieldShell>
            </div>
            <div>
              <p className="text-sm font-medium text-ink">研究来源</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {[
                  ["web", "联网"],
                  ["kb", "知识库"],
                  ["papers", "论文"],
                ].map(([value, label]) => {
                  const active = Array.isArray(config.sources) && config.sources.map(String).includes(value);
                  return (
                    <button
                      key={value}
                      type="button"
                      onClick={() => toggleSource(value)}
                      className={`rounded-md border px-2 py-1 text-xs transition ${
                        active
                          ? "border-brand-purple-300 bg-tint-lavender text-brand-purple"
                          : "border-line bg-canvas text-slate-600 hover:border-brand-purple-300"
                      }`}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            </div>
          </>
        ) : null}

        {capability === "visualize" ? (
          <FieldShell label="渲染模式">
            <SelectInput value={String(config.render_mode ?? "auto")} onChange={(event) => patch({ render_mode: event.target.value })}>
              <option value="auto">自动</option>
              <option value="svg">SVG</option>
              <option value="mermaid">Mermaid</option>
              <option value="chartjs">Chart.js</option>
            </SelectInput>
          </FieldShell>
        ) : null}

        {capability === "math_animator" ? (
          <>
            <div className="grid grid-cols-2 gap-3">
              <FieldShell label="输出">
                <SelectInput value={String(config.output_mode ?? "video")} onChange={(event) => patch({ output_mode: event.target.value })}>
                  <option value="video">视频</option>
                  <option value="image">图片</option>
                </SelectInput>
              </FieldShell>
              <FieldShell label="质量">
                <SelectInput value={String(config.quality ?? "medium")} onChange={(event) => patch({ quality: event.target.value })}>
                  <option value="low">低</option>
                  <option value="medium">中</option>
                  <option value="high">高</option>
                </SelectInput>
              </FieldShell>
            </div>
            <FieldShell label="风格提示">
              <TextArea
                value={String(config.style_hint ?? "")}
                onChange={(event) => patch({ style_hint: event.target.value })}
                placeholder="例如：干净课堂风，突出公式变形过程。"
                className="min-h-20"
              />
            </FieldShell>
          </>
        ) : null}

        {capability === "deep_solve" ? (
          <label className="flex items-center justify-between gap-3 rounded-lg border border-line bg-canvas px-3 py-2 text-sm">
            <span className="text-slate-600">输出详细解答</span>
            <input
              type="checkbox"
              checked={Boolean(config.detailed_answer ?? true)}
              onChange={(event) => patch({ detailed_answer: event.target.checked })}
            />
          </label>
        ) : null}
      </div>
    </section>
  );
}

function RagStrategyControls({
  config,
  patch,
}: {
  config: Record<string, unknown>;
  patch: (next: Record<string, unknown>) => void;
}) {
  const activePreset = matchRagStrategyPreset(config);
  const applyPreset = (presetId: RagStrategyPresetId) => {
    const preset = RAG_STRATEGY_PRESETS.find((item) => item.id === presetId);
    if (!preset) return;
    patch(preset.config);
  };

  return (
    <div className="rounded-lg border border-line bg-canvas p-3">
      <div className="flex items-start gap-2">
        <span className="mt-0.5 h-2.5 w-2.5 shrink-0 rounded-sm bg-brand-purple" />
        <div>
          <p className="text-sm font-semibold text-ink">知识库检索策略</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            选择回答前如何查资料。日常问题用轻量方案，复杂追问用多路检索，证据要求高时优先扩大依据。
          </p>
        </div>
      </div>
      <div className="mt-3 grid gap-3">
        <div className="grid gap-2">
          {RAG_STRATEGY_PRESETS.map((preset) => {
            const selected = preset.id === activePreset;
            return (
              <button
                key={preset.id}
                type="button"
                className={`rounded-lg border p-2.5 text-left transition ${
                  selected
                    ? "border-brand-purple-300 bg-tint-lavender text-brand-purple"
                    : "border-line bg-white text-slate-600 hover:border-brand-purple-300"
                }`}
                onClick={() => applyPreset(preset.id)}
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold">{preset.label}</span>
                  {selected ? <Badge tone="brand">当前</Badge> : null}
                </span>
                <span className="mt-1 block text-xs leading-5 text-slate-500">{preset.description}</span>
              </button>
            );
          })}
        </div>
        <label className="flex items-start justify-between gap-3 rounded-lg border border-line bg-white px-3 py-2 text-sm">
          <span>
            <span className="block font-semibold text-ink">回答前先取资料</span>
            <span className="mt-1 block text-xs leading-5 text-slate-500">
              发送后先检索当前资料库，再组织回答；适合从资料库预检跳过来的问题。
            </span>
          </span>
          <input
            type="checkbox"
            className="mt-1 h-4 w-4 rounded border-line text-brand-purple"
            checked={isTruthyConfigFlag(config.prefetch_rag)}
            onChange={(event) => patch({ prefetch_rag: event.target.checked ? "1" : undefined })}
          />
        </label>
        <FieldShell label="检索方式">
          <SelectInput value={String(config.agentic_rag ?? "off")} onChange={(event) => patch({ agentic_rag: event.target.value })}>
            <option value="off">快速检索</option>
            <option value="auto">自动分解</option>
            <option value="force">强制多路</option>
          </SelectInput>
        </FieldShell>
        <div className="grid grid-cols-2 gap-3">
          <FieldShell label="自动补充关键词">
            <SelectInput value={String(config.query_transform ?? "none")} onChange={(event) => patch({ query_transform: event.target.value })}>
              <option value="none">关闭</option>
              <option value="hyde">开启</option>
            </SelectInput>
          </FieldShell>
          <FieldShell label="最多拆成">
            <SelectInput
              value={String(config.agentic_max_subqueries ?? "")}
              onChange={(event) => patch({ agentic_max_subqueries: event.target.value ? Number(event.target.value) : undefined })}
            >
              <option value="">自动</option>
              <option value="2">2 路</option>
              <option value="3">3 路</option>
              <option value="4">4 路</option>
              <option value="5">5 路</option>
            </SelectInput>
          </FieldShell>
        </div>
      </div>
    </div>
  );
}

type RagStrategyPresetId = "daily" | "complex" | "evidence";

const RAG_STRATEGY_PRESETS: Array<{
  id: RagStrategyPresetId;
  label: string;
  description: string;
  config: Record<string, unknown>;
}> = [
  {
    id: "daily",
    label: "日常问答",
    description: "适合单个概念、事实或短问题，速度优先。",
    config: {
      agentic_rag: "off",
      query_transform: "none",
      agentic_max_subqueries: undefined,
      prefetch_rag: undefined,
    },
  },
  {
    id: "complex",
    label: "复杂追问",
    description: "适合一个问题里包含多个角度，系统会自动拆分检索。",
    config: {
      agentic_rag: "auto",
      query_transform: "none",
      agentic_max_subqueries: 3,
    },
  },
  {
    id: "evidence",
    label: "更强依据",
    description: "适合需要引用更稳的回答，会先取资料并补充检索关键词。",
    config: {
      agentic_rag: "auto",
      query_transform: "hyde",
      agentic_max_subqueries: 4,
      prefetch_rag: "1",
    },
  },
];

function matchRagStrategyPreset(config: Record<string, unknown>): RagStrategyPresetId | "" {
  const agentic = String(config.agentic_rag ?? "off");
  const transform = String(config.query_transform ?? "none");
  const subqueries = Number(config.agentic_max_subqueries);
  const prefetch = isTruthyConfigFlag(config.prefetch_rag);

  if (agentic === "off" && transform === "none" && !prefetch) return "daily";
  if (agentic === "auto" && transform === "none" && subqueries === 3) return "complex";
  if (agentic === "auto" && transform === "hyde" && subqueries === 4 && prefetch) return "evidence";
  return "";
}
