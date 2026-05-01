"""Structured guided-learning engine for SparkWeave.

This module is intentionally separate from the legacy guided-learning HTML
generator. It models guidance as a learning loop: profile, course map, path,
tasks, evidence, mastery, and recommendations.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import re
import time
from typing import Any, Awaitable, Callable
import uuid

from sparkweave.logging import get_logger
from sparkweave.services.llm import complete as llm_complete
from sparkweave.services.paths import get_path_service
from sparkweave.services.video_search import recommend_learning_videos

CompletionFn = Callable[..., Awaitable[str]]
CapabilityRunnerFn = Callable[[str, Any], Awaitable[dict[str, Any]]]
GuideResourceEventSink = Callable[[str, dict[str, Any]], None]


@dataclass
class LearnerProfile:
    goal: str
    level: str = "unknown"
    time_budget_minutes: int = 30
    horizon: str = "short"
    preferences: list[str] = field(default_factory=list)
    weak_points: list[str] = field(default_factory=list)
    source_context_summary: str = ""


@dataclass
class CourseNode:
    node_id: str
    title: str
    description: str = ""
    prerequisites: list[str] = field(default_factory=list)
    difficulty: str = "medium"
    estimated_minutes: int = 20
    tags: list[str] = field(default_factory=list)
    mastery_target: str = "Explain the idea and solve one representative task."
    resource_strategy: list[str] = field(default_factory=list)


@dataclass
class CourseMap:
    title: str
    nodes: list[CourseNode] = field(default_factory=list)
    edges: list[dict[str, str]] = field(default_factory=list)
    generated_by: str = "fallback"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LearningTask:
    task_id: str
    node_id: str
    type: str
    title: str
    instruction: str
    estimated_minutes: int = 8
    status: str = "pending"
    success_criteria: list[str] = field(default_factory=list)
    artifact_refs: list[dict[str, Any]] = field(default_factory=list)
    origin: str = "planned"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanAdjustmentEvent:
    event_id: str
    type: str
    reason: str
    created_at: float = field(default_factory=time.time)
    evidence_id: str = ""
    task_id: str = ""
    inserted_task_ids: list[str] = field(default_factory=list)
    skipped_task_ids: list[str] = field(default_factory=list)


@dataclass
class LearningPath:
    path_id: str
    title: str
    rationale: str
    node_sequence: list[str] = field(default_factory=list)
    current_task_id: str = ""
    total_estimated_minutes: int = 0
    today_focus: str = ""
    next_recommendation: str = ""


@dataclass
class LearningEvidence:
    evidence_id: str
    task_id: str
    type: str = "completion"
    score: float | None = None
    reflection: str = ""
    mistake_types: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MasteryState:
    node_id: str
    score: float = 0.0
    status: str = "not_started"
    evidence_count: int = 0
    last_updated: float = field(default_factory=time.time)


@dataclass
class GuideSessionV2:
    session_id: str
    goal: str
    created_at: float
    updated_at: float
    status: str
    profile: LearnerProfile
    course_map: CourseMap
    learning_path: LearningPath
    tasks: list[LearningTask] = field(default_factory=list)
    evidence: list[LearningEvidence] = field(default_factory=list)
    mastery: dict[str, MasteryState] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    plan_events: list[PlanAdjustmentEvent] = field(default_factory=list)
    notebook_context: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GuideSessionV2":
        profile = LearnerProfile(**dict(data.get("profile") or {}))
        course_payload = dict(data.get("course_map") or {})
        nodes = [CourseNode(**dict(item)) for item in course_payload.get("nodes", [])]
        course_map = CourseMap(
            title=str(course_payload.get("title") or "Learning Map"),
            nodes=nodes,
            edges=list(course_payload.get("edges") or []),
            generated_by=str(course_payload.get("generated_by") or "unknown"),
            metadata=dict(course_payload.get("metadata") or {}),
        )
        path_payload = dict(data.get("learning_path") or {})
        learning_path = LearningPath(**path_payload)
        tasks = [LearningTask(**dict(item)) for item in data.get("tasks", [])]
        evidence = [LearningEvidence(**dict(item)) for item in data.get("evidence", [])]
        plan_events = [
            PlanAdjustmentEvent(**dict(item))
            for item in data.get("plan_events", [])
            if isinstance(item, dict)
        ]
        mastery = {
            str(node_id): MasteryState(**dict(payload))
            for node_id, payload in dict(data.get("mastery") or {}).items()
        }
        return cls(
            session_id=str(data.get("session_id") or ""),
            goal=str(data.get("goal") or profile.goal),
            created_at=float(data.get("created_at") or time.time()),
            updated_at=float(data.get("updated_at") or time.time()),
            status=str(data.get("status") or "planned"),
            profile=profile,
            course_map=course_map,
            learning_path=learning_path,
            tasks=tasks,
            evidence=evidence,
            mastery=mastery,
            recommendations=[str(item) for item in data.get("recommendations", [])],
            plan_events=plan_events,
            notebook_context=str(data.get("notebook_context") or ""),
        )


@dataclass
class GuideV2CreateInput:
    goal: str
    level: str = ""
    time_budget_minutes: int | None = None
    horizon: str = ""
    preferences: list[str] = field(default_factory=list)
    weak_points: list[str] = field(default_factory=list)
    notebook_context: str = ""
    course_template_id: str = ""
    use_memory: bool = True
    source_action: dict[str, Any] = field(default_factory=dict)


class GuideV2Manager:
    """Create and update structured guided-learning sessions."""

    def __init__(
        self,
        *,
        output_dir: str | Path | None = None,
        completion_fn: CompletionFn | None = None,
        capability_runner: CapabilityRunnerFn | None = None,
        learner_profile_service: Any | None = None,
        llm_options: dict[str, Any] | None = None,
    ) -> None:
        base_dir = Path(output_dir) if output_dir else get_path_service().get_guide_dir() / "v2"
        self.output_dir = base_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path_service = get_path_service()
        self.template_dirs = [
            path_service.project_root / "data" / "course_templates",
            self.output_dir / "templates",
        ]
        self.completion_fn = completion_fn or llm_complete
        self.capability_runner = capability_runner or _run_langgraph_capability
        self.learner_profile_service = learner_profile_service
        self.llm_options = dict(llm_options or {})
        self.logger = get_logger("GuideV2")
        self._sessions: dict[str, GuideSessionV2] = {}

    async def create_session(self, request: GuideV2CreateInput) -> dict[str, Any]:
        goal = request.goal.strip()
        if not goal:
            return {"success": False, "error": "Learning goal cannot be empty"}

        session_id = uuid.uuid4().hex[:10]
        learner_memory = self.build_learner_memory(refresh=True) if request.use_memory else {}
        unified_profile = await self._read_unified_learner_profile() if request.use_memory else {}
        profile = self._build_profile(request, learner_memory)
        self._apply_unified_profile_to_profile(profile, unified_profile, request=request)
        plan_payload = self._build_template_plan(request.course_template_id, profile)
        if not plan_payload:
            plan_payload = await self._build_plan_with_llm(profile, request.notebook_context)
        course_map = self._normalize_course_map(plan_payload, profile)
        source_action = self._normalize_source_action(request.source_action, goal=goal)
        if source_action:
            course_map.metadata["source_action"] = source_action
            course_map.metadata["created_from"] = source_action.get("source") or "learner_profile"
        tasks = self._normalize_tasks(plan_payload, course_map)
        if source_action and tasks:
            tasks[0].metadata["source_action"] = source_action
        learning_path = self._build_learning_path(plan_payload, profile, course_map, tasks)
        mastery = {
            node.node_id: MasteryState(node_id=node.node_id)
            for node in course_map.nodes
        }
        recommendations = self._build_recommendations(profile, course_map, tasks)
        now = time.time()
        session = GuideSessionV2(
            session_id=session_id,
            goal=goal,
            created_at=now,
            updated_at=now,
            status="planned",
            profile=profile,
            course_map=course_map,
            learning_path=learning_path,
            tasks=tasks,
            mastery=mastery,
            recommendations=recommendations,
            notebook_context=request.notebook_context,
        )
        self._attach_unified_profile_snapshot(session, unified_profile)
        if self._apply_memory_to_new_session(session, learner_memory):
            session.recommendations = self._build_session_recommendations(session)
        if source_action:
            label = str(source_action.get("source_label") or source_action.get("title") or "").strip()
            prefix = f"已根据学习画像建议「{label}」创建本路线。" if label else "已根据学习画像建议创建本路线。"
            session.recommendations.insert(0, prefix)
        self._save_session(session)
        return {"success": True, "session": self.get_session(session_id)}

    def list_sessions(self) -> list[dict[str, Any]]:
        sessions: list[dict[str, Any]] = []
        for path in self.output_dir.glob("session_*.json"):
            try:
                session = GuideSessionV2.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
            current_task = self._current_task(session)
            sessions.append(
                {
                    "session_id": session.session_id,
                    "goal": session.goal,
                    "status": session.status,
                    "created_at": session.created_at,
                    "updated_at": session.updated_at,
                    "progress": self._progress(session),
                    "current_task": asdict(current_task) if current_task else None,
                    "node_count": len(session.course_map.nodes),
                    "task_count": len(session.tasks),
                }
            )
        sessions.sort(key=lambda item: float(item.get("updated_at") or 0), reverse=True)
        return sessions

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        session = self._load_session(session_id)
        if not session:
            return None
        payload = session.to_dict()
        payload["current_task"] = (
            asdict(task) if (task := self._current_task(session)) is not None else None
        )
        payload["progress"] = self._progress(session)
        return payload

    def build_learner_memory(self, *, refresh: bool = True) -> dict[str, Any]:
        """Return the cross-session learner memory used to seed new guides."""

        if refresh:
            return self._refresh_learner_memory()
        payload = self._load_learner_memory()
        return payload if payload else self._refresh_learner_memory()

    def list_course_templates(self) -> list[dict[str, Any]]:
        """List built-in and JSON course templates available to the UI."""

        templates = self._builtin_course_templates()
        known_ids = {str(item.get("id") or "") for item in templates}
        for item in self._load_course_template_files():
            template_id = str(item.get("id") or "").strip()
            if not template_id or template_id in known_ids:
                continue
            templates.append(item)
            known_ids.add(template_id)
        return templates

    def _builtin_course_templates(self) -> list[dict[str, Any]]:
        profile = LearnerProfile(goal="系统学习机器学习基础", level="beginner", time_budget_minutes=45)
        ml_metadata = self._ml_foundations_metadata(profile)
        return [
            {
                "id": "ml_foundations",
                "title": "完整课程：机器学习基础",
                "course_id": ml_metadata.get("course_id"),
                "course_name": ml_metadata.get("course_name"),
                "description": "面向高校初学者的 8 周机器学习入门课程，覆盖数据、回归、优化、分类、评估、决策树和端到端项目。",
                "target_learners": ml_metadata.get("target_learners"),
                "level": "beginner",
                "suggested_weeks": ml_metadata.get("suggested_weeks"),
                "credits": ml_metadata.get("credits"),
                "estimated_minutes": 505,
                "tags": ["machine-learning", "ai", "project-based", "assessment"],
                "default_goal": "我想系统学习机器学习基础，并完成一个端到端建模课程项目。",
                "default_preferences": ["visual", "practice"],
                "default_time_budget_minutes": 45,
            "learning_outcomes": ml_metadata.get("learning_outcomes", []),
            "assessment": ml_metadata.get("assessment", []),
            "project_milestones": ml_metadata.get("project_milestones", []),
            "demo_seed": ml_metadata.get("demo_seed", {}),
        }
        ]

    def _load_course_template_files(self) -> list[dict[str, Any]]:
        templates: list[dict[str, Any]] = []
        for directory in self.template_dirs:
            if not directory.exists():
                continue
            for path in sorted(directory.glob("*.json")):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except Exception as exc:
                    self.logger.warning("Skipping invalid guide course template %s: %s", path, exc)
                    continue
                item = self._normalize_external_course_template(payload, path)
                if item:
                    templates.append(item)
        return templates

    @staticmethod
    def _normalize_external_course_template(
        payload: Any,
        path: Path,
    ) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None
        template_id = str(payload.get("id") or path.stem).strip()
        title = str(payload.get("title") or payload.get("course_name") or template_id).strip()
        if not template_id or not title:
            return None
        return {
            "id": template_id,
            "title": title,
            "course_id": str(payload.get("course_id") or "").strip(),
            "course_name": str(payload.get("course_name") or title).strip(),
            "description": str(payload.get("description") or "").strip(),
            "target_learners": str(payload.get("target_learners") or "").strip(),
            "level": str(payload.get("level") or "").strip(),
            "suggested_weeks": GuideV2Manager._coerce_int(payload.get("suggested_weeks"), default=0),
            "credits": GuideV2Manager._coerce_int(payload.get("credits"), default=0),
            "estimated_minutes": GuideV2Manager._coerce_int(payload.get("estimated_minutes"), default=0),
            "tags": [
                str(item).strip()
                for item in payload.get("tags", [])
                if str(item).strip()
            ]
            if isinstance(payload.get("tags"), list)
            else [],
            "default_goal": str(payload.get("default_goal") or "").strip(),
            "default_preferences": [
                str(item).strip()
                for item in payload.get("default_preferences", [])
                if str(item).strip()
            ]
            if isinstance(payload.get("default_preferences"), list)
            else [],
            "default_time_budget_minutes": GuideV2Manager._coerce_int(
                payload.get("default_time_budget_minutes"),
                default=30,
            ),
            "learning_outcomes": [
                str(item).strip()
                for item in payload.get("learning_outcomes", [])
                if str(item).strip()
            ]
            if isinstance(payload.get("learning_outcomes"), list)
            else [],
            "assessment": payload.get("assessment", []) if isinstance(payload.get("assessment"), list) else [],
            "project_milestones": payload.get("project_milestones", [])
            if isinstance(payload.get("project_milestones"), list)
            else [],
        }

    @staticmethod
    def _coerce_int(value: Any, *, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _diagnostic_questions(self, session: GuideSessionV2) -> list[dict[str, Any]]:
        nodes = session.course_map.nodes[:4]
        questions: list[dict[str, Any]] = [
            {
                "question_id": "experience_level",
                "type": "single_choice",
                "prompt": "你对这个学习目标的熟悉程度更接近哪一种？",
                "options": [
                    {"value": "new", "label": "几乎没系统学过"},
                    {"value": "learned", "label": "学过一些，但容易混淆"},
                    {"value": "can_apply", "label": "能解决基础题，想进一步提升"},
                ],
            },
            {
                "question_id": "time_fit",
                "type": "single_choice",
                "prompt": "你为这条路线预留的时间是否充足？",
                "options": [
                    {"value": "tight", "label": "比较紧，需要先抓重点"},
                    {"value": "fit", "label": "基本合适，可以按计划推进"},
                    {"value": "enough", "label": "时间充足，可以多做项目和迁移"},
                ],
            },
            {
                "question_id": "preferred_resource",
                "type": "single_choice",
                "prompt": "遇到不懂的地方，你更希望系统先给哪类资源？",
                "options": [
                    {"value": "visual", "label": "图解关系"},
                    {"value": "practice", "label": "练习检测"},
                    {"value": "video", "label": "短视频讲解"},
                    {"value": "research", "label": "资料拓展"},
                ],
            },
            {
                "question_id": "current_bottleneck",
                "type": "single_choice",
                "prompt": "如果现在学不下去，最可能卡在哪里？",
                "options": [
                    {"value": "concept", "label": "概念边界不清"},
                    {"value": "formula", "label": "公式/推导断裂"},
                    {"value": "practice", "label": "会看不会做题"},
                    {"value": "application", "label": "不知道如何迁移应用"},
                    {"value": "coding", "label": "实现或代码细节"},
                ],
            },
        ]
        for node in nodes[:3]:
            questions.append(
                {
                    "question_id": f"confidence:{node.node_id}",
                    "type": "scale",
                    "prompt": f"你对「{node.title}」的掌握程度是多少？",
                    "min": 1,
                    "max": 5,
                    "labels": {"1": "完全陌生", "3": "能说一点", "5": "能解释并应用"},
                    "node_id": node.node_id,
                    "node_title": node.title,
                }
            )
        if nodes:
            questions.append(
                {
                    "question_id": "weak_nodes",
                    "type": "multi_select",
                    "prompt": "下面哪些内容你希望系统优先照顾？",
                    "options": [
                        {"value": node.node_id, "label": node.title}
                        for node in nodes
                    ],
                }
            )
        return questions

    def _score_diagnostic_answers(
        self,
        session: GuideSessionV2,
        answers: list[dict[str, Any]],
    ) -> dict[str, Any]:
        answer_map = {
            str(item.get("question_id") or ""): item.get("value")
            for item in answers
            if isinstance(item, dict)
        }
        score_parts: list[float] = []
        experience_scores = {"new": 0.35, "learned": 0.65, "can_apply": 0.85}
        time_scores = {"tight": 0.55, "fit": 0.75, "enough": 0.9}
        if answer_map.get("experience_level") in experience_scores:
            score_parts.append(experience_scores[str(answer_map["experience_level"])])
        if answer_map.get("time_fit") in time_scores:
            score_parts.append(time_scores[str(answer_map["time_fit"])])

        weak_node_ids: set[str] = set()
        confidence_by_node: dict[str, float] = {}
        for key, value in answer_map.items():
            if not key.startswith("confidence:"):
                continue
            node_id = key.split(":", 1)[1]
            confidence = max(1.0, min(float(value or 1), 5.0))
            normalized = confidence / 5.0
            confidence_by_node[node_id] = normalized
            score_parts.append(normalized)
            if confidence <= 2:
                weak_node_ids.add(node_id)

        selected_weak = answer_map.get("weak_nodes")
        if isinstance(selected_weak, list):
            weak_node_ids.update(str(item) for item in selected_weak if str(item).strip())
        elif selected_weak:
            weak_node_ids.add(str(selected_weak))

        node_titles = {node.node_id: node.title for node in session.course_map.nodes}
        weak_points = [
            node_titles.get(node_id, node_id)
            for node_id in weak_node_ids
            if node_titles.get(node_id, node_id)
        ][:6]
        readiness = round(sum(score_parts) / len(score_parts), 3) if score_parts else 0.5
        if readiness < 0.55:
            label = "needs_foundation"
        elif readiness < 0.75:
            label = "ready_with_support"
        else:
            label = "ready_to_learn"

        preferred = str(answer_map.get("preferred_resource") or "").strip()
        bottleneck = str(answer_map.get("current_bottleneck") or "").strip()
        bottleneck_labels = {
            "concept": "概念边界不清",
            "formula": "公式/推导断裂",
            "practice": "会看不会做题",
            "application": "不知道如何迁移应用",
            "coding": "实现或代码细节",
        }
        bottleneck_label = bottleneck_labels.get(bottleneck, "")
        learning_strategy = self._diagnostic_learning_strategy(
            readiness_label=label,
            weak_points=weak_points,
            preferred_resource=preferred,
            bottleneck=bottleneck,
            bottleneck_label=bottleneck_label,
        )
        recommendations = self._diagnostic_recommendations(
            readiness_label=label,
            weak_points=weak_points,
            preferred_resource=preferred,
            bottleneck_label=bottleneck_label,
        )
        reflection = (
            f"Diagnostic readiness={readiness}; label={label}; "
            f"weak_points={', '.join(weak_points) if weak_points else 'none'}; "
            f"preferred_resource={preferred or 'auto'}; "
            f"bottleneck={bottleneck or 'unknown'}."
        )
        return {
            "readiness_score": readiness,
            "readiness_label": label,
            "weak_points": weak_points,
            "preferred_resource": preferred,
            "current_bottleneck": bottleneck,
            "bottleneck_label": bottleneck_label,
            "confidence_by_node": confidence_by_node,
            "learning_strategy": learning_strategy,
            "recommendations": recommendations,
            "reflection": reflection,
        }

    @staticmethod
    def _diagnostic_recommendations(
        *,
        readiness_label: str,
        weak_points: list[str],
        preferred_resource: str,
        bottleneck_label: str = "",
    ) -> list[str]:
        recommendations: list[str] = []
        if readiness_label == "needs_foundation":
            recommendations.append("先补一段基础导入任务，再进入原计划的核心任务。")
        elif readiness_label == "ready_with_support":
            recommendations.append("可以进入计划，但每个学习块后需要用练习或反思确认掌握。")
        else:
            recommendations.append("可以按当前路线推进，并尽早加入迁移应用或项目产出。")
        if weak_points:
            recommendations.append(f"优先照顾薄弱点：{weak_points[0]}。")
        if bottleneck_label:
            recommendations.append(f"当前主要卡点是「{bottleneck_label}」，后续任务会优先围绕它安排资源和验证。")
        if preferred_resource:
            labels = {"visual": "图解", "practice": "练习", "video": "短视频", "external_video": "公开视频", "research": "资料"}
            recommendations.append(f"遇到阻塞时，优先生成{labels.get(preferred_resource, preferred_resource)}资源。")
        return recommendations[:4]

    @staticmethod
    def _diagnostic_learning_strategy(
        *,
        readiness_label: str,
        weak_points: list[str],
        preferred_resource: str,
        bottleneck: str,
        bottleneck_label: str,
    ) -> list[dict[str, Any]]:
        focus = weak_points[0] if weak_points else bottleneck_label or "当前目标"
        resource_labels = {"visual": "图解", "practice": "练习", "video": "短视频", "external_video": "公开视频", "research": "资料"}
        preferred_label = resource_labels.get(preferred_resource, "图解或练习")
        strategy: list[dict[str, Any]] = []
        if readiness_label == "needs_foundation":
            strategy.append(
                {
                    "phase": "补基础",
                    "action": f"先用一个最小例子讲清「{focus}」的定义、条件和反例。",
                    "resource_type": "visual" if preferred_resource != "practice" else "research",
                    "success_check": "能用自己的话说出概念边界，并指出一个错误理解。",
                }
            )
        else:
            strategy.append(
                {
                    "phase": "校准",
                    "action": f"快速复述「{focus}」的关键判断步骤，确认哪些地方已经会、哪些地方只是熟悉。",
                    "resource_type": "visual",
                    "success_check": "能把关键步骤压缩成 3 条以内的判断规则。",
                }
            )

        if bottleneck == "formula":
            strategy.append(
                {
                    "phase": "拆公式",
                    "action": "把公式拆成符号含义、前提条件、推导中断点和一个数值例子。",
                    "resource_type": "video",
                    "success_check": "能指出每个符号的来源，并完成一次不看答案的推导复述。",
                }
            )
        elif bottleneck == "practice":
            strategy.append(
                {
                    "phase": "做题闭环",
                    "action": "生成 3 道由易到难的混合题，先暴露错误，再用解析修正判断方法。",
                    "resource_type": "quiz",
                    "success_check": "正确率达到 80% 以上，并能解释错题原因。",
                }
            )
        elif bottleneck == "application":
            strategy.append(
                {
                    "phase": "迁移",
                    "action": "换一个真实场景，用同一知识点解决新问题，避免只会原题。",
                    "resource_type": "research",
                    "success_check": "能说清新场景和原任务之间的共同结构。",
                }
            )
        elif bottleneck == "coding":
            strategy.append(
                {
                    "phase": "实现",
                    "action": "先写伪代码或流程图，再对照一个最小可运行例子检查输入、输出和边界条件。",
                    "resource_type": "research",
                    "success_check": "能解释每一步代码对应的概念含义。",
                }
            )
        else:
            strategy.append(
                {
                    "phase": "验证",
                    "action": f"优先生成{preferred_label}资源，再回到当前任务提交一条可评分证据。",
                    "resource_type": preferred_resource or "visual",
                    "success_check": "提交反思、练习结果或资源使用记录。",
                }
            )

        strategy.append(
            {
                "phase": "回写证据",
                "action": "完成任务后提交掌握分、错因和一句反思，让路线继续自动调整。",
                "resource_type": "evidence",
                "success_check": "系统能根据证据决定继续、补救或复测。",
            }
        )
        return strategy[:3]

    def _apply_diagnostic_profile(
        self,
        session: GuideSessionV2,
        diagnosis: dict[str, Any],
    ) -> None:
        def append_unique(items: list[str], value: str, *, limit: int = 8) -> None:
            cleaned = " ".join(str(value or "").split()).strip()
            if not cleaned:
                return
            if cleaned.lower() not in {item.lower() for item in items}:
                items.append(cleaned)
            del items[limit:]

        for weak in diagnosis.get("weak_points", []):
            append_unique(session.profile.weak_points, str(weak))
        preferred = str(diagnosis.get("preferred_resource") or "")
        if preferred:
            append_unique(
                session.profile.preferences,
                "practice" if preferred == "practice" else preferred,
            )
        score = float(diagnosis.get("readiness_score") or 0)
        if score < 0.45:
            session.profile.level = "beginner"
        elif score >= 0.8 and session.profile.level in {"", "unknown", "beginner"}:
            session.profile.level = "intermediate"
        session.profile.source_context_summary = (
            f"Diagnostic: {diagnosis.get('readiness_label')} "
            f"({round(score * 100)}%), weak={', '.join(diagnosis.get('weak_points', [])) or 'none'}, "
            f"bottleneck={diagnosis.get('bottleneck_label') or diagnosis.get('current_bottleneck') or 'unknown'}"
        )

    def _apply_diagnostic_mastery(
        self,
        session: GuideSessionV2,
        diagnosis: dict[str, Any],
    ) -> None:
        confidence = diagnosis.get("confidence_by_node", {})
        if not isinstance(confidence, dict):
            return
        for node_id, raw_score in confidence.items():
            state = session.mastery.setdefault(str(node_id), MasteryState(node_id=str(node_id)))
            score = max(0.0, min(float(raw_score or 0), 1.0))
            state.score = round(max(state.score, score * 0.6), 3)
            state.evidence_count = max(state.evidence_count, 1)
            state.last_updated = time.time()
            state.status = "mastered" if score >= 0.8 else "learning" if score >= 0.45 else "needs_support"

    def _adapt_path_from_diagnostic(
        self,
        session: GuideSessionV2,
        diagnosis: dict[str, Any],
        evidence: LearningEvidence,
    ) -> list[PlanAdjustmentEvent]:
        events: list[PlanAdjustmentEvent] = []
        readiness = float(diagnosis.get("readiness_score") or 0)
        weak_points = [str(item) for item in diagnosis.get("weak_points", []) if str(item).strip()]
        bottleneck_label = str(diagnosis.get("bottleneck_label") or "").strip()
        current = self._current_task(session)
        if current is None:
            return events

        current_index = next(
            (index for index, item in enumerate(session.tasks) if item.task_id == current.task_id),
            0,
        )
        existing_remediation = any(
            task.origin == "diagnostic_remediation" and task.status not in {"completed", "skipped"}
            for task in session.tasks
        )
        if readiness < 0.65 and not existing_remediation:
            target = weak_points[0] if weak_points else current.title
            bottleneck_hint = f"当前主要卡点是「{bottleneck_label}」，" if bottleneck_label else ""
            task = LearningTask(
                task_id=self._next_task_id(session, "D"),
                node_id=current.node_id,
                type="diagnostic",
                title=f"前测补基：{target}",
                instruction=(
                    f"{bottleneck_hint}先用 10 分钟补齐「{target}」的基础概念，再回到原任务。"
                    "建议生成一张图解或一组入门练习来验证理解。"
                ),
                estimated_minutes=max(8, min(current.estimated_minutes, 15)),
                success_criteria=[
                    "能说清这个薄弱点的核心定义",
                    "完成至少一道入门练习或写下一句反思",
                    "重新评估是否可以进入原任务",
                ],
                origin="diagnostic_remediation",
                metadata={
                    "trigger_evidence_id": evidence.evidence_id,
                    "readiness_score": readiness,
                    "weak_points": weak_points,
                    "current_bottleneck": diagnosis.get("current_bottleneck", ""),
                    "bottleneck_label": bottleneck_label,
                    "learning_strategy": diagnosis.get("learning_strategy", []),
                },
            )
            session.tasks.insert(current_index, task)
            event = PlanAdjustmentEvent(
                event_id=uuid.uuid4().hex[:10],
                type="diagnostic_remediation",
                reason=f"前测准备度为 {round(readiness * 100)}%，系统将基础补强任务提前到当前任务之前。",
                evidence_id=evidence.evidence_id,
                task_id=current.task_id,
                inserted_task_ids=[task.task_id],
            )
            session.plan_events.append(event)
            events.append(event)
        else:
            event = PlanAdjustmentEvent(
                event_id=uuid.uuid4().hex[:10],
                type="diagnostic_profile_update",
                reason=f"前测准备度为 {round(readiness * 100)}%，系统已更新学习画像和资源偏好。",
                evidence_id=evidence.evidence_id,
                task_id=current.task_id,
            )
            session.plan_events.append(event)
            events.append(event)

        session.learning_path.total_estimated_minutes = sum(
            item.estimated_minutes for item in session.tasks if item.status != "skipped"
        )
        session.learning_path.next_recommendation = events[-1].reason if events else session.learning_path.next_recommendation
        return events

    @staticmethod
    def _latest_diagnostic_evidence(session: GuideSessionV2) -> LearningEvidence | None:
        return max(
            (item for item in session.evidence if item.type == "diagnostic"),
            key=lambda item: item.created_at,
            default=None,
        )

    def _profile_dialogue_prompts(self, session: GuideSessionV2) -> list[str]:
        current = self._current_task(session)
        node_titles = [node.title for node in session.course_map.nodes[:3]]
        prompts = [
            "我今天只有 20 分钟，想先抓最重要的部分。",
            "我更喜欢先看图解，再做几道题确认。",
            "我对公式推导不太熟，容易看懂但不会自己做。",
        ]
        if current:
            prompts.insert(0, f"我对「{current.title}」不太确定，帮我先补一下基础。")
        if node_titles:
            prompts.append(f"我最担心「{node_titles[0]}」，希望路线先照顾它。")
        return prompts[:5]

    def _extract_profile_dialogue_signals(
        self,
        session: GuideSessionV2,
        message: str,
    ) -> dict[str, Any]:
        lowered = message.lower()
        preferences: list[str] = []
        if any(token in lowered for token in ("图", "图解", "可视化", "visual", "diagram")):
            preferences.append("visual")
        if any(token in lowered for token in ("公开视频", "公开课", "网课", "b站", "bilibili", "youtube", "external video")):
            preferences.append("external_video")
        if any(token in lowered for token in ("视频", "动画", "manim", "video", "animation")):
            preferences.append("video")
        if any(token in lowered for token in ("题", "练习", "测试", "quiz", "exercise", "practice")):
            preferences.append("practice")
        if any(token in lowered for token in ("资料", "论文", "搜索", "文献", "research", "paper")):
            preferences.append("research")

        level = ""
        if any(token in lowered for token in ("零基础", "没学过", "刚入门", "beginner")):
            level = "beginner"
        elif any(token in lowered for token in ("深入", "进阶", "论文", "项目", "advanced")):
            level = "advanced"
        elif any(token in lowered for token in ("学过", "复习", "不稳", "intermediate")):
            level = "intermediate"

        horizon = ""
        if any(token in lowered for token in ("今天", "今晚", "today")):
            horizon = "today"
        elif any(token in lowered for token in ("一周", "本周", "week")):
            horizon = "week"

        time_budget = None
        minute_match = re.search(r"(\d{1,3})\s*(?:分钟|分|min|minutes?)", message, re.IGNORECASE)
        hour_match = re.search(r"(\d{1,2})\s*(?:小时|h|hours?)", message, re.IGNORECASE)
        if minute_match:
            time_budget = max(5, min(int(minute_match.group(1)), 240))
        elif hour_match:
            time_budget = max(5, min(int(hour_match.group(1)) * 60, 240))

        weak_points: list[str] = []
        weak_node_ids: list[str] = []
        weakness_markers = ("不会", "不太会", "不懂", "不熟", "薄弱", "困难", "卡", "担心", "害怕", "不太确定")
        for node in session.course_map.nodes:
            if node.title and node.title in message:
                weak_node_ids.append(node.node_id)
                weak_points.append(node.title)
            elif any(tag and tag.lower() in lowered for tag in node.tags):
                weak_node_ids.append(node.node_id)
                weak_points.append(node.title)
        if any(token in lowered for token in weakness_markers):
            if any(token in lowered for token in ("公式", "推导", "derive", "math")):
                weak_points.append("公式推导")
            if any(token in lowered for token in ("代码", "编程", "实现", "code")):
                weak_points.append("代码实现")
            if any(token in lowered for token in ("概念", "直觉", "intuition")):
                weak_points.append("概念直觉")
            if not weak_points and session.course_map.nodes:
                weak_node_ids.append(session.course_map.nodes[0].node_id)
                weak_points.append(session.course_map.nodes[0].title)

        readiness = 0.7
        if level == "beginner":
            readiness -= 0.18
        if weak_points:
            readiness -= 0.12
        if time_budget is not None and time_budget < max(20, session.profile.time_budget_minutes):
            readiness -= 0.08
        if level == "advanced":
            readiness += 0.08
        readiness = round(max(0.25, min(readiness, 0.95)), 3)

        return {
            "preferences": self._dedupe_strings(preferences),
            "level": level,
            "horizon": horizon,
            "time_budget_minutes": time_budget,
            "weak_points": self._dedupe_strings(weak_points),
            "weak_node_ids": self._dedupe_strings(weak_node_ids),
            "readiness_score": readiness,
        }

    def _apply_profile_dialogue_signals(
        self,
        session: GuideSessionV2,
        signals: dict[str, Any],
    ) -> None:
        for pref in signals.get("preferences", []) or []:
            self._append_unique(session.profile.preferences, str(pref))
        for weak in signals.get("weak_points", []) or []:
            self._append_unique(session.profile.weak_points, str(weak))
        if signals.get("level"):
            session.profile.level = str(signals["level"])
        if signals.get("horizon"):
            session.profile.horizon = str(signals["horizon"])
        if signals.get("time_budget_minutes"):
            session.profile.time_budget_minutes = max(5, min(int(signals["time_budget_minutes"]), 240))
        score = float(signals.get("readiness_score") or 0)
        session.profile.source_context_summary = (
            f"Profile dialogue: readiness={round(score * 100)}%, "
            f"weak={', '.join(signals.get('weak_points') or []) or 'none'}, "
            f"prefs={', '.join(signals.get('preferences') or []) or 'auto'}"
        )
        for node_id in signals.get("weak_node_ids", []) or []:
            state = session.mastery.setdefault(str(node_id), MasteryState(node_id=str(node_id)))
            state.status = "needs_support"
            state.score = min(state.score, 0.35)
            state.evidence_count = max(state.evidence_count, 1)
            state.last_updated = time.time()

    def _adapt_path_from_profile_dialogue(
        self,
        session: GuideSessionV2,
        signals: dict[str, Any],
        evidence: LearningEvidence,
    ) -> list[PlanAdjustmentEvent]:
        weak_points = [str(item) for item in signals.get("weak_points", []) if str(item).strip()]
        if not weak_points:
            event = PlanAdjustmentEvent(
                event_id=uuid.uuid4().hex[:10],
                type="profile_dialogue_update",
                reason="已根据对话更新学习画像和资源偏好。",
                evidence_id=evidence.evidence_id,
                task_id=evidence.task_id,
            )
            session.plan_events.append(event)
            return [event]

        current = self._current_task(session)
        if current is None:
            return []
        has_pending_focus = any(
            task.origin == "profile_dialogue" and task.status not in {"completed", "skipped"}
            for task in session.tasks
        )
        if has_pending_focus:
            event = PlanAdjustmentEvent(
                event_id=uuid.uuid4().hex[:10],
                type="profile_dialogue_update",
                reason=f"画像已更新，继续优先处理薄弱点：{weak_points[0]}。",
                evidence_id=evidence.evidence_id,
                task_id=current.task_id,
            )
            session.plan_events.append(event)
            return [event]

        current_index = next(
            (index for index, item in enumerate(session.tasks) if item.task_id == current.task_id),
            0,
        )
        focus_task = LearningTask(
            task_id=self._next_task_id(session, "P"),
            node_id=current.node_id,
            type="profile_focus",
            title=f"画像补强：{weak_points[0]}",
            instruction=(
                f"先围绕「{weak_points[0]}」做一次最小补强：用自己的话解释它，"
                "再生成图解或练习确认是否能继续当前任务。"
            ),
            estimated_minutes=max(8, min(session.profile.time_budget_minutes, 15)),
            success_criteria=[
                "能说出薄弱点的核心含义",
                "完成一次图解/练习/反思中的至少一种",
                "给出新的掌握评分",
            ],
            origin="profile_dialogue",
            metadata={
                "trigger_evidence_id": evidence.evidence_id,
                "weak_points": weak_points,
                "signals": signals,
            },
        )
        session.tasks.insert(current_index, focus_task)
        event = PlanAdjustmentEvent(
            event_id=uuid.uuid4().hex[:10],
            type="profile_dialogue_focus",
            reason=f"对话中识别到薄弱点「{weak_points[0]}」，系统把补强任务提前到当前任务之前。",
            evidence_id=evidence.evidence_id,
            task_id=current.task_id,
            inserted_task_ids=[focus_task.task_id],
        )
        session.plan_events.append(event)
        session.learning_path.total_estimated_minutes = sum(
            item.estimated_minutes for item in session.tasks if item.status != "skipped"
        )
        session.learning_path.next_recommendation = event.reason
        return [event]

    def _profile_dialogue_reply(
        self,
        session: GuideSessionV2,
        signals: dict[str, Any],
    ) -> str:
        parts: list[str] = []
        if signals.get("time_budget_minutes"):
            parts.append(f"我已把单次学习时间调整为 {signals['time_budget_minutes']} 分钟")
        if signals.get("preferences"):
            parts.append(f"优先资源改为 {', '.join(signals['preferences'])}")
        if signals.get("weak_points"):
            parts.append(f"会先照顾薄弱点：{', '.join(signals['weak_points'][:2])}")
        if signals.get("level"):
            parts.append(f"当前水平更新为 {signals['level']}")
        if not parts:
            current = self._current_task(session)
            return f"我已记录这条画像信息。下一步建议继续完成「{current.title if current else '当前任务'}」，并留下学习证据。"
        return "；".join(parts) + "。我已经据此刷新路线和推荐。"

    @staticmethod
    def _latest_profile_dialogue_evidence(session: GuideSessionV2) -> LearningEvidence | None:
        return max(
            (item for item in session.evidence if item.type == "profile_dialogue"),
            key=lambda item: item.created_at,
            default=None,
        )

    @staticmethod
    def _append_unique(items: list[str], value: str, *, limit: int = 8) -> None:
        cleaned = " ".join(str(value or "").split()).strip()
        if not cleaned:
            return
        if cleaned.lower() not in {item.lower() for item in items}:
            items.append(cleaned)
        del items[limit:]

    @staticmethod
    def _dedupe_strings(items: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for item in items:
            cleaned = " ".join(str(item or "").split()).strip()
            key = cleaned.lower()
            if cleaned and key not in seen:
                deduped.append(cleaned)
                seen.add(key)
        return deduped

    def complete_task(
        self,
        session_id: str,
        task_id: str,
        *,
        score: float | None = None,
        reflection: str = "",
        mistake_types: list[str] | None = None,
    ) -> dict[str, Any]:
        session = self._load_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}
        task = next((item for item in session.tasks if item.task_id == task_id), None)
        if task is None:
            return {"success": False, "error": "Task not found"}
        task.status = "completed"
        evidence = LearningEvidence(
            evidence_id=uuid.uuid4().hex[:10],
            task_id=task_id,
            score=self._bounded_score(score),
            reflection=reflection.strip(),
            mistake_types=[str(item).strip() for item in (mistake_types or []) if str(item).strip()],
        )
        evidence.metadata["evidence_quality"] = self._evidence_quality_profile(task, evidence)
        session.evidence.append(evidence)
        self._update_mastery(session, task, evidence)
        self._update_profile_from_evidence(session, task, evidence)
        adjustments = self._adapt_learning_path(session, task, evidence)
        next_task = self._first_pending_task(session)
        session.learning_path.current_task_id = next_task.task_id if next_task else ""
        session.status = "completed" if next_task is None else "learning"
        session.recommendations = self._build_session_recommendations(session)
        feedback = self._learning_feedback(session, task, evidence, adjustments, next_task)
        evidence.metadata["learning_feedback"] = feedback
        session.updated_at = time.time()
        self._save_session(session)
        return {
            "success": True,
            "session": self.get_session(session_id),
            "completed_task": asdict(task),
            "evidence": asdict(evidence),
            "adjustments": [asdict(item) for item in adjustments],
            "next_task": asdict(next_task) if next_task else None,
            "learning_feedback": feedback,
        }

    def refresh_recommendations(self, session_id: str) -> dict[str, Any]:
        session = self._load_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}
        session.recommendations = self._build_session_recommendations(session)
        session.updated_at = time.time()
        self._save_session(session)
        return {"success": True, "recommendations": session.recommendations}

    def evaluate_session(self, session_id: str) -> dict[str, Any]:
        session = self._load_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        total_tasks = len(session.tasks)
        completed_tasks = sum(1 for task in session.tasks if task.status == "completed")
        skipped_tasks = sum(1 for task in session.tasks if task.status == "skipped")
        progress = self._progress(session)
        evidence_scores = [
            float(item.score)
            for item in session.evidence
            if item.score is not None
        ]
        average_evidence_score = (
            round(sum(evidence_scores) / len(evidence_scores), 3)
            if evidence_scores
            else 0.0
        )
        mastery_scores = [state.score for state in session.mastery.values()]
        average_mastery = (
            round(sum(mastery_scores) / len(mastery_scores), 3)
            if mastery_scores
            else 0.0
        )
        resource_counts = self._resource_counts(session)
        question_count = self._quiz_question_count(session)
        overall_score = round(
            progress * 0.35
            + average_evidence_score * 100 * 0.35
            + average_mastery * 100 * 0.30
        )
        learner_profile_context = self._evaluation_profile_context(session)
        risk_signals = self._risk_signals(session)
        next_actions = self._evaluation_next_actions(
            session,
            progress=progress,
            average_evidence_score=average_evidence_score,
            question_count=question_count,
            resource_counts=resource_counts,
        )
        risk_signals = self._profile_risk_signals(risk_signals, learner_profile_context)
        next_actions = self._profile_next_actions(next_actions, learner_profile_context)
        evaluation = {
            "success": True,
            "session_id": session.session_id,
            "generated_at": time.time(),
            "overall_score": max(0, min(int(overall_score), 100)),
            "readiness": self._readiness_label(overall_score, progress),
            "progress": progress,
            "completed_tasks": completed_tasks,
            "skipped_tasks": skipped_tasks,
            "total_tasks": total_tasks,
            "path_adjustment_count": len(session.plan_events),
            "average_evidence_score": average_evidence_score,
            "average_mastery": average_mastery,
            "mastery_distribution": self._mastery_distribution(session),
            "resource_counts": resource_counts,
            "question_count": question_count,
            "evidence_count": len(session.evidence),
            "evidence_trend": self._evidence_trend(session),
            "node_evaluations": self._node_evaluations(session),
            "strengths": self._strengths(session),
            "risk_signals": risk_signals,
            "next_actions": next_actions,
            "learner_profile_context": learner_profile_context,
        }
        return evaluation

    def build_learning_timeline(self, session_id: str) -> dict[str, Any]:
        """Build a unified timeline from behavior, evidence, and path events."""

        session = self._load_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        events = self._learning_timeline_events(session)
        summary = self._learning_timeline_summary(session, events)
        return {
            "success": True,
            "session_id": session.session_id,
            "generated_at": time.time(),
            "summary": summary,
            "events": events,
            "recent_events": sorted(events, key=lambda item: float(item.get("created_at") or 0), reverse=True)[:12],
            "behavior_tags": self._learning_behavior_tags(session, summary),
        }

    def build_mistake_review(self, session_id: str) -> dict[str, Any]:
        """Build a visible mistake -> remediation -> retest loop."""

        session = self._load_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        clusters = self._mistake_clusters(session)
        low_evidence = [
            item
            for item in session.evidence
            if item.score is not None and item.score < 0.65
        ]
        remediation_tasks = [
            asdict(task)
            for task in session.tasks
            if task.origin in {"adaptive_remediation", "diagnostic_remediation"}
        ]
        retest_tasks = [
            asdict(task)
            for task in session.tasks
            if task.origin == "adaptive_retest"
        ]
        pending_retests = [task for task in retest_tasks if task.get("status") not in {"completed", "skipped"}]
        pending_remediations = [
            task for task in remediation_tasks if task.get("status") not in {"completed", "skipped"}
        ]
        open_clusters = [item for item in clusters if item.get("loop_status") != "closed"]
        closed_clusters = [item for item in clusters if item.get("loop_status") == "closed"]
        return {
            "success": True,
            "session_id": session.session_id,
            "generated_at": time.time(),
            "summary": {
                "cluster_count": len(clusters),
                "open_cluster_count": len(open_clusters),
                "closed_cluster_count": len(closed_clusters),
                "low_score_evidence_count": len(low_evidence),
                "remediation_task_count": len(remediation_tasks),
                "pending_remediation_count": len(pending_remediations),
                "retest_task_count": len(retest_tasks),
                "pending_retest_count": len(pending_retests),
                "closed_loop": bool(clusters and not open_clusters),
            },
            "clusters": clusters,
            "remediation_tasks": remediation_tasks,
            "retest_tasks": retest_tasks,
            "retest_plan": self._mistake_retest_plan(session, clusters, pending_remediations, pending_retests),
        }

    def build_coach_briefing(self, session_id: str) -> dict[str, Any]:
        """Build a learner-facing action briefing for the current study moment."""

        session = self._load_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        evaluation = self.evaluate_session(session_id)
        if not evaluation.get("success"):
            return evaluation

        current_task = self._current_task(session)
        mistake_review = self.build_mistake_review(session_id)
        if not mistake_review.get("success"):
            mistake_review = {
                "summary": {},
                "clusters": [],
                "remediation_tasks": [],
                "retest_tasks": [],
            }
        loop_context = self._coach_loop_context(session, mistake_review)
        priority_task = loop_context.get("task")
        if isinstance(priority_task, LearningTask):
            current_task = priority_task
        effect_context = self._effect_context(session, evaluation=evaluation, mistake_review=mistake_review)
        timeline_events = effect_context["timeline_events"]
        behavior_summary = effect_context["behavior_summary"]
        feedback_digest = effect_context["feedback_digest"]
        effect_assessment = effect_context["effect_assessment"]
        learner_profile_context = effect_context.get("learner_profile_context", {})
        recent_events = sorted(timeline_events, key=lambda item: float(item.get("created_at") or 0), reverse=True)[:5]
        resource_plan = self.recommend_resources(session_id)
        resource_shortcuts = list(resource_plan.get("recommendations") or [])[:3] if resource_plan.get("success") else []
        node_titles = {node.node_id: node.title for node in session.course_map.nodes}
        mastery = (
            session.mastery.get(current_task.node_id, MasteryState(node_id=current_task.node_id))
            if current_task
            else None
        )
        blockers = self._coach_blockers(session, evaluation, behavior_summary, loop_context, effect_assessment)
        micro_plan = self._coach_micro_plan(current_task, resource_shortcuts, evaluation, loop_context)
        coach_actions = self._coach_actions(current_task, loop_context, resource_shortcuts, effect_assessment)
        briefing = {
            "success": True,
            "session_id": session.session_id,
            "generated_at": time.time(),
            "coach_mode": loop_context.get("mode", "normal"),
            "priority_reason": loop_context.get("priority_reason", ""),
            "mistake_summary": mistake_review.get("summary", {}),
            "priority_mistake": loop_context.get("cluster"),
            "headline": self._coach_headline(session, evaluation, current_task, loop_context),
            "summary": self._coach_summary(session, evaluation, behavior_summary, loop_context),
            "focus": {
                "task_id": current_task.task_id if current_task else "",
                "task_title": current_task.title if current_task else "",
                "task_type": current_task.type if current_task else "",
                "node_id": current_task.node_id if current_task else "",
                "node_title": node_titles.get(current_task.node_id, "") if current_task else "",
                "estimated_minutes": current_task.estimated_minutes if current_task else 0,
                "status": current_task.status if current_task else "done",
                "mastery_score": mastery.score if mastery else 0.0,
                "mastery_status": mastery.status if mastery else "not_started",
                "success_criteria": current_task.success_criteria if current_task else [],
            },
            "next_actions": evaluation.get("next_actions", []),
            "blockers": blockers,
            "evidence_reasons": self._coach_evidence_reasons(session, recent_events, behavior_summary),
            "micro_plan": micro_plan,
            "coach_actions": coach_actions,
            "resource_shortcuts": resource_shortcuts,
            "behavior_summary": behavior_summary,
            "feedback_digest": feedback_digest,
            "effect_assessment": effect_assessment,
            "learner_profile_context": learner_profile_context,
            "strategy_adjustments": effect_assessment.get("strategy_adjustments", []),
            "recent_events": recent_events,
        }
        return briefing

    def build_study_plan(self, session_id: str) -> dict[str, Any]:
        """Build a concrete study agenda with time blocks and checkpoints."""

        session = self._load_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        evaluation = self.evaluate_session(session_id)
        if not evaluation.get("success"):
            return evaluation
        effect_context = self._effect_context(session, evaluation=evaluation)
        effect_assessment = effect_context["effect_assessment"]
        learner_profile_context = effect_context.get("learner_profile_context", {})
        blocks = self._study_blocks(session)
        checkpoints = self._study_checkpoints(session, blocks)
        current_block = next(
            (block for block in blocks if block.get("status") in {"active", "pending"}),
            blocks[-1] if blocks else None,
        )
        next_checkpoint = next(
            (checkpoint for checkpoint in checkpoints if checkpoint.get("status") != "met"),
            checkpoints[-1] if checkpoints else None,
        )

        completed_tasks = int(evaluation.get("completed_tasks") or 0)
        total_tasks = int(evaluation.get("total_tasks") or len(session.tasks))
        remaining_minutes = sum(
            task.estimated_minutes
            for task in session.tasks
            if task.status not in {"completed", "skipped"}
        )
        summary = (
            f"建议按 {len(blocks)} 次学习推进：已完成 {completed_tasks}/{total_tasks} 个任务，"
            f"剩余约 {remaining_minutes} 分钟。"
        )
        if current_block:
            summary += f" 当前优先完成「{current_block.get('title')}」。"
        if effect_assessment.get("label"):
            summary += f" 学习效果评估为「{effect_assessment.get('label')}」，评分 {effect_assessment.get('score', 0)}。"
        rules = [
            "每个学习块必须留下反思或练习证据，系统才会调整后续路线。",
            "低于 0.75 的证据会触发补救任务或资源推送。",
            "完成练习、图解或视频后优先回到当前任务闭环，而不是无限生成资源。",
        ]
        for item in effect_assessment.get("strategy_adjustments") or []:
            if item and item not in rules:
                rules.append(str(item))

        return {
            "success": True,
            "session_id": session.session_id,
            "generated_at": time.time(),
            "summary": summary,
            "horizon": session.profile.horizon,
            "daily_time_budget": session.profile.time_budget_minutes,
            "remaining_minutes": remaining_minutes,
            "blocks": blocks,
            "checkpoints": checkpoints,
            "current_block": current_block,
            "next_checkpoint": next_checkpoint,
            "effect_assessment": effect_assessment,
            "learner_profile_context": learner_profile_context,
            "strategy_adjustments": effect_assessment.get("strategy_adjustments", []),
            "rules": rules[:5],
        }

    def build_diagnostic(self, session_id: str) -> dict[str, Any]:
        """Build a learner-facing diagnostic questionnaire for a session."""

        session = self._load_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        latest = self._latest_diagnostic_evidence(session)
        questions = self._diagnostic_questions(session)
        result = dict(latest.metadata or {}) if latest and latest.metadata else None
        return {
            "success": True,
            "session_id": session.session_id,
            "generated_at": time.time(),
            "status": "completed" if latest else "pending",
            "summary": (
                "用 2 分钟完成前测，系统会据此修正学习画像、薄弱点和第一轮任务顺序。"
                if latest is None
                else f"最近一次诊断分为 {round(float(latest.score or 0) * 100)}%，路径已根据结果更新。"
            ),
            "questions": questions,
            "last_result": result,
        }

    def submit_diagnostic(
        self,
        session_id: str,
        answers: list[dict[str, Any]],
    ) -> dict[str, Any]:
        session = self._load_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}
        if not answers:
            return {"success": False, "error": "Diagnostic answers cannot be empty"}

        diagnosis = self._score_diagnostic_answers(session, answers)
        current = self._current_task(session)
        evidence = LearningEvidence(
            evidence_id=uuid.uuid4().hex[:10],
            task_id=current.task_id if current else "_diagnostic",
            type="diagnostic",
            score=diagnosis["readiness_score"],
            reflection=diagnosis["reflection"],
            mistake_types=diagnosis["weak_points"],
            metadata={
                "readiness_label": diagnosis["readiness_label"],
                "weak_points": diagnosis["weak_points"],
                "current_bottleneck": diagnosis.get("current_bottleneck", ""),
                "bottleneck_label": diagnosis.get("bottleneck_label", ""),
                "learning_strategy": diagnosis.get("learning_strategy", []),
                "answers": answers,
                "recommendations": diagnosis["recommendations"],
            },
        )
        session.evidence.append(evidence)
        self._apply_diagnostic_profile(session, diagnosis)
        self._apply_diagnostic_mastery(session, diagnosis)
        adjustments = self._adapt_path_from_diagnostic(session, diagnosis, evidence)
        next_task = self._first_pending_task(session)
        session.learning_path.current_task_id = next_task.task_id if next_task else ""
        session.status = "learning" if next_task else "completed"
        session.recommendations = self._build_session_recommendations(session)
        session.updated_at = time.time()
        self._save_session(session)
        return {
            "success": True,
            "session_id": session.session_id,
            "diagnosis": diagnosis,
            "evidence": asdict(evidence),
            "adjustments": [asdict(item) for item in adjustments],
            "session": self.get_session(session_id),
        }

    def build_profile_dialogue(self, session_id: str) -> dict[str, Any]:
        """Return prompts and latest state for conversational profiling."""

        session = self._load_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        latest = self._latest_profile_dialogue_evidence(session)
        return {
            "success": True,
            "session_id": session.session_id,
            "generated_at": time.time(),
            "status": "updated" if latest else "ready",
            "summary": (
                "你可以直接告诉我：哪里不会、今天有多久、想先看图解还是先做题。"
                if latest is None
                else str((latest.metadata or {}).get("assistant_reply") or "学习画像已根据最近一次对话更新。")
            ),
            "suggested_prompts": self._profile_dialogue_prompts(session),
            "last_signals": dict(latest.metadata or {}) if latest else None,
        }

    def submit_profile_dialogue(
        self,
        session_id: str,
        message: str,
    ) -> dict[str, Any]:
        session = self._load_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}
        cleaned = " ".join(str(message or "").split()).strip()
        if not cleaned:
            return {"success": False, "error": "Message cannot be empty"}

        signals = self._extract_profile_dialogue_signals(session, cleaned)
        self._apply_profile_dialogue_signals(session, signals)
        evidence = LearningEvidence(
            evidence_id=uuid.uuid4().hex[:10],
            task_id=(self._current_task(session).task_id if self._current_task(session) else "_profile"),
            type="profile_dialogue",
            score=signals.get("readiness_score"),
            reflection=cleaned,
            mistake_types=[str(item) for item in signals.get("weak_points", [])],
            metadata={
                **signals,
                "message": cleaned,
                "assistant_reply": self._profile_dialogue_reply(session, signals),
            },
        )
        session.evidence.append(evidence)
        adjustments = self._adapt_path_from_profile_dialogue(session, signals, evidence)
        next_task = self._first_pending_task(session)
        session.learning_path.current_task_id = next_task.task_id if next_task else ""
        session.status = "learning" if next_task else session.status
        session.recommendations = self._build_session_recommendations(session)
        session.updated_at = time.time()
        self._save_session(session)
        return {
            "success": True,
            "session_id": session.session_id,
            "signals": signals,
            "assistant_reply": evidence.metadata["assistant_reply"],
            "evidence": asdict(evidence),
            "adjustments": [asdict(item) for item in adjustments],
            "session": self.get_session(session_id),
        }

    def recommend_resources(self, session_id: str) -> dict[str, Any]:
        """Recommend the next resources from learning evidence and mastery state.

        The recommendation engine is intentionally deterministic: it makes the
        learning loop explainable in demos and still works when the LLM provider
        is unavailable.
        """

        session = self._load_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        evaluation = self.evaluate_session(session_id)
        if not evaluation.get("success"):
            return evaluation

        target_task = (
            self._current_task(session)
            or self._first_pending_task(session)
            or (session.tasks[-1] if session.tasks else None)
        )
        if target_task is None:
            return {
                "success": True,
                "session_id": session.session_id,
                "generated_at": time.time(),
                "recommendations": [],
                "summary": "No learning tasks are available yet.",
            }

        task_by_id = {task.task_id: task for task in session.tasks}
        resource_counts = evaluation.get("resource_counts") or {}
        question_count = int(evaluation.get("question_count") or 0)
        progress = int(evaluation.get("progress") or 0)
        preferences = {str(item).strip().lower() for item in session.profile.preferences}
        prefers_external_video = GuideV2Manager._prefers_external_video(preferences)
        effect_context = self._effect_context(session, evaluation=evaluation)
        effect_assessment = effect_context["effect_assessment"]
        mistake_review = effect_context["mistake_review"]
        learner_profile_context = effect_context.get("learner_profile_context", {})
        effect_dimensions = {
            str(item.get("id") or ""): item
            for item in effect_assessment.get("dimensions") or []
            if isinstance(item, dict)
        }

        def dimension_score(name: str) -> int:
            return int(dict(effect_dimensions.get(name) or {}).get("score") or 0)

        effect_score = int(effect_assessment.get("score") or 0)
        effect_label = str(effect_assessment.get("label") or "")
        recommendations: dict[tuple[str, str], dict[str, Any]] = {}
        priority_rank = {"low": 1, "medium": 2, "high": 3}

        def add(
            *,
            resource_type: str,
            task: LearningTask | None,
            priority: str,
            title: str,
            reason: str,
            prompt: str,
        ) -> None:
            if task is None:
                return
            normalized_type = self._normalize_resource_type(resource_type)
            if not normalized_type:
                return
            key = (task.task_id, normalized_type)
            capability, _config = self._resource_capability(normalized_type, task, "low")
            item = {
                "id": f"{task.task_id}-{normalized_type}",
                "priority": priority if priority in priority_rank else "medium",
                "resource_type": normalized_type,
                "capability": capability,
                "title": title,
                "reason": reason,
                "prompt": prompt,
                "target_task_id": task.task_id,
                "target_task_title": task.title,
                "target_node_id": task.node_id,
                "effect_score": effect_score,
                "effect_label": effect_label,
            }
            existing = recommendations.get(key)
            if existing is None or priority_rank[item["priority"]] > priority_rank.get(str(existing.get("priority")), 0):
                recommendations[key] = item

        target_types = self._task_artifact_types(target_task)
        mistake_summary = dict(mistake_review.get("summary") or {})
        pending_remediations = [
            item
            for item in mistake_review.get("remediation_tasks", []) or []
            if isinstance(item, dict) and item.get("status") not in {"completed", "skipped"}
        ]
        pending_retests = [
            item
            for item in mistake_review.get("retest_tasks", []) or []
            if isinstance(item, dict) and item.get("status") not in {"completed", "skipped"}
        ]
        if pending_remediations and dimension_score("remediation") < 75:
            remediation_task = task_by_id.get(str(pending_remediations[0].get("task_id") or ""), target_task)
            add(
                resource_type="visual",
                task=remediation_task,
                priority="high",
                title="先生成错因补救图解",
                reason="学习效果评估显示错因闭环不足，优先把薄弱点、错误表现和修正步骤讲清楚。",
                prompt="生成一张补救图解：错因表现、根本原因、正确判断条件、反例辨析、三步修正路径，并给一个最小练习。",
            )
        if pending_retests and dimension_score("remediation") < 85:
            retest_task = task_by_id.get(str(pending_retests[0].get("task_id") or ""), target_task)
            add(
                resource_type="quiz",
                task=retest_task,
                priority="high",
                title="立刻生成错因复测题",
                reason="补救后需要用可评分复测确认闭环，避免看懂了但不会稳定迁移。",
                prompt="生成 4 道错因复测题，覆盖选择、判断、填空和简答；每题标注考察点、答案、解析和通过标准。",
            )
        if dimension_score("evidence") < 50:
            add(
                resource_type="quiz",
                task=target_task,
                priority="high",
                title="补齐学习证据小测",
                reason="学习效果评估显示证据质量不足，需要先产生可评分练习结果，再判断是否继续推进。",
                prompt="围绕当前任务生成一组短小但可评分的混合题，题型包含选择、判断、填空和简答，并输出错因标签。",
            )
        if dimension_score("engagement") < 50 and resource_counts.get("visual", 0) == 0:
            add(
                resource_type="visual",
                task=target_task,
                priority="high",
                title="生成上手图解",
                reason="学习参与度偏低，先用一张少文字、强结构的图解帮助进入当前任务。",
                prompt="生成一张极简上手图解：本任务要解决什么、关键概念如何连接、先做哪一步、常见误区是什么。",
            )

        if question_count == 0 or "quiz" not in target_types:
            add(
                resource_type="quiz",
                task=target_task,
                priority="high",
                title="生成一次混合题小测",
                reason="当前学习路径还缺少可量化的练习证据，需要用选择题、判断题、填空题和简答题建立测评闭环。",
                prompt=(
                    "围绕当前任务生成 4 道交互式混合题，覆盖概念判断、关键步骤、常见误区和一个迁移应用。"
                    "每题给出答案、解析和错误原因提示。"
                ),
            )

        weak_nodes = sorted(
            [
                item
                for item in evaluation.get("node_evaluations", [])
                if isinstance(item, dict)
                and (
                    str(item.get("status") or "") == "needs_support"
                    or float(item.get("mastery_score") or 0) < 0.45
                )
            ],
            key=lambda item: float(item.get("mastery_score") or 0),
        )
        if weak_nodes:
            weak = weak_nodes[0]
            weak_task = self._task_for_node(session, str(weak.get("node_id") or "")) or target_task
            add(
                resource_type="visual",
                task=weak_task,
                priority="high",
                title=f"补一张{weak.get('title') or '薄弱知识点'}图解",
                reason="该知识点掌握度偏低，先用图解建立直觉，再回到练习会更稳。",
                prompt="用一张结构清晰的图解释薄弱点：核心概念、前置条件、推理步骤、常见误区和一个最小例子。",
            )
            add(
                resource_type="quiz",
                task=weak_task,
                priority="medium",
                title="针对薄弱点再测一次",
                reason="薄弱知识点需要通过错因可见的练习来确认是否真正补上。",
                prompt="围绕薄弱知识点生成 4 道由易到难的混合题，重点暴露常见误区。",
            )

        scored_evidence = [
            item for item in session.evidence
            if item.score is not None and float(item.score) < 0.75
        ]
        if scored_evidence:
            weakest_evidence = min(scored_evidence, key=lambda item: float(item.score or 0))
            evidence_task = task_by_id.get(weakest_evidence.task_id, target_task)
            add(
                resource_type="visual",
                task=evidence_task,
                priority="medium",
                title="把低分任务重新讲清楚",
                reason="最近学习证据分数偏低，适合先回看推理链路，再做一次复测。",
                prompt=(
                    f"针对这次反思「{weakest_evidence.reflection or '暂无反思'}」重新讲解任务，"
                    "突出错因、关键判断和一步步纠正方式。"
                ),
            )

        if resource_counts.get("visual", 0) == 0 and progress < 100:
            add(
                resource_type="visual",
                task=target_task,
                priority="medium",
                title="先生成当前任务图解",
                reason="当前路径还没有图解资源，先把概念关系可视化能降低后续练习难度。",
                prompt="生成适合课堂投影的简洁图解：目标、关键概念、关系箭头、例子和注意事项。",
            )

        if prefers_external_video and resource_counts.get("external_video", 0) == 0:
            add(
                resource_type="external_video",
                task=target_task,
                priority="medium",
                title="找一组公开视频补充视角",
                reason="学习画像显示你会使用公开视频辅助理解，先筛选少量高相关讲解，再回到当前任务提交反馈。",
                prompt="检索适合当前任务的公开视频或公开课片段，只保留 2-3 个高相关链接，并说明每个视频解决哪个卡点。",
            )

        if ("video" in preferences or "animation" in preferences) and resource_counts.get("video", 0) == 0:
            add(
                resource_type="video",
                task=target_task,
                priority="medium",
                title="生成一个短视频讲解",
                reason="学习画像偏好动态解释，短视频适合讲清公式变化、过程流转或几何直觉。",
                prompt="制作 60 秒以内的分步讲解动画，公式逐步出现，画面留白充分，最后给一个小结。",
            )

        if resource_counts.get("research", 0) == 0 and progress >= 20:
            add(
                resource_type="research",
                task=target_task,
                priority="low",
                title="补充一组拓展资料",
                reason="已有初步学习证据后，可以补充高质量资料用于复习和迁移。",
                prompt="推荐 3-5 条适合当前水平的资料，并说明每条资料用于解决哪个学习问题。",
            )
        if effect_score >= 80 and progress >= 50:
            add(
                resource_type="quiz",
                task=target_task,
                priority="medium",
                title="生成迁移应用挑战",
                reason="学习效果评估已稳定，可以用新场景题检验是否真正能迁移。",
                prompt="生成 2 道迁移应用题，要求把当前知识用于新情境，并给出评分标准、参考解和常见误区。",
            )

        ordered = sorted(
            recommendations.values(),
            key=lambda item: (-priority_rank.get(str(item.get("priority")), 0), str(item.get("target_task_id")), str(item.get("resource_type"))),
        )[:4]
        summary = (
            f"资源推荐已结合学习效果评估「{effect_label or '待评估'}」"
            f"（{effect_score} 分）、错因闭环、资源缺口和学习画像生成。"
        )
        return {
            "success": True,
            "session_id": session.session_id,
            "generated_at": time.time(),
            "summary": summary,
            "effect_assessment": effect_assessment,
            "learner_profile_context": learner_profile_context,
            "recommendations": ordered,
        }

    def build_learning_report(self, session_id: str) -> dict[str, Any]:
        """Build a course-level learning report for demos and learner review."""

        session = self._load_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        evaluation = self.evaluate_session(session_id)
        if not evaluation.get("success"):
            return evaluation

        latest_reflection = ""
        if session.evidence:
            latest = max(session.evidence, key=lambda item: item.created_at)
            latest_reflection = latest.reflection

        overview = {
            "overall_score": evaluation.get("overall_score", 0),
            "readiness": evaluation.get("readiness", "not_started"),
            "progress": evaluation.get("progress", 0),
            "completed_tasks": evaluation.get("completed_tasks", 0),
            "skipped_tasks": evaluation.get("skipped_tasks", 0),
            "total_tasks": evaluation.get("total_tasks", 0),
            "path_adjustment_count": evaluation.get("path_adjustment_count", 0),
            "average_evidence_score": evaluation.get("average_evidence_score", 0.0),
            "average_mastery": evaluation.get("average_mastery", 0.0),
        }
        evidence_summary = {
            "count": len(session.evidence),
            "trend": evaluation.get("evidence_trend", []),
            "latest_reflection": latest_reflection,
        }
        timeline_events = self._learning_timeline_events(session)
        behavior_summary = self._learning_timeline_summary(session, timeline_events)
        behavior_tags = self._learning_behavior_tags(session, behavior_summary)
        feedback_digest = self._feedback_digest(timeline_events)
        mistake_review = self.build_mistake_review(session_id)
        mistake_payload = (
            {
                "summary": mistake_review.get("summary", {}),
                "clusters": list(mistake_review.get("clusters") or [])[:5],
                "retest_plan": list(mistake_review.get("retest_plan") or [])[:3],
            }
            if mistake_review.get("success")
            else {"summary": {}, "clusters": [], "retest_plan": []}
        )
        effect_assessment = self._effect_assessment(
            evaluation=evaluation,
            behavior_summary=behavior_summary,
            mistake_payload=mistake_payload,
            feedback_digest=feedback_digest,
            profile_context=evaluation.get("learner_profile_context"),
        )
        node_cards = self._report_node_cards(session)
        action_brief = self._report_action_brief(
            session=session,
            evaluation=evaluation,
            overview=overview,
            effect_assessment=effect_assessment,
            feedback_digest=feedback_digest,
            mistake_payload=mistake_payload,
            node_cards=node_cards,
        )
        demo_readiness = self._report_demo_readiness(
            session=session,
            evaluation=evaluation,
            overview=overview,
            behavior_summary=behavior_summary,
            resource_summary=evaluation.get("resource_counts", {}),
            feedback_digest=feedback_digest,
            action_brief=action_brief,
        )
        report: dict[str, Any] = {
            "success": True,
            "session_id": session.session_id,
            "generated_at": time.time(),
            "title": f"{session.goal} 学习效果报告",
            "summary": self._report_summary(session, evaluation),
            "overview": overview,
            "profile": asdict(session.profile),
            "node_cards": node_cards,
            "resource_summary": evaluation.get("resource_counts", {}),
            "evidence_summary": evidence_summary,
            "behavior_summary": behavior_summary,
            "behavior_tags": behavior_tags,
            "feedback_digest": feedback_digest,
            "effect_assessment": effect_assessment,
            "action_brief": action_brief,
            "demo_readiness": demo_readiness,
            "learner_profile_context": evaluation.get("learner_profile_context", {}),
            "timeline_events": sorted(
                timeline_events,
                key=lambda item: float(item.get("created_at") or 0),
                reverse=True,
            )[:8],
            "mistake_review": mistake_payload,
            "interventions": [asdict(item) for item in session.plan_events[-8:]],
            "risks": evaluation.get("risk_signals", []),
            "strengths": evaluation.get("strengths", []),
            "next_plan": evaluation.get("next_actions", []),
            "demo_script": self._report_demo_script(session, evaluation),
        }
        report["markdown"] = self._report_markdown(report)
        return report

    def build_course_package(self, session_id: str) -> dict[str, Any]:
        """Build a final course package with capstone, rubric, and portfolio."""

        session = self._load_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        evaluation = self.evaluate_session(session_id)
        if not evaluation.get("success"):
            return evaluation
        report = self.build_learning_report(session_id)
        node_cards = list(report.get("node_cards") or []) if report.get("success") else []
        portfolio = self._course_portfolio(session)
        learning_style = self._course_learning_style(
            session=session,
            evaluation=evaluation,
            report=report if report.get("success") else {},
        )
        demo_blueprint = self._course_demo_blueprint(
            session=session,
            evaluation=evaluation,
            report=report if report.get("success") else {},
            portfolio=portfolio,
            learning_style=learning_style,
        )
        demo_fallback_kit = self._course_demo_fallback_kit(
            session=session,
            evaluation=evaluation,
            report=report if report.get("success") else {},
            portfolio=portfolio,
        )
        demo_seed_pack = self._course_demo_seed_pack(
            session=session,
            evaluation=evaluation,
            report=report if report.get("success") else {},
        )
        package: dict[str, Any] = {
            "success": True,
            "session_id": session.session_id,
            "generated_at": time.time(),
            "title": f"{session.course_map.title or session.goal} 课程产出包",
            "summary": self._course_package_summary(session, evaluation),
            "course_metadata": session.course_map.metadata,
            "capstone_project": self._capstone_project(session, evaluation),
            "rubric": self._course_rubric(session, evaluation),
            "portfolio": portfolio,
            "review_plan": self._course_review_plan(node_cards),
            "learning_style": learning_style,
            "demo_outline": self._course_demo_outline(session, evaluation),
            "demo_blueprint": demo_blueprint,
            "demo_fallback_kit": demo_fallback_kit,
            "demo_seed_pack": demo_seed_pack,
            "learning_report": {
                "overall_score": evaluation.get("overall_score", 0),
                "readiness": evaluation.get("readiness", "not_started"),
                "progress": evaluation.get("progress", 0),
                "behavior_summary": report.get("behavior_summary", {}),
                "behavior_tags": report.get("behavior_tags", []),
                "feedback_digest": report.get("feedback_digest", {}),
                "effect_assessment": report.get("effect_assessment", {}),
                "demo_readiness": report.get("demo_readiness", {}),
                "recent_timeline_events": report.get("timeline_events", [])[:5],
                "mistake_summary": (report.get("mistake_review") or {}).get("summary", {}),
                "mistake_clusters": (report.get("mistake_review") or {}).get("clusters", [])[:3],
                "risks": evaluation.get("risk_signals", []),
                "next_actions": evaluation.get("next_actions", []),
            },
        }
        package["markdown"] = self._course_package_markdown(package)
        return package

    async def generate_resource(
        self,
        session_id: str,
        task_id: str,
        *,
        resource_type: str,
        prompt: str = "",
        quality: str = "low",
        event_sink: GuideResourceEventSink | None = None,
    ) -> dict[str, Any]:
        session = self._load_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}
        task = next((item for item in session.tasks if item.task_id == task_id), None)
        if task is None:
            return {"success": False, "error": "Task not found"}

        normalized_type = self._normalize_resource_type(resource_type)
        if not normalized_type:
            return {"success": False, "error": f"Unsupported resource type: {resource_type}"}
        capability, config = self._resource_capability(normalized_type, task, quality)
        if event_sink:
            event_sink(
                "status",
                {
                    "stage": "preparing",
                    "message": f"Preparing {capability} for {normalized_type}.",
                    "session_id": session_id,
                    "learning_task_id": task_id,
                    "resource_type": normalized_type,
                    "capability": capability,
                },
            )
        node = next((item for item in session.course_map.nodes if item.node_id == task.node_id), None)
        learner_profile_hints = self._resource_profile_hints(session, task, node)
        try:
            if normalized_type == "external_video":
                result = await recommend_learning_videos(
                    topic=task.title,
                    learner_hints=learner_profile_hints,
                    prompt=prompt,
                    language="zh",
                    max_results=3,
                    event_sink=event_sink,
                )
            else:
                context = self._build_resource_context(
                    session=session,
                    task=task,
                    node=node,
                    resource_type=normalized_type,
                    prompt=prompt,
                    capability=capability,
                    config=config,
                )
                if event_sink and self.capability_runner is _run_langgraph_capability:
                    result = await _run_langgraph_capability(capability, context, event_sink=event_sink)
                else:
                    result = await self.capability_runner(capability, context)
        except Exception as exc:
            self.logger.warning(
                "Guide v2 resource generation failed: session=%s task=%s type=%s error=%s",
                session_id,
                task_id,
                normalized_type,
                exc,
            )
            return {"success": False, "error": str(exc)}
        if event_sink:
            event_sink(
                "status",
                {
                    "stage": "saving",
                    "message": "Saving generated resource to the guide task.",
                    "session_id": session_id,
                    "learning_task_id": task_id,
                    "resource_type": normalized_type,
                    "capability": capability,
                },
            )

        artifact = {
            "id": uuid.uuid4().hex[:10],
            "type": normalized_type,
            "capability": capability,
            "title": self._resource_title(normalized_type, task),
            "created_at": time.time(),
            "status": "ready",
            "config": config,
            "personalization": learner_profile_hints,
            "result": result,
        }
        task.artifact_refs.append(artifact)
        session.status = "learning"
        session.recommendations = self._build_session_recommendations(session)
        session.updated_at = time.time()
        self._save_session(session)
        return {
            "success": True,
            "artifact": artifact,
            "task": asdict(task),
            "session": self.get_session(session_id),
        }

    def submit_quiz_attempt(
        self,
        session_id: str,
        task_id: str,
        artifact_id: str,
        *,
        answers: list[dict[str, Any]],
    ) -> dict[str, Any]:
        session = self._load_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}
        task = next((item for item in session.tasks if item.task_id == task_id), None)
        if task is None:
            return {"success": False, "error": "Task not found"}
        artifact = next(
            (item for item in task.artifact_refs if str(item.get("id") or "") == artifact_id),
            None,
        )
        if artifact is None:
            return {"success": False, "error": "Artifact not found"}
        if str(artifact.get("type") or "") != "quiz":
            return {"success": False, "error": "Artifact is not a quiz"}

        normalized_answers = self._normalize_quiz_answers(answers)
        if not normalized_answers:
            return {"success": False, "error": "Quiz answers are required"}

        total = len(normalized_answers)
        correct = sum(1 for item in normalized_answers if bool(item.get("is_correct")))
        score = round(correct / total, 3) if total else 0.0
        wrong_items = [item for item in normalized_answers if not bool(item.get("is_correct"))]
        mistake_types = self._quiz_mistake_types(wrong_items)
        concept_labels = self._quiz_concept_labels(normalized_answers)
        concept_feedback = self._quiz_concept_feedback(normalized_answers, fallback_concept=task.title)
        attempt = {
            "attempt_id": uuid.uuid4().hex[:10],
            "created_at": time.time(),
            "score": score,
            "correct_count": correct,
            "total_count": total,
            "answers": normalized_answers,
            "concepts": concept_labels,
            "concept_feedback": concept_feedback,
        }
        attempts = artifact.setdefault("quiz_attempts", [])
        if isinstance(attempts, list):
            attempts.append(attempt)
        else:
            artifact["quiz_attempts"] = [attempt]

        task.status = "completed"
        evidence = LearningEvidence(
            evidence_id=uuid.uuid4().hex[:10],
            task_id=task_id,
            type="quiz",
            score=score,
            reflection=self._quiz_attempt_reflection(task, attempt),
            mistake_types=mistake_types,
            metadata={
                "quiz_attempt_id": attempt["attempt_id"],
                "question_count": total,
                "correct_count": correct,
                "wrong_count": len(wrong_items),
                "concepts": concept_labels,
                "concept_feedback": concept_feedback,
            },
        )
        evidence.metadata["evidence_quality"] = self._evidence_quality_profile(task, evidence)
        session.evidence.append(evidence)
        self._update_mastery(session, task, evidence)
        self._update_profile_from_evidence(session, task, evidence)
        adjustments = self._adapt_learning_path(session, task, evidence)
        next_task = self._first_pending_task(session)
        session.learning_path.current_task_id = next_task.task_id if next_task else ""
        session.status = "completed" if next_task is None else "learning"
        session.recommendations = self._build_session_recommendations(session)
        feedback = self._learning_feedback(session, task, evidence, adjustments, next_task)
        evidence.metadata["learning_feedback"] = feedback
        session.updated_at = time.time()
        self._save_session(session)
        return {
            "success": True,
            "session_id": session.session_id,
            "task_id": task_id,
            "artifact_id": artifact_id,
            "attempt": attempt,
            "evidence": asdict(evidence),
            "adjustments": [asdict(item) for item in adjustments],
            "next_task": asdict(next_task) if next_task else None,
            "learning_feedback": feedback,
            "session": self.get_session(session_id),
        }

    def delete_session(self, session_id: str) -> dict[str, Any]:
        self._sessions.pop(session_id, None)
        path = self._session_path(session_id)
        if path.exists():
            path.unlink()
            self._refresh_learner_memory()
            return {"success": True, "session_id": session_id}
        return {"success": False, "error": "Session not found"}

    def _build_resource_context(
        self,
        *,
        session: GuideSessionV2,
        task: LearningTask,
        node: CourseNode | None,
        resource_type: str,
        prompt: str,
        capability: str,
        config: dict[str, Any],
    ) -> Any:
        from sparkweave.core.contracts import UnifiedContext

        learner_profile_hints = self._resource_profile_hints(session, task, node)
        user_message = self._resource_prompt(
            session=session,
            task=task,
            node=node,
            resource_type=resource_type,
            prompt=prompt,
        )
        return UnifiedContext(
            session_id=f"guide-v2-{session.session_id}",
            user_message=user_message,
            active_capability=capability,
            config_overrides=config,
            language="zh",
            notebook_context=session.notebook_context,
            metadata={
                "guide_session_id": session.session_id,
                "guide_task_id": task.task_id,
                "guide_node_id": task.node_id,
                "guide_resource_type": resource_type,
                "learner_profile_hints": learner_profile_hints,
            },
        )

    @staticmethod
    def _prefers_external_video(preferences: set[str] | list[str] | tuple[str, ...]) -> bool:
        items = {str(item).strip().lower() for item in preferences if str(item).strip()}
        return "external_video" in items or any(
            token in item
            for item in items
            for token in ("公开视频", "精选视频", "公开课", "网课", "bilibili", "youtube")
        )

    @staticmethod
    def _normalize_resource_type(value: str) -> str:
        raw = (value or "").strip().lower()
        aliases = {
            "visual": "visual",
            "diagram": "visual",
            "visualize": "visual",
            "visualization": "visual",
            "图解": "visual",
            "video": "video",
            "animation": "video",
            "math_animator": "video",
            "短视频": "video",
            "动画": "video",
            "external_video": "external_video",
            "curated_video": "external_video",
            "web_video": "external_video",
            "online_video": "external_video",
            "selected_video": "external_video",
            "精选视频": "external_video",
            "网络视频": "external_video",
            "公开视频": "external_video",
            "quiz": "quiz",
            "practice": "quiz",
            "question": "quiz",
            "questions": "quiz",
            "练习": "quiz",
            "题目": "quiz",
            "research": "research",
            "resource": "research",
            "materials": "research",
            "reading": "research",
            "资料": "research",
        }
        return aliases.get(raw, "")

    @staticmethod
    def _resource_capability(
        resource_type: str,
        task: LearningTask,
        quality: str,
    ) -> tuple[str, dict[str, Any]]:
        if resource_type == "visual":
            return "visualize", {"render_mode": "svg"}
        if resource_type == "video":
            safe_quality = quality if quality in {"low", "medium", "high"} else "low"
            return (
                "math_animator",
                {
                    "output_mode": "video",
                    "quality": safe_quality,
                    "max_retries": 2,
                    "style_hint": "简洁课堂板书风格，公式分步出现，避免拥挤排版。",
                },
            )
        if resource_type == "external_video":
            return (
                "external_video_search",
                {
                    "mode": "curated_links",
                    "sources": ["web", "bilibili", "youtube"],
                    "max_results": 3,
                },
            )
        if resource_type == "quiz":
            return (
                "deep_question",
                {
                    "mode": "custom",
                    "topic": task.title,
                    "num_questions": 4,
                    "difficulty": "medium",
                    "question_type": "mixed",
                    "preference": "包含选择题、判断题、填空题和简答题，答案解析要能指出常见误区。",
                    "response_schema_hint": "Each question must include concepts: string[] and knowledge_points: string[] so learner profile mastery can be updated by concept.",
                },
            )
        return (
            "deep_research",
            {
                "mode": "learning_path",
                "depth": "quick",
                "sources": ["kb", "web"],
                "use_code": False,
            },
        )

    @staticmethod
    def _resource_title(resource_type: str, task: LearningTask) -> str:
        labels = {
            "visual": "概念图解",
            "video": "短视频讲解",
            "external_video": "精选视频",
            "quiz": "交互练习",
            "research": "拓展资料",
        }
        return f"{labels.get(resource_type, '学习资源')}：{task.title}"

    @staticmethod
    def _resource_prompt(
        *,
        session: GuideSessionV2,
        task: LearningTask,
        node: CourseNode | None,
        resource_type: str,
        prompt: str,
    ) -> str:
        resource_goals = {
            "visual": "生成一张可直接用于学习的知识图解，突出概念关系、步骤和关键公式。",
            "video": "生成一段适合学生观看的短视频讲解脚本和 Manim 动画，分步解释，不要堆砌文字。",
            "external_video": "从公开网络中筛选适合当前任务的学习视频，只推荐少量高相关、入门友好的视频链接。",
            "quiz": "生成一组可交互练习题，题型要混合，包含答案、解析、难度和考察点。",
            "research": "整理适合当前任务的学习资料和下一步阅读建议，优先结合知识库上下文。",
        }
        node_text = (
            f"知识点：{node.title}\n说明：{node.description}\n掌握目标：{node.mastery_target}"
            if node
            else "知识点：未指定"
        )
        memory_payload = task.metadata.get("learner_memory") if isinstance(task.metadata.get("learner_memory"), dict) else {}
        memory_text = ""
        if memory_payload:
            hints: list[str] = []
            if memory_payload.get("preferred_resources"):
                hints.append(f"历史偏好资源：{', '.join(map(str, memory_payload.get('preferred_resources') or []))}")
            if memory_payload.get("known_weak_points"):
                hints.append(f"长期薄弱点：{', '.join(map(str, memory_payload.get('known_weak_points') or []))}")
            if memory_payload.get("common_mistakes"):
                hints.append(f"常见错因：{', '.join(map(str, memory_payload.get('common_mistakes') or []))}")
            if hints:
                memory_text = "长期学习画像提示：请显式照顾这些历史信号，避免重复踩坑；" + "；".join(hints) + "\n"
        extra = f"\n用户补充要求：{prompt.strip()}" if prompt.strip() else ""
        return (
            f"你是 SparkWeave 星火织学的导学智能体，正在为一个具体学习任务生成资源。\n"
            f"学习总目标：{session.goal}\n"
            f"{node_text}\n"
            f"{memory_text}"
            f"{GuideV2Manager._resource_profile_prompt(session, task, node, resource_type)}"
            f"当前任务：{task.title}\n"
            f"任务说明：{task.instruction}\n"
            f"成功标准：{'; '.join(task.success_criteria) if task.success_criteria else '完成后能解释关键思想并做一次自测'}\n"
            f"资源目标：{resource_goals.get(resource_type, '生成实用学习资源')}\n"
            f"请面向高校学生，表达清楚、可执行、不要空泛。{extra}"
        )

    @staticmethod
    def _resource_profile_hints(
        session: GuideSessionV2,
        task: LearningTask,
        node: CourseNode | None,
    ) -> dict[str, Any]:
        profile = session.profile
        mastery = session.mastery.get(task.node_id)
        task_memory = task.metadata.get("learner_memory") if isinstance(task.metadata.get("learner_memory"), dict) else {}
        preferred_from_task = (
            task.metadata.get("preferred_resource_types")
            if isinstance(task.metadata.get("preferred_resource_types"), list)
            else []
        )
        avoid_mistakes = task.metadata.get("avoid_mistakes") if isinstance(task.metadata.get("avoid_mistakes"), list) else []
        hints = {
            "level": profile.level,
            "time_budget_minutes": profile.time_budget_minutes,
            "preferences": GuideV2Manager._dedupe_strings(
                [str(item) for item in list(profile.preferences or []) + list(preferred_from_task or [])]
            )[:6],
            "weak_points": GuideV2Manager._dedupe_strings([str(item) for item in profile.weak_points or []])[:6],
            "avoid_mistakes": GuideV2Manager._dedupe_strings(
                [str(item) for item in list(avoid_mistakes or []) + list(task_memory.get("common_mistakes") or [])]
            )[:6],
            "node_title": node.title if node else "",
            "mastery_status": mastery.status if mastery else "",
            "mastery_score": mastery.score if mastery else None,
            "profile_context": profile.source_context_summary,
        }
        return {key: value for key, value in hints.items() if value not in ("", None, [], {})}

    @staticmethod
    def _resource_profile_prompt(
        session: GuideSessionV2,
        task: LearningTask,
        node: CourseNode | None,
        resource_type: str,
    ) -> str:
        hints = GuideV2Manager._resource_profile_hints(session, task, node)
        if not hints:
            return ""
        lines = ["Learner personalization:"]
        if hints.get("level"):
            lines.append(f"- level: {hints['level']}")
        if hints.get("time_budget_minutes"):
            lines.append(f"- time budget: {hints['time_budget_minutes']} minutes")
        if hints.get("preferences"):
            lines.append(f"- resource preferences: {', '.join(map(str, hints['preferences']))}")
        if hints.get("weak_points"):
            lines.append(f"- weak points to address: {', '.join(map(str, hints['weak_points']))}")
        if hints.get("avoid_mistakes"):
            lines.append(f"- common mistakes to prevent: {', '.join(map(str, hints['avoid_mistakes']))}")
        if hints.get("mastery_status"):
            lines.append(f"- current mastery: {hints['mastery_status']} ({hints.get('mastery_score', 'unknown')})")
        if hints.get("profile_context"):
            lines.append(f"- profile context: {str(hints['profile_context'])[:240]}")

        guidance = {
            "visual": "Make the diagram resolve the listed weak points first; prefer comparison, flow, formula meaning, and one small example over dense text.",
            "video": "Write a short step-by-step script and Manim plan; keep formulas LaTeX-safe, introduce symbols before using them, and avoid oversized formula blocks.",
            "quiz": "Generate mixed interactive questions: choice, true/false, fill-in, and short-answer when appropriate; each question must include concepts:string[] and knowledge_points:string[] plus answers, explanations, difficulty, and tested concept.",
            "research": "Keep resources practical and sequenced; recommend only materials directly useful for the current task.",
        }
        lines.append(f"- generation rule: {guidance.get(resource_type, 'Adapt the resource to the learner profile and current task.')}")
        return "\n".join(lines) + "\n"

    def _session_path(self, session_id: str) -> Path:
        safe_id = re.sub(r"[^A-Za-z0-9_-]", "", session_id)
        return self.output_dir / f"session_{safe_id}.json"

    def _save_session(self, session: GuideSessionV2) -> None:
        self._sessions[session.session_id] = session
        self._session_path(session.session_id).write_text(
            json.dumps(session.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._refresh_learner_memory()

    def _load_session(self, session_id: str) -> GuideSessionV2 | None:
        if session_id in self._sessions:
            return self._sessions[session_id]
        path = self._session_path(session_id)
        if not path.exists():
            return None
        try:
            session = GuideSessionV2.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:
            self.logger.warning("Failed to load guide v2 session %s: %s", session_id, exc)
            return None
        self._sessions[session.session_id] = session
        return session

    def _memory_path(self) -> Path:
        return self.output_dir / "learner_memory.json"

    def _load_learner_memory(self) -> dict[str, Any]:
        path = self._memory_path()
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.logger.warning("Failed to load guide v2 learner memory: %s", exc)
            return {}
        return payload if isinstance(payload, dict) else {}

    def _refresh_learner_memory(self) -> dict[str, Any]:
        memory = self._aggregate_learner_memory(self._all_sessions_for_memory())
        self._memory_path().write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")
        return memory

    def _all_sessions_for_memory(self) -> list[GuideSessionV2]:
        sessions: dict[str, GuideSessionV2] = dict(self._sessions)
        for path in self.output_dir.glob("session_*.json"):
            try:
                session = GuideSessionV2.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
            if session.session_id:
                sessions[session.session_id] = session
        return list(sessions.values())

    def _aggregate_learner_memory(self, sessions: list[GuideSessionV2]) -> dict[str, Any]:
        preference_counts: dict[str, int] = {}
        weak_counts: dict[str, int] = {}
        mistake_counts: dict[str, int] = {}
        strength_counts: dict[str, int] = {}
        level_counts: dict[str, int] = {}
        time_budgets: list[int] = []
        resource_counts: dict[str, int] = {}
        recent_goals: list[dict[str, Any]] = []
        evidence_count = 0
        scored_count = 0
        score_total = 0.0
        low_score_count = 0
        quiz_attempt_count = 0
        completed_sessions = 0
        last_activity_at = 0.0

        def add_count(counter: dict[str, int], value: str, amount: int = 1) -> None:
            cleaned = " ".join(str(value or "").split()).strip()
            if not cleaned:
                return
            counter[cleaned] = counter.get(cleaned, 0) + amount

        def ranked(counter: dict[str, int], limit: int = 8) -> list[dict[str, Any]]:
            return [
                {"label": label, "count": count}
                for label, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]
            ]

        for session in sessions:
            if not session.session_id:
                continue
            last_activity_at = max(last_activity_at, float(session.updated_at or session.created_at or 0))
            if session.status == "completed":
                completed_sessions += 1
            recent_goals.append(
                {
                    "session_id": session.session_id,
                    "goal": session.goal,
                    "status": session.status,
                    "updated_at": session.updated_at,
                    "progress": self._progress(session),
                }
            )
            for pref in session.profile.preferences:
                add_count(preference_counts, pref)
            for weak in session.profile.weak_points:
                add_count(weak_counts, weak)
            if session.profile.level:
                add_count(level_counts, session.profile.level)
            if session.profile.time_budget_minutes:
                time_budgets.append(int(session.profile.time_budget_minutes))

            task_by_id = {task.task_id: task for task in session.tasks}
            node_by_id = {node.node_id: node for node in session.course_map.nodes}
            for task in session.tasks:
                for artifact in task.artifact_refs:
                    artifact_type = str(artifact.get("type") or "resource")
                    resource_counts[artifact_type] = resource_counts.get(artifact_type, 0) + 1
                    attempts = artifact.get("quiz_attempts") if isinstance(artifact.get("quiz_attempts"), list) else []
                    quiz_attempt_count += len(attempts)

            for evidence in session.evidence:
                evidence_count += 1
                if evidence.score is not None:
                    scored_count += 1
                    score = float(evidence.score)
                    score_total += score
                    if score < 0.65:
                        low_score_count += 1
                        task = task_by_id.get(evidence.task_id)
                        node = node_by_id.get(task.node_id) if task else None
                        add_count(weak_counts, node.title if node else (task.title if task else evidence.task_id))
                    elif score >= 0.85:
                        task = task_by_id.get(evidence.task_id)
                        node = node_by_id.get(task.node_id) if task else None
                        add_count(strength_counts, node.title if node else (task.title if task else evidence.task_id))
                for mistake in evidence.mistake_types:
                    add_count(mistake_counts, mistake)
                    add_count(weak_counts, mistake)

            for node_id, mastery in session.mastery.items():
                node = node_by_id.get(node_id)
                label = node.title if node else node_id
                if mastery.status == "mastered" or mastery.score >= 0.8:
                    add_count(strength_counts, label)
                elif mastery.status == "needs_support" or mastery.score < 0.45 and mastery.evidence_count:
                    add_count(weak_counts, label)

        average_score = round(score_total / scored_count, 3) if scored_count else None
        preferred_time_budget = round(sum(time_budgets) / len(time_budgets)) if time_budgets else 30
        suggested_level = sorted(level_counts.items(), key=lambda item: (-item[1], item[0]))[0][0] if level_counts else "unknown"
        if average_score is not None:
            if average_score >= 0.85:
                suggested_level = "intermediate" if suggested_level in {"", "unknown", "beginner"} else suggested_level
            elif average_score < 0.55:
                suggested_level = "beginner"

        top_preferences = ranked(preference_counts, 6)
        persistent_weak_points = ranked(weak_counts, 8)
        common_mistakes = ranked(mistake_counts, 8)
        strengths = ranked(strength_counts, 8)
        recent_goals.sort(key=lambda item: float(item.get("updated_at") or 0), reverse=True)
        confidence = min(1.0, round((evidence_count + len(sessions)) / 10, 2))
        guidance: list[str] = []
        if persistent_weak_points:
            guidance.append(f"新路线优先照顾长期薄弱点：{persistent_weak_points[0]['label']}。")
        if common_mistakes:
            guidance.append(f"资源与练习需要显式暴露常见错因：{common_mistakes[0]['label']}。")
        if top_preferences:
            guidance.append(f"默认资源形式优先采用：{top_preferences[0]['label']}。")
        if average_score is not None and average_score < 0.7:
            guidance.append("先用可评分练习建立证据，再推进高难度迁移。")
        elif average_score is not None and average_score >= 0.85:
            guidance.append("可适当增加迁移应用和项目型产出。")
        if not guidance:
            guidance.append("先完成第一项任务，系统会逐步沉淀长期画像。")

        summary = (
            f"已沉淀 {len(sessions)} 条导学路线、{evidence_count} 条学习证据"
            f"{f'，平均得分 {round(average_score * 100)}%' if average_score is not None else ''}。"
        )
        return {
            "success": True,
            "memory_version": 1,
            "generated_at": time.time(),
            "session_count": len(sessions),
            "completed_session_count": completed_sessions,
            "evidence_count": evidence_count,
            "scored_evidence_count": scored_count,
            "average_score": average_score,
            "low_score_count": low_score_count,
            "quiz_attempt_count": quiz_attempt_count,
            "resource_counts": resource_counts,
            "preferred_time_budget_minutes": preferred_time_budget,
            "suggested_level": suggested_level,
            "confidence": confidence,
            "top_preferences": top_preferences,
            "persistent_weak_points": persistent_weak_points,
            "common_mistakes": common_mistakes,
            "strengths": strengths,
            "recent_goals": recent_goals[:6],
            "next_guidance": guidance[:5],
            "summary": summary,
            "last_activity_at": last_activity_at or None,
        }

    def _build_profile(self, request: GuideV2CreateInput, learner_memory: dict[str, Any] | None = None) -> LearnerProfile:
        goal = request.goal.strip()
        memory = learner_memory or {}
        memory_preferences = [str(item.get("label") or "") for item in memory.get("top_preferences") or [] if isinstance(item, dict)]
        memory_weak_points = [str(item.get("label") or "") for item in memory.get("persistent_weak_points") or [] if isinstance(item, dict)]
        memory_level = str(memory.get("suggested_level") or "").strip()
        if memory_level in {"", "unknown"}:
            memory_level = ""
        level = request.level.strip() or memory_level or self._infer_level(goal)
        budget = request.time_budget_minutes or int(memory.get("preferred_time_budget_minutes") or 0) or self._infer_time_budget(goal)
        preferences = self._dedupe_strings(list(request.preferences or []) + memory_preferences) or self._infer_preferences(goal)
        weak_points = self._dedupe_strings(list(request.weak_points or []) + memory_weak_points) or self._infer_weak_points(goal)
        context_parts = [self._summarize_context(request.notebook_context)]
        if memory.get("session_count"):
            context_parts.append(str(memory.get("summary") or ""))
            for item in memory.get("next_guidance") or []:
                context_parts.append(str(item))
        return LearnerProfile(
            goal=goal,
            level=level,
            time_budget_minutes=max(5, min(int(budget), 240)),
            horizon=request.horizon.strip() or self._infer_horizon(goal),
            preferences=preferences[:8],
            weak_points=weak_points[:8],
            source_context_summary=" ".join(item for item in context_parts if item).strip(),
        )

    async def _read_unified_learner_profile(self) -> dict[str, Any]:
        service = self.learner_profile_service
        if service is None:
            return {}
        try:
            profile = await service.read_profile(auto_refresh=True)
        except Exception as exc:
            self.logger.warning("Failed to read unified learner profile for guide planning: %s", exc)
            return {}
        return profile if isinstance(profile, dict) else {}

    def _attach_unified_profile_snapshot(
        self,
        session: GuideSessionV2,
        unified_profile: dict[str, Any],
    ) -> None:
        context = self._unified_profile_assessment_context(unified_profile)
        if context.get("available"):
            session.course_map.metadata["unified_learner_profile"] = context

    @staticmethod
    def _normalize_source_action(source_action: dict[str, Any] | None, *, goal: str) -> dict[str, Any]:
        if not isinstance(source_action, dict) or not source_action:
            return {}
        allowed = {
            "source",
            "kind",
            "title",
            "source_type",
            "source_label",
            "confidence",
            "estimated_minutes",
            "suggested_prompt",
            "href",
        }
        normalized: dict[str, Any] = {}
        for key in allowed:
            value = source_action.get(key)
            if value in (None, "", [], {}):
                continue
            if key in {"confidence"}:
                try:
                    normalized[key] = max(0.0, min(float(value), 1.0))
                except (TypeError, ValueError):
                    continue
            elif key in {"estimated_minutes"}:
                try:
                    normalized[key] = max(1, min(int(value), 240))
                except (TypeError, ValueError):
                    continue
            else:
                text = " ".join(str(value).split()).strip()
                if text:
                    normalized[key] = text[:500]
        if not normalized:
            return {}
        normalized.setdefault("source", "learner_profile")
        normalized.setdefault("kind", "next_action")
        normalized.setdefault("suggested_prompt", goal[:500])
        return normalized

    def _apply_unified_profile_to_profile(
        self,
        profile: LearnerProfile,
        unified_profile: dict[str, Any],
        *,
        request: GuideV2CreateInput,
    ) -> bool:
        hints = self._unified_profile_hints(unified_profile)
        if not hints:
            return False

        changed = False
        if not request.level.strip() and hints.get("level"):
            profile.level = str(hints["level"])
            changed = True
        if request.time_budget_minutes is None and hints.get("time_budget_minutes"):
            profile.time_budget_minutes = max(5, min(int(hints["time_budget_minutes"]), 240))
            changed = True

        for preference in hints.get("preferences") or []:
            before = len(profile.preferences)
            self._append_unique(profile.preferences, preference, limit=8)
            changed = changed or len(profile.preferences) != before
        for weak_point in hints.get("weak_points") or []:
            before = len(profile.weak_points)
            self._append_unique(profile.weak_points, weak_point, limit=8)
            changed = changed or len(profile.weak_points) != before

        context = self._unified_profile_context(hints)
        if context:
            profile.source_context_summary = " ".join(
                item for item in [profile.source_context_summary, context] if item
            ).strip()
            changed = True
        return changed

    def _evaluation_profile_context(self, session: GuideSessionV2) -> dict[str, Any]:
        latest = self._read_cached_unified_profile()
        context = self._unified_profile_assessment_context(latest)
        if not context.get("available"):
            cached = session.course_map.metadata.get("unified_learner_profile")
            context = dict(cached) if isinstance(cached, dict) else {}
        if not context.get("available"):
            return {"available": False}

        session_weak = {str(item).strip().lower() for item in session.profile.weak_points if str(item).strip()}
        profile_weak = [str(item) for item in context.get("weak_points") or [] if str(item).strip()]
        overlap = [item for item in profile_weak if item.lower() in session_weak]
        signal_score = int(context.get("signal_score") or 0)
        if overlap:
            signal_score = min(100, signal_score + 8)
        if context.get("calibration_count"):
            signal_score = min(100, signal_score + 5)
        context["session_weak_overlap"] = overlap[:4]
        context["signal_score"] = max(0, min(signal_score, 100))
        context["assessment_notes"] = self._profile_assessment_notes(context)
        return context

    def _read_cached_unified_profile(self) -> dict[str, Any]:
        service = self.learner_profile_service
        profile_path = getattr(service, "_profile_path", None)
        if not profile_path:
            return {}
        try:
            path = Path(profile_path)
            if not path.exists():
                return {}
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.logger.warning("Failed to read cached unified learner profile: %s", exc)
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _unified_profile_assessment_context(unified_profile: dict[str, Any]) -> dict[str, Any]:
        if not unified_profile:
            return {"available": False}
        overview = unified_profile.get("overview") if isinstance(unified_profile.get("overview"), dict) else {}
        stable = unified_profile.get("stable_profile") if isinstance(unified_profile.get("stable_profile"), dict) else {}
        learning_state = (
            unified_profile.get("learning_state")
            if isinstance(unified_profile.get("learning_state"), dict)
            else {}
        )
        data_quality = (
            unified_profile.get("data_quality")
            if isinstance(unified_profile.get("data_quality"), dict)
            else {}
        )
        evidence_count = GuideV2Manager._coerce_int(data_quality.get("evidence_count"), default=0)
        source_count = GuideV2Manager._coerce_int(data_quality.get("source_count"), default=0)
        calibration_count = GuideV2Manager._coerce_int(data_quality.get("calibration_count"), default=0)
        weak_points = GuideV2Manager._extract_label_list(learning_state.get("weak_points"), limit=6)
        preferences = GuideV2Manager._extract_label_list(stable.get("preferences"), limit=6)
        mastery = GuideV2Manager._extract_label_list(learning_state.get("mastery"), limit=6)
        recommendations = GuideV2Manager._extract_label_list(unified_profile.get("recommendations"), limit=5)
        signal_score = min(100, 45 + min(evidence_count, 18) * 2 + min(source_count, 5) * 7 + min(calibration_count, 4) * 8)
        if weak_points:
            signal_score = min(100, signal_score + 5)
        if not evidence_count and not source_count:
            signal_score = 45
        return {
            "available": True,
            "confidence": unified_profile.get("confidence"),
            "current_focus": str(overview.get("current_focus") or "").strip(),
            "summary": str(overview.get("summary") or "").strip(),
            "suggested_level": str(overview.get("suggested_level") or "").strip(),
            "preferred_time_budget_minutes": overview.get("preferred_time_budget_minutes"),
            "preferences": preferences,
            "weak_points": weak_points,
            "mastery": mastery,
            "recommendations": recommendations,
            "evidence_count": evidence_count,
            "source_count": source_count,
            "calibration_count": calibration_count,
            "read_only": bool(data_quality.get("read_only")),
            "signal_score": signal_score,
        }

    @staticmethod
    def _profile_assessment_notes(context: dict[str, Any]) -> list[str]:
        notes: list[str] = []
        if context.get("weak_points"):
            notes.append(f"长期画像仍提示薄弱点：{context['weak_points'][0]}")
        if context.get("session_weak_overlap"):
            notes.append(f"本次路线与长期薄弱点重合：{context['session_weak_overlap'][0]}")
        if context.get("recommendations"):
            notes.append(str(context["recommendations"][0]))
        if context.get("read_only"):
            notes.append("画像尚未经过用户校准，建议确认关键判断。")
        if not notes:
            notes.append("长期画像已纳入评估，但暂未发现需要额外干预的信号。")
        return notes[:4]

    @staticmethod
    def _profile_risk_signals(items: list[str], context: dict[str, Any]) -> list[str]:
        signals = list(items or [])
        if not context.get("available"):
            return signals
        if context.get("weak_points"):
            signals.append(f"长期画像仍显示薄弱点：{context['weak_points'][0]}。")
        if context.get("read_only"):
            signals.append("学习画像尚未校准，个性化判断需要用户确认。")
        return GuideV2Manager._dedupe_strings(signals)[:6]

    @staticmethod
    def _profile_next_actions(items: list[str], context: dict[str, Any]) -> list[str]:
        actions = list(items or [])
        if context.get("available"):
            if context.get("recommendations"):
                actions.insert(0, str(context["recommendations"][0]))
            elif context.get("weak_points"):
                actions.insert(0, f"先用图解或混合题补齐长期薄弱点：{context['weak_points'][0]}。")
            if context.get("read_only"):
                actions.append("到画像中心确认或修正系统对你的判断。")
        return GuideV2Manager._dedupe_strings(actions)[:6]

    @staticmethod
    def _profile_effect_evidence(context: dict[str, Any]) -> str:
        if not context.get("available"):
            return "尚未形成可用于长期评估的统一画像，当前主要依据本次路线证据。"
        weak = context.get("weak_points") or []
        pref = context.get("preferences") or []
        evidence_count = int(context.get("evidence_count") or 0)
        source_count = int(context.get("source_count") or 0)
        calibration_count = int(context.get("calibration_count") or 0)
        parts = [f"统一画像含 {source_count} 类来源、{evidence_count} 条证据"]
        if calibration_count:
            parts.append(f"已校准 {calibration_count} 次")
        if weak:
            parts.append(f"重点薄弱点：{weak[0]}")
        if pref:
            parts.append(f"偏好资源：{pref[0]}")
        return "；".join(parts) + "。"

    @staticmethod
    def _unified_profile_hints(unified_profile: dict[str, Any]) -> dict[str, Any]:
        if not unified_profile:
            return {}
        overview = unified_profile.get("overview") if isinstance(unified_profile.get("overview"), dict) else {}
        stable = unified_profile.get("stable_profile") if isinstance(unified_profile.get("stable_profile"), dict) else {}
        learning_state = (
            unified_profile.get("learning_state")
            if isinstance(unified_profile.get("learning_state"), dict)
            else {}
        )

        level = str(overview.get("suggested_level") or "").strip()
        if level in {"", "unknown"}:
            level = ""

        time_budget = GuideV2Manager._coerce_int(overview.get("preferred_time_budget_minutes"), default=0)
        weak_points = GuideV2Manager._extract_label_list(learning_state.get("weak_points"), limit=6)
        preferences = GuideV2Manager._extract_label_list(stable.get("preferences"), limit=6)
        goals = GuideV2Manager._extract_label_list(stable.get("goals"), limit=3)
        strengths = GuideV2Manager._extract_label_list(stable.get("strengths"), limit=3)

        hints = {
            "level": level,
            "time_budget_minutes": time_budget if time_budget > 0 else None,
            "current_focus": str(overview.get("current_focus") or "").strip(),
            "summary": str(overview.get("summary") or "").strip(),
            "preferences": preferences,
            "weak_points": weak_points,
            "goals": goals,
            "strengths": strengths,
            "confidence": unified_profile.get("confidence"),
        }
        return {key: value for key, value in hints.items() if value not in ("", None, [], {})}

    @staticmethod
    def _extract_label_list(value: Any, *, limit: int = 6) -> list[str]:
        items = value if isinstance(value, list) else []
        labels: list[str] = []
        for item in items:
            if isinstance(item, dict):
                label = str(item.get("label") or item.get("title") or item.get("value") or "").strip()
            else:
                label = str(item or "").strip()
            if label and label.lower() not in {existing.lower() for existing in labels}:
                labels.append(label)
            if len(labels) >= limit:
                break
        return labels

    @staticmethod
    def _unified_profile_context(hints: dict[str, Any]) -> str:
        parts: list[str] = []
        if hints.get("current_focus"):
            parts.append(f"focus={hints['current_focus']}")
        if hints.get("level"):
            parts.append(f"level={hints['level']}")
        if hints.get("weak_points"):
            parts.append(f"weak={', '.join(hints['weak_points'][:3])}")
        if hints.get("preferences"):
            parts.append(f"preferences={', '.join(hints['preferences'][:3])}")
        if hints.get("goals"):
            parts.append(f"goals={', '.join(hints['goals'][:2])}")
        if hints.get("confidence") is not None:
            parts.append(f"confidence={hints['confidence']}")
        return f"Unified learner profile: {'; '.join(parts)}." if parts else ""

    def _apply_memory_to_new_session(self, session: GuideSessionV2, memory: dict[str, Any]) -> bool:
        if not memory or int(memory.get("evidence_count") or 0) <= 0:
            return False

        preferences = [
            str(item.get("label") or "")
            for item in memory.get("top_preferences") or []
            if isinstance(item, dict) and str(item.get("label") or "").strip()
        ][:4]
        weak_points = [
            str(item.get("label") or "")
            for item in memory.get("persistent_weak_points") or []
            if isinstance(item, dict) and str(item.get("label") or "").strip()
        ][:4]
        common_mistakes = [
            str(item.get("label") or "")
            for item in memory.get("common_mistakes") or []
            if isinstance(item, dict) and str(item.get("label") or "").strip()
        ][:4]
        strengths = [
            str(item.get("label") or "")
            for item in memory.get("strengths") or []
            if isinstance(item, dict) and str(item.get("label") or "").strip()
        ][:4]
        if not any((preferences, weak_points, common_mistakes, strengths)):
            return False

        memory_payload = {
            "memory_version": memory.get("memory_version", 1),
            "source_session_count": int(memory.get("session_count") or 0),
            "evidence_count": int(memory.get("evidence_count") or 0),
            "average_score": memory.get("average_score"),
            "preferred_resources": preferences,
            "known_weak_points": weak_points,
            "common_mistakes": common_mistakes,
            "strengths": strengths,
            "guidance": list(memory.get("next_guidance") or [])[:4],
        }
        session.course_map.metadata["learner_memory"] = memory_payload

        for task in session.tasks:
            task.metadata["learner_memory"] = memory_payload
            if preferences:
                task.metadata["preferred_resource_types"] = preferences
            if common_mistakes:
                task.metadata["avoid_mistakes"] = common_mistakes
            if memory.get("average_score") is not None and float(memory.get("average_score") or 0) < 0.7:
                task.estimated_minutes = max(6, min(int(task.estimated_minutes or 8), max(10, session.profile.time_budget_minutes // 2)))
                self._append_unique(task.success_criteria, "完成一个可评分练习或写下一句可验证反思", limit=6)

        first_pending = self._first_pending_task(session)
        focus = weak_points[0] if weak_points else common_mistakes[0] if common_mistakes else ""
        if first_pending and focus:
            warmup = LearningTask(
                task_id=self._next_task_id(session, "M"),
                node_id=first_pending.node_id,
                type="memory_warmup",
                title=f"长期画像热身：{focus}",
                instruction=(
                    f"进入新路线前，先校准你过去反复出现的薄弱点「{focus}」。"
                    f"结合当前目标「{session.goal}」，写下一个最小例子、一个容易犯错的判断，"
                    "再说明你准备用什么练习或资源验证自己真的理解了。"
                ),
                estimated_minutes=max(6, min(10, session.profile.time_budget_minutes)),
                success_criteria=[
                    "说清楚这个薄弱点和当前目标的关系",
                    "写出一个过去容易出错的判断或步骤",
                    "确定一个可评分验证方式",
                ],
                origin="learner_memory",
                metadata={"learner_memory": memory_payload},
            )
            session.tasks.insert(0, warmup)
            session.learning_path.current_task_id = warmup.task_id
            session.learning_path.today_focus = f"先处理长期画像薄弱点：{focus}"
            session.learning_path.next_recommendation = (
                f"本路线已继承长期画像，建议先完成「{warmup.title}」，再进入原计划任务。"
            )
        elif first_pending:
            session.learning_path.current_task_id = first_pending.task_id

        session.learning_path.total_estimated_minutes = sum(
            task.estimated_minutes for task in session.tasks if task.status != "skipped"
        )
        return True

    @staticmethod
    def _ml_foundations_metadata(profile: LearnerProfile) -> dict[str, Any]:
        """Metadata for the built-in complete university course template."""

        weekly_schedule = [
            {"week": 1, "topic": "课程导论与机器学习问题定义", "deliverable": "学习目标卡 + 任务类型辨析"},
            {"week": 2, "topic": "数据集、特征、标签与数据划分", "deliverable": "一个真实场景的数据集方案"},
            {"week": 3, "topic": "线性回归与损失函数", "deliverable": "手算 MSE 的最小例题"},
            {"week": 4, "topic": "梯度下降与优化直觉", "deliverable": "梯度下降过程图解或短动画"},
            {"week": 5, "topic": "分类任务与逻辑回归", "deliverable": "决策边界说明 + 混合题练习"},
            {"week": 6, "topic": "模型评估、泛化与过拟合", "deliverable": "混淆矩阵指标计算表"},
            {"week": 7, "topic": "决策树与可解释模型", "deliverable": "两层决策树案例图"},
            {"week": 8, "topic": "课程项目整合与展示", "deliverable": "端到端建模报告提纲"},
        ]
        return {
            "course_id": "ML101",
            "course_name": "机器学习基础",
            "course_type": "complete_university_course",
            "credits": 2,
            "suggested_weeks": 8,
            "target_learners": "高校低年级或跨专业初学者",
            "learner_time_budget_minutes": profile.time_budget_minutes,
            "prerequisites": ["高等数学基础", "线性代数基础", "Python 或任意编程语言基本经验"],
            "learning_outcomes": [
                "能把真实问题表述为机器学习任务，并定义样本、特征和标签。",
                "能解释线性回归、逻辑回归、梯度下降和决策树的核心直觉。",
                "能使用准确率、精确率、召回率、F1 等指标评价模型。",
                "能完成一份包含问题定义、数据方案、建模选择、评估和反思的课程项目报告。",
            ],
            "assessment": [
                {"name": "过程练习与错因复盘", "weight": 30},
                {"name": "多模态学习资源作品", "weight": 20},
                {"name": "阶段测验", "weight": 20},
                {"name": "端到端课程项目", "weight": 30},
            ],
            "weekly_schedule": weekly_schedule,
            "project_milestones": [
                {"stage": "问题定义", "checkpoint": "明确预测目标、输入数据和使用场景。"},
                {"stage": "数据方案", "checkpoint": "列出字段、特征、标签、划分方式和潜在数据泄漏风险。"},
                {"stage": "模型选择", "checkpoint": "至少比较一个线性模型和一个可解释模型。"},
                {"stage": "评估反思", "checkpoint": "报告指标、错误案例、局限性和下一步改进。"},
            ],
            "demo_seed": GuideV2Manager._ml_foundations_demo_seed(profile),
        }

    @staticmethod
    def _ml_foundations_demo_seed(profile: LearnerProfile) -> dict[str, Any]:
        """Stable sample data for recording the built-in ML course demo."""

        return {
            "title": "机器学习基础稳定演示样例",
            "scenario": "一名跨专业学生想在 7 分钟内体验从画像、导学、资源生成到学习报告的完整闭环。",
            "persona": {
                "name": "跨专业初学者",
                "level": profile.level or "beginner",
                "goal": "理解机器学习基础，并能解释梯度下降和模型评估。",
                "weak_points": ["概念边界不清", "公式直觉不足", "指标容易混淆"],
                "preferences": ["图解", "短练习", "分步讲解"],
            },
            "task_chain": [
                {
                    "task_id": "T1",
                    "title": "建立机器学习全景图",
                    "stage": "画像与路线",
                    "show": "展示目标、偏好、薄弱点和知识地图。",
                    "sample_score": 0.72,
                    "sample_reflection": "我能区分监督学习和无监督学习，但还不确定特征、标签与样本的边界。",
                },
                {
                    "task_id": "T4",
                    "title": "画出梯度下降过程",
                    "stage": "多模态资源",
                    "resource_type": "visual",
                    "prompt": "围绕梯度下降生成一张图解：损失曲线、当前位置、负梯度方向、学习率过大/过小的对比。",
                    "sample_score": 0.58,
                    "sample_reflection": "我知道要沿下降方向走，但容易把梯度方向和参数更新方向说反。",
                },
                {
                    "task_id": "T6",
                    "title": "从混淆矩阵计算指标",
                    "stage": "交互练习",
                    "resource_type": "quiz",
                    "prompt": "生成一组模型评估混合题，包含准确率、精确率、召回率、F1 的选择、判断、填空和一道简答。",
                    "sample_score": 0.86,
                    "sample_reflection": "我能算出四个指标，也能解释召回率更适合漏诊代价高的场景。",
                },
            ],
            "resource_prompts": [
                {
                    "type": "visual",
                    "title": "梯度下降图解",
                    "prompt": "用山坡或损失曲线比喻梯度下降，突出负梯度、学习率和收敛。",
                },
                {
                    "type": "video",
                    "title": "梯度下降短视频",
                    "prompt": "用 Manim 分 4 步讲解梯度下降：目标、斜率、更新、学习率影响。",
                },
                {
                    "type": "quiz",
                    "title": "模型评估混合题",
                    "prompt": "围绕混淆矩阵生成选择、判断、填空、简答各 1 道，并附答案解析。",
                },
            ],
            "rehearsal_notes": [
                "优先演示 T1 -> T4 -> T6，覆盖画像、图解/动画、练习反馈和学习报告。",
                "如果现场时间不够，跳过完整课程项目，只展示课程产出包和演示就绪度。",
                "如果模型响应慢，直接展示兜底包中的历史产物和提示词。",
            ],
        }

    def _build_template_plan(self, template_id: str, profile: LearnerProfile) -> dict[str, Any]:
        template = (template_id or "").strip().lower()
        if template not in {"ml_foundations", "machine_learning_foundations"}:
            return {}
        topic = "机器学习基础"
        return {
            "course_map": {
                "title": f"{topic}完整课程导学",
                "generated_by": "template:ml_foundations",
                "metadata": self._ml_foundations_metadata(profile),
                "nodes": [
                    {"node_id": "ML1", "title": "课程导论与学习目标", "description": "理解机器学习要解决的问题、典型任务类型和学习路线。", "difficulty": "easy", "estimated_minutes": 30, "tags": ["orientation"], "mastery_target": "能区分监督学习、无监督学习和强化学习，并说出课程项目目标。", "resource_strategy": ["overview", "concept map"]},
                    {"node_id": "ML2", "title": "数据集、特征与标签", "description": "掌握样本、特征、标签、训练集、验证集、测试集和数据泄漏。", "prerequisites": ["ML1"], "difficulty": "easy", "estimated_minutes": 45, "tags": ["data"], "mastery_target": "能为一个真实问题定义特征、标签和数据划分方案。", "resource_strategy": ["case study", "quiz"]},
                    {"node_id": "ML3", "title": "线性回归与损失函数", "description": "理解线性模型、均方误差、参数学习和预测解释。", "prerequisites": ["ML2"], "difficulty": "medium", "estimated_minutes": 60, "tags": ["regression", "loss"], "mastery_target": "能手算一个小型线性回归例子，并解释损失函数意义。", "resource_strategy": ["worked example", "visual"]},
                    {"node_id": "ML4", "title": "梯度下降与优化直觉", "description": "理解梯度、学习率、收敛、局部最优和训练曲线。", "prerequisites": ["ML3"], "difficulty": "medium", "estimated_minutes": 60, "tags": ["optimization"], "mastery_target": "能解释梯度下降为什么沿负梯度方向更新，并分析学习率问题。", "resource_strategy": ["animation", "practice"]},
                    {"node_id": "ML5", "title": "分类、逻辑回归与决策边界", "description": "理解二分类、sigmoid、交叉熵和决策边界。", "prerequisites": ["ML4"], "difficulty": "medium", "estimated_minutes": 70, "tags": ["classification"], "mastery_target": "能解释逻辑回归输出概率的含义，并判断分类结果。", "resource_strategy": ["diagram", "mixed quiz"]},
                    {"node_id": "ML6", "title": "模型评估与泛化", "description": "掌握准确率、精确率、召回率、F1、过拟合、欠拟合和交叉验证。", "prerequisites": ["ML5"], "difficulty": "medium", "estimated_minutes": 60, "tags": ["evaluation"], "mastery_target": "能根据混淆矩阵计算指标，并选择合适的模型评估方式。", "resource_strategy": ["table", "quiz"]},
                    {"node_id": "ML7", "title": "决策树与可解释模型", "description": "理解树模型、信息增益、过拟合剪枝和可解释性。", "prerequisites": ["ML6"], "difficulty": "medium", "estimated_minutes": 60, "tags": ["tree", "interpretability"], "mastery_target": "能画出一个小型决策树并解释每次划分的含义。", "resource_strategy": ["visual", "case practice"]},
                    {"node_id": "ML8", "title": "课程项目：端到端建模报告", "description": "完成从问题定义、数据处理、建模、评估到反思的完整小项目。", "prerequisites": ["ML7"], "difficulty": "hard", "estimated_minutes": 120, "tags": ["project", "report"], "mastery_target": "能提交一份包含数据、模型、指标、误差分析和改进方向的报告。", "resource_strategy": ["project checklist", "rubric"]},
                ],
            },
            "learning_path": {
                "title": f"{topic}八阶段学习路线",
                "rationale": "先建立任务与数据意识，再学习核心模型和优化方法，最后通过项目形成迁移能力。",
                "node_sequence": ["ML1", "ML2", "ML3", "ML4", "ML5", "ML6", "ML7", "ML8"],
                "today_focus": "完成课程导论、数据定义和一个最小线性模型例子。",
                "next_recommendation": "先完成 ML1 和 ML2，再生成一次混合题检查基本概念。",
            },
            "tasks": [
                {"task_id": "T1", "node_id": "ML1", "type": "explain", "title": "建立机器学习全景图", "instruction": "用自己的话解释机器学习输入、输出、训练和预测的关系。", "estimated_minutes": 12, "success_criteria": ["区分三类学习任务", "说出一个课程项目方向"]},
                {"task_id": "T2", "node_id": "ML2", "type": "practice", "title": "设计一个数据集方案", "instruction": "选择一个校园场景，写出样本、特征、标签和数据划分。", "estimated_minutes": 15, "success_criteria": ["特征和标签定义清楚", "说明如何避免数据泄漏"]},
                {"task_id": "T3", "node_id": "ML3", "type": "practice", "title": "手算线性回归损失", "instruction": "给定 3 个样本，计算预测值、误差和均方误差。", "estimated_minutes": 18, "success_criteria": ["计算 MSE", "解释损失变大意味着什么"]},
                {"task_id": "T4", "node_id": "ML4", "type": "visualize", "title": "画出梯度下降过程", "instruction": "用曲线和箭头解释参数如何沿损失下降方向移动。", "estimated_minutes": 15, "success_criteria": ["指出梯度方向", "解释学习率过大/过小"]},
                {"task_id": "T5", "node_id": "ML5", "type": "practice", "title": "解释逻辑回归决策边界", "instruction": "用一个二维分类例子说明 sigmoid 概率和分类阈值。", "estimated_minutes": 18, "success_criteria": ["解释概率输出", "画出决策边界"]},
                {"task_id": "T6", "node_id": "ML6", "type": "practice", "title": "从混淆矩阵计算指标", "instruction": "计算 accuracy、precision、recall、F1，并说明适用场景。", "estimated_minutes": 20, "success_criteria": ["四个指标计算正确", "能选择合适指标"]},
                {"task_id": "T7", "node_id": "ML7", "type": "visualize", "title": "构建一个小型决策树", "instruction": "根据 6 条样本画出一个两层决策树，并解释每个节点。", "estimated_minutes": 20, "success_criteria": ["树结构清晰", "解释划分依据"]},
                {"task_id": "T8", "node_id": "ML8", "type": "project", "title": "完成端到端建模报告提纲", "instruction": "写出项目问题、数据字段、模型选择、评估指标和误差分析计划。", "estimated_minutes": 25, "success_criteria": ["报告结构完整", "包含误差分析和改进方向"]},
            ],
            "recommendations": [
                "先生成课程全景图，再进入数据集方案设计。",
                "每完成一个阶段都留下分数和一句反思，系统会据此调整路径。",
                "建议在 ML4 生成短视频讲解梯度下降，在 ML6 生成混合题检验指标计算。",
            ],
        }
    async def _build_plan_with_llm(
        self,
        profile: LearnerProfile,
        notebook_context: str,
    ) -> dict[str, Any]:
        prompt = (
            "Design a practical guided-learning session. Return JSON only with keys: "
            "course_map, learning_path, tasks, recommendations. "
            "course_map.nodes must include title, description, prerequisites, difficulty, "
            "estimated_minutes, tags, mastery_target, resource_strategy. "
            "tasks must include node_title or node_id, type, title, instruction, "
            "estimated_minutes, success_criteria.\n\n"
            f"Learner profile:\n{json.dumps(asdict(profile), ensure_ascii=False)}\n\n"
            f"Notebook or course context:\n{notebook_context[:5000] or '(none)'}"
        )
        try:
            raw = await self.completion_fn(
                prompt=prompt,
                system_prompt=(
                    "You are a learning path planner for higher education. "
                    "Create actionable, assessable tasks. Return JSON only."
                ),
                temperature=0.25,
                **self.llm_options,
            )
            parsed = self._parse_json_object(raw)
            return parsed if parsed else {}
        except Exception as exc:
            self.logger.info("Guide v2 LLM planning fell back to deterministic plan: %s", exc)
            return {}

    def _normalize_course_map(self, payload: dict[str, Any], profile: LearnerProfile) -> CourseMap:
        raw_map = payload.get("course_map") if isinstance(payload.get("course_map"), dict) else {}
        raw_nodes = raw_map.get("nodes") if isinstance(raw_map, dict) else None
        nodes: list[CourseNode] = []
        if isinstance(raw_nodes, list):
            for index, item in enumerate(raw_nodes[:8], start=1):
                node = self._normalize_node(item, index)
                if node:
                    nodes.append(node)
        if not nodes:
            nodes = self._fallback_nodes(profile)
        node_ids = {node.node_id for node in nodes}
        edges = []
        for node in nodes:
            for prereq in node.prerequisites:
                if prereq in node_ids:
                    edges.append({"from": prereq, "to": node.node_id})
        return CourseMap(
            title=str(raw_map.get("title") or self._short_title(profile.goal)),
            nodes=nodes,
            edges=edges,
            generated_by=str(raw_map.get("generated_by") or ("llm" if raw_nodes else "fallback")),
            metadata=dict(raw_map.get("metadata") or {}),
        )

    def _normalize_node(self, item: Any, index: int) -> CourseNode | None:
        if not isinstance(item, dict):
            return None
        title = str(item.get("title") or item.get("knowledge_title") or "").strip()
        if not title:
            return None
        node_id = str(item.get("node_id") or f"N{index}").strip()
        node_id = re.sub(r"[^A-Za-z0-9_-]", "", node_id) or f"N{index}"
        prerequisites = item.get("prerequisites") or []
        if not isinstance(prerequisites, list):
            prerequisites = [str(prerequisites)]
        tags = item.get("tags") or []
        if not isinstance(tags, list):
            tags = [str(tags)]
        strategy = item.get("resource_strategy") or []
        if not isinstance(strategy, list):
            strategy = [str(strategy)]
        return CourseNode(
            node_id=node_id,
            title=title,
            description=str(item.get("description") or item.get("summary") or "").strip(),
            prerequisites=[str(value).strip() for value in prerequisites if str(value).strip()],
            difficulty=str(item.get("difficulty") or "medium").strip() or "medium",
            estimated_minutes=max(5, min(self._safe_int(item.get("estimated_minutes"), 20), 120)),
            tags=[str(value).strip() for value in tags if str(value).strip()],
            mastery_target=str(item.get("mastery_target") or "").strip()
            or "Explain the idea and solve one representative task.",
            resource_strategy=[str(value).strip() for value in strategy if str(value).strip()],
        )

    def _normalize_tasks(self, payload: dict[str, Any], course_map: CourseMap) -> list[LearningTask]:
        title_to_id = {node.title.lower(): node.node_id for node in course_map.nodes}
        node_ids = {node.node_id for node in course_map.nodes}
        raw_tasks = payload.get("tasks") if isinstance(payload.get("tasks"), list) else []
        tasks: list[LearningTask] = []
        for index, item in enumerate(raw_tasks[:24], start=1):
            task = self._normalize_task(item, index, title_to_id, node_ids)
            if task:
                tasks.append(task)
        if not tasks:
            tasks = self._fallback_tasks(course_map)
        return tasks

    def _normalize_task(
        self,
        item: Any,
        index: int,
        title_to_id: dict[str, str],
        node_ids: set[str],
    ) -> LearningTask | None:
        if not isinstance(item, dict):
            return None
        node_id = str(item.get("node_id") or "").strip()
        if node_id not in node_ids:
            node_id = title_to_id.get(str(item.get("node_title") or "").strip().lower(), "")
        if not node_id:
            node_id = next(iter(node_ids), "")
        title = str(item.get("title") or "").strip()
        instruction = str(item.get("instruction") or item.get("description") or "").strip()
        if not title or not instruction:
            return None
        criteria = item.get("success_criteria") or []
        if not isinstance(criteria, list):
            criteria = [str(criteria)]
        return LearningTask(
            task_id=str(item.get("task_id") or f"T{index}"),
            node_id=node_id,
            type=str(item.get("type") or "explain").strip() or "explain",
            title=title,
            instruction=instruction,
            estimated_minutes=max(3, min(self._safe_int(item.get("estimated_minutes"), 8), 60)),
            success_criteria=[str(value).strip() for value in criteria if str(value).strip()],
        )

    def _adapt_learning_path(
        self,
        session: GuideSessionV2,
        task: LearningTask,
        evidence: LearningEvidence,
    ) -> list[PlanAdjustmentEvent]:
        """Insert or skip tasks from fresh evidence so the path reacts in place."""

        score = evidence.score
        if score is None:
            return []

        events: list[PlanAdjustmentEvent] = []
        task_index = next(
            (index for index, item in enumerate(session.tasks) if item.task_id == task.task_id),
            len(session.tasks) - 1,
        )
        node = next((item for item in session.course_map.nodes if item.node_id == task.node_id), None)
        node_title = node.title if node else task.title

        if score < 0.65 and task.origin != "adaptive_remediation":
            remediation = LearningTask(
                task_id=self._next_task_id(session, "R"),
                node_id=task.node_id,
                type="remediation",
                title=f"补救练习：{node_title}",
                instruction=(
                    "先回看本任务的关键概念和错因，再完成一组由易到难的纠错练习。"
                    f"最近反思：{evidence.reflection or '暂无反思'}"
                ),
                estimated_minutes=max(8, min(task.estimated_minutes + 4, 18)),
                success_criteria=[
                    "能指出原任务的主要错误原因",
                    "完成至少 3 道针对性练习",
                    "用一句话解释修正后的思路",
                ],
                origin="adaptive_remediation",
                metadata={
                    "trigger_task_id": task.task_id,
                    "trigger_evidence_id": evidence.evidence_id,
                    "trigger_score": score,
                },
            )
            retest = LearningTask(
                task_id=self._next_task_id(session, "Q"),
                node_id=task.node_id,
                type="quiz",
                title=f"复测：{node_title}",
                instruction=(
                    "完成补救练习后，用一组同类题复测是否真正修正错因。"
                    f"重点关注：{', '.join(evidence.mistake_types) if evidence.mistake_types else evidence.reflection or node_title}"
                ),
                estimated_minutes=max(6, min(task.estimated_minutes, 12)),
                success_criteria=[
                    "完成至少 3 道同类复测题",
                    "正确率达到 75% 以上",
                    "写出原错因和修正后的判断方法",
                ],
                origin="adaptive_retest",
                metadata={
                    "trigger_task_id": task.task_id,
                    "trigger_evidence_id": evidence.evidence_id,
                    "trigger_score": score,
                    "depends_on_task_id": remediation.task_id,
                    "mistake_types": list(evidence.mistake_types),
                },
            )
            self._insert_task_after(session, task_index, remediation)
            self._insert_task_after(session, task_index + 1, retest)
            event = PlanAdjustmentEvent(
                event_id=uuid.uuid4().hex[:10],
                type="insert_remediation",
                reason=f"{node_title} 的学习证据低于 65%，系统插入补救练习。",
                evidence_id=evidence.evidence_id,
                task_id=task.task_id,
                inserted_task_ids=[remediation.task_id, retest.task_id],
            )
            session.plan_events.append(event)
            events.append(event)

        if score >= 0.92:
            skipped = self._skip_redundant_task(session, task, task_index)
            if skipped is not None:
                event = PlanAdjustmentEvent(
                    event_id=uuid.uuid4().hex[:10],
                    type="skip_redundant",
                    reason=f"{node_title} 的证据表现很好，系统跳过一个重复铺垫任务。",
                    evidence_id=evidence.evidence_id,
                    task_id=task.task_id,
                    skipped_task_ids=[skipped.task_id],
                )
                session.plan_events.append(event)
                events.append(event)

        if (
            score >= 0.85
            and task.origin != "adaptive_transfer"
            and not any(item.origin == "adaptive_transfer" for item in session.tasks)
            and self._first_pending_task(session) is None
        ):
            transfer = LearningTask(
                task_id=self._next_task_id(session, "X"),
                node_id=task.node_id,
                type="project",
                title=f"迁移挑战：{self._short_title(session.goal)}",
                instruction="换一个真实场景应用这条学习路线，并说明哪些知识点被迁移使用。",
                estimated_minutes=15,
                success_criteria=[
                    "给出一个新场景或新题目",
                    "说明迁移所用的关键知识点",
                    "完成一次自评并保存总结",
                ],
                origin="adaptive_transfer",
                metadata={
                    "trigger_task_id": task.task_id,
                    "trigger_evidence_id": evidence.evidence_id,
                    "trigger_score": score,
                },
            )
            session.tasks.append(transfer)
            event = PlanAdjustmentEvent(
                event_id=uuid.uuid4().hex[:10],
                type="insert_transfer",
                reason="整条路线已完成且最近证据较好，系统追加迁移挑战。",
                evidence_id=evidence.evidence_id,
                task_id=task.task_id,
                inserted_task_ids=[transfer.task_id],
            )
            session.plan_events.append(event)
            events.append(event)

        if events:
            session.learning_path.total_estimated_minutes = sum(
                item.estimated_minutes for item in session.tasks if item.status != "skipped"
            )
            session.learning_path.next_recommendation = events[-1].reason
        return events

    def _insert_task_after(self, session: GuideSessionV2, index: int, task: LearningTask) -> None:
        insert_at = max(0, min(index + 1, len(session.tasks)))
        session.tasks.insert(insert_at, task)

    def _skip_redundant_task(
        self,
        session: GuideSessionV2,
        completed_task: LearningTask,
        completed_index: int,
    ) -> LearningTask | None:
        for candidate in session.tasks[completed_index + 1:]:
            if candidate.status in {"completed", "skipped"}:
                continue
            if candidate.node_id != completed_task.node_id:
                return None
            if candidate.origin != "planned":
                return None
            if candidate.type not in {"explain", "visualize", "reflection"}:
                return None
            candidate.status = "skipped"
            candidate.metadata = {
                **candidate.metadata,
                "skip_reason": "High-confidence evidence from the previous task.",
                "skipped_after_task_id": completed_task.task_id,
            }
            return candidate
        return None

    @staticmethod
    def _next_task_id(session: GuideSessionV2, prefix: str) -> str:
        existing = {task.task_id for task in session.tasks}
        index = 1
        while f"{prefix}{index}" in existing:
            index += 1
        return f"{prefix}{index}"

    def _build_learning_path(
        self,
        payload: dict[str, Any],
        profile: LearnerProfile,
        course_map: CourseMap,
        tasks: list[LearningTask],
    ) -> LearningPath:
        raw_path = payload.get("learning_path") if isinstance(payload.get("learning_path"), dict) else {}
        sequence = raw_path.get("node_sequence") if isinstance(raw_path, dict) else None
        if not isinstance(sequence, list) or not sequence:
            sequence = [node.node_id for node in course_map.nodes]
        current_task_id = tasks[0].task_id if tasks else ""
        return LearningPath(
            path_id=uuid.uuid4().hex[:10],
            title=str(raw_path.get("title") or f"{self._short_title(profile.goal)}导学路线"),
            rationale=str(raw_path.get("rationale") or self._fallback_rationale(profile)).strip(),
            node_sequence=[str(item) for item in sequence],
            current_task_id=current_task_id,
            total_estimated_minutes=sum(task.estimated_minutes for task in tasks),
            today_focus=str(raw_path.get("today_focus") or self._fallback_today_focus(course_map)).strip(),
            next_recommendation=str(raw_path.get("next_recommendation") or "").strip()
            or "先完成第一个任务并留下证据，系统会根据掌握分和反思动态调整后续路线。",
        )

    def _build_recommendations(
        self,
        profile: LearnerProfile,
        course_map: CourseMap,
        tasks: list[LearningTask],
    ) -> list[str]:
        pending = [task for task in tasks if task.status != "completed"]
        first = pending[0] if pending else None
        recommendations = []
        preferences = {item.lower() for item in profile.preferences}
        if first:
            recommendations.append(f"先完成「{first.title}」，预计 {first.estimated_minutes} 分钟。")
        if "visual" in preferences:
            recommendations.append("做题前先生成一张概念图，把术语、条件和常见误区放在同一张图里。")
        if "external_video" in preferences or any(token in item for item in preferences for token in ("公开视频", "精选视频", "bilibili", "youtube")):
            recommendations.append("需要补充讲解视角时，优先找一两个公开视频，看完再回到练习提交反馈。")
        if "video" in preferences:
            recommendations.append("遇到公式推导或过程变化时，优先生成一段短动画分步讲解。")
        if course_map.nodes:
            recommendations.append(f"本轮掌握目标：{course_map.nodes[0].mastery_target}")
        return recommendations[:4]

    def _study_blocks(self, session: GuideSessionV2) -> list[dict[str, Any]]:
        """Pack tasks into learner-facing time blocks."""

        budget = max(10, min(int(session.profile.time_budget_minutes or 30), 240))
        current = self._current_task(session)
        current_id = current.task_id if current else ""
        node_titles = {node.node_id: node.title for node in session.course_map.nodes}
        blocks: list[dict[str, Any]] = []
        bucket: list[LearningTask] = []
        bucket_minutes = 0

        def flush() -> None:
            nonlocal bucket, bucket_minutes
            if not bucket:
                return
            block_index = len(blocks) + 1
            completed = sum(1 for task in bucket if task.status in {"completed", "skipped"})
            contains_current = any(task.task_id == current_id for task in bucket)
            focus_node = bucket[0].node_id
            block_status = "completed" if completed == len(bucket) else "active" if contains_current else "pending"
            block_tasks = [
                {
                    "task_id": task.task_id,
                    "node_id": task.node_id,
                    "node_title": node_titles.get(task.node_id, task.node_id),
                    "type": task.type,
                    "title": task.title,
                    "status": task.status,
                    "estimated_minutes": task.estimated_minutes,
                    "success_criteria": task.success_criteria,
                    "artifact_count": len(task.artifact_refs),
                }
                for task in bucket
            ]
            blocks.append(
                {
                    "id": f"block-{block_index}",
                    "index": block_index,
                    "title": self._study_block_title(session, block_index, focus_node),
                    "focus": node_titles.get(focus_node, bucket[0].title),
                    "status": block_status,
                    "estimated_minutes": bucket_minutes,
                    "completed_tasks": completed,
                    "total_tasks": len(bucket),
                    "task_ids": [task.task_id for task in bucket],
                    "tasks": block_tasks,
                    "recommended_actions": self._study_block_actions(bucket, block_status),
                }
            )
            bucket = []
            bucket_minutes = 0

        for task in session.tasks:
            task_minutes = max(5, int(task.estimated_minutes or 8))
            if bucket and bucket_minutes + task_minutes > budget:
                flush()
            bucket.append(task)
            bucket_minutes += task_minutes
        flush()
        return blocks

    def _learning_timeline_events(self, session: GuideSessionV2) -> list[dict[str, Any]]:
        task_titles = {task.task_id: task.title for task in session.tasks}
        node_titles = {node.node_id: node.title for node in session.course_map.nodes}
        events: list[dict[str, Any]] = [
            {
                "id": f"session-{session.session_id}",
                "type": "session_created",
                "label": "路线创建",
                "title": "创建导学路线",
                "description": session.goal,
                "created_at": session.created_at,
                "score": None,
                "task_id": "",
                "task_title": "",
                "node_title": "",
                "impact": "学习目标、画像和初始路线已建立。",
                "source": "session",
            }
        ]

        for task in session.tasks:
            node_title = node_titles.get(task.node_id, task.node_id)
            if task.origin != "planned":
                events.append(
                    {
                        "id": f"task-{task.task_id}",
                        "type": "task_inserted",
                        "label": "任务插入",
                        "title": task.title,
                        "description": task.instruction,
                        "created_at": float(task.metadata.get("created_at") or session.updated_at),
                        "score": None,
                        "task_id": task.task_id,
                        "task_title": task.title,
                        "node_title": node_title,
                        "impact": f"来源：{task.origin}",
                        "source": "task",
                    }
                )
            for artifact in task.artifact_refs:
                artifact_type = str(artifact.get("type") or "resource")
                created_at = float(artifact.get("created_at") or session.updated_at)
                events.append(
                    {
                        "id": f"artifact-{artifact.get('id')}",
                        "type": "resource_generated",
                        "label": "资源生成",
                        "title": str(artifact.get("title") or self._resource_title(artifact_type, task)),
                        "description": f"{self._resource_label(artifact_type)} · {artifact.get('capability') or 'agent'}",
                        "created_at": created_at,
                        "score": None,
                        "task_id": task.task_id,
                        "task_title": task.title,
                        "node_title": node_title,
                        "impact": "多智能体资源已附着到当前任务。",
                        "source": "artifact",
                        "resource_type": artifact_type,
                    }
                )
                attempts = artifact.get("quiz_attempts") if isinstance(artifact.get("quiz_attempts"), list) else []
                for attempt in attempts:
                    events.append(
                        {
                            "id": f"quiz-{attempt.get('attempt_id')}",
                            "type": "quiz_attempt",
                            "label": "练习提交",
                            "title": f"提交练习：{task.title}",
                            "description": (
                                f"{attempt.get('correct_count', 0)}/{attempt.get('total_count', 0)} 正确"
                            ),
                            "created_at": float(attempt.get("created_at") or created_at),
                            "score": attempt.get("score"),
                            "task_id": task.task_id,
                            "task_title": task.title,
                            "node_title": node_title,
                            "impact": "练习结果已回写学习证据和题目本。",
                            "source": "quiz",
                        }
                    )

        for evidence in session.evidence:
            event_type = self._evidence_event_type(evidence.type)
            title = self._evidence_event_title(evidence, task_titles)
            feedback = evidence.metadata.get("learning_feedback") if isinstance(evidence.metadata, dict) else None
            feedback = feedback if isinstance(feedback, dict) else {}
            events.append(
                {
                    "id": f"evidence-{evidence.evidence_id}",
                    "type": event_type,
                    "label": self._timeline_type_label(event_type),
                    "title": title,
                    "description": str(feedback.get("summary") or evidence.reflection or title),
                    "created_at": evidence.created_at,
                    "score": evidence.score,
                    "task_id": evidence.task_id,
                    "task_title": task_titles.get(evidence.task_id, evidence.task_id),
                    "node_title": "",
                    "impact": str(feedback.get("summary") or self._evidence_impact(evidence)),
                    "source": "evidence",
                    "mistake_types": evidence.mistake_types,
                    "feedback_title": str(feedback.get("title") or ""),
                    "feedback_summary": str(feedback.get("summary") or ""),
                    "feedback_tone": str(feedback.get("tone") or ""),
                    "learning_feedback": feedback,
                }
            )

        for event in session.plan_events:
            events.append(
                {
                    "id": f"plan-{event.event_id}",
                    "type": "path_adjustment",
                    "label": "路径调整",
                    "title": self._timeline_type_label(event.type),
                    "description": event.reason,
                    "created_at": event.created_at,
                    "score": None,
                    "task_id": event.task_id,
                    "task_title": task_titles.get(event.task_id, event.task_id),
                    "node_title": "",
                    "impact": "路线根据学习证据自动改写。",
                    "source": "plan_event",
                    "inserted_task_ids": event.inserted_task_ids,
                    "skipped_task_ids": event.skipped_task_ids,
                }
            )

        return sorted(events, key=lambda item: float(item.get("created_at") or 0))

    def _learning_timeline_summary(
        self,
        session: GuideSessionV2,
        events: list[dict[str, Any]],
    ) -> dict[str, Any]:
        type_counts: dict[str, int] = {}
        for event in events:
            event_type = str(event.get("type") or "other")
            type_counts[event_type] = type_counts.get(event_type, 0) + 1
        quiz_attempts = type_counts.get("quiz_attempt", 0)
        resources = type_counts.get("resource_generated", 0)
        profile_updates = type_counts.get("profile_dialogue", 0) + type_counts.get("diagnostic", 0)
        scores = [
            float(event.get("score"))
            for event in events
            if event.get("score") is not None
        ]
        return {
            "event_count": len(events),
            "evidence_count": len(session.evidence),
            "resource_count": resources,
            "quiz_attempt_count": quiz_attempts,
            "path_adjustment_count": len(session.plan_events),
            "profile_update_count": profile_updates,
            "last_activity_at": max((float(event.get("created_at") or 0) for event in events), default=session.updated_at),
            "average_scored_activity": round(sum(scores) / len(scores), 3) if scores else 0.0,
            "type_counts": type_counts,
        }

    @staticmethod
    def _learning_behavior_tags(
        session: GuideSessionV2,
        summary: dict[str, Any],
    ) -> list[str]:
        tags: list[str] = []
        if summary.get("profile_update_count", 0) > 0:
            tags.append("画像已更新")
        if summary.get("resource_count", 0) > 0:
            tags.append("多模态资源")
        if summary.get("quiz_attempt_count", 0) > 0:
            tags.append("练习闭环")
        if summary.get("path_adjustment_count", 0) > 0:
            tags.append("路径自适应")
        if any(task.status == "completed" for task in session.tasks):
            tags.append("已有学习证据")
        return tags or ["等待学习行为"]

    @staticmethod
    def _feedback_digest(events: list[dict[str, Any]]) -> dict[str, Any]:
        feedback_events = [
            item
            for item in events
            if isinstance(item.get("learning_feedback"), dict)
            or str(item.get("feedback_summary") or "").strip()
        ]
        ordered = sorted(feedback_events, key=lambda item: float(item.get("created_at") or 0), reverse=True)
        tone_counts: dict[str, int] = {}
        items: list[dict[str, Any]] = []
        quality_scores: list[int] = []
        for event in ordered:
            feedback = event.get("learning_feedback") if isinstance(event.get("learning_feedback"), dict) else {}
            tone = str(feedback.get("tone") or event.get("feedback_tone") or "neutral")
            tone_counts[tone] = tone_counts.get(tone, 0) + 1
            quality = feedback.get("evidence_quality") if isinstance(feedback.get("evidence_quality"), dict) else {}
            quality_score = int(quality.get("score") or 0) if quality else 0
            if quality_score:
                quality_scores.append(quality_score)
            items.append(
                {
                    "event_id": event.get("id"),
                    "task_id": event.get("task_id"),
                    "task_title": event.get("task_title"),
                    "title": feedback.get("title") or event.get("feedback_title") or event.get("title"),
                    "summary": feedback.get("summary") or event.get("feedback_summary") or event.get("impact"),
                    "tone": tone,
                    "score_percent": feedback.get("score_percent"),
                    "evidence_quality": quality,
                    "created_at": event.get("created_at"),
                    "actions": list(feedback.get("actions") or [])[:3] if isinstance(feedback, dict) else [],
                }
            )
        latest = items[0] if items else None
        return {
            "count": len(items),
            "success_count": tone_counts.get("success", 0),
            "warning_count": tone_counts.get("warning", 0),
            "brand_count": tone_counts.get("brand", 0),
            "quality_average": round(sum(quality_scores) / len(quality_scores)) if quality_scores else 0,
            "latest": latest,
            "items": items[:6],
        }

    def _effect_context(
        self,
        session: GuideSessionV2,
        *,
        evaluation: dict[str, Any] | None = None,
        mistake_review: dict[str, Any] | None = None,
        timeline_events: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Collect behavior, feedback, mistake loop, and effect assessment in one place."""

        evaluation_payload = evaluation if isinstance(evaluation, dict) else self.evaluate_session(session.session_id)
        events = timeline_events if timeline_events is not None else self._learning_timeline_events(session)
        behavior_summary = self._learning_timeline_summary(session, events)
        feedback_digest = self._feedback_digest(events)
        mistake_payload = mistake_review if isinstance(mistake_review, dict) else self.build_mistake_review(session.session_id)
        if not mistake_payload.get("success", True):
            mistake_payload = {"summary": {}, "clusters": [], "retest_plan": []}
        effect_assessment = self._effect_assessment(
            evaluation=evaluation_payload,
            behavior_summary=behavior_summary,
            mistake_payload=mistake_payload,
            feedback_digest=feedback_digest,
            profile_context=evaluation_payload.get("learner_profile_context"),
        )
        return {
            "timeline_events": events,
            "behavior_summary": behavior_summary,
            "feedback_digest": feedback_digest,
            "mistake_review": mistake_payload,
            "effect_assessment": effect_assessment,
            "learner_profile_context": evaluation_payload.get("learner_profile_context", {}),
        }

    @staticmethod
    def _effect_assessment(
        *,
        evaluation: dict[str, Any],
        behavior_summary: dict[str, Any],
        mistake_payload: dict[str, Any],
        feedback_digest: dict[str, Any],
        profile_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        progress = int(evaluation.get("progress") or 0)
        overall_score = int(evaluation.get("overall_score") or 0)
        average_evidence_score = float(evaluation.get("average_evidence_score") or 0)
        evidence_count = int(behavior_summary.get("evidence_count") or 0)
        resource_count = int(behavior_summary.get("resource_count") or 0)
        quiz_count = int(behavior_summary.get("quiz_attempt_count") or 0)
        profile_updates = int(behavior_summary.get("profile_update_count") or 0)
        mistake_summary = dict(mistake_payload.get("summary") or {})
        cluster_count = int(mistake_summary.get("cluster_count") or 0)
        closed_count = int(mistake_summary.get("closed_cluster_count") or 0)
        pending_remediation = int(mistake_summary.get("pending_remediation_count") or 0)
        pending_retest = int(mistake_summary.get("pending_retest_count") or 0)
        warning_count = int(feedback_digest.get("warning_count") or 0)
        quality_average = int(feedback_digest.get("quality_average") or 0)

        evidence_quality = 0
        if evidence_count:
            score_part = round(average_evidence_score * 70)
            volume_part = min(30, evidence_count * 10)
            evidence_quality = max(0, min(100, score_part + volume_part))
            if quality_average:
                evidence_quality = round(evidence_quality * 0.6 + quality_average * 0.4)

        engagement = min(100, resource_count * 18 + quiz_count * 28 + profile_updates * 18 + evidence_count * 10)
        if cluster_count:
            remediation_loop = round((closed_count / cluster_count) * 100)
            remediation_loop = max(20, remediation_loop - pending_remediation * 12 - pending_retest * 8)
        else:
            remediation_loop = 80 if evidence_count else 35
        profile_payload = profile_context if isinstance(profile_context, dict) else {}
        profile_available = bool(profile_payload.get("available"))
        profile_signal_score = int(profile_payload.get("signal_score") or (72 if profile_available else 60))

        dimensions = [
            {
                "id": "progress",
                "label": "任务进度",
                "score": progress,
                "status": GuideV2Manager._effect_status(progress),
                "evidence": f"已完成 {evaluation.get('completed_tasks', 0)}/{evaluation.get('total_tasks', 0)} 个任务。",
            },
            {
                "id": "mastery",
                "label": "综合掌握",
                "score": overall_score,
                "status": GuideV2Manager._effect_status(overall_score),
                "evidence": f"综合掌握分 {overall_score}，平均掌握度 {round(float(evaluation.get('average_mastery') or 0) * 100)}%。",
            },
            {
                "id": "evidence",
                "label": "证据质量",
                "score": evidence_quality,
                "status": GuideV2Manager._effect_status(evidence_quality),
                "evidence": (
                    f"累计 {evidence_count} 条学习证据，平均证据分 {round(average_evidence_score * 100)}%。"
                    + (f" 证据完整度约 {quality_average}%。" if quality_average else "")
                ),
            },
            {
                "id": "engagement",
                "label": "学习参与",
                "score": engagement,
                "status": GuideV2Manager._effect_status(engagement),
                "evidence": f"生成 {resource_count} 个资源，提交 {quiz_count} 次练习，画像/诊断更新 {profile_updates} 次。",
            },
            {
                "id": "remediation",
                "label": "错因闭环",
                "score": max(0, min(100, remediation_loop)),
                "status": GuideV2Manager._effect_status(remediation_loop),
                "evidence": f"{closed_count}/{cluster_count} 类错因已关闭，待补救 {pending_remediation} 个，待复测 {pending_retest} 个。",
            },
            {
                "id": "longitudinal_profile",
                "label": "长期画像",
                "score": profile_signal_score,
                "status": GuideV2Manager._effect_status(profile_signal_score),
                "evidence": GuideV2Manager._profile_effect_evidence(profile_payload),
            },
        ]
        weights = {
            "progress": 0.16,
            "mastery": 0.27,
            "evidence": 0.2,
            "engagement": 0.14,
            "remediation": 0.13,
            "longitudinal_profile": 0.1,
        }
        effect_score = round(
            sum(int(item.get("score") or 0) * weights.get(str(item.get("id") or ""), 0) for item in dimensions)
        )
        label = GuideV2Manager._effect_label(effect_score, evidence_count=evidence_count, warning_count=warning_count)
        strategy: list[str] = []
        if evidence_count == 0:
            strategy.append("先完成一个可评分任务，建立第一条学习证据。")
        if evidence_quality < 65 and evidence_count:
            strategy.append("提高证据质量：用练习题或复测替代单纯反思。")
        if pending_remediation or pending_retest:
            strategy.append("优先完成补救和复测，让错因从待处理变成已关闭。")
        if resource_count == 0:
            strategy.append("为当前薄弱点生成图解或短视频，降低理解门槛。")
        if profile_available and profile_payload.get("weak_points"):
            strategy.append(f"长期画像提示优先补齐「{profile_payload['weak_points'][0]}」，避免单次路线结束后问题反复出现。")
        if profile_available and profile_payload.get("read_only"):
            strategy.append("画像仍缺少用户校准，建议在画像中心确认或修正系统判断。")
        if effect_score >= 80 and progress >= 60:
            strategy.append("进入迁移应用或课程项目，把掌握转化为产出。")
        if not strategy:
            strategy.append("继续保持当前节奏，下一步用迁移题验证稳定掌握。")
        return {
            "score": effect_score,
            "label": label,
            "summary": GuideV2Manager._effect_summary(label, effect_score, warning_count),
            "dimensions": dimensions,
            "strategy_adjustments": strategy[:4],
        }

    @staticmethod
    def _effect_status(score: float) -> str:
        if score >= 85:
            return "excellent"
        if score >= 70:
            return "stable"
        if score >= 50:
            return "needs_support"
        return "insufficient"

    @staticmethod
    def _effect_label(score: int, *, evidence_count: int, warning_count: int) -> str:
        if evidence_count == 0:
            return "证据不足"
        if score >= 85:
            return "可迁移应用"
        if score >= 70 and warning_count == 0:
            return "掌握稳定"
        if score >= 55:
            return "需要补强"
        return "需要引导"

    @staticmethod
    def _effect_summary(label: str, score: int, warning_count: int) -> str:
        if label == "证据不足":
            return "当前缺少足够学习证据，系统会先引导完成可评分任务。"
        if label == "可迁移应用":
            return f"学习效果评分 {score}，已具备进入迁移应用或项目产出的条件。"
        if label == "掌握稳定":
            return f"学习效果评分 {score}，当前路线推进稳定，可以继续按计划学习。"
        if label == "需要补强":
            return f"学习效果评分 {score}，系统已发现 {warning_count} 次需干预反馈，建议先补强薄弱点。"
        return f"学习效果评分 {score}，需要更多结构化讲解、练习和反馈来建立稳定掌握。"

    @staticmethod
    def _coach_loop_context(
        session: GuideSessionV2,
        mistake_review: dict[str, Any],
    ) -> dict[str, Any]:
        summary = mistake_review.get("summary") if isinstance(mistake_review.get("summary"), dict) else {}
        clusters = mistake_review.get("clusters") if isinstance(mistake_review.get("clusters"), list) else []
        remediation_tasks = (
            mistake_review.get("remediation_tasks")
            if isinstance(mistake_review.get("remediation_tasks"), list)
            else []
        )
        retest_tasks = mistake_review.get("retest_tasks") if isinstance(mistake_review.get("retest_tasks"), list) else []
        terminal = {"completed", "skipped"}
        task_by_id = {task.task_id: task for task in session.tasks}

        def pending_task(items: list[Any]) -> dict[str, Any] | None:
            return next(
                (
                    item
                    for item in items
                    if isinstance(item, dict) and str(item.get("status") or "") not in terminal
                ),
                None,
            )

        def cluster_for(task_id: str, field: str) -> dict[str, Any] | None:
            if not task_id:
                return None
            return next(
                (
                    item
                    for item in clusters
                    if isinstance(item, dict) and task_id in {str(value) for value in item.get(field) or []}
                ),
                None,
            )

        pending_remediation = pending_task(remediation_tasks)
        pending_retest = pending_task(retest_tasks)
        task: LearningTask | None = None
        cluster: dict[str, Any] | None = None
        mode = "normal"
        reason = "暂无未关闭错因，按当前学习路径推进。"

        if pending_remediation:
            task_id = str(pending_remediation.get("task_id") or "")
            task = task_by_id.get(task_id)
            cluster = cluster_for(task_id, "pending_remediation_task_ids")
            mode = "remediation"
            label = str((cluster or {}).get("label") or (task.title if task else "当前错因"))
            reason = f"错因「{label}」还没有完成补救，先把纠错证据补上。"
        elif pending_retest:
            task_id = str(pending_retest.get("task_id") or "")
            task = task_by_id.get(task_id)
            cluster = cluster_for(task_id, "pending_retest_task_ids")
            mode = "retest"
            label = str((cluster or {}).get("label") or (task.title if task else "当前错因"))
            reason = f"补救已完成，接下来用复测确认「{label}」是否真正关闭。"
        else:
            open_cluster = next(
                (
                    item
                    for item in clusters
                    if isinstance(item, dict) and str(item.get("loop_status") or "") != "closed"
                ),
                None,
            )
            if open_cluster and str(open_cluster.get("loop_status") or "") == "retest_failed":
                cluster = open_cluster
                mode = "retest_failed"
                label = str(cluster.get("label") or "当前错因")
                reason = f"「{label}」复测未通过，需要回到错因讲解和针对性练习。"
            elif summary.get("closed_loop"):
                cluster = next((item for item in clusters if isinstance(item, dict)), None)
                mode = "closed_loop"
                reason = "已发现的错因都完成了补救和复测，可以继续推进下一段学习。"
            elif open_cluster:
                cluster = open_cluster
                mode = "review"
                label = str(cluster.get("label") or "当前错因")
                reason = f"「{label}」还没有形成完整闭环，建议先生成复测题或补救图解。"

        if cluster is None:
            cluster = next((item for item in clusters if isinstance(item, dict)), None)
        return {
            "mode": mode,
            "priority_reason": reason,
            "task": task,
            "cluster": cluster,
            "summary": summary,
        }

    @staticmethod
    def _coach_headline(
        session: GuideSessionV2,
        evaluation: dict[str, Any],
        current_task: LearningTask | None,
        loop_context: dict[str, Any] | None = None,
    ) -> str:
        mode = str((loop_context or {}).get("mode") or "normal")
        cluster = (loop_context or {}).get("cluster")
        label = str(cluster.get("label") or "") if isinstance(cluster, dict) else ""
        if mode == "remediation" and current_task is not None:
            return f"今天先补救「{current_task.title}」，把错因「{label or '当前薄弱点'}」讲清楚。"
        if mode == "retest" and current_task is not None:
            return f"补救已完成，立刻用「{current_task.title}」验证错因是否关闭。"
        if mode == "retest_failed":
            return f"复测没有过，先回到「{label or '当前错因'}」做一次针对性拆解。"
        if mode == "closed_loop":
            return "本轮错因已经闭环，可以把节奏切回新知识推进。"
        if mode == "review":
            return f"先处理「{label or '当前错因'}」，再继续后面的路线。"
        progress = int(evaluation.get("progress") or 0)
        if current_task is None:
            return "本轮路线已完成，适合进入复盘和迁移应用。"
        if progress == 0:
            return f"先把「{current_task.title}」做成第一条学习证据。"
        if evaluation.get("risk_signals"):
            return f"今天先稳住「{current_task.title}」，补齐薄弱证据。"
        return f"继续推进「{current_task.title}」，完成后路线会自动校准。"

    @staticmethod
    def _coach_summary(
        session: GuideSessionV2,
        evaluation: dict[str, Any],
        behavior_summary: dict[str, Any],
        loop_context: dict[str, Any] | None = None,
    ) -> str:
        completed = int(evaluation.get("completed_tasks") or 0)
        total = int(evaluation.get("total_tasks") or len(session.tasks))
        score = int(evaluation.get("overall_score") or 0)
        event_count = int(behavior_summary.get("event_count") or 0)
        resource_count = int(behavior_summary.get("resource_count") or 0)
        quiz_count = int(behavior_summary.get("quiz_attempt_count") or 0)
        summary = (loop_context or {}).get("summary") if isinstance((loop_context or {}).get("summary"), dict) else {}
        mode = str((loop_context or {}).get("mode") or "normal")
        if mode in {"remediation", "retest", "retest_failed", "review", "closed_loop"}:
            open_count = int(summary.get("open_cluster_count") or 0)
            closed_count = int(summary.get("closed_cluster_count") or 0)
            pending_retest = int(summary.get("pending_retest_count") or 0)
            pending_remediation = int(summary.get("pending_remediation_count") or 0)
            return (
                f"已完成 {completed}/{total} 个任务，综合掌握分 {score}。"
                f"当前错因闭环：{open_count} 个待处理、{closed_count} 个已关闭、"
                f"{pending_remediation} 个补救任务、{pending_retest} 个复测任务。"
                f"{(loop_context or {}).get('priority_reason') or '下一步优先处理可验证证据。'}"
            )
        return (
            f"已完成 {completed}/{total} 个任务，综合掌握分 {score}。"
            f"系统已记录 {event_count} 条行为、{resource_count} 个资源和 {quiz_count} 次练习，"
            "下一步会优先围绕可验证证据推进。"
        )

    @staticmethod
    def _coach_blockers(
        session: GuideSessionV2,
        evaluation: dict[str, Any],
        behavior_summary: dict[str, Any],
        loop_context: dict[str, Any] | None = None,
        effect_assessment: dict[str, Any] | None = None,
    ) -> list[str]:
        blockers: list[str] = []
        reason = str((loop_context or {}).get("priority_reason") or "")
        if reason and str((loop_context or {}).get("mode") or "normal") != "normal":
            blockers.append(reason)
        for item in evaluation.get("risk_signals") or []:
            if item and item not in blockers:
                blockers.append(str(item))
        if not session.evidence:
            blockers.append("还没有任务完成证据，系统无法判断真实掌握情况。")
        if int(behavior_summary.get("quiz_attempt_count") or 0) == 0:
            blockers.append("还没有交互式练习结果，学习效果评估缺少量化数据。")
        if int(behavior_summary.get("resource_count") or 0) == 0:
            blockers.append("还没有图解、视频或题目资源，遇到抽象概念时可先生成辅助材料。")
        effect_score = int((effect_assessment or {}).get("score") or 0)
        if effect_score and effect_score < 70:
            for item in (effect_assessment or {}).get("strategy_adjustments") or []:
                if item and item not in blockers:
                    blockers.append(str(item))
        return blockers[:4]

    @staticmethod
    def _coach_evidence_reasons(
        session: GuideSessionV2,
        recent_events: list[dict[str, Any]],
        behavior_summary: dict[str, Any],
    ) -> list[str]:
        reasons: list[str] = []
        memory_payload = (
            session.course_map.metadata.get("learner_memory")
            if isinstance(session.course_map.metadata.get("learner_memory"), dict)
            else {}
        )
        if memory_payload:
            weak_points = [str(item) for item in memory_payload.get("known_weak_points") or [] if str(item).strip()]
            common_mistakes = [str(item) for item in memory_payload.get("common_mistakes") or [] if str(item).strip()]
            focus = weak_points[0] if weak_points else common_mistakes[0] if common_mistakes else ""
            if focus:
                reasons.append(f"长期学习画像显示「{focus}」反复出现，所以本轮先用热身和针对性资源降低复发概率。")
        if recent_events:
            latest = recent_events[0]
            reasons.append(f"最近事件：{latest.get('label') or latest.get('type')}，{latest.get('title') or latest.get('description') or '-'}。")
        if behavior_summary.get("average_scored_activity"):
            score = round(float(behavior_summary.get("average_scored_activity") or 0) * 100)
            reasons.append(f"有分数的学习行为平均约 {score}%，可作为路径调整依据。")
        if session.plan_events:
            reasons.append(f"路线已经自动调整 {len(session.plan_events)} 次，说明系统正在根据证据改变学习节奏。")
        if not reasons:
            reasons.append("当前简报主要基于初始学习画像和课程地图，完成第一项任务后会更精确。")
        return reasons[:4]

    @staticmethod
    def _evidence_quality_profile(task: LearningTask, evidence: LearningEvidence) -> dict[str, Any]:
        score = 0
        strengths: list[str] = []
        gaps: list[str] = []
        reflection = " ".join(str(evidence.reflection or "").split()).strip()

        if evidence.score is not None:
            score += 20
            strengths.append("提交了可量化掌握分")
        else:
            gaps.append("缺少掌握分，系统只能根据文字粗略判断")

        if evidence.type == "quiz":
            question_count = int(evidence.metadata.get("question_count") or 0)
            wrong_count = int(evidence.metadata.get("wrong_count") or 0)
            score += min(35, question_count * 8)
            if question_count >= 3:
                strengths.append("练习题数量足够支撑一次小测判断")
            elif question_count:
                gaps.append("题目数量偏少，建议再补一组同类题")
            if wrong_count:
                score += 12
                strengths.append("错题已暴露，可用于后续补救和复测")
            else:
                score += 8
                strengths.append("本次练习没有显式错题")
        else:
            if len(reflection) >= 36:
                score += 35
                strengths.append("反思较完整，包含可追踪的学习信息")
            elif len(reflection) >= 12:
                score += 22
                strengths.append("留下了基础反思")
            else:
                gaps.append("反思过短，难以判断你具体会在哪里")
            if evidence.mistake_types:
                score += 18
                strengths.append("标注了错因或薄弱点")
            elif evidence.score is not None and float(evidence.score) < 0.8:
                gaps.append("分数不高但没有标注错因")
            if task.artifact_refs:
                score += 10
                strengths.append("当前任务已有资源产物可作为旁证")
            if task.success_criteria:
                score += 7

        if evidence.score is not None and float(evidence.score) >= 0.85 and evidence.type != "quiz" and len(reflection) < 18:
            gaps.append("高分证据需要补一句理由，说明为什么认为自己掌握了")
        score = max(0, min(100, score))
        if score >= 80:
            label = "证据充分"
        elif score >= 60:
            label = "证据可用"
        elif score >= 40:
            label = "证据偏弱"
        else:
            label = "证据不足"
        if evidence.type == "quiz":
            next_prompt = "下一次证据优先提交 3-5 道混合题结果，并保留错题解析。"
        elif gaps:
            next_prompt = f"下一次证据请补充：{gaps[0]}。"
        else:
            next_prompt = "下一次继续提交掌握分、错因和一句可验证反思。"
        return {
            "score": score,
            "label": label,
            "strengths": strengths[:3],
            "gaps": gaps[:3],
            "next_evidence_prompt": next_prompt,
        }

    @staticmethod
    def _learning_feedback(
        session: GuideSessionV2,
        task: LearningTask,
        evidence: LearningEvidence,
        adjustments: list[PlanAdjustmentEvent],
        next_task: LearningTask | None,
    ) -> dict[str, Any]:
        score = evidence.score
        score_percent = round(float(score) * 100) if score is not None else None
        adjustment_types = [item.type for item in adjustments]
        evidence_quality = (
            evidence.metadata.get("evidence_quality")
            if isinstance(evidence.metadata.get("evidence_quality"), dict)
            else {}
        )
        concept_feedback = (
            evidence.metadata.get("concept_feedback")
            if isinstance(evidence.metadata.get("concept_feedback"), list)
            else []
        )
        resource_actions = GuideV2Manager._concept_feedback_resource_actions(
            task,
            concept_feedback,
            next_task=next_task,
            adjustment_types=adjustment_types,
        )
        actions: list[str] = []
        tone = "brand"

        if "insert_remediation" in adjustment_types:
            tone = "warning"
            title = "已插入补救与复测"
            summary = (
                f"这次证据显示「{task.title}」还不稳，系统已经把补救任务提前。"
                "先纠正错因，再用复测确认是否真正掌握。"
            )
            actions.append("先完成补救任务，必要时生成补救图解或纠错练习。")
        elif "insert_transfer" in adjustment_types:
            tone = "success"
            title = "可以进入迁移应用"
            summary = (
                f"「{task.title}」的完成质量不错，系统追加了迁移任务。"
                "下一步重点是把知识用到新场景，而不是重复刷同类题。"
            )
            actions.append("进入迁移任务，用新情境解释或应用本知识点。")
        elif next_task is None:
            tone = "success"
            title = "本轮学习路线已完成"
            summary = "当前学习路径已经闭合，适合保存学习报告、整理课程产出包，并做一次复盘。"
            actions.append("保存学习报告或课程产出包。")
        elif score is not None and score < 0.65:
            tone = "warning"
            title = "需要先稳住这个薄弱点"
            summary = f"本次掌握评分约 {score_percent}%，建议先回看讲解，再进入下一步。"
            actions.append("生成图解或例题，补齐关键理解。")
        elif score is not None and score >= 0.85:
            tone = "success"
            title = "掌握证据较稳定"
            summary = f"本次掌握评分约 {score_percent}%，可以继续推进下一项任务。"
            actions.append("继续下一任务，并尝试用自己的话解释核心概念。")
        else:
            title = "学习证据已记录"
            if score_percent is None:
                summary = "这次完成记录已进入学习画像，系统会用它校准后续路线。"
            else:
                summary = f"本次掌握评分约 {score_percent}%，系统已据此更新掌握度和下一步建议。"
            actions.append("继续当前路线，并在下一次完成时补充一句反思。")

        if evidence.mistake_types:
            actions.append(f"重点关注错因：{'、'.join(evidence.mistake_types[:3])}。")
        if concept_feedback:
            weakest = next(
                (
                    item for item in concept_feedback
                    if isinstance(item, dict) and str(item.get("status") or "") == "needs_support"
                ),
                None,
            )
            if weakest:
                actions.append(f"优先补齐知识点：{weakest.get('concept')}。{weakest.get('next_action') or ''}")
        if evidence_quality.get("next_evidence_prompt"):
            actions.append(str(evidence_quality["next_evidence_prompt"]))
        if next_task is not None:
            actions.append(f"下一步：{next_task.title}。")

        return {
            "title": title,
            "summary": summary,
            "tone": tone,
            "score_percent": score_percent,
            "task_id": task.task_id,
            "task_title": task.title,
            "next_task_id": next_task.task_id if next_task else "",
            "next_task_title": next_task.title if next_task else "",
            "adjustment_types": adjustment_types,
            "evidence_quality": evidence_quality,
            "concept_feedback": concept_feedback,
            "resource_actions": resource_actions,
            "actions": actions[:4],
            "session_status": session.status,
        }

    @staticmethod
    def _concept_feedback_resource_actions(
        task: LearningTask,
        concept_feedback: list[Any],
        *,
        next_task: LearningTask | None = None,
        adjustment_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        if not concept_feedback:
            return []
        rows = [item for item in concept_feedback if isinstance(item, dict)]
        if not rows:
            return []
        status_rank = {"needs_support": 0, "developing": 1, "stable": 2}
        rows.sort(key=lambda item: (status_rank.get(str(item.get("status") or ""), 1), float(item.get("score") or 0)))
        target = rows[0]
        concept = " ".join(str(target.get("concept") or task.title).split()).strip() or task.title
        status = str(target.get("status") or "")
        score_percent = int(target.get("score_percent") or round(float(target.get("score") or 0) * 100))
        adjustment_set = set(adjustment_types or [])
        adaptive_next_origins = {
            "adaptive_remediation",
            "diagnostic_remediation",
            "adaptive_retest",
            "adaptive_transfer",
        }
        action_task = task
        if next_task is not None and (
            "insert_remediation" in adjustment_set
            or "insert_transfer" in adjustment_set
            or next_task.origin in adaptive_next_origins
        ):
            action_task = next_task

        def action(
            suffix: str,
            *,
            title: str,
            resource_type: str,
            prompt: str,
            primary: bool,
        ) -> dict[str, Any]:
            return {
                "id": f"{action_task.task_id}-concept-{suffix}",
                "action_type": "resource",
                "label": title,
                "title": title,
                "resource_type": resource_type,
                "target_task_id": action_task.task_id,
                "target_task_title": action_task.title,
                "prompt": prompt,
                "primary": primary,
                "concept": concept,
                "concept_status": status,
                "concept_score_percent": score_percent,
            }

        if status == "stable":
            return [
                action(
                    "transfer-quiz",
                    title=f"挑战「{concept}」变式题",
                    resource_type="quiz",
                    primary=True,
                    prompt=(
                        f"围绕知识点「{concept}」生成 2 道迁移应用题，难度略高于当前练习。"
                        "题目必须包含 concepts、knowledge_points、答案、解析、评分标准和常见误区。"
                    ),
                )
            ]

        return [
            action(
                "visual",
                title=f"补「{concept}」图解",
                resource_type="visual",
                primary=True,
                prompt=(
                    f"围绕知识点「{concept}」生成一张补基图解。"
                    "必须包含：概念定义、和当前任务的关系、最小例子、常见误区、三步纠正方法。"
                ),
            ),
            action(
                "quiz",
                title=f"做「{concept}」低门槛复测",
                resource_type="quiz",
                primary=False,
                prompt=(
                    f"围绕知识点「{concept}」生成 4 道低门槛复测题。"
                    "题型包含选择、判断、填空和简答；每题必须带 concepts、knowledge_points、答案、解析和错因提示。"
                ),
            ),
        ]

    @staticmethod
    def _coach_actions(
        current_task: LearningTask | None,
        loop_context: dict[str, Any],
        resource_shortcuts: list[dict[str, Any]],
        effect_assessment: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if current_task is None:
            return []

        mode = str(loop_context.get("mode") or "normal")
        cluster = loop_context.get("cluster")
        label = str(cluster.get("label") or current_task.title) if isinstance(cluster, dict) else current_task.title
        suggested = str(cluster.get("suggested_action") or "") if isinstance(cluster, dict) else ""
        target_id = current_task.task_id

        def action(
            suffix: str,
            *,
            title: str,
            resource_type: str,
            prompt: str,
            primary: bool = False,
        ) -> dict[str, Any]:
            return {
                "id": f"{target_id}-{suffix}",
                "action_type": "resource",
                "label": title,
                "title": title,
                "resource_type": resource_type,
                "target_task_id": target_id,
                "target_task_title": current_task.title,
                "prompt": prompt,
                "primary": primary,
            }

        if current_task.origin == "diagnostic_remediation":
            strategy_items = current_task.metadata.get("learning_strategy")
            strategy_actions: list[dict[str, Any]] = []
            if isinstance(strategy_items, list):
                for index, item in enumerate(strategy_items):
                    if not isinstance(item, dict):
                        continue
                    resource_type = str(item.get("resource_type") or "").strip()
                    if resource_type == "practice":
                        resource_type = "quiz"
                    if resource_type not in {"visual", "video", "external_video", "quiz", "research"}:
                        continue
                    phase = str(item.get("phase") or "前测策略").strip()
                    action_text = str(item.get("action") or "").strip()
                    success_check = str(item.get("success_check") or "").strip()
                    prompt = (
                        f"根据前测结果围绕「{current_task.title}」执行「{phase}」：{action_text} "
                        f"输出必须包含可验证标准：{success_check or '完成后能提交一条学习证据'}。"
                    )
                    strategy_actions.append(
                        action(
                            f"diagnostic-{index + 1}-{resource_type}",
                            title=f"前测策略：{phase}",
                            resource_type=resource_type,
                            primary=not strategy_actions,
                            prompt=prompt,
                        )
                    )
                    if len(strategy_actions) >= 2:
                        break
            if strategy_actions:
                return strategy_actions

        if mode == "remediation":
            return [
                action(
                    "remediation-visual",
                    title="生成补救图解",
                    resource_type="visual",
                    primary=True,
                    prompt=(
                        f"围绕「{label}」生成一张补救图解：先说明错因，再拆解关键概念、判断步骤、"
                        f"反例和一个修正后的最小例子。{f'建议动作：{suggested}' if suggested else ''}"
                    ),
                ),
                action(
                    "remediation-quiz",
                    title="生成纠错练习",
                    resource_type="quiz",
                    prompt=f"针对「{label}」生成 4 道由易到难的混合题，题型包含选择、判断、填空和简答；每题给出错因提示和解析。",
                ),
            ]

        if mode == "retest":
            return [
                action(
                    "retest-quiz",
                    title="生成复测题",
                    resource_type="quiz",
                    primary=True,
                    prompt=f"围绕「{label}」生成一组复测题，重点验证补救后的判断方法是否稳定；题型混合，要求给出答案、解析和通过标准。",
                )
            ]

        if mode in {"retest_failed", "review"}:
            return [
                action(
                    "review-visual",
                    title="重新拆解错因",
                    resource_type="visual",
                    primary=True,
                    prompt=f"复测或错因追踪仍未闭环。请把「{label}」重新拆成：错误表现、根因、正确判断条件、反例辨析和 3 步补救路径。",
                ),
                action(
                    "review-quiz",
                    title="生成同类复测",
                    resource_type="quiz",
                    prompt=f"围绕「{label}」生成 3 道同类复测题，专门暴露相同错因，并在解析里说明如何避免再次犯错。",
                ),
            ]

        if mode == "closed_loop":
            return [
                action(
                    "transfer-quiz",
                    title="生成迁移应用题",
                    resource_type="quiz",
                    primary=True,
                    prompt=f"围绕「{current_task.title}」生成 2 道迁移应用题，帮助确认错因闭环后能否把知识用到新场景。",
                )
            ]

        dimensions = {
            str(item.get("id") or ""): item
            for item in (effect_assessment or {}).get("dimensions") or []
            if isinstance(item, dict)
        }
        evidence_score = int(dict(dimensions.get("evidence") or {}).get("score") or 0)
        engagement_score = int(dict(dimensions.get("engagement") or {}).get("score") or 0)
        effect_score = int((effect_assessment or {}).get("score") or 0)
        if mode == "normal" and (effect_score < 50 or evidence_score < 50):
            return [
                action(
                    "evidence-quiz",
                    title="生成可评分练习",
                    resource_type="quiz",
                    primary=True,
                    prompt=(
                        f"围绕「{current_task.title}」生成一组可评分练习，题型包含选择、判断、填空和简答。"
                        "目标是快速产生学习证据，帮助判断当前掌握程度，并给出每题解析和错因标签。"
                    ),
                ),
                action(
                    "evidence-visual",
                    title="生成概念图解",
                    resource_type="visual",
                    prompt=f"围绕「{current_task.title}」生成一张极简概念图解，突出关键定义、判断条件、常见误区和一个最小例子。",
                ),
            ]
        if mode == "normal" and engagement_score < 50:
            return [
                action(
                    "engagement-visual",
                    title="生成上手图解",
                    resource_type="visual",
                    primary=True,
                    prompt=f"围绕「{current_task.title}」生成一张能帮助学生快速进入状态的图解，要求少文字、强结构、给出下一步动作。",
                )
            ]

        first = next(
            (
                item
                for item in resource_shortcuts
                if str(item.get("target_task_id") or "") == target_id and str(item.get("resource_type") or "")
            ),
            None,
        )
        if first:
            resource_type = str(first.get("resource_type") or "visual")
            return [
                action(
                    f"shortcut-{resource_type}",
                    title=str(first.get("title") or f"调用{GuideV2Manager._resource_label(resource_type)}智能体"),
                    resource_type=resource_type,
                    primary=True,
                    prompt=str(first.get("prompt") or f"围绕「{current_task.title}」生成适合当前学习阶段的资源。"),
                )
            ]
        return []

    @staticmethod
    def _coach_micro_plan(
        current_task: LearningTask | None,
        resource_shortcuts: list[dict[str, Any]],
        evaluation: dict[str, Any],
        loop_context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if current_task is None:
            return [
                {"step": 1, "title": "保存学习报告", "duration_minutes": 5, "action_type": "report"},
                {"step": 2, "title": "选择一个迁移场景复述核心知识", "duration_minutes": 12, "action_type": "transfer"},
                {"step": 3, "title": "整理课程产出包并补充作品集", "duration_minutes": 15, "action_type": "portfolio"},
            ]

        mode = str((loop_context or {}).get("mode") or "normal")
        cluster = (loop_context or {}).get("cluster")
        label = str(cluster.get("label") or "当前错因") if isinstance(cluster, dict) else "当前错因"
        if mode == "remediation":
            return [
                {
                    "step": 1,
                    "title": f"复盘错因：{label}",
                    "duration_minutes": 5,
                    "action_type": "resource",
                    "resource_type": "visual",
                    "target_task_id": current_task.task_id,
                },
                {
                    "step": 2,
                    "title": f"完成补救任务：{current_task.title}",
                    "duration_minutes": max(6, min(int(current_task.estimated_minutes or 10), 15)),
                    "action_type": "complete_remediation",
                },
                {
                    "step": 3,
                    "title": "提交纠错反思和掌握评分",
                    "duration_minutes": 4,
                    "action_type": "evidence",
                },
            ]
        if mode == "retest":
            return [
                {
                    "step": 1,
                    "title": f"快速回看补救结论：{label}",
                    "duration_minutes": 4,
                    "action_type": "review",
                },
                {
                    "step": 2,
                    "title": f"完成复测：{current_task.title}",
                    "duration_minutes": max(6, min(int(current_task.estimated_minutes or 8), 12)),
                    "action_type": "resource",
                    "resource_type": "quiz",
                    "target_task_id": current_task.task_id,
                },
                {
                    "step": 3,
                    "title": "若达到 75%，关闭错因并继续下一任务",
                    "duration_minutes": 3,
                    "action_type": "close_loop",
                },
            ]
        if mode == "retest_failed":
            return [
                {
                    "step": 1,
                    "title": f"生成或查看「{label}」的补救图解",
                    "duration_minutes": 6,
                    "action_type": "resource",
                    "resource_type": "visual",
                    "target_task_id": current_task.task_id,
                },
                {
                    "step": 2,
                    "title": "做 2 道同类反例辨析题",
                    "duration_minutes": 8,
                    "action_type": "resource",
                    "resource_type": "quiz",
                    "target_task_id": current_task.task_id,
                },
                {
                    "step": 3,
                    "title": "重新提交复测证据",
                    "duration_minutes": 4,
                    "action_type": "evidence",
                },
            ]

        plan = [
            {
                "step": 1,
                "title": f"阅读并复述：{current_task.title}",
                "duration_minutes": min(8, max(4, int(current_task.estimated_minutes or 8) // 2)),
                "action_type": "study",
            }
        ]
        if resource_shortcuts:
            first = resource_shortcuts[0]
            plan.append(
                {
                    "step": 2,
                    "title": f"调用{GuideV2Manager._resource_label(str(first.get('resource_type') or 'resource'))}智能体",
                    "duration_minutes": 6,
                    "action_type": "resource",
                    "resource_type": first.get("resource_type"),
                    "target_task_id": first.get("target_task_id"),
                }
            )
        else:
            plan.append(
                {
                    "step": 2,
                    "title": "用自己的话写出一个例子或反例",
                    "duration_minutes": 6,
                    "action_type": "example",
                }
            )
        plan.append(
            {
                "step": 3,
                "title": "提交掌握评分和一句话反思",
                "duration_minutes": 4,
                "action_type": "evidence",
            }
        )
        if int(evaluation.get("progress") or 0) >= 80:
            plan.append(
                {
                    "step": 4,
                    "title": "把本轮结果保存到 Notebook 或课程产出包",
                    "duration_minutes": 5,
                    "action_type": "save",
                }
            )
        return plan[:4]

    def _study_checkpoints(
        self,
        session: GuideSessionV2,
        blocks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        checkpoints: list[dict[str, Any]] = []
        evidence_by_task = {item.task_id: item for item in session.evidence}
        for block in blocks:
            task_ids = [str(item) for item in block.get("task_ids", [])]
            scores = [
                float(evidence_by_task[task_id].score)
                for task_id in task_ids
                if task_id in evidence_by_task and evidence_by_task[task_id].score is not None
            ]
            average_score = round(sum(scores) / len(scores), 3) if scores else None
            has_resource = any(
                len(task.artifact_refs) > 0
                for task in session.tasks
                if task.task_id in task_ids
            )
            met = block.get("status") == "completed" and (average_score is None or average_score >= 0.7)
            checkpoints.append(
                {
                    "id": f"checkpoint-{block.get('index')}",
                    "title": f"{block.get('title')} 复盘",
                    "trigger": f"完成 {block.get('total_tasks', 0)} 个任务后检查",
                    "status": "met" if met else "needs_review" if block.get("status") == "completed" else "pending",
                    "average_score": average_score,
                    "criteria": [
                        "能用自己的话解释本学习块的核心概念",
                        "至少完成一次练习或反思记录",
                        "若掌握分低于 0.75，先生成针对性图解或混合题再继续",
                    ],
                    "evidence": {
                        "task_count": len(task_ids),
                        "scored_count": len(scores),
                        "has_resource": has_resource,
                    },
                }
            )

        milestones = session.course_map.metadata.get("project_milestones")
        if isinstance(milestones, list):
            for index, raw in enumerate(milestones[:3], start=1):
                item = dict(raw) if isinstance(raw, dict) else {}
                checkpoints.append(
                    {
                        "id": f"milestone-{index}",
                        "title": str(item.get("stage") or f"项目里程碑 {index}"),
                        "trigger": str(item.get("artifact") or "形成阶段性产出"),
                        "status": "pending",
                        "average_score": None,
                        "criteria": [
                            str(item.get("artifact") or "提交一个可展示的学习产物"),
                            "说明本阶段用到了哪些知识点",
                        ],
                        "evidence": {"source": "course_template"},
                    }
                )
        return checkpoints

    @staticmethod
    def _study_block_title(session: GuideSessionV2, index: int, focus_node_id: str) -> str:
        horizon = (session.profile.horizon or "").lower()
        if horizon == "week":
            return f"第 {index} 天"
        if horizon in {"today", "short"}:
            return f"第 {index} 次学习"
        node_title = next(
            (node.title for node in session.course_map.nodes if node.node_id == focus_node_id),
            "",
        )
        return node_title or f"第 {index} 次学习"

    @staticmethod
    def _study_block_actions(tasks: list[LearningTask], status: str) -> list[str]:
        if not tasks:
            return []
        pending = [task for task in tasks if task.status not in {"completed", "skipped"}]
        target = pending[0] if pending else tasks[-1]
        actions = [
            f"先完成「{target.title}」，不要同时展开太多分支。",
            "完成后写一句反思，并给出 0-1 掌握评分。",
        ]
        if target.type in {"visualize", "visual"}:
            actions.insert(1, "如果概念抽象，先生成图解再完成任务。")
        elif target.type in {"practice", "quiz"}:
            actions.insert(1, "先做练习，再根据错因生成补救资源。")
        elif target.type == "project":
            actions.insert(1, "产出一段可保存到 Notebook 的项目说明。")
        if status == "completed":
            return ["回看本学习块证据，确认是否需要复盘薄弱点。"]
        return actions[:3]

    @staticmethod
    def _evidence_event_type(evidence_type: str) -> str:
        mapping = {
            "diagnostic": "diagnostic",
            "profile_dialogue": "profile_dialogue",
            "quiz": "quiz_evidence",
            "completion": "task_completed",
        }
        return mapping.get(evidence_type, "learning_evidence")

    @staticmethod
    def _evidence_event_title(
        evidence: LearningEvidence,
        task_titles: dict[str, str],
    ) -> str:
        if evidence.type == "diagnostic":
            label = str(evidence.metadata.get("readiness_label") or "diagnostic")
            return f"完成学习画像前测：{label}"
        if evidence.type == "profile_dialogue":
            return "通过对话更新学习画像"
        if evidence.type == "quiz":
            return f"练习结果回写：{task_titles.get(evidence.task_id, evidence.task_id)}"
        return f"完成任务：{task_titles.get(evidence.task_id, evidence.task_id)}"

    @staticmethod
    def _evidence_impact(evidence: LearningEvidence) -> str:
        if evidence.type == "diagnostic":
            return "准备度、薄弱点和资源偏好已更新。"
        if evidence.type == "profile_dialogue":
            return "自然语言画像已转化为路线调整信号。"
        if evidence.type == "quiz":
            return "练习分数已进入掌握度评估。"
        if evidence.score is not None and evidence.score < 0.65:
            return "低分证据可能触发补救任务。"
        if evidence.score is not None and evidence.score >= 0.85:
            return "高分证据可推动进入后续或迁移任务。"
        return "任务完成情况已进入学习评估。"

    @staticmethod
    def _timeline_type_label(event_type: str) -> str:
        labels = {
            "session_created": "路线创建",
            "task_inserted": "任务插入",
            "resource_generated": "资源生成",
            "quiz_attempt": "练习提交",
            "diagnostic": "前测诊断",
            "profile_dialogue": "画像对话",
            "quiz_evidence": "练习证据",
            "task_completed": "任务完成",
            "learning_evidence": "学习证据",
            "path_adjustment": "路径调整",
            "diagnostic_remediation": "前测补强",
            "diagnostic_profile_update": "前测更新",
            "profile_dialogue_focus": "画像补强",
            "profile_dialogue_update": "画像更新",
            "insert_remediation": "插入补救",
            "insert_transfer": "追加迁移",
            "skip_redundant": "跳过重复",
        }
        return labels.get(event_type, event_type or "事件")

    @staticmethod
    def _resource_label(resource_type: str) -> str:
        labels = {
            "visual": "图解",
            "video": "短视频",
            "external_video": "精选视频",
            "quiz": "练习",
            "research": "资料",
        }
        return labels.get(resource_type, resource_type or "资源")

    def _build_session_recommendations(self, session: GuideSessionV2) -> list[str]:
        """Build evidence-aware next-step guidance for the learner cockpit."""

        recommendations: list[str] = []
        memory_payload = (
            session.course_map.metadata.get("learner_memory")
            if isinstance(session.course_map.metadata.get("learner_memory"), dict)
            else {}
        )
        if memory_payload:
            weak_points = [str(item) for item in memory_payload.get("known_weak_points") or [] if str(item).strip()]
            common_mistakes = [str(item) for item in memory_payload.get("common_mistakes") or [] if str(item).strip()]
            preferred_resources = [
                str(item) for item in memory_payload.get("preferred_resources") or [] if str(item).strip()
            ]
            focus = weak_points[0] if weak_points else common_mistakes[0] if common_mistakes else ""
            resource_hint = f"，优先使用{preferred_resources[0]}资源" if preferred_resources else ""
            if focus:
                recommendations.append(f"已继承长期学习画像：先校准「{focus}」{resource_hint}，再推进新路线。")
            else:
                recommendations.append(f"已继承长期学习画像{resource_hint}，本轮路线会参考历史证据动态调整。")
        current = self._current_task(session)
        if current:
            recommendations.append(
                f"继续当前任务：{current.title}。先完成任务，再用一句反思和 0-1 掌握分留下学习证据。"
            )

        latest_evidence = max(session.evidence, key=lambda item: item.created_at, default=None)
        if latest_evidence is None:
            recommendations.append("先完成第一个任务，系统需要至少一条学习证据来判断真实掌握情况。")
        elif latest_evidence.score is not None and latest_evidence.score < 0.75:
            task_title = next(
                (task.title for task in session.tasks if task.task_id == latest_evidence.task_id),
                "刚完成的任务",
            )
            recommendations.append(f"回看低分任务「{task_title}」，生成图解或例题后再做一次小测。")
        elif latest_evidence.score is not None and latest_evidence.score >= 0.85:
            recommendations.append("最近一次证据表现不错，可以进入下一任务，并尝试加入迁移应用题。")

        weak_nodes = [
            node.title
            for node in session.course_map.nodes
            if session.mastery.get(node.node_id, MasteryState(node_id=node.node_id)).status == "needs_support"
        ]
        if weak_nodes:
            recommendations.append(f"优先补强薄弱知识点：{weak_nodes[0]}。建议先图解，再练习。")

        resource_counts = self._resource_counts(session)
        if resource_counts.get("quiz", 0) == 0:
            recommendations.append("还没有形成练习闭环，建议立刻生成一组混合题。")
        elif resource_counts.get("visual", 0) == 0:
            recommendations.append("已有练习后补一张概念图，帮助把错题原因归到知识结构上。")

        if self._progress(session) >= 100:
            recommendations.append("路径已完成，下一步可生成总结资料并把关键题目保存到题目本。")

        deduped: list[str] = []
        for item in recommendations:
            if item and item not in deduped:
                deduped.append(item)
        return deduped[:4]

    def _report_summary(self, session: GuideSessionV2, evaluation: dict[str, Any]) -> str:
        progress = int(evaluation.get("progress") or 0)
        score = int(evaluation.get("overall_score") or 0)
        risks = [str(item) for item in evaluation.get("risk_signals", []) if str(item).strip()]
        strengths = [str(item) for item in evaluation.get("strengths", []) if str(item).strip()]
        if progress <= 0:
            return "尚未形成学习证据。建议先完成第一个导学任务，系统会根据掌握分、反思和资源使用情况动态调整路径。"
        if risks:
            return f"当前综合掌握分为 {score}，主要风险是：{risks[0]}。建议先完成补救任务或生成针对性图解/练习。"
        if score >= 80:
            lead = strengths[0] if strengths else "学习路径推进稳定"
            return f"当前综合掌握分为 {score}，{lead}。可以进入迁移应用或课程项目阶段。"
        return f"当前综合掌握分为 {score}，已经形成初步学习证据，但仍需要通过练习、错因反思和资源复用继续巩固。"

    def _report_node_cards(self, session: GuideSessionV2) -> list[dict[str, Any]]:
        cards: list[dict[str, Any]] = []
        for node in session.course_map.nodes:
            node_tasks = [task for task in session.tasks if task.node_id == node.node_id]
            completed = sum(1 for task in node_tasks if task.status == "completed")
            artifacts = sum(len(task.artifact_refs) for task in node_tasks)
            state = session.mastery.get(node.node_id, MasteryState(node_id=node.node_id))
            cards.append(
                {
                    "node_id": node.node_id,
                    "title": node.title,
                    "status": state.status,
                    "mastery_score": state.score,
                    "completed_tasks": completed,
                    "total_tasks": len(node_tasks),
                    "artifact_count": artifacts,
                    "difficulty": node.difficulty,
                    "mastery_target": node.mastery_target,
                    "suggestion": self._node_report_suggestion(
                        status=state.status,
                        score=state.score,
                        artifact_count=artifacts,
                        completed_tasks=completed,
                        total_tasks=len(node_tasks),
                    ),
                }
            )
        return cards

    @staticmethod
    def _node_report_suggestion(
        *,
        status: str,
        score: float,
        artifact_count: int,
        completed_tasks: int,
        total_tasks: int,
    ) -> str:
        if status == "needs_support" or score < 0.45:
            return "优先补救：先生成图解或例题拆解，再用混合题复测。"
        if total_tasks and completed_tasks >= total_tasks and score >= 0.8:
            return "掌握稳定：适合进入迁移应用或项目化输出。"
        if artifact_count == 0:
            return "资源不足：建议生成一个可视化或练习资源，补齐学习证据。"
        if completed_tasks == 0:
            return "尚未开始：先完成该知识点的最小任务，留下反思证据。"
        return "继续巩固：完成剩余任务，并记录错因或关键收获。"

    @staticmethod
    def _report_action_brief(
        *,
        session: GuideSessionV2,
        evaluation: dict[str, Any],
        overview: dict[str, Any],
        effect_assessment: dict[str, Any],
        feedback_digest: dict[str, Any],
        mistake_payload: dict[str, Any],
        node_cards: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Compress the report into one learner-facing next action."""

        progress = int(overview.get("progress") or 0)
        overall_score = int(overview.get("overall_score") or 0)
        effect_score = int(effect_assessment.get("score") or overall_score)
        completed = int(overview.get("completed_tasks") or 0)
        total = int(overview.get("total_tasks") or 0)
        evidence_count = int((evaluation.get("evidence_count") or completed) or 0)
        latest_feedback = dict(feedback_digest.get("latest") or {})
        latest_score = latest_feedback.get("score_percent")
        warning_count = int(feedback_digest.get("warning_count") or 0)
        mistake_summary = dict(mistake_payload.get("summary") or {})
        pending_remediation = int(mistake_summary.get("pending_remediation_count") or 0)
        clusters = [item for item in mistake_payload.get("clusters") or [] if isinstance(item, dict)]
        weak_cluster = clusters[0] if clusters else {}
        weak_node = next(
            (
                item
                for item in node_cards
                if str(item.get("status") or "") == "needs_support"
                or float(item.get("mastery_score") or 0) < 0.65
            ),
            {},
        )
        current = GuideV2Manager._current_task(session)
        weak_label = (
            str(weak_cluster.get("label") or "").strip()
            or str(weak_node.get("title") or "").strip()
            or (session.profile.weak_points[0] if session.profile.weak_points else "")
        )
        last_evidence = max(session.evidence, key=lambda item: item.created_at, default=None)
        target_task = current
        if target_task is None and last_evidence is not None:
            target_task = next((task for task in session.tasks if task.task_id == last_evidence.task_id), None)
        if target_task is None and weak_node.get("node_id"):
            target_task = GuideV2Manager._task_for_node(session, str(weak_node.get("node_id") or ""))
        if target_task is None and session.tasks:
            target_task = session.tasks[-1]

        signals: list[dict[str, Any]] = [
            {"label": "综合掌握", "value": f"{overall_score} 分", "tone": GuideV2Manager._report_signal_tone(overall_score)},
            {"label": "学习进度", "value": f"{completed}/{total} 个任务", "tone": "brand" if progress else "neutral"},
        ]
        if weak_label:
            signals.append({"label": "优先卡点", "value": weak_label, "tone": "warning"})
        if latest_score is not None:
            signals.append(
                {
                    "label": "最近反馈",
                    "value": f"{round(float(latest_score))} 分",
                    "tone": GuideV2Manager._report_signal_tone(float(latest_score)),
                }
            )

        preferences = {str(item).strip().lower() for item in session.profile.preferences if str(item).strip()}
        prefers_external_video = GuideV2Manager._prefers_external_video(preferences)
        secondary: list[dict[str, str]] = []

        def resource_for(kind: str) -> str:
            if kind in {"quiz", "retest", "transfer"}:
                return "quiz"
            if kind in {"remediate", "visual"}:
                return "visual"
            if kind == "video":
                return "video"
            if kind == "external_video":
                return "external_video"
            return ""

        def action(label: str, detail: str, kind: str) -> dict[str, str]:
            payload = {"label": label, "detail": detail, "kind": kind}
            resource_type = resource_for(kind)
            if resource_type and target_task is not None:
                topic = weak_label or target_task.title or session.goal
                payload["target_task_id"] = target_task.task_id
                payload["resource_type"] = resource_type
                if kind == "retest":
                    payload["prompt"] = f"围绕「{topic}」生成一组低门槛复测题，包含选择题、判断题和1道简答题。"
                elif kind == "transfer":
                    payload["prompt"] = f"围绕「{topic}」生成一组迁移应用练习，题目要换一个新场景验证理解。"
                elif kind == "remediate":
                    payload["prompt"] = f"围绕「{topic}」生成一份补救图解，重点解释概念边界、常见错因和正确步骤。"
                elif kind == "visual":
                    payload["prompt"] = f"围绕「{topic}」生成一张概念图解，突出关键关系和学习顺序。"
                elif kind == "external_video":
                    payload["prompt"] = f"围绕「{topic}」筛选 2-3 个公开视频或公开课片段，说明每个视频适合解决哪个卡点。"
                else:
                    payload["prompt"] = f"围绕「{topic}」生成一组混合题型练习，提交后可用于评估掌握情况。"
            return payload

        if evidence_count == 0 or progress == 0:
            title = "先拿到第一条真实学习证据"
            summary = "现在还不能急着评价掌握程度，先完成一个可评分小任务，让系统知道你真实卡在哪里。"
            primary = action(
                "完成第一个任务",
                current.title if current else "选择路线中的第一个任务，完成后提交掌握评分和一句反思。",
                "current_task",
            )
            secondary.extend(
                [
                    action("做一组短练习", "用选择、判断或填空题快速产生可评分证据。", "quiz"),
                    action("看路线结构", "如果不知道从哪开始，先打开完整路线确认学习顺序。", "route_map"),
                ]
            )
        elif pending_remediation or warning_count or (latest_score is not None and float(latest_score) < 60):
            focus = weak_label or "刚暴露出来的错因"
            title = f"先补「{focus}」"
            summary = "这轮学习最怕继续往前冲。先把错因补清楚，再用复测确认它真的被改掉。"
            primary = action("生成补救图解", f"围绕「{focus}」生成一张图解或短讲解，先把概念边界讲清楚。", "remediate")
            secondary.extend(
                [
                    action("做一轮复测", "补完后立即做一组短题，确认不是只是看懂。", "retest"),
                    action(
                        "找讲解视频" if prefers_external_video else "回看完整路线",
                        "筛选少量公开视频，换一种讲法补清卡点。" if prefers_external_video else "确认系统插入的补救任务和后续任务顺序。",
                        "external_video" if prefers_external_video else "route_map",
                    ),
                ]
            )
        elif effect_score >= 80 and progress >= 70:
            title = "进入迁移应用"
            summary = "当前证据已经比较稳定，下一步应该把理解转成产出，而不是继续重复基础讲解。"
            primary = action("做课程小项目", "选择一个新场景，用本轮知识解释、计算或实现一个小成果。", "course_package")
            secondary.extend(
                [
                    action("保存学习报告", "把这轮掌握证据沉淀到 Notebook，作为比赛演示和复盘材料。", "save_report"),
                    action("做一组迁移题", "用不同题面验证知识能不能迁移。", "transfer"),
                ]
            )
        elif effect_score >= 60:
            title = "稳一下再推进"
            summary = "你已经有基础，但还不够稳。先用一轮短练习确认关键点，再进入下一步更保险。"
            primary = action(
                "做一组短练习",
                f"优先围绕「{weak_label}」做混合题。" if weak_label else "围绕当前任务做一组混合题。",
                "quiz",
            )
            secondary.extend(
                [
                    action(
                        "找参考视频" if prefers_external_video else "看一张概念图",
                        "用公开视频换一个讲解视角，再回到短练习确认。" if prefers_external_video else "如果做题前仍不确定，先用图解把关系理顺。",
                        "external_video" if prefers_external_video else "visual",
                    ),
                    action("继续当前路线", current.title if current else "回到路线页继续下一个任务。", "current_task"),
                ]
            )
        else:
            title = "先重新建立直观理解"
            summary = "当前掌握还比较松散，最需要的是降低理解门槛，而不是增加任务数量。"
            primary = action(
                "找精选公开视频" if prefers_external_video else "看图解或短视频",
                (
                    f"先围绕「{weak_label}」找 2-3 个公开视频，换一种讲法建立直觉。"
                    if weak_label and prefers_external_video
                    else "先找少量公开视频建立直觉，再回到练习验证。"
                    if prefers_external_video
                    else f"先围绕「{weak_label}」建立直观理解。"
                    if weak_label
                    else "先把当前知识点讲清楚。"
                ),
                "external_video" if prefers_external_video else "visual",
            )
            secondary.extend(
                [
                    action("补一条反思", "写清楚哪里不懂，帮助画像更新得更准。", "reflection"),
                    action("做低门槛复测", "用判断题和选择题确认基础概念。", "retest"),
                ]
            )

        return {
            "title": title,
            "summary": summary,
            "primary_action": primary,
            "secondary_actions": secondary[:2],
            "signals": signals[:4],
        }

    @staticmethod
    def _report_signal_tone(score: float) -> str:
        if score >= 80:
            return "success"
        if score >= 60:
            return "brand"
        if score > 0:
            return "warning"
        return "neutral"

    @staticmethod
    def _report_demo_readiness(
        *,
        session: GuideSessionV2,
        evaluation: dict[str, Any],
        overview: dict[str, Any],
        behavior_summary: dict[str, Any],
        resource_summary: dict[str, Any],
        feedback_digest: dict[str, Any],
        action_brief: dict[str, Any],
    ) -> dict[str, Any]:
        """Judge whether this guide session is ready for a short competition demo."""

        profile_context = dict(evaluation.get("learner_profile_context") or {})
        profile_updates = int(behavior_summary.get("profile_update_count") or 0)
        evidence_count = int(behavior_summary.get("evidence_count") or evaluation.get("evidence_count") or 0)
        resource_count = int(behavior_summary.get("resource_count") or 0)
        quiz_attempts = int(behavior_summary.get("quiz_attempt_count") or 0)
        completed = int(overview.get("completed_tasks") or 0)
        progress = int(overview.get("progress") or 0)
        feedback_count = int(feedback_digest.get("count") or 0)
        has_profile_signal = bool(profile_updates or profile_context or session.profile.preferences or session.profile.weak_points)
        has_visual_resource = bool(
            resource_summary.get("visual")
            or resource_summary.get("video")
            or resource_summary.get("animation")
            or resource_count >= 2
        )
        has_quiz_loop = bool(resource_summary.get("quiz") or quiz_attempts)
        has_report_action = bool((action_brief.get("primary_action") or {}).get("label"))
        has_portfolio = bool(any(task.artifact_refs for task in session.tasks) or completed)

        checks: list[dict[str, str]] = [
            {
                "id": "profile",
                "label": "画像证据",
                "status": "ready" if has_profile_signal else "missing",
                "detail": "已有画像、前测或对话证据。" if has_profile_signal else "先完成一次画像对话或前测，让系统有个性化依据。",
            },
            {
                "id": "resource",
                "label": "多模态资源",
                "status": "ready" if has_visual_resource else ("partial" if resource_count else "missing"),
                "detail": "已有图解、动画或多种资源产物。" if has_visual_resource else "建议至少生成一份图解或短视频，体现多智能体资源生成。",
            },
            {
                "id": "practice",
                "label": "练习闭环",
                "status": "ready" if has_quiz_loop else "missing",
                "detail": "已有交互练习或答题回写。" if has_quiz_loop else "补一组选择/判断/填空练习，并提交结果回写画像。",
            },
            {
                "id": "prescription",
                "label": "学习处方",
                "status": "ready" if has_report_action and feedback_count else ("partial" if has_report_action else "missing"),
                "detail": "报告已能给出下一步处方，并有反馈依据。" if has_report_action and feedback_count else "完成任务提交后，让报告产出可执行的学习处方。",
            },
            {
                "id": "portfolio",
                "label": "可展示产物",
                "status": "ready" if has_portfolio and progress >= 30 else ("partial" if has_portfolio else "missing"),
                "detail": "已有可保存到 Notebook 的任务证据或产物。" if has_portfolio else "至少保留一份资源、练习记录或报告，作为录屏兜底材料。",
            },
        ]

        weights = {"ready": 20, "partial": 10, "missing": 0}
        score = sum(weights.get(item["status"], 0) for item in checks)
        if progress >= 70 and score >= 70:
            label = "可录屏"
            summary = "核心证据已经成链，可以录制画像、导学、资源、练习和报告的完整闭环。"
        elif score >= 50:
            label = "演示准备中"
            summary = "主线已经成型，再补齐缺口证据后更适合录制 7 分钟演示。"
        else:
            label = "需要补齐"
            summary = "目前还缺少关键学习证据，建议先跑通一次画像、资源生成和练习提交。"

        next_steps: list[str] = []
        if not has_profile_signal:
            next_steps.append("先做画像对话或前测诊断。")
        if not has_visual_resource:
            next_steps.append("围绕当前任务生成一份图解或短视频。")
        if not has_quiz_loop:
            next_steps.append("生成一组交互练习并提交答案。")
        if not has_report_action:
            next_steps.append("完成任务后刷新学习报告，确认学习处方出现。")
        if not has_portfolio:
            next_steps.append("保存一份报告或资源到 Notebook 作为演示证据。")
        if not next_steps:
            next_steps.append("按演示脚本串联画像、任务、资源、练习、报告和产出包。")

        return {
            "score": max(0, min(score, 100)),
            "label": label,
            "summary": summary,
            "checks": checks,
            "next_steps": next_steps[:3],
        }

    def _report_demo_script(self, session: GuideSessionV2, evaluation: dict[str, Any]) -> list[str]:
        current = self._current_task(session)
        script = [
            f"学习目标：{session.goal}",
            f"当前进度：{evaluation.get('completed_tasks', 0)}/{evaluation.get('total_tasks', 0)} 个任务，综合掌握分 {evaluation.get('overall_score', 0)}。",
        ]
        if current:
            script.append(f"下一步任务：{current.title}")
        if session.plan_events:
            script.append(f"系统已根据学习证据自动调整路径 {len(session.plan_events)} 次。")
        else:
            script.append("系统将在产生学习证据后自动判断是否需要补救、跳过或增加迁移挑战。")
        return script

    @staticmethod
    def _report_markdown(report: dict[str, Any]) -> str:
        overview = dict(report.get("overview") or {})
        effect_assessment = dict(report.get("effect_assessment") or {})
        effect_dimensions = [item for item in effect_assessment.get("dimensions") or [] if isinstance(item, dict)]
        profile = dict(report.get("profile") or {})
        resource_summary = dict(report.get("resource_summary") or {})
        behavior_summary = dict(report.get("behavior_summary") or {})
        behavior_tags = [str(item) for item in report.get("behavior_tags") or []]
        feedback_digest = dict(report.get("feedback_digest") or {})
        feedback_items = [item for item in feedback_digest.get("items") or [] if isinstance(item, dict)]
        action_brief = dict(report.get("action_brief") or {})
        primary_action = dict(action_brief.get("primary_action") or {})
        secondary_actions = [item for item in action_brief.get("secondary_actions") or [] if isinstance(item, dict)]
        action_signals = [item for item in action_brief.get("signals") or [] if isinstance(item, dict)]
        demo_readiness = dict(report.get("demo_readiness") or {})
        demo_checks = [item for item in demo_readiness.get("checks") or [] if isinstance(item, dict)]
        demo_next_steps = [str(item) for item in demo_readiness.get("next_steps") or []]
        timeline_events = [item for item in report.get("timeline_events") or [] if isinstance(item, dict)]
        mistake_review = dict(report.get("mistake_review") or {})
        mistake_summary = dict(mistake_review.get("summary") or {})
        mistake_clusters = [item for item in mistake_review.get("clusters") or [] if isinstance(item, dict)]
        retest_plan = [item for item in mistake_review.get("retest_plan") or [] if isinstance(item, dict)]
        lines = [
            f"# {report.get('title') or '学习效果报告'}",
            "",
            f"> {report.get('summary') or ''}",
            "",
            "## 总览",
            "",
            f"- 综合掌握分：{overview.get('overall_score', 0)}",
            f"- 就绪状态：{overview.get('readiness', 'not_started')}",
            f"- 任务进度：{overview.get('completed_tasks', 0)}/{overview.get('total_tasks', 0)}，进度 {overview.get('progress', 0)}%",
            f"- 路径动态调整：{overview.get('path_adjustment_count', 0)} 次",
            f"- 平均证据分：{round(float(overview.get('average_evidence_score') or 0) * 100)}%",
            f"- 平均掌握度：{round(float(overview.get('average_mastery') or 0) * 100)}%",
            "",
            "## 学习效果评估",
            "",
            f"- 评估结论：{effect_assessment.get('label') or '-'}",
            f"- 效果评分：{effect_assessment.get('score', 0)}",
            f"- 评估说明：{effect_assessment.get('summary') or '-'}",
        ]
        for dimension in effect_dimensions[:5]:
            lines.append(
                f"- {dimension.get('label') or dimension.get('id')}: {dimension.get('score', 0)}"
                f"（{dimension.get('status') or '-'}）- {dimension.get('evidence') or '-'}"
            )
        for item in effect_assessment.get("strategy_adjustments") or []:
            lines.append(f"- 策略调整：{item}")
        if action_brief:
            lines.extend(["", "## 学习处方", ""])
            lines.append(f"- 先做：{action_brief.get('title') or '-'}")
            lines.append(f"- 原因：{action_brief.get('summary') or '-'}")
            if primary_action:
                lines.append(
                    f"- 立即行动：{primary_action.get('label') or '-'} - {primary_action.get('detail') or '-'}"
                )
            for item in secondary_actions[:2]:
                lines.append(f"- 备选：{item.get('label') or '-'} - {item.get('detail') or '-'}")
            if action_signals:
                signal_text = "；".join(
                    f"{item.get('label') or '-'}：{item.get('value') or '-'}" for item in action_signals[:4]
                )
                lines.append(f"- 依据：{signal_text}")
        if demo_readiness:
            lines.extend(["", "## 演示就绪度", ""])
            lines.append(f"- 状态：{demo_readiness.get('label') or '-'}")
            lines.append(f"- 分数：{demo_readiness.get('score', 0)}")
            lines.append(f"- 说明：{demo_readiness.get('summary') or '-'}")
            for item in demo_checks[:5]:
                lines.append(
                    f"- {item.get('label') or item.get('id') or '-'}：{item.get('status') or '-'} - {item.get('detail') or '-'}"
                )
            for item in demo_next_steps[:3]:
                lines.append(f"- 补齐动作：{item}")
        lines.extend(
            [
            "",
            "## 学习画像",
            "",
            f"- 水平：{profile.get('level') or 'unknown'}",
            f"- 时间预算：{profile.get('time_budget_minutes') or '-'} 分钟",
            f"- 偏好：{', '.join(profile.get('preferences') or []) or '-'}",
            f"- 薄弱点：{', '.join(profile.get('weak_points') or []) or '-'}",
            "",
            "## 知识点掌握",
            "",
            ]
        )
        for node in list(report.get("node_cards") or [])[:8]:
            if not isinstance(node, dict):
                continue
            lines.extend(
                [
                    f"### {node.get('title') or node.get('node_id')}",
                    "",
                    f"- 状态：{node.get('status', 'not_started')}，掌握度 {round(float(node.get('mastery_score') or 0) * 100)}%",
                    f"- 任务：{node.get('completed_tasks', 0)}/{node.get('total_tasks', 0)}，资源 {node.get('artifact_count', 0)} 个",
                    f"- 建议：{node.get('suggestion') or '-'}",
                    "",
                ]
            )
        lines.extend(["## 资源与证据", ""])
        if resource_summary:
            for key, value in sorted(resource_summary.items()):
                lines.append(f"- {key}: {value}")
        else:
            lines.append("- 暂无生成资源")
        evidence_summary = dict(report.get("evidence_summary") or {})
        lines.extend(
            [
                f"- 学习证据：{evidence_summary.get('count', 0)} 条",
                f"- 最新反思：{evidence_summary.get('latest_reflection') or '-'}",
                "",
                "## 风险与下一步",
                "",
            ]
        )
        for risk in report.get("risks") or []:
            lines.append(f"- 风险：{risk}")
        if not report.get("risks"):
            lines.append("- 当前没有明显风险信号")
        for action in report.get("next_plan") or []:
            lines.append(f"- 下一步：{action}")
        lines.extend(["", "## 学习行为证据", ""])
        lines.extend(
            [
                f"- 行为事件：{behavior_summary.get('event_count', 0)} 条",
                f"- 学习证据：{behavior_summary.get('evidence_count', 0)} 条",
                f"- 资源生成：{behavior_summary.get('resource_count', 0)} 个",
                f"- 练习提交：{behavior_summary.get('quiz_attempt_count', 0)} 次",
                f"- 画像/诊断更新：{behavior_summary.get('profile_update_count', 0)} 次",
                f"- 行为标签：{', '.join(behavior_tags) if behavior_tags else '-'}",
            ]
        )
        if timeline_events:
            lines.append("- 最近轨迹：")
            for event in timeline_events[:5]:
                label = event.get("label") or event.get("type") or "event"
                title = event.get("title") or event.get("description") or "-"
                score = event.get("score")
                score_text = f"，得分 {round(float(score) * 100)}%" if score is not None else ""
                lines.append(f"  - {label}：{title}{score_text}")
        lines.extend(["", "## 即时反馈摘要", ""])
        lines.extend(
            [
                f"- 反馈次数：{feedback_digest.get('count', 0)} 次",
                f"- 稳定反馈：{feedback_digest.get('success_count', 0)} 次",
                f"- 需干预反馈：{feedback_digest.get('warning_count', 0)} 次",
            ]
        )
        if feedback_items:
            lines.append("- 代表性反馈：")
            for item in feedback_items[:4]:
                lines.append(f"  - {item.get('title') or '-'}：{item.get('summary') or '-'}")
        else:
            lines.append("- 暂无即时反馈")
        lines.extend(["", "## 错因与复测闭环", ""])
        lines.extend(
            [
                f"- 错因类别：{mistake_summary.get('cluster_count', 0)} 类",
                f"- 低分证据：{mistake_summary.get('low_score_evidence_count', 0)} 条",
                f"- 待补救任务：{mistake_summary.get('pending_remediation_count', 0)} 个",
                f"- 待复测任务：{mistake_summary.get('pending_retest_count', 0)} 个",
            ]
        )
        for cluster in mistake_clusters[:4]:
            lines.append(f"- 错因：{cluster.get('label') or '-'}；建议：{cluster.get('suggested_action') or '-'}")
        for step in retest_plan[:3]:
            lines.append(f"- 复测计划 {step.get('step') or '-'}：{step.get('title') or '-'}")
        lines.extend(["", "## 演示讲稿提示", ""])
        for item in report.get("demo_script") or []:
            lines.append(f"- {item}")
        return "\n".join(lines).strip() + "\n"

    def _course_package_summary(self, session: GuideSessionV2, evaluation: dict[str, Any]) -> str:
        progress = int(evaluation.get("progress") or 0)
        score = int(evaluation.get("overall_score") or 0)
        if progress >= 80 and score >= 75:
            return "已具备进入课程项目展示的基础，可围绕核心知识点完成一个可复盘、可评分、可演示的学习产出。"
        if progress > 0:
            return "已形成部分学习证据，课程产出包将把剩余学习任务和项目交付绑定起来，帮助继续推进闭环。"
        return "课程产出包已预生成。建议先完成导学任务和练习，再用真实学习证据更新最终项目要求。"

    @staticmethod
    def _course_learning_style(
        *,
        session: GuideSessionV2,
        evaluation: dict[str, Any],
        report: dict[str, Any],
    ) -> dict[str, Any]:
        preferences = [str(item) for item in (session.profile.preferences or []) if str(item).strip()]
        weak_points = [str(item) for item in (session.profile.weak_points or []) if str(item).strip()]
        behavior = dict(report.get("behavior_summary") or {})
        score = int(evaluation.get("overall_score") or 0)
        progress = int(evaluation.get("progress") or 0)
        completed = int(evaluation.get("completed_tasks") or 0)
        quiz_attempts = int(behavior.get("quiz_attempt_count") or 0)
        resource_count = int(behavior.get("resource_count") or 0)
        profile_updates = int(behavior.get("profile_update_count") or 0)

        joined_preferences = " ".join(preferences).lower()
        prefers_practice = bool(re.search(r"练习|题|practice|quiz", joined_preferences))
        prefers_visual = bool(re.search(r"图解|图|visual|diagram", joined_preferences))
        prefers_video = bool(re.search(r"视频|video|动画|manim", joined_preferences))

        label = "渐进压实型"
        summary = "学习路线会先保住核心理解，再通过资源、练习和反思逐步压实。"
        if prefers_practice and quiz_attempts > 0:
            label = "练习驱动型"
            summary = "课程产出包会把练习证据和错因复盘放在更突出的位置，用可评分任务证明掌握过程。"
        elif prefers_visual and weak_points:
            label = "概念澄清型"
            summary = "课程产出包会优先展示图解、知识地图和关键概念边界，让评委看到系统如何降低理解门槛。"
        elif prefers_video and score >= 60:
            label = "快速串联型"
            summary = "课程产出包会用短视频、分步讲解或录屏脚本串起主线，再回到练习和报告确认效果。"
        elif profile_updates >= 2 or score < 55:
            label = "反复校准型"
            summary = "课程产出包会强调画像修正、反馈证据和学习处方，说明系统如何边学边调整。"

        if progress >= 70 and score >= 70:
            trend = "最近证据已经比较稳定，可以在演示中稍微加快节奏。"
        elif completed or resource_count or quiz_attempts:
            trend = "已经形成部分学习证据，适合展示从任务到资源再到反馈的闭环。"
        else:
            trend = "证据仍在起步阶段，演示时应优先跑通一次画像、资源和练习提交。"

        signals = [
            {"label": "偏好", "value": "、".join(preferences[:2]) if preferences else "继续观察"},
            {"label": "卡点", "value": "、".join(weak_points[:2]) if weak_points else "暂无明显堆积"},
            {"label": "证据", "value": f"{completed} 个任务 / {resource_count} 个资源 / {quiz_attempts} 次练习"},
        ]

        return {
            "label": label,
            "summary": summary,
            "trend": trend,
            "signals": signals,
            "demo_talking_point": f"这条课程 Demo 会按「{label}」组织产物，说明画像不是静态标签，而是在影响资源顺序、练习安排和学习报告。",
            "path_effect": "画像先影响当前任务，再影响资源类型和练习反馈，最后进入课程产出包。",
        }

    def _capstone_project(self, session: GuideSessionV2, evaluation: dict[str, Any]) -> dict[str, Any]:
        nodes = session.course_map.nodes
        topic = session.course_map.title or self._short_title(session.goal)
        weak_points = list(session.profile.weak_points or [])
        focus_nodes = [
            node.title
            for node in nodes
            if session.mastery.get(node.node_id, MasteryState(node_id=node.node_id)).status != "mastered"
        ][:3]
        if not focus_nodes:
            focus_nodes = [node.title for node in nodes[:3]]
        scenario = (
            f"围绕「{topic}」设计一个端到端学习成果：说明问题背景、拆解关键概念、完成代表性练习，"
            "并用图解、短视频或题目结果证明自己的掌握过程。"
        )
        if weak_points:
            scenario += f" 项目中必须回应薄弱点：{weak_points[0]}。"
        return {
            "title": f"{topic} 学习成果项目",
            "scenario": scenario,
            "deliverables": [
                "一页知识结构图或概念关系图",
                "一份 800-1200 字学习说明，解释关键概念、常见误区和个人理解",
                "一组混合练习题的作答记录与错因复盘",
                "一个 3 分钟以内的讲解脚本或短视频素材说明",
            ],
            "steps": [
                "选定 2-3 个核心知识点，写出它们之间的因果或依赖关系。",
                "用一个具体例子演示知识点如何解决问题。",
                "完成练习并记录正确率、错因和修正后的理解。",
                "把图解、练习、反思整理成可展示的课程作品。",
            ],
            "focus_nodes": focus_nodes,
            "estimated_minutes": max(45, min(120, int(evaluation.get("total_tasks") or 4) * 12)),
        }

    @staticmethod
    def _course_rubric(session: GuideSessionV2, evaluation: dict[str, Any]) -> list[dict[str, Any]]:
        progress = int(evaluation.get("progress") or 0)
        practice_weight = 25 if progress < 60 else 20
        return [
            {
                "criterion": "知识结构完整性",
                "weight": 25,
                "excellent": "能说明核心概念、先修关系、应用边界和常见误区。",
                "baseline": "能列出主要概念并给出基本解释。",
            },
            {
                "criterion": "问题解决与迁移",
                "weight": 25,
                "excellent": "能把知识点迁移到新场景，并解释每一步决策依据。",
                "baseline": "能完成一个同类型例题或任务。",
            },
            {
                "criterion": "练习证据与错因复盘",
                "weight": practice_weight,
                "excellent": "练习结果、错因、修正策略完整，能体现学习进步。",
                "baseline": "至少有一组练习记录和基本答案解析。",
            },
            {
                "criterion": "多模态表达",
                "weight": 15,
                "excellent": "图解、动画、文字说明相互补充，表达清晰。",
                "baseline": "至少包含一种可视化或讲解材料。",
            },
            {
                "criterion": "自我评估与下一步计划",
                "weight": 10,
                "excellent": "能结合学习报告提出具体后续计划。",
                "baseline": "能说明当前掌握情况和一个后续行动。",
            },
        ]

    @staticmethod
    def _course_portfolio(session: GuideSessionV2) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        task_lookup = {task.task_id: task for task in session.tasks}
        for task in session.tasks:
            for artifact in task.artifact_refs:
                if not isinstance(artifact, dict):
                    continue
                result = artifact.get("result") if isinstance(artifact.get("result"), dict) else {}
                items.append(
                    {
                        "artifact_id": str(artifact.get("id") or ""),
                        "task_id": task.task_id,
                        "task_title": task_lookup.get(task.task_id, task).title,
                        "type": str(artifact.get("type") or ""),
                        "capability": str(artifact.get("capability") or ""),
                        "title": str(artifact.get("title") or task.title),
                        "status": str(artifact.get("status") or "ready"),
                        "summary": str(result.get("response") or "")[:180],
                    }
                )
        return items

    @staticmethod
    def _course_review_plan(node_cards: list[Any]) -> list[dict[str, Any]]:
        plan: list[dict[str, Any]] = []
        for raw in node_cards:
            if not isinstance(raw, dict):
                continue
            score = float(raw.get("mastery_score") or 0)
            if score >= 0.85:
                action = "用迁移题或项目场景保持熟练度。"
                priority = "low"
            elif score >= 0.55:
                action = "补一组混合练习，并把错因写入学习报告。"
                priority = "medium"
            else:
                action = "先看图解或例题拆解，再做低门槛复测。"
                priority = "high"
            plan.append(
                {
                    "node_id": raw.get("node_id"),
                    "title": raw.get("title"),
                    "priority": priority,
                    "action": action,
                    "mastery_score": score,
                }
            )
        plan.sort(key=lambda item: {"high": 0, "medium": 1, "low": 2}.get(str(item.get("priority")), 3))
        return plan[:6]

    @staticmethod
    def _course_demo_outline(session: GuideSessionV2, evaluation: dict[str, Any]) -> list[str]:
        return [
            f"用一句话说明学习目标：{session.goal}",
            f"展示知识地图：{len(session.course_map.nodes)} 个知识点、{len(session.tasks)} 个学习任务。",
            f"展示学习证据：完成 {evaluation.get('completed_tasks', 0)} 个任务，综合掌握分 {evaluation.get('overall_score', 0)}。",
            "展示多智能体资源：图解、练习、视频或资料如何附着在任务上。",
            "展示最终课程项目与评分 Rubric，说明系统如何支持持续优化。",
        ]

    @staticmethod
    def _course_demo_blueprint(
        *,
        session: GuideSessionV2,
        evaluation: dict[str, Any],
        report: dict[str, Any],
        portfolio: list[dict[str, Any]],
        learning_style: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build a concrete recording plan for the competition demo."""

        current = GuideV2Manager._current_task(session)
        readiness = dict(report.get("demo_readiness") or {})
        learning_style = dict(learning_style or {})
        action_brief = dict(report.get("action_brief") or {})
        primary_action = dict(action_brief.get("primary_action") or {})
        resource_counts = dict(evaluation.get("resource_counts") or {})
        completed = int(evaluation.get("completed_tasks") or 0)
        total = int(evaluation.get("total_tasks") or 0)
        score = int(evaluation.get("overall_score") or 0)
        first_artifact = next((item for item in portfolio if item.get("title")), {})
        resource_text = []
        if resource_counts.get("visual"):
            resource_text.append("图解")
        if resource_counts.get("video"):
            resource_text.append("短视频")
        if resource_counts.get("quiz"):
            resource_text.append("练习")
        resource_summary = "、".join(resource_text) if resource_text else "图解或练习"

        storyline = [
            {
                "minute": "0:00-0:40",
                "title": "学习目标与画像入口",
                "show": "打开导学首页，说明目标、水平、偏好和薄弱点如何进入画像。",
                "talking_point": learning_style.get("demo_talking_point")
                or "系统先理解学生，再安排路径，避免一开始就让用户面对复杂工具。",
                "requirement": "对话式学习画像自主构建",
            },
            {
                "minute": "0:40-1:50",
                "title": "个性化路线与当前任务",
                "show": f"展示知识地图和当前任务：{current.title if current else session.goal}。",
                "talking_point": f"路线包含 {len(session.course_map.nodes)} 个知识点、{len(session.tasks)} 个任务，当前进度 {completed}/{total}。",
                "requirement": "个性化学习路径规划和资源推送",
            },
            {
                "minute": "1:50-3:20",
                "title": "多智能体生成资源",
                "show": f"围绕当前任务生成或展示 {resource_summary}，说明画像智能体、资源智能体、评估智能体如何协作。",
                "talking_point": "前端只展示协作摘要，不暴露日志，让评委看到多智能体协作但不干扰学习。",
                "requirement": "多智能体协同的资源生成",
            },
            {
                "minute": "3:20-4:50",
                "title": "交互练习与即时辅导",
                "show": "提交一组练习或任务反思，展示对错反馈、解析和下一步建议。",
                "talking_point": "练习结果会回写画像和导学报告，形成真正的学习行为证据。",
                "requirement": "智能辅导与学习效果评估",
            },
            {
                "minute": "4:50-6:20",
                "title": "学习报告与处方",
                "show": f"展示学习处方：{action_brief.get('title') or primary_action.get('label') or '下一步建议'}。",
                "talking_point": f"报告给出掌握分 {score}，并把错因、画像信号压缩成可执行行动。",
                "requirement": "学习效果评估与动态调整",
            },
            {
                "minute": "6:20-7:00",
                "title": "课程产出包收尾",
                "show": "展示课程项目、Rubric、作品集索引和演示就绪度。",
                "talking_point": "最后把过程证据整理成可评分、可复盘、可提交的课程作品。",
                "requirement": "配套文档与完整运行成果",
            },
        ]

        fallbacks = [
            "提前保存一份图解、练习结果和学习报告到 Notebook，模型波动时直接展示历史产物。",
            "如果短视频渲染较慢，先展示 Manim 代码和已生成截图，再说明 FFmpeg/LaTeX 配置已完成。",
            "如果 RAG 或联网搜索不可用，演示仍围绕导学画像、任务资源和练习反馈跑通主线。",
        ]
        if first_artifact:
            fallbacks.insert(0, f"可优先展示已生成产物：{first_artifact.get('title')}。")

        judge_mapping = [
            {"requirement": "画像", "evidence": "画像页、导学画像、任务反思、练习回写。"},
            {"requirement": "多智能体", "evidence": "资源卡协作链路、图解/动画/出题/评估智能体。"},
            {"requirement": "路径规划", "evidence": "知识地图、当前任务、动态补基和学习处方。"},
            {"requirement": "智能辅导", "evidence": "文字答疑、图解、短视频、交互练习和即时反馈。"},
            {"requirement": "效果评估", "evidence": "学习报告、错因复测、演示就绪度和课程产出包。"},
        ]

        return {
            "title": "7 分钟比赛演示路线",
            "duration_minutes": 7,
            "summary": readiness.get("summary")
            or "按画像、路线、资源、练习、报告、产出包的顺序录制，能完整覆盖赛题主线。",
            "readiness_label": readiness.get("label") or evaluation.get("readiness", "not_started"),
            "readiness_score": readiness.get("score", 0),
            "learning_style": learning_style,
            "storyline": storyline,
            "fallbacks": fallbacks[:4],
            "judge_mapping": judge_mapping,
        }

    @staticmethod
    def _course_demo_fallback_kit(
        *,
        session: GuideSessionV2,
        evaluation: dict[str, Any],
        report: dict[str, Any],
        portfolio: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Prepare deterministic demo material when live generation is unstable."""

        current = GuideV2Manager._current_task(session)
        topic = session.course_map.metadata.get("course_name") or session.course_map.title or session.goal
        weak_points = list(session.profile.weak_points or [])
        preferences = list(session.profile.preferences or [])
        first_artifact = next((item for item in portfolio if item.get("title")), {})
        readiness = dict(report.get("demo_readiness") or {})
        action_brief = dict(report.get("action_brief") or {})
        action_title = str(action_brief.get("title") or "根据报告继续下一步").strip()

        persona = {
            "name": "跨专业初学者",
            "goal": session.goal,
            "level": session.profile.level or "beginner",
            "weak_points": weak_points[:3] or ["概念边界不清", "公式直觉不足"],
            "preferences": preferences[:3] or ["图解", "练习"],
            "story": "学生希望用较短时间理解核心概念，并通过图解、练习和反思确认自己真的掌握。",
        }

        assets: list[dict[str, str]] = [
            {
                "type": "profile",
                "title": "典型学习画像",
                "status": "ready",
                "show": "展示画像页或导学画像摘要，说明系统如何识别水平、偏好和薄弱点。",
                "talking_point": "画像不是表单，而是由对话、任务、练习和反思持续更新。",
                "fallback_prompt": "让系统用一句话解释当前学习者画像和优先卡点。",
            },
            {
                "type": "visual",
                "title": f"{current.title if current else topic} 图解",
                "status": "ready" if any(item.get("type") == "visual" for item in portfolio) else "seed",
                "show": "展示图解产物或点击生成图解按钮。",
                "talking_point": "图解智能体把抽象概念转成可视结构，降低学习门槛。",
                "fallback_prompt": f"围绕「{current.title if current else topic}」生成一张概念关系图，突出关键步骤和常见误区。",
            },
            {
                "type": "quiz",
                "title": "交互练习与反馈",
                "status": "ready" if any(item.get("type") == "quiz" for item in portfolio) else "seed",
                "show": "展示选择、判断、填空或简答题，并提交答案查看反馈。",
                "talking_point": "练习不是孤立题目，提交后会回写画像、报告和下一步建议。",
                "fallback_prompt": f"围绕「{current.title if current else topic}」生成一组低门槛混合题，包含选择、判断、填空和简答。",
            },
            {
                "type": "report",
                "title": "学习报告与处方",
                "status": "ready" if action_brief else "seed",
                "show": f"展示学习处方：{action_title}。",
                "talking_point": "系统把掌握分、错因和画像信号压缩成一个可执行动作。",
                "fallback_prompt": "打开学习报告，展示学习处方、演示就绪度和下一步补齐动作。",
            },
        ]
        if first_artifact:
            assets.insert(
                0,
                {
                    "type": "saved",
                    "title": str(first_artifact.get("title") or "已保存产物"),
                    "status": "ready",
                    "show": "模型波动时优先展示这份已生成产物。",
                    "talking_point": "系统会把资源沉淀到作品集，不依赖现场重新生成。",
                    "fallback_prompt": str(first_artifact.get("summary") or "打开作品集中的历史产物。"),
                },
            )

        checklist = [
            "打开或创建「机器学习基础」导学路线，确保当前任务可见。",
            "准备一个画像证据：前测、画像对话或任务反思至少完成一项。",
            "准备一个多模态产物：图解优先，短视频作为加分展示。",
            "准备一组可提交练习，并确认提交后能看到反馈和画像回写。",
            "最后打开学习报告和课程产出包，展示学习处方、演示就绪度和 7 分钟路线。",
        ]

        if readiness.get("next_steps"):
            checklist.insert(0, f"先补齐：{readiness.get('next_steps', [''])[0]}")

        fallback_script = [
            "如果现场生成较慢，就切换到已保存产物，说明 SparkWeave 支持资源沉淀与复盘。",
            "如果短视频没有及时渲染，就展示图解和 Manim 代码/历史视频，强调多模态生成链路。",
            "如果外部知识库不可用，就演示画像、导学、练习、报告这条本地闭环。",
        ]

        return {
            "title": "录屏兜底包",
            "summary": "为比赛录屏准备一套稳定材料：固定画像、可展示产物、排练清单和兜底话术。",
            "persona": persona,
            "assets": assets[:5],
            "checklist": checklist[:6],
            "fallback_script": fallback_script,
        }

    @staticmethod
    def _course_demo_seed_pack(
        *,
        session: GuideSessionV2,
        evaluation: dict[str, Any],
        report: dict[str, Any],
    ) -> dict[str, Any]:
        """Expose a reproducible task chain for rehearsing the course demo."""

        metadata_seed = dict(session.course_map.metadata.get("demo_seed") or {})
        seed_chain = [item for item in metadata_seed.get("task_chain") or [] if isinstance(item, dict)]
        seed_prompts = [item for item in metadata_seed.get("resource_prompts") or [] if isinstance(item, dict)]
        task_lookup = {task.task_id: task for task in session.tasks}
        current = GuideV2Manager._current_task(session)
        if not seed_chain:
            seed_chain = [
                {
                    "task_id": current.task_id if current else "",
                    "title": current.title if current else session.goal,
                    "stage": "当前任务",
                    "show": "展示当前任务、生成一个资源、提交一次反馈。",
                    "sample_score": 0.72,
                    "sample_reflection": "我理解了大方向，但还需要用练习确认细节。",
                }
            ]

        task_chain: list[dict[str, Any]] = []
        for item in seed_chain[:4]:
            task_id = str(item.get("task_id") or "")
            task = task_lookup.get(task_id)
            task_chain.append(
                {
                    "task_id": task_id,
                    "title": task.title if task else str(item.get("title") or "演示任务"),
                    "stage": str(item.get("stage") or "演示步骤"),
                    "show": str(item.get("show") or task.instruction if task else item.get("show") or ""),
                    "resource_type": str(item.get("resource_type") or ""),
                    "prompt": str(item.get("prompt") or ""),
                    "sample_score": float(item.get("sample_score") or 0.72),
                    "sample_reflection": str(item.get("sample_reflection") or "我能说出核心思路，但还需要更多练习。"),
                    "status": task.status if task else "seed",
                }
            )

        return {
            "title": metadata_seed.get("title") or "稳定 Demo 样例",
            "scenario": metadata_seed.get("scenario")
            or "使用固定学习者画像和任务链，稳定演示画像、资源、练习和报告闭环。",
            "persona": metadata_seed.get("persona")
            or {
                "name": "演示学习者",
                "level": session.profile.level or "beginner",
                "goal": session.goal,
                "weak_points": list(session.profile.weak_points or [])[:3],
                "preferences": list(session.profile.preferences or [])[:3],
            },
            "task_chain": task_chain,
            "resource_prompts": seed_prompts[:4],
            "rehearsal_notes": list(metadata_seed.get("rehearsal_notes") or [])[:4],
            "report_anchor": {
                "score": evaluation.get("overall_score", 0),
                "readiness": evaluation.get("readiness", "not_started"),
                "action": (report.get("action_brief") or {}).get("title") or "",
            },
        }

    @staticmethod
    def _course_package_markdown(package: dict[str, Any]) -> str:
        project = dict(package.get("capstone_project") or {})
        report = dict(package.get("learning_report") or {})
        metadata = dict(package.get("course_metadata") or {})
        learning_style = dict(package.get("learning_style") or {})
        learning_style_signals = [item for item in learning_style.get("signals") or [] if isinstance(item, dict)]
        demo_blueprint = dict(package.get("demo_blueprint") or {})
        demo_storyline = [item for item in demo_blueprint.get("storyline") or [] if isinstance(item, dict)]
        demo_fallbacks = [str(item) for item in demo_blueprint.get("fallbacks") or []]
        judge_mapping = [item for item in demo_blueprint.get("judge_mapping") or [] if isinstance(item, dict)]
        fallback_kit = dict(package.get("demo_fallback_kit") or {})
        fallback_persona = dict(fallback_kit.get("persona") or {})
        fallback_assets = [item for item in fallback_kit.get("assets") or [] if isinstance(item, dict)]
        fallback_checklist = [str(item) for item in fallback_kit.get("checklist") or []]
        fallback_script = [str(item) for item in fallback_kit.get("fallback_script") or []]
        seed_pack = dict(package.get("demo_seed_pack") or {})
        seed_persona = dict(seed_pack.get("persona") or {})
        seed_chain = [item for item in seed_pack.get("task_chain") or [] if isinstance(item, dict)]
        seed_prompts = [item for item in seed_pack.get("resource_prompts") or [] if isinstance(item, dict)]
        rehearsal_notes = [str(item) for item in seed_pack.get("rehearsal_notes") or []]
        behavior_summary = dict(report.get("behavior_summary") or {})
        behavior_tags = [str(item) for item in report.get("behavior_tags") or []]
        recent_timeline_events = [item for item in report.get("recent_timeline_events") or [] if isinstance(item, dict)]
        mistake_summary = dict(report.get("mistake_summary") or {})
        mistake_clusters = [item for item in report.get("mistake_clusters") or [] if isinstance(item, dict)]
        lines = [
            f"# {package.get('title') or '课程产出包'}",
            "",
            f"> {package.get('summary') or ''}",
            "",
            "## 课程信息",
            "",
            f"- 课程名称：{metadata.get('course_name') or '-'}",
            f"- 建议周期：{metadata.get('suggested_weeks') or '-'} 周",
            f"- 学分建议：{metadata.get('credits') or '-'}",
            f"- 面向对象：{metadata.get('target_learners') or '-'}",
            "",
            "## 学习状态",
            "",
            f"- 综合掌握分：{report.get('overall_score', 0)}",
            f"- 就绪状态：{report.get('readiness', 'not_started')}",
            f"- 进度：{report.get('progress', 0)}%",
            f"- 行为事件：{behavior_summary.get('event_count', 0)} 条",
            f"- 资源/练习：{behavior_summary.get('resource_count', 0)} 个资源，{behavior_summary.get('quiz_attempt_count', 0)} 次练习",
            f"- 行为标签：{', '.join(behavior_tags) if behavior_tags else '-'}",
            f"- 错因闭环：{mistake_summary.get('cluster_count', 0)} 类错因，{mistake_summary.get('pending_retest_count', 0)} 个待复测",
            "",
            "## 学习目标",
            "",
        ]
        for item in metadata.get("learning_outcomes") or []:
            lines.append(f"- {item}")
        if not metadata.get("learning_outcomes"):
            lines.append("- 完成课程核心任务并形成可展示作品。")
        if learning_style:
            lines.extend(["", "## 学习画像与推进方式", ""])
            lines.append(f"- 推进风格：{learning_style.get('label') or '-'}")
            lines.append(f"- 说明：{learning_style.get('summary') or '-'}")
            lines.append(f"- 趋势：{learning_style.get('trend') or '-'}")
            if learning_style.get("path_effect"):
                lines.append(f"- 路线影响：{learning_style.get('path_effect')}")
            for item in learning_style_signals[:3]:
                lines.append(f"- {item.get('label') or '信号'}：{item.get('value') or '-'}")
        if recent_timeline_events:
            lines.extend(["", "## 最近学习轨迹", ""])
            for event in recent_timeline_events[:5]:
                label = event.get("label") or event.get("type") or "event"
                title = event.get("title") or event.get("description") or "-"
                lines.append(f"- {label}：{title}")
        if mistake_clusters:
            lines.extend(["", "## 错因复测依据", ""])
            for cluster in mistake_clusters[:3]:
                lines.append(f"- {cluster.get('label') or '-'}：{cluster.get('suggested_action') or '-'}")
        lines.extend(
            [
                "",
                "## 周次安排",
                "",
            ]
        )
        for item in metadata.get("weekly_schedule") or []:
            if isinstance(item, dict):
                lines.append(f"- 第 {item.get('week')} 周：{item.get('topic')}（产出：{item.get('deliverable')}）")
        if not metadata.get("weekly_schedule"):
            lines.append("- 按导学任务顺序推进。")
        lines.extend(
            [
                "",
                "## 课程项目",
                "",
                f"### {project.get('title') or '学习成果项目'}",
                "",
                str(project.get("scenario") or ""),
                "",
                "### 交付物",
                "",
            ]
        )
        for item in project.get("deliverables") or []:
            lines.append(f"- {item}")
        lines.extend(["", "### 执行步骤", ""])
        for index, item in enumerate(project.get("steps") or [], start=1):
            lines.append(f"{index}. {item}")
        lines.extend(["", "## 评分 Rubric", ""])
        for item in package.get("rubric") or []:
            if not isinstance(item, dict):
                continue
            lines.extend(
                [
                    f"### {item.get('criterion')}（{item.get('weight')}%）",
                    "",
                    f"- 优秀：{item.get('excellent')}",
                    f"- 达标：{item.get('baseline')}",
                    "",
                ]
            )
        lines.extend(["## 复习计划", ""])
        for item in package.get("review_plan") or []:
            if isinstance(item, dict):
                lines.append(f"- [{item.get('priority')}] {item.get('title')}: {item.get('action')}")
        if not package.get("review_plan"):
            lines.append("- 完成更多任务后会生成个性化复习计划。")
        lines.extend(["", "## 作品集索引", ""])
        for item in package.get("portfolio") or []:
            if isinstance(item, dict):
                lines.append(f"- {item.get('title')}（{item.get('type')} / {item.get('capability')}）")
        if not package.get("portfolio"):
            lines.append("- 暂无生成资源。")
        lines.extend(["", "## 演示提纲", ""])
        for item in package.get("demo_outline") or []:
            lines.append(f"- {item}")
        if demo_blueprint:
            lines.extend(["", "## 7 分钟演示路线", ""])
            lines.append(f"- 就绪状态：{demo_blueprint.get('readiness_label') or '-'}")
            lines.append(f"- 就绪分：{demo_blueprint.get('readiness_score', 0)}")
            lines.append(f"- 说明：{demo_blueprint.get('summary') or '-'}")
            for item in demo_storyline[:6]:
                lines.append(
                    f"- {item.get('minute') or '-'}｜{item.get('title') or '-'}：{item.get('show') or '-'}"
                )
            if judge_mapping:
                lines.extend(["", "### 赛题映射", ""])
                for item in judge_mapping:
                    lines.append(f"- {item.get('requirement') or '-'}：{item.get('evidence') or '-'}")
            if demo_fallbacks:
                lines.extend(["", "### 演示兜底", ""])
                for item in demo_fallbacks[:4]:
                    lines.append(f"- {item}")
        if fallback_kit:
            lines.extend(["", "## 录屏兜底包", ""])
            lines.append(f"- 摘要：{fallback_kit.get('summary') or '-'}")
            lines.append(f"- 学习者：{fallback_persona.get('name') or '-'}")
            lines.append(f"- 目标：{fallback_persona.get('goal') or '-'}")
            lines.append(f"- 卡点：{', '.join(fallback_persona.get('weak_points') or []) or '-'}")
            if fallback_assets:
                lines.extend(["", "### 稳定展示素材", ""])
                for item in fallback_assets[:5]:
                    lines.append(
                        f"- [{item.get('status') or '-'}] {item.get('title') or '-'}：{item.get('show') or '-'}"
                    )
            if fallback_checklist:
                lines.extend(["", "### 录屏前检查", ""])
                for item in fallback_checklist[:6]:
                    lines.append(f"- {item}")
            if fallback_script:
                lines.extend(["", "### 兜底话术", ""])
                for item in fallback_script[:3]:
                    lines.append(f"- {item}")
        if seed_pack:
            lines.extend(["", "## 稳定 Demo 样例", ""])
            lines.append(f"- 场景：{seed_pack.get('scenario') or '-'}")
            lines.append(f"- 学习者：{seed_persona.get('name') or '-'}")
            lines.append(f"- 目标：{seed_persona.get('goal') or '-'}")
            if seed_chain:
                lines.extend(["", "### 可复现任务链", ""])
                for item in seed_chain[:4]:
                    lines.append(
                        f"- {item.get('stage') or '-'}｜{item.get('title') or '-'}："
                        f"{item.get('show') or '-'}；示例反思：{item.get('sample_reflection') or '-'}"
                    )
            if seed_prompts:
                lines.extend(["", "### 稳定资源提示词", ""])
                for item in seed_prompts[:4]:
                    lines.append(f"- {item.get('title') or item.get('type') or '-'}：{item.get('prompt') or '-'}")
            if rehearsal_notes:
                lines.extend(["", "### 排练备注", ""])
                for item in rehearsal_notes[:4]:
                    lines.append(f"- {item}")
        return "\n".join(lines).strip() + "\n"

    def _fallback_nodes(self, profile: LearnerProfile) -> list[CourseNode]:
        topic = self._short_title(profile.goal)
        return [
            CourseNode(
                node_id="N1",
                title=f"{topic}：核心直觉",
                description="先澄清关键概念、使用条件和这个主题为什么值得学。",
                difficulty="easy",
                estimated_minutes=min(profile.time_budget_minutes, 20),
                tags=["基础", "直觉"],
                mastery_target="能用自己的话讲清核心想法，并指出一个容易混淆的边界。",
                resource_strategy=["简明讲解", "概念图"],
            ),
            CourseNode(
                node_id="N2",
                title=f"{topic}：代表例题",
                description="把核心想法用到一个有代表性的题目或真实场景里。",
                prerequisites=["N1"],
                difficulty="medium",
                estimated_minutes=min(profile.time_budget_minutes, 25),
                tags=["例题", "练习"],
                mastery_target="能按正确推理步骤完成一个代表性例题，并解释每一步为什么成立。",
                resource_strategy=["分步例题", "引导练习"],
            ),
            CourseNode(
                node_id="N3",
                title=f"{topic}：检测与迁移",
                description="用混合题检查掌握情况，再迁移到一个新情境。",
                prerequisites=["N2"],
                difficulty="medium",
                estimated_minutes=min(profile.time_budget_minutes, 20),
                tags=["测评", "迁移"],
                mastery_target="能完成混合题，并说出自己的主要错因和修正方法。",
                resource_strategy=["交互练习", "反思复盘"],
            ),
        ]

    @staticmethod
    def _fallback_tasks(course_map: CourseMap) -> list[LearningTask]:
        tasks: list[LearningTask] = []
        for node in course_map.nodes:
            task_index = len(tasks) + 1
            tasks.append(
                LearningTask(
                    task_id=f"T{task_index}",
                    node_id=node.node_id,
                    type="explain",
                    title=f"建立理解：{node.title}",
                    instruction=(
                        f"先学习「{node.title}」的简明讲解，写下一个核心想法、一个使用条件，"
                        "以及一个你仍然不确定的点。"
                    ),
                    estimated_minutes=max(5, min(node.estimated_minutes // 2, 15)),
                    success_criteria=["用一句话说清概念", "写出一个常见误区", "留下可评分的反思证据"],
                )
            )
            task_index = len(tasks) + 1
            tasks.append(
                LearningTask(
                    task_id=f"T{task_index}",
                    node_id=node.node_id,
                    type="practice",
                    title=f"检测掌握：{node.title}",
                    instruction=(
                        "完成一组短练习或口头自测。如果正确率低于 80%，先生成图解或例题，"
                        "再重新提交一次掌握证据。"
                    ),
                    estimated_minutes=max(5, min(node.estimated_minutes // 2, 12)),
                    success_criteria=["正确率达到 80% 以上", "解释至少一个错误答案的原因", "确认下一步是否需要补救"],
                )
            )
        return tasks

    def _update_mastery(
        self,
        session: GuideSessionV2,
        task: LearningTask,
        evidence: LearningEvidence,
    ) -> None:
        state = session.mastery.setdefault(task.node_id, MasteryState(node_id=task.node_id))
        score = evidence.score
        if score is None:
            score = 0.75 if evidence.reflection else 0.6
        previous_weight = max(state.evidence_count, 0)
        state.score = round(((state.score * previous_weight) + score) / (previous_weight + 1), 3)
        state.evidence_count += 1
        state.last_updated = time.time()
        state.status = "mastered" if state.score >= 0.8 else "learning" if state.score >= 0.45 else "needs_support"

    def _update_profile_from_evidence(
        self,
        session: GuideSessionV2,
        task: LearningTask,
        evidence: LearningEvidence,
    ) -> None:
        """Continuously refine the learner profile from real learning evidence."""

        node = next((item for item in session.course_map.nodes if item.node_id == task.node_id), None)
        weak_label = node.title if node else task.title

        def append_unique(items: list[str], value: str, *, limit: int = 8) -> None:
            cleaned = " ".join(str(value or "").split()).strip()
            if not cleaned:
                return
            normalized = {item.strip().lower() for item in items}
            if cleaned.lower() not in normalized:
                items.append(cleaned)
            del items[limit:]

        if evidence.score is not None and evidence.score < 0.65:
            append_unique(session.profile.weak_points, weak_label)
        if evidence.mistake_types:
            for mistake in evidence.mistake_types:
                append_unique(session.profile.weak_points, mistake)

        artifact_types = self._task_artifact_types(task)
        if "visual" in artifact_types:
            append_unique(session.profile.preferences, "visual")
        if "video" in artifact_types:
            append_unique(session.profile.preferences, "video")
        if "quiz" in artifact_types:
            append_unique(session.profile.preferences, "practice")

        if evidence.score is not None:
            if evidence.score >= 0.85 and session.profile.level in {"", "unknown", "beginner"}:
                session.profile.level = "intermediate"
            elif evidence.score < 0.45:
                session.profile.level = "beginner"

        reflection = " ".join(evidence.reflection.split()).strip()
        if reflection:
            session.profile.source_context_summary = (
                f"Latest evidence on {task.title}: score={evidence.score if evidence.score is not None else 'unknown'}; "
                f"reflection={reflection[:180]}"
            )

    @staticmethod
    def _normalize_quiz_answers(answers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(answers, start=1):
            if not isinstance(item, dict):
                continue
            question = " ".join(str(item.get("question") or "").split()).strip()
            if not question:
                continue
            raw_options = item.get("options") if isinstance(item.get("options"), dict) else {}
            normalized.append(
                {
                    "question_id": str(item.get("question_id") or f"q{index}"),
                    "question": question,
                    "question_type": str(item.get("question_type") or ""),
                    "options": {str(key): str(value) for key, value in raw_options.items()},
                    "user_answer": str(item.get("user_answer") or ""),
                    "correct_answer": str(item.get("correct_answer") or ""),
                    "explanation": str(item.get("explanation") or ""),
                    "difficulty": str(item.get("difficulty") or ""),
                    "concepts": GuideV2Manager._quiz_concept_labels([item]),
                    "is_correct": bool(item.get("is_correct")),
                }
            )
        return normalized

    @staticmethod
    def _quiz_mistake_types(wrong_items: list[dict[str, Any]]) -> list[str]:
        mistakes: list[str] = []
        for item in wrong_items[:6]:
            for concept in GuideV2Manager._quiz_concept_labels([item])[:3]:
                if concept and concept not in mistakes:
                    mistakes.append(concept)
            question_type = str(item.get("question_type") or "").strip()
            difficulty = str(item.get("difficulty") or "").strip()
            question = str(item.get("question") or "").strip()
            label = question_type or difficulty or question[:32]
            if label and label not in mistakes:
                mistakes.append(label)
        return mistakes

    @staticmethod
    def _quiz_concept_labels(items: list[dict[str, Any]]) -> list[str]:
        labels: list[str] = []
        keys = (
            "concepts",
            "concept",
            "tested_concepts",
            "tested_concept",
            "knowledge_points",
            "knowledge_point",
            "learning_points",
            "learning_point",
            "categories",
            "category",
            "tags",
        )

        def add(value: Any) -> None:
            if value is None or value == "":
                return
            if isinstance(value, str):
                parts = re.split(r"\s*(?:,|，|、|;|；|\|)\s*", value)
                for part in parts:
                    text = " ".join(part.split()).strip()
                    if text and text not in labels:
                        labels.append(text)
                return
            if isinstance(value, dict):
                for key in ("label", "name", "title", "value", "concept", "concept_id", "id"):
                    text = " ".join(str(value.get(key) or "").split()).strip()
                    if text:
                        if text not in labels:
                            labels.append(text)
                        return
                return
            if isinstance(value, (list, tuple, set)):
                for item in value:
                    add(item)
                return
            text = " ".join(str(value).split()).strip()
            if text and text not in labels:
                labels.append(text)

        for item in items:
            if not isinstance(item, dict):
                continue
            for key in keys:
                add(item.get(key))
            metadata = item.get("metadata")
            if isinstance(metadata, dict):
                for key in keys:
                    add(metadata.get(key))
        return labels[:8]

    @staticmethod
    def _quiz_concept_feedback(
        answers: list[dict[str, Any]],
        *,
        fallback_concept: str = "",
    ) -> list[dict[str, Any]]:
        stats: dict[str, dict[str, Any]] = {}
        fallback = " ".join(str(fallback_concept or "当前任务").split()).strip() or "当前任务"
        for answer in answers:
            labels = GuideV2Manager._quiz_concept_labels([answer]) or [fallback]
            is_correct = bool(answer.get("is_correct"))
            question = " ".join(str(answer.get("question") or "").split()).strip()
            for label in labels[:4]:
                item = stats.setdefault(
                    label,
                    {
                        "concept": label,
                        "correct_count": 0,
                        "total_count": 0,
                        "wrong_questions": [],
                    },
                )
                item["total_count"] += 1
                item["correct_count"] += int(is_correct)
                if not is_correct and question and len(item["wrong_questions"]) < 3:
                    item["wrong_questions"].append(question)

        feedback: list[dict[str, Any]] = []
        for item in stats.values():
            total = int(item["total_count"] or 0)
            correct = int(item["correct_count"] or 0)
            score = round(correct / total, 3) if total else 0.0
            if score >= 0.85:
                status = "stable"
                summary = "这个知识点表现稳定，可以进入迁移应用。"
                next_action = "尝试用自己的话解释，并做一道变式题。"
            elif score >= 0.6:
                status = "developing"
                summary = "这个知识点已有基础，但还需要再巩固边界。"
                next_action = "回看错题解析，再补一题相近练习。"
            else:
                status = "needs_support"
                summary = "这个知识点仍是当前卡点，需要先补基础再推进。"
                next_action = "先生成图解或短讲解，再做低门槛复测。"
            feedback.append(
                {
                    "concept": item["concept"],
                    "score": score,
                    "score_percent": round(score * 100),
                    "status": status,
                    "correct_count": correct,
                    "total_count": total,
                    "wrong_questions": item["wrong_questions"],
                    "summary": summary,
                    "next_action": next_action,
                }
            )
        feedback.sort(key=lambda row: (float(row["score"]), -int(row["total_count"]), str(row["concept"])))
        return feedback[:8]

    @staticmethod
    def _mistake_clusters(session: GuideSessionV2) -> list[dict[str, Any]]:
        task_titles = {task.task_id: task.title for task in session.tasks}
        evidence_by_task: dict[str, list[LearningEvidence]] = {}
        for evidence in session.evidence:
            evidence_by_task.setdefault(evidence.task_id, []).append(evidence)
        clusters: dict[str, dict[str, Any]] = {}

        def add(label: str, evidence: LearningEvidence, *, source: str) -> None:
            cleaned = " ".join(str(label or "").split()).strip()
            if not cleaned:
                return
            key = cleaned.lower()
            cluster = clusters.setdefault(
                key,
                {
                    "label": cleaned,
                    "count": 0,
                    "source": source,
                    "task_ids": [],
                    "task_titles": [],
                    "scores": [],
                    "latest_at": 0.0,
                    "latest_reflection": "",
                },
            )
            cluster["count"] += 1
            if evidence.task_id and evidence.task_id not in cluster["task_ids"]:
                cluster["task_ids"].append(evidence.task_id)
            title = task_titles.get(evidence.task_id, evidence.task_id)
            if title and title not in cluster["task_titles"]:
                cluster["task_titles"].append(title)
            if evidence.score is not None:
                cluster["scores"].append(float(evidence.score))
            if evidence.created_at >= float(cluster.get("latest_at") or 0):
                cluster["latest_at"] = evidence.created_at
                cluster["latest_reflection"] = evidence.reflection

        for evidence in session.evidence:
            for mistake in evidence.mistake_types:
                add(mistake, evidence, source="mistake_type")
            if evidence.score is not None and evidence.score < 0.65 and not evidence.mistake_types:
                title = task_titles.get(evidence.task_id, evidence.task_id)
                add(title, evidence, source="low_score")

        results: list[dict[str, Any]] = []
        for cluster in clusters.values():
            scores = list(cluster.pop("scores", []))
            average_score = round(sum(scores) / len(scores), 3) if scores else None
            label = str(cluster.get("label") or "")
            cluster["average_score"] = average_score
            cluster["severity"] = (
                "high"
                if average_score is not None and average_score < 0.45
                else "medium"
                if average_score is not None and average_score < 0.7
                else "review"
            )
            cluster.update(GuideV2Manager._mistake_loop_state(session, cluster, evidence_by_task))
            if cluster.get("loop_status") == "closed":
                cluster["severity"] = "closed"
            cluster["suggested_action"] = GuideV2Manager._mistake_suggested_action(label, average_score)
            results.append(cluster)

        return sorted(
            results,
            key=lambda item: (
                -int(item.get("count") or 0),
                float(item.get("average_score") or 1.0),
                -float(item.get("latest_at") or 0),
            ),
        )[:8]

    @staticmethod
    def _mistake_suggested_action(label: str, average_score: float | None) -> str:
        normalized = label.lower()
        if "choice" in normalized or "选择" in normalized:
            return "先复述概念边界，再做 2 道反例辨析题。"
        if "judge" in normalized or "判断" in normalized:
            return "先列出判断条件，再用正反样例复测。"
        if "blank" in normalized or "填空" in normalized or "公式" in normalized:
            return "补齐关键公式或步骤，再做一次低门槛填空复测。"
        if average_score is not None and average_score < 0.45:
            return "先看图解或例题拆解，再做 3 道递进纠错题。"
        return "用一道同类题复测，并写出错因修正说明。"

    @staticmethod
    def _mistake_loop_state(
        session: GuideSessionV2,
        cluster: dict[str, Any],
        evidence_by_task: dict[str, list[LearningEvidence]],
    ) -> dict[str, Any]:
        label = str(cluster.get("label") or "").strip()
        label_key = label.lower()
        task_ids = {str(item) for item in cluster.get("task_ids") or []}

        def related(task: LearningTask) -> bool:
            metadata = task.metadata or {}
            trigger_task_id = str(metadata.get("trigger_task_id") or "")
            mistakes = [str(item).lower() for item in metadata.get("mistake_types") or []]
            title = task.title.lower()
            return (
                bool(trigger_task_id and trigger_task_id in task_ids)
                or bool(label_key and label_key in mistakes)
                or bool(label_key and label_key in title)
            )

        remediations = [
            task
            for task in session.tasks
            if task.origin in {"adaptive_remediation", "diagnostic_remediation"} and related(task)
        ]
        retests = [
            task
            for task in session.tasks
            if task.origin == "adaptive_retest" and related(task)
        ]
        pending_remediations = [task for task in remediations if task.status not in {"completed", "skipped"}]
        pending_retests = [task for task in retests if task.status not in {"completed", "skipped"}]

        retest_scores: list[tuple[float, float]] = []
        for task in retests:
            for evidence in evidence_by_task.get(task.task_id, []):
                if evidence.score is not None:
                    retest_scores.append((float(evidence.score), evidence.created_at))
        passed_retests = [(score, created_at) for score, created_at in retest_scores if score >= 0.75]
        latest_retest = max(retest_scores, key=lambda item: item[1], default=None)
        latest_pass = max(passed_retests, key=lambda item: item[1], default=None)

        if pending_remediations:
            status = "needs_remediation"
        elif pending_retests:
            status = "ready_for_retest"
        elif passed_retests:
            status = "closed"
        elif retests and retest_scores:
            status = "retest_failed"
        elif retests:
            status = "ready_for_retest"
        else:
            status = "needs_review"

        return {
            "loop_status": status,
            "pending_remediation_task_ids": [task.task_id for task in pending_remediations],
            "pending_retest_task_ids": [task.task_id for task in pending_retests],
            "related_remediation_task_ids": [task.task_id for task in remediations],
            "related_retest_task_ids": [task.task_id for task in retests],
            "latest_retest_score": latest_retest[0] if latest_retest else None,
            "closed_at": latest_pass[1] if latest_pass else None,
            "passed_retest_count": len(passed_retests),
        }

    @staticmethod
    def _mistake_retest_plan(
        session: GuideSessionV2,
        clusters: list[dict[str, Any]],
        pending_remediations: list[dict[str, Any]],
        pending_retests: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if pending_remediations:
            task = pending_remediations[0]
            return [
                {
                    "step": 1,
                    "title": f"先完成补救任务：{task.get('title')}",
                    "action_type": "complete_remediation",
                    "task_id": task.get("task_id"),
                },
                {
                    "step": 2,
                    "title": "完成后进入复测任务或生成一组混合题",
                    "action_type": "prepare_retest",
                    "task_id": task.get("task_id"),
                },
            ]
        if pending_retests:
            task = pending_retests[0]
            return [
                {
                    "step": 1,
                    "title": f"完成复测：{task.get('title')}",
                    "action_type": "complete_retest",
                    "task_id": task.get("task_id"),
                },
                {
                    "step": 2,
                    "title": "提交分数和一句话错因修正",
                    "action_type": "submit_evidence",
                    "task_id": task.get("task_id"),
                },
            ]
        if clusters and all(str(item.get("loop_status") or "") == "closed" for item in clusters):
            return [
                {
                    "step": 1,
                    "title": "本轮错因已通过复测关闭，可进入下一知识点或迁移应用。",
                    "action_type": "closed",
                }
            ]
        if clusters:
            cluster = clusters[0]
            return [
                {
                    "step": 1,
                    "title": f"围绕「{cluster.get('label')}」生成一组复测题",
                    "action_type": "generate_quiz",
                },
                {
                    "step": 2,
                    "title": str(cluster.get("suggested_action") or "完成复测并记录修正后的理解。"),
                    "action_type": "review_mistake",
                },
            ]
        current = GuideV2Manager._current_task(session)
        return [
            {
                "step": 1,
                "title": f"完成当前任务：{current.title}" if current else "完成下一项学习任务",
                "action_type": "continue_learning",
                "task_id": current.task_id if current else "",
            },
            {
                "step": 2,
                "title": "提交练习或反思后，系统会自动生成错因闭环。",
                "action_type": "collect_evidence",
            },
        ]

    @staticmethod
    def _quiz_attempt_reflection(task: LearningTask, attempt: dict[str, Any]) -> str:
        total = int(attempt.get("total_count") or 0)
        correct = int(attempt.get("correct_count") or 0)
        score = float(attempt.get("score") or 0.0)
        wrong = total - correct
        if wrong:
            return (
                f"Interactive quiz for {task.title}: {correct}/{total} correct, "
                f"score={score:.2f}. Needs review on {wrong} item(s)."
            )
        return f"Interactive quiz for {task.title}: {correct}/{total} correct, score={score:.2f}."

    @staticmethod
    def _current_task(session: GuideSessionV2) -> LearningTask | None:
        target = session.learning_path.current_task_id
        if target:
            found = next((task for task in session.tasks if task.task_id == target), None)
            if found:
                return found
        return GuideV2Manager._first_pending_task(session)

    @staticmethod
    def _first_pending_task(session: GuideSessionV2) -> LearningTask | None:
        terminal_statuses = {"completed", "skipped"}
        return next((task for task in session.tasks if task.status not in terminal_statuses), None)

    @staticmethod
    def _task_for_node(session: GuideSessionV2, node_id: str) -> LearningTask | None:
        if not node_id:
            return None
        pending = next(
            (task for task in session.tasks if task.node_id == node_id and task.status != "completed"),
            None,
        )
        if pending is not None:
            return pending
        return next((task for task in session.tasks if task.node_id == node_id), None)

    @staticmethod
    def _task_artifact_types(task: LearningTask) -> set[str]:
        return {
            str(artifact.get("type") or "").strip()
            for artifact in task.artifact_refs
            if isinstance(artifact, dict)
        }

    @staticmethod
    def _progress(session: GuideSessionV2) -> int:
        if not session.tasks:
            return 0
        done = sum(1 for task in session.tasks if task.status in {"completed", "skipped"})
        return int((done / len(session.tasks)) * 100)

    @staticmethod
    def _resource_counts(session: GuideSessionV2) -> dict[str, int]:
        counts = {"visual": 0, "video": 0, "external_video": 0, "quiz": 0, "research": 0, "other": 0}
        for task in session.tasks:
            for artifact in task.artifact_refs:
                artifact_type = str(artifact.get("type") or "").strip() or "other"
                key = artifact_type if artifact_type in counts else "other"
                counts[key] += 1
        return counts

    @staticmethod
    def _quiz_question_count(session: GuideSessionV2) -> int:
        count = 0
        for task in session.tasks:
            for artifact in task.artifact_refs:
                if str(artifact.get("type") or "") != "quiz":
                    continue
                result = artifact.get("result") if isinstance(artifact.get("result"), dict) else {}
                results = result.get("results") if isinstance(result.get("results"), list) else []
                count += len(results)
        return count

    @staticmethod
    def _mastery_distribution(session: GuideSessionV2) -> dict[str, int]:
        distribution = {
            "mastered": 0,
            "learning": 0,
            "needs_support": 0,
            "not_started": 0,
        }
        for state in session.mastery.values():
            key = state.status if state.status in distribution else "not_started"
            distribution[key] += 1
        return distribution

    @staticmethod
    def _evidence_trend(session: GuideSessionV2) -> list[dict[str, Any]]:
        task_titles = {task.task_id: task.title for task in session.tasks}
        trend = []
        for item in sorted(session.evidence, key=lambda evidence: evidence.created_at):
            trend.append(
                {
                    "evidence_id": item.evidence_id,
                    "task_id": item.task_id,
                    "task_title": task_titles.get(item.task_id, item.task_id),
                    "score": item.score,
                    "reflection": item.reflection,
                    "created_at": item.created_at,
                }
            )
        return trend

    @staticmethod
    def _node_evaluations(session: GuideSessionV2) -> list[dict[str, Any]]:
        evaluations = []
        for node in session.course_map.nodes:
            node_tasks = [task for task in session.tasks if task.node_id == node.node_id]
            completed = sum(1 for task in node_tasks if task.status == "completed")
            artifact_count = sum(len(task.artifact_refs) for task in node_tasks)
            mastery = session.mastery.get(node.node_id, MasteryState(node_id=node.node_id))
            evaluations.append(
                {
                    "node_id": node.node_id,
                    "title": node.title,
                    "mastery_score": mastery.score,
                    "status": mastery.status,
                    "completed_tasks": completed,
                    "total_tasks": len(node_tasks),
                    "artifact_count": artifact_count,
                    "mastery_target": node.mastery_target,
                }
            )
        return evaluations

    @staticmethod
    def _strengths(session: GuideSessionV2) -> list[str]:
        strengths: list[str] = []
        mastered_nodes = [
            node.title
            for node in session.course_map.nodes
            if session.mastery.get(node.node_id, MasteryState(node_id=node.node_id)).status == "mastered"
        ]
        if mastered_nodes:
            strengths.append(f"已掌握：{mastered_nodes[0]}")
        completed = sum(1 for task in session.tasks if task.status == "completed")
        if completed:
            strengths.append(f"已完成 {completed} 个学习任务，形成了可评估学习证据。")
        counts = GuideV2Manager._resource_counts(session)
        if counts.get("visual", 0) or counts.get("video", 0):
            strengths.append("已经使用多模态资源辅助理解。")
        return strengths[:3]

    @staticmethod
    def _risk_signals(session: GuideSessionV2) -> list[str]:
        risks: list[str] = []
        weak_nodes = [
            node.title
            for node in session.course_map.nodes
            if session.mastery.get(node.node_id, MasteryState(node_id=node.node_id)).status == "needs_support"
        ]
        if weak_nodes:
            risks.append(f"需要补强：{weak_nodes[0]}")
        if not session.evidence:
            risks.append("还没有完成任务证据，暂时无法判断真实掌握情况。")
        elif any(item.score is not None and item.score < 0.6 for item in session.evidence):
            risks.append("存在低于 60% 的学习证据，需要回看解析或补做练习。")
        counts = GuideV2Manager._resource_counts(session)
        if counts.get("quiz", 0) == 0:
            risks.append("还没有生成练习题，缺少可量化测评数据。")
        return risks[:4]

    @staticmethod
    def _evaluation_next_actions(
        session: GuideSessionV2,
        *,
        progress: int,
        average_evidence_score: float,
        question_count: int,
        resource_counts: dict[str, int],
    ) -> list[str]:
        actions: list[str] = []
        pending = GuideV2Manager._first_pending_task(session)
        if pending:
            actions.append(f"继续当前路线：完成「{pending.title}」。")
        if question_count == 0:
            actions.append("为当前任务生成一组混合题型练习，补齐测评数据。")
        elif average_evidence_score and average_evidence_score < 0.75:
            actions.append("针对错题或低分任务生成图解/例题，再完成一次复测。")
        if resource_counts.get("visual", 0) == 0 and progress < 100:
            actions.append("为最难的知识点生成图解，先建立直觉再做题。")
        if progress >= 100 and average_evidence_score >= 0.8:
            actions.append("进入迁移任务：换一个新场景解释或应用该知识点。")
        return actions[:4]

    @staticmethod
    def _readiness_label(overall_score: float, progress: int) -> str:
        if progress == 0:
            return "待开始"
        if overall_score >= 85:
            return "掌握良好"
        if overall_score >= 65:
            return "稳步推进"
        if overall_score >= 40:
            return "需要练习"
        return "需要引导"

    @staticmethod
    def _parse_json_object(raw: str) -> dict[str, Any]:
        text = raw.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            text = match.group(1).strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start < 0 or end <= start:
                return {}
            parsed = json.loads(text[start : end + 1])
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _bounded_score(score: float | None) -> float | None:
        if score is None:
            return None
        try:
            return max(0.0, min(float(score), 1.0))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _short_title(goal: str) -> str:
        cleaned = " ".join(goal.strip().split())
        return cleaned[:48] or "Learning Topic"

    @staticmethod
    def _summarize_context(context: str) -> str:
        text = " ".join((context or "").split())
        return text[:240]

    @staticmethod
    def _infer_level(goal: str) -> str:
        lowered = goal.lower()
        if any(token in lowered for token in ("零基础", "beginner", "入门", "基础")):
            return "beginner"
        if any(token in lowered for token in ("进阶", "advanced", "论文", "paper")):
            return "advanced"
        return "intermediate"

    @staticmethod
    def _infer_horizon(goal: str) -> str:
        lowered = goal.lower()
        if any(token in lowered for token in ("今天", "20分钟", "30分钟", "today")):
            return "today"
        if any(token in lowered for token in ("一周", "week")):
            return "week"
        return "short"

    @staticmethod
    def _infer_time_budget(goal: str) -> int:
        match = re.search(r"(\d{1,3})\s*(?:分钟|min|minutes)", goal, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return 30

    @staticmethod
    def _infer_preferences(goal: str) -> list[str]:
        lowered = goal.lower()
        prefs = []
        if any(token in lowered for token in ("图", "可视化", "visual")):
            prefs.append("visual")
        if any(token in lowered for token in ("公开视频", "公开课", "网课", "b站", "bilibili", "youtube", "external video")):
            prefs.append("external_video")
        if any(token in lowered for token in ("视频", "动画", "video", "animation")):
            prefs.append("video")
        if any(token in lowered for token in ("题", "练习", "quiz", "exercise")):
            prefs.append("practice")
        return prefs or ["explanation", "practice"]

    @staticmethod
    def _infer_weak_points(goal: str) -> list[str]:
        lowered = goal.lower()
        weak = []
        if any(token in lowered for token in ("公式", "推导", "derive")):
            weak.append("formula reasoning")
        if any(token in lowered for token in ("代码", "编程", "code")):
            weak.append("implementation")
        if any(token in lowered for token in ("概念", "intuition")):
            weak.append("conceptual intuition")
        return weak

    @staticmethod
    def _fallback_rationale(profile: LearnerProfile) -> str:
        return (
            "先建立核心直觉，再进入代表例题，最后用短测和迁移任务形成证据闭环；"
            "路线会根据掌握分、错因和反思动态调整，而不是只按固定目录推进。"
        )

    @staticmethod
    def _fallback_today_focus(course_map: CourseMap) -> str:
        return course_map.nodes[0].title if course_map.nodes else "开始学习"


async def _run_langgraph_capability(
    capability: str,
    context: Any,
    *,
    event_sink: GuideResourceEventSink | None = None,
) -> dict[str, Any]:
    from sparkweave.core.contracts import StreamBus, StreamEventType
    from sparkweave.runtime.runner import LangGraphRunner

    bus = StreamBus()
    forward_task = None

    if event_sink:
        async def _forward_events() -> None:
            async for event in bus.subscribe():
                if event.type == StreamEventType.DONE:
                    continue
                event_sink(
                    "trace",
                    {
                        "stage": event.stage,
                        "message": event.content,
                        "source": event.source,
                        "type": event.type.value if hasattr(event.type, "value") else str(event.type),
                        "metadata": event.metadata,
                    },
                )

        import asyncio

        forward_task = asyncio.create_task(_forward_events())

    try:
        await LangGraphRunner().run(context, bus)
    finally:
        await bus.close()
        if forward_task is not None:
            await forward_task

    errors = [event for event in bus._history if event.type == StreamEventType.ERROR]
    if errors:
        message = errors[-1].content or errors[-1].metadata.get("error") or "Capability execution failed"
        raise RuntimeError(str(message))
    result_events = [event for event in bus._history if event.type == StreamEventType.RESULT]
    if result_events:
        return dict(result_events[-1].metadata or {})
    content = "".join(
        event.content for event in bus._history if event.type == StreamEventType.CONTENT and event.content
    ).strip()
    if content:
        return {"response": content}
    return {"response": "No result returned."}


__all__ = [
    "CourseMap",
    "CourseNode",
    "CapabilityRunnerFn",
    "GuideResourceEventSink",
    "GuideSessionV2",
    "GuideV2CreateInput",
    "GuideV2Manager",
    "LearnerProfile",
    "LearningEvidence",
    "LearningPath",
    "LearningTask",
    "MasteryState",
    "PlanAdjustmentEvent",
]
