import { AnimatePresence, motion } from "framer-motion";
import {
  AlertCircle,
  ArrowRight,
  BookOpen,
  Brain,
  CheckCircle2,
  Database,
  Eraser,
  Loader2,
  RefreshCw,
  Save,
  Target,
  UserRound,
} from "lucide-react";
import type { ReactNode } from "react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { TextArea, TextInput } from "@/components/ui/Field";
import { MarkdownRenderer } from "@/components/ui/MarkdownRenderer";
import { PeopleAccent } from "@/components/ui/PeopleAccent";
import { LearningEffectLoopCard } from "@/components/profile/LearningEffectLoopCard";
import {
  useLearnerProfile,
  useLearnerProfileEvidencePreview,
  useLearnerProfileMutations,
  useMemory,
  useMemoryMutations,
} from "@/hooks/useApiQueries";
import type {
  LearnerEvidencePreview,
  LearnerMastery,
  LearnerProfileCalibrationRequest,
  LearnerProfileSnapshot,
  LearnerWeakPoint,
  MemoryFile,
  MemorySnapshot,
} from "@/lib/types";

type PageTab = "profile" | "evidence" | "memory";
type CalibrateProfile = (input: LearnerProfileCalibrationRequest) => Promise<void>;
type ProfileChangeDetail = {
  label: string;
  previous: string;
  current: string;
  evidenceHints?: string[];
};

type ProfileChangeSummary = {
  title: string;
  tone: "brand" | "calibration";
  items: string[];
  details: ProfileChangeDetail[];
  updatedAt: string;
};

type LearningProgressStyle = {
  label: string;
  summary: string;
  confidenceText: string;
  signals: Array<{ label: string; detail: string; tone: "success" | "brand" | "warning" }>;
  suggestions: string[];
  recentShift?: {
    label: string;
    summary: string;
    direction: "stable" | "accelerating" | "correcting" | "observing";
    cues: string[];
  } | null;
};

type EvidenceBrief = {
  title: string;
  summary: string;
  stats: Array<{ label: string; value: string }>;
  cues: string[];
};

const PAGE_TABS: Array<{ key: PageTab; label: string; helper: string; icon: typeof Brain }> = [
  { key: "profile", label: "概览", helper: "先看下一步", icon: UserRound },
  { key: "evidence", label: "依据", helper: "为什么这样判断", icon: Database },
  { key: "memory", label: "补充", helper: "手动修正画像", icon: BookOpen },
];

const MEMORY_TABS: Array<{ key: MemoryFile; label: string; hint: string; icon: typeof Brain; placeholder: string }> = [
  {
    key: "summary",
    label: "学习摘要",
    hint: "记录最近在学什么、推进到哪里、还卡在什么地方。",
    icon: BookOpen,
    placeholder: "## 当前重点\n- \n\n## 已完成\n- \n\n## 待解决\n- ",
  },
  {
    key: "profile",
    label: "稳定偏好",
    hint: "记录长期目标、表达习惯和资源偏好。",
    icon: UserRound,
    placeholder: "## 目标\n- \n\n## 学习偏好\n- \n\n## 当前水平\n- ",
  },
];

