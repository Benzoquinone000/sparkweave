import { Fragment } from "react";
import { BookOpen, FileDown, GraduationCap, Loader2, Video } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  effectStatusTone,
  fallbackAssetLabel,
  fallbackAssetTone,
  guideDisplayText,
  guideStageLabel,
  preflightCheckTone,
  preflightStatusLabel,
  preflightStatusTone,
  submissionStatusLabel,
  submissionStatusTone,
} from "@/lib/guideDisplay";
import type { GuideV2CoursePackage } from "@/lib/types";
import { CompetitionDemoDashboard } from "./CompetitionDemoDashboard";
import { EvalList, EvalMini } from "./GuideMetrics";

export function GuideCoursePackagePanel({
  coursePackage,
  loading,
  canSave,
  saving,
  onSave,
  canExport,
  onExport,
}: {
  coursePackage: GuideV2CoursePackage | null;
  loading: boolean;
  canSave: boolean;
  saving: boolean;
  onSave: () => void;
  canExport: boolean;
  onExport: () => void;
}) {
  const project = coursePackage?.capstone_project ?? {};
  const rubric = coursePackage?.rubric ?? [];
  const review = coursePackage?.review_plan ?? [];
  const report = coursePackage?.learning_report ?? {};
  const behavior = report.behavior_summary ?? {};
  const behaviorTags = report.behavior_tags ?? [];
  const recentEvents = report.recent_timeline_events ?? [];
  const effectAssessment = report.effect_assessment;
  const demoBlueprint = coursePackage?.demo_blueprint ?? null;
  const fallbackKit = coursePackage?.demo_fallback_kit ?? null;
  const seedPack = coursePackage?.demo_seed_pack ?? null;
  const demoPreflight = coursePackage?.demo_preflight ?? null;
  const presentationOutline = coursePackage?.presentation_outline ?? null;
  const recordingScript = coursePackage?.recording_script ?? null;
  const competitionSubmission = coursePackage?.competition_submission ?? null;
  const aiCodingStatement = coursePackage?.ai_coding_statement ?? null;
  const competitionAlignment = coursePackage?.competition_alignment ?? null;
  const agentCollaboration = coursePackage?.agent_collaboration_blueprint ?? null;
  const defenseQa = coursePackage?.defense_qa ?? null;
  const learningStyle = coursePackage?.learning_style ?? demoBlueprint?.learning_style ?? null;
  return (
    <section className="rounded-lg border border-line bg-white p-4" data-testid="guide-course-package-panel">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <GraduationCap size={18} className="text-brand-purple" />
          <div>
            <h2 className="text-base font-semibold text-ink">课程产出包</h2>
            {coursePackage?.title ? (
              <p className="mt-0.5 text-xs text-slate-500">{guideDisplayText(coursePackage.title)}</p>
            ) : null}
          </div>
        </div>
        {loading ? <Loader2 size={16} className="animate-spin text-brand-purple" /> : <Badge tone="brand">{project.estimated_minutes ?? "-"} 分钟</Badge>}
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-600">
        {guideDisplayText(coursePackage?.summary, "系统会把学习路径整理成最终项目、评分标准、复习计划和作品集索引。")}
      </p>
      <CompetitionDemoDashboard coursePackage={coursePackage} loading={loading} />
      <div className="mt-4 rounded-lg border border-line bg-canvas p-3">
        <p className="text-sm font-semibold text-ink">{guideDisplayText(project.title, "学习成果项目")}</p>
        <p className="mt-2 line-clamp-4 text-xs leading-5 text-slate-600">{guideDisplayText(project.scenario, "完成更多学习任务后会生成更贴合你的项目说明。")}</p>
      </div>
      <CourseDemoPreflightCard preflight={demoPreflight} />
      <CourseLearningStyleCard learningStyle={learningStyle} />
      <CourseDemoRecordingChecklistCard
        blueprint={demoBlueprint}
        kit={fallbackKit}
        seed={seedPack}
        learningStyle={learningStyle}
        script={recordingScript}
      />
      <CoursePresentationOutlineCard outline={presentationOutline} />
      <CourseCompetitionAlignmentCard alignment={competitionAlignment} />
      <CourseAgentCollaborationCard blueprint={agentCollaboration} />
      <CourseDefenseQaCard defense={defenseQa} />
      <CourseCompetitionSubmissionCard submission={competitionSubmission} aiCoding={aiCodingStatement} />
      <div className="mt-4 rounded-lg border border-line bg-white p-3">
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm font-semibold text-ink">产出依据</p>
          <Badge tone="neutral">{Number(behavior.event_count ?? 0)} 条行为</Badge>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <EvalMini label="掌握" value={Number(report.overall_score ?? 0)} />
          <EvalMini label="进度" value={Number(report.progress ?? 0)} suffix="%" />
          <EvalMini label="资源" value={Number(behavior.resource_count ?? 0)} suffix="个" />
          <EvalMini label="练习" value={Number(behavior.quiz_attempt_count ?? 0)} suffix="次" />
        </div>
        {behaviorTags.length ? (
          <div className="mt-3 flex flex-wrap gap-2">
            {behaviorTags.slice(0, 4).map((tag) => (
              <Badge key={tag} tone="brand">{guideDisplayText(tag)}</Badge>
            ))}
          </div>
        ) : null}
        {recentEvents.length ? (
          <p className="mt-3 line-clamp-2 text-xs leading-5 text-slate-500">
            最近：{recentEvents.slice(0, 2).map((event) => guideDisplayText(event.title || event.description || event.type)).join(" / ")}
          </p>
        ) : null}
        {effectAssessment ? (
          <div className="mt-3 rounded-lg border border-line bg-canvas p-2">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-semibold text-ink">学习效果</p>
              <Badge tone={effectStatusTone(effectAssessment.score)}>{guideDisplayText(effectAssessment.label, `${Number(effectAssessment.score ?? 0)} 分`)}</Badge>
            </div>
            <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-600">{guideDisplayText(effectAssessment.summary, "已生成学习效果评估。")}</p>
          </div>
        ) : null}
      </div>
      <div className="mt-4 space-y-2">
        {rubric.slice(0, 3).map((item) => (
          <div key={item.criterion} className="rounded-lg border border-line bg-white p-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-semibold text-ink">{guideDisplayText(item.criterion)}</p>
              <Badge tone="neutral">{item.weight ?? 0}%</Badge>
            </div>
            <p className="mt-1 text-xs leading-5 text-slate-500">{guideDisplayText(item.baseline || item.excellent)}</p>
          </div>
        ))}
      </div>
      <EvalList
        title="复习重点"
        items={review.slice(0, 3).map((item) => `${guideDisplayText(item.title, "知识点")}：${guideDisplayText(item.action)}`)}
        empty="完成更多任务后生成复习计划。"
        tone="brand"
      />
      <div className="mt-4 grid gap-2 md:grid-cols-2">
        <Button tone="secondary" className="w-full" disabled={!canSave || saving || !coursePackage} onClick={onSave}>
          {saving ? <Loader2 size={16} className="animate-spin" /> : <BookOpen size={16} />}
          保存到记录本
        </Button>
        <Button
          tone="primary"
          className="w-full"
          disabled={!canExport || !coursePackage}
          onClick={onExport}
          data-testid="guide-course-package-download"
        >
          <FileDown size={16} />
          下载 Markdown
        </Button>
      </div>
    </section>
  );
}

