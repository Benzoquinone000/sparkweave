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
                "confidence": next_action.get("confidence"),
            },
        }
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
        _append_list(lines, "strengths", hints.get("strengths"))
        _append_list(lines, "weak_points", hints.get("weak_points"))
        _append_list(lines, "mastery_needs_attention", hints.get("mastery_needs_attention"))

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


__all__ = [
    "ProfileContextInjector",
    "create_profile_context_injector",
    "get_profile_context_injector",
]
