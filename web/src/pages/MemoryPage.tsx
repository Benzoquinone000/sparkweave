import { useLocation } from "@tanstack/react-router";
import { motion } from "framer-motion";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Database,
  Edit3,
  Loader2,
  RefreshCw,
  Target,
  UserRound,
} from "lucide-react";
import { lazy, Suspense, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { TextInput } from "@/components/ui/Field";
import {
  useLearnerProfile,
  useLearnerProfileMutations,
  useMemory,
  useMemoryMutations,
} from "@/hooks/useApiQueries";
import type { LearnerProfileSnapshot } from "@/lib/types";
import { formatPercent } from "./memory/memoryDisplayUtils";
import { LearnerProfileVisualMap } from "./memory/LearnerProfileVisualMap";
import { buildNextActionHref } from "./memory/profileGuideLinks";
import type { CalibrateProfile } from "./memory/profileTypes";

type MemoryPageMode = "overview" | "evidence" | "edit";

const EvidencePanel = lazy(() => import("./memory/EvidencePanel").then((module) => ({ default: module.EvidencePanel })));
const MemoryEditor = lazy(() => import("./memory/MemoryEditor").then((module) => ({ default: module.MemoryEditor })));

const ROUTES: Array<{
  mode: MemoryPageMode;
  href: string;
  label: string;
  helper: string;
  icon: typeof Target;
  testId: string;
}> = [
  {
    mode: "overview",
    href: "/memory",
    label: "概览",
    helper: "只看下一步",
    icon: UserRound,
    testId: "learner-profile-tab-profile",
  },
  {
    mode: "evidence",
    href: "/memory/evidence",
    label: "依据",
    helper: "查看判断来源",
    icon: Database,
    testId: "learner-profile-tab-evidence",
  },
  {
    mode: "edit",
    href: "/memory/edit",
    label: "补充",
    helper: "修正长期信息",
    icon: BookOpen,
    testId: "learner-profile-tab-memory",
  },
];

export function MemoryPage() {
  const pathname = useLocation({ select: (location) => location.pathname });
  const mode = getMemoryMode(pathname);
  const [notice, setNotice] = useState("");
  const [quickCorrection, setQuickCorrection] = useState("");
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
    setNotice("");
    await profileMutations.refresh.mutateAsync({ force: true });
    setNotice("画像已重新整理。");
  };

  const calibrateProfile: CalibrateProfile = async (input) => {
    const result = await profileMutations.calibrate.mutateAsync(input);
    const focus = result.profile?.overview?.current_focus?.trim();
    if (input.action === "confirm") {
      setNotice("已确认。系统会更放心地按这个方向安排学习。");
      return;
    }
    setNotice(focus ? `已记录修正，当前重点：${focus}` : "已记录修正。");
  };

  const submitQuickCorrection = async () => {
    const next = quickCorrection.trim();
    if (!next || !profile.data) return;
    setNotice("");
    await calibrateProfile({
      action: "correct",
      claim_type: "profile_overview",
      value: [profile.data.overview.current_focus, profile.data.overview.summary].filter(Boolean).join("\n"),
      corrected_value: next,
      note: "Quick correction from learner profile overview",
      source_id: "profile_overview",
    });
    setQuickCorrection("");
  };

  const confirmOverview = async () => {
    if (!profile.data) return;
    setNotice("");
    await calibrateProfile({
      action: "confirm",
      claim_type: "profile_overview",
      value: [profile.data.overview.current_focus, profile.data.overview.summary].filter(Boolean).join("\n"),
      note: "Quick confirmation from learner profile overview",
      source_id: "profile_overview",
    });
  };

  return (
    <div className="h-full overflow-y-auto px-3.5 py-3.5 pb-20 lg:px-4 lg:pb-4">
      <div className="mx-auto flex min-h-full max-w-[1080px] flex-col gap-3.5">
        <MemoryHeader mode={mode} refreshing={profileMutations.refresh.isPending} onRefresh={() => void refreshProfile()} />
        <MemoryRouteNav activeMode={mode} />

        <div className="min-h-0 flex-1">
          {mode === "overview" ? (
            <MemoryOverview
              profile={profile.data}
              isLoading={profile.isLoading}
              isError={profile.isError}
              refreshing={profileMutations.refresh.isPending}
              calibrating={profileMutations.calibrate.isPending}
              notice={notice}
              quickCorrection={quickCorrection}
              onQuickCorrectionChange={setQuickCorrection}
              onRefresh={() => void refreshProfile()}
              onConfirm={() => void confirmOverview()}
              onSubmitCorrection={() => void submitQuickCorrection()}
            />
          ) : null}

          {mode === "evidence" ? (
            <div className="h-full overflow-y-auto pr-1">
              <Suspense fallback={<RouteLoading label="正在准备画像依据" />}>
                <EvidencePanel profile={profile.data} />
              </Suspense>
            </div>
          ) : null}

          {mode === "edit" ? (
            <div className="h-full overflow-y-auto pr-1">
              <Suspense fallback={<RouteLoading label="正在准备手动补充" />}>
                <MemoryEditor key={snapshotKey} snapshot={snapshot} isLoading={memory.isLoading} mutations={memoryMutations} />
              </Suspense>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function MemoryHeader({
  mode,
  refreshing,
  onRefresh,
}: {
  mode: MemoryPageMode;
  refreshing: boolean;
  onRefresh: () => void;
}) {
  const copy = {
    overview: {
      eyebrow: "学习画像",
      title: "先看系统建议你做什么",
      detail: "默认页只保留当前建议和最少依据。想看证据或手动补充，进入对应页面。",
    },
    evidence: {
      eyebrow: "画像依据",
      title: "这些判断从哪里来",
      detail: "这里单独查看证据，不和行动建议混在一起。",
    },
    edit: {
      eyebrow: "手动补充",
      title: "修正长期记忆",
      detail: "只在需要时补目标、偏好或背景，不打断主学习流程。",
    },
  }[mode];

  return (
    <motion.header
      className="rounded-lg border border-line bg-white/90 px-3.5 py-2.5 shadow-[0_1px_2px_rgba(15,15,15,0.025)]"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          {mode !== "overview" ? (
            <a
              href="/memory"
              className="mb-2 inline-flex items-center gap-1 text-xs font-semibold text-slate-500 transition hover:text-brand-purple"
            >
              <ArrowLeft size={14} />
              返回概览
            </a>
          ) : null}
          <p className="text-xs font-semibold text-brand-orange">{copy.eyebrow}</p>
          <h1 className="mt-1 text-xl font-semibold leading-tight text-ink">{copy.title}</h1>
          <p className="mt-1 max-w-2xl text-xs leading-5 text-slate-600">{copy.detail}</p>
        </div>
        <Button tone="secondary" onClick={onRefresh} disabled={refreshing} data-testid="learner-profile-refresh">
          {refreshing ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
          重新整理
        </Button>
      </div>
    </motion.header>
  );
}

function MemoryRouteNav({ activeMode }: { activeMode: MemoryPageMode }) {
  return (
    <nav className="grid gap-2 sm:grid-cols-3" aria-label="学习画像页面">
      {ROUTES.map((route) => {
        const Icon = route.icon;
        const active = activeMode === route.mode;
        return (
          <a
            key={route.mode}
            href={route.href}
            data-testid={route.testId}
            className={`dt-interactive rounded-lg border px-3 py-2 transition ${
              active
                ? "border-ink bg-white text-ink shadow-[0_1px_2px_rgba(15,15,15,0.04)]"
                : "border-line bg-white/72 text-slate-600 hover:border-line-strong hover:bg-white hover:text-ink"
            }`}
          >
            <span className="flex items-center gap-2 text-sm font-semibold">
              <Icon size={16} />
              {route.label}
            </span>
            <span className="mt-0.5 block text-xs text-slate-500">{route.helper}</span>
          </a>
        );
      })}
    </nav>
  );
}

function MemoryOverview({
  profile,
  isLoading,
  isError,
  refreshing,
  calibrating,
  notice,
  quickCorrection,
  onQuickCorrectionChange,
  onRefresh,
  onConfirm,
  onSubmitCorrection,
}: {
  profile?: LearnerProfileSnapshot;
  isLoading: boolean;
  isError: boolean;
  refreshing: boolean;
  calibrating: boolean;
  notice: string;
  quickCorrection: string;
  onQuickCorrectionChange: (value: string) => void;
  onRefresh: () => void;
  onConfirm: () => void;
  onSubmitCorrection: () => void;
}) {
  if (isLoading) {
    return <RouteLoading label="正在读取学习画像" />;
  }

  if (isError || !profile) {
    return (
      <section className="rounded-lg border border-line bg-white p-6">
        <EmptyState
          icon={<AlertCircle size={24} />}
          title="画像暂时不可用"
          description="可以先重新整理一次，系统会从现有学习证据聚合画像。"
          action={
            <Button tone="primary" onClick={onRefresh} disabled={refreshing}>
              {refreshing ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
              重新生成
            </Button>
          }
        />
      </section>
    );
  }

  const nextAction = profile.next_action;
  const weakPoint = profile.learning_state.weak_points?.[0];
  const preferred = preferenceLabel(profile.stable_profile.preferences?.[0] || "");
  const primaryTitle = nextAction?.title?.trim() || profile.overview.current_focus || "先完成一次导学或练习";
  const primarySummary =
    nextAction?.summary?.trim() ||
    profile.overview.summary ||
    "系统会根据导学、练习和笔记证据，逐步整理出更准确的学习重点。";
  const primaryActionHref = nextAction ? buildNextActionHref(nextAction) : "/guide?new=1";
  const primaryActionLabel = nextAction?.primary_label?.trim() || "进入导学";
  return (
    <motion.div
      className="grid gap-4 lg:grid-cols-[minmax(0,1.35fr)_minmax(292px,0.62fr)]"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      <section
        className="flex flex-col rounded-lg border border-line bg-white p-4 shadow-[0_8px_26px_rgba(15,15,15,0.035)]"
        data-testid="learner-profile-overview"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase text-steel">现在只做这一件事</p>
            <h2 className="mt-2 text-xl font-semibold leading-tight text-ink">{primaryTitle}</h2>
          </div>
          <span className="rounded-md border border-line bg-surface px-2.5 py-1 text-xs font-medium text-slate-600">
            可信 {formatPercent(profile.confidence)}
          </span>
        </div>
        <p className="mt-2.5 max-w-3xl text-xs leading-5 text-slate-600">{primarySummary}</p>

        <LearnerProfileVisualMap profile={profile} />

        <DecisionPath focus={profile.overview.current_focus} weakPoint={weakPoint?.label} action={primaryActionLabel} />

        <div className="mt-4 flex flex-wrap gap-2">
          <a
            href={primaryActionHref}
            data-testid="learner-profile-primary-action"
            className="dt-interactive inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-brand-purple bg-brand-purple px-3.5 text-sm font-medium text-white hover:bg-brand-purple-800"
          >
            {primaryActionLabel}
            <ArrowRight size={16} />
          </a>
          <Button type="button" tone="secondary" onClick={onConfirm} disabled={calibrating} data-testid="learner-profile-confirm-overview">
            {calibrating ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
            判断准确
          </Button>
        </div>

        <form
          className="mt-5 border-t border-line-soft pt-5"
          data-testid="learner-profile-correction-form"
          onSubmit={(event) => {
            event.preventDefault();
            onSubmitCorrection();
          }}
        >
          <label className="text-sm font-semibold text-ink" htmlFor="profile-quick-correction">
            不准？一句话改掉
          </label>
          <div className="mt-2 grid gap-2 md:grid-cols-[minmax(0,1fr)_auto]">
            <TextInput
              id="profile-quick-correction"
              value={quickCorrection}
              onChange={(event) => onQuickCorrectionChange(event.target.value)}
              placeholder="例如：我主要卡在公式含义，不是基础概念。"
            />
            <Button type="submit" tone="primary" disabled={calibrating || !quickCorrection.trim()}>
              {calibrating ? <Loader2 size={16} className="animate-spin" /> : <Edit3 size={16} />}
              保存
            </Button>
          </div>
          {notice ? (
            <p className="mt-2 text-xs font-medium text-brand-purple" data-testid="learner-profile-notice">
              {notice}
            </p>
          ) : null}
        </form>
      </section>

      <aside className="rounded-lg border border-line bg-white/86 p-4 shadow-[0_1px_2px_rgba(15,15,15,0.025)]">
        <div className="flex items-center justify-between gap-3 border-b border-line-soft pb-3">
          <div>
            <p className="text-sm font-semibold text-ink">画像信号</p>
            <p className="mt-0.5 text-xs text-steel">只保留会影响下一步的判断</p>
          </div>
          <span className="rounded-md bg-surface px-2 py-1 text-xs font-medium text-slate-500">
            {profile.data_quality.evidence_count ?? 0} 条证据
          </span>
        </div>
        <div className="divide-y divide-line-soft">
          <SignalRow icon={<Target size={16} />} label="当前重点" value={profile.overview.current_focus || "等待更多学习证据"} />
          <SignalRow icon={<AlertCircle size={16} />} label="优先卡点" value={weakPoint?.label || "还没有明显薄弱点"} />
          <SignalRow
          icon={<BookOpen size={17} />}
          label="你的学习推进方式"
          value={`系统接下来会优先${preferred ? `使用${preferred}` : "用图解和低门槛练习"}推进。`}
          testId="learner-progress-style-card"
        />
        </div>
        <a
          href="/memory/evidence"
          className="dt-interactive mt-4 flex items-center justify-between gap-3 rounded-lg border border-line bg-surface px-3 py-3 text-sm transition hover:border-line-strong hover:bg-white hover:text-ink"
        >
          <span>
            <span className="flex items-center gap-2 font-semibold">
              <Database size={16} />
              看判断依据
            </span>
            <span className="mt-1 block text-xs text-steel">单独打开证据页</span>
          </span>
          <ArrowRight size={16} className="text-steel" />
        </a>
      </aside>
    </motion.div>
  );
}

function DecisionPath({ focus, weakPoint, action }: { focus?: string; weakPoint?: string; action: string }) {
  const items = [
    { label: "目标", value: focus || "先形成学习证据" },
    { label: "判断", value: weakPoint || "暂无明显卡点" },
    { label: "行动", value: action },
  ];
  return (
    <div className="mt-5 grid overflow-hidden rounded-lg border border-line bg-surface sm:grid-cols-3">
      {items.map((item, index) => (
        <div key={item.label} className="relative min-w-0 border-b border-line px-3 py-3 last:border-b-0 sm:border-b-0 sm:border-r sm:last:border-r-0">
          <p className="text-[11px] font-semibold uppercase text-steel">{item.label}</p>
          <p className="mt-1 line-clamp-2 text-sm font-medium leading-5 text-charcoal">{item.value}</p>
          {index < items.length - 1 ? <ArrowRight className="absolute right-2 top-3 hidden text-slate-300 sm:block" size={14} /> : null}
        </div>
      ))}
    </div>
  );
}

function SignalRow({ icon, label, value, testId }: { icon: ReactNode; label: string; value: string; testId?: string }) {
  return (
    <div className="flex gap-3 py-3" data-testid={testId}>
      <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-md border border-line bg-surface text-slate-500">{icon}</span>
      <div className="min-w-0">
        <p className="text-sm font-semibold text-ink">{label}</p>
        <p className="mt-1 line-clamp-2 text-sm leading-5 text-slate-600">{value}</p>
      </div>
    </div>
  );
}

function RouteLoading({ label }: { label: string }) {
  return (
    <section className="rounded-lg border border-line bg-white/82 p-4">
      <p className="text-sm font-semibold text-ink">{label}</p>
      <div className="mt-3 space-y-2">
        <span className="block h-3 w-44 max-w-full rounded bg-slate-100" />
        <span className="block h-16 rounded bg-slate-100/80" />
        <span className="block h-16 rounded bg-slate-100/60" />
      </div>
    </section>
  );
}

function preferenceLabel(value: string) {
  const normalized = String(value || "").trim();
  const lowered = normalized.toLowerCase();
  if (lowered === "external_video" || lowered === "public_video") return "公开视频";
  if (lowered === "external_image" || lowered === "public_image") return "公开图片";
  if (lowered === "short_video" || lowered === "video") return "短视频";
  if (lowered === "visual") return "图解";
  if (lowered === "practice") return "练习";
  if (lowered === "quiz") return "互动练习";
  return normalized;
}

function getMemoryMode(pathname: string): MemoryPageMode {
  if (pathname.endsWith("/evidence")) return "evidence";
  if (pathname.endsWith("/edit")) return "edit";
  return "overview";
}
