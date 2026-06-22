import { Download, Loader2, Save, Trophy } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import type {
  GuideV2Artifact,
  GuideV2LearningFeedback,
  GuideV2LearningReport,
  GuideV2ResourceType,
  GuideV2Task,
  QuizResultItem,
} from "@/lib/types";
import { GuideResourceArtifactPager } from "./GuideResourceArtifactPager";

export function GuideCompleteStagePage({
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
  const overview = report?.overview;
  const score = typeof overview?.overall_score === "number" ? Math.round(overview.overall_score) : null;
  const progress = typeof overview?.progress === "number" ? Math.round(overview.progress * 100) : null;

  return (
    <section id="guide-complete-section" className="flex h-full min-h-0 flex-col gap-3">
      <div className="shrink-0 rounded-lg border border-line bg-white p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Trophy size={18} className="text-brand-purple" />
          <Badge tone="success">路线完成</Badge>
          {score !== null ? <Badge tone="brand">{score} 分</Badge> : null}
          {progress !== null ? <Badge tone="neutral">{progress}% 进度</Badge> : null}
        </div>
        <h3 className="mt-3 line-clamp-2 text-xl font-semibold text-ink">{report?.title || "学习报告"}</h3>
        <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-600">
          {reportLoading ? "正在整理学习报告..." : report?.summary || "这一轮学习已经结束，可以保存报告或查看课程成果。"}
        </p>
      </div>

      {prescriptionFeedback ? (
        <div className="shrink-0 rounded-lg border border-emerald-200 bg-emerald-50 p-3">
          <p className="line-clamp-1 text-sm font-semibold text-ink">{prescriptionFeedback.title || "处方练习已回写"}</p>
          <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-600">
            {prescriptionFeedback.summary || "系统已根据处方练习更新学习报告和学习记录。"}
          </p>
        </div>
      ) : null}

      <div className="min-h-0 flex-1 rounded-lg border border-line bg-canvas p-3">
        {showPrescriptionResults && prescriptionArtifacts.length ? (
          <GuideResourceArtifactPager
            artifacts={prescriptionArtifacts}
            saveNotebookId={saveNotebookId}
            saving={savingArtifact}
            quizSubmitting={quizSubmitting}
            compact
            onSave={onSaveArtifact}
            onSubmitQuiz={onSubmitQuiz}
            onCompleteTask={onReviewReport}
            finalLabel="回到报告"
            finalHint="看完产物后，继续按学习处方调整。"
          />
        ) : (
          <div className="grid h-full place-items-center text-center">
            <div>
              {generatingType ? <Loader2 size={24} className="mx-auto animate-spin text-brand-purple" /> : <Trophy size={26} className="mx-auto text-brand-purple" />}
              <p className="mt-3 text-sm font-semibold text-ink">
                {prescriptionTask?.title || (generatingType ? "正在准备处方产物" : "这一轮可以收尾了")}
              </p>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                {generatingType ? "完成后会出现在这里。" : "报告、路线和课程成果都可以单独查看。"}
              </p>
            </div>
          </div>
        )}
      </div>

      <div className="grid shrink-0 gap-2 sm:grid-cols-4">
        <Button tone="secondary" disabled={!canSaveReport || savingReport} onClick={onSaveReport}>
          {savingReport ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
          保存
        </Button>
        <Button tone="secondary" disabled={!canExportReport} onClick={onExportReport}>
          <Download size={16} />
          导出
        </Button>
        <Button tone="secondary" onClick={onOpenRouteMap}>
          看路线
        </Button>
        <Button tone="primary" onClick={onOpenCoursePackage}>
          课程成果
        </Button>
      </div>

      <button type="button" className="sr-only" onClick={onOpenMemory}>
        查看记录
      </button>
    </section>
  );
}
