import { motion } from "framer-motion";
import { AlertCircle, ArrowRight, Brain, CheckCircle2, Loader2, RefreshCw, Save, Target } from "lucide-react";
import type { ReactNode } from "react";
import { lazy, Suspense, useState } from "react";

import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { TextInput } from "@/components/ui/Field";
import type { LearnerMastery, LearnerProfileSnapshot, LearnerWeakPoint } from "@/lib/types";
import { buildLearningProgressStyle, type LearningProgressStyle } from "./learningProgressStyle";
import { formatPercent } from "./memoryDisplayUtils";
import { buildNextActionHref } from "./profileGuideLinks";
import type { ProfileChangeSummary } from "./profileChangeSummary";
import type { CalibrateProfile } from "./profileTypes";

const LearningEffectLoopCard = lazy(() =>
  import("@/components/profile/LearningEffectLoopCard").then((module) => ({ default: module.LearningEffectLoopCard })),
);
const LearningStyleCard = lazy(() =>
  import("./LearningStyleCard").then((module) => ({ default: module.LearningStyleCard })),
);
const ProfileChangeCard = lazy(() =>
  import("./ProfileChangeCard").then((module) => ({ default: module.ProfileChangeCard })),
);
const WeakPointItem = lazy(() =>
  import("./ProfileLearningCards").then((module) => ({ default: module.WeakPointItem })),
);
const MasteryItem = lazy(() =>
  import("./ProfileLearningCards").then((module) => ({ default: module.MasteryItem })),
);