function CourseDefenseQaCard({
  defense,
}: {
  defense: GuideV2CoursePackage["defense_qa"] | null;
}) {
  const questions = defense?.questions ?? [];
  if (!defense || !questions.length) return null;
  return (
    <div className="mt-4 rounded-lg border border-line bg-white p-3" data-testid="guide-defense-qa-card">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">{guideDisplayText(defense.title, "答辩问答预案")}</Badge>
            {defense.course_name ? <Badge tone="neutral">{guideDisplayText(defense.course_name)}</Badge> : null}
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            {guideDisplayText(defense.summary, "把评委可能追问的问题提前整理成可讲的回答。")}
          </p>
        </div>
        <Badge tone="success">{Number(defense.question_count ?? questions.length)} 问</Badge>
      </div>
      <div className="mt-3 space-y-2">
        {questions.slice(0, 2).map((item, index) => (
          <div key={`${item.question || "question"}-${index}`} className="rounded-lg border border-line bg-canvas p-2">
            <p className="text-xs font-semibold text-ink">{guideDisplayText(item.question, "答辩问题")}</p>
            <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-600">
              {guideDisplayText(item.answer || item.evidence, "准备一句能落到页面证据的回答。")}
            </p>
          </div>
        ))}
      </div>
      {defense.next_action ? (
        <p className="mt-3 rounded-lg border border-line bg-canvas px-3 py-2 text-xs leading-5 text-slate-600">
          下一步：{guideDisplayText(defense.next_action)}
        </p>
      ) : null}
    </div>
  );
}

