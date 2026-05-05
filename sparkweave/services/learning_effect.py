"""Learning effect closed-loop aggregation.

This service turns the existing learner evidence ledger into a global learning
effect report. It intentionally starts with transparent rules so the product can
explain every recommendation before we upgrade parts of it to BKT/IRT later.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import re
import time
from typing import Any
from urllib.parse import urlencode
import uuid

from sparkweave.services.learner_evidence import (
    LearnerEvidenceService,
    get_learner_evidence_service,
)


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
    writes_back: list[str] = field(default_factory=lambda: ["mastery", "profile"])


class LearningEffectService:
    """Build reports, concept states, and interventions from learner evidence."""

    def __init__(self, *, evidence_service: LearnerEvidenceService | None = None) -> None:
        self._evidence_service = evidence_service or get_learner_evidence_service()

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
        actions = self._build_next_actions(concepts, summary, course_id=course_id)
        remediation_loop = self._remediation_loop(events)
        dimensions = self._dimensions(events=events, concepts=concepts, summary=summary)
        overall_score = _weighted_score(
            dimensions,
            {
                "mastery": 0.27,
                "progress": 0.14,
                "stability": 0.16,
                "evidence_quality": 0.17,
                "engagement": 0.12,
                "remediation": 0.09,
                "resource_effectiveness": 0.05,
            },
        )
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
        actions = self._build_next_actions(concepts, summary, course_id=course_id)
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
                _attach_action_execution_payload(action, course_id=course_id)
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
            _attach_action_execution_payload(action, course_id=course_id)
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


def _chat_href(prompt: str, capability: str = "chat") -> str:
    params = {"new": "1", "prompt": prompt}
    if capability:
        params["capability"] = capability
    return "/chat?" + urlencode(params)


def _attach_action_execution_payload(action: NextBestAction, *, course_id: str) -> NextBestAction:
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
        action.href = _chat_href(action.prompt, action.capability)
        return action
    if action_type == "generate_visual":
        action.capability = "visualize"
        action.prompt = (
            f"请为「{topic}」生成一张面向初学者的学习图解。"
            "重点画出概念关系、关键步骤、常见混淆点，并用一句话说明怎么读图。"
        )
        action.config = {"render_mode": "auto", "topic": topic, "purpose": "remediation_visual"}
        action.href = _chat_href(action.prompt, action.capability)
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
        action.href = _chat_href(action.prompt, action.capability)
        return action
    if action_type in {"generate_resource", "advance"}:
        action.capability = "chat"
        action.prompt = (
            f"请根据我的学习画像，为「{topic}」安排一个最小可执行的下一步学习任务。"
            "请只给一个任务，包含目标、10 分钟步骤、产出物和完成后的自测方式。"
        )
        action.config = {"purpose": action_type, "topic": topic}
        action.href = _chat_href(action.prompt, action.capability)
        return action
    action.capability = action.capability or "chat"
    action.prompt = action.prompt or f"请根据我的学习画像，围绕「{topic}」安排下一步学习。"
    action.config = action.config or {"purpose": action_type or "next_action", "topic": topic}
    action.href = action.href or _chat_href(action.prompt, action.capability)
    return action


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
