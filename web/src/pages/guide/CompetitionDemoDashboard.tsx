import {
  AudioLines,
  BrainCircuit,
  CheckCircle2,
  FileSearch,
  GraduationCap,
  Mic,
  SquareFunction,
  Image,
  Loader2,
  MessageSquareText,
  Route,
  Search,
  Sparkles,
  Target,
  Video,
  Workflow,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { useSystemStatus } from "@/hooks/useApiQueries";
import {
  effectStatusTone,
  guideDisplayText,
  preflightStatusLabel,
  preflightStatusTone,
  submissionStatusLabel,
  submissionStatusTone,
  type GuideTone,
} from "@/lib/guideDisplay";
import type { GuideV2CoursePackage, SystemStatus } from "@/lib/types";
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

type IflytekDemoCue = {
  label: string;
  detail: string;
  tone: GuideTone;
};

const FALLBACK_REQUIREMENTS = [
  "对话式学习记录整理",
  "多步骤协同生成学习资源",
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
  const systemStatus = useSystemStatus();
  const iflytekNodes = buildIflytekNodes(coursePackage, systemStatus.data);
  const iflytekConfigured = iflytekNodes.filter((node) => node.status !== "available").length;
  const iflytekDemoCues = buildIflytekDemoCues(iflytekNodes, coursePackage);
  const iflytekSummary = guideDisplayText(
    coursePackage?.iflytek_toolchain?.summary,
    "把模型、资料查找、识别、搜索和语音合成放回学习链里讲。",
  );
  const headline = guideDisplayText(
    alignment?.summary || coursePackage?.summary,
    "用一条完整学习链证明记录、路线、资源、辅导和评估都已经连起来。",
  );
  const nextAction = guideDisplayText(
    preflight?.primary_gap?.action || alignment?.primary_gap?.demo_action || preflight?.next_action || alignment?.next_action,
    "按学习记录、路线、资源、练习、报告的顺序录制 7 分钟演示。",
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
              <Badge tone={dashboardTone}>{coverageScore ? `证明分 ${coverageScore}` : "等待材料"}</Badge>
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
                <p className="text-sm font-semibold text-ink">学习链轨道</p>
                <p className="mt-1 text-xs leading-5 text-slate-500">目标进入系统后，每一步都留下记录，再推动下一步调整。</p>
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
                <p className="text-sm font-semibold text-ink">讯飞服务接入概览</p>
                <p className="mt-1 text-xs leading-5 text-slate-500">{iflytekSummary}</p>
              </div>
              <Badge tone={iflytekConfigured >= iflytekNodes.length - 2 ? "success" : "brand"}>
                {iflytekConfigured}/{iflytekNodes.length} 已接入
              </Badge>
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {iflytekNodes.map((node) => (
                <IflytekCapabilityRow key={node.id} node={node} />
              ))}
            </div>
            <div className="mt-3 rounded-lg border border-line bg-canvas p-3" data-testid="competition-iflytek-demo-cues">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs font-semibold text-ink">7 分钟讲法</p>
                <span className="text-[11px] text-slate-400">从能力到学习价值</span>
              </div>
              <div className="mt-2 grid gap-2">
                {iflytekDemoCues.map((cue) => (
                  <div key={cue.label} className="grid grid-cols-[4.5rem_minmax(0,1fr)] gap-2 rounded-lg border border-line bg-white px-2 py-2">
                    <Badge tone={cue.tone}>{cue.label}</Badge>
                    <p className="min-w-0 text-xs leading-5 text-slate-600">{cue.detail}</p>
                  </div>
                ))}
              </div>
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
              <DashboardMiniMetric label="记录" value={Number(behavior.evidence_count ?? behavior.event_count ?? 0)} />
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
        evidence: guideDisplayText((item.evidence ?? []).find(Boolean), "等待当前课程产物补齐证明材料。"),
        action: guideDisplayText(item.demo_action, "指向当前页面材料，用一句话说明这一项已经完成。"),
      }))
    : FALLBACK_REQUIREMENTS.map((label, index) => ({
        id: `fallback-${index}`,
        label,
        status: "todo",
        evidence: "生成课程成果包后会显示对应材料。",
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
      label: "学习记录",
      metric: style?.label || `${Number(behavior.profile_update_count ?? 0)} 次更新`,
      detail: guideDisplayText(style?.summary || style?.signals?.[0]?.value, "汇总目标、薄弱点、偏好和最近记录。"),
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
      detail: guideDisplayText(coursePackage?.agent_collaboration_blueprint?.summary, "学习记录、资料查找、图解、出题和评估步骤协同。"),
      tone: coursePackage?.agent_collaboration_blueprint ? "brand" : "neutral",
      icon: MessageSquareText,
    },
    {
      id: "feedback",
      label: "练习反馈",
      metric: `${quizCount} 次练习`,
      detail: guideDisplayText(report?.recent_timeline_events?.[0]?.description || report?.recent_timeline_events?.[0]?.title, "提交后形成学习记录。"),
      tone: quizCount > 0 || evidenceCount > 0 ? "success" : "neutral",
      icon: Target,
    },
    {
      id: "assessment",
      label: "效果评估",
      metric: score ? `${score} 分` : "待评估",
      detail: guideDisplayText(report?.effect_assessment?.summary || nextAction, "把记录转成下一步学习处方。"),
      tone: effectStatusTone(score),
      icon: GraduationCap,
    },
  ];
}

