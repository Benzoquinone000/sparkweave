import {
  useGuideV2CoursePackage,
  useGuideV2Diagnostic,
  useGuideV2LearningReport,
  useGuideV2Mutations,
  useGuideV2SessionDetail,
  useGuideV2Sessions,
  useGuideV2StudyPlan,
  useGuideV2Templates,
  useLearnerProfile,
  useLearnerProfileMutations,
  useNotebookDetail,
  useNotebooks,
} from "@/hooks/useApiQueries";

export function useGuideRuntimeData({
  forceNewSession,
  referenceNotebookId,
  selectedSessionId,
}: {
  forceNewSession: boolean;
  referenceNotebookId: string;
  selectedSessionId: string | null;
}) {
  const sessions = useGuideV2Sessions();
  const templates = useGuideV2Templates();
  const learnerProfile = useLearnerProfile();
  const learnerProfileMutations = useLearnerProfileMutations();
  const mutations = useGuideV2Mutations();
  const notebooks = useNotebooks();
  const referenceNotebook = useNotebookDetail(referenceNotebookId || null);
  const activeSessionId = forceNewSession ? null : selectedSessionId || sessions.data?.[0]?.session_id || null;
  const detail = useGuideV2SessionDetail(activeSessionId);
  const studyPlan = useGuideV2StudyPlan(activeSessionId);
  const diagnostic = useGuideV2Diagnostic(activeSessionId);
  const learningReport = useGuideV2LearningReport(activeSessionId);
  const coursePackage = useGuideV2CoursePackage(activeSessionId);

  return {
    activeSessionId,
    coursePackage,
    detail,
    diagnostic,
    learnerProfile,
    learnerProfileMutations,
    learningReport,
    mutations,
    notebooks,
    referenceNotebook,
    session: detail.data ?? null,
    sessions,
    studyPlan,
    templates,
  };
}
