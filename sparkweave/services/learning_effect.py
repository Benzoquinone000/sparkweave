"""Learning effect closed-loop aggregation.

This service turns the existing learner evidence ledger into a global learning
effect report. It intentionally starts with transparent rules so the product can
explain every recommendation before we upgrade parts of it to BKT/IRT later.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import re
import time
from typing import Any
from urllib.parse import urlencode
import uuid

from sparkweave.services.learner_evidence import (
    LearnerEvidenceService,
    get_learner_evidence_service,
)

LEARNING_EFFECT_DIMENSION_WEIGHTS: dict[str, float] = {
    "mastery": 0.27,
    "progress": 0.14,
    "stability": 0.16,
    "evidence_quality": 0.17,
    "engagement": 0.12,
    "remediation": 0.09,
    "resource_effectiveness": 0.05,
}


@dataclass
class ConceptMasteryState:
    concept_id: str
    title: str
    score: float = 0.0
    status: str = "unknown"
    confidence: float = 0.0
    trend: str = "flat"
    evidence_count: int = 0
    scored_event_count: int = 0
    correct_count: int = 0
    incorrect_count: int = 0
    open_mistake_count: int = 0
    resource_count: int = 0
    last_practiced_at: float | None = None
    next_review_at: float | None = None
    evidence_refs: list[str] = field(default_factory=list)
    common_mistakes: list[str] = field(default_factory=list)
    recommendation: str = ""


@dataclass
class NextBestAction:
    id: str
    type: str
    title: str
    reason: str
    target_concepts: list[str] = field(default_factory=list)
    estimated_minutes: int = 8
    priority: float = 0.5
    href: str = ""
    capability: str = "chat"
    prompt: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    knowledge_bases: list[str] = field(default_factory=list)
    writes_back: list[str] = field(default_factory=lambda: ["mastery", "profile"])


class LearningEffectService:
    """Build reports, concept states, and interventions from learner evidence."""

    def __init__(
        self,
        *,
        evidence_service: LearnerEvidenceService | None = None,
        knowledge_manager: Any | None = None,
    ) -> None:
        self._evidence_service = evidence_service or get_learner_evidence_service()
        self._knowledge_manager = knowledge_manager

    def health(self) -> dict[str, Any]:
        listing = self._evidence_service.list_events(limit=1)
        return {
            "status": "healthy",
            "service": "learning_effect",
            "event_count": int(dict(listing.get("summary") or {}).get("event_count") or listing.get("total") or 0),
        }

    def append_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        event = self._evidence_service.append_event(_flatten_learning_event(payload))
        return {"event": event}

    def complete_action(
        self,
        action_id: str,
        *,
        note: str = "",
        score: float | None = None,
        course_id: str = "",
        concept_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        concepts = [_clean(item, 120) for item in concept_ids or [] if _clean(item, 120)]
        event = self._evidence_service.append_event(
            {
                "id": f"ev_learning_effect_action_{_safe_id(action_id)}_{uuid.uuid4().hex[:10]}",
                "source": "learning_effect",
                "source_id": action_id,
                "verb": "completed",
                "object_type": "intervention_action",
                "object_id": action_id,
                "title": "完成学习处方动作",
                "summary": note,
                "course_id": course_id,
                "score": score,
                "confidence": 0.78,
                "metadata": {
                    "action_id": action_id,
                    "concepts": concepts,
                    "concept_id": _safe_id(concepts[0]).lower() if concepts else "",
                },
            }
        )
        return {"event": event, "report": self.build_report(course_id=course_id)}

    def build_report(
        self,
        *,
        course_id: str = "",
        window: str = "14d",
        limit: int = 500,
    ) -> dict[str, Any]:
        events = self._events(course_id=course_id, window=window, limit=limit)
        return self.build_report_from_events(events, course_id=course_id, window=window)

    def build_report_from_events(
        self,
        events: list[dict[str, Any]],
        *,
        course_id: str = "",
        window: str = "custom",
    ) -> dict[str, Any]:
        """Build a learning-effect report from already collected events."""

        events = [dict(item) for item in events if isinstance(item, dict)]
        events.sort(key=_event_time)
        concepts = self._build_concepts(events)
        summary = self._summarize_events(events)
        knowledge_context = self._build_knowledge_context(
            course_id=course_id,
            concepts=concepts,
            summary=summary,
        )
        actions = self._build_next_actions(
            concepts,
            summary,
            course_id=course_id,
            knowledge_context=knowledge_context,
        )
        remediation_loop = self._remediation_loop(events)
        dimensions = self._dimensions(events=events, concepts=concepts, summary=summary)
        overall_score = _weighted_score(dimensions, LEARNING_EFFECT_DIMENSION_WEIGHTS)
        label = _overall_label(overall_score, evidence_count=len(events), open_mistakes=summary["open_mistake_count"])
        visualization = self._learning_effect_visualization(
            events=events,
            concepts=concepts,
            dimensions=dimensions,
            summary=summary,
            remediation_loop=remediation_loop,
            actions=actions,
            overall_score=overall_score,
            overall_label=label,
        )
        learner_receipt = self._learner_receipt(
            concepts=concepts,
            summary=summary,
            remediation_loop=remediation_loop,
            actions=actions,
            overall_score=overall_score,
            overall_label=label,
        )
        study_brief = self._study_brief(
            concepts=concepts,
            summary=summary,
            remediation_loop=remediation_loop,
            actions=actions,
            overall_score=overall_score,
            overall_label=label,
            learner_receipt=learner_receipt,
            course_id=course_id,
            knowledge_context=knowledge_context,
        )
        explainability = self._explain_report(
            events=events,
            concepts=concepts,
            dimensions=dimensions,
            summary=summary,
            remediation_loop=remediation_loop,
            actions=actions,
            overall_score=overall_score,
            overall_label=label,
            learner_receipt=learner_receipt,
            study_brief=study_brief,
            knowledge_context=knowledge_context,
        )
        return {
            "success": True,
            "generated_at": time.time(),
            "course_id": course_id,
            "window": window,
            "overall": {
                "score": overall_score,
                "label": label,
                "summary": _overall_summary(label, overall_score, actions),
            },
            "dimensions": dimensions,
            "concepts": [asdict(item) for item in concepts[:24]],
            "open_mistakes": self._open_mistakes(events)[:12],
            "remediation_loop": remediation_loop,
            "visualization": visualization,
            "learner_receipt": learner_receipt,
            "study_brief": study_brief,
            "explainability": explainability,
            "knowledge_context": knowledge_context,
            "next_actions": [asdict(item) for item in actions[:6]],
            "evidence_refs": self._evidence_refs(events, limit=10),
            "summary": summary,
        }

    def list_concepts(
        self,
        *,
        course_id: str = "",
        window: str = "all",
        limit: int = 100,
    ) -> dict[str, Any]:
        events = self._events(course_id=course_id, window=window, limit=500)
        concepts = self._build_concepts(events)
        return {
            "success": True,
            "course_id": course_id,
            "window": window,
            "items": [asdict(item) for item in concepts[: max(1, min(limit, 200))]],
            "total": len(concepts),
            "summary": self._concept_summary(concepts),
        }

    def next_actions(
        self,
        *,
        course_id: str = "",
        window: str = "14d",
        limit: int = 6,
    ) -> dict[str, Any]:
        events = self._events(course_id=course_id, window=window, limit=500)
        concepts = self._build_concepts(events)
        summary = self._summarize_events(events)
        knowledge_context = self._build_knowledge_context(
            course_id=course_id,
            concepts=concepts,
            summary=summary,
        )
        actions = self._build_next_actions(
            concepts,
            summary,
            course_id=course_id,
            knowledge_context=knowledge_context,
        )
        return {
            "success": True,
            "course_id": course_id,
            "window": window,
            "items": [asdict(item) for item in actions[: max(1, min(limit, 20))]],
            "total": len(actions),
        }

    def demo_summary(
        self,
        *,
        course_id: str = "",
        window: str = "14d",
    ) -> dict[str, Any]:
        """Return a compact, presentation-friendly learning-effect summary."""

        report = self.build_report(course_id=course_id, window=window)
        overall = dict(report.get("overall") or {})
        summary = dict(report.get("summary") or {})
        receipt = dict(report.get("learner_receipt") or {})
        study_brief = dict(report.get("study_brief") or {})
        explainability = dict(report.get("explainability") or {})
        remediation = dict(report.get("remediation_loop") or {})
        primary_action = dict((report.get("next_actions") or [{}])[0] or {})
        concepts = [dict(item) for item in report.get("concepts") or [] if isinstance(item, dict)]
        dimensions = [dict(item) for item in report.get("dimensions") or [] if isinstance(item, dict)]
        weak_concepts = [
            item
            for item in concepts
            if str(item.get("status") or "") in {"needs_foundation", "needs_support", "unknown"}
            or int(item.get("open_mistake_count") or 0) > 0
        ][:3]
        weak_concept_highlights = [
            {
                "concept_id": item.get("concept_id") or "",
                "title": item.get("title") or item.get("concept_id") or "未命名概念",
                "score": item.get("score") or 0,
                "status": item.get("status") or "unknown",
                "status_label": _status_label(str(item.get("status") or "unknown")),
                "recommendation": item.get("recommendation") or "",
            }
            for item in weak_concepts
        ]
        event_count = int(summary.get("event_count") or 0)
        answered_count = int(summary.get("answered_count") or summary.get("quiz_count") or 0)
        resource_count = int(summary.get("resource_count") or 0)
        open_mistakes = int(summary.get("open_mistake_count") or 0)
        loop_pending = int(remediation.get("pending_remediation_count") or 0)
        loop_retest = int(remediation.get("ready_for_retest_count") or 0)
        loop_closed = int(remediation.get("closed_count") or 0)

        proof_points = [
            {
                "label": "证据",
                "value": f"{event_count} 条",
                "detail": f"{answered_count} 次作答，{resource_count} 个资源行为。",
            },
            {
                "label": "画像",
                "value": receipt.get("state_label") or overall.get("label") or "待评估",
                "detail": receipt.get("profile_update") or "画像会随练习、资源和反思继续更新。",
            },
            {
                "label": "处方",
                "value": primary_action.get("title") or receipt.get("next_step") or "继续学习",
                "detail": primary_action.get("reason") or receipt.get("reason") or "系统会根据下一次证据继续调整。",
            },
            {
                "label": "闭环",
                "value": f"待补救 {loop_pending} / 待复测 {loop_retest} / 已闭环 {loop_closed}",
                "detail": "错因会先补救，再用复测确认是否真正关闭。",
            },
        ]
        talking_points = [
            f"学习效果评估基于最近 {event_count} 条学习证据生成，而不是只看单次回答。",
            receipt.get("profile_update") or "系统会把答题、资源和反思写回同一个学习画像。",
            f"当前建议下一步是：{primary_action.get('title') or receipt.get('next_step') or '继续学习'}。",
        ]
        if weak_concepts:
            talking_points.append("优先薄弱点：" + "、".join(str(item.get("title") or item.get("concept_id")) for item in weak_concepts))
        if open_mistakes:
            talking_points.append(f"仍有 {open_mistakes} 个错因信号需要补救或复测。")

        result = {
            "success": True,
            "generated_at": report.get("generated_at"),
            "course_id": course_id,
            "window": window,
            "headline": receipt.get("headline") or overall.get("summary") or "学习效果评估摘要",
            "status_label": overall.get("label") or receipt.get("state_label") or "待评估",
            "score": overall.get("score", 0),
            "score_label": receipt.get("score_label") or f"{overall.get('score', 0)} 分",
            "confidence_label": receipt.get("confidence_label") or "等待证据",
            "proof_points": proof_points,
            "study_brief": study_brief,
            "explainability": explainability,
            "weak_concepts": weak_concept_highlights,
            "dimension_highlights": dimensions[:4],
            "primary_action": {
                "id": primary_action.get("id") or receipt.get("action_id") or "",
                "type": primary_action.get("type") or "",
                "title": primary_action.get("title") or receipt.get("next_step") or "继续学习",
                "reason": primary_action.get("reason") or receipt.get("reason") or "",
                "href": primary_action.get("href") or receipt.get("action_href") or "",
                "capability": primary_action.get("capability") or "",
                "estimated_minutes": primary_action.get("estimated_minutes") or 8,
            },
            "requirement_alignment": [
                {
                    "requirement": "学习效果评估",
                    "status": overall.get("label") or "待评估",
                    "evidence": f"{event_count} 条学习证据、{answered_count} 次作答、{resource_count} 个资源行为。",
                },
                {
                    "requirement": "动态调整学习方案",
                    "status": "已生成下一步处方" if primary_action else "等待第一步诊断",
                    "evidence": primary_action.get("title") or receipt.get("next_step") or "先建立画像基线。",
                },
                {
                    "requirement": "错因补救复测闭环",
                    "status": f"待补救 {loop_pending} / 待复测 {loop_retest} / 已闭环 {loop_closed}",
                    "evidence": "补救动作和复测结果会继续写回画像。",
                },
            ],
            "talking_points": talking_points,
        }
        result["markdown"] = _learning_effect_demo_markdown(result)
        return result

    def _events(self, *, course_id: str, window: str, limit: int) -> list[dict[str, Any]]:
        listing = self._evidence_service.list_events(limit=max(1, min(limit, 500)))
        items = [dict(item) for item in listing.get("items") or [] if isinstance(item, dict)]
        if course_id:
            items = [
                item
                for item in items
                if str(item.get("course_id") or "").strip() == course_id
                or str(dict(item.get("metadata") or {}).get("course_id") or "").strip() == course_id
            ]
        cutoff = _window_cutoff(window)
        if cutoff is not None:
            items = [item for item in items if _event_time(item) >= cutoff]
        items.sort(key=_event_time)
        return items

    def _build_concepts(self, events: list[dict[str, Any]]) -> list[ConceptMasteryState]:
        grouped: dict[str, dict[str, Any]] = {}
        for event in events:
            concepts = _concept_candidates(event)
            if not concepts:
                continue
            event_score = _event_score(event)
            is_mastery_signal = _is_mastery_signal(event, event_score)
            for concept_id, title in concepts:
                bucket = grouped.setdefault(
                    concept_id,
                    {
                        "title": title,
                        "events": [],
                        "scores": [],
                        "sources": set(),
                        "mistakes": [],
                        "resources": 0,
                        "correct": 0,
                        "incorrect": 0,
                    },
                )
                bucket["title"] = bucket["title"] or title
                bucket["events"].append(event)
                bucket["sources"].add(str(event.get("source") or "unknown"))
                if _is_resource_event(event):
                    bucket["resources"] += 1
                if event.get("is_correct") is True:
                    bucket["correct"] += 1
                elif event.get("is_correct") is False:
                    bucket["incorrect"] += 1
                for mistake in _mistake_labels(event):
                    if mistake not in bucket["mistakes"]:
                        bucket["mistakes"].append(mistake)
                if is_mastery_signal and event_score is not None:
                    bucket["scores"].append((event_score, _event_weight(event), _event_time(event), event))

        states: list[ConceptMasteryState] = []
        for concept_id, bucket in grouped.items():
            scores: list[tuple[float, float, float, dict[str, Any]]] = bucket["scores"]
            score = _rolling_score(scores)
            event_count = len(bucket["events"])
            scored_count = len(scores)
            confidence = _confidence(event_count, scored_count, len(bucket["sources"]))
            trend = _trend(scores)
            last_time = max((_event_time(item) for item in bucket["events"]), default=0.0) or None
            status = _mastery_status(score, scored_count)
            incorrect = int(bucket["incorrect"])
            correct = int(bucket["correct"])
            open_mistakes = max(0, incorrect - max(0, correct // 2))
            state = ConceptMasteryState(
                concept_id=concept_id,
                title=str(bucket["title"] or concept_id),
                score=round(score, 3),
                status=status,
                confidence=confidence,
                trend=trend,
                evidence_count=event_count,
                scored_event_count=scored_count,
                correct_count=correct,
                incorrect_count=incorrect,
                open_mistake_count=open_mistakes,
                resource_count=int(bucket["resources"]),
                last_practiced_at=last_time,
                next_review_at=_next_review_at(last_time, status),
                evidence_refs=[
                    str(item.get("id") or "")
                    for item in sorted(bucket["events"], key=_event_time, reverse=True)[:5]
                    if item.get("id")
                ],
                common_mistakes=list(bucket["mistakes"])[:5],
                recommendation=_concept_recommendation(status, open_mistakes, trend),
            )
            states.append(state)
        states.sort(key=lambda item: (_status_rank(item.status), item.score, -item.evidence_count))
        return states

    def _dimensions(
        self,
        *,
        events: list[dict[str, Any]],
        concepts: list[ConceptMasteryState],
        summary: dict[str, Any],
    ) -> list[dict[str, Any]]:
        concept_scores = [item.score for item in concepts if item.scored_event_count]
        mastery_score = round(sum(concept_scores) / len(concept_scores) * 100) if concept_scores else 0
        completed = summary["completed_count"]
        answered = summary["answered_count"]
        progress_score = min(100, completed * 24 + answered * 10)
        due_reviews = sum(1 for item in concepts if item.next_review_at and item.next_review_at <= time.time())
        stable = sum(1 for item in concepts if item.status in {"proficient", "mastered"} and item.confidence >= 0.55)
        stability_score = round((stable / len(concepts)) * 100) if concepts else 0
        if due_reviews:
            stability_score = max(0, stability_score - min(35, due_reviews * 8))
        evidence_quality = min(
            100,
            len(events) * 8
            + summary["scored_count"] * 10
            + len(summary["sources"]) * 8
            + summary["reflection_count"] * 7,
        )
        engagement_score = min(
            100,
            summary["resource_count"] * 14
            + summary["saved_count"] * 18
            + completed * 18
            + answered * 12,
        )
        mistake_total = summary["mistake_count"]
        open_mistake_count = summary["open_mistake_count"]
        if mistake_total:
            remediation_score = max(0, round((1 - open_mistake_count / max(1, mistake_total)) * 100))
        else:
            remediation_score = 72 if events else 35
        resource_effectiveness = min(
            100,
            summary["resource_count"] * 12
            + summary["saved_count"] * 18
            + summary["helpful_count"] * 25
            + max(0, round(summary["accuracy"] * 25)),
        )
        return [
            _dimension("mastery", "知识掌握", mastery_score, "按知识点答题、任务完成和复测结果估算。"),
            _dimension("progress", "学习推进", progress_score, f"完成 {completed} 个任务，提交 {answered} 次作答。"),
            _dimension("stability", "稳定迁移", stability_score, f"{stable}/{len(concepts)} 个知识点达到熟练或掌握，{due_reviews} 个需要复测。"),
            _dimension("evidence_quality", "证据质量", evidence_quality, f"累计 {len(events)} 条事件，{summary['scored_count']} 条可评分证据。"),
            _dimension("engagement", "学习投入", engagement_score, f"生成/查看 {summary['resource_count']} 个资源，保存 {summary['saved_count']} 次。"),
            _dimension("remediation", "错因闭环", remediation_score, f"累计 {mistake_total} 个错因信号，仍有 {open_mistake_count} 个待处理。"),
            _dimension("resource_effectiveness", "资源有效性", resource_effectiveness, "根据资源使用、保存、反馈和后续正确率估算。"),
        ]

    def _build_next_actions(
        self,
        concepts: list[ConceptMasteryState],
        summary: dict[str, Any],
        *,
        course_id: str,
        knowledge_context: dict[str, Any] | None = None,
    ) -> list[NextBestAction]:
        actions: list[NextBestAction] = []
        if not concepts and summary["event_count"] == 0:
            actions.append(
                NextBestAction(
                    id="nba_start_diagnostic",
                    type="diagnostic",
                    title="先做一次 5 题诊断",
                    reason="还没有足够学习证据，先建立当前水平线。",
                    estimated_minutes=8,
                    priority=0.98,
                    href=_guide_href(course_id, "diagnostic"),
                    writes_back=["mastery", "profile", "baseline"],
                )
            )
            for action in actions:
                _attach_action_execution_payload(
                    action,
                    course_id=course_id,
                    knowledge_context=knowledge_context,
                )
            return actions

        weak = [item for item in concepts if item.status in {"needs_foundation", "needs_support", "unknown"}]
        due = [item for item in concepts if item.next_review_at and item.next_review_at <= time.time()]
        first_weak = weak[0] if weak else None
        if first_weak:
            actions.append(
                NextBestAction(
                    id=f"nba_visual_{first_weak.concept_id}",
                    type="generate_visual",
                    title=f"先看一张「{first_weak.title}」图解",
                    reason=f"{first_weak.title} 当前处于「{_status_label(first_weak.status)}」，图解能快速补齐直觉。",
                    target_concepts=[first_weak.concept_id],
                    estimated_minutes=6,
                    priority=0.94,
                    href=_chat_href(f"为我生成一张{first_weak.title}的概念图解"),
                    writes_back=["resource_preference", "mastery"],
                )
            )
            actions.append(
                NextBestAction(
                    id=f"nba_practice_{first_weak.concept_id}",
                    type="generate_practice",
                    title=f"做 3 道「{first_weak.title}」小练习",
                    reason="单纯看资源不能证明掌握，需要用可评分练习回写画像。",
                    target_concepts=[first_weak.concept_id],
                    estimated_minutes=10,
                    priority=0.9,
                    href=_guide_href(course_id, f"practice:{first_weak.title}"),
                    writes_back=["mastery", "mistake_review", "profile"],
                )
            )

        if due:
            target = due[0]
            actions.append(
                NextBestAction(
                    id=f"nba_retest_{target.concept_id}",
                    type="retest",
                    title=f"复测「{target.title}」是否还稳",
                    reason="这个知识点到了复测时间，短测能判断是否真的迁移稳定。",
                    target_concepts=[target.concept_id],
                    estimated_minutes=7,
                    priority=0.86,
                    href=_guide_href(course_id, f"retest:{target.title}"),
                    writes_back=["stability", "mastery", "profile"],
                )
            )

        if summary["open_mistake_count"] > 0:
            target = first_weak or (concepts[0] if concepts else None)
            actions.append(
                NextBestAction(
                    id="nba_close_mistakes",
                    type="mistake_review",
                    title="先关闭一个反复错因",
                    reason=f"当前仍有 {summary['open_mistake_count']} 个错因信号未闭环。",
                    target_concepts=[target.concept_id] if target else [],
                    estimated_minutes=9,
                    priority=0.82,
                    href=_guide_href(course_id, "mistake_review"),
                    writes_back=["mistake_review", "mastery"],
                )
            )

        if summary["resource_count"] == 0 and concepts:
            target = concepts[0]
            actions.append(
                NextBestAction(
                    id=f"nba_resource_{target.concept_id}",
                    type="generate_resource",
                    title=f"生成一份「{target.title}」入门材料",
                    reason="当前评估主要来自作答，补一个低门槛资源可以降低理解成本。",
                    target_concepts=[target.concept_id],
                    estimated_minutes=5,
                    priority=0.72,
                    href=_chat_href(f"根据我的画像生成{target.title}的入门材料"),
                    writes_back=["resource_preference"],
                )
            )

        if not actions and concepts:
            target = max(concepts, key=lambda item: item.score)
            actions.append(
                NextBestAction(
                    id=f"nba_advance_{target.concept_id}",
                    type="advance",
                    title="进入下一节或项目任务",
                    reason="当前证据显示主要知识点状态较稳，可以用迁移任务验证应用能力。",
                    target_concepts=[target.concept_id],
                    estimated_minutes=15,
                    priority=0.74,
                    href=_guide_href(course_id, "advance"),
                    writes_back=["transfer", "mastery", "profile"],
                )
            )

        deduped: dict[str, NextBestAction] = {}
        for action in sorted(actions, key=lambda item: item.priority, reverse=True):
            _attach_action_execution_payload(
                action,
                course_id=course_id,
                knowledge_context=knowledge_context,
            )
            deduped.setdefault(action.id, action)
        return list(deduped.values())

    def _summarize_events(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        sources = sorted({str(item.get("source") or "unknown") for item in events})
        scored = [_event_score(item) for item in events if _event_score(item) is not None]
        answered = [item for item in events if item.get("verb") == "answered" or item.get("object_type") in {"quiz", "quiz_item"}]
        correct = [item for item in answered if item.get("is_correct") is True]
        incorrect = [item for item in answered if item.get("is_correct") is False]
        mistake_count = sum(len(_mistake_labels(item)) or int(item.get("is_correct") is False) for item in events)
        closed_estimate = min(mistake_count, len(correct) // 2)
        return {
            "event_count": len(events),
            "sources": sources,
            "scored_count": len(scored),
            "average_score": round(sum(scored) / len(scored), 3) if scored else 0.0,
            "answered_count": len(answered),
            "accuracy": round(len(correct) / len(answered), 3) if answered else 0.0,
            "completed_count": sum(1 for item in events if item.get("verb") == "completed"),
            "resource_count": sum(1 for item in events if _is_resource_event(item)),
            "saved_count": sum(1 for item in events if item.get("verb") == "saved"),
            "reflection_count": sum(1 for item in events if _clean(item.get("reflection") or item.get("summary"), 20)),
            "helpful_count": sum(1 for item in events if dict(item.get("metadata") or {}).get("helpful") is True),
            "mistake_count": mistake_count,
            "open_mistake_count": max(0, mistake_count - closed_estimate),
        }

    def _open_mistakes(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for event in sorted(events, key=_event_time, reverse=True):
            labels = _mistake_labels(event)
            if not labels and event.get("is_correct") is False:
                labels = ["回答错误，需要复盘"]
            for label in labels:
                concepts = _concept_candidates(event)
                items.append(
                    {
                        "label": label,
                        "source": event.get("source") or "",
                        "title": event.get("title") or "",
                        "concept_id": concepts[0][0] if concepts else "",
                        "evidence_id": event.get("id") or "",
                        "created_at": event.get("created_at"),
                    }
                )
        return items

    def _remediation_loop(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        completed_times: dict[str, float] = {}
        correct_times_by_concept: dict[str, list[float]] = {}
        for event in events:
            event_time = _event_time(event)
            if event.get("verb") == "completed":
                for task_id in _event_task_ids(event):
                    completed_times[task_id] = max(completed_times.get(task_id, 0.0), event_time)
            if event.get("is_correct") is True or (_event_score(event) or 0) >= 0.85:
                for concept_id, _title in _concept_candidates(event):
                    correct_times_by_concept.setdefault(concept_id, []).append(event_time)

        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for event in sorted(events, key=_event_time, reverse=True):
            remediation = _event_remediation_task(event)
            if not remediation:
                continue
            concept = _clean(remediation.get("concept") or remediation.get("title"), 120) or "当前薄弱点"
            concept_id = _safe_id(concept).lower()
            target_task_id = _clean(remediation.get("target_task_id"), 120)
            item_key = f"{target_task_id}:{concept_id}"
            if item_key in seen:
                continue
            seen.add(item_key)
            created_time = _event_time(event)
            completed_time = completed_times.get(target_task_id, 0.0)
            retest_times = [
                item_time
                for item_time in correct_times_by_concept.get(concept_id, [])
                if completed_time and item_time >= completed_time
            ]
            closed_time = min(retest_times) if retest_times else 0.0
            status = "pending_remediation"
            status_label = "待补救"
            if completed_time and completed_time >= created_time:
                status = "ready_for_retest"
                status_label = "待复测"
                if closed_time:
                    status = "closed"
                    status_label = "已闭环"
            explanation = _remediation_loop_explanation(
                event,
                concept=concept,
                status=status,
                source_score=_event_score(event),
                completed_time=completed_time,
                closed_time=closed_time,
            )
            action_payload = _remediation_action_payload(
                concept=concept,
                status=status,
                resource_type=_clean(remediation.get("resource_type"), 40),
            )
            items.append(
                {
                    "title": remediation.get("title") or f"补齐「{concept}」",
                    "concept": concept,
                    "target_task_id": target_task_id,
                    "resource_type": remediation.get("resource_type") or "",
                    "estimated_minutes": remediation.get("estimated_minutes") or 10,
                    "status": status,
                    "status_label": status_label,
                    "reason": explanation["reason"],
                    "evidence_summary": explanation["evidence_summary"],
                    "next_step": explanation["next_step"],
                    "progress_label": explanation["progress_label"],
                    "action_label": action_payload["label"],
                    "action_href": action_payload["href"],
                    "action_capability": action_payload["capability"],
                    "action_prompt": action_payload["prompt"],
                    "action_config": action_payload["config"],
                    "created_at": event.get("created_at"),
                    "completed_at": completed_time or None,
                    "closed_at": closed_time or None,
                    "evidence_id": event.get("id") or "",
                }
            )

        return {
            "total": len(items),
            "pending_remediation_count": sum(1 for item in items if item["status"] == "pending_remediation"),
            "ready_for_retest_count": sum(1 for item in items if item["status"] == "ready_for_retest"),
            "closed_count": sum(1 for item in items if item["status"] == "closed"),
            "items": items[:8],
        }

    def _evidence_refs(self, events: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        for event in sorted(events, key=_event_time, reverse=True)[:limit]:
            refs.append(
                {
                    "id": event.get("id") or "",
                    "source": event.get("source") or "",
                    "verb": event.get("verb") or "",
                    "title": event.get("title") or "",
                    "score": event.get("score"),
                    "created_at": event.get("created_at"),
                }
            )
        return refs

    def _build_knowledge_context(
        self,
        *,
        course_id: str,
        concepts: list[ConceptMasteryState],
        summary: dict[str, Any],
    ) -> dict[str, Any]:
        """Summarize the KB that should ground learning-effect actions."""

        del summary  # Reserved for future course-to-KB routing signals.
        focus = next(
            (
                item
                for item in concepts
                if item.status in {"needs_foundation", "needs_support", "unknown"} or item.open_mistake_count
            ),
            concepts[0] if concepts else None,
        )
        focus_title = focus.title if focus else "当前学习目标"

        try:
            manager = self._knowledge_manager
            if manager is None:
                from sparkweave.knowledge.manager import KnowledgeBaseManager

                manager = KnowledgeBaseManager()
            kb_names = [str(item).strip() for item in (manager.list_knowledge_bases() or []) if str(item).strip()]
            if not kb_names:
                return _empty_knowledge_context(
                    focus_title=focus_title,
                    status="missing",
                    summary="还没有可用资料库。先上传课程资料后，学习建议就能带上可检索依据。",
                )
            kb_name = _select_learning_kb(manager, kb_names, course_id)
            if not kb_name:
                return _empty_knowledge_context(
                    focus_title=focus_title,
                    status="missing",
                    summary="还没有选定资料库。设置默认资料库后，学习建议会自动引用相关材料。",
                )

            info = manager.get_info(kb_name) if hasattr(manager, "get_info") else {}
            info = info if isinstance(info, dict) else {}
            statistics = info.get("statistics") if isinstance(info.get("statistics"), dict) else {}
            metadata = info.get("metadata") if isinstance(info.get("metadata"), dict) else {}
            status = str(info.get("status") or statistics.get("status") or "unknown")
            provider = str(metadata.get("rag_provider") or statistics.get("rag_provider") or "")
            document_count = _safe_int_value(statistics.get("raw_documents"))
            ready = status == "ready" and bool(statistics.get("rag_initialized"))
            if bool(metadata.get("needs_reindex")) or bool(statistics.get("needs_reindex")):
                status = "needs_reindex"
                ready = False

            eval_report = _load_latest_knowledge_eval(manager, kb_name)
            eval_summary = _summarize_knowledge_eval(eval_report)
            quality_label = str(eval_summary.get("quality_label") or "")
            status_label = _knowledge_status_label(status=status, ready=ready, eval_summary=eval_summary)
            summary_text = _knowledge_context_summary(
                kb_name=kb_name,
                ready=ready,
                document_count=document_count,
                status_label=status_label,
                quality_label=quality_label,
            )
            action_label = "修复资料库" if status == "needs_reindex" else ("运行检索评测" if ready and not eval_summary.get("available") else "打开资料库")
            return {
                "available": bool(kb_name),
                "ready": ready,
                "status": status,
                "status_label": status_label,
                "kb_name": kb_name,
                "provider": provider,
                "document_count": document_count,
                "focus_query": focus_title,
                "summary": summary_text,
                "action_label": action_label,
                "action_href": "/knowledge",
                "latest_eval": eval_summary,
                "can_ground_actions": bool(ready and kb_name),
            }
        except Exception as exc:
            return _empty_knowledge_context(
                focus_title=focus_title,
                status="error",
                summary=f"资料库状态暂时无法读取：{_clean(exc, 120)}",
            )

    def _learning_effect_visualization(
        self,
        *,
        events: list[dict[str, Any]],
        concepts: list[ConceptMasteryState],
        dimensions: list[dict[str, Any]],
        summary: dict[str, Any],
        remediation_loop: dict[str, Any],
        actions: list[NextBestAction],
        overall_score: int,
        overall_label: str,
    ) -> dict[str, Any]:
        """Return a compact visual map that the UI and demo package can trust."""

        event_count = int(summary.get("event_count") or 0)
        answered_count = int(summary.get("answered_count") or 0)
        resource_count = int(summary.get("resource_count") or 0)
        action_count = len(actions)
        total_loop = int(remediation_loop.get("total") or 0)
        pending_loop = int(remediation_loop.get("pending_remediation_count") or 0)
        ready_loop = int(remediation_loop.get("ready_for_retest_count") or 0)
        closed_loop = int(remediation_loop.get("closed_count") or 0)
        weakest = [item for item in concepts if item.status in {"needs_foundation", "needs_support", "unknown"}]
        first_action = actions[0] if actions else None
        summary_text = (
            "证据已经形成可执行闭环。"
            if event_count and action_count
            else "先积累一次诊断、练习或资源反馈，系统会生成可执行闭环。"
        )

        nodes = [
            {
                "id": "evidence",
                "label": "证据流",
                "value": f"{event_count} 条",
                "detail": f"{answered_count} 次练习 · {resource_count} 个资源",
                "tone": "brand" if event_count else "neutral",
            },
            {
                "id": "assessment",
                "label": "效果评估",
                "value": f"{overall_score} 分" if event_count else "待评",
                "detail": overall_label,
                "tone": _effect_status(overall_score) if event_count else "thin_evidence",
            },
            {
                "id": "dispatch",
                "label": "动态调度",
                "value": f"{action_count} 个动作",
                "detail": first_action.title if first_action else "等待下一条证据",
                "tone": "brand" if action_count else "neutral",
            },
            {
                "id": "closed_loop",
                "label": "闭环进度",
                "value": f"{closed_loop}/{total_loop}" if total_loop else "0/0",
                "detail": f"待补 {pending_loop} · 待测 {ready_loop}" if total_loop else "暂无错因任务",
                "tone": "success" if total_loop and closed_loop == total_loop else ("warning" if pending_loop else "brand"),
            },
        ]

        return {
            "summary": summary_text,
            "nodes": nodes,
            "edges": [
                {"from": "evidence", "to": "assessment", "label": "汇总"},
                {"from": "assessment", "to": "dispatch", "label": "生成下一步"},
                {"from": "dispatch", "to": "closed_loop", "label": "回写证据"},
            ],
            "dimension_bars": [
                {
                    "id": item.get("id") or "",
                    "label": item.get("label") or "",
                    "score": item.get("score") or 0,
                    "status": item.get("status") or "",
                    "evidence": item.get("evidence") or "",
                }
                for item in dimensions[:6]
            ],
            "evidence_timeline": [_visual_timeline_event(event) for event in sorted(events, key=_event_time, reverse=True)[:5]],
            "weak_points": [
                {
                    "concept_id": item.concept_id,
                    "title": item.title,
                    "score": round(item.score * 100),
                    "status": item.status,
                    "recommendation": item.recommendation,
                }
                for item in weakest[:4]
            ],
            "loop": {
                "total": total_loop,
                "pending": pending_loop,
                "ready_for_retest": ready_loop,
                "closed": closed_loop,
            },
        }

    def _learner_receipt(
        self,
        *,
        concepts: list[ConceptMasteryState],
        summary: dict[str, Any],
        remediation_loop: dict[str, Any],
        actions: list[NextBestAction],
        overall_score: int,
        overall_label: str,
    ) -> dict[str, Any]:
        """Return a user-facing receipt for the learning-effect loop."""

        event_count = int(summary.get("event_count") or 0)
        answered_count = int(summary.get("answered_count") or 0)
        resource_count = int(summary.get("resource_count") or 0)
        scored_count = int(summary.get("scored_count") or 0)
        open_mistakes = int(summary.get("open_mistake_count") or 0)
        primary_action = actions[0] if actions else None
        weak_concepts = [item for item in concepts if item.status in {"needs_foundation", "needs_support", "unknown"} or item.open_mistake_count]
        focus = weak_concepts[0] if weak_concepts else (concepts[0] if concepts else None)
        confidence_label = _receipt_confidence_label(event_count=event_count, scored_count=scored_count, resource_count=resource_count)

        if event_count <= 0:
            evidence_summary = "目前还没有足够学习证据。先做一次诊断，系统会据此建立画像基线。"
            profile_update = "画像等待第一批可评分证据。"
        else:
            evidence_summary = f"基于最近 {event_count} 条学习证据，其中包含 {answered_count} 次作答、{resource_count} 个资源行为。"
            if open_mistakes:
                evidence_summary += f" 仍有 {open_mistakes} 个错因信号需要闭环。"
            if focus:
                profile_update = f"画像已把「{focus.title}」标记为「{_status_label(focus.status)}」，置信度约 {round(focus.confidence * 100)}%。"
            else:
                profile_update = "画像已同步最近的任务、练习和资源使用记录。"

        if primary_action:
            next_step = primary_action.title
            reason = primary_action.reason
            action_label = _receipt_action_label(primary_action.type)
            action_href = primary_action.href
            action_id = primary_action.id
            writes_back = primary_action.writes_back
        else:
            next_step = "继续保持当前学习节奏"
            reason = "当前没有必须立刻处理的薄弱点，继续留下练习和反思证据即可。"
            action_label = "继续学习"
            action_href = _guide_href("", "continue")
            action_id = ""
            writes_back = ["mastery", "profile"]

        headline = _receipt_headline(
            overall_label=overall_label,
            score=overall_score,
            focus_title=focus.title if focus else "",
            action_title=next_step,
            event_count=event_count,
        )
        return {
            "headline": headline,
            "state_label": overall_label,
            "score": overall_score,
            "score_label": f"{overall_score} 分" if event_count else "待建立",
            "confidence_label": confidence_label,
            "evidence_summary": evidence_summary,
            "profile_update": profile_update,
            "next_step": next_step,
            "reason": reason,
            "action_id": action_id,
            "action_label": action_label,
            "action_href": action_href,
            "writes_back": writes_back,
            "focus_concepts": [
                {
                    "concept_id": item.concept_id,
                    "title": item.title,
                    "status": item.status,
                    "status_label": _status_label(item.status),
                    "score": round(item.score * 100),
                }
                for item in (weak_concepts or concepts)[:3]
            ],
            "loop": {
                "pending": int(remediation_loop.get("pending_remediation_count") or 0),
                "ready_for_retest": int(remediation_loop.get("ready_for_retest_count") or 0),
                "closed": int(remediation_loop.get("closed_count") or 0),
            },
        }

    def _study_brief(
        self,
        *,
        concepts: list[ConceptMasteryState],
        summary: dict[str, Any],
        remediation_loop: dict[str, Any],
        actions: list[NextBestAction],
        overall_score: int,
        overall_label: str,
        learner_receipt: dict[str, Any],
        course_id: str,
        knowledge_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return the smallest actionable plan a learner should see today."""

        event_count = int(summary.get("event_count") or 0)
        open_mistakes = int(summary.get("open_mistake_count") or 0)
        pending_loop = int(remediation_loop.get("pending_remediation_count") or 0)
        ready_loop = int(remediation_loop.get("ready_for_retest_count") or 0)
        primary_action = actions[0] if actions else None
        weak_concepts = [
            item
            for item in concepts
            if item.status in {"needs_foundation", "needs_support", "unknown"} or item.open_mistake_count
        ]
        focus = weak_concepts[0] if weak_concepts else (concepts[0] if concepts else None)
        focus_title = focus.title if focus else "当前学习目标"

        if event_count <= 0:
            mode = "baseline"
            mode_label = "建立基线"
            headline = "今天先做一次小诊断"
            summary_text = "系统还不了解你的当前水平。先用 5 题诊断建立画像，再决定补图解、练习还是短视频。"
            timebox = 10
            main_href = primary_action.href if primary_action else _guide_href(course_id, "diagnostic")
            main_capability = primary_action.capability if primary_action else "deep_question"
            main_prompt = primary_action.prompt if primary_action else "请生成 5 道诊断题，先判断我的当前基础。"
            agenda = [
                _brief_step(
                    "完成 5 题诊断",
                    8,
                    "只需要判断当前基础，不追求满分。",
                    action_label="开始诊断",
                    action_href=main_href,
                    capability=main_capability,
                    prompt=main_prompt,
                ),
                _brief_step("写一句卡点", 2, "用一句话说清最不确定的地方，系统会把它写入画像。"),
            ]
            criteria = ["完成诊断", "留下一个卡点", "生成第一条画像证据"]
        elif pending_loop:
            mode = "remediation"
            mode_label = "补救错因"
            headline = f"先补齐「{focus_title}」"
            summary_text = f"当前还有 {pending_loop} 个错因没有闭环。今天只处理一个最关键卡点，避免同时开太多战线。"
            timebox = max(8, min(20, int(primary_action.estimated_minutes if primary_action else 10) + 4))
            agenda = [
                _brief_step(
                    primary_action.title if primary_action else f"补齐「{focus_title}」",
                    int(primary_action.estimated_minutes if primary_action else 10),
                    primary_action.reason if primary_action else "先补救错因，再进入复测。",
                    action_label=_receipt_action_label(primary_action.type) if primary_action else "开始补救",
                    action_href=primary_action.href if primary_action else _guide_href(course_id, "mistake_review"),
                    capability=primary_action.capability if primary_action else "visualize",
                    prompt=primary_action.prompt if primary_action else f"请用图解帮我补齐「{focus_title}」这个错因。",
                ),
                _brief_step("用一句话复述", 3, "复述“我之前错在哪里，现在怎么判断”。"),
                _brief_step("回到导学提交", 2, "提交后系统会判断是否可以进入复测。"),
            ]
            criteria = ["能说清错因", "完成补救动作", "产生可复测证据"]
        elif ready_loop:
            mode = "retest"
            mode_label = "复测确认"
            headline = f"复测「{focus_title}」是否真正掌握"
            summary_text = "补救已经完成，今天不要继续看资料，直接用小测确认是否能独立做对。"
            timebox = max(8, min(16, int(primary_action.estimated_minutes if primary_action else 7) + 3))
            agenda = [
                _brief_step(
                    primary_action.title if primary_action else f"复测「{focus_title}」",
                    int(primary_action.estimated_minutes if primary_action else 7),
                    primary_action.reason if primary_action else "用小测确认补救是否真正生效。",
                    action_label="去复测",
                    action_href=primary_action.href if primary_action else _guide_href(course_id, f"retest:{focus_title}"),
                    capability=primary_action.capability if primary_action else "deep_question",
                    prompt=primary_action.prompt if primary_action else f"请围绕「{focus_title}」生成 3 道复测题。",
                ),
                _brief_step("只看错题解析", 3, "如果复测出错，只处理错题，不再扩展新内容。"),
            ]
            criteria = ["独立完成复测", "错题能解释原因", "闭环状态更新"]
        elif primary_action:
            mode = str(primary_action.type or "continue")
            mode_label = _brief_mode_label(mode)
            headline = primary_action.title
            summary_text = primary_action.reason or learner_receipt.get("reason") or f"{overall_label}，先推进一个最小任务。"
            timebox = max(6, min(25, int(primary_action.estimated_minutes or 8) + 3))
            agenda = [
                _brief_step(
                    primary_action.title,
                    int(primary_action.estimated_minutes or 8),
                    primary_action.reason,
                    action_label=_receipt_action_label(primary_action.type),
                    action_href=primary_action.href,
                    capability=primary_action.capability,
                    prompt=primary_action.prompt,
                ),
                *_supporting_brief_steps(primary_action, focus_title),
            ]
            criteria = _brief_success_criteria(primary_action.type, focus_title)
        else:
            mode = "maintain"
            mode_label = "保持节奏"
            headline = "今天做一次轻量复习"
            summary_text = f"{overall_label}，当前没有必须立刻处理的薄弱点。用一个小复习保持稳定。"
            timebox = 8
            agenda = [
                _brief_step(
                    f"复习「{focus_title}」",
                    6,
                    "快速回忆核心概念，再做一个自测问题。",
                    action_label="安排复习",
                    action_href=_guide_href(course_id, f"review:{focus_title}"),
                    capability="deep_question",
                    prompt=f"请根据我的学习画像，为「{focus_title}」安排一个 5 分钟复习任务。",
                ),
                _brief_step("记录一句反思", 2, "写下还想继续深入的地方。"),
            ]
            criteria = ["完成一次复习", "保留反思证据", "进入下一节前状态稳定"]

        return {
            "headline": headline,
            "summary": summary_text,
            "mode": mode,
            "mode_label": mode_label,
            "focus": {
                "concept_id": focus.concept_id if focus else "",
                "title": focus_title,
                "status": focus.status if focus else "unknown",
                "status_label": _status_label(focus.status if focus else "unknown"),
                "score": round(focus.score * 100) if focus else 0,
            },
            "timebox_minutes": timebox,
            "score": overall_score,
            "score_label": f"{overall_score} 分" if event_count else "待建立",
            "confidence_label": learner_receipt.get("confidence_label") or "等待证据",
            "agenda": agenda[:4],
            "success_criteria": criteria[:4],
            "avoid": _brief_avoid_list(mode=mode, open_mistakes=open_mistakes),
            "writes_back": sorted({item for action in actions[:2] for item in action.writes_back} or {"profile", "mastery"}),
            "primary_action_id": primary_action.id if primary_action else "",
            "knowledge_evidence": _study_knowledge_evidence(
                knowledge_context,
                focus_title=focus_title,
            ),
        }

    def _explain_report(
        self,
        *,
        events: list[dict[str, Any]],
        concepts: list[ConceptMasteryState],
        dimensions: list[dict[str, Any]],
        summary: dict[str, Any],
        remediation_loop: dict[str, Any],
        actions: list[NextBestAction],
        overall_score: int,
        overall_label: str,
        learner_receipt: dict[str, Any],
        study_brief: dict[str, Any],
        knowledge_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Explain the assessment in user-facing language."""

        event_count = int(summary.get("event_count") or 0)
        answered_count = int(summary.get("answered_count") or 0)
        resource_count = int(summary.get("resource_count") or 0)
        scored_count = int(summary.get("scored_count") or 0)
        open_mistakes = int(summary.get("open_mistake_count") or 0)
        pending_loop = int(remediation_loop.get("pending_remediation_count") or 0)
        ready_loop = int(remediation_loop.get("ready_for_retest_count") or 0)
        closed_loop = int(remediation_loop.get("closed_count") or 0)
        primary_action = actions[0] if actions else None
        weak_concepts = [
            item
            for item in concepts
            if item.status in {"needs_foundation", "needs_support", "unknown"} or item.open_mistake_count
        ]
        focus = weak_concepts[0] if weak_concepts else (concepts[0] if concepts else None)
        confidence = _explain_confidence(event_count=event_count, scored_count=scored_count, source_count=len(summary.get("sources") or []))
        score_breakdown = _score_breakdown(dimensions)
        attention = [item for item in score_breakdown if int(item.get("score") or 0) < 60][:3]
        support = [item for item in score_breakdown if int(item.get("score") or 0) >= 72][:2]

        if event_count <= 0:
            headline = "这不是低分，而是证据还不够"
            summary_text = "系统现在只知道你还没有留下可评分学习证据，所以先建议做一次小诊断来建立画像基线。"
        elif focus:
            headline = f"主要判断依据是「{focus.title}」还需要处理"
            summary_text = (
                f"系统综合了 {event_count} 条证据，发现「{focus.title}」处于「{_status_label(focus.status)}」。"
                f"当前建议先执行「{primary_action.title if primary_action else study_brief.get('headline') or '下一步学习任务'}」。"
            )
        else:
            headline = f"当前状态是「{overall_label}」"
            summary_text = (
                f"系统综合了 {event_count} 条证据后给出 {overall_score} 分。"
                f"下一步是「{primary_action.title if primary_action else study_brief.get('headline') or '保持节奏'}」。"
            )

        evidence_used = [
            {
                "label": "作答证据",
                "value": f"{answered_count} 次",
                "detail": f"正确率约 {round(float(summary.get('accuracy') or 0) * 100)}%，用于判断知识掌握。",
                "tone": "brand" if answered_count else "thin_evidence",
            },
            {
                "label": "资源行为",
                "value": f"{resource_count} 个",
                "detail": "图解、视频、笔记和保存行为会影响资源偏好与投入度。",
                "tone": "brand" if resource_count else "neutral",
            },
            {
                "label": "错因闭环",
                "value": f"待补 {pending_loop} / 待测 {ready_loop} / 已闭 {closed_loop}",
                "detail": f"仍有 {open_mistakes} 个错因信号会拉低闭环评分。",
                "tone": "warning" if open_mistakes or pending_loop else "success",
            },
        ]
        if focus:
            evidence_used.append(
                {
                    "label": "当前焦点",
                    "value": focus.title,
                    "detail": f"{_status_label(focus.status)}，掌握度约 {round(focus.score * 100)}%，置信度约 {round(focus.confidence * 100)}%。",
                    "tone": "warning" if focus.status in {"needs_foundation", "needs_support", "unknown"} else "brand",
                }
            )
        knowledge_evidence = _explain_knowledge_evidence(knowledge_context)
        if knowledge_evidence:
            evidence_used.append(knowledge_evidence)

        decision_rules = [
            {
                "label": "先看证据量",
                "result": f"{event_count} 条证据，{scored_count} 条可评分。",
                "status": "warning" if confidence["level"] in {"low", "none"} else "success",
                "explanation": "证据越少，系统越倾向于推荐诊断而不是直接下结论。",
            },
            {
                "label": "再看知识掌握",
                "result": _dimension_result(score_breakdown, "mastery"),
                "status": _dimension_rule_status(score_breakdown, "mastery"),
                "explanation": "答题、任务完成和复测结果会共同影响掌握度。",
            },
            {
                "label": "最后看错因是否闭环",
                "result": f"待处理错因 {open_mistakes} 个。",
                "status": "warning" if open_mistakes else "success",
                "explanation": "答错后如果没有补救和复测，系统不会把它视为真正掌握。",
            },
        ]

        action_rationale = {
            "title": primary_action.title if primary_action else study_brief.get("headline") or "继续学习",
            "reason": primary_action.reason if primary_action else learner_receipt.get("reason") or summary_text,
            "because": _action_because(
                primary_action=primary_action,
                focus=focus,
                event_count=event_count,
                open_mistakes=open_mistakes,
                confidence_label=confidence["label"],
                knowledge_context=knowledge_context,
            ),
            "will_update": primary_action.writes_back if primary_action else study_brief.get("writes_back") or ["profile", "mastery"],
        }

        return {
            "headline": headline,
            "summary": summary_text,
            "confidence": confidence,
            "evidence_used": evidence_used,
            "decision_rules": decision_rules,
            "score_breakdown": score_breakdown,
            "attention_factors": attention,
            "supporting_factors": support,
            "action_rationale": action_rationale,
            "plain_language": [
                "系统不是只看最后一次回答，而是综合作答、资源使用、反思和错因闭环。",
                "证据不足时，系统会优先建议诊断；错因未闭环时，会优先建议补救或复测。",
                "完成下一步后，新证据会写回同一个学习画像，下一次建议会随之变化。",
            ],
        }

    @staticmethod
    def _concept_summary(concepts: list[ConceptMasteryState]) -> dict[str, Any]:
        by_status: dict[str, int] = {}
        for item in concepts:
            by_status[item.status] = by_status.get(item.status, 0) + 1
        average = round(sum(item.score for item in concepts) / len(concepts), 3) if concepts else 0.0
        return {"count": len(concepts), "average_score": average, "by_status": by_status}


def _learning_effect_demo_markdown(summary: dict[str, Any]) -> str:
    """Render the compact summary as a one-page Markdown proof."""

    lines = [
        "# 学习效果评估闭环摘要",
        "",
        f"**当前判断**：{summary.get('headline') or '学习效果评估摘要'}",
        "",
        f"- 状态：{summary.get('status_label') or '待评估'}",
        f"- 分数：{summary.get('score_label') or summary.get('score') or 0}",
        f"- 可信度：{summary.get('confidence_label') or '等待证据'}",
        "",
        "## 证据链",
        "",
    ]
    for item in summary.get("proof_points") or []:
        if not isinstance(item, dict):
            continue
        lines.append(f"- **{item.get('label') or '证据'}**：{item.get('value') or ''}。{item.get('detail') or ''}".strip())

    explainability = summary.get("explainability") if isinstance(summary.get("explainability"), dict) else {}
    if explainability:
        confidence = explainability.get("confidence") if isinstance(explainability.get("confidence"), dict) else {}
        lines.extend(
            [
                "",
                "## 为什么这样判断",
                "",
                f"- 解释：{explainability.get('summary') or explainability.get('headline') or '系统综合证据生成判断。'}",
                f"- 可信度：{confidence.get('label') or '等待证据'}。{confidence.get('reason') or ''}".strip(),
            ]
        )
        for rule in explainability.get("decision_rules") or []:
            if isinstance(rule, dict):
                lines.append(f"- {rule.get('label') or '规则'}：{rule.get('result') or ''}".strip())

    study_brief = summary.get("study_brief") if isinstance(summary.get("study_brief"), dict) else {}
    if study_brief:
        lines.extend(
            [
                "",
                "## 今日学习安排",
                "",
                f"- 主题：{study_brief.get('headline') or '继续学习'}",
                f"- 时间盒：{study_brief.get('timebox_minutes') or 10} 分钟",
                f"- 说明：{study_brief.get('summary') or '按当前画像只推进一个最小任务。'}",
            ]
        )
        for step in study_brief.get("agenda") or []:
            if isinstance(step, dict):
                lines.append(f"- {step.get('label') or '学习步骤'}：{step.get('minutes') or 0} 分钟。{step.get('detail') or ''}".strip())

    action = summary.get("primary_action") if isinstance(summary.get("primary_action"), dict) else {}
    if action:
        lines.extend(
            [
                "",
                "## 下一步处方",
                "",
                f"- 动作：{action.get('title') or '继续学习'}",
                f"- 原因：{action.get('reason') or '系统会根据新证据继续调整。'}",
                f"- 入口：`{action.get('href') or ''}`",
            ]
        )

    weak_concepts = [item for item in summary.get("weak_concepts") or [] if isinstance(item, dict)]
    if weak_concepts:
        lines.extend(["", "## 优先薄弱点", ""])
        for item in weak_concepts[:5]:
            label = item.get("title") or item.get("concept_id") or "未命名概念"
            status = _status_label(str(item.get("status") or "unknown"))
            raw_score = _as_float(item.get("score"), 0.0) or 0.0
            score = round(raw_score * 100) if raw_score <= 1 else round(raw_score)
            lines.append(f"- {label}：{status}，掌握度约 {score}%。")

    alignment = [item for item in summary.get("requirement_alignment") or [] if isinstance(item, dict)]
    if alignment:
        lines.extend(["", "## 赛题要求对齐", ""])
        for item in alignment:
            lines.append(
                f"- **{item.get('requirement') or '要求'}**：{item.get('status') or '待补充'}。{item.get('evidence') or ''}".strip()
            )

    talking_points = [str(item).strip() for item in summary.get("talking_points") or [] if str(item).strip()]
    if talking_points:
        lines.extend(["", "## 答辩讲法", ""])
        for item in talking_points[:6]:
            lines.append(f"- {item}")

    return "\n".join(lines).strip() + "\n"


def _brief_step(
    label: str,
    minutes: int,
    detail: str,
    *,
    action_label: str = "",
    action_href: str = "",
    capability: str = "",
    prompt: str = "",
) -> dict[str, Any]:
    return {
        "label": _clean(label, 120) or "学习步骤",
        "minutes": max(1, min(int(minutes or 1), 45)),
        "detail": _clean(detail, 220),
        "action_label": _clean(action_label, 40),
        "action_href": _clean(action_href, 1200),
        "capability": _clean(capability, 80),
        "prompt": _clean(prompt, 600),
    }


def _brief_mode_label(mode: str) -> str:
    return {
        "diagnostic": "诊断起步",
        "generate_visual": "图解补基",
        "generate_practice": "练习验证",
        "retest": "复测确认",
        "mistake_review": "错因闭环",
        "generate_resource": "资料补充",
        "advance": "进阶迁移",
        "baseline": "建立基线",
        "remediation": "补救错因",
        "maintain": "保持节奏",
    }.get(str(mode or ""), "继续学习")


def _supporting_brief_steps(action: NextBestAction, focus_title: str) -> list[dict[str, Any]]:
    action_type = str(action.type or "")
    if action_type == "generate_visual":
        return [
            _brief_step("复述图解", 2, "看完后用一句话说清核心关系。"),
            _brief_step("做 1 题验证", 4, "用小题确认不是只看懂画面。", action_href=_guide_href("", f"practice:{focus_title}"), action_label="做练习"),
        ]
    if action_type == "generate_practice":
        return [
            _brief_step("提交答案", 2, "不要只在心里想，提交后系统才能回写画像。"),
            _brief_step("看错因反馈", 3, "只处理本组最关键的一个错因。"),
        ]
    if action_type == "retest":
        return [_brief_step("对照错题", 3, "如果复测出错，先解释错误原因，再决定是否补救。")]
    if action_type == "mistake_review":
        return [_brief_step("写错因句子", 3, "格式：我之前把 A 当成 B，现在判断依据是 C。")]
    if action_type == "advance":
        return [_brief_step("记录迁移场景", 3, "写下这个知识点可以用在哪个真实任务里。")]
    return [_brief_step("留下反馈", 2, "完成后点记录或写一句反思，让系统更新下一步。")]


def _brief_success_criteria(action_type: str, focus_title: str) -> list[str]:
    if action_type == "generate_visual":
        return [f"能口头解释「{focus_title}」", "完成 1 题验证", "资源偏好写回画像"]
    if action_type == "generate_practice":
        return ["完成并提交练习", "收到对错反馈", "下一步建议发生更新"]
    if action_type == "retest":
        return ["独立完成复测", "正确率达到 80% 左右", "错因状态被关闭或继续补救"]
    if action_type == "mistake_review":
        return ["说清一个错因", "完成补救动作", "进入复测等待"]
    if action_type == "advance":
        return ["完成一个迁移任务", "写下应用场景", "准备进入下一节"]
    return ["完成当前动作", "留下学习证据", "画像与下一步同步更新"]


def _brief_avoid_list(*, mode: str, open_mistakes: int) -> list[str]:
    items = ["不要一次打开太多资料", "不要只看不提交"]
    if mode in {"remediation", "mistake_review"} or open_mistakes:
        items.insert(0, "先关一个错因，不要同时补多个点")
    if mode in {"retest", "advance"}:
        items.append("不要在复测前继续刷讲解")
    return items[:3]


def _select_learning_kb(manager: Any, kb_names: list[str], course_id: str) -> str:
    candidates = []
    raw_course = _clean(course_id, 120)
    if raw_course:
        candidates.extend(
            [
                raw_course,
                raw_course.lower(),
                raw_course.replace("_", "-"),
                raw_course.replace("-", "_"),
            ]
        )
    for candidate in candidates:
        if candidate in kb_names:
            return candidate
    try:
        default = _clean(manager.get_default(), 120) if hasattr(manager, "get_default") else ""
        if default and default in kb_names:
            return default
    except Exception:
        pass
    return kb_names[0] if kb_names else ""


def _empty_knowledge_context(*, focus_title: str, status: str, summary: str) -> dict[str, Any]:
    status_label = "未连接" if status == "missing" else "需检查"
    return {
        "available": False,
        "ready": False,
        "status": status,
        "status_label": status_label,
        "kb_name": "",
        "provider": "",
        "document_count": 0,
        "focus_query": focus_title,
        "summary": summary,
        "action_label": "打开资料库",
        "action_href": "/knowledge",
        "latest_eval": {"available": False},
        "can_ground_actions": False,
    }


def _load_latest_knowledge_eval(manager: Any, kb_name: str) -> dict[str, Any] | None:
    try:
        kb_path = manager.get_knowledge_base_path(kb_name)
        path = kb_path / "rag_eval" / "latest.json"
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _summarize_knowledge_eval(report: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(report, dict) or not report:
        return {"available": False}
    summary_rows = [item for item in report.get("summary") or [] if isinstance(item, dict)]
    experiment = report.get("experiment_summary") if isinstance(report.get("experiment_summary"), dict) else {}
    leader_name = _clean(experiment.get("quality_leader") or report.get("baseline_strategy") or "baseline", 120)
    row = next((item for item in summary_rows if str(item.get("strategy") or "") == leader_name), None)
    if row is None:
        baseline = _clean(report.get("baseline_strategy") or "baseline", 120)
        row = next((item for item in summary_rows if str(item.get("strategy") or "") == baseline), None)
    if row is None and summary_rows:
        row = summary_rows[0]
    row = row or {}
    source_hit = _safe_number(row.get("source_hit_rate"))
    ndcg = _safe_number(row.get("avg_source_ndcg"))
    success = _safe_number(row.get("success_rate"))
    quality = source_hit if source_hit is not None else success
    return {
        "available": True,
        "created_at": report.get("created_at"),
        "case_count": _safe_int_value(report.get("case_count") or row.get("cases")),
        "strategy": leader_name,
        "decision": experiment.get("decision") or "",
        "decision_label": experiment.get("label") or "",
        "quality_label": _knowledge_quality_label(quality),
        "source_hit_rate": source_hit,
        "source_ndcg": ndcg,
        "success_rate": success,
        "diagnostic_headline": dict(report.get("diagnostic_summary") or {}).get("headline") or "",
    }


def _knowledge_quality_label(value: float | None) -> str:
    if value is None:
        return "已评测"
    if value >= 0.85:
        return "证据命中高"
    if value >= 0.65:
        return "证据可用"
    return "需要补强"


def _knowledge_status_label(*, status: str, ready: bool, eval_summary: dict[str, Any]) -> str:
    if status == "needs_reindex":
        return "需重建索引"
    if not ready:
        return "待检查"
    if eval_summary.get("available"):
        return str(eval_summary.get("quality_label") or "已评测")
    return "可检索"


def _knowledge_context_summary(
    *,
    kb_name: str,
    ready: bool,
    document_count: int,
    status_label: str,
    quality_label: str,
) -> str:
    if not ready:
        return f"资料库「{kb_name}」当前为「{status_label}」，建议先完成修复或重建索引。"
    if quality_label:
        return f"资料库「{kb_name}」已可检索，包含 {document_count} 份资料；最近评测显示「{quality_label}」。"
    return f"资料库「{kb_name}」已可检索，包含 {document_count} 份资料；建议补一次检索评测作为质量基线。"


def _study_knowledge_evidence(
    knowledge_context: dict[str, Any] | None,
    *,
    focus_title: str,
) -> dict[str, Any] | None:
    if not isinstance(knowledge_context, dict) or not knowledge_context.get("kb_name"):
        return None
    latest_eval = knowledge_context.get("latest_eval") if isinstance(knowledge_context.get("latest_eval"), dict) else {}
    metrics: list[dict[str, str]] = [
        {"label": "资料", "value": f"{_safe_int_value(knowledge_context.get('document_count'))} 份"},
        {"label": "状态", "value": str(knowledge_context.get("status_label") or "待检查")},
    ]
    if latest_eval.get("available"):
        source_hit = _safe_number(latest_eval.get("source_hit_rate"))
        ndcg = _safe_number(latest_eval.get("source_ndcg"))
        if source_hit is not None:
            metrics.append({"label": "来源命中", "value": _format_percent(source_hit)})
        if ndcg is not None:
            metrics.append({"label": "证据排序", "value": _format_percent(ndcg)})
    return {
        "title": "资料依据",
        "kb_name": knowledge_context.get("kb_name") or "",
        "summary": knowledge_context.get("summary") or f"围绕「{focus_title}」执行下一步时会优先检查资料库。",
        "status_label": knowledge_context.get("status_label") or "",
        "focus_query": knowledge_context.get("focus_query") or focus_title,
        "action_label": knowledge_context.get("action_label") or "打开资料库",
        "action_href": knowledge_context.get("action_href") or "/knowledge",
        "ready": bool(knowledge_context.get("ready")),
        "metrics": metrics[:4],
    }


def _explain_knowledge_evidence(knowledge_context: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(knowledge_context, dict) or not knowledge_context.get("kb_name"):
        return None
    latest_eval = knowledge_context.get("latest_eval") if isinstance(knowledge_context.get("latest_eval"), dict) else {}
    parts = [str(knowledge_context.get("summary") or "").strip()]
    if latest_eval.get("available"):
        source_hit = _safe_number(latest_eval.get("source_hit_rate"))
        if source_hit is not None:
            parts.append(f"来源命中约 {_format_percent(source_hit)}。")
    return {
        "label": "资料依据",
        "value": str(knowledge_context.get("status_label") or knowledge_context.get("kb_name") or "资料库"),
        "detail": " ".join(part for part in parts if part).strip(),
        "tone": "success" if knowledge_context.get("ready") else "warning",
    }


def _knowledge_context_can_ground(knowledge_context: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(knowledge_context, dict)
        and knowledge_context.get("can_ground_actions")
        and _clean(knowledge_context.get("kb_name"), 120)
    )


def _knowledge_action_instruction(knowledge_context: dict[str, Any] | None) -> str:
    if not _knowledge_context_can_ground(knowledge_context):
        return ""
    kb_name = _clean((knowledge_context or {}).get("kb_name"), 120)
    focus = _clean((knowledge_context or {}).get("focus_query"), 120)
    latest_eval = (knowledge_context or {}).get("latest_eval")
    latest_eval = latest_eval if isinstance(latest_eval, dict) else {}
    quality = _clean(latest_eval.get("quality_label"), 80)
    suffix = f"最近评测：{quality}。" if quality else "如果资料不足，请明确说明。"
    return f"\n\n请优先检索并引用资料库「{kb_name}」中与「{focus or '当前主题'}」相关的材料；{suffix}"


def _safe_int_value(value: Any) -> int:
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return 0


def _safe_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_percent(value: float) -> str:
    return f"{round(max(0.0, min(1.0, float(value))) * 100)}%"


def _explain_confidence(*, event_count: int, scored_count: int, source_count: int) -> dict[str, Any]:
    if event_count <= 0:
        return {
            "level": "none",
            "label": "等待证据",
            "score": 0,
            "reason": "还没有学习事件，系统只能建议先诊断。",
        }
    raw = _clamp(0.18 + min(event_count, 12) * 0.045 + min(scored_count, 8) * 0.07 + min(source_count, 5) * 0.05, 0.0, 1.0)
    score = round(raw * 100)
    if score >= 72:
        level = "high"
        label = "解释较可靠"
    elif score >= 45:
        level = "medium"
        label = "初步可信"
    else:
        level = "low"
        label = "证据偏少"
    return {
        "level": level,
        "label": label,
        "score": score,
        "reason": f"基于 {event_count} 条事件、{scored_count} 条可评分证据和 {source_count} 类来源估算。",
    }


def _score_breakdown(dimensions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for dimension in dimensions:
        id_ = str(dimension.get("id") or "")
        score = max(0, min(100, int(dimension.get("score") or 0)))
        weight = LEARNING_EFFECT_DIMENSION_WEIGHTS.get(id_, 0.0)
        items.append(
            {
                "id": id_,
                "label": dimension.get("label") or learning_effect_dimension_label(id_),
                "score": score,
                "weight": weight,
                "weight_label": f"{round(weight * 100)}%",
                "impact": round(score * weight, 1),
                "status": dimension.get("status") or _effect_status(score),
                "evidence": dimension.get("evidence") or "",
                "explanation": _dimension_explanation(id_, score, str(dimension.get("evidence") or "")),
            }
        )
    items.sort(key=lambda item: (int(item["score"]), -float(item["weight"])))
    return items


def learning_effect_dimension_label(id_: str) -> str:
    return {
        "mastery": "知识掌握",
        "progress": "学习推进",
        "stability": "稳定迁移",
        "evidence_quality": "证据质量",
        "engagement": "学习投入",
        "remediation": "错因闭环",
        "resource_effectiveness": "资源有效性",
    }.get(id_, "评估维度")


def _dimension_explanation(id_: str, score: int, evidence: str) -> str:
    prefix = {
        "mastery": "它反映你是否真的会做题和复测。",
        "progress": "它反映学习任务是否在持续推进。",
        "stability": "它反映知识点是否经过间隔复测后仍然稳定。",
        "evidence_quality": "它反映系统判断是否有足够依据。",
        "engagement": "它反映你是否真的使用了资源并完成任务。",
        "remediation": "它反映错因是否完成补救和复测。",
        "resource_effectiveness": "它反映资源是否带来后续练习或保存反馈。",
    }.get(id_, "它是综合评估的一部分。")
    if score < 50:
        suffix = "目前偏低，所以会拉低综合判断。"
    elif score < 72:
        suffix = "目前处于观察区，系统会继续收集证据。"
    else:
        suffix = "目前是支撑项，会提高综合判断。"
    return f"{prefix}{suffix} {evidence}".strip()


def _dimension_result(score_breakdown: list[dict[str, Any]], id_: str) -> str:
    item = next((entry for entry in score_breakdown if entry.get("id") == id_), None)
    if not item:
        return "暂无足够数据。"
    return f"{item.get('label')} {item.get('score')} 分，权重 {item.get('weight_label')}。"


def _dimension_rule_status(score_breakdown: list[dict[str, Any]], id_: str) -> str:
    item = next((entry for entry in score_breakdown if entry.get("id") == id_), None)
    score = int(item.get("score") or 0) if item else 0
    if score >= 72:
        return "success"
    if score >= 50:
        return "brand"
    return "warning"


def _action_because(
    *,
    primary_action: NextBestAction | None,
    focus: ConceptMasteryState | None,
    event_count: int,
    open_mistakes: int,
    confidence_label: str,
    knowledge_context: dict[str, Any] | None = None,
) -> list[str]:
    reasons: list[str] = []
    if event_count <= 0:
        reasons.append("还没有可评分证据，直接推荐学习材料会不够准。")
    if focus:
        reasons.append(f"当前焦点「{focus.title}」是「{_status_label(focus.status)}」，掌握度约 {round(focus.score * 100)}%。")
    if open_mistakes:
        reasons.append(f"仍有 {open_mistakes} 个错因没有完成补救和复测。")
    if primary_action:
        reasons.append(f"这个动作预计 {primary_action.estimated_minutes or 8} 分钟，完成后会回写 {', '.join(primary_action.writes_back or ['profile'])}。")
    if _knowledge_context_can_ground(knowledge_context):
        kb_name = str((knowledge_context or {}).get("kb_name") or "").strip()
        reasons.append(f"执行时会附带资料库「{kb_name}」，优先检索与当前卡点相关的材料。")
    reasons.append(f"当前解释可信度：{confidence_label}。")
    return reasons[:4]


def _flatten_learning_event(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    signals = payload.get("signals") if isinstance(payload.get("signals"), dict) else {}
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    concept_ids = payload.get("concept_ids") or metadata.get("concepts") or metadata.get("concept_ids") or []
    concepts = [_clean(item, 120) for item in _labels_from_value(concept_ids) if _clean(item, 120)]
    return {
        "source": payload.get("source") or "learning_effect",
        "source_id": payload.get("source_id") or payload.get("id") or "",
        "actor": payload.get("actor") or "learner",
        "verb": payload.get("verb") or "observed",
        "object_type": payload.get("object_type") or "learning_activity",
        "object_id": payload.get("object_id") or (concepts[0] if concepts else ""),
        "title": payload.get("title") or payload.get("object_id") or "学习事件",
        "summary": payload.get("summary") or "",
        "course_id": payload.get("course_id") or metadata.get("course_id") or "",
        "node_id": payload.get("node_id") or metadata.get("node_id") or "",
        "task_id": payload.get("task_id") or metadata.get("task_id") or "",
        "resource_type": payload.get("resource_type") or metadata.get("resource_type") or "",
        "score": result.get("score", payload.get("score")),
        "is_correct": result.get("is_correct", payload.get("is_correct")),
        "duration_seconds": result.get("duration_seconds", payload.get("duration_seconds")),
        "confidence": payload.get("confidence") or 0.68,
        "reflection": signals.get("reflection") or payload.get("reflection") or "",
        "mistake_types": signals.get("mistake_types") or payload.get("mistake_types") or [],
        "created_at": payload.get("created_at"),
        "weight": payload.get("weight") or 1.0,
        "metadata": {
            **metadata,
            "concepts": concepts,
            "concept_id": _safe_id(concepts[0]).lower() if concepts else metadata.get("concept_id", ""),
            "difficulty": result.get("difficulty", metadata.get("difficulty", "")),
            "attempt_count": result.get("attempt_count", metadata.get("attempt_count", "")),
            "source_event_id": payload.get("id") or "",
        },
    }


def _concept_candidates(event: dict[str, Any]) -> list[tuple[str, str]]:
    metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
    labels: list[str] = []
    for key in ("concepts", "concept_ids", "knowledge_points", "tags"):
        for label in _labels_from_value(metadata.get(key)):
            if label not in labels:
                labels.append(label)
    for key in ("primary_concept", "concept", "concept_id", "node_id"):
        label = _clean(metadata.get(key) or event.get(key), 120)
        if label and label not in labels:
            labels.append(label)
    object_type = str(event.get("object_type") or "")
    object_id = _clean(event.get("object_id"), 120)
    if object_id and object_type in {"quiz", "quiz_item", "concept", "guide_task", "learning_objective"}:
        labels.append(object_id)
    for mistake in _mistake_labels(event):
        if mistake.startswith("concept:"):
            label = _clean(mistake.split(":", 1)[1], 120)
            if label and label not in labels:
                labels.append(label)
    pairs: list[tuple[str, str]] = []
    for label in labels:
        concept_id = _safe_id(label).lower()
        if concept_id and concept_id not in {item[0] for item in pairs}:
            pairs.append((concept_id, label))
    return pairs[:8]


def _event_remediation_task(event: dict[str, Any]) -> dict[str, Any]:
    metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
    direct = metadata.get("remediation_task")
    if isinstance(direct, dict):
        return direct
    feedback = metadata.get("learning_feedback")
    if isinstance(feedback, dict) and isinstance(feedback.get("remediation_task"), dict):
        return dict(feedback["remediation_task"])
    return {}


def _event_task_ids(event: dict[str, Any]) -> list[str]:
    metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
    candidates = [
        event.get("task_id"),
        event.get("source_id"),
        metadata.get("task_id"),
        metadata.get("target_task_id"),
    ]
    if str(event.get("object_type") or "") in {"guide_task", "learning_task", "intervention_action"}:
        candidates.append(event.get("object_id"))
    ids: list[str] = []
    for candidate in candidates:
        item = _clean(candidate, 160)
        if item and item not in ids:
            ids.append(item)
    return ids


def _remediation_loop_explanation(
    event: dict[str, Any],
    *,
    concept: str,
    status: str,
    source_score: float | None,
    completed_time: float,
    closed_time: float,
) -> dict[str, str]:
    title = _clean(event.get("title"), 120) or "一次练习反馈"
    mistakes = [item for item in _mistake_labels(event) if not item.startswith("concept:")]
    score_text = f"，得分约 {round(source_score * 100)}%" if source_score is not None else ""
    mistake_text = f"，主要错因是「{mistakes[0]}」" if mistakes else ""
    evidence_summary = f"系统依据「{title}」{score_text}{mistake_text}，判断「{concept}」还需要一次定向巩固。"

    if status == "closed":
        reason = "补救任务已经完成，并且后续复测出现了正确或高分证据。"
        next_step = "保持这个节奏，隔一段时间再做一次短复习，避免遗忘反弹。"
        progress_label = "已完成补救和复测"
    elif status == "ready_for_retest":
        reason = "补救任务已经完成，但还缺少一次复测证据来确认是否真正掌握。"
        next_step = "现在做一组 3 到 5 题的复测，系统会据此把状态更新为已闭环或继续补救。"
        progress_label = "补救完成，等待复测"
    else:
        reason = "最近的练习或反馈暴露出稳定薄弱点，系统已经生成了最小补救任务。"
        next_step = "先完成这条补救任务，再回到提交页做一次复测。"
        progress_label = "需要先补救"

    if completed_time and not closed_time and status == "ready_for_retest":
        evidence_summary += " 当前已有补救完成记录。"
    if closed_time:
        evidence_summary += " 当前已有复测通过记录。"

    return {
        "reason": reason,
        "evidence_summary": evidence_summary,
        "next_step": next_step,
        "progress_label": progress_label,
    }


def _remediation_action_payload(*, concept: str, status: str, resource_type: str) -> dict[str, Any]:
    topic = _clean(concept, 120) or "当前薄弱点"
    normalized_resource = _clean(resource_type, 40).lower()
    if status == "ready_for_retest":
        prompt = (
            f"请围绕「{topic}」生成 3 道复测题，题型混合选择题、判断题和简答题。"
            "每题给出答案、解析、考察概念和错因提示，最后判断是否可以闭环。"
        )
        return {
            "label": "去复测",
            "capability": "deep_question",
            "prompt": prompt,
            "config": {
                "mode": "custom",
                "topic": topic,
                "num_questions": 3,
                "difficulty": "auto",
                "question_type": "mixed",
                "purpose": "retest",
            },
            "href": _chat_href(prompt, "deep_question"),
        }
    if status == "closed":
        prompt = f"请根据我的学习画像，为「{topic}」安排一个 5 分钟的间隔复习任务，只保留一个小目标和一个自测问题。"
        return {
            "label": "安排复习",
            "capability": "chat",
            "prompt": prompt,
            "config": {"purpose": "spaced_review", "topic": topic},
            "href": _chat_href(prompt, "chat"),
        }
    if normalized_resource in {"quiz", "practice", "question", "questions", "exercise"}:
        prompt = (
            f"请围绕「{topic}」生成一组补救练习，包含选择题、判断题、填空题和简答题。"
            "每题都要有答案、解析和常见错因提醒。"
        )
        return {
            "label": "做补救题",
            "capability": "deep_question",
            "prompt": prompt,
            "config": {
                "mode": "custom",
                "topic": topic,
                "num_questions": 5,
                "difficulty": "auto",
                "question_type": "mixed",
                "purpose": "remediation_practice",
            },
            "href": _chat_href(prompt, "deep_question"),
        }
    prompt = f"请为「{topic}」生成一张补救图解，突出概念边界、关键步骤和最容易混淆的点。"
    return {
        "label": "开始补救",
        "capability": "visualize",
        "prompt": prompt,
        "config": {"render_mode": "auto", "topic": topic, "purpose": "remediation_visual"},
        "href": _chat_href(prompt, "visualize"),
    }


def _visual_timeline_event(event: dict[str, Any]) -> dict[str, Any]:
    score = _event_score(event)
    concept_labels = [title for _concept_id, title in _concept_candidates(event)]
    return {
        "id": event.get("id") or "",
        "label": _clean(event.get("title"), 80) or _event_kind_label(event),
        "detail": _timeline_detail(event, concept_labels),
        "kind": _event_kind(event),
        "score": round(score * 100) if score is not None else None,
        "created_at": event.get("created_at"),
        "source": event.get("source") or "",
    }


def _timeline_detail(event: dict[str, Any], concepts: list[str]) -> str:
    parts = [_event_kind_label(event)]
    if concepts:
        parts.append("、".join(concepts[:2]))
    source = _clean(event.get("source"), 40)
    if source:
        parts.append(source)
    return " · ".join(parts)


def _event_kind(event: dict[str, Any]) -> str:
    verb = str(event.get("verb") or "")
    object_type = str(event.get("object_type") or "")
    if verb == "answered" or object_type in {"quiz", "quiz_item"}:
        return "quiz"
    if verb == "completed":
        return "completion"
    if _is_resource_event(event):
        return "resource"
    if verb in {"saved", "viewed", "played"}:
        return "resource"
    if _clean(event.get("reflection"), 20):
        return "reflection"
    return "evidence"


def _event_kind_label(event: dict[str, Any]) -> str:
    labels = {
        "quiz": "练习作答",
        "completion": "任务完成",
        "resource": "资源使用",
        "reflection": "学习反思",
        "evidence": "学习证据",
    }
    return labels.get(_event_kind(event), "学习证据")


def _event_score(event: dict[str, Any]) -> float | None:
    score = _as_float(event.get("score"), None)
    if score is not None:
        if score > 1:
            score = score / 100
        score = _clamp(score, 0.0, 1.0)
    elif event.get("is_correct") is True:
        score = 1.0
    elif event.get("is_correct") is False:
        score = 0.0
    elif event.get("verb") == "completed":
        score = 0.72
    elif event.get("verb") in {"saved", "viewed", "played"}:
        score = 0.55
    if score is None:
        return None
    difficulty = str(dict(event.get("metadata") or {}).get("difficulty") or "").lower()
    if event.get("is_correct") is True:
        if difficulty in {"hard", "difficult", "高", "困难"}:
            score = min(1.0, score + 0.08)
        elif difficulty in {"easy", "low", "低", "简单"}:
            score = max(0.0, score - 0.04)
    elif event.get("is_correct") is False:
        if difficulty in {"hard", "difficult", "高", "困难"}:
            score = max(score, 0.18)
    return round(_clamp(score, 0.0, 1.0), 3)


def _event_weight(event: dict[str, Any]) -> float:
    source = str(event.get("source") or "")
    verb = str(event.get("verb") or "")
    object_type = str(event.get("object_type") or "")
    weight = _as_float(event.get("weight"), 1.0) or 1.0
    if object_type in {"quiz", "quiz_item"} or verb == "answered":
        weight *= 1.15
    if "diagnostic" in source or "diagnostic" in object_type:
        weight *= 1.2
    if "profile_calibration" in source:
        weight *= 0.8
    if _is_resource_event(event):
        weight *= 0.45
    return _clamp(weight, 0.1, 2.0)


def _rolling_score(scores: list[tuple[float, float, float, dict[str, Any]]]) -> float:
    if not scores:
        return 0.0
    value = 0.45
    for score, weight, _, _ in sorted(scores, key=lambda item: item[2]):
        alpha = _clamp(0.22 * weight, 0.12, 0.48)
        value = value * (1 - alpha) + score * alpha
    return _clamp(value, 0.0, 1.0)


def _trend(scores: list[tuple[float, float, float, dict[str, Any]]]) -> str:
    if len(scores) < 3:
        return "flat"
    ordered = sorted(scores, key=lambda item: item[2])
    midpoint = len(ordered) // 2
    early = [item[0] for item in ordered[:midpoint]]
    late = [item[0] for item in ordered[midpoint:]]
    if not early or not late:
        return "flat"
    delta = sum(late) / len(late) - sum(early) / len(early)
    if delta > 0.08:
        return "up"
    if delta < -0.08:
        return "down"
    return "flat"


def _confidence(event_count: int, scored_count: int, source_count: int) -> float:
    return round(_clamp(0.18 + event_count * 0.06 + scored_count * 0.08 + source_count * 0.06, 0.0, 1.0), 3)


def _mastery_status(score: float, scored_count: int) -> str:
    if scored_count == 0:
        return "unknown"
    if score < 0.35:
        return "needs_foundation"
    if score < 0.55:
        return "needs_support"
    if score < 0.75:
        return "practicing"
    if score < 0.88:
        return "proficient"
    return "mastered"


def _next_review_at(last_time: float | None, status: str) -> float | None:
    if not last_time:
        return None
    days = {
        "needs_foundation": 1,
        "needs_support": 1,
        "practicing": 3,
        "proficient": 7,
        "mastered": 21,
    }.get(status)
    return last_time + days * 86400 if days else None


def _concept_recommendation(status: str, open_mistakes: int, trend: str) -> str:
    if status in {"unknown", "needs_foundation"}:
        return "先做诊断或看入门图解，建立第一条可靠证据。"
    if status == "needs_support":
        return "先补齐概念边界，再做少量可评分练习。"
    if open_mistakes:
        return "优先关闭最近错因，再安排复测。"
    if trend == "down":
        return "最近趋势下滑，建议做混合复测。"
    if status in {"proficient", "mastered"}:
        return "可以进入迁移应用或下一节。"
    return "继续用练习巩固，完成后回写画像。"


def _is_mastery_signal(event: dict[str, Any], score: float | None) -> bool:
    if score is None:
        return False
    if _is_resource_event(event) and event.get("verb") == "generated":
        return False
    return True


def _is_resource_event(event: dict[str, Any]) -> bool:
    return str(event.get("object_type") or "") == "resource" or bool(event.get("resource_type"))


def _mistake_labels(event: dict[str, Any]) -> list[str]:
    labels = [_clean(item, 100) for item in event.get("mistake_types") or [] if _clean(item, 100)]
    metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
    for key in ("mistake_types", "mistakes", "error_types"):
        for item in _labels_from_value(metadata.get(key)):
            if item and item not in labels:
                labels.append(item)
    return labels[:8]


def _dimension(id_: str, label: str, score: int, evidence: str) -> dict[str, Any]:
    value = max(0, min(int(score), 100))
    return {"id": id_, "label": label, "score": value, "status": _effect_status(value), "evidence": evidence}


def _effect_status(score: int) -> str:
    if score >= 80:
        return "good"
    if score >= 60:
        return "watch"
    if score >= 40:
        return "needs_support"
    return "thin_evidence"


def _weighted_score(dimensions: list[dict[str, Any]], weights: dict[str, float]) -> int:
    if not dimensions:
        return 0
    return round(sum(int(item.get("score") or 0) * weights.get(str(item.get("id") or ""), 0) for item in dimensions))


def _overall_label(score: int, *, evidence_count: int, open_mistakes: int) -> str:
    if evidence_count == 0:
        return "需要先建立基线"
    if open_mistakes >= 3 or score < 50:
        return "需要补基"
    if score < 72:
        return "正在进步"
    if score < 86:
        return "状态良好"
    return "可以进阶"


def _overall_summary(label: str, score: int, actions: list[NextBestAction]) -> str:
    if actions:
        return f"{label}，综合评分 {score}。建议先执行：{actions[0].title}。"
    return f"{label}，综合评分 {score}。继续保持当前节奏。"


def _receipt_confidence_label(*, event_count: int, scored_count: int, resource_count: int) -> str:
    if event_count <= 0:
        return "等待证据"
    if scored_count >= 4 and event_count >= 8:
        return "证据较充分"
    if scored_count >= 2 or (event_count >= 4 and resource_count >= 1):
        return "初步可靠"
    return "证据偏少"


def _receipt_action_label(action_type: str) -> str:
    return {
        "diagnostic": "开始诊断",
        "generate_visual": "看图解",
        "generate_practice": "做练习",
        "retest": "去复测",
        "mistake_review": "关掉错因",
        "generate_resource": "生成资料",
        "advance": "继续进阶",
    }.get(action_type, "执行这一步")


def _receipt_headline(*, overall_label: str, score: int, focus_title: str, action_title: str, event_count: int) -> str:
    if event_count <= 0:
        return "先做一次小诊断，建立学习画像基线"
    if focus_title:
        return f"当前先处理「{focus_title}」，再继续推进"
    if score >= 86:
        return "状态不错，可以进入迁移任务"
    if action_title:
        return f"现在先做：{action_title}"
    return f"{overall_label}，继续保持当前节奏"


def _status_rank(status: str) -> int:
    return {
        "needs_foundation": 0,
        "needs_support": 1,
        "unknown": 2,
        "practicing": 3,
        "proficient": 4,
        "mastered": 5,
    }.get(status, 2)


def _status_label(status: str) -> str:
    return {
        "unknown": "证据不足",
        "needs_foundation": "基础未稳",
        "needs_support": "需要补基",
        "practicing": "正在练习",
        "proficient": "基本熟练",
        "mastered": "稳定掌握",
    }.get(status, status)


def _window_cutoff(window: str) -> float | None:
    value = str(window or "").strip().lower()
    if value in {"", "all", "any"}:
        return None
    match = re.fullmatch(r"(\d+)\s*d", value)
    if match:
        return time.time() - int(match.group(1)) * 86400
    match = re.fullmatch(r"(\d+)\s*h", value)
    if match:
        return time.time() - int(match.group(1)) * 3600
    return None


def _event_time(event: dict[str, Any]) -> float:
    return _as_timestamp(event.get("created_at"))


def _as_timestamp(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    try:
        return float(text)
    except Exception:
        pass
    try:
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return 0.0


def _labels_from_value(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [_clean(part, 120) for part in re.split(r"[,，;；]", value) if _clean(part, 120)]
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


def _guide_href(course_id: str, intent: str) -> str:
    params = {"new": "1"}
    if course_id:
        params["course_id"] = course_id
    if intent:
        params["effect_action"] = intent
    return "/guide?" + urlencode(params)


def _chat_href(
    prompt: str,
    capability: str = "chat",
    knowledge_bases: list[str] | None = None,
) -> str:
    params: list[tuple[str, str]] = [("new", "1"), ("prompt", prompt)]
    if capability:
        params.append(("capability", capability))
    for kb_name in knowledge_bases or []:
        clean_name = _clean(kb_name, 120)
        if clean_name:
            params.append(("kb", clean_name))
    return "/chat?" + urlencode(params)


def _attach_action_execution_payload(
    action: NextBestAction,
    *,
    course_id: str,
    knowledge_context: dict[str, Any] | None = None,
) -> NextBestAction:
    """Attach a directly executable capability payload to a next-best action."""

    topic = _action_topic(action)
    action_type = _clean(action.type, 80)
    if action_type == "diagnostic":
        action.capability = "deep_question"
        action.prompt = (
            f"请围绕「{topic}」生成 5 道诊断题，题型混合选择题、判断题和简答题。"
            "每题都要标注考察概念、答案、解析，并在结尾给出需要补基的判断。"
        )
        action.config = {
            "mode": "custom",
            "topic": topic,
            "num_questions": 5,
            "difficulty": "auto",
            "question_type": "mixed",
            "purpose": "diagnostic",
        }
        _attach_knowledge_to_action(action, knowledge_context=knowledge_context)
        action.href = _chat_href(action.prompt, action.capability, action.knowledge_bases)
        return action
    if action_type == "generate_visual":
        action.capability = "visualize"
        action.prompt = (
            f"请为「{topic}」生成一张面向初学者的学习图解。"
            "重点画出概念关系、关键步骤、常见混淆点，并用一句话说明怎么读图。"
        )
        action.config = {"render_mode": "auto", "topic": topic, "purpose": "remediation_visual"}
        _attach_knowledge_to_action(action, knowledge_context=knowledge_context)
        action.href = _chat_href(action.prompt, action.capability, action.knowledge_bases)
        return action
    if action_type in {"generate_practice", "retest", "mistake_review"}:
        purpose = {
            "generate_practice": "practice",
            "retest": "retest",
            "mistake_review": "mistake_review",
        }.get(action_type, "practice")
        action.capability = "deep_question"
        action.prompt = (
            f"请围绕「{topic}」生成一组 3 到 5 道交互式练习。"
            "包含选择题、判断题、填空题或简答题，难度循序渐进；每题给答案、解析、考察概念和错因提示。"
        )
        action.config = {
            "mode": "custom",
            "topic": topic,
            "num_questions": 5 if action_type != "retest" else 3,
            "difficulty": "auto",
            "question_type": "mixed",
            "purpose": purpose,
        }
        _attach_knowledge_to_action(action, knowledge_context=knowledge_context)
        action.href = _chat_href(action.prompt, action.capability, action.knowledge_bases)
        return action
    if action_type in {"generate_resource", "advance"}:
        action.capability = "chat"
        action.prompt = (
            f"请根据我的学习画像，为「{topic}」安排一个最小可执行的下一步学习任务。"
            "请只给一个任务，包含目标、10 分钟步骤、产出物和完成后的自测方式。"
        )
        action.config = {"purpose": action_type, "topic": topic}
        _attach_knowledge_to_action(action, knowledge_context=knowledge_context)
        action.href = _chat_href(action.prompt, action.capability, action.knowledge_bases)
        return action
    action.capability = action.capability or "chat"
    action.prompt = action.prompt or f"请根据我的学习画像，围绕「{topic}」安排下一步学习。"
    action.config = action.config or {"purpose": action_type or "next_action", "topic": topic}
    _attach_knowledge_to_action(action, knowledge_context=knowledge_context)
    action.href = action.href or _chat_href(action.prompt, action.capability, action.knowledge_bases)
    return action


def _attach_knowledge_to_action(
    action: NextBestAction,
    *,
    knowledge_context: dict[str, Any] | None,
) -> None:
    if not _knowledge_context_can_ground(knowledge_context):
        return
    kb_name = _clean((knowledge_context or {}).get("kb_name"), 120)
    if not kb_name:
        return
    action.knowledge_bases = list(dict.fromkeys([*action.knowledge_bases, kb_name]))
    if action.capability in {"chat", "deep_solve", "deep_question", "deep_research"}:
        action.config.setdefault("retrieval_profile", "auto")
        action.config.setdefault("agentic_rag", "auto")
        action.config.setdefault("query_transform", "hyde")
        instruction = _knowledge_action_instruction(knowledge_context)
        if instruction and instruction not in action.prompt:
            action.prompt = f"{action.prompt}{instruction}"


def _action_topic(action: NextBestAction) -> str:
    concepts = [_clean(item, 80) for item in action.target_concepts if _clean(item, 80)]
    if concepts:
        return "、".join(concepts[:3])
    title = _clean(action.title, 80)
    return title or "当前学习目标"


def _clean(value: Any, limit: int = 200) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _safe_id(value: Any) -> str:
    text = _clean(value, 160).lower()
    text = re.sub(r"[^\w\u4e00-\u9fff]+", "_", text, flags=re.UNICODE).strip("_")
    return text or "item"


def _as_float(value: Any, default: float | None = 0.0) -> float | None:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except Exception:
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


_learning_effect_service: LearningEffectService | None = None


def get_learning_effect_service() -> LearningEffectService:
    global _learning_effect_service
    if _learning_effect_service is None:
        _learning_effect_service = LearningEffectService()
    return _learning_effect_service


def create_learning_effect_service(**kwargs: Any) -> LearningEffectService:
    return LearningEffectService(**kwargs)


__all__ = [
    "ConceptMasteryState",
    "LearningEffectService",
    "NextBestAction",
    "create_learning_effect_service",
    "get_learning_effect_service",
]