function buildIflytekNodes(coursePackage: GuideV2CoursePackage | null, status?: SystemStatus): IflytekNode[] {
  const artifactTypes = collectArtifactTypes(coursePackage);
  const usedVision = hasAnyType(artifactTypes, ["vision", "ocr", "image", "scan"]);
  const usedFormula = hasAnyType(artifactTypes, ["formula", "formula_ocr", "math", "latex"]);
  const usedAudio = hasAnyType(artifactTypes, ["audio", "tts", "narration"]);
  const usedVideo = hasAnyType(artifactTypes, ["video", "external_video"]);
  const usedSpeech = hasAnyType(artifactTypes, ["speech", "asr", "oral_practice", "pronunciation"]);
  return [
    {
      id: "spark",
      label: "讯飞星火",
      role: "对话、导学、资源生成、学习评估",
      status: serviceNodeStatus(serviceConfigured(status?.llm), Boolean(coursePackage)),
      evidence: coursePackage ? "已生成课程成果包和演示讲法" : serviceEvidence(status?.llm, "可作为问答模型接入"),
      icon: Sparkles,
    },
    {
      id: "embedding",
      label: "讯飞 Embedding",
      role: "课程资料整理与资料来源查找",
      status: serviceNodeStatus(serviceConfigured(status?.embeddings), Boolean(coursePackage?.portfolio?.length)),
      evidence: serviceEvidence(status?.embeddings, "支撑资料库整理与引用来源"),
      icon: FileSearch,
    },
    {
      id: "search",
      label: "讯飞 ONE SEARCH",
      role: "外部资料和精选公开视频查找",
      status: serviceNodeStatus(serviceConfigured(status?.search), artifactTypes.has("external_video")),
      evidence: artifactTypes.has("external_video") ? "已有公开视频学习资源" : serviceEvidence(status?.search, "可补充外部学习资源"),
      icon: Search,
    },
    {
      id: "ocr",
      label: "讯飞图片文字识别",
      role: "扫描资料、图片题和讲义识别",
      status: serviceNodeStatus(serviceConfigured(status?.ocr), usedVision),
      evidence: usedVision ? "已有图片/扫描资料识别链路" : serviceEvidence(status?.ocr, "可把扫描资料转成可引用内容"),
      icon: Image,
    },
    {
      id: "formula_ocr",
      label: "讯飞公式识别",
      role: "公式图片转 LaTeX，辅助数学题讲解",
      status: serviceNodeStatus(serviceConfigured(status?.formula_ocr), usedFormula),
      evidence: usedFormula ? "可把公式识别结果交给解题智能体" : serviceEvidence(status?.formula_ocr, "可接入数学图片题解析"),
      icon: SquareFunction,
    },
    {
      id: "image_understanding",
      label: "讯飞图片理解",
      role: "图表、实验图、几何图的多模态解释",
      status: serviceNodeStatus(serviceConfigured(status?.image_understanding), usedVision),
      evidence: usedVision ? "图片资料可进入多模态辅导" : serviceEvidence(status?.image_understanding, "可扩展图解式答疑"),
      icon: BrainCircuit,
    },
    {
      id: "tts",
      label: "讯飞 TTS",
      role: "语音讲解和短视频旁白",
      status: serviceNodeStatus(serviceConfigured(status?.tts), usedAudio || usedVideo),
      evidence: usedAudio || usedVideo ? "已有音视频讲解素材" : serviceEvidence(status?.tts, "可把讲解合成为音频"),
      icon: AudioLines,
    },
    {
      id: "asr",
      label: "讯飞语音识别",
      role: "课堂录音、学生口述问题转文本",
      status: serviceNodeStatus(serviceConfigured(status?.asr), usedSpeech),
      evidence: usedSpeech ? "语音输入可转入学习记录" : serviceEvidence(status?.asr, "可补齐口述学习场景"),
      icon: Mic,
    },
    {
      id: "speech_eval",
      label: "讯飞语音评测",
      role: "朗读、口语练习和表达质量反馈",
      status: serviceNodeStatus(serviceConfigured(status?.speech_eval), usedSpeech),
      evidence: usedSpeech ? "口语练习可形成效果评估证据" : serviceEvidence(status?.speech_eval, "可作为学习效果加分项"),
      icon: Target,
    },
    {
      id: "iflytek_workflow",
      label: "讯飞星辰工作流",
      role: "把生成、审核、推送封装成可复用流程",
      status: serviceNodeStatus(serviceConfigured(status?.iflytek_workflow), Boolean(coursePackage?.agent_collaboration_blueprint)),
      evidence: coursePackage?.agent_collaboration_blueprint
        ? "多智能体协同流程已有演示证据"
        : serviceEvidence(status?.iflytek_workflow, "可沉淀比赛演示标准流程"),
      icon: Workflow,
    },
  ];
}

