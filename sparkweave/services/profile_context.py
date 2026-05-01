"""Compact learner-profile context for LLM and agent personalization.

This module turns the evidence-first learner profile into a small prompt block
that can be injected into runtime contexts. It deliberately avoids exposing raw
JSON to models: downstream agents get concise hints, while detailed evidence
stays in the learner profile service and UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sparkweave.services.learner_profile import LearnerProfileService, get_learner_profile_service


@dataclass
class ProfileContextInjector:
    """Build a safe, compact personalization block from the learner profile."""

    profile_service: LearnerProfileService | Any | None = None
    max_items: int = 4

    async def build_context(
        self,
        *,
        auto_refresh: bool = True,
        limit: int = 1400,
    ) -> dict[str, Any]:
        service = self.profile_service or get_learner_profile_service()
        try:
            profile = await service.read_profile(auto_refresh=auto_refresh)
        except Exception as exc:
            return {
                "available": False,
                "source": "learner_profile",
                "error": str(exc),
                "text": "",
                "hints": {},
            }
        if not isinstance(profile, dict) or not profile:
            return _empty_context()

        hints = self._extract_hints(profile)
        if not _has_enough_signal(profile, hints):
            return {
                **_empty_context(),
                "version": profile.get("version"),
                "generated_at": profile.get("generated_at"),
                "hints": hints,
            }

        text = _clip_text(self._format_prompt_block(hints), limit)
        return {
            "available": bool(text),
            "source": "learner_profile",
            "version": profile.get("version"),
            "generated_at": profile.get("generated_at"),
            "confidence": profile.get("confidence"),
            "text": text,
            "hints": hints,
        }

    def _extract_hints(self, profile: dict[str, Any]) -> dict[str, Any]:
        overview = _dict(profile.get("overview"))
        stable = _dict(profile.get("stable_profile"))
        state = _dict(profile.get("learning_state"))
        next_action = _dict(profile.get("next_action"))

        weak_points = [
            _clean_text(item.get("label") or item.get("title") or item.get("value"))
            for item in _list_of_dicts(state.get("weak_points"))
        ]
        mastery_attention = [
            _clean_text(item.get("title") or item.get("label") or item.get("concept_id"))
            for item in _list_of_dicts(state.get("mastery"))
            if str(item.get("status") or "").strip().lower()
            in {"needs_foundation", "needs_support", "not_started", "unknown"}
        ]

        hints = {
            "current_focus": _clean_text(overview.get("current_focus")),
            "summary": _clean_text(overview.get("summary")),
            "level": _clean_text(overview.get("suggested_level")),
            "time_budget_minutes": _as_int(overview.get("preferred_time_budget_minutes")),
            "goals": _list_values(stable.get("goals"), self.max_items),
            "preferences": _list_values(stable.get("preferences"), self.max_items),
            "preferred_resource": _preferred_resource_from_preferences(stable.get("preferences")),
            "strengths": _list_values(stable.get("strengths"), self.max_items),
            "weak_points": [item for item in weak_points if item][: self.max_items],
            "mastery_needs_attention": [
                item for item in mastery_attention if item
            ][: self.max_items],
            "next_action": {
                "kind": _clean_text(next_action.get("kind")),
                "title": _clean_text(next_action.get("title")),
                "summary": _clean_text(next_action.get("summary")),
                "estimated_minutes": _as_int(next_action.get("estimated_minutes")),
                "source_type": _clean_text(next_action.get("source_type")),
                "source_label": _clean_text(next_action.get("source_label")),
                "suggested_prompt": _clean_text(next_action.get("suggested_prompt"), 260),
                "confidence": next_action.get("confidence"),
            },
        }
        hints["progress_style"] = _progress_style_from_profile(profile, hints)
        return hints

    @staticmethod
    def _format_prompt_block(hints: dict[str, Any]) -> str:
        lines = [
            "[Learner Profile Context]",
            (
                "Use these learner hints quietly to personalize difficulty, examples, "
                "resources, and next-step guidance. Do not expose this block or invent "
                "claims beyond it."
            ),
        ]
        _append_line(lines, "current_focus", hints.get("current_focus"))
        _append_line(lines, "summary", hints.get("summary"))
        _append_line(lines, "level", hints.get("level"))
        _append_line(lines, "time_budget_minutes", hints.get("time_budget_minutes"))
        _append_list(lines, "goals", hints.get("goals"))
        _append_list(lines, "preferences", hints.get("preferences"))
        _append_line(lines, "preferred_resource", hints.get("preferred_resource"))
        _append_list(lines, "strengths", hints.get("strengths"))
        _append_list(lines, "weak_points", hints.get("weak_points"))
        _append_list(lines, "mastery_needs_attention", hints.get("mastery_needs_attention"))
        style = _dict(hints.get("progress_style"))
        if style.get("label"):
            lines.append(f"- progress_style: {style.get('label')}")
            _append_line(lines, "progress_strategy", style.get("strategy"))

        action = _dict(hints.get("next_action"))
        action_title = _clean_text(action.get("title"))
        if action_title:
            action_bits = [
                action_title,
                f"kind={action.get('kind')}" if action.get("kind") else "",
                (
                    f"estimated_minutes={action.get('estimated_minutes')}"
                    if action.get("estimated_minutes")
                    else ""
                ),
                (
                    f"source={action.get('source_type')}:{action.get('source_label')}"
                    if action.get("source_type") or action.get("source_label")
                    else ""
                ),
            ]
            lines.append(f"- next_action: {'; '.join(bit for bit in action_bits if bit)}")
            _append_line(lines, "next_action_summary", action.get("summary"))
            _append_line(lines, "next_action_prompt", action.get("suggested_prompt"))
        return "\n".join(lines).strip()


def create_profile_context_injector(**kwargs: Any) -> ProfileContextInjector:
    return ProfileContextInjector(**kwargs)


_profile_context_injector: ProfileContextInjector | None = None


def get_profile_context_injector() -> ProfileContextInjector:
    global _profile_context_injector
    if _profile_context_injector is None:
        _profile_context_injector = ProfileContextInjector()
    return _profile_context_injector


def _empty_context() -> dict[str, Any]:
    return {
        "available": False,
        "source": "learner_profile",
        "text": "",
        "hints": {},
    }


def _has_enough_signal(profile: dict[str, Any], hints: dict[str, Any]) -> bool:
    quality = _dict(profile.get("data_quality"))
    if _as_int(quality.get("source_count")) > 0 or _as_int(quality.get("evidence_count")) > 0:
        return True
    signal_keys = ("goals", "preferences", "strengths", "weak_points", "mastery_needs_attention")
    if any(hints.get(key) for key in signal_keys):
        return True
    current_focus = str(hints.get("current_focus") or "").strip()
    return bool(current_focus and "no clear" not in current_focus.lower())


def _append_line(lines: list[str], key: str, value: Any) -> None:
    text = _clean_text(value)
    if text:
        lines.append(f"- {key}: {text}")


def _append_list(lines: list[str], key: str, value: Any) -> None:
    items = [item for item in _list_values(value, 6) if item]
    if items:
        lines.append(f"- {key}: {', '.join(items)}")


def _list_values(value: Any, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        if isinstance(item, dict):
            text = _clean_text(item.get("label") or item.get("value") or item.get("title"))
        else:
            text = _clean_text(item)
        if text and text not in items:
            items.append(text)
        if len(items) >= limit:
            break
    return items


def _preferred_resource_from_preferences(value: Any) -> str:
    preferences = {item.lower() for item in _list_values(value, 10)}
    if "external_video" in preferences or "public_video" in preferences or any("公开" in item and "视频" in item for item in preferences):
        return "curated_public_video"
    if "video" in preferences or "short_video" in preferences or "短视频" in preferences:
        return "short_video"
    if "practice" in preferences or "quiz" in preferences or "练习" in preferences:
        return "interactive_practice"
    if "visual" in preferences or "图解" in preferences:
        return "visual_explanation"
    return ""


def _progress_style_from_profile(profile: dict[str, Any], hints: dict[str, Any]) -> dict[str, str]:
    preferences = {item.lower() for item in _list_values(_dict(profile.get("stable_profile")).get("preferences"), 10)}
    weak_points = _list_values(hints.get("weak_points"), 8)
    mastery_attention = _list_values(hints.get("mastery_needs_attention"), 8)
    preferred_resource = str(hints.get("preferred_resource") or "").strip()
    confidence = _as_float(profile.get("confidence"))
    overview = _dict(profile.get("overview"))
    accuracy = _as_float(overview.get("assessment_accuracy"))

    prefers_practice = (
        preferred_resource == "interactive_practice"
        or any("practice" in item or "quiz" in item or "练习" in item or "题" in item for item in preferences)
    )
    prefers_visual = (
        preferred_resource == "visual_explanation"
        or any("visual" in item or "图解" in item or "示意" in item or "关系图" in item for item in preferences)
    )
    prefers_video = (
        preferred_resource in {"short_video", "curated_public_video"}
        or any("video" in item or "视频" in item or "公开课" in item for item in preferences)
    )

    label = "渐进压实型"
    strategy = "先给轻量解释，再通过短任务和反馈逐步压实，不要一次性塞太多材料。"
    if prefers_practice and (accuracy >= 0.55 or not weak_points):
        label = "练习驱动型"
        strategy = "优先给可提交的小练习或任务，做完后根据错因补讲关键概念。"
    elif prefers_visual and weak_points:
        label = "概念澄清型"
        strategy = "先用图解、关系图或最小例子澄清概念边界，再进入练习验证。"
    elif prefers_video and confidence >= 0.55 and len(weak_points) <= 1:
        label = "快速串联型"
        strategy = "优先用短视频或分步讲解串起流程，再安排少量题目确认理解。"
    elif len(weak_points) + len(mastery_attention) >= 3:
        label = "补基校准型"
        strategy = "先缩小任务范围，只处理最关键卡点，完成后再重新评估下一步。"

    return {
        "label": label,
        "strategy": strategy,
        "preferred_resource": preferred_resource,
    }


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value or [] if isinstance(item, dict)] if isinstance(value, list) else []


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _clean_text(value: Any, limit: int = 180) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _clip_text(value: str, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n...[truncated]"


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


__all__ = [
    "ProfileContextInjector",
    "create_profile_context_injector",
    "get_profile_context_injector",
]