function CourseCompetitionAlignmentCard({
  alignment,
}: {
  alignment: GuideV2CoursePackage["competition_alignment"] | null;
}) {
  const requirements = alignment?.requirements ?? [];
  if (!alignment || !requirements.length) return null;
  const ready = Number(alignment.ready_count ?? 0);
  const total = Number(alignment.total_count ?? requirements.length);
  const coverage = Number(alignment.coverage_score ?? 0);
  const gap = alignment.primary_gap;
  const visibleRequirements = requirements.slice(0, 5);
  const proofChain = alignment.proof_chain ?? [];
  return (
    <div className="mt-4 rounded-lg border border-brand-purple-300 bg-tint-lavender p-3" data-testid="guide-competition-alignment-card">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">{guideDisplayText(alignment.title, "赛题五项对齐")}</Badge>
            {alignment.course_name ? <Badge tone="neutral">{guideDisplayText(alignment.course_name)}</Badge> : null}
            {coverage ? <Badge tone={coverage >= 80 ? "success" : "warning"}>覆盖分 {coverage}</Badge> : null}
          </div>
          <p className="mt-2 text-sm leading-6 text-ink">
            {guideDisplayText(alignment.summary, "把当前学习闭环映射成比赛可展示证据。")}
          </p>
        </div>
        <Badge tone={ready >= total ? "success" : "warning"}>{ready} / {total}</Badge>
      </div>
      <div className="mt-3 space-y-2">
        {visibleRequirements.map((item, index) => (
          <div key={item.id || item.requirement || index} className="rounded-lg border border-white/80 bg-white p-2" data-testid="guide-competition-requirement">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="min-w-0 text-xs font-semibold text-ink">
                {index + 1}. {guideDisplayText(item.requirement, "赛题要求")}
              </p>
              <Badge tone={submissionStatusTone(item.status)}>{submissionStatusLabel(item.status)}</Badge>
            </div>
            <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-600">
              {guideDisplayText((item.evidence ?? []).filter(Boolean)[0], "等待更多学习证据。")}
            </p>
            <p className="mt-1 line-clamp-1 text-xs leading-5 text-steel">
              录屏：{guideDisplayText(item.demo_action, "指向当前页面证据，用一句话说明这一项已经闭环。")}
            </p>
          </div>
        ))}
      </div>
      {proofChain.length ? (
        <div className="mt-3 grid gap-2 md:grid-cols-3" data-testid="guide-competition-proof-chain">
          {proofChain.slice(0, 3).map((item, index) => (
            <div key={`${item.label}-${index}`} className="rounded-lg border border-white/80 bg-white p-2">
              <p className="text-xs font-semibold text-brand-purple">{guideDisplayText(item.label, `证明 ${index + 1}`)}</p>
              <p className="mt-1 line-clamp-3 text-xs leading-5 text-slate-600">
                {guideDisplayText(item.detail, "把功能证据、现场动作和答辩讲法串起来。")}
              </p>
            </div>
          ))}
        </div>
      ) : null}
      <p className="mt-3 rounded-lg border border-brand-purple-300 bg-white px-3 py-2 text-xs leading-5 text-slate-600">
        {gap ? "先补：" : "录屏动作："}
        {guideDisplayText((gap?.demo_action || alignment.next_action), "按画像、路线、资源、练习、报告顺序展示。")}
      </p>
    </div>
  );
}

