"""Data contracts for Guide V2 sessions and learning paths."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import time
from typing import Any


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


__all__ = [
    "CourseMap",
    "CourseNode",
    "GuideSessionV2",
    "GuideV2CreateInput",
    "LearnerProfile",
    "LearningEvidence",
    "LearningPath",
    "LearningTask",
    "MasteryState",
    "PlanAdjustmentEvent",
]
