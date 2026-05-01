from __future__ import annotations

import pytest

from sparkweave.services.learner_evidence import (
    LearnerEvidenceService,
    build_chat_statement_events,
    build_profile_calibration_event,
    build_quiz_answer_events,
)
from sparkweave.services.learner_profile import LearnerProfileService


class _Memory:
    def read_snapshot(self):
        return type(
            "Snapshot",
            (),
            {
                "summary": "## Current Focus\n- 正在学习梯度下降，需要图解和练习。\n## Open Questions\n- 卡点：学习率判断错误",
                "profile": "## Learning Style\n- 偏好图解和分步骤解释。",
                "summary_updated_at": "2026-04-27T10:00:00+08:00",
                "profile_updated_at": "2026-04-27T10:00:00+08:00",
            },
        )()


class _Guide:
    def build_learner_memory(self, *, refresh: bool = True):
        return {
            "success": True,
            "session_count": 1,
            "evidence_count": 2,
            "confidence": 0.7,
            "suggested_level": "beginner",
            "preferred_time_budget_minutes": 20,
            "top_preferences": [{"label": "visual", "count": 2}],
            "persistent_weak_points": [{"label": "公式推导", "count": 2}],
            "common_mistakes": [{"label": "学习率判断错误", "count": 1}],
            "strengths": [{"label": "直观理解", "count": 1}],
            "recent_goals": [{"goal": "掌握梯度下降", "updated_at": 1}],
            "next_guidance": ["先补齐公式推导，再做入门练习。"],
            "last_activity_at": 1_777_000_000,
        }

    def list_sessions(self):
        return [{"session_id": "g1", "goal": "梯度下降前测补基", "updated_at": 1_777_000_000}]

    def get_session(self, session_id: str):
        assert session_id == "g1"
        return {
            "session_id": "g1",
            "goal": "梯度下降前测补基",
            "profile": {
                "goal": "梯度下降前测补基",
                "level": "beginner",
                "time_budget_minutes": 20,
                "preferences": ["practice"],
                "weak_points": ["概念边界不清"],
            },
            "course_map": {"nodes": [{"node_id": "n1", "title": "梯度下降直观理解"}]},
            "mastery": {
                "n1": {
                    "score": 0.42,
                    "status": "needs_support",
                    "evidence_count": 1,
                    "last_updated": 1_777_000_000,
                }
            },
            "evidence": [
                {
                    "evidence_id": "e1",
                    "task_id": "t1",
                    "score": 0.42,
                    "reflection": "学习率和梯度方向还不稳。",
                    "mistake_types": ["学习率判断错误"],
                    "created_at": 1_777_000_000,
                }
            ],
        }


class _Store:
    async def list_notebook_entries(self, limit: int = 200, offset: int = 0):
        return {
            "items": [
                {
                    "id": 1,
                    "question": "学习率过大可能发生什么？",
                    "question_type": "choice",
                    "difficulty": "easy",
                    "user_answer": "更稳定",
                    "correct_answer": "震荡",
                    "explanation": "学习率过大会越过最优点。",
                    "is_correct": False,
                    "categories": [{"id": 1, "name": "梯度下降"}],
                    "created_at": 1_777_000_000,
                    "updated_at": 1_777_000_000,
                },
                {
                    "id": 2,
                    "question": "梯度方向表示最快上升方向。",
                    "question_type": "true_false",
                    "difficulty": "easy",
                    "is_correct": True,
                    "categories": [{"id": 1, "name": "梯度下降"}],
                    "created_at": 1_777_000_100,
                    "updated_at": 1_777_000_100,
                },
            ],
            "total": 2,
        }


class _Notebook:
    def list_notebooks(self):
        return [{"id": "nb1", "name": "机器学习笔记", "updated_at": 1_777_000_200, "record_count": 1}]

    def get_notebook(self, notebook_id: str):
        return {
            "id": notebook_id,
            "records": [
                {
                    "id": "r1",
                    "title": "梯度下降复盘",
                    "summary": "记录了学习率、梯度方向和损失曲线。",
                    "type": "reflection",
                    "created_at": 1_777_000_200,
                }
            ],
        }


