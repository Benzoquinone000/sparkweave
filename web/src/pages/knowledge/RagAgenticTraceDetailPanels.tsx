import { Badge } from "@/components/ui/Badge";

import {
  formatAgenticRepairStrategy,
  readNumber,
  readString,
  toStringArray,
} from "./ragUtils";

export function AgenticRepairPanel({ repair }: { repair: Record<string, unknown> | null }) {
  if (!repair) return null;

  const repairStrategy = readString(repair, "strategy");
  const repairBranches = Array.isArray(repair.branch_repairs)
    ? repair.branch_repairs.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object" && !Array.isArray(item)))
    : [];

  return (
    <div className="mt-3 border-t border-line pt-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold text-ink">来源补强</p>
        <div className="flex flex-wrap gap-2">
          <Badge tone={repairStrategy === "single_search_fallback" ? "warning" : "success"}>
            {formatAgenticRepairStrategy(repairStrategy)}
          </Badge>
          {typeof readNumber(repair, "attempted_branches") === "number" ? (
            <Badge tone="neutral">
              尝试 {readNumber(repair, "attempted_branches")}，采纳 {readNumber(repair, "accepted_branches") ?? 0}
            </Badge>
          ) : null}
        </div>
      </div>
      {repairBranches.length ? (
        <div className="mt-2 grid gap-2 md:grid-cols-2">
          {repairBranches.slice(0, 4).map((item, index) => (
            <div key={`${readString(item, "query") || "repair"}-${index}`} className="rounded-md border border-line bg-white px-3 py-2">
              <div className="flex items-center justify-between gap-2">
                <p className="truncate text-xs font-semibold text-ink">{readString(item, "query") || `补强项 ${index + 1}`}</p>
                <Badge tone={item.accepted ? "success" : "neutral"}>{item.accepted ? "已采纳" : "未采纳"}</Badge>
              </div>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                可选来源 {String(readNumber(item, "candidate_source_count") ?? 0)} · 相关度{" "}
                {String(readNumber(item, "candidate_relevance_score") ?? "-")}
              </p>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function AgenticSubqueriesPanel({ subqueries }: { subqueries: Record<string, unknown>[] }) {
  if (!subqueries.length) return null;

  return (
    <div className="mt-3 border-t border-line pt-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold text-ink">拆分问题查找</p>
        <Badge tone="neutral">{subqueries.length} 路资料</Badge>
      </div>
      <div className="mt-2 grid gap-2 md:grid-cols-2">
        {subqueries.map((item, index) => {
          const subquery = readString(item, "query") || `拆分问题 ${index + 1}`;
          const sourceTotal = readNumber(item, "source_count") ?? 0;
          const chars = readNumber(item, "content_chars") ?? 0;
          const relevant = item.relevant === true;
          const repaired = item.repaired === true;
          return (
            <div key={`${subquery}-${index}`} className="rounded-md border border-line bg-white px-3 py-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="min-w-0 flex-1 truncate text-xs font-semibold text-ink">{subquery}</p>
                <div className="flex shrink-0 gap-1">
                  {repaired ? <Badge tone="success">已修复</Badge> : null}
                  <Badge tone={relevant ? "success" : sourceTotal ? "warning" : "neutral"}>
                    {relevant ? "相关" : sourceTotal ? "偏弱" : "无来源"}
                  </Badge>
                </div>
              </div>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                来源 {sourceTotal} · 回答材料 {chars} 字
                {readString(item, "purpose") ? ` · ${readString(item, "purpose")}` : ""}
              </p>
              {toStringArray(item.matched_terms).length ? (
                <div className="mt-2 flex flex-wrap gap-1">
                  {toStringArray(item.matched_terms).slice(0, 6).map((term) => (
                    <span key={term} className="rounded bg-tint-lavender px-1.5 py-0.5 text-[11px] font-medium text-brand-purple">
                      {term}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function AgenticContextPackSummary({
  contextPack,
  branchCount,
}: {
  contextPack: Record<string, unknown> | null;
  branchCount: number;
}) {
  if (!branchCount) return null;

  return (
    <div className="mt-3 border-t border-line pt-3 text-xs leading-5 text-slate-500">
      回答材料整理：包含 {String(readNumber(contextPack, "included_subqueries") ?? branchCount)} /{" "}
      {String(readNumber(contextPack, "subquery_count") ?? branchCount)} 个拆分问题
      {contextPack?.truncated ? "，已按上限截断。" : "，未截断。"}
    </div>
  );
}
