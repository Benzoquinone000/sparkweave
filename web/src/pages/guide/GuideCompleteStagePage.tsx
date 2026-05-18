import { Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import type {
  GuideV2Artifact,
  GuideV2LearningFeedback,
  GuideV2LearningReport,
  GuideV2ResourceType,
  GuideV2Task,
  QuizResultItem,
} from "@/lib/types";
import { GuideLearningReportPanel } from "./GuideLearningReportPanel";
import { GuidePrescriptionFeedbackNotice } from "./GuideLearningFeedbackPanel";
import { GuideResourceArtifactPager } from "./GuideResourceArtifactPager";

export function GuideCompleteStagePage({
  highlightedSectionId,
  report,
  reportLoading,
  canSaveReport,
  savingReport,
  canExportReport,
  prescriptionFeedback,
  showPrescriptionResults,
  prescriptionTask,
  prescriptionArtifacts,
  generatingType,
  saveNotebookId,
  savingArtifact,
  quizSubmitting,
  onSaveReport,
  onExportReport,
  onOpenRouteMap,
  onOpenCoursePackage,
  onGenerateResource,
  onReviewReport,
  onOpenMemory,
  onSaveArtifact,
  onSubmitQuiz,
}: {
  highlightedSectionId: string | null;
  report: GuideV2LearningReport | null;
  reportLoading: boolean;
  canSaveReport: boolean;
  savingReport: boolean;
  canExportReport: boolean;
  prescriptionFeedback: GuideV2LearningFeedback | null;
  showPrescriptionResults: boolean;
  prescriptionTask: GuideV2Task | null;
  prescriptionArtifacts: GuideV2Artifact[];
  generatingType: GuideV2ResourceType | null;
  saveNotebookId: string;
  savingArtifact: boolean;
  quizSubmitting: boolean;
  onSaveReport: () => void;
  onExportReport: () => void;
  onOpenRouteMap: () => void;
  onOpenCoursePackage: () => void;
  onGenerateResource: (type: GuideV2ResourceType, taskId: string, prompt: string) => void;
  onReviewReport: () => void;
  onOpenMemory: () => void;
  onSaveArtifact: (artifact: GuideV2Artifact) => void;
  onSubmitQuiz: (artifact: GuideV2Artifact, answers: QuizResultItem[]) => void;
}) {
  return (
    <section
      id="guide-complete-section"
      className={`rounded-lg border bg-white p-5 shadow-sm transition-all duration-500 ${
        highlightedSectionId === "guide-complete-section"
          ? "border-brand-purple ring-2 ring-brand-purple-300"
          : "border-line"
      }`}
    >
      <Badge tone="success">路线完成</Badge>
      <h2 className="mt-3 text-xl font-semibold text-ink">你已经走完这条学习路线</h2>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">先看总结，再决定下一轮学什么。</p>
      <div className="mt-4">
        <GuideLearningReportPanel
          report={report}
          loading={reportLoading}
          canSave={canSaveReport}
          saving={savingReport}
          onSave={onSaveReport}
          canExport={canExportReport}
          onExport={onExportReport}
          onOpenRouteMap={onOpenRouteMap}
          onOpenCoursePackage={onOpenCoursePackage}
          onGenerateResource={onGenerateResource}
        />
      </div>
      {prescriptionFeedback ? (
        <GuidePrescriptionFeedbackNotice
          feedback={prescriptionFeedback}
          onReviewReport={onReviewReport}
          onOpenMemory={onOpenMemory}
        />
      ) : null}
      {showPrescriptionResults ? (
        <div
          id="guide-prescription-results-section"
          className={`mt-4 rounded-lg border bg-white p-4 transition-all duration-500 ${
            highlightedSectionId === "guide-prescription-results-section"
              ? "border-brand-purple ring-2 ring-brand-purple-300"
              : "border-line"
          }`}
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-ink">处方产物</p>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                {prescriptionTask?.title
                  ? `围绕「${prescriptionTask.title}」生成，学完后回到报告继续调整。`
                  : "围绕学习处方生成，完成后可以保存或提交。"}
              </p>
            </div>
            <Badge tone={prescriptionArtifacts.length ? "success" : "neutral"}>
              {prescriptionArtifacts.length ? `已生成 ${prescriptionArtifacts.length} 份` : "暂未开始"}
            </Badge>
          </div>
          <div className="mt-3 space-y-3">
            {generatingType && !prescriptionArtifacts.length ? (
              <div className="flex items-center gap-2 rounded-lg border border-brand-purple-300 bg-tint-lavender p-3 text-sm text-charcoal">
                <Loader2 size={16} className="animate-spin" />
                正在准备中，完成后会直接出现在这里。
              </div>
            ) : null}
            {prescriptionArtifacts.length ? (
              <GuideResourceArtifactPager
                artifacts={prescriptionArtifacts}
                saveNotebookId={saveNotebookId}
                saving={savingArtifact}
                quizSubmitting={quizSubmitting}
                onSave={onSaveArtifact}
                onSubmitQuiz={onSubmitQuiz}
                onCompleteTask={onReviewReport}
                finalLabel="回到报告"
                finalHint="看完产物后，继续按学习处方调整。"
              />
            ) : null}
          </div>
        </div>
      ) : null}
      <button
        type="button"
        className="mt-4 w-full rounded-lg border border-line bg-canvas p-4 text-left transition hover:border-brand-purple-300 hover:bg-tint-lavender"
        onClick={onOpenCoursePackage}
      >
        <span className="text-sm font-semibold text-ink">查看课程产出包</span>
        <span className="mt-1 block text-xs leading-5 text-slate-500">项目、评分标准和复习重点放在单独页面里。</span>
      </button>
    </section>
  );
}
