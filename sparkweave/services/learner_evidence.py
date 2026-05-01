"""Normalized learner evidence ledger.

P2 starts turning learner profile into an evidence-first system. The ledger is
append-only JSONL so it is easy to inspect, easy to back up, and safe to evolve
without touching the existing SQLite/session schemas.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
from pathlib import Path
import time
from typing import Any
import uuid

from sparkweave.services.paths import PathService, get_path_service


@dataclass
class LearnerEvidenceEvent:
    id: str
    source: str
    source_id: str = ""
    actor: str = "learner"
    verb: str = "observed"
    object_type: str = "learning_activity"
    object_id: str = ""
    title: str = ""
    summary: str = ""
    course_id: str = ""
    node_id: str = ""
    task_id: str = ""
    resource_type: str = ""
    score: float | None = None
    is_correct: bool | None = None
    duration_seconds: float | None = None
    confidence: float = 0.5
    reflection: str = ""
    mistake_types: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


class LearnerEvidenceService:
    """Append and query normalized learner evidence events."""

    def __init__(
        self,
        *,
        path_service: PathService | None = None,
        output_dir: str | Path | None = None,
    ) -> None:
        self._path_service = path_service or get_path_service()
        self._output_dir = Path(output_dir) if output_dir else self._path_service.get_user_root() / "learner_profile"
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._ledger_path = self._output_dir / "evidence.jsonl"

    @property
    def ledger_path(self) -> Path:
        return self._ledger_path

    def append_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        event = self._normalize_event(payload)
        self._append_jsonl(event)
        return event

    def append_events(self, payloads: list[dict[str, Any]], *, dedupe: bool = True) -> dict[str, Any]:
        existing_ids = {event.get("id") for event in self._read_all()} if dedupe else set()
        added: list[dict[str, Any]] = []
        skipped = 0
        for payload in payloads:
            event = self._normalize_event(payload)
            if dedupe and event["id"] in existing_ids:
                skipped += 1
                continue
            added.append(event)
            existing_ids.add(event["id"])
        if added:
            with self._ledger_path.open("a", encoding="utf-8") as handle:
                for event in added:
                    handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        return {"added": len(added), "skipped": skipped, "events": added}

    def list_events(
        self,
        *,
        source: str | None = None,
        verb: str | None = None,
        object_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        events = self._read_all()
        if source:
            events = [event for event in events if event.get("source") == source]
        if verb:
            events = [event for event in events if event.get("verb") == verb]
        if object_type:
            events = [event for event in events if event.get("object_type") == object_type]
        events.sort(key=lambda event: _as_float(event.get("created_at"), 0.0), reverse=True)
        total = len(events)
        start = max(0, int(offset or 0))
        end = start + max(1, min(int(limit or 100), 500))
        return {"items": events[start:end], "total": total, "summary": self.summarize(events)}

    def summarize(self, events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        items = events if events is not None else self._read_all()
        by_source: dict[str, int] = {}
        by_verb: dict[str, int] = {}
        by_object_type: dict[str, int] = {}
        scored = 0
        score_total = 0.0
        correct = 0
        answered = 0
        latest = 0.0
        for event in items:
            source = str(event.get("source") or "unknown")
            verb = str(event.get("verb") or "observed")
            object_type = str(event.get("object_type") or "learning_activity")
            by_source[source] = by_source.get(source, 0) + 1
            by_verb[verb] = by_verb.get(verb, 0) + 1
            by_object_type[object_type] = by_object_type.get(object_type, 0) + 1
            latest = max(latest, _as_float(event.get("created_at"), 0.0))
            score = _as_float(event.get("score"), None)
            if score is not None:
                scored += 1
                score_total += score
            if event.get("is_correct") is not None:
                answered += 1
                correct += int(bool(event.get("is_correct")))
        return {
            "event_count": len(items),
            "by_source": by_source,
            "by_verb": by_verb,
            "by_object_type": by_object_type,
            "average_score": round(score_total / scored, 3) if scored else None,
            "accuracy": round(correct / answered, 3) if answered else None,
            "latest_event_at": latest or None,
        }

    def rebuild_from_profile(self, profile: dict[str, Any], *, clear: bool = False) -> dict[str, Any]:
        if clear and self._ledger_path.exists():
            self._ledger_path.unlink()
        payloads = [self._event_from_preview(item) for item in profile.get("evidence_preview") or [] if isinstance(item, dict)]
        return self.append_events(payloads, dedupe=True)

    def clear(self) -> dict[str, Any]:
        if self._ledger_path.exists():
            self._ledger_path.unlink()
        return {"cleared": True}

    def _read_all(self) -> list[dict[str, Any]]:
        if not self._ledger_path.exists():
            return []
        events: list[dict[str, Any]] = []
        try:
            lines = self._ledger_path.read_text(encoding="utf-8").splitlines()
        except Exception:
            return []
        for line in lines:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if isinstance(payload, dict) and payload.get("id") and payload.get("source"):
                events.append(payload)
        return events

    def _append_jsonl(self, event: dict[str, Any]) -> None:
        with self._ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    def _normalize_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        source = _clean(payload.get("source") or payload.get("source_id") or "manual", 80)
        title = _clean(payload.get("title") or payload.get("object_id") or payload.get("summary") or "学习证据", 160)
        event = LearnerEvidenceEvent(
            id=_clean(payload.get("id") or f"ev_{uuid.uuid4().hex}", 120),
            source=source,
            source_id=_clean(payload.get("source_id") or "", 160),
            actor=_clean(payload.get("actor") or "learner", 40),
            verb=_clean(payload.get("verb") or "observed", 40),
            object_type=_clean(payload.get("object_type") or "learning_activity", 80),
            object_id=_clean(payload.get("object_id") or "", 160),
            title=title,
            summary=_clean(payload.get("summary") or "", 600),
            course_id=_clean(payload.get("course_id") or "", 120),
            node_id=_clean(payload.get("node_id") or "", 120),
            task_id=_clean(payload.get("task_id") or "", 120),
            resource_type=_clean(payload.get("resource_type") or "", 80),
            score=_as_float(payload.get("score"), None),
            is_correct=_as_bool_or_none(payload.get("is_correct")),
            duration_seconds=_as_float(payload.get("duration_seconds"), None),
            confidence=_clamp(_as_float(payload.get("confidence"), 0.5) or 0.5, 0.0, 1.0),
            reflection=_clean(payload.get("reflection") or "", 600),
            mistake_types=[_clean(item, 80) for item in payload.get("mistake_types") or [] if _clean(item, 80)],
            created_at=_as_timestamp(payload.get("created_at")),
            weight=max(0.0, _as_float(payload.get("weight"), 1.0) or 1.0),
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )
        return asdict(event)

    def _event_from_preview(self, item: dict[str, Any]) -> dict[str, Any]:
        source = _clean(item.get("source_id") or "profile_preview", 80)
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        return {
            "id": f"ev_preview_{_safe_id(item.get('evidence_id') or uuid.uuid4().hex)}",
            "source": source,
            "source_id": _clean(item.get("evidence_id") or "", 160),
            "verb": _verb_from_preview(item),
            "object_type": _object_type_from_preview(item),
            "object_id": _clean(metadata.get("task_id") or item.get("evidence_id") or "", 160),
            "title": item.get("title") or "学习证据",
            "summary": item.get("summary") or "",
            "score": item.get("score"),
            "confidence": 0.55,
            "created_at": item.get("created_at"),
            "metadata": {
                **metadata,
                "source_label": item.get("source_label"),
                "profile_preview": True,
            },
        }


def build_guide_task_event(
    *,
    session_id: str,
    task: dict[str, Any],
    evidence: dict[str, Any],
    session_goal: str = "",
    source: str = "guide_v2",
) -> dict[str, Any]:
    task_id = _clean(task.get("task_id") or evidence.get("task_id") or "", 120)
    evidence_id = _clean(evidence.get("evidence_id") or "", 120)
    metadata = evidence.get("metadata") if isinstance(evidence.get("metadata"), dict) else {}
    return {
        "id": f"ev_{_safe_id(source)}_{_safe_id(session_id)}_{_safe_id(task_id)}_{_safe_id(evidence_id)}",
        "source": source,
        "source_id": f"{session_id}:{task_id}:{evidence_id}",
        "verb": "completed",
        "object_type": str(evidence.get("type") or "guide_task"),
        "object_id": task_id,
        "title": task.get("title") or session_goal or "导学任务",
        "summary": evidence.get("reflection") or task.get("instruction") or "",
        "node_id": task.get("node_id") or "",
        "task_id": task_id,
        "score": evidence.get("score"),
        "confidence": 0.82,
        "reflection": evidence.get("reflection") or "",
        "mistake_types": evidence.get("mistake_types") or [],
        "created_at": evidence.get("created_at"),
        "metadata": {
            **metadata,
            "guide_session_id": session_id,
            "task_status": task.get("status"),
            "origin": task.get("origin"),
        },
    }


def build_guide_session_event(
    *,
    session: dict[str, Any],
    source: str = "guide_v2",
) -> dict[str, Any]:
    session_id = _clean(session.get("session_id") or "", 120)
    goal = _clean(session.get("goal") or "导学路线", 220)
    course_map = session.get("course_map") if isinstance(session.get("course_map"), dict) else {}
    metadata = course_map.get("metadata") if isinstance(course_map.get("metadata"), dict) else {}
    source_action = metadata.get("source_action") if isinstance(metadata.get("source_action"), dict) else {}
    source_label = _clean(source_action.get("source_label") or source_action.get("title") or "", 160)
    summary = (
        f"根据学习画像建议「{source_label}」创建导学路线。"
        if source_label
        else "创建新的导学路线。"
    )
    return {
        "id": f"ev_{_safe_id(source)}_{_safe_id(session_id)}_created",
        "source": source,
        "source_id": session_id,
        "verb": "planned",
        "object_type": "guide_session",
        "object_id": session_id,
        "title": goal,
        "summary": summary,
        "confidence": 0.72 if source_action else 0.55,
        "created_at": session.get("created_at"),
        "metadata": {
            "guide_session_id": session_id,
            "status": session.get("status"),
            "source_action": source_action,
            "created_from": metadata.get("created_from") or "",
        },
    }


def build_guide_resource_event(
    *,
    session_id: str,
    task: dict[str, Any],
    artifact: dict[str, Any],
    session_goal: str = "",
    source: str = "guide_v2",
) -> dict[str, Any]:
    task_id = _clean(task.get("task_id") or artifact.get("task_id") or "", 120)
    artifact_id = _clean(artifact.get("id") or uuid.uuid4().hex, 120)
    resource_type = _clean(artifact.get("type") or "", 80)
    result = artifact.get("result") if isinstance(artifact.get("result"), dict) else {}
    response = _clean(result.get("response") or "", 360)
    title = artifact.get("title") or task.get("title") or session_goal or "Guide resource"
    metadata = {
        "guide_session_id": session_id,
        "guide_task_id": task_id,
        "artifact_id": artifact_id,
        "capability": artifact.get("capability") or "",
        "artifact_status": artifact.get("status") or "",
        "resource_generated": True,
    }
    if isinstance(result.get("videos"), list):
        metadata["video_count"] = len(result["videos"])
    if isinstance(result.get("artifacts"), list):
        metadata["artifact_count"] = len(result["artifacts"])
    return {
        "id": f"ev_{_safe_id(source)}_resource_{_safe_id(session_id)}_{_safe_id(task_id)}_{_safe_id(artifact_id)}",
        "source": source,
        "source_id": f"{session_id}:{task_id}:{artifact_id}",
        "verb": "generated",
        "object_type": "resource",
        "object_id": artifact_id,
        "title": title,
        "summary": response or task.get("instruction") or session_goal or "",
        "node_id": task.get("node_id") or "",
        "task_id": task_id,
        "resource_type": resource_type,
        "confidence": 0.46,
        "created_at": artifact.get("created_at"),
        "weight": 0.35,
        "metadata": metadata,
    }


def build_quiz_answer_events(
    answers: list[dict[str, Any]],
    *,
    source: str,
    session_id: str,
    task_id: str = "",
    artifact_id: str = "",
    course_id: str = "",
    node_id: str = "",
    source_id_prefix: str = "",
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    prefix = source_id_prefix or session_id
    for index, answer in enumerate(answers, 1):
        question = _clean(answer.get("question") or "题目记录", 220)
        question_id = _clean(answer.get("question_id") or _safe_id(question) or str(index), 120)
        concepts = _extract_concept_labels(answer)
        primary_concept = concepts[0] if concepts else ""
        concept_id = _safe_id(primary_concept).lower() if primary_concept else ""
        is_correct = _as_bool_or_none(answer.get("is_correct"))
        score = 1.0 if is_correct is True else (0.0 if is_correct is False else None)
        question_type = _clean(answer.get("question_type") or "", 80)
        difficulty = _clean(answer.get("difficulty") or "", 80)
        mistake_types: list[str] = []
        if is_correct is False:
            if primary_concept:
                mistake_types.append(f"concept:{primary_concept}")
            if question_type:
                mistake_types.append(f"题型：{question_type}")
            if difficulty:
                mistake_types.append(f"难度：{difficulty}")
        summary_parts = []
        if answer.get("user_answer"):
            summary_parts.append(f"作答：{_clean(answer.get('user_answer'), 120)}")
        if answer.get("correct_answer"):
            summary_parts.append(f"参考答案：{_clean(answer.get('correct_answer'), 120)}")
        if answer.get("explanation"):
            summary_parts.append(f"解析：{_clean(answer.get('explanation'), 220)}")
        return_id = f"ev_quiz_{_safe_id(source)}_{_safe_id(prefix)}_{_safe_id(task_id)}_{_safe_id(artifact_id)}_{_safe_id(question_id)}"
        events.append(
            {
                "id": return_id,
                "source": source,
                "source_id": f"{prefix}:{question_id}",
                "verb": "answered",
                "object_type": "quiz",
                "object_id": concept_id or question_id,
                "title": question,
                "summary": "；".join(summary_parts),
                "course_id": course_id,
                "node_id": node_id,
                "task_id": task_id,
                "resource_type": "quiz",
                "score": score,
                "is_correct": is_correct,
                "confidence": 0.86,
                "mistake_types": mistake_types,
                "metadata": {
                    "question_type": question_type,
                    "difficulty": difficulty,
                    "artifact_id": artifact_id,
                    "session_id": session_id,
                    "question_id": question_id,
                    "concepts": concepts,
                    "primary_concept": primary_concept,
                    "concept_id": concept_id,
                    "options": answer.get("options") if isinstance(answer.get("options"), dict) else {},
                },
            }
        )
    return events


def _extract_concept_labels(payload: dict[str, Any]) -> list[str]:
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
    for key in keys:
        for label in _labels_from_value(payload.get(key)):
            if label and label not in labels:
                labels.append(label)
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        for key in keys:
            for label in _labels_from_value(metadata.get(key)):
                if label and label not in labels:
                    labels.append(label)
    return labels[:8]


def _labels_from_value(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        parts = [part.strip() for part in value.replace("；", ",").replace("，", ",").split(",")]
        return [_clean(part, 120) for part in parts if _clean(part, 120)]
    if isinstance(value, dict):
        for key in ("label", "name", "title", "value", "concept", "concept_id", "id"):
            label = _clean(value.get(key), 120)
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
    label = _clean(value, 120)
    return [label] if label else []


def build_notebook_record_event(
    *,
    record: dict[str, Any],
    notebook_ids: list[str],
    source: str = "notebook",
) -> dict[str, Any]:
    record_id = _clean(record.get("id") or uuid.uuid4().hex, 120)
    record_type = _clean(record.get("type") or "notebook_record", 80)
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    event_source = _clean(metadata.get("source") or source, 80)
    resource_type = _infer_notebook_resource_type(record_type, metadata)
    return {
        "id": f"ev_notebook_{_safe_id(record_id)}_{_safe_id('-'.join(notebook_ids))}",
        "source": event_source,
        "source_id": record_id,
        "verb": "saved",
        "object_type": "notebook_record",
        "object_id": record_id,
        "title": record.get("title") or "学习笔记",
        "summary": record.get("summary") or record.get("user_query") or "",
        "resource_type": resource_type,
        "created_at": record.get("created_at"),
        "confidence": 0.62,
        "metadata": {
            **metadata,
            "notebook_ids": notebook_ids,
            "record_type": record_type,
            "inferred_resource_type": resource_type,
            "kb_name": record.get("kb_name"),
        },
    }


def _infer_notebook_resource_type(record_type: str, metadata: dict[str, Any]) -> str:
    external_video = metadata.get("external_video")
    if isinstance(external_video, dict) and (
        external_video.get("render_type") == "external_video" or isinstance(external_video.get("videos"), list)
    ):
        return "external_video"
    if isinstance(metadata.get("math_animator"), dict):
        return "video"
    if isinstance(metadata.get("visualize"), dict):
        return "visual"
    quiz = metadata.get("quiz")
    if isinstance(quiz, dict) and quiz.get("count"):
        return "quiz"
    capability = _clean(metadata.get("capability") or "", 80)
    if capability == "math_animator":
        return "video"
    if capability == "visualize":
        return "visual"
    if capability == "deep_question" or record_type == "question":
        return "quiz"
    if capability == "deep_research" or record_type == "research":
        return "research"
    return record_type or "notebook_record"


def build_profile_calibration_event(
    *,
    action: str,
    claim_type: str,
    value: str,
    corrected_value: str = "",
    note: str = "",
    source_id: str = "",
) -> dict[str, Any]:
    normalized_action = _clean(action, 40).lower()
    if normalized_action not in {"confirm", "reject", "correct"}:
        normalized_action = "confirm"
    verb = {
        "confirm": "confirmed_profile",
        "reject": "rejected_profile",
        "correct": "corrected_profile",
    }[normalized_action]
    normalized_type = _clean(claim_type or "profile_claim", 80)
    original = _clean(value, 180)
    corrected = _clean(corrected_value, 180)
    title = corrected if normalized_action == "correct" and corrected else original
    return {
        "id": f"ev_profile_calibration_{_safe_id(normalized_type)}_{_safe_id(original)}_{uuid.uuid4().hex[:10]}",
        "source": "profile_calibration",
        "source_id": source_id or f"{normalized_type}:{original}",
        "actor": "learner",
        "verb": verb,
        "object_type": "profile_claim",
        "object_id": _safe_id(original),
        "title": title or "profile calibration",
        "summary": note,
        "confidence": 1.0,
        "reflection": note,
        "metadata": {
            "action": normalized_action,
            "claim_type": normalized_type,
            "value": original,
            "corrected_value": corrected,
        },
    }


def build_chat_statement_events(
    message: str,
    *,
    session_id: str,
    turn_id: str = "",
    capability: str = "chat",
    language: str = "",
) -> list[dict[str, Any]]:
    text = _clean(message, 500)
    if not text:
        return []

    source = _clean(capability or "chat", 80)
    source_id = f"{session_id}:{turn_id}" if turn_id else session_id
    base_id = f"ev_chat_{_safe_id(source)}_{_safe_id(session_id)}_{_safe_id(turn_id)}_{uuid.uuid4().hex[:8]}"
    metadata = {
        "session_id": session_id,
        "turn_id": turn_id,
        "language": language,
        "extraction": "heuristic_v1",
    }
    events: list[dict[str, Any]] = []

    if _looks_like_goal_statement(text):
        events.append(
            {
                "id": f"{base_id}_goal",
                "source": source,
                "source_id": source_id,
                "verb": "stated",
                "object_type": "learning_goal",
                "object_id": _safe_id(text),
                "title": text,
                "summary": text,
                "confidence": 0.42,
                "weight": 0.65,
                "metadata": metadata,
            }
        )

    if _looks_like_learning_blocker(text):
        events.append(
            {
                "id": f"{base_id}_blocker",
                "source": source,
                "source_id": source_id,
                "verb": "stated",
                "object_type": "learning_blocker",
                "object_id": _safe_id(text),
                "title": text,
                "summary": text,
                "confidence": 0.5,
                "weight": 0.75,
                "metadata": metadata,
            }
        )

    for preference in _chat_resource_preferences(text):
        events.append(
            {
                "id": f"{base_id}_preference_{_safe_id(preference)}",
                "source": source,
                "source_id": source_id,
                "verb": "stated",
                "object_type": "learning_preference",
                "object_id": _safe_id(preference),
                "title": preference,
                "summary": text,
                "resource_type": preference,
                "confidence": 0.46,
                "weight": 0.6,
                "metadata": metadata,
            }
        )

    return events


def _looks_like_goal_statement(text: str) -> bool:
    markers = (
        "我想",
        "我希望",
        "我的目标",
        "想学习",
        "想掌握",
        "需要学习",
        "准备学习",
        "学习目标",
        "learn",
        "master",
        "goal",
    )
    lowered = text.lower()
    return any(marker in lowered for marker in markers)


def _looks_like_learning_blocker(text: str) -> bool:
    markers = (
        "不懂",
        "不会",
        "不理解",
        "没理解",
        "搞不清",
        "卡",
        "困惑",
        "难",
        "问题",
        "confused",
        "stuck",
        "do not understand",
        "don't understand",
    )
    lowered = text.lower()
    return any(marker in lowered for marker in markers)


def _chat_resource_preferences(text: str) -> list[str]:
    lowered = text.lower()
    candidates: list[tuple[str, tuple[str, ...]]] = [
        ("visual", ("图解", "图", "可视化", "示意图", "流程图", "mermaid", "svg", "visual")),
        ("video", ("视频", "短视频", "动画", "manim", "video", "animation")),
        ("quiz", ("练习", "题目", "测验", "选择题", "判断题", "quiz", "exercise")),
        ("example", ("例子", "案例", "示例", "example", "case")),
        ("code", ("代码", "编程", "python", "c++", "java", "code")),
        ("step_by_step", ("一步步", "分步", "详细", "推导", "step by step", "derive")),
    ]
    preferences: list[str] = []
    for value, markers in candidates:
        if any(marker in lowered for marker in markers):
            preferences.append(value)
    return preferences


def _verb_from_preview(item: dict[str, Any]) -> str:
    if item.get("score") is not None:
        return "answered"
    source = str(item.get("source_id") or "")
    if source == "notebook":
        return "saved"
    if source.startswith("guide"):
        return "completed"
    return "observed"


def _object_type_from_preview(item: dict[str, Any]) -> str:
    source = str(item.get("source_id") or "")
    if source == "question_notebook":
        return "quiz"
    if source == "notebook":
        return "notebook_record"
    if source.startswith("guide"):
        return "guide_task"
    if source == "memory":
        return "memory_snapshot"
    return "learning_activity"


def _clean(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").replace("\r", "\n").split()).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _safe_id(value: Any) -> str:
    text = _clean(value, 160)
    chars: list[str] = []
    for char in text:
        if char.isalnum() or char in {"_", "-", "."}:
            chars.append(char)
        else:
            chars.append("_")
    return "".join(chars).strip("_") or uuid.uuid4().hex


def _as_bool_or_none(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    return None


def _as_float(value: Any, default: float | None = 0.0) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_timestamp(value: Any) -> float:
    if value is None or value == "":
        return time.time()
    if isinstance(value, str):
        text = value.strip()
        try:
            return float(text)
        except ValueError:
            try:
                return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
            except Exception:
                return time.time()
    try:
        return float(value)
    except (TypeError, ValueError):
        return time.time()


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


_learner_evidence_service: LearnerEvidenceService | None = None


def get_learner_evidence_service() -> LearnerEvidenceService:
    global _learner_evidence_service
    if _learner_evidence_service is None:
        _learner_evidence_service = LearnerEvidenceService()
    return _learner_evidence_service


def create_learner_evidence_service(**kwargs: Any) -> LearnerEvidenceService:
    return LearnerEvidenceService(**kwargs)


__all__ = [
    "build_guide_resource_event",
    "build_guide_session_event",
    "build_guide_task_event",
    "build_chat_statement_events",
    "build_notebook_record_event",
    "build_profile_calibration_event",
    "build_quiz_answer_events",
    "LearnerEvidenceEvent",
    "LearnerEvidenceService",
    "create_learner_evidence_service",
    "get_learner_evidence_service",
]
