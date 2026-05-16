import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { TextArea } from "@/components/ui/Field";
import type { LearnerMastery, LearnerWeakPoint } from "@/lib/types";
import { formatPercent } from "./memoryDisplayUtils";
import { buildGuidePromptHref } from "./profileGuideLinks";
import { profileSourceIds } from "./profileChangeSummary";
import type { CalibrateProfile } from "./profileTypes";

export function WeakPointItem({
  item,
  onCalibrate,
  calibrating,
}: {
  item: LearnerWeakPoint;
  onCalibrate: CalibrateProfile;
  calibrating: boolean;
}) {
  const confidence = Math.max(0, Math.min(1, item.confidence || 0));
  const actionCopy =
    item.severity === "high"
      ? "先别急着往后学，建议先用一个图解或 3 道小题把这里补清。"
      : "这块可以边学边补，遇到卡顿时优先回来验证。";
  const guideHref = buildGuidePromptHref({
    prompt: `用 10 分钟帮我补齐「${item.label}」，先给一个直观解释，再给 3 道小练习验证。`,
    title: `补齐：${item.label}`,
    sourceType: "weak_point",
    sourceLabel: item.label,
    actionKind: "weak_point",
    minutes: 10,
    confidence,
  });
  return (
    <div className="rounded-lg border border-line bg-white p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold text-ink">{item.label}</h3>
        <span className={`rounded-md px-2 py-1 text-xs ${item.severity === "high" ? "bg-red-50 text-brand-red" : "bg-white text-slate-500"}`}>
          {item.severity === "high" ? "高优先级" : "待补强"}
        </span>
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-700">{item.reason || actionCopy}</p>
      <div className="mt-3 rounded-md border border-red-100 bg-red-50 px-3 py-2 text-xs leading-5 text-brand-red">
        {actionCopy}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
        <span>判断依据 {formatPercent(confidence)}</span>
        {item.evidence_count ? <span>{item.evidence_count} 条证据</span> : null}
      </div>
      <a
        href={guideHref}
        className="dt-interactive mt-3 inline-flex min-h-9 items-center justify-center gap-2 rounded-md border border-brand-purple bg-brand-purple px-3 text-xs font-medium text-white hover:bg-brand-purple-800"
      >
        去补这个
        <ArrowRight size={14} />
      </a>
      <CalibrationActions claimType="weak_point" value={item.label} sourceId={profileSourceIds(item)[0] || ""} onCalibrate={onCalibrate} calibrating={calibrating} />
    </div>
  );
}

export function MasteryItem({
  item,
  onCalibrate,
  calibrating,
}: {
  item: LearnerMastery;
  onCalibrate: CalibrateProfile;
  calibrating: boolean;
}) {
  const score = item.score ?? 0;
  const boundedScore = Math.max(0, Math.min(1, score));
  const copy =
    boundedScore >= 0.8
      ? "这块已经比较稳，可以继续推进，但偶尔做一道题保持手感。"
      : boundedScore >= 0.55
        ? "这块有基础，但还不够稳，建议用短练习再确认一次。"
        : "这块还需要补底层概念，先别直接上复杂任务。";
  const toneClass = boundedScore >= 0.8 ? "bg-emerald-500" : boundedScore >= 0.55 ? "bg-brand-purple" : "bg-amber-500";
  const guideHref = buildGuidePromptHref({
    prompt:
      boundedScore >= 0.8
        ? `围绕「${item.title}」出 3 道稍有挑战的题，帮我确认是否真的掌握。`
        : `帮我用 10 分钟巩固「${item.title}」，先快速复习关键概念，再做 3 道短练习。`,
    title: boundedScore >= 0.8 ? `复测：${item.title}` : `巩固：${item.title}`,
    sourceType: "mastery",
    sourceLabel: item.title,
    actionKind: boundedScore >= 0.8 ? "mastery_check" : "mastery_support",
    minutes: 10,
    confidence: boundedScore,
  });
  return (
    <div className="rounded-lg border border-line bg-white p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold text-ink">{item.title}</h3>
        <span className="rounded-md bg-white px-2 py-1 text-xs text-slate-600">{statusLabel(item.status)}</span>
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-700">{copy}</p>
      <div className="mt-3 h-2 rounded-sm bg-canvas">
        <div className={`h-2 rounded-sm ${toneClass}`} style={{ width: `${Math.round(boundedScore * 100)}%` }} />
      </div>
      <p className="mt-2 text-xs text-slate-500">
        {item.score === null || item.score === undefined ? "暂无分数" : formatPercent(item.score)}
        {item.evidence_count ? ` · ${item.evidence_count} 条证据` : ""}
      </p>
      <a
        href={guideHref}
        className="dt-interactive mt-3 inline-flex min-h-9 items-center justify-center gap-2 rounded-md border border-line bg-canvas px-3 text-xs font-medium text-slate-700 hover:border-brand-purple-300 hover:bg-tint-lavender"
      >
        {boundedScore >= 0.8 ? "复测一下" : "巩固一下"}
        <ArrowRight size={14} />
      </a>
      <CalibrationActions claimType="mastery" value={item.title} sourceId={profileSourceIds(item)[0] || ""} onCalibrate={onCalibrate} calibrating={calibrating} />
    </div>
  );
}

