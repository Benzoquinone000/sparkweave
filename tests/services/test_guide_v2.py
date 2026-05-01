from __future__ import annotations

import json
from typing import Any

import pytest

from sparkweave.services.guide_v2 import GuideV2CreateInput, GuideV2Manager


class _UnifiedProfileService:
    def __init__(self, profile: dict[str, Any]) -> None:
        self.profile = profile
        self.calls: list[bool] = []

    async def read_profile(self, *, auto_refresh: bool = True) -> dict[str, Any]:
        self.calls.append(auto_refresh)
        return self.profile


@pytest.mark.asyncio
async def test_guide_v2_creates_structured_session_with_fallback(tmp_path) -> None:
    async def _failing_completion(**_kwargs):
        raise RuntimeError("llm unavailable")

    manager = GuideV2Manager(output_dir=tmp_path, completion_fn=_failing_completion)

    result = await manager.create_session(
        GuideV2CreateInput(
            goal="用 30 分钟学习梯度下降，需要图解和练习",
            preferences=["visual", "practice"],
            source_action={
                "source": "learner_profile",
                "kind": "remediate",
                "source_label": "学习率判断错误",
                "suggested_prompt": "围绕学习率判断错误安排补基任务。",
                "confidence": 0.76,
                "estimated_minutes": 15,
            },
        )
    )

    assert result["success"] is True
    session = result["session"]
    assert session["profile"]["level"] in {"beginner", "intermediate", "advanced"}
    assert session["course_map"]["nodes"]
    assert session["learning_path"]["current_task_id"] == session["tasks"][0]["task_id"]
    assert session["current_task"]["task_id"] == session["tasks"][0]["task_id"]
    assert "Build understanding" not in session["current_task"]["title"]
    assert session["learning_path"]["title"].endswith("导学路线")
    assert session["course_map"]["metadata"]["created_from"] == "learner_profile"
    assert session["course_map"]["metadata"]["source_action"]["source_label"] == "学习率判断错误"
    assert session["tasks"][0]["metadata"]["source_action"]["kind"] == "remediate"
    assert session["recommendations"][0].startswith("已根据学习画像建议")
    assert any("先完成" in item for item in session["recommendations"])
    assert session["progress"] == 0

    stored = next(tmp_path.glob("session_*.json"))
    payload = json.loads(stored.read_text(encoding="utf-8"))
    assert payload["session_id"] == session["session_id"]


@pytest.mark.asyncio
async def test_guide_v2_builds_cross_session_learner_memory(tmp_path) -> None:
    async def _failing_completion(**_kwargs):
        raise RuntimeError("llm unavailable")

    manager = GuideV2Manager(output_dir=tmp_path, completion_fn=_failing_completion)
    first = await manager.create_session(
        GuideV2CreateInput(
            goal="学习梯度下降",
            preferences=["visual", "practice"],
            weak_points=["公式推导"],
        )
    )
    first_session_id = first["session"]["session_id"]
    first_task = first["session"]["tasks"][0]

    manager.complete_task(
        first_session_id,
        first_task["task_id"],
        score=0.42,
        reflection="公式推导和学习率关系还不清楚。",
        mistake_types=["学习率判断错误"],
    )

    memory = manager.build_learner_memory()

    assert memory["session_count"] == 1
    assert memory["evidence_count"] == 1
    assert memory["average_score"] == 0.42
    assert any(item["label"] == "visual" for item in memory["top_preferences"])
    assert any(item["label"] == "公式推导" for item in memory["persistent_weak_points"])
    assert any(item["label"] == "学习率判断错误" for item in memory["common_mistakes"])
    assert memory["next_guidance"]
    assert (tmp_path / "learner_memory.json").exists()

    inherited = await manager.create_session(GuideV2CreateInput(goal="学习反向传播"))
    inherited_profile = inherited["session"]["profile"]

    assert "visual" in inherited_profile["preferences"]
    assert "公式推导" in inherited_profile["weak_points"]
    assert "学习率判断错误" in inherited_profile["weak_points"]
    assert "已沉淀" in inherited_profile["source_context_summary"]
    assert inherited["session"]["current_task"]["origin"] == "learner_memory"
    assert inherited["session"]["tasks"][0]["type"] == "memory_warmup"
    assert inherited["session"]["tasks"][0]["metadata"]["learner_memory"]["evidence_count"] == 1
    assert inherited["session"]["tasks"][1]["metadata"]["learner_memory"]["known_weak_points"]
    assert inherited["session"]["course_map"]["metadata"]["learner_memory"]["source_session_count"] == 1
    assert any("长期学习画像" in item for item in inherited["session"]["recommendations"])
    briefing = manager.build_coach_briefing(inherited["session"]["session_id"])
    assert briefing["success"] is True
    assert any("长期学习画像" in item for item in briefing["evidence_reasons"])