function formatDate(value?: string | null) {
  if (!value) return "暂无";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function formatPercent(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return "暂无";
  return `${Math.round(value * 100)}%`;
}

function profileConfidenceLabel(confidence: number, accuracy: number) {
  if (confidence >= 0.75 && accuracy >= 0.55) return "系统比较有把握";
  if (confidence >= 0.5) return "仍在继续校准";
  return "先轻量观察";
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

function profileSourceIds(item: { source_ids?: string[] | null }) {
  return Array.isArray(item.source_ids) ? item.source_ids.filter(Boolean) : [];
}

export function MemoryPage() {
  const [activeTab, setActiveTab] = useState<PageTab>("profile");
  const [changeSummary, setChangeSummary] = useState<ProfileChangeSummary | null>(null);
  const profile = useLearnerProfile();
  const profileMutations = useLearnerProfileMutations();
  const memory = useMemory();
  const memoryMutations = useMemoryMutations();

  const snapshot = memory.data ?? {
    summary: "",
    profile: "",
    summary_updated_at: null,
    profile_updated_at: null,
  };
  const snapshotKey = [
    snapshot.summary_updated_at,
    snapshot.profile_updated_at,
    snapshot.summary.length,
    snapshot.profile.length,
  ].join(":");

  const refreshProfile = async () => {
    const nextProfile = await profileMutations.refresh.mutateAsync({ force: true });
    setChangeSummary(
      buildProfileChangeSummary({
        previous: profile.data,
        current: nextProfile,
        title: "画像已更新",
        tone: "brand",
      }),
    );
  };

  const calibrateProfile: CalibrateProfile = async (input) => {
    const result = await profileMutations.calibrate.mutateAsync(input);
    setChangeSummary(
      buildProfileChangeSummary({
        previous: profile.data,
        current: result.profile,
        title: "画像已按你的反馈调整",
        tone: "calibration",
      }),
    );
  };
  const heroFocus = profile.data?.overview.current_focus?.trim() || "先完成一次导学，系统会生成第一版画像。";
  const heroWeakPoint = profile.data?.learning_state.weak_points?.[0]?.label || "薄弱点会随练习证据自动浮现";
  const heroEvidenceCount = profile.data?.data_quality.evidence_count ?? 0;

  return (
    <div className="h-full overflow-y-auto px-4 py-4 pb-24 lg:px-5 lg:pb-6">
      <div className="mx-auto max-w-6xl space-y-4">
        <motion.section
          className="dt-page-header dt-page-header-accent-orange"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22 }}
        >
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px] lg:items-center">
            <div>
              <p className="dt-page-eyebrow">学习画像</p>
              <div className="mt-1 flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h1 className="text-2xl font-semibold leading-tight text-ink">一页看懂系统怎么理解你</h1>
                  <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-600">
                    画像只回答三个问题：你现在卡在哪、适合怎么学、下一步做什么。不准就直接修正。
                  </p>
                  <div className="mt-4 flex flex-wrap items-center gap-2">
                    <a
                      href="/guide"
                      className="dt-interactive inline-flex min-h-10 items-center gap-2 rounded-lg border border-brand-purple bg-brand-purple px-4 text-sm font-medium text-white hover:bg-brand-purple-800"
                    >
                      进入导学
                      <ArrowRight size={16} />
                    </a>
                    <Button
                      tone="secondary"
                      onClick={() => void refreshProfile()}
                      disabled={profileMutations.refresh.isPending}
                      data-testid="learner-profile-refresh"
                    >
                      {profileMutations.refresh.isPending ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
                      重新整理
                    </Button>
                  </div>
                </div>
              </div>
            </div>
            <div className="dt-workspace-mockup">
              <div className="relative min-h-[150px] overflow-hidden border-b border-line bg-[#fbfbfa] p-4">
                <div className="relative z-10 max-w-[230px]">
                  <p className="text-sm font-semibold text-ink">画像会跟着你更新</p>
                  <p className="mt-1 text-xs leading-5 text-steel">偏好、薄弱点和证据都会沉淀下来。</p>
                </div>
                <PeopleAccent name="thinking" className="absolute bottom-[-24px] right-[-18px] h-44 w-52 opacity-90" />
              </div>
              <div className="grid gap-2 bg-white p-3 sm:grid-cols-3">
                <div className="dt-feature-tile dt-feature-tile-lavender px-3 py-2">
                  <p className="text-xs font-semibold text-steel">当前重点</p>
                  <p className="mt-1 line-clamp-2 text-sm font-semibold leading-5 text-ink">{heroFocus}</p>
                </div>
                <div className="dt-feature-tile dt-feature-tile-yellow px-3 py-2">
                  <p className="text-xs font-semibold text-steel">主要卡点</p>
                  <p className="mt-1 line-clamp-2 text-sm font-semibold leading-5 text-ink">{heroWeakPoint}</p>
                </div>
                <div className="dt-feature-tile dt-feature-tile-sky px-3 py-2">
                  <p className="text-xs font-semibold text-steel">证据数</p>
                  <p className="mt-1 text-sm font-semibold leading-5 text-ink">{heroEvidenceCount} 条学习证据</p>
                </div>
              </div>
            </div>
          </div>
        </motion.section>

        <nav
          className="flex flex-wrap gap-1 rounded-lg border border-line bg-white p-1 shadow-sm"
          aria-label="学习画像页面"
          role="tablist"
        >
          {PAGE_TABS.map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.key;
            return (
              <motion.button
                key={tab.key}
                type="button"
                onClick={() => setActiveTab(tab.key)}
                whileHover={{ y: -1 }}
                whileTap={{ scale: 0.99 }}
                role="tab"
                aria-selected={active}
                data-testid={`learner-profile-tab-${tab.key}`}
                className={`min-h-10 flex-1 rounded-md px-3 py-2 text-left transition sm:min-w-32 ${
                  active ? "bg-tint-lavender text-brand-purple" : "text-slate-500 hover:bg-canvas hover:text-slate-700"
                }`}
              >
                <span className="flex items-center gap-2 text-sm font-semibold">
                  <Icon size={17} />
                  {tab.label}
                </span>
                {active ? <span className="mt-0.5 block text-xs text-slate-500">{tab.helper}</span> : null}
              </motion.button>
            );
          })}
        </nav>

        <AnimatePresence mode="wait">
          {activeTab === "profile" ? (
            <ProfilePanel
              key="profile"
              profile={profile.data}
              changeSummary={changeSummary}
              isLoading={profile.isLoading}
              isError={profile.isError}
              onRefresh={() => void refreshProfile()}
              refreshing={profileMutations.refresh.isPending}
              onCalibrate={calibrateProfile}
              calibrating={profileMutations.calibrate.isPending}
            />
          ) : null}
          {activeTab === "evidence" ? <EvidencePanel key="evidence" profile={profile.data} /> : null}
          {activeTab === "memory" ? (
            <MemoryEditor
              key={snapshotKey}
              snapshot={snapshot}
              isLoading={memory.isLoading}
              mutations={memoryMutations}
            />
          ) : null}
        </AnimatePresence>
      </div>
    </div>
  );
}

