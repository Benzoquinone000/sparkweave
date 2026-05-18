import { Badge } from "@/components/ui/Badge";
import { FieldShell, SelectInput } from "@/components/ui/Field";

import { formatAgenticMode } from "./ragUtils";

export function RagSearchAgenticSettingsPanel({
  agentic,
  agenticMaxContextChars,
  agenticMaxSources,
  agenticMinRelevantCoverage,
  onAgenticMaxContextCharsChange,
  onAgenticMaxSourcesChange,
  onAgenticMinRelevantCoverageChange,
}: {
  agentic: string;
  agenticMaxContextChars: number;
  agenticMaxSources: number;
  agenticMinRelevantCoverage: number;
  onAgenticMaxContextCharsChange: (value: number) => void;
  onAgenticMaxSourcesChange: (value: number) => void;
  onAgenticMinRelevantCoverageChange: (value: number) => void;
}) {
  return (
    <div className="rounded-lg border border-line bg-canvas p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-ink">深度检索设置</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            控制多路检索的上下文大小、来源上限和质量门槛，便于排查“资料已入库但回答找不到依据”的问题。
          </p>
        </div>
        <Badge tone={agentic === "off" ? "neutral" : agentic === "force" ? "brand" : "success"}>
          {formatAgenticMode(agentic)}
        </Badge>
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        <FieldShell label="上下文预算">
          <SelectInput
            value={String(agenticMaxContextChars)}
            onChange={(event) => onAgenticMaxContextCharsChange(Number(event.target.value) || 5000)}
          >
            <option value="1500">1500 字</option>
            <option value="3000">3000 字</option>
            <option value="5000">5000 字</option>
            <option value="8000">8000 字</option>
            <option value="12000">12000 字</option>
          </SelectInput>
        </FieldShell>
        <FieldShell label="来源上限">
          <SelectInput
            value={String(agenticMaxSources)}
            onChange={(event) => onAgenticMaxSourcesChange(Number(event.target.value) || 8)}
          >
            <option value="4">4 条</option>
            <option value="6">6 条</option>
            <option value="8">8 条</option>
            <option value="12">12 条</option>
            <option value="16">16 条</option>
          </SelectInput>
        </FieldShell>
        <FieldShell label="相关覆盖阈值">
          <SelectInput
            value={String(agenticMinRelevantCoverage)}
            onChange={(event) => onAgenticMinRelevantCoverageChange(Number(event.target.value) || 0.67)}
          >
            <option value="0.5">50%</option>
            <option value="0.67">67%</option>
            <option value="0.8">80%</option>
            <option value="1">100%</option>
          </SelectInput>
        </FieldShell>
      </div>
    </div>
  );
}