@pytest.mark.asyncio
async def test_learner_profile_aggregates_existing_evidence(tmp_path) -> None:
    service = LearnerProfileService(
        memory_service=_Memory(),
        guide_manager=_Guide(),
        session_store=_Store(),
        notebook_manager=_Notebook(),
        evidence_service=LearnerEvidenceService(output_dir=tmp_path / "evidence"),
        output_dir=tmp_path,
    )

    profile = await service.refresh()

    assert profile["version"] == 1
    assert profile["overview"]["suggested_level"] == "beginner"
    assert profile["overview"]["preferred_time_budget_minutes"] == 20
    assert "梯度下降" in profile["overview"]["current_focus"]
    assert any(item == "visual" for item in profile["stable_profile"]["preferences"])
    assert any(item["label"] == "公式推导" for item in profile["learning_state"]["weak_points"])
    assert any(item["title"] == "梯度下降直观理解" for item in profile["learning_state"]["mastery"])
    assert profile["next_action"]["kind"] == "remediate"
    weak_labels = {item["label"] for item in profile["learning_state"]["weak_points"]}
    assert profile["next_action"]["source_label"] in weak_labels
    assert profile["next_action"]["href"] == "/guide"
    assert "补基任务" in profile["next_action"]["suggested_prompt"]
    assert profile["data_quality"]["source_count"] >= 4
    assert profile["data_quality"]["evidence_count"] >= 4
    assert (tmp_path / "profile.json").exists()


@pytest.mark.asyncio
async def test_learner_profile_evidence_preview_filters_source(tmp_path) -> None:
    service = LearnerProfileService(
        memory_service=_Memory(),
        guide_manager=_Guide(),
        session_store=_Store(),
        notebook_manager=_Notebook(),
        evidence_service=LearnerEvidenceService(output_dir=tmp_path / "evidence"),
        output_dir=tmp_path,
    )
    await service.refresh()

    preview = await service.list_evidence_preview(source="question_notebook", limit=5)

    assert preview["total"] == 2
    assert all(item["source_id"] == "question_notebook" for item in preview["items"])


@pytest.mark.asyncio
async def test_learner_profile_reads_formal_evidence_ledger(tmp_path) -> None:
    evidence = LearnerEvidenceService(output_dir=tmp_path / "evidence")
    evidence.append_event(
        {
            "source": "guide",
            "verb": "answered",
            "object_type": "quiz",
            "object_id": "learning-rate",
            "title": "学习率判断",
            "score": 0.2,
            "is_correct": False,
            "mistake_types": ["学习率判断错误"],
            "created_at": 1_777_000_000,
        }
    )
    evidence.append_event(
        {
            "source": "resource",
            "verb": "viewed",
            "object_type": "resource",
            "object_id": "https://example.com/video",
            "title": "Gradient descent video",
            "summary": "Learner opened a curated public video.",
            "resource_type": "external_video",
            "created_at": 1_777_000_100,
        }
    )
    service = LearnerProfileService(
        memory_service=_Memory(),
        guide_manager=_Guide(),
        session_store=_Store(),
        notebook_manager=_Notebook(),
        evidence_service=evidence,
        output_dir=tmp_path,
    )

    profile = await service.refresh(include_sources=["evidence"])

    assert any(source["source_id"] == "evidence" for source in profile["sources"])
    assert any(item["label"] == "学习率判断错误" for item in profile["learning_state"]["weak_points"])
    assert any(item["concept_id"] == "learning-rate" for item in profile["learning_state"]["mastery"])
    assert "external_video" in profile["stable_profile"]["preferences"]
    assert any(item["metadata"].get("resource_type") == "external_video" for item in profile["evidence_preview"])


@pytest.mark.asyncio
async def test_learner_profile_does_not_treat_generated_resource_as_preference(tmp_path) -> None:
    evidence = LearnerEvidenceService(output_dir=tmp_path / "evidence")
    evidence.append_event(
        {
            "source": "guide_v2",
            "verb": "generated",
            "object_type": "resource",
            "object_id": "artifact-video",
            "title": "Generated public video recommendations",
            "summary": "The system generated video cards, but the learner has not opened them yet.",
            "resource_type": "external_video",
            "created_at": 1_777_000_000,
        }
    )
    service = LearnerProfileService(
        memory_service=_Memory(),
        guide_manager=_Guide(),
        session_store=_Store(),
        notebook_manager=_Notebook(),
        evidence_service=evidence,
        output_dir=tmp_path,
    )

    profile = await service.refresh(include_sources=["evidence"])

    assert "external_video" not in profile["stable_profile"]["preferences"]
    assert any(item["metadata"].get("resource_type") == "external_video" for item in profile["evidence_preview"])