function buildIflytekDemoCues(iflytekNodes: IflytekNode[], coursePackage: GuideV2CoursePackage | null): IflytekDemoCue[] {
  const packageCues = coursePackage?.iflytek_toolchain?.demo_cues ?? [];
  if (packageCues.length) {
    return packageCues.slice(0, 3).map((cue, index) => ({
      label: guideDisplayText(cue.label, ["开场", "中段", "收尾"][index] || "讲法"),
      detail: guideDisplayText(cue.detail, "把讯飞能力讲回学习任务，而不是只展示工具配置。"),
      tone: demoCueTone(cue.tone),
    }));
  }

  const used = iflytekNodes.filter((node) => node.status === "used");
  const wired = iflytekNodes.filter((node) => node.status === "wired");
  const hasSpeech = hasNode(iflytekNodes, ["tts", "asr", "speech_eval"], "used");
  const hasVision = hasNode(iflytekNodes, ["ocr", "formula_ocr", "image_understanding"], "used");
  const hasWorkflow = hasNode(iflytekNodes, ["iflytek_workflow"], "used");

  return [
    {
      label: "开场",
      detail: `先说明比赛要求使用讯飞工具链，本页可看到 ${used.length + wired.length}/${iflytekNodes.length} 项已接入。`,
      tone: used.length || wired.length ? "brand" : "warning",
    },
    {
      label: "中段",
      detail: hasVision
        ? "展示图片、扫描件或公式如何先被识别理解，再进入资料问答和智能辅导。"
        : "用资料入库、检索和课程资源生成证明工具链已经服务学习任务。",
      tone: hasVision ? "success" : "brand",
    },
    {
      label: "收尾",
      detail:
        hasSpeech || hasWorkflow || coursePackage?.learning_report
          ? "最后展示语音、多智能体流程或学习报告，把多模态输入转成可评估的学习记录。"
          : "最后展示学习报告和下一步计划，把模型输出落回个性化学习闭环。",
      tone: hasSpeech || hasWorkflow || coursePackage?.learning_report ? "success" : "brand",
    },
  ];
}

function demoCueTone(value: unknown): GuideTone {
  const tone = String(value ?? "").trim();
  if (tone === "success" || tone === "warning" || tone === "danger" || tone === "brand" || tone === "neutral") {
    return tone;
  }
  return "brand";
}

function hasNode(iflytekNodes: IflytekNode[], ids: string[], status: IflytekNode["status"]) {
  return iflytekNodes.some((node) => ids.includes(node.id) && node.status === status);
}

function hasAnyType(types: Set<string>, values: string[]) {
  return values.some((value) => types.has(value));
}

function serviceConfigured(service?: { status?: string; provider?: string | null; model?: string | null; uri?: string | null }) {
  return (
    String(service?.status ?? "").toLowerCase() === "configured" ||
    Boolean(service?.provider || service?.model || service?.uri)
  );
}

function serviceNodeStatus(configured: boolean, used: boolean): IflytekNode["status"] {
  if (used) return "used";
  if (configured) return "wired";
  return "available";
}

function serviceEvidence(
  service: { status?: string; provider?: string | null; model?: string | null; uri?: string | null } | undefined,
  fallback: string,
) {
  if (service?.model) return `已配置 ${service.model}`;
  if (service?.provider) return `已配置 ${service.provider}`;
  if (service?.uri) return "已配置服务地址";
  return fallback;
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
