import { Database, Search, X } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useKnowledgeBases } from "@/hooks/useApiQueries";

export function KnowledgeSelector({
  selected,
  onChange,
}: {
  selected: string[];
  onChange: (value: string[]) => void;
}) {
  const [filter, setFilter] = useState("");
  const query = useKnowledgeBases();
  const bases = useMemo(() => query.data ?? [], [query.data]);
  const filteredBases = useMemo(() => {
    const keyword = filter.trim().toLowerCase();
    if (!keyword) return bases;
    return bases.filter((kb) => kb.name.toLowerCase().includes(keyword));
  }, [bases, filter]);
  const defaultKb = bases.find((kb) => kb.is_default)?.name ?? "";
  const selectedBases = selected.filter((name) => bases.some((kb) => kb.name === name));
  const canSearch = bases.length > 4;
  const selectDefault = () => {
    if (defaultKb) onChange([defaultKb]);
  };

  return (
    <div className="space-y-2">
      <div className="rounded-lg border border-line bg-canvas p-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="text-xs font-semibold text-ink">
              {selectedBases.length ? `已选择 ${selectedBases.length} 个资料库` : "未选择资料库"}
            </p>
            <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">
              {selectedBases.length
                ? selectedBases.join("、")
                : "未选择时，知识库工具不会检索课程资料。"}
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap gap-1.5">
            {defaultKb && !selectedBases.length ? (
              <Button tone="secondary" className="min-h-7 bg-white px-2 text-xs" type="button" onClick={selectDefault}>
                选择默认
              </Button>
            ) : null}
            {selectedBases.length ? (
              <Button tone="quiet" className="min-h-7 px-2 text-xs" type="button" onClick={() => onChange([])}>
                <X size={13} />
                清空
              </Button>
            ) : null}
          </div>
        </div>
      </div>

      {canSearch ? (
        <label className="flex min-h-9 items-center gap-2 rounded-lg border border-line bg-white px-2.5 text-sm text-steel focus-within:border-brand-purple-300">
          <Search size={15} />
          <input
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            placeholder="搜索资料库"
            className="min-w-0 flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-steel"
          />
          {filter ? (
            <button type="button" className="dt-interactive rounded-md p-1 hover:bg-surface" onClick={() => setFilter("")} aria-label="清空搜索">
              <X size={13} />
            </button>
          ) : null}
        </label>
      ) : null}

      <div className="space-y-1.5">
        {filteredBases.map((kb) => {
        const active = selected.includes(kb.name);
        return (
          <button
            key={kb.name}
            type="button"
            onClick={() =>
              onChange(active ? selected.filter((item) => item !== kb.name) : [...selected, kb.name])
            }
            className={`dt-interactive flex min-h-10 w-full items-center gap-2 rounded-lg border px-2.5 py-2 text-left ${
              active ? "border-ink bg-ink text-white" : "border-line bg-white hover:border-brand-purple"
            }`}
            data-testid={`knowledge-selector-${kb.name}`}
          >
            <Database size={15} className={active ? "text-white" : "text-steel"} />
            <span className="min-w-0 flex-1">
              <span className="flex min-w-0 items-center gap-2">
                <span className={`min-w-0 flex-1 truncate text-sm font-medium ${active ? "text-white" : "text-ink"}`}>{kb.name}</span>
                {kb.is_default ? <Badge tone={active ? "neutral" : "brand"}>默认</Badge> : null}
              </span>
              <span className={`mt-1 block truncate text-xs leading-4 ${active ? "text-white/65" : "text-steel"}`}>
                {formatKnowledgeBaseStatus(kb.status)} · {formatKnowledgeBaseCount(kb.document_count, "文档")}
              </span>
            </span>
          </button>
        );
      })}
        {bases.length && !filteredBases.length ? (
          <p className="rounded-lg border border-dashed border-line bg-white p-3 text-xs leading-5 text-slate-500">
            没有匹配的资料库，换个关键词试试。
          </p>
        ) : null}
      </div>
      {!bases.length ? (
        <div className="rounded-lg border border-dashed border-line bg-white p-3 text-sm leading-6 text-slate-500">
          <p>暂未发现资料库。你仍然可以先用普通问答，或去资料库页面导入课程资料。</p>
          <a
            href="/knowledge"
            className="dt-interactive mt-2 inline-flex min-h-8 items-center rounded-lg border border-line px-2.5 text-xs font-medium text-ink hover:border-brand-purple-300"
          >
            打开资料库
          </a>
        </div>
      ) : null}
    </div>
  );
}

function formatKnowledgeBaseStatus(status: string | undefined) {
  const value = String(status || "ready").toLowerCase();
  if (value === "ready") return "可使用";
  if (value === "loading") return "读取中";
  if (value === "error" || value === "failed") return "异常";
  return status || "可使用";
}

function formatKnowledgeBaseCount(value: number | string | undefined, unit: string) {
  if (typeof value === "number" && Number.isFinite(value)) return `${value} ${unit}`;
  if (typeof value === "string" && value.trim()) return `${value} ${unit}`;
  return `- ${unit}`;
}
