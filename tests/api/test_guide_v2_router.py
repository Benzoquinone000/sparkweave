from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sparkweave.api.routers import guide_v2
from sparkweave.services.guide_v2 import GuideV2CreateInput, GuideV2Manager


class _EvidenceRecorder:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def append_events(self, events: list[dict], *, dedupe: bool = True):
        self.events.extend(events)
        return {"added": len(events), "skipped": 0, "events": events}


def _client_with_manager(manager: GuideV2Manager, monkeypatch, recorder: _EvidenceRecorder | None = None) -> TestClient:
    evidence_recorder = recorder or _EvidenceRecorder()
    app = FastAPI()
    app.include_router(guide_v2.router, prefix="/api/v1/guide/v2")
    monkeypatch.setattr(guide_v2, "get_guide_v2_manager", lambda: manager)
    monkeypatch.setattr(guide_v2, "get_learner_evidence_service", lambda: evidence_recorder)
    return TestClient(app)


def test_guide_v2_router_create_get_complete_and_delete(tmp_path, monkeypatch) -> None:
    async def _failing_completion(**_kwargs):
        raise RuntimeError("llm unavailable")

    async def _runner(capability: str, context: Any) -> dict[str, Any]:
        if capability == "deep_question":
            return {
                "response": "quiz ready",
                "results": [
                    {
                        "qa_pair": {
                            "question_id": "q1",
                            "question": "逻辑回归输出表示什么？",
                            "question_type": "choice",
                            "options": {"A": "概率", "B": "距离"},
                            "correct_answer": "A",
                            "explanation": "sigmoid 输出可解释为概率。",
                            "difficulty": "medium",
                            "concepts": ["逻辑回归"],
                        }
                    }
                ],
            }
        return {
            "response": f"{capability} ready",
            "guide_task_id": context.metadata.get("guide_task_id"),
        }

    manager = GuideV2Manager(
        output_dir=tmp_path,
        completion_fn=_failing_completion,
        capability_runner=_runner,
    )
    evidence_recorder = _EvidenceRecorder()
    client = _client_with_manager(manager, monkeypatch, evidence_recorder)

    templates_response = client.get("/api/v1/guide/v2/templates")
    assert templates_response.status_code == 200
    templates = templates_response.json()["templates"]
    assert templates[0]["id"] == "ml_foundations"
    assert templates[0]["course_id"] == "ML101"
    assert templates[0]["demo_seed"]["task_chain"]

    create_response = client.post(
        "/api/v1/guide/v2/sessions",
        json={
            "goal": "一周内掌握逻辑回归",
            "level": "beginner",
            "preferences": ["visual", "practice"],
            "source_action": {
                "source": "learner_profile",
                "kind": "continue",
                "source_label": "逻辑回归",
                "suggested_prompt": "基于画像继续学习逻辑回归。",
            },
        },
    )
    assert create_response.status_code == 200
    create_payload = create_response.json()
    created = create_payload["session"]
    session_id = created["session_id"]
    task_id = created["tasks"][0]["task_id"]
    assert created["course_map"]["metadata"]["source_action"]["source_label"] == "逻辑回归"
    assert created["tasks"][0]["metadata"]["source_action"]["kind"] == "continue"
    assert create_payload["evidence"]["recorded"] is True
    assert evidence_recorder.events[0]["source"] == "guide_v2"
    assert evidence_recorder.events[0]["object_type"] == "guide_session"
    assert evidence_recorder.events[0]["metadata"]["source_action"]["source_label"] == "逻辑回归"

    detail_response = client.get(f"/api/v1/guide/v2/sessions/{session_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["current_task"]["task_id"] == task_id
    assert detail["course_map"]["nodes"]

    memory_response = client.get("/api/v1/guide/v2/learner-memory")
    assert memory_response.status_code == 200
    memory = memory_response.json()
    assert memory["session_count"] == 1
    assert any(item["label"] == "visual" for item in memory["top_preferences"])

    resource_response = client.post(
        f"/api/v1/guide/v2/sessions/{session_id}/tasks/{task_id}/resources",
        json={"resource_type": "quiz", "prompt": "加入选择题和判断题"},
    )
    assert resource_response.status_code == 200
    resource = resource_response.json()
    assert resource["artifact"]["type"] == "quiz"
    assert resource["artifact"]["capability"] == "deep_question"
    assert resource["task"]["artifact_refs"]
    artifact_id = resource["artifact"]["id"]

    class _NotebookManager:
        def add_record(self, **kwargs):
            return {
                "record": {
                    "id": "record_1",
                    "title": kwargs["title"],
                    "record_type": kwargs["record_type"],
                    "output": kwargs["output"],
                },
                "added_to_notebooks": kwargs["notebook_ids"],
            }

    class _QuestionStore:
        def __init__(self) -> None:
            self.sessions: set[str] = set()
            self.items: list[dict] = []

        async def get_session(self, session_id: str):
            return {"id": session_id} if session_id in self.sessions else None

        async def create_session(self, title: str | None = None, session_id: str | None = None):
            self.sessions.add(session_id or "created")
            return {"id": session_id, "title": title}

        async def upsert_notebook_entries(self, session_id: str, items: list[dict]):
            self.items.extend(items)
            return len(items)

    question_store = _QuestionStore()
    monkeypatch.setattr(guide_v2, "notebook_manager", _NotebookManager())
    monkeypatch.setattr(guide_v2, "get_sqlite_session_store", lambda: question_store)

    quiz_submit_response = client.post(
        f"/api/v1/guide/v2/sessions/{session_id}/tasks/{task_id}/artifacts/{artifact_id}/quiz-results",
        json={
            "answers": [
                {
                    "question_id": "q1",
                    "question": "逻辑回归输出表示什么？",
                    "question_type": "choice",
                    "options": {"A": "概率", "B": "距离"},
                    "user_answer": "A",
                    "correct_answer": "A",
                    "explanation": "sigmoid 输出可解释为概率。",
                    "difficulty": "medium",
                    "is_correct": True,
                    "concepts": ["逻辑回归"],
                }
            ]
        },
    )
    assert quiz_submit_response.status_code == 200
    quiz_submit = quiz_submit_response.json()
    assert quiz_submit["attempt"]["score"] == 1
    assert quiz_submit["attempt"]["concepts"] == ["逻辑回归"]
    assert quiz_submit["attempt"]["concept_feedback"][0]["concept"] == "逻辑回归"
    assert quiz_submit["attempt"]["concept_feedback"][0]["status"] == "stable"
    assert quiz_submit["evidence"]["type"] == "quiz"
    assert quiz_submit["evidence"]["metadata"]["concepts"] == ["逻辑回归"]
    assert quiz_submit["learning_feedback"]["concept_feedback"][0]["concept"] == "逻辑回归"
    assert quiz_submit["learning_feedback"]["resource_actions"][0]["resource_type"] == "quiz"
    expected_action_target = task_id
    if quiz_submit["adjustments"] and quiz_submit["adjustments"][0].get("inserted_task_ids"):
        expected_action_target = quiz_submit["adjustments"][0]["inserted_task_ids"][0]
    assert quiz_submit["learning_feedback"]["resource_actions"][0]["target_task_id"] == expected_action_target
    assert quiz_submit["learning_feedback"]["title"]
    assert quiz_submit["learning_feedback"]["evidence_quality"]["score"] > 0
    assert quiz_submit["evidence"]["metadata"]["learning_feedback"]["title"]
    assert quiz_submit["question_notebook"]["saved"] is True

    save_response = client.post(
        f"/api/v1/guide/v2/sessions/{session_id}/tasks/{task_id}/artifacts/{artifact_id}/save",
        json={"notebook_ids": ["nb_1"], "save_questions": True},
    )
    assert save_response.status_code == 200
    saved = save_response.json()
    assert saved["notebook"]["added_to_notebooks"] == ["nb_1"]
    assert saved["question_notebook"]["saved"] is True
    assert saved["question_notebook"]["count"] == 1
    assert question_store.items[0]["question_id"] == "q1"

    report_save_response = client.post(
        f"/api/v1/guide/v2/sessions/{session_id}/report/save",
        json={"notebook_ids": ["nb_1"]},
    )
    assert report_save_response.status_code == 200
    report_saved = report_save_response.json()
    assert report_saved["notebook"]["added_to_notebooks"] == ["nb_1"]
    assert report_saved["notebook"]["record"]["record_type"] == "guided_learning"

    package_save_response = client.post(
        f"/api/v1/guide/v2/sessions/{session_id}/course-package/save",
        json={"notebook_ids": ["nb_1"]},
    )
    assert package_save_response.status_code == 200
    package_saved = package_save_response.json()
    assert package_saved["notebook"]["added_to_notebooks"] == ["nb_1"]
    assert package_saved["notebook"]["record"]["record_type"] == "guided_learning"

    evaluation_response = client.get(f"/api/v1/guide/v2/sessions/{session_id}/evaluation")
    assert evaluation_response.status_code == 200
    evaluation = evaluation_response.json()
    assert evaluation["session_id"] == session_id
    assert evaluation["resource_counts"]["quiz"] == 1
    assert evaluation["question_count"] == 1

    study_plan_response = client.get(f"/api/v1/guide/v2/sessions/{session_id}/study-plan")
    assert study_plan_response.status_code == 200
    study_plan = study_plan_response.json()
    assert study_plan["session_id"] == session_id
    assert study_plan["blocks"]
    assert study_plan["checkpoints"]
    assert study_plan["current_block"]
    assert study_plan["effect_assessment"]["dimensions"]

    diagnostic_response = client.get(f"/api/v1/guide/v2/sessions/{session_id}/diagnostic")
    assert diagnostic_response.status_code == 200
    diagnostic = diagnostic_response.json()
    assert diagnostic["questions"]
    diagnostic_answers = [
        {"question_id": "experience_level", "value": "learned"},
        {"question_id": "time_fit", "value": "fit"},
        {"question_id": "preferred_resource", "value": "practice"},
        {"question_id": "current_bottleneck", "value": "practice"},
    ]
    for question in diagnostic["questions"]:
        if str(question["question_id"]).startswith("confidence:"):
            diagnostic_answers.append({"question_id": question["question_id"], "value": 3})
            break
    diagnostic_submit_response = client.post(
        f"/api/v1/guide/v2/sessions/{session_id}/diagnostic",
        json={"answers": diagnostic_answers},
    )
    assert diagnostic_submit_response.status_code == 200
    diagnostic_result = diagnostic_submit_response.json()
    assert diagnostic_result["diagnosis"]["readiness_score"] > 0
    assert diagnostic_result["diagnosis"]["bottleneck_label"] == "会看不会做题"
    assert diagnostic_result["diagnosis"]["learning_strategy"]
    assert diagnostic_result["session"]["profile"]["source_context_summary"]

    profile_dialogue_response = client.get(f"/api/v1/guide/v2/sessions/{session_id}/profile-dialogue")
    assert profile_dialogue_response.status_code == 200
    assert profile_dialogue_response.json()["suggested_prompts"]
    profile_dialogue_submit_response = client.post(
        f"/api/v1/guide/v2/sessions/{session_id}/profile-dialogue",
        json={"message": "我今天只有20分钟，想先看图解再做练习。"},
    )
    assert profile_dialogue_submit_response.status_code == 200
    profile_dialogue = profile_dialogue_submit_response.json()
    assert profile_dialogue["signals"]["time_budget_minutes"] == 20
    assert profile_dialogue["assistant_reply"]

    timeline_response = client.get(f"/api/v1/guide/v2/sessions/{session_id}/learning-timeline")
    assert timeline_response.status_code == 200
    timeline = timeline_response.json()
    assert timeline["session_id"] == session_id
    assert timeline["summary"]["event_count"] >= 1
    assert timeline["recent_events"]
    assert timeline["behavior_tags"]

    mistake_review_response = client.get(f"/api/v1/guide/v2/sessions/{session_id}/mistake-review")
    assert mistake_review_response.status_code == 200
    mistake_review = mistake_review_response.json()
    assert "summary" in mistake_review
    assert "retest_plan" in mistake_review

    briefing_response = client.get(f"/api/v1/guide/v2/sessions/{session_id}/coach-briefing")
    assert briefing_response.status_code == 200
    briefing = briefing_response.json()
    assert briefing["headline"]
    assert briefing["coach_mode"]
    assert "coach_actions" in briefing
    assert briefing["effect_assessment"]["dimensions"]
    assert "mistake_summary" in briefing
    assert briefing["focus"]["task_title"]
    assert briefing["micro_plan"]

    report_response = client.get(f"/api/v1/guide/v2/sessions/{session_id}/report")
    assert report_response.status_code == 200
    report = report_response.json()
    assert report["session_id"] == session_id
    assert report["overview"]["total_tasks"] >= len(created["tasks"])
    assert report["node_cards"]
    assert report["behavior_summary"]["event_count"] >= timeline["summary"]["event_count"]
    assert report["timeline_events"]
    assert report["effect_assessment"]["dimensions"]
    assert report["action_brief"]["primary_action"]["label"]
    assert report["demo_readiness"]["score"] >= 0
    assert report["demo_readiness"]["checks"]
    assert "mistake_review" in report
    assert report["markdown"]

    package_response = client.get(f"/api/v1/guide/v2/sessions/{session_id}/course-package")
    assert package_response.status_code == 200
    package = package_response.json()
    assert package["session_id"] == session_id
    assert package["capstone_project"]["deliverables"]
    assert "course_metadata" in package
    assert package["learning_report"]["behavior_summary"]["event_count"] >= timeline["summary"]["event_count"]
    assert package["learning_report"]["effect_assessment"]["dimensions"]
    assert "mistake_summary" in package["learning_report"]
    assert package["learning_report"]["demo_readiness"]["checks"]
    assert package["rubric"]
    assert package["demo_blueprint"]["storyline"]
    assert package["demo_blueprint"]["judge_mapping"]
    assert package["demo_fallback_kit"]["assets"]
    assert package["demo_fallback_kit"]["checklist"]
    assert package["demo_seed_pack"]["task_chain"]

    resource_recommendations_response = client.get(
        f"/api/v1/guide/v2/sessions/{session_id}/resource-recommendations"
    )
    assert resource_recommendations_response.status_code == 200
    resource_recommendations = resource_recommendations_response.json()
    assert resource_recommendations["session_id"] == session_id
    assert resource_recommendations["effect_assessment"]["dimensions"]
    assert isinstance(resource_recommendations["recommendations"], list)
    assert resource_recommendations["recommendations"][0]["target_task_id"]

    job_response = client.post(
        f"/api/v1/guide/v2/sessions/{session_id}/tasks/{task_id}/resources/jobs",
        json={"resource_type": "visual", "prompt": "做成图解"},
    )
    assert job_response.status_code == 200
    job_id = job_response.json()["task_id"]
    events_response = client.get(f"/api/v1/guide/v2/resource-jobs/{job_id}/events")
    assert events_response.status_code == 200
    assert "event: complete" in events_response.text
    assert "event: result" in events_response.text

    complete_response = client.post(
        f"/api/v1/guide/v2/sessions/{session_id}/tasks/{task_id}/complete",
        json={"score": 0.85, "reflection": "我理解了核心概念。"},
    )
    assert complete_response.status_code == 200
    completed = complete_response.json()
    assert completed["completed_task"]["status"] == "completed"
    assert completed["session"]["progress"] > 0
    assert completed["learning_feedback"]["summary"]
    assert completed["learning_feedback"]["evidence_quality"]["label"]
    assert completed["evidence"]["metadata"]["learning_feedback"]["summary"]

    refresh_response = client.post(f"/api/v1/guide/v2/sessions/{session_id}/recommendations/refresh")
    assert refresh_response.status_code == 200
    assert refresh_response.json()["recommendations"]

    delete_response = client.delete(f"/api/v1/guide/v2/sessions/{session_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["success"] is True


def test_guide_v2_router_rejects_empty_goal(tmp_path, monkeypatch) -> None:
    manager = GuideV2Manager(output_dir=tmp_path)
    client = _client_with_manager(manager, monkeypatch)

    response = client.post("/api/v1/guide/v2/sessions", json={"goal": "  "})

    assert response.status_code == 400


def test_guide_v2_router_lists_sessions(tmp_path, monkeypatch) -> None:
    manager = GuideV2Manager(output_dir=tmp_path)

    async def _create() -> None:
        await manager.create_session(GuideV2CreateInput(goal="学习卷积神经网络"))

    import asyncio

    asyncio.run(_create())
    client = _client_with_manager(manager, monkeypatch)

    response = client.get("/api/v1/guide/v2/sessions")

    assert response.status_code == 200
    assert response.json()["sessions"][0]["goal"] == "学习卷积神经网络"
