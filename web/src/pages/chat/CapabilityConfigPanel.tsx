import { FieldShell, SelectInput, TextArea, TextInput } from "@/components/ui/Field";
import type { CapabilityId } from "@/lib/types";

export function CapabilityConfigPanel({
  capability,
  config,
  onChange,
  embedded = false,
}: {
  capability: CapabilityId;
  config: Record<string, unknown>;
  onChange: (value: Record<string, unknown>) => void;
  embedded?: boolean;
}) {
  const patch = (next: Record<string, unknown>) => onChange({ ...config, ...next });
  const toggleSource = (source: string) => {
    const current = Array.isArray(config.sources) ? config.sources.map(String) : [];
    patch({ sources: current.includes(source) ? current.filter((item) => item !== source) : [...current, source] });
  };

  if (capability === "chat") {
    return null;
  }

  return (
    <section className={embedded ? "pt-3" : "border-b border-line p-3"}>
      <h2 className="text-sm font-semibold text-ink">本轮设置</h2>
      <div className="mt-3 grid gap-3">
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
                className="min-h-16"
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
                  ["kb", "资料库"],
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
          <FieldShell label="图解形式">
            <SelectInput value={String(config.render_mode ?? "auto")} onChange={(event) => patch({ render_mode: event.target.value })}>
              <option value="auto">自动</option>
              <option value="svg">图形</option>
              <option value="mermaid">流程图</option>
              <option value="chartjs">数据图表</option>
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
                <SelectInput value={String(config.quality ?? "high")} onChange={(event) => patch({ quality: event.target.value })}>
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
                className="min-h-16"
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