export function ProfilePanel({
  profile,
  changeSummary,
  isLoading,
  isError,
  refreshing,
  onRefresh,
  onCalibrate,
  calibrating,
}: {
  profile?: LearnerProfileSnapshot;
  changeSummary: ProfileChangeSummary | null;
  isLoading: boolean;
  isError: boolean;
  refreshing: boolean;
  onRefresh: () => void;
  onCalibrate: CalibrateProfile;
  calibrating: boolean;
}) {
  const [quickCorrection, setQuickCorrection] = useState("");
  const [quickNotice, setQuickNotice] = useState("");

  if (isLoading) {
    return (
      <motion.section className="rounded-lg border border-line bg-white p-8 text-center text-slate-500" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        <Loader2 className="mx-auto animate-spin text-brand-purple" />
        <p className="mt-3 text-sm">正在读取学习画像...</p>
      </motion.section>
    );
  }

  if (isError || !profile) {
    return (
      <motion.section className="rounded-lg border border-line bg-white p-6" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        <EmptyState
          icon={<AlertCircle size={24} />}
          title="画像暂时不可用"
          description="后端画像服务没有返回数据。可以先更新一次画像，系统会从现有学习证据重新聚合。"
          action={
            <Button tone="primary" onClick={onRefresh} disabled={refreshing}>
              {refreshing ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
              重新生成
            </Button>
          }
        />
      </motion.section>
    );
  }

  const weakPoints = profile.learning_state.weak_points ?? [];
  const mastery = profile.learning_state.mastery ?? [];
  const preferences = profile.stable_profile.preferences ?? [];
  const strengths = profile.stable_profile.strengths ?? [];
  const nextAction = profile.next_action;
  const progressStyle = buildLearningProgressStyle(profile);
  const topWeakPoints = weakPoints.slice(0, 2);
  const topMastery = mastery.slice(0, 3);
  const preferenceLabels = preferences.map(preferenceLabel);
  const quickTags = [
    ...preferenceLabels.slice(0, 3).map((item) => `偏好：${item}`),
    ...strengths.slice(0, 2).map((item) => `优势：${item}`),
  ];
  const primaryTitle = nextAction?.title?.trim() || profile.overview.current_focus || "先完成一次导学或练习";
  const primarySummary =
    nextAction?.summary?.trim() ||
    profile.overview.summary ||
    "系统会根据你的导学、练习和笔记证据，慢慢整理出更准确的学习重点。";
  const primaryActionHref = nextAction ? buildNextActionHref(nextAction) : "/guide?new=1";
  const primaryActionLabel = nextAction?.primary_label?.trim() || "进入导学";
  const primaryMinutes =
    typeof nextAction?.estimated_minutes === "number" && Number.isFinite(nextAction.estimated_minutes)
      ? Math.round(nextAction.estimated_minutes)
      : null;
  const dashboardReasons = buildProfileDashboardReasons({
    profile,
    progressStyle,
    weakPoints: topWeakPoints,
    mastery: topMastery,
    preferences: preferenceLabels,
  });
  const overviewClaimValue = [profile.overview.current_focus, profile.overview.summary].filter(Boolean).join("\n");
  const confirmOverview = async () => {
    setQuickNotice("");
    try {
      await onCalibrate({
        action: "confirm",
        claim_type: "profile_overview",
        value: overviewClaimValue,
        note: "Quick confirmation from learner profile overview",
        source_id: "profile_overview",
      });
      setQuickNotice("已确认。系统会更放心地按这个方向安排学习。");
    } catch {
      setQuickNotice("保存失败，请稍后再试。");
    }
  };
  const submitQuickCorrection = async () => {
    const next = quickCorrection.trim();
    if (!next) return;
    setQuickNotice("");
    try {
      await onCalibrate({
        action: "correct",
        claim_type: "profile_overview",
        value: [profile.overview.current_focus, profile.overview.summary].filter(Boolean).join("\n"),
        corrected_value: next,
        note: "Quick correction from learner profile overview",
        source_id: "profile_overview",
      });
      setQuickCorrection("");
      setQuickNotice("已记录。后续导学和聊天会参考这次修正。");
    } catch {
      setQuickNotice("保存失败，请稍后再试。");
    }
  };

  return (
    <motion.div
      className="space-y-4"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      transition={{ duration: 0.22 }}
    >
      <section className="rounded-lg border border-line bg-white p-5 shadow-sm" data-testid="learner-profile-overview">
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1.45fr)_minmax(260px,0.9fr)]">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase text-brand-purple">现在只做这一件事</p>
            <h2 className="mt-2 text-2xl font-semibold leading-tight text-ink">{primaryTitle}</h2>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">{primarySummary}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {primaryMinutes ? <Tag>{primaryMinutes} 分钟</Tag> : null}
              <Tag>{progressStyle.label}</Tag>
              {quickTags.map((item) => (
                <Tag key={item}>{item}</Tag>
              ))}
              {!quickTags.length ? <span className="text-sm text-slate-500">偏好和优势还在形成中</span> : null}
            </div>
            <a
              href={primaryActionHref}
              data-testid="learner-profile-primary-action"
              className="dt-interactive mt-5 inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-brand-purple bg-brand-purple px-4 text-sm font-medium text-white hover:bg-brand-purple-800"
            >
              {primaryActionLabel}
              <ArrowRight size={16} />
            </a>
            <button
              type="button"
              onClick={() => void confirmOverview()}
              disabled={calibrating || !overviewClaimValue}
              data-testid="learner-profile-confirm-overview"
              className="dt-interactive ml-2 mt-5 inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-line bg-white px-4 text-sm font-medium text-slate-700 transition hover:border-brand-purple-300 hover:text-brand-purple disabled:cursor-not-allowed disabled:opacity-60"
            >
              {calibrating ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
              判断准确
            </button>
          </div>
          <div className="min-w-0 lg:border-l lg:border-line lg:pl-5">
            <p className="flex items-center gap-2 text-sm font-semibold text-ink">
              <Target size={16} className="text-brand-purple" />
              为什么这样安排
            </p>
            <div className="mt-3 space-y-3">
              {dashboardReasons.map((item) => (
                <div key={item.label}>
                  <p className="text-xs font-medium text-slate-500">{item.label}</p>
                  <p className="mt-1 text-sm leading-5 text-slate-700">{item.value}</p>
                </div>
              ))}
            </div>
            <div className="mt-4 grid grid-cols-3 gap-2 text-center">
              <MiniStat label="可信" value={formatPercent(profile.confidence)} />
              <MiniStat label="证据" value={`${profile.data_quality.evidence_count ?? 0}`} />
              <MiniStat label="校准" value={`${profile.data_quality.calibration_count ?? 0}`} />
            </div>
          </div>
        </div>
      </section>

      {changeSummary ? (
        <Suspense fallback={<ProfileSectionLoading label="正在整理画像变化" />}>
          <ProfileChangeCard summary={changeSummary} />
        </Suspense>
      ) : null}

      <Suspense fallback={<ProfileSectionLoading label="正在整理学习效果闭环" />}>
        <LearningEffectLoopCard />
      </Suspense>

      <Suspense fallback={<ProfileSectionLoading label="正在准备学习推进方式" />}>
        <LearningStyleCard progressStyle={progressStyle} actionHref={primaryActionHref} actionLabel={primaryActionLabel} />
      </Suspense>

      <section className="grid gap-3 lg:grid-cols-2">
        <Panel title="最需要补的" icon={<AlertCircle size={17} />}>
          {topWeakPoints.length ? (
            <Suspense fallback={<ProfileSectionLoading label="正在准备薄弱点校准" />}>
              <div className="space-y-2">
                {topWeakPoints.map((item) => (
                  <WeakPointItem key={`${item.label}-${item.evidence_count ?? 0}`} item={item} onCalibrate={onCalibrate} calibrating={calibrating} />
                ))}
              </div>
            </Suspense>
          ) : (
            <p className="text-sm leading-6 text-slate-500">暂时没有明显薄弱点。继续提交练习后，这里会更准。</p>
          )}
        </Panel>

        <Panel title="掌握情况" icon={<Brain size={17} />}>
          {topMastery.length ? (
            <Suspense fallback={<ProfileSectionLoading label="正在准备掌握度校准" />}>
              <div className="space-y-2">
                {topMastery.map((item) => (
                  <MasteryItem key={item.concept_id} item={item} onCalibrate={onCalibrate} calibrating={calibrating} />
                ))}
              </div>
            </Suspense>
          ) : (
            <p className="text-sm leading-6 text-slate-500">还没有足够的题目或导学证据来判断掌握度。</p>
          )}
        </Panel>
      </section>

      <section className="rounded-lg border border-line bg-white p-3">
        <form
          className="space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            void submitQuickCorrection();
          }}
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-sm font-semibold text-ink">画像不准？一句话改掉</p>
              <p className="mt-1 text-xs leading-5 text-slate-500">系统后续导学、聊天和推荐都会参考这次修正。</p>
            </div>
            <Button type="button" tone="secondary" onClick={onRefresh} disabled={refreshing}>
              {refreshing ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
              重新整理
            </Button>
          </div>
          <div className="grid gap-2 md:grid-cols-[minmax(0,1fr)_auto]">
            <TextInput
              value={quickCorrection}
              onChange={(event) => {
                setQuickCorrection(event.target.value);
                setQuickNotice("");
              }}
              placeholder="例如：我主要卡在公式含义和应用场景，不是基础差。"
            />
            <Button type="submit" tone="primary" disabled={calibrating || !quickCorrection.trim()}>
              {calibrating ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
              保存
            </Button>
          </div>
          {quickNotice ? <p className="text-xs font-medium text-brand-purple">{quickNotice}</p> : null}
        </form>
      </section>
    </motion.div>
  );
}