function ProfilePanel({
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

      {changeSummary ? <ProfileChangeCard summary={changeSummary} /> : null}

      <LearningEffectLoopCard />

      <LearningStyleCard progressStyle={progressStyle} actionHref={primaryActionHref} actionLabel={primaryActionLabel} />

      <section className="grid gap-3 lg:grid-cols-2">
        <Panel title="最需要补的" icon={<AlertCircle size={17} />}>
          {topWeakPoints.length ? (
            <div className="space-y-2">
              {topWeakPoints.map((item) => (
                <WeakPointItem key={`${item.label}-${profileSourceIds(item).join("-")}`} item={item} onCalibrate={onCalibrate} calibrating={calibrating} />
              ))}
            </div>
          ) : (
            <p className="text-sm leading-6 text-slate-500">暂时没有明显薄弱点。继续提交练习后，这里会更准。</p>
          )}
        </Panel>

        <Panel title="掌握情况" icon={<Brain size={17} />}>
          {topMastery.length ? (
            <div className="space-y-2">
              {topMastery.map((item) => (
                <MasteryItem key={item.concept_id} item={item} onCalibrate={onCalibrate} calibrating={calibrating} />
              ))}
            </div>
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

function LearningStyleCard({
  progressStyle,
  actionHref,
  actionLabel,
}: {
  progressStyle: LearningProgressStyle;
  actionHref: string;
  actionLabel: string;
}) {
  const shift = progressStyle.recentShift;
  const directionTone: Record<NonNullable<LearningProgressStyle["recentShift"]>["direction"], string> = {
    stable: "border-emerald-100 bg-emerald-50 text-emerald-700",
    accelerating: "border-blue-100 bg-blue-50 text-brand-blue",
    correcting: "border-amber-100 bg-amber-50 text-amber-700",
    observing: "border-line bg-canvas text-slate-600",
  };

  return (
    <section className="rounded-lg border border-line bg-white p-4 shadow-sm" data-testid="learner-progress-style-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase text-brand-purple">你的学习推进方式</p>
          <h2 className="mt-2 text-lg font-semibold text-ink">系统会按“{progressStyle.label}”带你走</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{progressStyle.summary}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Tag>{progressStyle.confidenceText}</Tag>
          <a
            href={actionHref}
            className="dt-interactive inline-flex min-h-9 items-center justify-center gap-2 rounded-md border border-brand-purple-300 bg-tint-lavender px-3 text-xs font-medium text-brand-purple hover:bg-white"
          >
            {actionLabel}
            <ArrowRight size={14} />
          </a>
        </div>
      </div>

      <div className="mt-4 grid gap-2 md:grid-cols-3">
        {progressStyle.signals.slice(0, 3).map((signal, index) => (
          <motion.div
            key={signal.label}
            className="rounded-lg border border-line bg-canvas p-3"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.04, duration: 0.18 }}
          >
            <div className="flex items-center gap-2">
              <span className="flex size-6 shrink-0 items-center justify-center rounded-md bg-white text-xs font-semibold text-brand-purple">
                {index + 1}
              </span>
              <Badge tone={signal.tone}>{signal.label}</Badge>
            </div>
            <p className="mt-2 text-xs leading-5 text-slate-600">{signal.detail}</p>
          </motion.div>
        ))}
      </div>

      <div className={`mt-3 rounded-lg border p-3 ${shift ? directionTone[shift.direction] : "border-line bg-canvas text-slate-600"}`}>
        <div className="flex flex-wrap items-center gap-2">
          <CheckCircle2 size={15} />
          <p className="text-xs font-semibold">{shift?.label || "最近仍在观察"}</p>
        </div>
        <p className="mt-2 text-xs leading-5">{shift?.summary || "继续完成一次任务或练习后，系统会更清楚你适合怎样推进。"}</p>
        {shift?.cues.length ? (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {shift.cues.slice(0, 3).map((cue) => (
              <span key={cue} className="rounded-md border border-white/70 bg-white/80 px-2 py-1 text-[11px] text-slate-600">
                {cue}
              </span>
            ))}
          </div>
        ) : null}
      </div>

      {progressStyle.suggestions.length ? (
        <p className="mt-3 text-xs leading-5 text-slate-500">系统接下来会优先：{progressStyle.suggestions[0]}</p>
      ) : null}
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

function buildNextActionHref(action: NonNullable<LearnerProfileSnapshot["next_action"]>) {
  const href = typeof action.href === "string" && action.href.trim() ? action.href : "/guide";
  const title = typeof action.title === "string" ? action.title.trim() : "";
  const prompt = typeof action.suggested_prompt === "string" ? action.suggested_prompt.trim() : "";
  const minutes = typeof action.estimated_minutes === "number" && Number.isFinite(action.estimated_minutes) ? Math.round(action.estimated_minutes) : null;
  const confidence = typeof action.confidence === "number" ? Math.max(0, Math.min(1, action.confidence)) : null;
  const actionParams = new URLSearchParams();
  actionParams.set("new", "1");
  if (prompt) actionParams.set("prompt", prompt);
  if (title) actionParams.set("action_title", title);
  if (typeof action.kind === "string" && action.kind.trim()) actionParams.set("action_kind", action.kind.trim());
  if (typeof action.source_type === "string" && action.source_type.trim()) actionParams.set("source_type", action.source_type.trim());
  if (typeof action.source_label === "string" && action.source_label.trim()) actionParams.set("source_label", action.source_label.trim());
  if (minutes) actionParams.set("estimated_minutes", String(minutes));
  if (confidence !== null) actionParams.set("confidence", String(confidence));
  actionParams.set("target_section", "guide-create-section");
  return `${href}${href.includes("?") ? "&" : "?"}${actionParams.toString()}`;
}

function buildGuidePromptHref({
  prompt,
  title,
  sourceType,
  sourceLabel,
  actionKind,
  minutes,
  confidence,
}: {
  prompt: string;
  title: string;
  sourceType: string;
  sourceLabel: string;
  actionKind: string;
  minutes?: number;
  confidence?: number;
}) {
  const actionParams = new URLSearchParams();
  actionParams.set("new", "1");
  actionParams.set("prompt", prompt);
  actionParams.set("action_title", title);
  actionParams.set("action_kind", actionKind);
  actionParams.set("source_type", sourceType);
  actionParams.set("source_label", sourceLabel);
  if (typeof minutes === "number" && Number.isFinite(minutes)) actionParams.set("estimated_minutes", String(Math.round(minutes)));
  if (typeof confidence === "number" && Number.isFinite(confidence)) actionParams.set("confidence", String(Math.max(0, Math.min(1, confidence))));
  actionParams.set("target_section", "guide-create-section");
  return `/guide?${actionParams.toString()}`;
}

function ProfileChangeCard({ summary }: { summary: ProfileChangeSummary }) {
  const toneClass = summary.tone === "calibration" ? "border-amber-200 bg-amber-50" : "border-brand-purple-300 bg-tint-lavender";
  return (
    <motion.section
      className={`rounded-lg border p-4 ${toneClass}`}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold text-brand-purple">最近变化</p>
          <h2 className="mt-2 text-lg font-semibold text-ink">{summary.title}</h2>
        </div>
        <span className="text-xs text-slate-500">{formatDate(summary.updatedAt)}</span>
      </div>
      <div className="mt-3 grid gap-2">
        {summary.items.map((item, index) => (
          <div key={`${item}-${index}`} className="rounded-lg border border-white/70 bg-white/80 px-3 py-2 text-sm leading-6 text-slate-700">
            {item}
          </div>
        ))}
      </div>
      {summary.details.length ? (
        <div className="mt-4 grid gap-2">
          {summary.details.map((detail) => (
            <div key={`${detail.label}-${detail.previous}-${detail.current}`} className="rounded-lg border border-white/70 bg-white/70 p-3">
              <div className="text-xs font-semibold text-slate-500">{detail.label}</div>
              <div className="mt-2 grid gap-2 md:grid-cols-2">
                <div className="rounded-md border border-line bg-white px-3 py-2">
                  <div className="text-[11px] font-medium text-slate-400">之前</div>
                  <div className="mt-1 text-sm leading-6 text-slate-600">{detail.previous}</div>
                </div>
                <div className="rounded-md border border-brand-purple-300 bg-tint-lavender px-3 py-2">
                  <div className="text-[11px] font-medium text-brand-purple">现在</div>
                  <div className="mt-1 text-sm leading-6 text-ink">{detail.current}</div>
                </div>
              </div>
              {detail.evidenceHints?.length ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {detail.evidenceHints.map((hint) => (
                    <span key={`${detail.label}-${hint}`} className="rounded-md border border-line bg-white px-2 py-1 text-xs text-slate-500">
                      相关依据：{hint}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
    </motion.section>
  );
}

function EvidencePanel({ profile }: { profile?: LearnerProfileSnapshot }) {
  const [source, setSource] = useState<string | null>(null);
  const evidence = useLearnerProfileEvidencePreview(source, 40);
  const sources = profile?.sources ?? [];
  const items = evidence.data?.items ?? profile?.evidence_preview ?? [];
  const brief = buildEvidenceBrief(items, profile);

  return (
    <motion.section
      className="space-y-3 rounded-lg border border-line bg-white p-4"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      transition={{ duration: 0.22 }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-ink">画像证据</h2>
          <p className="mt-1 text-sm text-slate-500">每条画像判断都应该能回到真实学习记录。</p>
        </div>
        {evidence.isFetching ? <Loader2 size={18} className="animate-spin text-brand-purple" /> : null}
      </div>

      {brief ? <EvidenceBriefCard brief={brief} /> : null}

      <div className="flex flex-wrap gap-2">
        <FilterButton active={!source} onClick={() => setSource(null)}>
          全部
        </FilterButton>
        {sources.map((item) => (
          <FilterButton key={item.source_id} active={source === item.source_id} onClick={() => setSource(item.source_id)}>
            {evidenceSourceLabel(item.label || item.source_id)}
          </FilterButton>
        ))}
      </div>

      {items.length ? (
        <div className="grid gap-2">
          {items.map((item) => (
            <EvidenceItem key={item.evidence_id} item={item} />
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<Database size={24} />}
          title="还没有画像证据"
          description="完成导学任务、提交练习或保存笔记后，这里会展示画像形成的依据。"
        />
      )}
    </motion.section>
  );
}

function EvidenceBriefCard({ brief }: { brief: EvidenceBrief }) {
  return (
    <div className="rounded-lg border border-brand-purple-300 bg-tint-lavender p-4" data-testid="learner-evidence-brief">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Badge tone="brand">证据结论</Badge>
          <h3 className="mt-2 text-base font-semibold text-ink">{brief.title}</h3>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-charcoal">{brief.summary}</p>
        </div>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-3">
        {brief.stats.map((item) => (
          <div key={`${item.label}-${item.value}`} className="rounded-md border border-brand-purple-300 bg-white/80 px-3 py-2">
            <p className="text-[11px] font-medium text-slate-500">{item.label}</p>
            <p className="mt-1 truncate text-sm font-semibold text-ink">{item.value}</p>
          </div>
        ))}
      </div>
      {brief.cues.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {brief.cues.map((cue) => (
            <span key={cue} className="rounded-md border border-brand-purple-300 bg-white/80 px-2 py-1 text-xs text-charcoal">
              {cue}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function buildEvidenceBrief(items: LearnerEvidencePreview[], profile?: LearnerProfileSnapshot): EvidenceBrief | null {
  const total = Number(profile?.data_quality.evidence_count ?? items.length);
  if (!items.length && !total) return null;

  const latest = items[0];
  const verbs = countTop(items.map((item) => evidenceVerbLabel(metadataText(item.metadata, "verb"))).filter(Boolean));
  const resourceTypes = countTop(items.map((item) => resourceTypeLabel(metadataText(item.metadata, "resource_type"))).filter(Boolean));
  const sourceLabels = countTop(items.map((item) => evidenceSourceLabel(item.source_label)).filter(Boolean));
  const scores = items
    .map((item) => (typeof item.score === "number" && Number.isFinite(item.score) ? item.score : null))
    .filter((value): value is number => value !== null);
  const averageScore = scores.length ? scores.reduce((sum, value) => sum + value, 0) / scores.length : null;
  const latestVerb = latest ? evidenceVerbLabel(metadataText(latest.metadata, "verb")) : "";
  const latestResource = latest ? resourceTypeLabel(metadataText(latest.metadata, "resource_type")) : "";
  const latestSource = latest ? evidenceSourceLabel(latest.source_label) : "";

  let title = "证据正在帮系统收敛判断";
  if (latestVerb === "看过" && latestResource) title = `最近在用${latestResource}补理解`;
  else if (latestVerb === "答题") title = "最近留下了练习证据";
  else if (latestVerb === "完成") title = "最近完成了一步导学任务";
  else if (latestVerb === "确认画像" || latestVerb === "修正画像" || latestVerb === "否定画像") title = "最近主动校准了画像";
  else if (latestSource) title = `最近证据来自${latestSource}`;

  const summaryParts = [
    total ? `当前画像累计参考 ${total} 条学习证据。` : "",
    latest?.summary || latest?.title ? `最近一条是“${latest.summary || latest.title}”。` : "",
    averageScore !== null ? `最近可评分证据均值约 ${Math.round(averageScore * 100)}%。` : "",
  ].filter(Boolean);
  const summary = summaryParts.length
    ? summaryParts.join("")
    : "系统会优先看你真实做过、看过、答过和校准过的记录，而不是只凭一次对话下结论。";

  const stats = [
    { label: "累计证据", value: total ? `${total} 条` : `${items.length} 条` },
    { label: "当前筛选", value: items.length ? `${items.length} 条` : "暂无" },
    { label: "最新记录", value: latest?.created_at ? formatDate(latest.created_at) : "暂无" },
  ];
  if (averageScore !== null) stats[1] = { label: "最近得分", value: formatPercent(averageScore) };

  const cues = [
    ...verbs.slice(0, 2).map((item) => `行为：${item.label} ${item.count} 次`),
    ...resourceTypes.slice(0, 2).map((item) => `资源：${item.label}`),
    ...sourceLabels.slice(0, 2).map((item) => `来源：${item.label}`),
  ].slice(0, 5);

  return { title, summary, stats, cues };
}

function countTop(values: string[]) {
  const counts = new Map<string, number>();
  values.forEach((value) => counts.set(value, (counts.get(value) ?? 0) + 1));
  return [...counts.entries()]
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}

function MemoryEditor({
  snapshot,
  isLoading,
  mutations,
}: {
  snapshot: MemorySnapshot;
  isLoading: boolean;
  mutations: ReturnType<typeof useMemoryMutations>;
}) {
  const [activeFile, setActiveFile] = useState<MemoryFile>("summary");
  const [viewMode, setViewMode] = useState<"edit" | "preview">("edit");
  const [drafts, setDrafts] = useState<Record<MemoryFile, string>>({
    summary: snapshot.summary || "",
    profile: snapshot.profile || "",
  });

  const activeTab = MEMORY_TABS.find((tab) => tab.key === activeFile) ?? MEMORY_TABS[0];
  const activeContent = drafts[activeFile] ?? "";
  const savedContent = snapshot[activeFile] ?? "";
  const hasChanges = activeContent !== savedContent;
  const wordCount = useMemo(() => activeContent.trim().split(/\s+/).filter(Boolean).length, [activeContent]);

  const save = async () => {
    await mutations.save.mutateAsync({ file: activeFile, content: activeContent });
  };

  const refresh = async () => {
    await mutations.refresh.mutateAsync({ sessionId: null, language: "zh" });
  };

  const clear = async () => {
    if (!window.confirm(`清空“${activeTab.label}”？`)) return;
    await mutations.clear.mutateAsync(activeFile);
  };

  return (
    <motion.section
      className="grid gap-4 lg:grid-cols-[240px_minmax(0,1fr)]"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      transition={{ duration: 0.22 }}
    >
      <aside className="rounded-lg border border-line bg-white p-3">
        <h2 className="text-base font-semibold text-ink">手动补充</h2>
        <p className="mt-1 text-sm leading-5 text-slate-500">只在需要时补一句长期信息；日常先看画像概览即可。</p>
        <div className="mt-4 grid gap-2">
          {MEMORY_TABS.map((tab) => {
            const Icon = tab.icon;
            const active = tab.key === activeFile;
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveFile(tab.key)}
                className={`rounded-lg border p-3 text-left transition ${
                  active ? "border-brand-purple-300 bg-tint-lavender text-brand-purple" : "border-line bg-canvas text-slate-600 hover:border-brand-purple-300"
                }`}
              >
                <span className="flex items-center gap-2 font-semibold">
                  <Icon size={16} />
                  {tab.label}
                </span>
                <span className="mt-1 block text-xs text-slate-500">
                  {formatDate(tab.key === "summary" ? snapshot.summary_updated_at : snapshot.profile_updated_at)}
                </span>
              </button>
            );
          })}
        </div>
      </aside>

      <section className="rounded-lg border border-line bg-white p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-ink">{activeTab.label}</h2>
            <p className="mt-1 text-sm text-slate-500">{activeTab.hint}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button tone="secondary" onClick={() => void refresh()} disabled={mutations.refresh.isPending} data-testid="memory-refresh">
              {mutations.refresh.isPending ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
              从最近会话刷新
            </Button>
            <Button tone="primary" onClick={() => void save()} disabled={!hasChanges || mutations.save.isPending} data-testid="memory-save">
              {mutations.save.isPending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
              保存
            </Button>
            <Button tone="danger" onClick={() => void clear()} disabled={mutations.clear.isPending} data-testid="memory-clear">
              {mutations.clear.isPending ? <Loader2 size={16} className="animate-spin" /> : <Eraser size={16} />}
              清空
            </Button>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
          <span>{hasChanges ? "有未保存修改" : "已同步"}</span>
          <span>{wordCount} 个词</span>
          <div className="flex rounded-lg border border-line bg-canvas p-1">
            {(["edit", "preview"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => setViewMode(mode)}
                className={`min-h-8 rounded-md px-3 text-sm transition ${
                  viewMode === mode ? "bg-white text-brand-purple" : "text-slate-500 hover:text-ink"
                }`}
              >
                {mode === "edit" ? "编辑" : "预览"}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-4">
          <AnimatePresence mode="wait">
            {isLoading ? (
              <motion.div
                key="loading"
                className="flex min-h-[420px] items-center justify-center rounded-lg border border-line bg-canvas text-slate-500"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <Loader2 className="mr-2 animate-spin" size={18} />
                正在加载
              </motion.div>
            ) : viewMode === "edit" ? (
              <motion.div key="edit" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <TextArea
                  value={activeContent}
                  onChange={(event) => setDrafts((prev) => ({ ...prev, [activeFile]: event.target.value }))}
                  placeholder={activeTab.placeholder}
                  data-testid="memory-editor"
                  className="min-h-[420px] font-mono text-sm leading-6"
                />
              </motion.div>
            ) : (
              <motion.div
                key="preview"
                className="min-h-[420px] rounded-lg border border-line bg-canvas p-4"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                {activeContent.trim() ? (
                  <MarkdownRenderer>{activeContent}</MarkdownRenderer>
                ) : (
                  <EmptyState icon={<BookOpen size={24} />} title="暂无内容" description="切回编辑页补充记忆内容。" />
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </section>
    </motion.section>
  );
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

function WeakPointItem({
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

function MasteryItem({
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

function FilterButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-md border px-3 py-2 text-sm transition ${
        active ? "border-brand-purple-300 bg-tint-lavender text-brand-purple" : "border-line bg-canvas text-slate-600 hover:border-brand-purple-300"
      }`}
    >
      {children}
    </button>
  );
}

function metadataText(metadata: Record<string, unknown> | undefined, key: string) {
  const value = metadata?.[key];
  return typeof value === "string" ? value : "";
}

function metadataTextList(metadata: Record<string, unknown> | undefined, key: string) {
  const value = metadata?.[key];
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item || "").trim()).filter(Boolean).slice(0, 3);
}

function evidenceVerbLabel(value: string) {
  const map: Record<string, string> = {
    requested: "请求",
    viewed: "看过",
    saved: "保存",
    generated: "生成",
    answered: "答题",
    completed: "完成",
    planned: "规划",
    confirmed_profile: "确认画像",
    corrected_profile: "修正画像",
    rejected_profile: "否定画像",
  };
  return map[value] || value;
}

function evidenceSourceLabel(value: string) {
  const map: Record<string, string> = {
    chat: "学习对话",
    evidence: "学习记录",
    guide: "导学任务",
    guide_v2: "导学任务",
    guide_resource: "学习资源",
    guide_quiz: "练习反馈",
    notebook: "笔记本",
    question_notebook: "题库",
    profile_calibration: "画像校准",
    external_video_search: "公开视频智能体",
    math_animator: "短视频智能体",
    visualize: "图解智能体",
    deep_question: "出题智能体",
    deep_research: "研究智能体",
    deep_solve: "解题智能体",
  };
  return map[value] || value || "学习记录";
}

function resourceTypeLabel(value: string) {
  const map: Record<string, string> = {
    external_video: "公开视频",
    video: "视频",
    visual: "图解",
    quiz: "练习",
    research: "研究",
    chat: "对话",
    question: "题目",
    solve: "解题",
  };
  return map[value] || value;
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

function EvidenceItem({ item }: { item: LearnerEvidencePreview }) {
  const verb = evidenceVerbLabel(metadataText(item.metadata, "verb"));
  const resourceType = resourceTypeLabel(metadataText(item.metadata, "resource_type"));
  const sourceLabel = evidenceSourceLabel(item.source_label);
  const watchPlan = metadataTextList(item.metadata, "watch_plan");
  const reflectionPrompt = metadataText(item.metadata, "reflection_prompt");
  return (
    <article className="rounded-lg border border-line bg-canvas p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-xs font-medium text-brand-purple">{sourceLabel}</p>
          <h3 className="mt-1 font-semibold text-ink">{item.title}</h3>
        </div>
        <span className="text-xs text-slate-500">{formatDate(item.created_at)}</span>
      </div>
      {verb || resourceType ? (
        <div className="mt-2 flex flex-wrap gap-2">
          {verb ? <Badge tone="neutral">{verb}</Badge> : null}
          {resourceType ? <Badge tone={resourceType === "公开视频" || resourceType === "视频" ? "brand" : "neutral"}>{resourceType}</Badge> : null}
        </div>
      ) : null}
      {item.summary ? <p className="mt-2 text-sm leading-6 text-slate-600">{item.summary}</p> : null}
      {watchPlan.length ? (
        <div className="mt-3 rounded-md border border-brand-purple-300 bg-white px-3 py-2">
          <p className="text-xs font-medium text-brand-purple">观看计划</p>
          <ol className="mt-1 grid gap-1 text-xs leading-5 text-slate-600">
            {watchPlan.map((step, index) => (
              <li key={`${step}-${index}`}>
                {index + 1}. {step}
              </li>
            ))}
          </ol>
        </div>
      ) : null}
      {reflectionPrompt ? (
        <p className="mt-2 rounded-md border border-line bg-white px-3 py-2 text-xs leading-5 text-slate-600">
          反思问题：{reflectionPrompt}
        </p>
      ) : null}
      {item.score !== null && item.score !== undefined ? <p className="mt-2 text-xs text-slate-500">分数：{formatPercent(item.score)}</p> : null}
    </article>
  );
}

function buildProfileChangeSummary({
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

function buildLearningProgressStyle(profile: LearnerProfileSnapshot): LearningProgressStyle {
  const preferences = profile.stable_profile.preferences ?? [];
  const masteryItems = profile.learning_state.mastery ?? [];
  const weakPoints = profile.learning_state.weak_points ?? [];
  const evidenceItems = profile.evidence_preview ?? [];
  const calibrationCount = Number(profile.data_quality.calibration_count ?? 0);
  const confidence = clampScore(profile.confidence ?? 0);
  const accuracy = clampScore(profile.overview.assessment_accuracy ?? 0);
  const masteryAverage = masteryItems.length
    ? clampScore(masteryItems.reduce((sum, item) => sum + clampScore(item.score ?? 0), 0) / masteryItems.length)
    : 0;
  const scoredEvidence = evidenceItems.filter((item) => item.score !== null && item.score !== undefined);
  const evidenceAverage = scoredEvidence.length
    ? clampScore(scoredEvidence.reduce((sum, item) => sum + clampScore(item.score ?? 0), 0) / scoredEvidence.length)
    : 0;

  const prefersPractice = preferences.some((item) => /practice|练习|题/.test(item));
  const prefersVisual = preferences.some((item) => /visual|图解|图|示意/.test(item));
  const prefersVideo = preferences.some((item) => /video|视频/.test(item));

  let label = "渐进压实型";
  let summary = "你现在更像是先获得一个大致理解，再通过练习、反馈和补强把知识一点点压实。";

  if (prefersPractice && accuracy >= 0.55 && masteryAverage >= 0.5) {
    label = "练习驱动型";
    summary = "你更适合边做边学。系统大多可以先给你练习或任务，再根据结果快速校准讲解深浅。";
  } else if (prefersVisual && weakPoints.length > 0) {
    label = "概念澄清型";
    summary = "你更像是先把结构和边界看清楚，再进入练习。系统适合优先给你图解、关系图和最小例子。";
  } else if (prefersVideo && confidence >= 0.55 && weakPoints.length <= 1) {
    label = "快速串联型";
    summary = "当基础已经够用时，你更适合先用短视频或分步讲解把流程串起来，再回到任务区完成验证。";
  } else if (calibrationCount >= 2 && confidence < 0.55) {
    label = "反复校准型";
    summary = "你的学习路径更依赖持续校准。系统需要通过更多反馈、反思和短测，逐步把判断收敛到更准。";
  }

  const signals: LearningProgressStyle["signals"] = [
    {
      label: "起步方式",
      detail: prefersPractice
        ? "当前偏好更接近“先做再调”。"
        : prefersVisual
          ? "当前偏好更接近“先看懂结构再动手”。"
          : prefersVideo
            ? "当前偏好更接近“先串流程再进入任务”。"
            : "系统目前观察到你会在讲解、练习和反馈之间交替推进。",
      tone: prefersPractice || prefersVisual || prefersVideo ? "brand" : "warning",
    },
    {
      label: "稳定程度",
      detail:
        masteryItems.length > 0
          ? `当前掌握跟踪均值约 ${Math.round(masteryAverage * 100)}%，说明你的推进已经开始从“看过”转向“会做”。`
          : "掌握度证据还不够多，系统仍在观察你更适合哪种推进节奏。",
      tone: masteryAverage >= 0.7 ? "success" : masteryAverage >= 0.45 ? "brand" : "warning",
    },
    {
      label: "反馈习惯",
      detail:
        calibrationCount > 0 || scoredEvidence.length > 0
          ? `你已经留下了 ${Math.max(calibrationCount, scoredEvidence.length)} 组可用于调节路线的反馈信号。`
          : "当前主动反馈还不多，后续多提交反思和评分会让系统更快学会你的节奏。",
      tone: calibrationCount >= 2 || scoredEvidence.length >= 3 ? "success" : "brand",
    },
  ];

  const suggestions = [
    prefersPractice
      ? "在导学里优先把“做练习”或“完成当前任务”放到更前面。"
      : prefersVisual
        ? "在卡点明显时，先给你图解或概念关系图，再进入题目。"
        : prefersVideo
          ? "在基础够用时，优先给你短视频或分步讲解，减少进入任务前的阻力。"
          : "先保持轻量资源 + 短任务的节奏，继续观察你更稳定的推进方式。",
    weakPoints.length > 0
      ? `当前仍要优先照顾「${weakPoints.slice(0, 2).map((item) => item.label).join("、")}」这类卡点。`
      : "当前没有明显堆积的薄弱点，可以把更多精力放到连续推进上。",
    evidenceAverage > 0
      ? `最近证据强度约为 ${Math.round(evidenceAverage * 100)}%，继续留下清晰反馈能让路线越走越顺。`
      : "接下来多完成一两次带评分的练习，这块风格判断会更稳。",
  ];

  return {
    label,
    summary,
    confidenceText: profileConfidenceLabel(confidence, accuracy),
    signals,
    suggestions,
    recentShift: buildRecentProgressShift(profile, label),
  };
}

function buildRecentProgressShift(profile: LearnerProfileSnapshot, styleLabel: string): LearningProgressStyle["recentShift"] {
  const recentEvidence = (profile.evidence_preview ?? []).slice(0, 5);
  if (!recentEvidence.length) return null;

  const scores = recentEvidence
    .map((item) => (typeof item.score === "number" ? clampScore(item.score) : null))
    .filter((item): item is number => item !== null);
  const averageScore = scores.length ? scores.reduce((sum, item) => sum + item, 0) / scores.length : null;
  const recentText = recentEvidence.map((item) => `${item.source_label} ${item.title} ${item.summary || ""}`).join(" ");
  const hasCalibration = /校准|画像|profile/i.test(recentText);
  const hasQuiz = /练习|答题|quiz|题目/i.test(recentText);
  const hasResource = /图解|视频|资源|visual|video/i.test(recentText);

  const cues = [
    hasQuiz ? "最近有练习反馈" : "",
    hasCalibration ? "最近有显式校准" : "",
    hasResource ? "最近有资源使用" : "",
    averageScore !== null ? `最近证据均值约 ${Math.round(averageScore * 100)}%` : "",
  ].filter(Boolean);

  if (hasCalibration || (averageScore !== null && averageScore < 0.6)) {
    return {
      label: "最近更像在修正路径",
      direction: "correcting",
      summary: "最近几条学习证据说明，系统仍在边学边修正你的路线。当前更适合先补清、再确认，而不是直接快推。",
      cues,
    };
  }

  if (averageScore !== null && averageScore >= 0.78 && hasQuiz) {
    return {
      label: "最近正在变稳",
      direction: "stable",
      summary: `最近几次练习和任务证据已经比较稳定，说明你这段时间的「${styleLabel}」开始真正站住了。`,
      cues,
    };
  }

  if (hasResource && hasQuiz && averageScore !== null && averageScore >= 0.62) {
    return {
      label: "最近开始提速",
      direction: "accelerating",
      summary: `最近的资源使用和练习反馈衔接得更顺，系统判断你可以在现有「${styleLabel}」基础上稍微加快一点节奏。`,
      cues,
    };
  }

  return {
    label: "最近仍在继续观察",
    direction: "observing",
    summary: "最近证据还在持续积累中。系统已经能看出你大致适合的学习方式，但还在观察哪种节奏最稳。",
    cues,
  };
}

function clampScore(value: number) {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(1, value));
}
