import { BarChart3, GraduationCap, ListChecks, Video } from "lucide-react";

import { LazyExternalVideoViewer, LazyMathAnimatorViewer } from "@/components/results/LazyMediaResultViewers";
import { LazyVisualizationViewer } from "@/components/results/LazyVisualizationViewer";
import { MarkdownRenderer } from "@/components/ui/MarkdownRenderer";
import type { NotebookRecord } from "@/lib/types";
import type { RecordAsset } from "./recordAssetUtils";

export function RecordAssetPreview({ record, asset }: { record: NotebookRecord; asset: RecordAsset }) {
  if (asset.visualize) {
    return (
      <div className="mt-4 border-t border-line pt-4">
        <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
          <BarChart3 size={16} className="text-brand-blue" />
          可视化资产预览
        </h4>
        <LazyVisualizationViewer result={asset.visualize} />
      </div>
    );
  }

  if (asset.quizQuestions.length) {
    return (
      <div className="mt-4 border-t border-line pt-4">
        <h4 className="flex items-center gap-2 text-sm font-semibold text-ink">
          <ListChecks size={16} className="text-brand-purple" />
          题目资产预览
        </h4>
        <div className="mt-3 grid gap-3">
          {asset.quizQuestions.map((question, index) => (
            <div key={`${question.question_id ?? index}-${question.question}`} className="rounded-lg bg-canvas p-3">
              <p className="text-sm font-semibold leading-6 text-ink">
                {index + 1}. {question.question}
              </p>
              {question.options && Object.keys(question.options).length ? (
                <div className="mt-2 grid gap-1">
                  {Object.entries(question.options).map(([key, value]) => (
                    <p key={key} className="text-sm leading-6 text-slate-600">
                      <span className="font-semibold text-brand-purple">{key}.</span> {value}
                    </p>
                  ))}
                </div>
              ) : null}
              <p className="mt-2 text-sm leading-6 text-slate-600">
                <span className="font-semibold text-ink">参考答案：</span>
                {question.correct_answer || "未提供"}
              </p>
              {question.explanation ? <p className="mt-1 text-sm leading-6 text-slate-500">{question.explanation}</p> : null}
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (asset.mathAnimator) {
    return (
      <div className="mt-4 border-t border-line pt-4">
        <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
          <Video size={16} className="text-brand-blue" />
          数学动画资产预览
        </h4>
        <LazyMathAnimatorViewer result={asset.mathAnimator} />
      </div>
    );
  }

  if (asset.externalVideo) {
    return (
      <div className="mt-4 border-t border-line pt-4">
        <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
          <Video size={16} className="text-brand-blue" />
          精选视频资产预览
        </h4>
        <LazyExternalVideoViewer result={asset.externalVideo} />
      </div>
    );
  }

  if (asset.guideHtml) {
    return (
      <div className="mt-4 border-t border-line pt-4">
        <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
          <GraduationCap size={16} className="text-brand-purple" />
          导学页面预览
        </h4>
        <div className="h-72 overflow-hidden rounded-lg border border-line bg-canvas">
          <iframe
            title={`${record.title} 导学页面`}
            data-testid="guide-asset-preview"
            srcDoc={asset.guideHtml}
            sandbox=""
            className="h-full w-full bg-white"
          />
        </div>
      </div>
    );
  }

  if (record.output) {
    return (
      <div className="markdown-body mt-4 border-t border-line pt-4 text-sm leading-6 text-slate-700">
        <MarkdownRenderer>{record.output}</MarkdownRenderer>
      </div>
    );
  }

  return null;
}