@pytest.mark.asyncio
async def test_guide_v2_uses_unified_learner_profile_when_planning(tmp_path) -> None:
    async def _failing_completion(**_kwargs):
        raise RuntimeError("llm unavailable")

    unified_service = _UnifiedProfileService(
        {
            "confidence": 0.74,
            "overview": {
                "current_focus": "梯度下降直观理解",
                "suggested_level": "beginner",
                "preferred_time_budget_minutes": 15,
                "summary": "需要先补齐优化直觉。",
            },
            "stable_profile": {
                "goals": ["掌握机器学习优化基础"],
                "preferences": ["video", "visual"],
                "strengths": ["愿意做反思"],
            },
            "learning_state": {
                "weak_points": [
                    {"label": "概念边界不清"},
                    {"label": "公式推导"},
                ],
            },
        }
    )
    manager = GuideV2Manager(
        output_dir=tmp_path,
        completion_fn=_failing_completion,
        learner_profile_service=unified_service,
    )

    result = await manager.create_session(GuideV2CreateInput(goal="学习梯度下降"))

    assert result["success"] is True
    profile = result["session"]["profile"]
    assert unified_service.calls == [True]
    assert profile["level"] == "beginner"
    assert profile["time_budget_minutes"] == 15
    assert "video" in profile["preferences"]
    assert "visual" in profile["preferences"]
    assert "概念边界不清" in profile["weak_points"]
    assert "公式推导" in profile["weak_points"]
    assert "Unified learner profile" in profile["source_context_summary"]
    assert "梯度下降直观理解" in profile["source_context_summary"]
    evaluation = manager.evaluate_session(result["session"]["session_id"])
    assert evaluation["learner_profile_context"]["available"] is True
    assert evaluation["learner_profile_context"]["weak_points"][0] == "概念边界不清"
    assert any("长期画像" in item for item in evaluation["risk_signals"])
    report = manager.build_learning_report(result["session"]["session_id"])
    assert report["learner_profile_context"]["available"] is True
    assert any(item["id"] == "longitudinal_profile" for item in report["effect_assessment"]["dimensions"])


@pytest.mark.asyncio
async def test_guide_v2_keeps_explicit_request_over_unified_profile(tmp_path) -> None:
    async def _failing_completion(**_kwargs):
        raise RuntimeError("llm unavailable")

    unified_service = _UnifiedProfileService(
        {
            "overview": {
                "suggested_level": "beginner",
                "preferred_time_budget_minutes": 15,
            },
            "stable_profile": {"preferences": ["video"]},
            "learning_state": {"weak_points": [{"label": "公式推导"}]},
        }
    )
    manager = GuideV2Manager(
        output_dir=tmp_path,
        completion_fn=_failing_completion,
        learner_profile_service=unified_service,
    )

    result = await manager.create_session(
        GuideV2CreateInput(
            goal="学习反向传播",
            level="advanced",
            time_budget_minutes=60,
            preferences=["practice"],
            weak_points=["代码实现"],
        )
    )

    profile = result["session"]["profile"]
    assert profile["level"] == "advanced"
    assert profile["time_budget_minutes"] == 60
    assert profile["preferences"][:2] == ["practice", "video"]
    assert profile["weak_points"][:2] == ["代码实现", "公式推导"]


@pytest.mark.asyncio
async def test_guide_v2_uses_llm_plan_when_available(tmp_path) -> None:
    async def _completion(**_kwargs):
        return json.dumps(
            {
                "course_map": {
                    "title": "Gradient Descent",
                    "nodes": [
                        {
                            "node_id": "N1",
                            "title": "Loss landscape",
                            "description": "Read the curve as optimization terrain.",
                            "difficulty": "easy",
                            "estimated_minutes": 12,
                            "tags": ["visual"],
                            "mastery_target": "Explain why the slope gives direction.",
                            "resource_strategy": ["visualize"],
                        }
                    ],
                },
                "learning_path": {
                    "title": "Gradient Descent Starter",
                    "rationale": "Start from the visual landscape.",
                    "node_sequence": ["N1"],
                    "today_focus": "Loss landscape",
                },
                "tasks": [
                    {
                        "task_id": "T1",
                        "node_id": "N1",
                        "type": "visualize",
                        "title": "Draw the loss landscape",
                        "instruction": "Use a curve to explain moving downhill.",
                        "estimated_minutes": 8,
                        "success_criteria": ["Identify downhill direction"],
                    }
                ],
                "recommendations": ["Use a graph before formulas."],
            },
            ensure_ascii=False,
        )

    manager = GuideV2Manager(output_dir=tmp_path, completion_fn=_completion)
    result = await manager.create_session(GuideV2CreateInput(goal="学习梯度下降"))

    session = result["session"]
    assert session["course_map"]["generated_by"] == "llm"
    assert session["course_map"]["nodes"][0]["title"] == "Loss landscape"
    assert session["tasks"][0]["type"] == "visualize"
    assert session["learning_path"]["today_focus"] == "Loss landscape"