function CourseAgentCollaborationCard({
  blueprint,
}: {
  blueprint: GuideV2CoursePackage["agent_collaboration_blueprint"] | null;
}) {
  const roles = blueprint?.roles ?? [];
  const route = blueprint?.route ?? [];
  if (!blueprint || (!roles.length && !route.length)) return null;
  const readiness = blueprint.readiness;
  const leadRoute = route.slice(0, 5);
  return (
    <div className="mt-4 rounded-lg border border-line bg-white p-3" data-testid="guide-agent-collaboration-blueprint">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">{guideDisplayText(blueprint.title, "多智能体协作蓝图")}</Badge>
            {blueprint.course_name ? <Badge tone="neutral">{guideDisplayText(blueprint.course_name)}</Badge> : null}
            {readiness?.score ? <Badge tone={Number(readiness.score) >= 80 ? "success" : "warning"}>{Number(readiness.score)} 分</Badge> : null}
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            {guideDisplayText(blueprint.summary, "把画像、路径、资源和评估串成一条可讲清楚的协作路线。")}
          </p>
        </div>
        {readiness?.label ? <Badge tone={Number(readiness.score ?? 0) >= 80 ? "success" : "warning"}>{guideDisplayText(readiness.label)}</Badge> : null}
      </div>
      {leadRoute.length ? (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {leadRoute.map((item, index) => (
            <Fragment key={`${item.from}-${item.to}-${index}`}>
              <span className="rounded-md border border-brand-purple-300 bg-tint-lavender px-2 py-1 text-xs font-medium text-charcoal">
                {guideDisplayText(item.to || item.from, "智能体")}
              </span>
              {index < leadRoute.length - 1 ? <span className="text-xs text-slate-400">→</span> : null}
            </Fragment>
          ))}
        </div>
      ) : null}
      <div className="mt-3 grid gap-2 md:grid-cols-2">
        {roles.slice(0, 4).map((role) => (
          <div key={role.id || role.name} className="rounded-lg border border-line bg-canvas p-2">
            <div className="flex items-center justify-between gap-2">
              <p className="min-w-0 truncate text-xs font-semibold text-ink">{guideDisplayText(role.name, "智能体")}</p>
              <span className="h-1.5 w-1.5 rounded-sm bg-brand-purple" />
            </div>
            <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-600">
              {guideDisplayText(role.responsibility || role.output, "负责把学习证据转成下一步动作。")}
            </p>
            {role.output ? (
              <p className="mt-1 line-clamp-1 text-xs leading-5 text-steel">
                产出：{guideDisplayText(role.output)}
              </p>
            ) : null}
          </div>
        ))}
      </div>
      {blueprint.recording_tip || blueprint.next_action ? (
        <p className="mt-3 rounded-lg border border-line bg-canvas px-3 py-2 text-xs leading-5 text-slate-600">
          录屏：{guideDisplayText(blueprint.recording_tip || blueprint.next_action)}
        </p>
      ) : null}
    </div>
  );
}