function ProfileSectionLoading({ label }: { label: string }) {
  return (
    <section className="rounded-lg border border-line bg-white/82 p-4">
      <p className="text-sm font-semibold text-ink">{label}</p>
      <div className="mt-3 space-y-2">
        <span className="block h-3 w-44 max-w-full rounded bg-slate-100" />
        <span className="block h-12 rounded bg-slate-100/80" />
      </div>
    </section>
  );
}

function buildProfileDashboardReasons({
  profile,
  progressStyle,
  weakPoints,
  mastery,
  preferences,
}: {
  profile: LearnerProfileSnapshot;
  progressStyle: LearningProgressStyle;
  weakPoints: LearnerWeakPoint[];
  mastery: LearnerMastery[];
  preferences: string[];
}) {
  const rows = [
    {
      label: "系统理解",
      value: profile.overview.current_focus || "系统正在根据你的学习记录形成判断。",
    },
  ];

  if (weakPoints[0]) {
    rows.push({
      label: "优先卡点",
      value: weakPoints[0].reason || `当前最需要先补「${weakPoints[0].label}」。`,
    });
  } else if (mastery[0]) {
    rows.push({
      label: "已有基础",
      value: `「${mastery[0].title}」掌握度约 ${formatPercent(mastery[0].score)}，可以作为继续推进的支点。`,
    });
  } else {
    rows.push({
      label: "证据状态",
      value: "目前证据还少，先完成一次导学或练习，判断会更准。",
    });
  }

  rows.push({
    label: "适合方式",
    value: preferences.length
      ? `优先按「${preferences.slice(0, 2).join("、")}」的方式推进；做完后会回写掌握度和下一步建议。`
      : `${progressStyle.summary} 做完后会回写画像，让下一步更准。`,
  });

  return rows.slice(0, 3);
}

function Panel({ title, icon, children }: { title: string; icon?: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-line bg-white p-4">
      <h2 className="flex items-center gap-2 text-base font-semibold text-ink">
        <span className="text-brand-purple">{icon}</span>
        {title}
      </h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function MiniStat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-md bg-canvas px-2 py-2">
      <p className="text-[11px] font-medium text-slate-500">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-ink">{value}</p>
    </div>
  );
}

function Tag({ children }: { children: ReactNode }) {
  return <span className="rounded-md border border-brand-purple-300 bg-tint-lavender px-2 py-1 text-xs font-medium text-brand-purple">{children}</span>;
}

function preferenceLabel(value: string) {
  const normalized = String(value || "").trim();
  const lowered = normalized.toLowerCase();
  if (lowered === "external_video" || lowered === "public_video") return "公开视频";
  if (lowered === "short_video") return "短视频";
  if (lowered === "visual") return "图解";
  if (lowered === "practice") return "练习";
  if (lowered === "quiz") return "交互练习";
  return normalized;
}