@pytest.mark.asyncio
async def test_guide_v2_complete_task_updates_mastery_and_next_task(tmp_path) -> None:
    manager = GuideV2Manager(
        output_dir=tmp_path,
        completion_fn=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("unused")),
    )
    created = await manager.create_session(GuideV2CreateInput(goal="学习反向传播"))
    session_id = created["session"]["session_id"]
    first_task = created["session"]["tasks"][0]

    result = manager.complete_task(
        session_id,
        first_task["task_id"],
        score=0.9,
        reflection="我能解释链式法则如何传递梯度。",
    )

    assert result["success"] is True
    updated = result["session"]
    assert updated["tasks"][0]["status"] == "completed"
    assert updated["mastery"][first_task["node_id"]]["status"] == "mastered"
    assert updated["learning_path"]["current_task_id"] == updated["tasks"][1]["task_id"]
    assert updated["progress"] > 0


def test_guide_v2_lists_and_deletes_sessions(tmp_path) -> None:
    manager = GuideV2Manager(output_dir=tmp_path)
    session = manager.get_session("missing")
    assert session is None

    result = manager.delete_session("missing")
    assert result["success"] is False


def test_guide_v2_lists_course_templates(tmp_path) -> None:
    manager = GuideV2Manager(output_dir=tmp_path)

    templates = manager.list_course_templates()

    assert templates
    ml = templates[0]
    assert ml["id"] == "ml_foundations"
    assert ml["course_id"] == "ML101"
    assert ml["default_goal"]
    assert ml["learning_outcomes"]
    assert ml["assessment"]
    assert ml["demo_seed"]["task_chain"]
    assert ml["demo_seed"]["resource_prompts"]


def test_guide_v2_loads_json_course_templates(tmp_path) -> None:
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    (template_dir / "linear_algebra.json").write_text(
        """
{
  "id": "linear_algebra",
  "title": "线性代数入门",
  "course_id": "MATH101",
  "description": "矩阵、向量空间与线性变换。",
  "default_goal": "我想系统学习线性代数。",
  "default_preferences": ["visual", "practice"],
  "suggested_weeks": 6,
  "learning_outcomes": ["能解释矩阵乘法的几何含义"]
}
""".strip(),
        encoding="utf-8",
    )
    manager = GuideV2Manager(output_dir=tmp_path)

    templates = manager.list_course_templates()

    loaded = next(item for item in templates if item["id"] == "linear_algebra")
    assert loaded["course_id"] == "MATH101"
    assert loaded["default_preferences"] == ["visual", "practice"]
    assert loaded["suggested_weeks"] == 6
    assert loaded["learning_outcomes"] == ["能解释矩阵乘法的几何含义"]


@pytest.mark.asyncio
async def test_guide_v2_builds_study_plan_blocks_and_checkpoints(tmp_path) -> None:
    async def _failing_completion(**_kwargs):
        raise RuntimeError("llm unavailable")

    manager = GuideV2Manager(output_dir=tmp_path, completion_fn=_failing_completion)
    created = await manager.create_session(
        GuideV2CreateInput(
            goal="系统学习机器学习基础",
            time_budget_minutes=30,
            course_template_id="ml_foundations",
        )
    )
    session_id = created["session"]["session_id"]

    plan = manager.build_study_plan(session_id)

    assert plan["success"] is True
    assert plan["blocks"]
    assert plan["blocks"][0]["estimated_minutes"] <= 30
    assert plan["current_block"]["status"] == "active"
    assert plan["checkpoints"]
    assert plan["next_checkpoint"]["criteria"]
    assert plan["effect_assessment"]["dimensions"]
    assert plan["strategy_adjustments"]
    assert plan["remaining_minutes"] > 0


@pytest.mark.asyncio
async def test_guide_v2_diagnostic_updates_profile_and_path(tmp_path) -> None:
    async def _failing_completion(**_kwargs):
        raise RuntimeError("llm unavailable")

    manager = GuideV2Manager(output_dir=tmp_path, completion_fn=_failing_completion)
    created = await manager.create_session(
        GuideV2CreateInput(goal="系统学习机器学习基础", course_template_id="ml_foundations")
    )
    session_id = created["session"]["session_id"]

    diagnostic = manager.build_diagnostic(session_id)
    assert diagnostic["success"] is True
    assert diagnostic["questions"]
    answers = [
        {"question_id": "experience_level", "value": "new"},
        {"question_id": "time_fit", "value": "tight"},
        {"question_id": "preferred_resource", "value": "visual"},
        {"question_id": "current_bottleneck", "value": "formula"},
    ]
    for question in diagnostic["questions"]:
        if str(question["question_id"]).startswith("confidence:"):
            answers.append({"question_id": question["question_id"], "value": 1})
            break

    result = manager.submit_diagnostic(session_id, answers)

    assert result["success"] is True
    assert result["diagnosis"]["readiness_score"] < 0.65
    assert result["diagnosis"]["bottleneck_label"] == "公式/推导断裂"
    assert result["diagnosis"]["learning_strategy"]
    assert result["adjustments"][0]["type"] == "diagnostic_remediation"
    session = manager.get_session(session_id)
    assert session["tasks"][0]["origin"] == "diagnostic_remediation"
    assert session["tasks"][0]["metadata"]["bottleneck_label"] == "公式/推导断裂"
    assert session["profile"]["weak_points"]
    briefing = manager.build_coach_briefing(session_id)
    assert briefing["coach_actions"][0]["label"].startswith("前测策略")
    assert briefing["coach_actions"][0]["resource_type"] in {"visual", "video"}
    completed_diagnostic = manager.build_diagnostic(session_id)
    assert completed_diagnostic["status"] == "completed"
    assert completed_diagnostic["last_result"]["learning_strategy"]