function CourseCompetitionSubmissionCard({
  submission,
  aiCoding,
}: {
  submission: GuideV2CoursePackage["competition_submission"] | null;
  aiCoding: GuideV2CoursePackage["ai_coding_statement"] | null;
}) {
  const checklist = submission?.checklist ?? [];
  if (!submission || !checklist.length) return null;
  const ready = Number(submission.ready_count ?? 0);
  const total = Number(submission.total_count ?? checklist.length);
  return (
    <div className="mt-4 rounded-lg border border-blue-100 bg-blue-50 p-3" data-testid="guide-competition-submission-card">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">{guideDisplayText(submission.title, "比赛提交清单")}</Badge>
            {submission.course_name ? <Badge tone="neutral">{guideDisplayText(submission.course_name)}</Badge> : null}
          </div>
          <p className="mt-2 text-sm leading-6 text-blue-950">
            {guideDisplayText(submission.summary, "按赛题提交物检查当前课程产出。")}
          </p>
        </div>
        <Badge tone={ready >= total ? "success" : "warning"}>{ready} / {total}</Badge>
      </div>
      <div className="mt-3 grid gap-2 md:grid-cols-2">
        {checklist.slice(0, 4).map((item) => (
          <div key={`${item.item}-${item.status}`} className="rounded-lg border border-white/80 bg-white p-2">
            <div className="flex items-center justify-between gap-2">
              <p className="min-w-0 truncate text-xs font-semibold text-ink">{guideDisplayText(item.item, "提交物")}</p>
              <Badge tone={submissionStatusTone(item.status)}>{submissionStatusLabel(item.status)}</Badge>
            </div>
            <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-600">{guideDisplayText(item.evidence, "等待更多学习证据。")}</p>
          </div>
        ))}
      </div>
      {submission.next_action ? (
        <p className="mt-3 rounded-lg border border-blue-100 bg-white px-3 py-2 text-xs leading-5 text-slate-600">
          下一步：{guideDisplayText(submission.next_action)}
        </p>
      ) : null}
      {aiCoding ? (
        <div className="mt-3 rounded-lg border border-blue-100 bg-white p-2" data-testid="guide-ai-coding-statement">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="success">{guideDisplayText(aiCoding.title, "AI Coding 工具说明")}</Badge>
            <span className="text-xs text-slate-500">可放入提交材料</span>
          </div>
          <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-600">
            {guideDisplayText(aiCoding.summary, "说明 AI Coding 参与范围、人工复核和密钥边界。")}
          </p>
        </div>
      ) : null}
    </div>
  );
}

