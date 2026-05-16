import { useState } from "react";

import type { GuideV2LearningFeedback, GuideV2ResourceType, NotebookRecord } from "@/lib/types";
import type { GuideSubPage } from "./guideLearningStrategy";

export function useGuidePageState() {
  const [goal, setGoal] = useState("");
  const [goalTouched, setGoalTouched] = useState(false);
  const [courseTemplateId, setCourseTemplateId] = useState("");
  const [level, setLevel] = useState("");
  const [horizon, setHorizon] = useState("");
  const [timeBudget, setTimeBudget] = useState("30");
  const [preferences, setPreferences] = useState<string[]>(["visual", "practice"]);
  const [weakPoints, setWeakPoints] = useState("");
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [referenceNotebookId, setReferenceNotebookId] = useState("");
  const [selectedRecordIds, setSelectedRecordIds] = useState<string[]>([]);
  const [reflection, setReflection] = useState("");
  const [score, setScore] = useState("0.85");
  const [generatingType, setGeneratingType] = useState<GuideV2ResourceType | null>(null);
  const [resourceJobId, setResourceJobId] = useState<string | null>(null);
  const [prescriptionTaskId, setPrescriptionTaskId] = useState("");
  const [saveNotebookId, setSaveNotebookId] = useState("");
  const [saveMessage, setSaveMessage] = useState("");
  const [supportOpen, setSupportOpen] = useState(false);
  const [learningFeedback, setLearningFeedback] = useState<GuideV2LearningFeedback | null>(null);
  const [prescriptionFeedback, setPrescriptionFeedback] = useState<GuideV2LearningFeedback | null>(null);
  const [guideSubPage, setGuideSubPage] = useState<GuideSubPage>("main");
  const [forceNewSession, setForceNewSession] = useState(false);
  const [sourceAction, setSourceAction] = useState<Record<string, unknown> | null>(null);

  const updateGoal = (value: string) => {
    setGoalTouched(true);
    setGoal(value);
  };

  const resetReferenceNotebook = (notebookId: string) => {
    setReferenceNotebookId(notebookId);
    setSelectedRecordIds([]);
  };

  const toggleReferenceRecord = (record: NotebookRecord) => {
    const recordId = record.record_id || record.id;
    setSelectedRecordIds((current) =>
      current.includes(recordId) ? current.filter((id) => id !== recordId) : [...current, recordId],
    );
  };

  const resetForNewRoute = () => {
    setForceNewSession(true);
    setSourceAction(null);
    setSelectedSessionId(null);
    setGuideSubPage("main");
    setSupportOpen(false);
  };

  const selectExistingRoute = (sessionId: string) => {
    setForceNewSession(false);
    setSourceAction(null);
    setSelectedSessionId(sessionId);
    setSupportOpen(false);
  };

  return {
    courseTemplateId,
    forceNewSession,
    generatingType,
    goal,
    goalTouched,
    guideSubPage,
    horizon,
    learningFeedback,
    level,
    preferences,
    prescriptionFeedback,
    prescriptionTaskId,
    referenceNotebookId,
    reflection,
    resourceJobId,
    saveMessage,
    saveNotebookId,
    score,
    selectedRecordIds,
    selectedSessionId,
    sourceAction,
    supportOpen,
    timeBudget,
    weakPoints,
    resetForNewRoute,
    resetReferenceNotebook,
    selectExistingRoute,
    setCourseTemplateId,
    setForceNewSession,
    setGeneratingType,
    setGoal,
    setGoalTouched,
    setGuideSubPage,
    setHorizon,
    setLearningFeedback,
    setLevel,
    setPreferences,
    setPrescriptionFeedback,
    setPrescriptionTaskId,
    setReflection,
    setResourceJobId,
    setSaveMessage,
    setSaveNotebookId,
    setScore,
    setSelectedSessionId,
    setSourceAction,
    setSupportOpen,
    setTimeBudget,
    setWeakPoints,
    toggleReferenceRecord,
    updateGoal,
  };
}