@pytest.mark.asyncio
async def test_guide_v2_profile_dialogue_updates_profile_and_inserts_focus_task(tmp_path) -> None:
    async def _failing_completion(**_kwargs):
        raise RuntimeError("llm unavailable")

    manager = GuideV2Manager(output_dir=tmp_path, completion_fn=_failing_completion)
    created = await manager.create_session(
        GuideV2CreateInput(goal="系统学习机器学习基础", course_template_id="ml_foundations")
    )
    session_id = created["session"]["session_id"]

    dialogue = manager.build_profile_dialogue(session_id)
    assert dialogue["success"] is True
    assert dialogue["suggested_prompts"]

    result = manager.submit_profile_dialogue(
        session_id,
        "我今天只有20分钟，公式推导不太会，希望先看图解再做题。",
    )

    assert result["success"] is True
    assert result["signals"]["time_budget_minutes"] == 20
    assert "visual" in result["signals"]["preferences"]
    assert result["adjustments"][0]["type"] == "profile_dialogue_focus"
    session = manager.get_session(session_id)
    assert session["profile"]["time_budget_minutes"] == 20
    assert session["tasks"][0]["origin"] == "profile_dialogue"
    assert manager.build_profile_dialogue(session_id)["status"] == "updated"


@pytest.mark.asyncio
async def test_guide_v2_builds_learning_timeline(tmp_path) -> None:
    async def _failing_completion(**_kwargs):
        raise RuntimeError("llm unavailable")

    manager = GuideV2Manager(output_dir=tmp_path, completion_fn=_failing_completion)
    created = await manager.create_session(GuideV2CreateInput(goal="学习梯度下降"))
    session_id = created["session"]["session_id"]
    await manager.create_session(GuideV2CreateInput(goal="另一条路线"))

    manager.submit_profile_dialogue(session_id, "我今天只有20分钟，概念不太懂，希望先看图解。")
    task_id = manager.get_session(session_id)["current_task"]["task_id"]
    manager.complete_task(session_id, task_id, score=0.82, reflection="我能解释主要概念。")

    timeline = manager.build_learning_timeline(session_id)

    assert timeline["success"] is True
    assert timeline["summary"]["event_count"] >= 4
    assert timeline["summary"]["profile_update_count"] >= 1
    assert timeline["summary"]["path_adjustment_count"] >= 1
    assert any(event["type"] == "profile_dialogue" for event in timeline["events"])
    assert any(event["type"] == "task_completed" for event in timeline["events"])
    assert timeline["behavior_tags"]

    briefing = manager.build_coach_briefing(session_id)

    assert briefing["success"] is True
    assert briefing["headline"]
    assert briefing["focus"]["task_title"]
    assert briefing["micro_plan"]
    assert briefing["evidence_reasons"]


@pytest.mark.asyncio
async def test_guide_v2_generates_resource_and_attaches_artifact(tmp_path) -> None:
    async def _failing_completion(**_kwargs):
        raise RuntimeError("llm unavailable")

    calls: list[tuple[str, Any]] = []

    async def _runner(capability: str, context: Any) -> dict[str, Any]:
        calls.append((capability, context))
        return {
            "response": "概念图已生成",
            "render_type": "svg",
            "code": {"language": "svg", "content": "<svg />"},
        }

    manager = GuideV2Manager(
        output_dir=tmp_path,
        completion_fn=_failing_completion,
        capability_runner=_runner,
    )
    created = await manager.create_session(
        GuideV2CreateInput(
            goal="学习牛顿第二定律",
            level="beginner",
            time_budget_minutes=25,
            preferences=["visual", "practice"],
            weak_points=["公式含义"],
        )
    )
    session_id = created["session"]["session_id"]
    task_id = created["session"]["tasks"][0]["task_id"]

    events: list[tuple[str, dict[str, Any]]] = []
    result = await manager.generate_resource(
        session_id,
        task_id,
        resource_type="visual",
        prompt="突出公式含义",
        event_sink=lambda event, payload: events.append((event, payload)),
    )

    assert result["success"] is True
    assert [event for event, _payload in events] == ["status", "status"]
    assert events[0][1]["stage"] == "preparing"
    assert events[-1][1]["stage"] == "saving"
    assert calls[0][0] == "visualize"
    assert calls[0][1].config_overrides == {"render_mode": "svg"}
    assert "牛顿第二定律" in calls[0][1].user_message
    assert "Learner personalization:" in calls[0][1].user_message
    assert "weak points to address: 公式含义" in calls[0][1].user_message
    hints = calls[0][1].metadata["learner_profile_hints"]
    assert hints["level"] == "beginner"
    assert hints["time_budget_minutes"] == 25
    assert "visual" in hints["preferences"]
    assert "公式含义" in hints["weak_points"]
    artifact = result["artifact"]
    assert artifact["type"] == "visual"
    assert artifact["personalization"]["weak_points"] == ["公式含义"]
    assert artifact["result"]["render_type"] == "svg"
    updated = manager.get_session(session_id)
    assert updated["tasks"][0]["artifact_refs"][0]["id"] == artifact["id"]


