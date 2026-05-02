"""Unified read-only learner profile aggregation.

The profile service intentionally starts as a read-only projection over the
evidence SparkWeave already owns: public memory, guided-learning sessions,
question notebook answers, and saved notebook records. It does not rewrite the
underlying sources; it only produces a stable, explainable snapshot for the UI
and for future recommendation agents.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import inspect
import json
from pathlib import Path
import time
from typing import Any

from sparkweave.services.guide_v2 import GuideV2Manager
from sparkweave.services.learner_evidence import (
    LearnerEvidenceService,
    get_learner_evidence_service,
)
from sparkweave.services.memory import MemoryService, get_memory_service
from sparkweave.services.notebook import NotebookManager, get_notebook_manager
from sparkweave.services.paths import PathService, get_path_service
from sparkweave.services.session_store import SQLiteSessionStore, get_sqlite_session_store


@dataclass
class LearnerProfileSource:
    source_id: str
    label: str
    kind: str
    evidence_count: int = 0
    updated_at: str | None = None
    confidence: float = 0.0


@dataclass
class LearnerProfileClaim:
    label: str
    value: str
    source_ids: list[str] = field(default_factory=list)
    confidence: float = 0.0
    evidence_count: int = 0


@dataclass
class LearnerMastery:
    concept_id: str
    title: str
    score: float | None = None
    status: str = "unknown"
    source_ids: list[str] = field(default_factory=list)
    evidence_count: int = 0
    updated_at: str | None = None


@dataclass
class LearnerWeakPoint:
    label: str
    reason: str = ""
    severity: str = "medium"
    source_ids: list[str] = field(default_factory=list)
    evidence_count: int = 0
    confidence: float = 0.0
    updated_at: str | None = None


@dataclass
class LearnerEvidencePreview:
    evidence_id: str
    source_id: str
    source_label: str
    title: str
    summary: str = ""
    created_at: str | None = None
    score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LearnerProfileSnapshot:
    version: int
    generated_at: str
    confidence: float
    overview: dict[str, Any]
    stable_profile: dict[str, Any]
    learning_state: dict[str, Any]
    next_action: dict[str, Any]
    recommendations: list[str]
    sources: list[dict[str, Any]]
    evidence_preview: list[dict[str, Any]]
    data_quality: dict[str, Any]


class LearnerProfileService:
    """Build a learner profile snapshot from existing SparkWeave evidence."""

    def __init__(
        self,
        *,
        path_service: PathService | None = None,
        memory_service: MemoryService | None = None,
        guide_manager: GuideV2Manager | None = None,
        session_store: SQLiteSessionStore | None = None,
        notebook_manager: NotebookManager | None = None,
        evidence_service: LearnerEvidenceService | None = None,
        output_dir: str | Path | None = None,
    ) -> None:
        self._path_service = path_service or get_path_service()
        self._memory_service = memory_service or get_memory_service()
        self._guide_manager = guide_manager or GuideV2Manager()
        self._store = session_store or get_sqlite_session_store()
        self._notebook_manager = notebook_manager or get_notebook_manager()
        self._evidence_service = evidence_service or get_learner_evidence_service()
        self._output_dir = Path(output_dir) if output_dir else self._path_service.get_user_root() / "learner_profile"
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._profile_path = self._output_dir / "profile.json"

    async def read_profile(self, *, auto_refresh: bool = True) -> dict[str, Any]:
        if self._profile_path.exists() and not auto_refresh:
            payload = self._read_json(self._profile_path)
            if payload:
                return payload
        if self._profile_path.exists() and not self._is_stale(self._profile_path):
            payload = self._read_json(self._profile_path)
            if payload:
                return payload
        return await self.refresh(force=True)

    async def refresh(
        self,
        *,
        include_sources: list[str] | None = None,
        force: bool = True,
    ) -> dict[str, Any]:
        _ = force
        allowed = {item.strip() for item in include_sources or [] if item and item.strip()}

        builder = _ProfileBuilder()
        if not allowed or "memory" in allowed:
            self._collect_memory(builder)
        if not allowed or "guide" in allowed:
            self._collect_guide_memory(builder)
            self._collect_guide_sessions(builder)
        if not allowed or "question_notebook" in allowed:
            await self._collect_question_notebook(builder)
        if not allowed or "notebook" in allowed:
            self._collect_notebooks(builder)
        if not allowed or "evidence" in allowed:
            self._collect_evidence_ledger(builder)

        snapshot = builder.build()
        self._profile_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return snapshot

    async def list_evidence_preview(
        self,
        *,
        source: str | None = None,
        limit: int = 30,
    ) -> dict[str, Any]:
        profile = await self.read_profile(auto_refresh=True)
        evidence = list(profile.get("evidence_preview") or [])
        source_filter = (source or "").strip()
        if source_filter:
            evidence = [item for item in evidence if item.get("source_id") == source_filter]
        return {
            "items": evidence[: max(1, min(int(limit or 30), 100))],
            "total": len(evidence),
        }

    def _collect_memory(self, builder: "_ProfileBuilder") -> None:
        try:
            snapshot = self._memory_service.read_snapshot()
        except Exception as exc:
            builder.warn(f"memory: {exc}")
            return

        summary = _get(snapshot, "summary", "")
        profile = _get(snapshot, "profile", "")
        updated_at = _latest_iso(
            _get(snapshot, "summary_updated_at", None),
            _get(snapshot, "profile_updated_at", None),
        )
        count = int(bool(summary)) + int(bool(profile))
        if not count:
            return

        builder.add_source(
            LearnerProfileSource(
                source_id="memory",
                label="长期记忆",
                kind="memory",
                evidence_count=count,
                updated_at=updated_at,
                confidence=0.45,
            )
        )
        text = "\n".join(part for part in [profile, summary] if part).strip()
        builder.add_evidence(
            LearnerEvidencePreview(
                evidence_id="memory.snapshot",
                source_id="memory",
                source_label="长期记忆",
                title="SUMMARY / PROFILE",
                summary=_short(text, 220),
                created_at=updated_at,
            )
        )
        for goal in _extract_goal_lines(text):
            builder.add_goal(goal, "memory", 0.45)
        for pref in _infer_preferences(text):
            builder.add_preference(pref, "memory", 0.38)
        for weak in _extract_weak_lines(text):
            builder.add_weak_point(weak, "memory", reason="长期记忆中出现的待补强点", confidence=0.42)

    def _collect_guide_memory(self, builder: "_ProfileBuilder") -> None:
        try:
            memory = self._guide_manager.build_learner_memory(refresh=True)
        except Exception as exc:
            builder.warn(f"guide learner memory: {exc}")
            return
        if not isinstance(memory, dict) or not memory.get("success", True):
            return

        evidence_count = _as_int(memory.get("evidence_count"), 0)
        session_count = _as_int(memory.get("session_count"), 0)
        if evidence_count <= 0 and session_count <= 0:
            return

        builder.add_source(
            LearnerProfileSource(
                source_id="guide.memory",
                label="导学长期画像",
                kind="guide_memory",
                evidence_count=max(evidence_count, session_count),
                updated_at=_timestamp_to_iso(memory.get("last_activity_at")) or _now_iso(),
                confidence=_clamp(_as_float(memory.get("confidence"), 0.45), 0.25, 0.9),
            )
        )
        builder.level = str(memory.get("suggested_level") or builder.level or "unknown")
        builder.time_budget_minutes = _as_int(memory.get("preferred_time_budget_minutes"), builder.time_budget_minutes)
        if memory.get("summary"):
            builder.summary_candidates.append(str(memory.get("summary")))
        for item in _ranked_labels(memory.get("recent_goals")):
            builder.add_goal(item, "guide.memory", 0.62)
        for item in _ranked_labels(memory.get("top_preferences")):
            builder.add_preference(item, "guide.memory", 0.62)
        for item in _ranked_labels(memory.get("persistent_weak_points")):
            builder.add_weak_point(item, "guide.memory", reason="多次导学证据中重复出现", confidence=0.72)
        for item in _ranked_labels(memory.get("common_mistakes")):
            builder.add_weak_point(item, "guide.memory", reason="导学练习中的常见错误", confidence=0.68)
        for item in _ranked_labels(memory.get("strengths")):
            builder.add_strength(item, "guide.memory", 0.65)
        for item in memory.get("next_guidance") or []:
            builder.add_recommendation(str(item), "guide.memory")

    def _collect_guide_sessions(self, builder: "_ProfileBuilder") -> None:
        try:
            summaries = self._guide_manager.list_sessions()
        except Exception as exc:
            builder.warn(f"guide sessions: {exc}")
            return
        if not summaries:
            return

        recent = sorted(
            [item for item in summaries if isinstance(item, dict)],
            key=lambda item: _as_float(item.get("updated_at"), 0.0),
            reverse=True,
        )[:10]
        builder.add_source(
            LearnerProfileSource(
                source_id="guide.sessions",
                label="导学会话",
                kind="guide_session",
                evidence_count=len(recent),
                updated_at=_timestamp_to_iso(recent[0].get("updated_at")) if recent else None,
                confidence=0.58,
            )
        )
        for summary in recent:
            session_id = str(summary.get("session_id") or "").strip()
            if not session_id:
                continue
            try:
                session = self._guide_manager.get_session(session_id)
            except Exception as exc:
                builder.warn(f"guide session {session_id}: {exc}")
                continue
            if not isinstance(session, dict):
                continue
            source_id = "guide.sessions"
            title = str(session.get("goal") or summary.get("goal") or "导学任务")
            builder.add_goal(title, source_id, 0.55)
            profile = _dict(session.get("profile"))
            if profile.get("level") and builder.level in {"", "unknown"}:
                builder.level = str(profile.get("level"))
            if profile.get("time_budget_minutes"):
                builder.time_budget_minutes = _as_int(profile.get("time_budget_minutes"), builder.time_budget_minutes)
            for pref in profile.get("preferences") or []:
                builder.add_preference(str(pref), source_id, 0.52)
            for weak in profile.get("weak_points") or []:
                builder.add_weak_point(str(weak), source_id, reason="导学会话建模出的薄弱点", confidence=0.58)
            node_titles = {
                str(node.get("node_id")): str(node.get("title") or node.get("node_id"))
                for node in _dict(session.get("course_map")).get("nodes", [])
                if isinstance(node, dict)
            }
            for node_id, mastery in _dict(session.get("mastery")).items():
                item = _dict(mastery)
                score = _as_float(item.get("score"), None)
                status = str(item.get("status") or "unknown")
                title_for_node = node_titles.get(str(node_id), str(node_id))
                builder.add_mastery(
                    concept_id=str(node_id),
                    title=title_for_node,
                    score=score,
                    status=status,
                    source_id=source_id,
                    evidence_count=_as_int(item.get("evidence_count"), 0),
                    updated_at=_timestamp_to_iso(item.get("last_updated")),
                )
                if status == "needs_support" or (score is not None and score < 0.55 and _as_int(item.get("evidence_count"), 0)):
                    builder.add_weak_point(title_for_node, source_id, reason="导学掌握度偏低", confidence=0.68)
                elif status == "mastered" or (score is not None and score >= 0.82):
                    builder.add_strength(title_for_node, source_id, 0.62)
            for evidence in (session.get("evidence") or [])[-8:]:
                if not isinstance(evidence, dict):
                    continue
                builder.add_evidence(
                    LearnerEvidencePreview(
                        evidence_id=f"guide.{session_id}.{evidence.get('evidence_id') or len(builder.evidence_preview)}",
                        source_id=source_id,
                        source_label="导学会话",
                        title=title,
                        summary=_short(str(evidence.get("reflection") or evidence.get("type") or "学习证据"), 180),
                        created_at=_timestamp_to_iso(evidence.get("created_at")),
                        score=_as_float(evidence.get("score"), None),
                        metadata={
                            "session_id": session_id,
                            "task_id": evidence.get("task_id"),
                            "mistake_types": evidence.get("mistake_types") or [],
                        },
                    )
                )

    async def _collect_question_notebook(self, builder: "_ProfileBuilder") -> None:
        try:
            result = self._store.list_notebook_entries(limit=200, offset=0)
            if inspect.isawaitable(result):
                result = await result
        except Exception as exc:
            builder.warn(f"question notebook: {exc}")
            return

        items = result.get("items") if isinstance(result, dict) else result
        entries = [item for item in (items or []) if isinstance(item, dict)]
        if not entries:
            return

        latest = max((_as_float(item.get("updated_at") or item.get("created_at"), 0.0) for item in entries), default=0.0)
        builder.add_source(
            LearnerProfileSource(
                source_id="question_notebook",
                label="题目本",
                kind="assessment",
                evidence_count=len(entries),
                updated_at=_timestamp_to_iso(latest),
                confidence=0.72,
            )
        )
        groups: dict[str, dict[str, Any]] = {}
        scored_total = 0
        correct_total = 0
        for item in entries:
            labels = _entry_labels(item)
            scored = item.get("is_correct") is not None
            if scored:
                scored_total += 1
                correct_total += int(bool(item.get("is_correct")))
            for label in labels:
                group = groups.setdefault(label, {"total": 0, "scored": 0, "correct": 0})
                group["total"] += 1
                if scored:
                    group["scored"] += 1
                    group["correct"] += int(bool(item.get("is_correct")))
            builder.add_evidence(
                LearnerEvidencePreview(
                    evidence_id=f"question.{item.get('id')}",
                    source_id="question_notebook",
                    source_label="题目本",
                    title=_short(str(item.get("question") or "题目记录"), 80),
                    summary=_question_summary(item),
                    created_at=_timestamp_to_iso(item.get("updated_at") or item.get("created_at")),
                    score=1.0 if item.get("is_correct") is True else (0.0 if item.get("is_correct") is False else None),
                    metadata={
                        "question_type": item.get("question_type"),
                        "difficulty": item.get("difficulty"),
                        "bookmarked": bool(item.get("bookmarked")),
                        "concepts": labels,
                    },
                )
            )

        if scored_total:
            builder.assessment_accuracy = round(correct_total / scored_total, 3)
        for label, stats in groups.items():
            if stats["scored"]:
                score = stats["correct"] / stats["scored"]
                status = "mastered" if score >= 0.82 else ("needs_support" if score < 0.65 else "developing")
                builder.add_mastery(
                    concept_id=_slug(label),
                    title=label,
                    score=round(score, 3),
                    status=status,
                    source_id="question_notebook",
                    evidence_count=stats["scored"],
                    updated_at=_timestamp_to_iso(latest),
                )
                if score < 0.65 and stats["scored"] >= 2:
                    builder.add_weak_point(
                        label,
                        "question_notebook",
                        reason=f"题目本正确率 {round(score * 100)}%",
                        confidence=0.76,
                        evidence_count=stats["scored"],
                    )

    def _collect_notebooks(self, builder: "_ProfileBuilder") -> None:
        try:
            notebooks = self._notebook_manager.list_notebooks()
        except Exception as exc:
            builder.warn(f"notebook: {exc}")
            return
        if not notebooks:
            return

        recent = sorted(notebooks, key=lambda item: _as_float(item.get("updated_at"), 0.0), reverse=True)[:5]
        record_count = sum(_as_int(item.get("record_count"), 0) for item in recent)
        builder.add_source(
            LearnerProfileSource(
                source_id="notebook",
                label="学习笔记",
                kind="notebook",
                evidence_count=record_count,
                updated_at=_timestamp_to_iso(recent[0].get("updated_at")),
                confidence=0.42,
            )
        )
        for notebook in recent:
            notebook_id = str(notebook.get("id") or "")
            try:
                detail = self._notebook_manager.get_notebook(notebook_id)
            except Exception:
                detail = None
            if not isinstance(detail, dict):
                continue
            for record in (detail.get("records") or [])[-10:]:
                if not isinstance(record, dict):
                    continue
                builder.add_evidence(
                    LearnerEvidencePreview(
                        evidence_id=f"notebook.{notebook_id}.{record.get('id')}",
                        source_id="notebook",
                        source_label="学习笔记",
                        title=_short(str(record.get("title") or notebook.get("name") or "笔记记录"), 80),
                        summary=_short(str(record.get("summary") or record.get("user_query") or ""), 180),
                        created_at=_timestamp_to_iso(record.get("created_at") or record.get("updated_at")),
                        metadata={
                            "notebook_id": notebook_id,
                            "record_type": record.get("type"),
                        },
                    )
                )

    def _collect_evidence_ledger(self, builder: "_ProfileBuilder") -> None:
        try:
            result = self._evidence_service.list_events(limit=300)
        except Exception as exc:
            builder.warn(f"evidence ledger: {exc}")
            return

        events = [item for item in result.get("items", []) if isinstance(item, dict)]
        if not events:
            return

        summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
        builder.add_source(
            LearnerProfileSource(
                source_id="evidence",
                label="学习证据账本",
                kind="evidence_ledger",
                evidence_count=len(events),
                updated_at=_timestamp_to_iso(summary.get("latest_event_at")),
                confidence=0.82,
            )
        )

        mastery_groups: dict[str, dict[str, Any]] = {}
        for event in events:
            source = str(event.get("source") or "")
            source_id = f"evidence.{source}" if source else "evidence"
            title = _normalize_label(event.get("title") or event.get("object_id") or "学习活动")
            score = _as_float(event.get("score"), None)
            object_type = str(event.get("object_type") or "")
            object_id = str(event.get("object_id") or event.get("node_id") or title)
            concept_labels = _event_concept_labels(event)
            if source == "profile_calibration" or object_type == "profile_claim":
                builder.apply_calibration(event)
                builder.add_evidence(
                    LearnerEvidencePreview(
                        evidence_id=str(event.get("id") or ""),
                        source_id="evidence.profile_calibration",
                        source_label="profile_calibration",
                        title=title,
                        summary=_short(str(event.get("summary") or event.get("reflection") or ""), 180),
                        created_at=_timestamp_to_iso(event.get("created_at")),
                        metadata={
                            "verb": event.get("verb"),
                            "object_type": object_type,
                            "ledger": True,
                            "calibration": True,
                        },
                    )
                )
                continue
            event_confidence = _clamp(_as_float(event.get("confidence"), 0.5) or 0.5, 0.0, 1.0)
            if object_type == "learning_goal":
                builder.add_goal(title, source_id, min(0.62, event_confidence))
            elif object_type == "learning_blocker":
                builder.add_weak_point(
                    title,
                    source_id,
                    reason="Learner stated this blocker in conversation.",
                    confidence=min(0.68, event_confidence),
                )
            elif object_type == "learning_preference":
                builder.add_preference(str(event.get("resource_type") or title), source_id, min(0.62, event_confidence))
            resource_type = str(event.get("resource_type") or "")
            verb = str(event.get("verb") or "").strip().lower()
            if resource_type and verb in {"viewed", "saved", "answered", "completed"}:
                builder.add_preference(resource_type, "evidence", min(0.58, max(0.32, event_confidence)))
            for mistake in event.get("mistake_types") or []:
                mistake_label = str(mistake)
                if mistake_label.startswith("concept:"):
                    continue
                builder.add_weak_point(mistake_label, "evidence", reason="证据账本记录的错误类型", confidence=0.72)
            if event.get("is_correct") is False or (score is not None and score < 0.65):
                for label in concept_labels or [title]:
                    builder.add_weak_point(label, "evidence", reason="证据账本中的低分/错误记录", confidence=0.7)
            elif score is not None and score >= 0.85:
                for label in concept_labels or [title]:
                    builder.add_strength(label, "evidence", 0.62)
            if score is not None and object_id:
                for label in concept_labels or [object_id]:
                    group_id = _slug(label)
                    if not group_id:
                        continue
                    group_title = label if concept_labels else title
                    group = mastery_groups.setdefault(group_id, {"title": group_title, "scores": []})
                    group["scores"].append(score)
            builder.add_evidence(
                LearnerEvidencePreview(
                    evidence_id=str(event.get("id") or ""),
                    source_id=source_id,
                    source_label=str(event.get("source") or "学习证据"),
                    title=title,
                    summary=_short(str(event.get("summary") or event.get("reflection") or ""), 180),
                    created_at=_timestamp_to_iso(event.get("created_at")),
                    score=score,
                    metadata=_event_preview_metadata(event, object_type, resource_type, concept_labels),
                )
            )

        for object_id, group in mastery_groups.items():
            scores = [float(score) for score in group["scores"]]
            if not scores:
                continue
            average = round(sum(scores) / len(scores), 3)
            status = "mastered" if average >= 0.82 else ("needs_support" if average < 0.65 else "developing")
            builder.add_mastery(
                concept_id=str(object_id),
                title=str(group["title"]),
                score=average,
                status=status,
                source_id="evidence",
                evidence_count=len(scores),
                updated_at=None,
            )

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _is_stale(path: Path, ttl_seconds: int = 60) -> bool:
        try:
            return time.time() - path.stat().st_mtime > ttl_seconds
        except Exception:
            return True


class _ProfileBuilder:
    def __init__(self) -> None:
        self.sources: dict[str, LearnerProfileSource] = {}
        self.evidence_preview: list[LearnerEvidencePreview] = []
        self.goals: dict[str, LearnerProfileClaim] = {}
        self.preferences: dict[str, LearnerProfileClaim] = {}
        self.strengths: dict[str, LearnerProfileClaim] = {}
        self.weak_points: dict[str, LearnerWeakPoint] = {}
        self.mastery: dict[str, LearnerMastery] = {}
        self.recommendations: list[str] = []
        self.summary_candidates: list[str] = []
        self.warnings: list[str] = []
        self.rejected_claims: dict[str, set[str]] = {}
        self.calibration_count = 0
        self.level = "unknown"
        self.time_budget_minutes = 30
        self.assessment_accuracy: float | None = None

    def warn(self, message: str) -> None:
        if message and message not in self.warnings:
            self.warnings.append(message)

    def add_source(self, source: LearnerProfileSource) -> None:
        current = self.sources.get(source.source_id)
        if not current:
            self.sources[source.source_id] = source
            return
        current.evidence_count = max(current.evidence_count, source.evidence_count)
        current.confidence = max(current.confidence, source.confidence)
        current.updated_at = _latest_iso(current.updated_at, source.updated_at)

    def add_evidence(self, evidence: LearnerEvidencePreview) -> None:
        if not evidence.title:
            return
        self.evidence_preview.append(evidence)

    def add_goal(self, value: str, source_id: str, confidence: float) -> None:
        self._add_claim(self.goals, "goal", value, source_id, confidence)

    def add_preference(self, value: str, source_id: str, confidence: float) -> None:
        self._add_claim(self.preferences, "preference", value, source_id, confidence)

    def add_strength(self, value: str, source_id: str, confidence: float) -> None:
        self._add_claim(self.strengths, "strength", value, source_id, confidence)

    def add_recommendation(self, value: str, source_id: str) -> None:
        text = _short(value, 140)
        if not text:
            return
        if text not in self.recommendations:
            self.recommendations.append(text)
        self._touch_source_evidence(source_id, 1)

    def apply_calibration(self, event: dict[str, Any]) -> None:
        metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
        action = str(metadata.get("action") or event.get("verb") or "").lower()
        claim_type = self._normalize_claim_type(str(metadata.get("claim_type") or "profile_claim"))
        value = _normalize_label(metadata.get("value") or event.get("title") or event.get("object_id") or "")
        corrected = _normalize_label(metadata.get("corrected_value") or "")
        if not value and not corrected:
            return
        self.calibration_count += 1
        self.add_source(
            LearnerProfileSource(
                source_id="profile_calibration",
                label="Profile calibration",
                kind="user_calibration",
                evidence_count=self.calibration_count,
                updated_at=_timestamp_to_iso(event.get("created_at")),
                confidence=1.0,
            )
        )
        if action in {"reject", "rejected_profile"}:
            self.reject_claim(claim_type, value)
            return
        if action in {"correct", "corrected_profile"}:
            self.reject_claim(claim_type, value)
            if corrected:
                self._add_calibrated_claim(claim_type, corrected)
            return
        if value:
            self._add_calibrated_claim(claim_type, value)

    def reject_claim(self, claim_type: str, value: str) -> None:
        normalized = self._normalize_claim_type(claim_type)
        label = _normalize_label(value)
        if not label:
            return
        self.rejected_claims.setdefault(normalized, set()).add(label.lower())

    def _add_calibrated_claim(self, claim_type: str, value: str) -> None:
        normalized = self._normalize_claim_type(claim_type)
        if normalized in {"profile_overview", "overview", "summary", "current_focus"}:
            text = _short(value, 320)
            if text:
                self.summary_candidates.insert(0, text)
                self.add_goal(_short(text, 90), "profile_calibration", 1.0)
        elif normalized == "goal":
            self.add_goal(value, "profile_calibration", 1.0)
        elif normalized == "preference":
            self.add_preference(value, "profile_calibration", 1.0)
        elif normalized == "strength":
            self.add_strength(value, "profile_calibration", 1.0)
        elif normalized == "weak_point":
            self.add_weak_point(value, "profile_calibration", reason="User calibrated profile claim", confidence=1.0)
        elif normalized == "mastery":
            self.add_mastery(
                concept_id=value,
                title=value,
                score=None,
                status="confirmed",
                source_id="profile_calibration",
                evidence_count=1,
                updated_at=None,
            )
        else:
            self.add_goal(value, "profile_calibration", 1.0)

    @staticmethod
    def _normalize_claim_type(value: str) -> str:
        text = str(value or "").strip().lower().replace("-", "_")
        aliases = {
            "weak": "weak_point",
            "weakpoint": "weak_point",
            "weak_points": "weak_point",
            "profile": "profile_overview",
            "profile_claim": "profile_overview",
            "overview_claim": "profile_overview",
            "focus": "current_focus",
            "pref": "preference",
            "preferences": "preference",
            "goals": "goal",
            "strengths": "strength",
        }
        return aliases.get(text, text or "profile_claim")

    def add_weak_point(
        self,
        value: str,
        source_id: str,
        *,
        reason: str = "",
        confidence: float = 0.55,
        evidence_count: int = 1,
    ) -> None:
        label = _normalize_label(value)
        if not label:
            return
        item = self.weak_points.get(label)
        if not item:
            item = LearnerWeakPoint(label=label)
            self.weak_points[label] = item
        if source_id not in item.source_ids:
            item.source_ids.append(source_id)
        item.evidence_count += max(1, evidence_count)
        item.confidence = max(item.confidence, _clamp(confidence, 0.0, 1.0))
        item.reason = item.reason or reason
        item.severity = "high" if item.confidence >= 0.72 or item.evidence_count >= 3 else "medium"
        item.updated_at = _latest_iso(item.updated_at, self._source_updated_at(source_id))
        self._touch_source_evidence(source_id, max(1, evidence_count))

    def add_mastery(
        self,
        *,
        concept_id: str,
        title: str,
        score: float | None,
        status: str,
        source_id: str,
        evidence_count: int = 0,
        updated_at: str | None = None,
    ) -> None:
        concept_key = _slug(concept_id or title)
        if not concept_key:
            return
        item = self.mastery.get(concept_key)
        if not item:
            item = LearnerMastery(concept_id=concept_key, title=_normalize_label(title) or concept_key)
            self.mastery[concept_key] = item
        if source_id not in item.source_ids:
            item.source_ids.append(source_id)
        item.evidence_count += max(0, evidence_count)
        if score is not None:
            item.score = score if item.score is None else round((item.score + score) / 2, 3)
        if status and status != "unknown":
            item.status = status
        item.updated_at = _latest_iso(item.updated_at, updated_at)

    def _add_claim(
        self,
        bucket: dict[str, LearnerProfileClaim],
        label: str,
        value: str,
        source_id: str,
        confidence: float,
    ) -> None:
        text = _normalize_label(value)
        if not text:
            return
        item = bucket.get(text)
        if not item:
            item = LearnerProfileClaim(label=label, value=text)
            bucket[text] = item
        if source_id not in item.source_ids:
            item.source_ids.append(source_id)
        item.evidence_count += 1
        item.confidence = max(item.confidence, _clamp(confidence, 0.0, 1.0))
        self._touch_source_evidence(source_id, 1)

    def _touch_source_evidence(self, source_id: str, amount: int) -> None:
        source = self.sources.get(source_id)
        if source:
            source.evidence_count = max(source.evidence_count, amount)

    def _source_updated_at(self, source_id: str) -> str | None:
        source = self.sources.get(source_id)
        return source.updated_at if source else None

    def _is_rejected(self, claim_type: str, value: str) -> bool:
        label = _normalize_label(value).lower()
        if not label:
            return False
        normalized = self._normalize_claim_type(claim_type)
        return label in self.rejected_claims.get(normalized, set())

    def _filtered_claims(
        self,
        bucket: dict[str, LearnerProfileClaim],
        claim_type: str,
    ) -> dict[str, LearnerProfileClaim]:
        return {
            key: item
            for key, item in bucket.items()
            if not self._is_rejected(claim_type, item.value)
        }

    def build(self) -> dict[str, Any]:
        sources = [asdict(item) for item in sorted(self.sources.values(), key=lambda item: item.source_id)]
        evidence = sorted(
            self.evidence_preview,
            key=lambda item: item.created_at or "",
            reverse=True,
        )[:80]
        evidence_dicts = [asdict(item) for item in evidence]
        weak_points = sorted(
            [item for item in self.weak_points.values() if not self._is_rejected("weak_point", item.label)],
            key=lambda item: (-item.confidence, -item.evidence_count, item.label),
        )[:12]
        mastery = sorted(
            [
                item for item in self.mastery.values()
                if not self._is_rejected("mastery", item.title)
                and not self._is_rejected("mastery", item.concept_id)
            ],
            key=lambda item: (
                1 if item.status == "needs_support" else 0,
                -(item.score if item.score is not None else -1),
                item.title,
            ),
            reverse=True,
        )[:18]
        goals = _claims_to_values(self._filtered_claims(self.goals, "goal"), 6)
        preferences = _claims_to_values(self._filtered_claims(self.preferences, "preference"), 8)
        strengths = _claims_to_values(self._filtered_claims(self.strengths, "strength"), 8)
        source_count = len(sources)
        evidence_count = len(evidence_dicts)
        confidence = _clamp(round(0.16 * source_count + min(evidence_count, 30) * 0.018, 2), 0.05, 0.92)
        current_focus = goals[0] if goals else "还没有形成明确的当前学习目标"
        summary = self.summary_candidates[0] if self.summary_candidates else self._fallback_summary(goals, weak_points)

        recommendations = list(self.recommendations[:8])
        if weak_points and not any("补" in item or "薄弱" in item for item in recommendations):
            recommendations.insert(0, f"优先补齐「{weak_points[0].label}」，再推进更高难度任务。")
        if not recommendations:
            recommendations.append("先完成一次导学任务或交互练习，系统会据此沉淀更可靠的画像。")
        next_action = self._next_action(
            goals=goals,
            weak_points=weak_points,
            mastery=mastery,
            recommendations=recommendations,
        )

        snapshot = LearnerProfileSnapshot(
            version=1,
            generated_at=_now_iso(),
            confidence=confidence,
            overview={
                "current_focus": current_focus,
                "suggested_level": self.level or "unknown",
                "preferred_time_budget_minutes": self.time_budget_minutes,
                "assessment_accuracy": self.assessment_accuracy,
                "summary": summary,
            },
            stable_profile={
                "goals": goals,
                "preferences": preferences,
                "strengths": strengths,
                "constraints": [],
            },
            learning_state={
                "weak_points": [asdict(item) for item in weak_points],
                "mastery": [asdict(item) for item in mastery],
            },
            next_action=next_action,
            recommendations=recommendations[:8],
            sources=sources,
            evidence_preview=evidence_dicts,
            data_quality={
                "source_count": source_count,
                "evidence_count": evidence_count,
                "warnings": self.warnings[:12],
                "read_only": self.calibration_count == 0,
                "calibration_count": self.calibration_count,
            },
        )
        return asdict(snapshot)

    def _next_action(
        self,
        *,
        goals: list[str],
        weak_points: list[LearnerWeakPoint],
        mastery: list[LearnerMastery],
        recommendations: list[str],
    ) -> dict[str, Any]:
        minutes = max(5, min(int(self.time_budget_minutes or 30), 90))
        if weak_points:
            item = weak_points[0]
            resource_hint = self._preferred_resource_hint()
            return {
                "kind": "remediate",
                "title": f"先补齐「{item.label}」",
                "summary": item.reason or f"已有 {item.evidence_count} 条证据指向这个薄弱点，建议先用一个短任务把它稳住。",
                "primary_label": "进入导学补基",
                "href": "/guide",
                "estimated_minutes": min(minutes, 20),
                "source_type": "weak_point",
                "source_label": item.label,
                "confidence": item.confidence,
                "suggested_prompt": (
                    f"围绕「{item.label}」安排一个 {min(minutes, 20)} 分钟补基任务，"
                    f"先生成{resource_hint}，再用 3 道小题确认理解。"
                ),
            }

        needs_support = next(
            (item for item in mastery if item.status in {"needs_support", "not_started", "unknown"}),
            None,
        )
        if needs_support is not None:
            return {
                "kind": "practice",
                "title": f"用练习确认「{needs_support.title}」",
                "summary": "这个知识点还缺少稳定证据，先做一组低门槛交互题，比继续看长资料更有效。",
                "primary_label": "进入导学练习",
                "href": "/guide",
                "estimated_minutes": min(minutes, 15),
                "source_type": "mastery",
                "source_label": needs_support.title,
                "confidence": 0.55,
                "suggested_prompt": (
                    f"为「{needs_support.title}」生成 {min(minutes, 15)} 分钟交互练习，"
                    "包含选择、判断、填空和一句话解释。"
                ),
            }

        if goals:
            return {
                "kind": "continue",
                "title": f"继续推进「{goals[0]}」",
                "summary": recommendations[0] if recommendations else "画像已经有了方向，下一步适合进入导学路线继续推进。",
                "primary_label": "继续导学",
                "href": "/guide",
                "estimated_minutes": minutes,
                "source_type": "goal",
                "source_label": goals[0],
                "confidence": min(0.8, self.assessment_accuracy or 0.6),
                "suggested_prompt": f"基于我的学习画像，继续规划「{goals[0]}」的下一步学习任务。",
            }

        return {
            "kind": "calibrate",
            "title": "先让系统认识你",
            "summary": "画像证据还不够。用一句话告诉系统你要学什么、哪里卡住、偏好什么资源。",
            "primary_label": "去导学画像",
            "href": "/guide",
            "estimated_minutes": 5,
            "source_type": "profile",
            "source_label": "画像校准",
            "confidence": 0.2,
            "suggested_prompt": "我想建立学习画像：我的目标是……，当前卡点是……，我更喜欢图解/练习/视频。",
        }

    def _preferred_resource_hint(self) -> str:
        values = {item.value.lower() for item in self.preferences.values()}
        if "external_video" in values or "public_video" in values or "公开视频" in values or "公开课" in values:
            return "精选公开视频"
        if "video" in values or "short_video" in values or "短视频" in values:
            return "短视频讲解"
        if "practice" in values or "quiz" in values or "练习" in values:
            return "入门练习"
        if "visual" in values or "图解" in values:
            return "图解"
        return "图解"

    @staticmethod
    def _fallback_summary(goals: list[str], weak_points: list[LearnerWeakPoint]) -> str:
        if goals and weak_points:
            return f"当前围绕「{goals[0]}」学习，主要需要补强「{weak_points[0].label}」。"
        if goals:
            return f"当前学习重点是「{goals[0]}」。"
        if weak_points:
            return f"系统已识别出需要优先补强的点：「{weak_points[0].label}」。"
        return "画像正在等待更多学习证据。"


def _claims_to_values(bucket: dict[str, LearnerProfileClaim], limit: int) -> list[str]:
    return [
        item.value
        for item in sorted(bucket.values(), key=lambda item: (-item.confidence, -item.evidence_count, item.value))[:limit]
    ]


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _get(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _readable_timestamp(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return _timestamp_to_iso(value)


def _timestamp_to_iso(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = float(text)
        except ValueError:
            return text
        value = parsed
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    try:
        return datetime.fromtimestamp(number).astimezone().isoformat()
    except Exception:
        return None


def _latest_iso(*values: Any) -> str | None:
    parsed: list[tuple[float, str]] = []
    for value in values:
        iso = _readable_timestamp(value)
        if not iso:
            continue
        try:
            ts = datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
        except Exception:
            ts = 0.0
        parsed.append((ts, iso))
    if not parsed:
        return None
    return sorted(parsed, key=lambda item: item[0], reverse=True)[0][1]


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _short(value: str, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _normalize_label(value: Any) -> str:
    text = " ".join(str(value or "").replace("\r", "\n").split())
    return _short(text.strip(" -*#：:"), 80)


def _slug(value: Any) -> str:
    text = _normalize_label(value).lower()
    keep = []
    for char in text:
        if char.isalnum():
            keep.append(char)
        elif keep and keep[-1] != "-":
            keep.append("-")
    return "".join(keep).strip("-")[:80]


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float | None = 0.0) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _ranked_labels(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    labels: list[str] = []
    for item in value:
        if isinstance(item, dict):
            label = item.get("label") or item.get("goal") or item.get("title")
        else:
            label = item
        normalized = _normalize_label(label)
        if normalized and normalized not in labels:
            labels.append(normalized)
    return labels


def _extract_goal_lines(text: str) -> list[str]:
    goals: list[str] = []
    for raw in text.splitlines():
        line = _normalize_label(raw)
        if not line or len(line) < 4:
            continue
        lower = line.lower()
        if any(token in lower for token in ["goal", "current focus", "正在", "目标", "学习", "掌握"]):
            if line not in goals:
                goals.append(line)
        if len(goals) >= 5:
            break
    return goals


def _extract_weak_lines(text: str) -> list[str]:
    weak: list[str] = []
    for raw in text.splitlines():
        line = _normalize_label(raw)
        if not line or len(line) < 3:
            continue
        lower = line.lower()
        if any(token in lower for token in ["weak", "mistake", "open question", "薄弱", "卡点", "错误", "待解决"]):
            if line not in weak:
                weak.append(line)
        if len(weak) >= 6:
            break
    return weak


def _infer_preferences(text: str) -> list[str]:
    lowered = text.lower()
    candidates = [
        ("图解", ["图解", "可视化", "visual"]),
        ("练习驱动", ["练习", "题目", "quiz", "practice"]),
        ("短视频讲解", ["视频", "动画", "manim", "video"]),
        ("分步骤解释", ["步骤", "step", "推导", "拆解"]),
        ("代码示例", ["代码", "python", "c++", "编程"]),
    ]
    return [label for label, keys in candidates if any(key in lowered for key in keys)]


def _entry_labels(item: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    for key in (
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
    ):
        for label in _labels_from_value(item.get(key)):
            if label and label not in labels:
                labels.append(label)
    if not labels and item.get("question_type"):
        labels.append(f"题型：{_normalize_label(item.get('question_type'))}")
    if item.get("difficulty"):
        labels.append(f"难度：{_normalize_label(item.get('difficulty'))}")
    return [label for label in labels if label] or ["未分类题目"]


def _event_concept_labels(event: dict[str, Any]) -> list[str]:
    metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
    labels: list[str] = []
    keys = (
        "concepts",
        "concept",
        "primary_concept",
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
    for source in (metadata, event):
        for key in keys:
            for label in _labels_from_value(source.get(key)):
                if label and label not in labels:
                    labels.append(label)
    for mistake in event.get("mistake_types") or []:
        text = str(mistake)
        if text.startswith("concept:"):
            label = _normalize_label(text.split(":", 1)[1])
            if label and label not in labels:
                labels.append(label)
    return labels[:8]


def _event_preview_metadata(
    event: dict[str, Any],
    object_type: str,
    resource_type: str,
    concept_labels: list[str],
) -> dict[str, Any]:
    raw_metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
    metadata: dict[str, Any] = {
        "verb": event.get("verb"),
        "object_type": object_type,
        "resource_type": resource_type,
        "ledger": True,
        "concepts": concept_labels,
    }
    for key in (
        "platform",
        "kind",
        "query",
        "fallback_search",
        "watch_plan",
        "reflection_prompt",
        "style_hint",
    ):
        value = raw_metadata.get(key)
        if value not in (None, "", [], {}):
            metadata[key] = value
    if event.get("duration_seconds") not in (None, ""):
        metadata["duration_seconds"] = event.get("duration_seconds")
    return metadata


def _labels_from_value(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        parts = [part.strip() for part in value.replace("；", ",").replace("，", ",").split(",")]
        return [_normalize_label(part) for part in parts if _normalize_label(part)]
    if isinstance(value, dict):
        for key in ("label", "name", "title", "value", "concept", "concept_id", "id"):
            label = _normalize_label(value.get(key))
            if label:
                return [label]
        return []
    if isinstance(value, (list, tuple, set)):
        labels: list[str] = []
        for item in value:
            for label in _labels_from_value(item):
                if label and label not in labels:
                    labels.append(label)
        return labels
    label = _normalize_label(value)
    return [label] if label else []


def _question_summary(item: dict[str, Any]) -> str:
    parts: list[str] = []
    if item.get("is_correct") is True:
        parts.append("回答正确")
    elif item.get("is_correct") is False:
        parts.append("回答错误")
    if item.get("user_answer"):
        parts.append(f"作答：{_short(str(item.get('user_answer')), 60)}")
    if item.get("explanation"):
        parts.append(f"解析：{_short(str(item.get('explanation')), 100)}")
    return "；".join(parts)


_learner_profile_service: LearnerProfileService | None = None


def get_learner_profile_service() -> LearnerProfileService:
    global _learner_profile_service
    if _learner_profile_service is None:
        _learner_profile_service = LearnerProfileService()
    return _learner_profile_service


def create_learner_profile_service(**kwargs: Any) -> LearnerProfileService:
    return LearnerProfileService(**kwargs)


__all__ = [
    "LearnerEvidencePreview",
    "LearnerMastery",
    "LearnerProfileClaim",
    "LearnerProfileService",
    "LearnerProfileSnapshot",
    "LearnerProfileSource",
    "LearnerWeakPoint",
    "create_learner_profile_service",
    "get_learner_profile_service",
]
