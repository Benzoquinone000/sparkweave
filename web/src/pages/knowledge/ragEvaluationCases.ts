import type { RagEvaluationCaseInput } from "@/lib/types";

export function buildQuickRagEvaluationCases(kbName: string): RagEvaluationCaseInput[] {
  return [
    {
      id: "quick-overview",
      kb_name: kbName,
      query_type: "concept",
      topic: "overview",
      difficulty: "basic",
      chapter: "overview",
      question: "请概括这个资料库最核心的学习主题，并给出依据。",
    },
    {
      id: "quick-keypoints",
      kb_name: kbName,
      query_type: "fact",
      topic: "keypoints",
      difficulty: "basic",
      chapter: "keypoints",
      question: "这个资料库中最重要的关键概念有哪些？",
    },
    {
      id: "quick-learning-order",
      kb_name: kbName,
      query_type: "guide",
      topic: "learning_order",
      difficulty: "intermediate",
      chapter: "learning_path",
      question: "如果我是初学者，应该按什么顺序学习这份资料？",
    },
  ];
}