@pytest.mark.asyncio
async def test_guide_v2_quiz_attempt_updates_learning_evidence(tmp_path) -> None:
    async def _failing_completion(**_kwargs):
        raise RuntimeError("llm unavailable")

    async def _runner(_capability: str, _context: Any) -> dict[str, Any]:
        return {
            "response": "quiz ready",
            "results": [
                {
                    "qa_pair": {
                        "question_id": "q1",
                        "question": "A feature matrix stores what?",
                        "question_type": "choice",
                        "options": {"A": "Examples and features", "B": "Only labels"},
                        "correct_answer": "A",
                        "explanation": "Rows usually represent examples and columns represent features.",
                        "concepts": ["feature matrix"],
                    }
                },
                {
                    "qa_pair": {
                        "question_id": "q2",
                        "question": "Labels are the target outputs.",
                        "question_type": "true_false",
                        "options": {"True": "正确", "False": "错误"},
                        "correct_answer": "True",
                        "explanation": "Labels are what supervised learning predicts.",
                        "concepts": ["labels"],
                    }
                },
            ],
        }

    manager = GuideV2Manager(
        output_dir=tmp_path,
        completion_fn=_failing_completion,
        capability_runner=_runner,
    )
    created = await manager.create_session(GuideV2CreateInput(goal="Learn supervised learning basics"))
    session_id = created["session"]["session_id"]
    task_id = created["session"]["tasks"][0]["task_id"]
    generated = await manager.generate_resource(session_id, task_id, resource_type="quiz")
    artifact_id = generated["artifact"]["id"]

    result = manager.submit_quiz_attempt(
        session_id,
        task_id,
        artifact_id,
        answers=[
            {
                "question_id": "q1",
                "question": "A feature matrix stores what?",
                "question_type": "choice",
                "options": {"A": "Examples and features", "B": "Only labels"},
                "user_answer": "A",
                "correct_answer": "A",
                "is_correct": True,
                "concepts": ["feature matrix"],
            },
            {
                "question_id": "q2",
                "question": "Labels are the target outputs.",
                "question_type": "true_false",
                "options": {"True": "正确", "False": "错误"},
                "user_answer": "False",
                "correct_answer": "True",
                "is_correct": False,
                "concepts": ["labels"],
            },
        ],
    )

    assert result["success"] is True
    assert result["attempt"]["score"] == 0.5
    assert result["attempt"]["concepts"] == ["feature matrix", "labels"]
    assert result["attempt"]["concept_feedback"][0]["concept"] == "labels"
    assert result["attempt"]["concept_feedback"][0]["status"] == "needs_support"
    assert result["evidence"]["type"] == "quiz"
    assert result["evidence"]["metadata"]["concepts"] == ["feature matrix", "labels"]
    assert result["evidence"]["metadata"]["concept_feedback"][0]["concept"] == "labels"
    assert "labels" in result["evidence"]["mistake_types"]
    assert result["learning_feedback"]["tone"] == "warning"
    assert result["learning_feedback"]["concept_feedback"][0]["concept"] == "labels"
    assert result["learning_feedback"]["resource_actions"][0]["resource_type"] == "visual"
    remediation_id = result["adjustments"][0]["inserted_task_ids"][0]
    assert result["learning_feedback"]["resource_actions"][0]["target_task_id"] == remediation_id
    assert "labels" in result["learning_feedback"]["resource_actions"][0]["prompt"]
    assert result["learning_feedback"]["actions"]
    assert result["learning_feedback"]["evidence_quality"]["score"] > 0
    assert result["evidence"]["metadata"]["evidence_quality"]["label"]
    assert result["evidence"]["metadata"]["learning_feedback"]["tone"] == "warning"
    assert result["session"]["tasks"][0]["status"] == "completed"
    updated = manager.get_session(session_id)
    assert updated["tasks"][0]["artifact_refs"][0]["quiz_attempts"][0]["correct_count"] == 1
    assert updated["mastery"][created["session"]["tasks"][0]["node_id"]]["status"] in {"learning", "needs_support"}
    assert updated["plan_events"]
    assert len(updated["plan_events"][0]["inserted_task_ids"]) == 2
    assert any(task["origin"] == "adaptive_retest" for task in updated["tasks"])
    remediation_id, retest_id = updated["plan_events"][0]["inserted_task_ids"]

    review = manager.build_mistake_review(session_id)

    assert review["success"] is True
    assert review["summary"]["cluster_count"] >= 1
    assert review["summary"]["pending_retest_count"] >= 1
    assert review["clusters"][0]["loop_status"] == "needs_remediation"
    assert review["clusters"][0]["suggested_action"]
    assert review["retest_plan"]
    briefing = manager.build_coach_briefing(session_id)
    assert briefing["coach_mode"] == "remediation"
    assert briefing["mistake_summary"]["open_cluster_count"] >= 1
    assert briefing["priority_mistake"]["loop_status"] == "needs_remediation"
    assert briefing["effect_assessment"]["dimensions"]
    assert briefing["strategy_adjustments"]
    assert briefing["coach_actions"][0]["resource_type"] == "visual"
    assert briefing["coach_actions"][0]["target_task_id"] == remediation_id

    manager.complete_task(session_id, remediation_id, score=0.78, reflection="我已经整理出错因。")
    ready_review = manager.build_mistake_review(session_id)
    assert ready_review["clusters"][0]["loop_status"] == "ready_for_retest"
    ready_briefing = manager.build_coach_briefing(session_id)
    assert ready_briefing["coach_mode"] == "retest"
    assert ready_briefing["priority_mistake"]["loop_status"] == "ready_for_retest"
    assert ready_briefing["coach_actions"][0]["resource_type"] == "quiz"
    assert ready_briefing["coach_actions"][0]["target_task_id"] == retest_id

    manager.complete_task(session_id, retest_id, score=0.86, reflection="复测通过，能解释判断条件。")
    closed_review = manager.build_mistake_review(session_id)
    assert closed_review["summary"]["closed_loop"] is True
    assert closed_review["summary"]["closed_cluster_count"] >= 1
    assert closed_review["clusters"][0]["loop_status"] == "closed"
    closed_briefing = manager.build_coach_briefing(session_id)
    assert closed_briefing["coach_mode"] == "closed_loop"
    assert closed_briefing["mistake_summary"]["closed_loop"] is True


