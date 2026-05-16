import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, BookOpen, Brain, Database, Loader2, RefreshCw, UserRound } from "lucide-react";
import { lazy, Suspense, useState } from "react";

import { Button } from "@/components/ui/Button";
import { PeopleAccent } from "@/components/ui/PeopleAccent";
import {
  useLearnerProfile,
  useLearnerProfileMutations,
  useMemory,
  useMemoryMutations,
} from "@/hooks/useApiQueries";
import type { ProfileChangeSummary } from "./memory/profileChangeSummary";
import type { CalibrateProfile } from "./memory/profileTypes";

type PageTab = "profile" | "evidence" | "memory";

const PAGE_TABS: Array<{ key: PageTab; label: string; helper: string; icon: typeof Brain }> = [
  { key: "profile", label: "概览", helper: "先看下一步", icon: UserRound },
  { key: "evidence", label: "依据", helper: "为什么这样判断", icon: Database },
  { key: "memory", label: "补充", helper: "手动修正画像", icon: BookOpen },
];

const EvidencePanel = lazy(() => import("./memory/EvidencePanel").then((module) => ({ default: module.EvidencePanel })));
const MemoryEditor = lazy(() => import("./memory/MemoryEditor").then((module) => ({ default: module.MemoryEditor })));
const ProfilePanel = lazy(() => import("./memory/ProfilePanel").then((module) => ({ default: module.ProfilePanel })));

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
    const { buildProfileChangeSummary } = await import("./memory/profileChangeSummary");
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
    const { buildProfileChangeSummary } = await import("./memory/profileChangeSummary");
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
                <PeopleAccent name="learner_profile" className="absolute bottom-[-24px] right-[-18px] h-44 w-52 opacity-90" />
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
            <Suspense key="profile" fallback={<MemoryTabLoading label="正在准备画像概览" />}>
              <ProfilePanel
                profile={profile.data}
                changeSummary={changeSummary}
                isLoading={profile.isLoading}
                isError={profile.isError}
                onRefresh={() => void refreshProfile()}
                refreshing={profileMutations.refresh.isPending}
                onCalibrate={calibrateProfile}
                calibrating={profileMutations.calibrate.isPending}
              />
            </Suspense>
          ) : null}
          {activeTab === "evidence" ? (
            <Suspense key="evidence" fallback={<MemoryTabLoading label="正在准备画像依据" />}>
              <EvidencePanel profile={profile.data} />
            </Suspense>
          ) : null}
          {activeTab === "memory" ? (
            <Suspense key="memory" fallback={<MemoryTabLoading label="正在准备手动补充" />}>
              <MemoryEditor
                key={snapshotKey}
                snapshot={snapshot}
                isLoading={memory.isLoading}
                mutations={memoryMutations}
              />
            </Suspense>
          ) : null}
        </AnimatePresence>
      </div>
    </div>
  );
}

function MemoryTabLoading({ label }: { label: string }) {
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
