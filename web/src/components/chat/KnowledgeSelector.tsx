import { Database } from "lucide-react";

import { useKnowledgeBases } from "@/hooks/useApiQueries";

export function KnowledgeSelector({
  selected,
  onChange,
}: {
  selected: string[];
  onChange: (value: string[]) => void;
}) {
  const query = useKnowledgeBases();
  const bases = query.data ?? [];

  return (
    <div className="space-y-1.5">
      {bases.map((kb) => {
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
          >
            <Database size={15} className={active ? "text-white" : "text-steel"} />
            <span className="min-w-0 flex-1">
              <span className={`block truncate text-sm font-medium ${active ? "text-white" : "text-ink"}`}>{kb.name}</span>
              <span className={`block truncate text-xs leading-4 ${active ? "text-white/65" : "text-steel"}`}>
                {kb.is_default ? "默认知识库" : kb.status || "ready"}
              </span>
            </span>
          </button>
        );
      })}
      {!bases.length ? (
        <p className="rounded-lg border border-dashed border-line bg-white p-3 text-sm leading-6 text-slate-500">
          暂未发现知识库。你仍然可以先用普通问答或在 Knowledge 页面创建资料库。
        </p>
      ) : null}
    </div>
  );
}