@pytest.mark.asyncio
async def test_guide_v2_evaluates_learning_effect(tmp_path) -> None:
    async def _failing_completion(**_kwargs):
        raise RuntimeError("llm unavailable")

    async def _runner(_capability: str, _context: Any) -> dict[str, Any]:
        return {
            "response": "quiz ready",
            "results": [
                {
                    "qa_pair": {
                        "question_id": "q1",
                        "question": "What is a gradient?",
                        "correct_answer": "direction",
                    }
                }
            ],
        }

    manager = GuideV2Manager(
        output_dir=tmp_path,
        completion_fn=_failing_completion,
        capability_runner=_runner,
    )
    created = await manager.create_session(GuideV2CreateInput(goal="学习梯度下降"))
    session_id = created["session"]["session_id"]
    task_id = created["session"]["tasks"][0]["task_id"]
    manager.complete_task(session_id, task_id, score=0.9, reflection="理解了下降方向")
    await manager.generate_resource(session_id, task_id, resource_type="quiz")

    result = manager.evaluate_session(session_id)

    assert result["success"] is True
    assert result["overall_score"] > 0
    assert result["completed_tasks"] == 1
    assert result["question_count"] == 1
    assert result["resource_counts"]["quiz"] == 1
    assert result["evidence_trend"][0]["score"] == 0.9
    assert result["next_actions"]


