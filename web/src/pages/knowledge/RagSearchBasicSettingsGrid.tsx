import { FieldShell, SelectInput } from "@/components/ui/Field";

export function RagSearchBasicSettingsGrid({
  profile,
  mode,
  agentic,
  topK,
  onProfileChange,
  onModeChange,
  onAgenticChange,
  onTopKChange,
}: {
  profile: string;
  mode: string;
  agentic: string;
  topK: number;
  onProfileChange: (value: string) => void;
  onModeChange: (value: string) => void;
  onAgenticChange: (value: string) => void;
  onTopKChange: (value: number) => void;
}) {
  return (
    <div className="grid gap-3 md:grid-cols-4">
      <FieldShell label="问题侧重">
        <SelectInput value={profile} onChange={(event) => onProfileChange(event.target.value)}>
          <option value="auto">自动判断</option>
          <option value="concept">概念解释</option>
          <option value="exact">精确事实</option>
          <option value="broad">综合问题</option>
          <option value="formula">公式推导</option>
        </SelectInput>
      </FieldShell>
      <FieldShell label="匹配方式">
        <SelectInput value={mode} onChange={(event) => onModeChange(event.target.value)}>
          <option value="hybrid">关键词 + 语义</option>
          <option value="dense">语义优先</option>
        </SelectInput>
      </FieldShell>
      <FieldShell label="查找策略">
        <SelectInput value={agentic} onChange={(event) => onAgenticChange(event.target.value)}>
          <option value="auto">自动多路</option>
          <option value="force">总是拆分</option>
          <option value="off">轻量查找</option>
        </SelectInput>
      </FieldShell>
      <FieldShell label="来源数量">
        <SelectInput value={String(topK)} onChange={(event) => onTopKChange(Number(event.target.value) || 5)}>
          <option value="3">3 条</option>
          <option value="5">5 条</option>
          <option value="8">8 条</option>
          <option value="12">12 条</option>
        </SelectInput>
      </FieldShell>
    </div>
  );
}
