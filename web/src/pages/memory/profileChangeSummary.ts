import type { LearnerProfileSnapshot } from "@/lib/types";

export type ProfileChangeDetail = {
  label: string;
  previous: string;
  current: string;
  evidenceHints?: string[];
};

export type ProfileChangeSummary = {
  title: string;
  tone: "brand" | "calibration";
  items: string[];
  details: ProfileChangeDetail[];
  updatedAt: string;
};

export function profileSourceIds(item: { source_ids?: string[] | null }) {
  return Array.isArray(item.source_ids) ? item.source_ids.filter(Boolean) : [];
}

export function buildProfileChangeSummary({
  previous,
  current,
  title,
  tone,
}: {
  previous?: LearnerProfileSnapshot;
  current: LearnerProfileSnapshot;
  title: string;
  tone: "brand" | "calibration";
}): ProfileChangeSummary {
  const items: string[] = [];
  const details: ProfileChangeDetail[] = [];
  const sourceLabelById = new Map(current.sources.map((source) => [source.source_id, source.label]));
  const topEvidenceHints = current.evidence_preview
    .slice(0, 3)
    .map((item) => item.source_label || item.title)
    .filter((value, index, array): value is string => Boolean(value) && array.indexOf(value) === index);
  const previousFocus = previous?.overview.current_focus?.trim() || "";
  const currentFocus = current.overview.current_focus?.trim() || "";
  if (currentFocus && currentFocus !== previousFocus) {
    items.push(`当前学习重点调整为“${currentFocus}”。`);
    details.push({
      label: "学习重点",
      previous: previousFocus || "之前还没有明确判断",
      current: currentFocus,
      evidenceHints: topEvidenceHints.slice(0, 2),
    });
  }

  const previousWeak = new Set((previous?.learning_state.weak_points || []).map((item) => item.label));
  const currentWeakItems = current.learning_state.weak_points || [];
  const currentWeak = (current.learning_state.weak_points || []).map((item) => item.label);
  const addedWeak = currentWeak.filter((item) => item && !previousWeak.has(item));
  if (addedWeak.length) {
    const relatedWeakSources = currentWeakItems
      .filter((item) => addedWeak.includes(item.label))
      .flatMap((item) => profileSourceIds(item))
      .map((sourceId) => sourceLabelById.get(sourceId) || sourceId)
      .filter((value, index, array): value is string => Boolean(value) && array.indexOf(value) === index)
      .slice(0, 3);
    items.push(`新增关注点：${addedWeak.slice(0, 2).join("、")}。`);
    details.push({
      label: "优先补强",
      previous: Array.from(previousWeak).slice(0, 3).join("、") || "之前没有明确薄弱点",
      current: currentWeak.slice(0, 3).join("、") || "暂未形成新的薄弱点",
      evidenceHints: relatedWeakSources,
    });
  }

  const previousCalibration = Number(previous?.data_quality.calibration_count || 0);
  const currentCalibration = Number(current.data_quality.calibration_count || 0);
  if (currentCalibration > previousCalibration) {
    items.push(`画像已累计校准 ${currentCalibration} 次，后续推荐会更贴近你的真实状态。`);
    details.push({
      label: "校准参与",
      previous: `你此前一共校准了 ${previousCalibration} 次`,
      current: `现在累计校准 ${currentCalibration} 次`,
      evidenceHints: ["你的显式反馈"],
    });
  }

  const previousEvidence = Number(previous?.data_quality.evidence_count || 0);
  const currentEvidence = Number(current.data_quality.evidence_count || 0);
  if (currentEvidence > previousEvidence) {
    items.push(`画像证据从 ${previousEvidence} 条增长到 ${currentEvidence} 条。`);
    details.push({
      label: "证据规模",
      previous: `${previousEvidence} 条学习证据`,
      current: `${currentEvidence} 条学习证据`,
      evidenceHints: topEvidenceHints.slice(0, 3),
    });
  }

  const previousActionTitle = previous?.next_action?.title?.trim() || "";
  const nextActionTitle = current.next_action?.title?.trim() || "";
  if (nextActionTitle) {
    items.push(`下一步建议更新为“${nextActionTitle}”。`);
    if (nextActionTitle !== previousActionTitle) {
      details.push({
        label: "下一步建议",
        previous: previousActionTitle || "之前还没有给出明确的下一步",
        current: nextActionTitle,
        evidenceHints: [current.next_action?.source_label, current.next_action?.source_type]
          .filter((value, index, array): value is string => Boolean(value) && array.indexOf(value) === index)
          .slice(0, 2),
      });
    }
  }

  const previousSummary = previous?.overview.summary?.trim() || "";
  const currentSummary = current.overview.summary?.trim() || "";
  if (currentSummary && currentSummary !== previousSummary && details.length < 4) {
    details.push({
      label: "整体判断",
      previous: previousSummary || "之前还没有形成摘要",
      current: currentSummary,
      evidenceHints: topEvidenceHints.slice(0, 2),
    });
  }

  if (!items.length) {
    items.push("系统已重新整理画像，并保持当前判断不变。");
  }

  return {
    title,
    tone,
    items: items.slice(0, 4),
    details: details.slice(0, 4),
    updatedAt: current.generated_at || new Date().toISOString(),
  };
}