@pytest.mark.asyncio
async def test_learner_profile_groups_quiz_evidence_by_concept(tmp_path) -> None:
    evidence = LearnerEvidenceService(output_dir=tmp_path / "evidence")
    evidence.append_events(
        build_quiz_answer_events(
            [
                {
                    "question_id": "q1",
                    "question": "What does a large learning rate risk?",
                    "question_type": "choice",
                    "is_correct": False,
                    "concepts": ["gradient descent", "learning rate"],
                },
                {
                    "question_id": "q2",
                    "question": "Gradient descent moves against the gradient.",
                    "question_type": "true_false",
                    "is_correct": True,
                    "concepts": ["gradient descent"],
                },
            ],
            source="guide_v2",
            session_id="session_1",
            task_id="task_1",
            artifact_id="quiz_1",
        )
    )
    service = LearnerProfileService(
        memory_service=_Memory(),
        guide_manager=_Guide(),
        session_store=_Store(),
        notebook_manager=_Notebook(),
        evidence_service=evidence,
        output_dir=tmp_path,
    )

    profile = await service.refresh(include_sources=["evidence"])
    mastery = next(
        item for item in profile["learning_state"]["mastery"]
        if item["concept_id"] == "gradient-descent"
    )

    assert mastery["title"] == "gradient descent"
    assert mastery["evidence_count"] == 2
    assert mastery["score"] == 0.5
    assert any(item["label"] == "gradient descent" for item in profile["learning_state"]["weak_points"])


@pytest.mark.asyncio
async def test_learner_profile_applies_user_calibration(tmp_path) -> None:
    evidence = LearnerEvidenceService(output_dir=tmp_path / "evidence")
    evidence.append_event(
        {
            "source": "guide",
            "verb": "answered",
            "object_type": "quiz",
            "object_id": "linear-algebra",
            "title": "linear algebra",
            "score": 0.2,
            "is_correct": False,
            "created_at": 1_777_000_000,
        }
    )
    evidence.append_event(
        build_profile_calibration_event(
            action="reject",
            claim_type="weak_point",
            value="linear algebra",
            note="This is not my current issue.",
        )
    )
    evidence.append_event(
        build_profile_calibration_event(
            action="correct",
            claim_type="preference",
            value="quiz",
            corrected_value="short video",
        )
    )
    service = LearnerProfileService(
        memory_service=_Memory(),
        guide_manager=_Guide(),
        session_store=_Store(),
        notebook_manager=_Notebook(),
        evidence_service=evidence,
        output_dir=tmp_path,
    )

    profile = await service.refresh(include_sources=["evidence"])

    assert not any(item["label"] == "linear algebra" for item in profile["learning_state"]["weak_points"])
    assert "short video" in profile["stable_profile"]["preferences"]
    assert profile["data_quality"]["calibration_count"] == 2
    assert profile["data_quality"]["read_only"] is False


@pytest.mark.asyncio
async def test_learner_profile_applies_overview_correction(tmp_path) -> None:
    evidence = LearnerEvidenceService(output_dir=tmp_path / "evidence")
    correction = "我不是基础差，我主要卡在公式含义和应用场景。"
    evidence.append_event(
        build_profile_calibration_event(
            action="correct",
            claim_type="profile_overview",
            value="系统认为我基础薄弱。",
            corrected_value=correction,
        )
    )
    service = LearnerProfileService(
        memory_service=_Memory(),
        guide_manager=_Guide(),
        session_store=_Store(),
        notebook_manager=_Notebook(),
        evidence_service=evidence,
        output_dir=tmp_path,
    )

    profile = await service.refresh(include_sources=["evidence"])

    assert profile["overview"]["summary"] == correction
    assert profile["overview"]["current_focus"] == correction
    assert profile["data_quality"]["calibration_count"] == 1


@pytest.mark.asyncio
async def test_learner_profile_uses_chat_statement_events(tmp_path) -> None:
    evidence = LearnerEvidenceService(output_dir=tmp_path / "evidence")
    evidence.append_events(
        build_chat_statement_events(
            "I want to master gradient descent, but I am confused by the formula. I prefer visual videos.",
            session_id="chat_1",
            turn_id="turn_1",
            capability="chat",
            language="en",
        )
    )
    service = LearnerProfileService(
        memory_service=_Memory(),
        guide_manager=_Guide(),
        session_store=_Store(),
        notebook_manager=_Notebook(),
        evidence_service=evidence,
        output_dir=tmp_path,
    )

    profile = await service.refresh(include_sources=["evidence"])

    assert any("gradient descent" in item for item in profile["stable_profile"]["goals"])
    assert any("confused" in item["label"] for item in profile["learning_state"]["weak_points"])
    assert "visual" in profile["stable_profile"]["preferences"]
    assert "video" in profile["stable_profile"]["preferences"]
