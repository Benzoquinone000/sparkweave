import { ArrowLeft, ArrowRight } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/Button";

type GuideStepFrameProps = {
  step: number;
  total: number;
  title: string;
  subtitle?: string;
  children: ReactNode;
  previousLabel?: string;
  nextLabel?: string;
  nextDisabled?: boolean;
  onPrevious?: () => void;
  onNext?: () => void;
};

export function GuideStepFrame({
  step,
  total,
  title,
  subtitle,
  children,
  previousLabel,
  nextLabel,
  nextDisabled = false,
  onPrevious,
  onNext,
}: GuideStepFrameProps) {
  return (
    <section className="flex h-full min-h-0 flex-col rounded-lg border border-line bg-white p-4 shadow-sm sm:p-5">
      <header className="flex shrink-0 flex-wrap items-start justify-between gap-3 border-b border-line pb-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-steel">
            第 {step} 步 / 共 {total} 步
          </p>
          <h2 className="mt-1.5 text-xl font-semibold leading-tight text-ink">{title}</h2>
          {subtitle ? <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-500">{subtitle}</p> : null}
        </div>
        <div className="flex items-center gap-1.5">
          {Array.from({ length: total }, (_item, index) => (
            <span
              key={index}
              className={`h-2 rounded-lg transition-all ${
                index + 1 === step ? "w-6 bg-ink" : index + 1 < step ? "w-2 bg-brand-purple" : "w-2 bg-slate-200"
              }`}
            />
          ))}
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-hidden py-3">{children}</div>

      {(onPrevious || onNext) && (
        <footer className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-t border-line pt-3">
          {onPrevious ? (
            <Button tone="secondary" onClick={onPrevious}>
              <ArrowLeft size={16} />
              {previousLabel || "上一页"}
            </Button>
          ) : (
            <span />
          )}
          {onNext ? (
            <Button tone="primary" disabled={nextDisabled} onClick={onNext}>
              {nextLabel || "下一页"}
              <ArrowRight size={16} />
            </Button>
          ) : null}
        </footer>
      )}
    </section>
  );
}
