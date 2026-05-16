import {
  AudioLines,
  BrainCircuit,
  CheckCircle2,
  FileSearch,
  GraduationCap,
  Image,
  Loader2,
  MessageSquareText,
  Route,
  Search,
  Sparkles,
  Target,
  Video,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import {
  effectStatusTone,
  guideDisplayText,
  preflightStatusLabel,
  preflightStatusTone,
  submissionStatusLabel,
  submissionStatusTone,
  type GuideTone,
} from "@/lib/guideDisplay";
import type { GuideV2CoursePackage } from "@/lib/types";
import { ProgressBar } from "./GuideMetrics";

type CompetitionRequirementView = {
  id: string;
  label: string;
  status?: string;
  evidence: string;
  action: string;
};

type LoopNode = {
  id: string;
  label: string;
  metric: string;
  detail: string;
  tone: GuideTone;
  icon: LucideIcon;
};

type IflytekNode = {
  id: string;
  label: string;
  role: string;
  status: "used" | "wired" | "available";
  evidence: string;
  icon: LucideIcon;
};

const FALLBACK_REQUIREMENTS = [
  "对话式学习画像自主构建",
  "多智能体协同的资源生成",
  "个性化学习路径规划和资源推送",
  "智能辅导",
  "学习效果评估",
];

export function CompetitionDemoDashboard({
  coursePackage,
  loading,
}: {
  coursePackage: GuideV2CoursePackage | null;
  loading: boolean;
}) {
  const alignment = coursePackage?.competition_alignment ?? null;
  const preflight = coursePackage?.demo_preflight ?? null;
  const report = coursePackage?.learning_report ?? null;
  const behavior = report?.behavior_summary ?? {};
  const requirements = buildRequirementViews(alignment);
  const readyCount =
    Number(alignment?.ready_count ?? requirements.filter((item) => String(item.status || "").toLowerCase() === "ready").length) || 0;
  const totalCount = Number(alignment?.total_count ?? requirements.length) || requirements.length;
  const coverageScore = normalizeScore(alignment?.coverage_score ?? preflight?.score ?? coursePackage?.demo_blueprint?.readiness_score ?? 0);
  const dashboardTone = coverageScore >= 85 ? "success" : coverageScore >= 65 ? "brand" : coverageScore > 0 ? "warning" : "neutral";
  const loopNodes = buildLoopNodes(coursePackage);
  const iflytekNodes = buildIflytekNodes(coursePackage);
  const headline = guideDisplayText(
    alignment?.summary || coursePackage?.summary,
    "用一条学习闭环证明画像、路径、资源、辅导和评估都已经连起来。",
  );
  const nextAction = guideDisplayText(
    preflight?.primary_gap?.action || alignment?.primary_gap?.demo_action || preflight?.next_action || alignment?.next_action,
    "按画像、路线、资源、练习、报告的顺序录制 7 分钟演示。",
  );

  return (
    <section
      className="mt-4 overflow-hidden rounded-lg border border-brand-purple-300 bg-white shadow-sm"
      data-testid="competition-demo-dashboard"
    >
      <div className="border-b border-line bg-tint-lavender p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="brand">评委模式</Badge>
              <Badge tone={dashboardTone}>{coverageScore ? `证明分 ${coverageScore}` : "等待证据"}</Badge>
              {preflight?.status ? (
                <Badge tone={preflightStatusTone(preflight.status)}>{preflightStatusLabel(preflight.status)}</Badge>
              ) : null}
            </div>
            <h3 className="mt-3 text-xl font-semibold text-ink">比赛演示驾驶舱</h3>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-charcoal">{headline}</p>
          </div>
          <div className="min-w-[180px] rounded-lg border border-white/80 bg-white p-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-semibold text-slate-500">赛题覆盖</p>
              {loading ? <Loader2 size={14} className="animate-spin text-brand-purple" /> : <CheckCircle2 size={15} className="text-brand-purple" />}
            </div>
            <p className="mt-2 text-2xl font-semibold text-ink">
              {readyCount}
              <span className="text-sm font-medium text-slate-400">/{totalCount}</span>
            </p>
            <ProgressBar value={coverageScore} className="mt-2" />
          </div>
        </div>
      </div>

      <div className="grid gap-4 p-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(300px,0.9fr)]">
        <div className="space-y-4">
          <div>
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-semibold text-ink">赛题五项证明</p>
              <span className="text-xs text-slate-400">截图时先讲这里</span>
            </div>
            <div className="mt-3 grid gap-2 md:grid-cols-5">
              {requirements.map((item, index) => (
                <CompetitionRequirementCard key={item.id} item={item} index={index} />
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-line bg-canvas p-3" data-testid="competition-loop-rail">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-sm font-semibold text-ink">学习闭环轨道</p>
                <p className="mt-1 text-xs leading-5 text-slate-500">目标进入系统后，每一步都留下证据，再推动下一步调整。</p>
              </div>
              <Badge tone={Number(behavior.path_adjustment_count ?? 0) > 0 ? "success" : "brand"}>
                动态调整 {Number(behavior.path_adjustment_count ?? 0)}
              </Badge>
            </div>
            <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
              {loopNodes.map((node, index) => (
                <LoopRailNode key={node.id} node={node} index={index} isLast={index === loopNodes.length - 1} />
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-lg border border-line bg-white p-3" data-testid="competition-iflytek-strip">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="text-sm font-semibold text-ink">讯飞能力证明条</p>
                <p className="mt-1 text-xs leading-5 text-slate-500">把模型、检索、识别、搜索和语音合成放回学习闭环里讲。</p>
              </div>
              <Badge tone="brand">工具链</Badge>
            </div>
            <div className="mt-3 grid gap-2">
              {iflytekNodes.map((node) => (
                <IflytekCapabilityRow key={node.id} node={node} />
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-line bg-canvas p-3">
            <div className="flex items-start gap-3">
              <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-white text-brand-purple">
                <Video size={17} />
              </span>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-ink">录屏下一步</p>
                <p className="mt-1 text-xs leading-5 text-slate-600">{nextAction}</p>
              </div>
            </div>
            <div className="mt-3 grid grid-cols-3 gap-2 text-center">
              <DashboardMiniMetric label="资源" value={Number(behavior.resource_count ?? coursePackage?.portfolio?.length ?? 0)} />
              <DashboardMiniMetric label="练习" value={Number(behavior.quiz_attempt_count ?? 0)} />
              <DashboardMiniMetric label="证据" value={Number(behavior.evidence_count ?? behavior.event_count ?? 0)} />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function CompetitionRequirementCard({
  item,
  index,
}: {
  item: CompetitionRequirementView;
  index: number;
}) {
  const statusTone = submissionStatusTone(item.status);
  return (
    <div className="min-w-0 rounded-lg border border-line bg-white p-2" data-testid="competition-requirement-card">
      <div className="flex items-center justify-between gap-2">
        <span className="grid h-6 w-6 shrink-0 place-items-center rounded-md bg-tint-lavender text-xs font-semibold text-brand-purple">
          {index + 1}
        </span>
        <Badge tone={statusTone}>{submissionStatusLabel(item.status)}</Badge>
      </div>
      <p className="mt-2 min-h-10 text-xs font-semibold leading-5 text-ink">{item.label}</p>
      <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{item.evidence}</p>
      <p className="mt-2 line-clamp-1 text-[11px] leading-4 text-steel">录屏：{item.action}</p>
    </div>
  );
}

function LoopRailNode({
  node,
  index,
  isLast,
}: {
  node: LoopNode;
  index: number;
  isLast: boolean;
}) {
  const Icon = node.icon;
  return (
    <div className="flex shrink-0 items-center gap-2">
      <div className="w-[150px] rounded-lg border border-line bg-white p-3">
        <div className="flex items-center justify-between gap-2">
          <span className={`grid size-8 place-items-center rounded-lg ${nodeToneClass(node.tone)}`}>
            <Icon size={15} />
          </span>
          <span className="text-xs font-semibold text-slate-400">0{index + 1}</span>
        </div>
        <p className="mt-2 text-sm font-semibold text-ink">{node.label}</p>
        <p className="mt-1 text-xs font-semibold text-brand-purple">{node.metric}</p>
        <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{node.detail}</p>
      </div>
      {!isLast ? <span className="text-slate-300">→</span> : null}
    </div>
  );
}

function IflytekCapabilityRow({ node }: { node: IflytekNode }) {
  const Icon = node.icon;
  return (
    <div className="grid grid-cols-[2rem_minmax(0,1fr)_auto] items-center gap-2 rounded-lg border border-line bg-canvas px-3 py-2">
      <span className="grid size-8 place-items-center rounded-lg bg-white text-brand-purple">
        <Icon size={15} />
      </span>
      <span className="min-w-0">
        <span className="block truncate text-xs font-semibold text-ink">{node.label}</span>
        <span className="mt-0.5 block truncate text-xs text-slate-500">{node.role}</span>
        <span className="mt-0.5 block truncate text-[11px] text-steel">{node.evidence}</span>
      </span>
      <Badge tone={iflytekTone(node.status)}>{iflytekStatusLabel(node.status)}</Badge>
    </div>
  );
}

function DashboardMiniMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-line bg-white px-2 py-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-base font-semibold text-ink">{Number.isFinite(value) ? value : 0}</p>
    </div>
  );
}

function buildRequirementViews(alignment: GuideV2CoursePackage["competition_alignment"] | null): CompetitionRequirementView[] {
  const source = alignment?.requirements?.length ? alignment.requirements : [];
  const items = source.length
    ? source.map((item, index) => ({
        id: item.id || `requirement-${index}`,
        label: guideDisplayText(item.requirement, FALLBACK_REQUIREMENTS[index] || "赛题要求"),
        status: item.status,
        evidence: guideDisplayText((item.evidence ?? []).find(Boolean), "等待当前课程产物补齐证据。"),
        action: guideDisplayText(item.demo_action, "指向当前页面证据，用一句话说明这一项已经闭环。"),
      }))
    : FALLBACK_REQUIREMENTS.map((label, index) => ({
        id: `fallback-${index}`,
        label,
        status: "todo",
        evidence: "生成课程产出包后会显示对应证据。",
        action: "先跑通稳定演示路线。",
      }));

  return items.slice(0, 5);
}

function buildLoopNodes(coursePackage: GuideV2CoursePackage | null): LoopNode[] {
  const report = coursePackage?.learning_report ?? null;
  const behavior = report?.behavior_summary ?? {};
  const style = coursePackage?.learning_style ?? coursePackage?.demo_blueprint?.learning_style ?? null;
  const portfolioCount = coursePackage?.portfolio?.length ?? 0;
  const resourceCount = Number(behavior.resource_count ?? portfolioCount);
  const quizCount = Number(behavior.quiz_attempt_count ?? 0);
  const evidenceCount = Number(behavior.evidence_count ?? behavior.event_count ?? 0);
  const score = normalizeScore(report?.effect_assessment?.score ?? report?.overall_score ?? 0);
  const nextAction = report?.next_actions?.[0] || coursePackage?.demo_preflight?.next_action || "";

  return [
    {
      id: "profile",
      label: "学习画像",
      metric: style?.label || `${Number(behavior.profile_update_count ?? 0)} 次更新`,
      detail: guideDisplayText(style?.summary || style?.signals?.[0]?.value, "汇总目标、薄弱点、偏好和最近证据。"),
      tone: style ? "brand" : "neutral",
      icon: BrainCircuit,
    },
    {
      id: "path",
      label: "路径规划",
      metric: `${Number(behavior.path_adjustment_count ?? 0)} 次调整`,
      detail: guideDisplayText(coursePackage?.demo_blueprint?.storyline?.[0]?.show || coursePackage?.summary, "把目标压缩成当前任务和录屏路线。"),
      tone: Number(behavior.path_adjustment_count ?? 0) > 0 ? "success" : "brand",
      icon: Route,
    },
    {
      id: "resource",
      label: "资源生成",
      metric: `${resourceCount} 个资源`,
      detail: guideDisplayText(coursePackage?.portfolio?.[0]?.summary || coursePackage?.demo_seed_pack?.sample_artifacts?.[0]?.preview, "围绕当前任务生成图解、视频或练习。"),
      tone: resourceCount > 0 ? "success" : "neutral",
      icon: Sparkles,
    },
    {
      id: "tutor",
      label: "智能辅导",
      metric: coursePackage?.agent_collaboration_blueprint?.roles?.length
        ? `${coursePackage.agent_collaboration_blueprint.roles.length} 个角色`
        : "多模态讲解",
      detail: guideDisplayText(coursePackage?.agent_collaboration_blueprint?.summary, "画像、检索、图解、出题和评估智能体接力。"),
      tone: coursePackage?.agent_collaboration_blueprint ? "brand" : "neutral",
      icon: MessageSquareText,
    },
    {
      id: "feedback",
      label: "练习反馈",
      metric: `${quizCount} 次练习`,
      detail: guideDisplayText(report?.recent_timeline_events?.[0]?.description || report?.recent_timeline_events?.[0]?.title, "提交后形成学习证据。"),
      tone: quizCount > 0 || evidenceCount > 0 ? "success" : "neutral",
      icon: Target,
    },
    {
      id: "assessment",
      label: "效果评估",
      metric: score ? `${score} 分` : "待评估",
      detail: guideDisplayText(report?.effect_assessment?.summary || nextAction, "把证据转成下一步学习处方。"),
      tone: effectStatusTone(score),
      icon: GraduationCap,
    },
  ];
}

function buildIflytekNodes(coursePackage: GuideV2CoursePackage | null): IflytekNode[] {
  const artifactTypes = collectArtifactTypes(coursePackage);
  return [
    {
      id: "spark",
      label: "讯飞星火",
      role: "对话、导学、资源生成、学习评估",
      status: coursePackage ? "used" : "wired",
      evidence: coursePackage ? "已生成课程产出包和演示讲法" : "可作为问答模型接入",
      icon: Sparkles,
    },
    {
      id: "embedding",
      label: "讯飞 Embedding",
      role: "课程资料索引与 RAG 证据检索",
      status: "wired",
      evidence: "支撑知识库智能索引与引用依据",
      icon: FileSearch,
    },
    {
      id: "search",
      label: "讯飞 ONE SEARCH",
      role: "外部资料和精选公开视频检索",
      status: artifactTypes.has("external_video") ? "used" : "available",
      evidence: artifactTypes.has("external_video") ? "已有公开视频学习资源" : "可补充外部学习资源",
      icon: Search,
    },
    {
      id: "ocr",
      label: "讯飞 OCR",
      role: "扫描资料、图片题和讲义识别",
      status: artifactTypes.has("vision") || artifactTypes.has("ocr") || artifactTypes.has("image") ? "used" : "available",
      evidence: "可把扫描资料转成可检索文本",
      icon: Image,
    },
    {
      id: "tts",
      label: "讯飞 TTS",
      role: "语音讲解和短视频旁白",
      status: artifactTypes.has("audio") || artifactTypes.has("video") ? "used" : "available",
      evidence: artifactTypes.has("audio") || artifactTypes.has("video") ? "已有音视频讲解素材" : "可把讲解合成为音频",
      icon: AudioLines,
    },
  ];
}

function collectArtifactTypes(coursePackage: GuideV2CoursePackage | null) {
  const types = new Set<string>();
  coursePackage?.portfolio?.forEach((item) => addType(types, item.type));
  coursePackage?.demo_fallback_kit?.assets?.forEach((item) => addType(types, item.type));
  coursePackage?.demo_seed_pack?.sample_artifacts?.forEach((item) => addType(types, item.type));
  return types;
}

function addType(types: Set<string>, value: unknown) {
  const type = String(value ?? "").trim().toLowerCase();
  if (type) types.add(type);
}

function normalizeScore(value: unknown) {
  const score = Number(value ?? 0);
  if (!Number.isFinite(score) || score <= 0) return 0;
  return Math.round(score <= 1 ? score * 100 : score);
}

function nodeToneClass(tone: GuideTone) {
  if (tone === "success") return "bg-emerald-50 text-emerald-700";
  if (tone === "warning") return "bg-amber-50 text-amber-700";
  if (tone === "danger") return "bg-red-50 text-red-700";
  if (tone === "brand") return "bg-tint-lavender text-brand-purple";
  return "border border-line bg-white text-slate-500";
}

function iflytekStatusLabel(status: IflytekNode["status"]) {
  if (status === "used") return "已用于演示";
  if (status === "wired") return "已接入";
  return "可配置";
}

function iflytekTone(status: IflytekNode["status"]): GuideTone {
  if (status === "used") return "success";
  if (status === "wired") return "brand";
  return "neutral";
}
