import type { LucideIcon } from "lucide-react";

import { Badge } from "@/components/ui/Badge";

export type AssistantKnowledgeSource = {
  title: string;
  status: string;
  summary: string;
  focusQuery: string;
  actionLabel?: string;
  actionHref?: string;
  metrics: Array<{ label: string; value: string }>;
};

export type AssistantArtifactCard = {
  id: string;
  title: string;
  detail: string;
  meta: string;
  prompt: string;
  icon: LucideIcon;
};

type AssistantEvidenceRef = {
  id: string;
  title: string;
  detail: string;
};

export function AssistantEvidenceSummaryGrid({
  source,
  evidenceRefs,
  artifacts,
  onUsePrompt,
}: {
  source: AssistantKnowledgeSource;
  evidenceRefs: AssistantEvidenceRef[];
  artifacts: AssistantArtifactCard[];
  onUsePrompt: (prompt: string) => void;
}) {
  return (
    <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="border border-line bg-[linear-gradient(135deg,#fbfaf8_0%,#fff_52%,#f8f5e8_100%)] p-3" style={{ borderRadius: 8 }} data-testid="assistant-knowledge-source">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs font-semibold text-brand-purple">资料来源</p>
            <h3 className="mt-1 truncate text-sm font-semibold text-ink">{source.title}</h3>
            <p className="mt-2 text-sm leading-6 text-slate-600">{source.summary}</p>
            {source.actionHref ? (
              <a
                href={source.actionHref}
                className="mt-3 inline-flex min-h-8 items-center rounded-md border border-line bg-white px-3 text-xs font-medium text-brand-purple transition hover:border-brand-purple-300"
              >
                {source.actionLabel || "打开资料库"}
              </a>
            ) : null}
          </div>
          <Badge tone="neutral">{source.focusQuery}</Badge>
        </div>
        <div className="mt-3 grid gap-2 sm:grid-cols-3">
          {source.metrics.map((metric) => (
            <div key={`${metric.label}-${metric.value}`} className="bg-white px-3 py-2" style={{ borderRadius: 8 }}>
              <p className="text-xs text-slate-500">{metric.label}</p>
              <p className="mt-1 truncate text-sm font-semibold text-ink">{metric.value}</p>
            </div>
          ))}
        </div>
        <div className="mt-3 border-t border-line pt-3">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs font-semibold text-ink">最近证据</p>
            <Badge tone="neutral">{evidenceRefs.length || "待建立"}</Badge>
          </div>
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            {evidenceRefs.length ? (
              evidenceRefs.slice(0, 4).map((item) => (
                <div key={item.id} className="border border-line/70 bg-white px-3 py-2" style={{ borderRadius: 8 }}>
                  <p className="truncate text-xs font-semibold text-ink">{item.title}</p>
                  <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{item.detail}</p>
                </div>
              ))
            ) : (
              <p className="text-sm leading-6 text-slate-500">完成一次练习、打开资料或反馈助教回答后，这里会显示可追溯证据。</p>
            )}
          </div>
        </div>
      </div>

      <div className="grid gap-2 content-start">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold text-brand-purple">助教产物</p>
            <h3 className="mt-1 text-sm font-semibold text-ink">可继续加工的学习材料</h3>
          </div>
          <Badge tone="neutral">{artifacts.length}</Badge>
        </div>
        {artifacts.map((artifact) => {
          const Icon = artifact.icon;
          return (
            <button
              key={artifact.id}
              type="button"
              className="dt-interactive border border-line bg-white p-3 text-left shadow-[0_1px_2px_rgba(15,15,15,0.02)] transition hover:border-brand-purple-300"
              style={{ borderRadius: 8 }}
              onClick={() => onUsePrompt(artifact.prompt)}
              data-testid={`assistant-artifact-${artifact.id}`}
            >
              <span className="flex items-start gap-3">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center border border-line bg-canvas text-brand-purple" style={{ borderRadius: 8 }}>
                  <Icon size={16} />
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-sm font-semibold text-ink">{artifact.title}</span>
                  <span className="mt-1 block line-clamp-2 text-xs leading-5 text-slate-500">{artifact.detail}</span>
                  <span className="mt-2 block text-xs font-medium text-brand-purple">{artifact.meta}</span>
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