@pytest.mark.asyncio
async def test_guide_v2_builds_learning_report(tmp_path) -> None:
    async def _failing_completion(**_kwargs):
        raise RuntimeError("llm unavailable")

    manager = GuideV2Manager(output_dir=tmp_path, completion_fn=_failing_completion)
    created = await manager.create_session(
        GuideV2CreateInput(
            goal="Build a machine learning study plan",
            course_template_id="ml_foundations",
        )
    )
    session_id = created["session"]["session_id"]
    first_task = created["session"]["tasks"][0]

    manager.complete_task(
        session_id,
        first_task["task_id"],
        score=0.4,
        reflection="I still confuse features, labels, and examples.",
    )

    report = manager.build_learning_report(session_id)

    assert report["success"] is True
    assert report["session_id"] == session_id
    assert report["overview"]["path_adjustment_count"] >= 1
    assert report["overview"]["completed_tasks"] == 1
    assert report["node_cards"]
    assert report["node_cards"][0]["suggestion"]
    assert report["evidence_summary"]["count"] == 1
    assert report["behavior_summary"]["event_count"] >= 2
    assert report["behavior_tags"]
    assert report["feedback_digest"]["count"] >= 1
    assert report["feedback_digest"]["quality_average"] >= 0
    assert report["feedback_digest"]["latest"]["summary"]
    assert report["effect_assessment"]["score"] >= 0
    assert report["effect_assessment"]["dimensions"]
    assert any(item["id"] == "longitudinal_profile" for item in report["effect_assessment"]["dimensions"])
    assert report["effect_assessment"]["strategy_adjustments"]
    assert report["action_brief"]["title"]
    assert report["action_brief"]["primary_action"]["label"]
    assert report["action_brief"]["primary_action"]["target_task_id"]
    assert report["action_brief"]["primary_action"]["resource_type"] in {"visual", "quiz"}
    assert report["action_brief"]["primary_action"]["prompt"]
    assert report["action_brief"]["signals"]
    assert report["demo_readiness"]["score"] >= 0
    assert report["demo_readiness"]["label"]
    assert report["demo_readiness"]["checks"]
    assert report["demo_readiness"]["next_steps"]
    assert report["timeline_events"]
    assert report["mistake_review"]["summary"]["cluster_count"] >= 1
    assert report["interventions"]
    assert "markdown" in report
    assert "学习效果报告" in report["markdown"]
    assert "学习效果评估" in report["markdown"]
    assert "学习处方" in report["markdown"]
    assert "演示就绪度" in report["markdown"]
    assert "学习行为证据" in report["markdown"]
    assert "即时反馈摘要" in report["markdown"]
    assert "错因与复测闭环" in report["markdown"]


@pytest.mark.asyncio
async def test_guide_v2_builds_course_package(tmp_path) -> None:
    async def _failing_completion(**_kwargs):
        raise RuntimeError("llm unavailable")

    manager = GuideV2Manager(output_dir=tmp_path, completion_fn=_failing_completion)
    created = await manager.create_session(
        GuideV2CreateInput(
            goal="Build a complete machine learning foundations portfolio",
            course_template_id="ml_foundations",
            preferences=["visual", "practice"],
        )
    )
    session_id = created["session"]["session_id"]
    first_task = created["session"]["tasks"][0]
    manager.complete_task(session_id, first_task["task_id"], score=0.82, reflection="I can explain the course goal.")

    package = manager.build_course_package(session_id)

    assert package["success"] is True
    assert package["session_id"] == session_id
    assert package["capstone_project"]["deliverables"]
    assert package["course_metadata"]["course_id"] == "ML101"
    assert package["rubric"]
    assert package["review_plan"]
    assert package["demo_outline"]
    assert package["demo_blueprint"]["duration_minutes"] == 7
    assert package["learning_style"]["label"]
    assert package["learning_style"]["signals"]
    assert package["demo_blueprint"]["learning_style"]["label"] == package["learning_style"]["label"]
    assert package["demo_blueprint"]["storyline"]
    assert package["demo_blueprint"]["judge_mapping"]
    assert package["demo_fallback_kit"]["persona"]["goal"]
    assert package["demo_fallback_kit"]["assets"]
    assert package["demo_fallback_kit"]["checklist"]
    assert package["demo_fallback_kit"]["fallback_script"]
    assert package["demo_seed_pack"]["task_chain"]
    assert package["demo_seed_pack"]["resource_prompts"]
    assert package["demo_seed_pack"]["report_anchor"]["score"] >= 0
    assert package["learning_report"]["demo_readiness"]["checks"]
    assert package["learning_report"]["behavior_summary"]["event_count"] >= 2
    assert package["learning_report"]["feedback_digest"]["count"] >= 1
    assert package["learning_report"]["effect_assessment"]["dimensions"]
    assert package["learning_report"]["behavior_tags"]
    assert "mistake_summary" in package["learning_report"]
    assert "课程产出包" in package["markdown"]
    assert "学习画像与推进方式" in package["markdown"]
    assert "最近学习轨迹" in package["markdown"]
    assert "7 分钟演示路线" in package["markdown"]
    assert "录屏兜底包" in package["markdown"]
    assert "稳定 Demo 样例" in package["markdown"]