function CourseDemoPreflightCard({
  preflight,
}: {
  preflight: GuideV2CoursePackage["demo_preflight"] | null;
}) {
  const checks = preflight?.checks ?? [];
  if (!preflight || !checks.length) return null;
  const ready = Number(preflight.ready_count ?? 0);
  const total = Number(preflight.total_count ?? checks.length);
  const gap = preflight.primary_gap;
  return (
    <div className="mt-4 rounded-lg border border-red-100 bg-red-50 p-3" data-testid="guide-demo-preflight-card">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={preflightStatusTone(preflight.status)}>{guideDisplayText(preflight.title, "赛前一键检查")}</Badge>
            <Badge tone="neutral">{ready} / {total}</Badge>
          </div>
          <p className="mt-2 text-sm leading-6 text-red-950">
            {guideDisplayText(preflight.summary, "检查录屏、答辩和提交材料是否成链。")}
          </p>
        </div>
        <Badge tone={preflightStatusTone(preflight.status)}>{preflightStatusLabel(preflight.status)}</Badge>
      </div>
      {gap ? (
        <p className="mt-3 rounded-lg border border-white/80 bg-white p-2 text-xs leading-5 text-slate-700">
          先补：{guideDisplayText(gap.label, "待补齐")}。{guideDisplayText(gap.action || preflight.next_action, "补齐后即可开始录屏。")}
        </p>
      ) : (
        <p className="mt-3 rounded-lg border border-white/80 bg-white p-2 text-xs leading-5 text-slate-700">
          {guideDisplayText(preflight.next_action, "可以开始录制 7 分钟演示。")}
        </p>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        {checks.slice(0, 5).map((item) => (
          <Badge key={item.id || item.label} tone={preflightCheckTone(item.status)}>
            {guideDisplayText(item.label, "检查项")}
          </Badge>
        ))}
      </div>
    </div>
  );
}

function CoursePresentationOutlineCard({
  outline,
}: {
  outline: GuideV2CoursePackage["presentation_outline"] | null;
}) {
  const slides = outline?.slides ?? [];
  if (!outline || !slides.length) return null;
  return (
    <div className="mt-4 rounded-lg border border-brand-purple-300 bg-white p-3" data-testid="guide-presentation-outline-card">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">{guideDisplayText(outline.title, "演示 PPT 骨架")}</Badge>
            {outline.course_name ? <Badge tone="neutral">{guideDisplayText(outline.course_name)}</Badge> : null}
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            {guideDisplayText(outline.summary, "按赛题评分点生成可直接整理成 PPT 的讲述骨架。")}
          </p>
        </div>
        <Badge tone="success">{Number(outline.slide_count ?? slides.length)} 页</Badge>
      </div>
      <div className="mt-3 space-y-2">
        {slides.slice(0, 3).map((slide) => (
          <div key={`${slide.slide_no}-${slide.title}`} className="rounded-lg border border-line bg-canvas p-2">
            <p className="text-xs font-semibold text-ink">
              P{slide.slide_no ?? "-"} · {guideDisplayText(slide.title, "演示页")}
            </p>
            <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-600">
              {guideDisplayText(slide.evidence || slide.purpose, "补一张系统截图或学习产物。")}
            </p>
          </div>
        ))}
      </div>
      {outline.next_action ? (
        <p className="mt-3 rounded-lg border border-line bg-canvas px-3 py-2 text-xs leading-5 text-slate-600">
          下一步：{guideDisplayText(outline.next_action)}
        </p>
      ) : null}
    </div>
  );
}

function CourseLearningStyleCard({ learningStyle }: { learningStyle: GuideV2CoursePackage["learning_style"] | null }) {
  if (!learningStyle?.label && !learningStyle?.summary) return null;
  const signals = learningStyle.signals ?? [];
  return (
    <div className="mt-4 rounded-lg border border-brand-purple-300 bg-tint-lavender p-3" data-testid="guide-course-learning-style">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="brand">画像驱动产出</Badge>
        {learningStyle.label ? <Badge tone="neutral">{learningStyle.label}</Badge> : null}
      </div>
      <p className="mt-2 text-sm leading-6 text-ink">
        {learningStyle.summary || "课程产出包会把画像、资源、练习和报告串成可展示的学习闭环。"}
      </p>
      {learningStyle.trend ? <p className="mt-1 text-xs leading-5 text-charcoal">{learningStyle.trend}</p> : null}
      {signals.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {signals.slice(0, 3).map((signal) => (
            <span key={`${signal.label}-${signal.value}`} className="rounded-md border border-brand-purple-300 bg-white px-2 py-1 text-xs text-slate-600">
              {signal.label || "信号"}：{signal.value || "-"}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function CourseDemoRecordingChecklistCard({
  blueprint,
  kit,
  seed,
  learningStyle,
  script,
}: {
  blueprint: GuideV2CoursePackage["demo_blueprint"] | null;
  kit: GuideV2CoursePackage["demo_fallback_kit"] | null;
  seed: GuideV2CoursePackage["demo_seed_pack"] | null;
  learningStyle: GuideV2CoursePackage["learning_style"] | null;
  script: GuideV2CoursePackage["recording_script"] | null;
}) {
  const storyline = blueprint?.storyline ?? [];
  const taskChain = seed?.task_chain ?? [];
  const recordingCue = script?.segments?.[0];
  const steps = storyline.length
    ? storyline.slice(0, 3).map((step, index) => ({
        key: `${step.minute || index}-${step.title || index}`,
        label: step.minute || `片段 ${index + 1}`,
        title: step.title || "演示片段",
        detail: step.show || step.talking_point || step.requirement || "",
      }))
    : taskChain.slice(0, 3).map((task, index) => ({
        key: `${task.task_id || index}-${task.stage || index}`,
        label: guideStageLabel(task.stage, `步骤 ${index + 1}`),
        title: guideDisplayText(task.title, "演示任务"),
        detail: task.show || task.sample_reflection || task.prompt || "",
      }));
  const persona = kit?.persona ?? seed?.persona ?? {};
  const assets = kit?.assets ?? [];
  const seedArtifacts = seed?.sample_artifacts ?? [];
  const stableAssets = [
    ...assets,
    ...seedArtifacts.map((item) => ({
      type: item.type,
      title: item.title,
      status: item.status || "seed",
      show: item.preview || item.demo_action || item.talking_point,
    })),
  ];
  const fallback = kit?.checklist?.[0] || blueprint?.fallbacks?.[0] || seed?.rehearsal_notes?.[0] || "";
  const title = guideDisplayText(blueprint?.title || seed?.title, "录屏检查");
  const summary = guideDisplayText(blueprint?.summary || kit?.summary || seed?.scenario, "打开画像、路线、资源、反馈和产出包，讲一条完整学习闭环。");
  const hasContent = Boolean(blueprint || kit || seed || script || steps.length || stableAssets.length || fallback);

  if (!hasContent) {
    return null;
  }

  return (
    <div className="mt-4 rounded-lg border border-line bg-white p-3" data-testid="guide-demo-recording-checklist">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Video size={16} className="text-brand-purple" />
          <p className="text-sm font-semibold text-ink">录屏检查</p>
        </div>
        <Badge tone={effectStatusTone(Number(blueprint?.readiness_score ?? 0))}>
          {guideDisplayText(blueprint?.readiness_label, `${blueprint?.duration_minutes ?? 7} 分钟`)}
        </Badge>
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-600">{summary}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Badge tone="brand">{title}</Badge>
        {learningStyle?.label ? <Badge tone="success">{learningStyle.label}</Badge> : null}
        {persona.name ? <Badge tone="neutral">{guideDisplayText(persona.name)}</Badge> : null}
        {(persona.weak_points ?? []).slice(0, 1).map((item) => (
          <Badge key={item} tone="warning">{guideDisplayText(item)}</Badge>
        ))}
      </div>
      {steps.length ? (
        <div className="mt-3 grid gap-2 md:grid-cols-3">
          {steps.map((step) => (
            <div key={step.key} className="rounded-lg border border-line bg-canvas p-2">
              <div className="flex items-center gap-2">
                <Badge tone="brand">{guideDisplayText(step.label)}</Badge>
                <p className="min-w-0 truncate text-xs font-semibold text-ink">{guideDisplayText(step.title)}</p>
              </div>
              <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-600">{guideDisplayText(step.detail, "按当前页面顺序展示即可。")}</p>
            </div>
          ))}
        </div>
      ) : null}
      {stableAssets.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {stableAssets.slice(0, 3).map((asset) => (
            <Badge key={`${asset.type}-${asset.title}`} tone={fallbackAssetTone(asset.status)}>
              {fallbackAssetLabel(asset.status)}：{guideDisplayText(asset.title || asset.type, "演示素材")}
            </Badge>
          ))}
        </div>
      ) : null}
      {recordingCue ? (
        <p className="mt-3 rounded-lg border border-brand-purple-300 bg-tint-lavender p-2 text-xs leading-5 text-charcoal" data-testid="guide-recording-script-cue">
          讲稿：{guideDisplayText(recordingCue.narration || recordingCue.screen, "先说明学习者目标，再展示当前任务。")}
        </p>
      ) : null}
      {fallback ? (
        <p className="mt-3 rounded-lg border border-line bg-canvas p-2 text-xs leading-5 text-slate-600">
          兜底：{guideDisplayText(fallback)}
        </p>
      ) : null}
    </div>
  );
}
