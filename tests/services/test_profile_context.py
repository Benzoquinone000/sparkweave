from __future__ import annotations

import pytest

from sparkweave.services.profile_context import ProfileContextInjector


class FakeProfileService:
    def __init__(self, profile: dict | None = None, error: Exception | None = None) -> None:
        self.profile = profile or {}
        self.error = error
        self.calls: list[dict] = []

    async def read_profile(self, *, auto_refresh: bool = True) -> dict:
        self.calls.append({"auto_refresh": auto_refresh})
        if self.error is not None:
            raise self.error
        return self.profile


@pytest.mark.asyncio
async def test_profile_context_injector_builds_compact_prompt_block() -> None:
    service = FakeProfileService(
        {
            "version": 1,
            "generated_at": "2026-04-27T10:00:00Z",
            "confidence": 0.82,
            "overview": {
                "current_focus": "梯度下降",
                "suggested_level": "beginner",
                "preferred_time_budget_minutes": 20,
                "summary": "正在补齐梯度下降的直观理解。",
            },
            "stable_profile": {
                "goals": ["机器学习入门"],
                "preferences": ["visual", "practice"],
                "strengths": ["愿意做反思"],
            },
            "learning_state": {
                "weak_points": [
                    {"label": "概念边界不清", "confidence": 0.74},
                    {"label": "公式含义不稳", "confidence": 0.68},
                ],
                "mastery": [
                    {"title": "梯度方向", "status": "needs_support"},
                    {"title": "线性代数", "status": "mastered"},
                ],
            },
            "next_action": {
                "kind": "remediate",
                "title": "前测补基：梯度下降的直观理解",
                "summary": "先看图解，再做三道小题。",
                "estimated_minutes": 10,
                "source_type": "weak_point",
                "source_label": "概念边界不清",
                "confidence": 0.76,
            },
            "data_quality": {"source_count": 3, "evidence_count": 9},
        }
    )

    payload = await ProfileContextInjector(profile_service=service).build_context()

    assert payload["available"] is True
    assert payload["source"] == "learner_profile"
    assert payload["hints"]["current_focus"] == "梯度下降"
    assert payload["hints"]["weak_points"] == ["概念边界不清", "公式含义不稳"]
    assert payload["hints"]["mastery_needs_attention"] == ["梯度方向"]
    assert "[Learner Profile Context]" in payload["text"]
    assert "raw" not in payload["text"].lower()
    assert "梯度下降" in payload["text"]
    assert service.calls == [{"auto_refresh": True}]


@pytest.mark.asyncio
async def test_profile_context_injector_stays_empty_without_evidence() -> None:
    payload = await ProfileContextInjector(
        profile_service=FakeProfileService(
            {
                "overview": {"current_focus": ""},
                "stable_profile": {},
                "learning_state": {},
                "data_quality": {"source_count": 0, "evidence_count": 0},
            }
        )
    ).build_context()

    assert payload["available"] is False
    assert payload["text"] == ""


@pytest.mark.asyncio
async def test_profile_context_injector_fails_closed() -> None:
    payload = await ProfileContextInjector(
        profile_service=FakeProfileService(error=RuntimeError("profile store unavailable"))
    ).build_context()

    assert payload["available"] is False
    assert payload["text"] == ""
    assert "profile store unavailable" in payload["error"]