function CalibrationActions({
  claimType,
  value,
  sourceId,
  onCalibrate,
  calibrating,
}: {
  claimType: string;
  value: string;
  sourceId: string;
  onCalibrate: CalibrateProfile;
  calibrating: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [correctedValue, setCorrectedValue] = useState(value);

  const submit = (action: "confirm" | "reject" | "correct", nextValue = "") => {
    void onCalibrate({
      action,
      claim_type: claimType,
      value,
      corrected_value: nextValue,
      note: action === "confirm" ? "Confirmed from profile UI" : "Calibrated from profile UI",
      source_id: sourceId,
    });
    if (action !== "correct") {
      setEditing(false);
      setCorrectedValue(value);
    }
  };

  const saveCorrection = () => {
    const next = correctedValue.trim();
    if (!next || next === value) {
      setEditing(false);
      setCorrectedValue(value);
      return;
    }
    submit("correct", next);
    setEditing(false);
  };

  return (
    <div className="mt-3 space-y-2 text-xs">
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={calibrating}
          onClick={() => submit("confirm")}
          className="rounded-md border border-brand-purple-300 bg-white px-2 py-1 font-medium text-brand-purple transition hover:border-brand-purple-300 disabled:opacity-50"
        >
          准确
        </button>
        <button
          type="button"
          disabled={calibrating}
          onClick={() => setEditing((current) => !current)}
          className="rounded-md border border-line bg-white px-2 py-1 font-medium text-slate-600 transition hover:border-brand-purple-300 disabled:opacity-50"
        >
          修改
        </button>
        <button
          type="button"
          disabled={calibrating}
          onClick={() => submit("reject")}
          className="rounded-md border border-red-100 bg-white px-2 py-1 font-medium text-brand-red transition hover:border-red-200 disabled:opacity-50"
        >
          不准
        </button>
      </div>
      <AnimatePresence initial={false}>
        {editing ? (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="rounded-lg border border-line bg-white p-3"
          >
            <p className="mb-2 text-xs font-medium text-slate-500">把它改成更准确的说法</p>
            <TextArea
              value={correctedValue}
              onChange={(event) => setCorrectedValue(event.target.value)}
              className="min-h-[88px] text-sm leading-6"
            />
            <div className="mt-2 flex flex-wrap gap-2">
              <Button tone="primary" onClick={saveCorrection} disabled={calibrating}>
                保存修正
              </Button>
              <Button
                tone="secondary"
                onClick={() => {
                  setEditing(false);
                  setCorrectedValue(value);
                }}
                disabled={calibrating}
              >
                取消
              </Button>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

function statusLabel(value: string) {
  const map: Record<string, string> = {
    mastered: "已掌握",
    developing: "发展中",
    needs_support: "待补强",
    not_started: "未开始",
    unknown: "待观察",
  };
  return map[value] || value || "待观察";
}