@pytest.mark.asyncio
async def test_guide_v2_recommends_personalized_resources(tmp_path) -> None:
    async def _failing_completion(**_kwargs):
        raise RuntimeError("llm unavailable")

    manager = GuideV2Manager(output_dir=tmp_path, completion_fn=_failing_completion)
    created = await manager.create_session(
        GuideV2CreateInput(
            goal="学习线性代数特征值",
            preferences=["visual", "video"],
        )
    )
    session_id = created["session"]["session_id"]
    first_task = created["session"]["tasks"][0]

    initial = manager.recommend_resources(session_id)

    assert initial["success"] is True
    assert initial["effect_assessment"]["dimensions"]
    assert "学习效果评估" in initial["summary"]
    assert any(item["resource_type"] == "quiz" for item in initial["recommendations"])
    assert any(item["resource_type"] == "video" for item in initial["recommendations"])
    assert initial["recommendations"][0]["target_task_id"]
    assert initial["recommendations"][0]["effect_score"] == initial["effect_assessment"]["score"]

    completed = manager.complete_task(
        session_id,
        first_task["task_id"],
        score=0.3,
        reflection="仍然分不清特征值和特征向量的关系",
    )
    assert completed["adjustments"][0]["type"] == "insert_remediation"
    assert len(completed["adjustments"][0]["inserted_task_ids"]) == 2
    assert completed["session"]["current_task"]["origin"] == "adaptive_remediation"
    assert completed["learning_feedback"]["tone"] == "warning"
    assert completed["learning_feedback"]["evidence_quality"]["score"] > 0
    assert completed["learning_feedback"]["next_task_id"] == completed["session"]["current_task"]["task_id"]
    assert completed["evidence"]["metadata"]["learning_feedback"]["title"] == completed["learning_feedback"]["title"]
    assert any(task["origin"] == "adaptive_retest" for task in completed["session"]["tasks"])
    profile = manager.get_session(session_id)["profile"]
    assert profile["weak_points"]
    assert "Latest evidence" in profile["source_context_summary"]

    after_low_score = manager.recommend_resources(session_id)

    assert after_low_score["effect_assessment"]["score"] < 80
    assert any(
        item["resource_type"] == "visual" and item["priority"] in {"high", "medium"}
        for item in after_low_score["recommendations"]
    )
    assert any("掌握" in item["reason"] or "证据" in item["reason"] for item in after_low_score["recommendations"])

    refreshed = manager.refresh_recommendations(session_id)
    assert refreshed["success"] is True
    assert any("低分" in item or "薄弱" in item for item in refreshed["recommendations"])

    review = manager.build_mistake_review(session_id)
    assert review["summary"]["pending_remediation_count"] >= 1
    assert review["summary"]["pending_retest_count"] >= 1
    assert review["summary"]["open_cluster_count"] >= 1
    assert review["clusters"][0]["loop_status"] in {"needs_remediation", "ready_for_retest"}
    timeline = manager.build_learning_timeline(session_id)
    feedback_events = [item for item in timeline["events"] if item.get("feedback_summary")]
    assert feedback_events
    assert feedback_events[-1]["learning_feedback"]["tone"] == "warning"

@pytest.mark.asyncio
async def test_guide_v2_adds_transfer_challenge_after_strong_completion(tmp_path) -> None:
    async def _failing_completion(**_kwargs):
        raise RuntimeError("llm unavailable")

    manager = GuideV2Manager(output_dir=tmp_path, completion_fn=_failing_completion)
    created = await manager.create_session(GuideV2CreateInput(goal="学习概率论中的贝叶斯公式"))
    session_id = created["session"]["session_id"]
    initial_task_ids = [task["task_id"] for task in created["session"]["tasks"]]

    result = None
    for task_id in initial_task_ids:
        result = manager.complete_task(
            session_id,
            task_id,
            score=0.88,
            reflection="能够解释并应用这个知识点。",
        )

    assert result is not None
    assert result["adjustments"][-1]["type"] == "insert_transfer"
    assert result["session"]["current_task"]["origin"] == "adaptive_transfer"
    assert result["session"]["status"] == "learning"

    evaluation = manager.evaluate_session(session_id)
    assert evaluation["path_adjustment_count"] >= 1
    assert evaluation["progress"] < 100

    transfer_task_id = result["session"]["current_task"]["task_id"]
    finished = manager.complete_task(session_id, transfer_task_id, score=0.9, reflection="能迁移到新场景。")
    assert finished["session"]["status"] == "completed"
    assert finished["session"]["progress"] == 100
    assert finished["learning_feedback"]["tone"] == "success"
@pytest.mark.asyncio
async def test_guide_v2_creates_machine_learning_course_template(tmp_path) -> None:
    async def _failing_completion(**_kwargs):
        raise RuntimeError("llm should not be called for templates")

    manager = GuideV2Manager(output_dir=tmp_path, completion_fn=_failing_completion)
    result = await manager.create_session(
        GuideV2CreateInput(
            goal="我想系统学习机器学习基础",
            course_template_id="ml_foundations",
        )
    )

    assert result["success"] is True
    session = result["session"]
    assert session["course_map"]["generated_by"] == "template:ml_foundations"
    assert session["course_map"]["metadata"]["course_id"] == "ML101"
    assert len(session["course_map"]["metadata"]["weekly_schedule"]) == 8
    assert session["course_map"]["metadata"]["assessment"]
    assert session["course_map"]["title"].startswith("机器学习基础")
    assert len(session["course_map"]["nodes"]) == 8
    assert len(session["tasks"]) == 8
    assert session["tasks"][-1]["type"] == "project"
