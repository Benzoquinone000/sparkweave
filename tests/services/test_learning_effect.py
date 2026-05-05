from __future__ import annotations

from sparkweave.services.learner_evidence import LearnerEvidenceService
from sparkweave.services.learning_effect import LearningEffectService


def test_learning_effect_recommends_diagnostic_without_evidence(tmp_path) -> None:
    service = LearningEffectService(evidence_service=LearnerEvidenceService(output_dir=tmp_path))

    report = service.build_report(window="all")

    assert report["overall"]["label"] == "需要先建立基线"
    assert report["next_actions"][0]["type"] == "diagnostic"
    assert report["next_actions"][0]["capability"] == "deep_question"
    assert report["next_actions"][0]["prompt"]
    assert report["next_actions"][0]["config"]["purpose"] == "diagnostic"
    assert "capability=deep_question" in report["next_actions"][0]["href"]
    assert report["dimensions"][0]["id"] == "mastery"
    assert report["visualization"]["nodes"][0]["id"] == "evidence"
    assert report["visualization"]["summary"]
    assert report["learner_receipt"]["score_label"] == "待建立"
    assert report["learner_receipt"]["action_id"] == report["next_actions"][0]["id"]
    assert report["learner_receipt"]["action_href"] == report["next_actions"][0]["href"]
    assert "profile" in report["learner_receipt"]["writes_back"]


def test_learning_effect_builds_concept_mastery_from_quiz_events(tmp_path) -> None:
    evidence = LearnerEvidenceService(output_dir=tmp_path)
    service = LearningEffectService(evidence_service=evidence)
    evidence.append_event(
        {
            "source": "question_notebook",
            "verb": "answered",
            "object_type": "quiz",
            "object_id": "gradient_descent",
            "title": "学习率过大会发生什么？",
            "score": 0,
            "is_correct": False,
            "mistake_types": ["concept:梯度下降", "学习率判断错误"],
            "metadata": {"concepts": ["梯度下降"], "difficulty": "medium"},
            "created_at": 1_777_000_000,
        }
    )
    evidence.append_event(
        {
            "source": "guide_v2",
            "verb": "answered",
            "object_type": "quiz",
            "object_id": "gradient_descent",
            "title": "负梯度方向表示什么？",
            "score": 0.8,
            "is_correct": True,
            "metadata": {"concepts": ["梯度下降"], "difficulty": "medium"},
            "created_at": 1_777_000_300,
        }
    )

    concepts = service.list_concepts(window="all")["items"]
    concept = next(item for item in concepts if item["concept_id"] == "梯度下降")

    assert concept["evidence_count"] == 2
    assert concept["scored_event_count"] == 2
    assert concept["incorrect_count"] == 1
    assert concept["correct_count"] == 1
    assert concept["status"] in {"needs_support", "practicing"}
    assert concept["trend"] == "flat"

    report = service.build_report(window="all")
    assert report["summary"]["answered_count"] == 2
    assert report["summary"]["accuracy"] == 0.5
    assert any(action["type"] in {"generate_visual", "generate_practice", "mistake_review"} for action in report["next_actions"])
    assert all(action["prompt"] and action["capability"] for action in report["next_actions"])
    assert any(action["capability"] == "visualize" for action in report["next_actions"])
    assert any(action["capability"] == "deep_question" for action in report["next_actions"])
    assert report["visualization"]["nodes"][1]["id"] == "assessment"
    assert report["visualization"]["edges"][0]["from"] == "evidence"
    assert report["visualization"]["evidence_timeline"][0]["kind"] == "quiz"
    assert report["visualization"]["dimension_bars"][0]["id"] == "mastery"
    assert report["learner_receipt"]["score"] == report["overall"]["score"]
    assert report["learner_receipt"]["focus_concepts"]
    assert report["learner_receipt"]["next_step"]
    assert report["learner_receipt"]["profile_update"]

    demo = service.demo_summary(window="all")
    assert demo["headline"]
    assert demo["primary_action"]["title"]
    assert demo["proof_points"][0]["label"] == "证据"
    assert any(item["requirement"] == "学习效果评估" for item in demo["requirement_alignment"])
    assert "学习效果评估闭环摘要" in demo["markdown"]
    assert "答辩讲法" in demo["markdown"]


def test_learning_effect_tracks_trend_and_completion_action(tmp_path) -> None:
    evidence = LearnerEvidenceService(output_dir=tmp_path)
    service = LearningEffectService(evidence_service=evidence)
    for index, score in enumerate([0.1, 0.2, 0.9, 1.0], 1):
        evidence.append_event(
            {
                "id": f"ev_{index}",
                "source": "guide_v2",
                "verb": "answered",
                "object_type": "quiz",
                "object_id": "loss_function",
                "title": "损失函数练习",
                "score": score,
                "is_correct": score > 0.5,
                "metadata": {"concepts": ["损失函数"]},
                "created_at": 1_777_000_000 + index,
            }
        )

    concepts = service.list_concepts(window="all")["items"]
    concept = next(item for item in concepts if item["concept_id"] == "损失函数")
    assert concept["trend"] == "up"

    result = service.complete_action(
        "nba_retest_loss_function",
        note="复测完成",
        score=0.9,
        concept_ids=["损失函数"],
    )
    assert result["event"]["source"] == "learning_effect"
    assert result["report"]["success"] is True


def test_learning_effect_counts_saved_notebook_resources(tmp_path) -> None:
    evidence = LearnerEvidenceService(output_dir=tmp_path)
    service = LearningEffectService(evidence_service=evidence)
    evidence.append_event(
        {
            "source": "chat",
            "verb": "saved",
            "object_type": "resource",
            "object_id": "rec-note",
            "title": "Gradient descent note",
            "summary": "Saved a concise explanation.",
            "resource_type": "note",
            "metadata": {"concepts": ["gradient descent"], "record_object_type": "notebook_record"},
            "created_at": 1_777_000_000,
        }
    )

    report = service.build_report(window="all")

    assert report["summary"]["resource_count"] == 1
    assert report["summary"]["saved_count"] == 1
    engagement = next(item for item in report["dimensions"] if item["id"] == "engagement")
    assert engagement["score"] >= 32


def test_learning_effect_tracks_remediation_loop_status(tmp_path) -> None:
    evidence = LearnerEvidenceService(output_dir=tmp_path)
    service = LearningEffectService(evidence_service=evidence)
    evidence.append_event(
        {
            "id": "ev_feedback",
            "source": "guide_v2",
            "verb": "answered",
            "object_type": "quiz",
            "object_id": "labels",
            "title": "Labels quiz",
            "score": 0.2,
            "is_correct": False,
            "metadata": {
                "concepts": ["labels"],
                "learning_feedback": {
                    "remediation_task": {
                        "title": "Fix labels",
                        "concept": "labels",
                        "target_task_id": "task_remediate_labels",
                        "resource_type": "visual",
                        "estimated_minutes": 10,
                    }
                },
            },
            "created_at": 1_777_000_000,
        }
    )
    pending = service.build_report(window="all")["remediation_loop"]
    assert pending["pending_remediation_count"] == 1
    assert pending["items"][0]["status"] == "pending_remediation"
    assert pending["items"][0]["reason"]
    assert "labels" in pending["items"][0]["evidence_summary"]
    assert pending["items"][0]["next_step"]
    assert pending["items"][0]["progress_label"] == "需要先补救"
    assert pending["items"][0]["action_label"] == "开始补救"
    assert pending["items"][0]["action_capability"] == "visualize"
    assert "capability=visualize" in pending["items"][0]["action_href"]
    pending_report = service.build_report(window="all")
    assert pending_report["visualization"]["loop"]["pending"] == 1
    assert pending_report["visualization"]["weak_points"]

    evidence.append_event(
        {
            "id": "ev_completed",
            "source": "guide_v2",
            "verb": "completed",
            "object_type": "guide_task",
            "object_id": "task_remediate_labels",
            "task_id": "task_remediate_labels",
            "metadata": {"concepts": ["labels"]},
            "created_at": 1_777_000_100,
        }
    )
    ready = service.build_report(window="all")["remediation_loop"]
    assert ready["ready_for_retest_count"] == 1
    assert ready["items"][0]["status"] == "ready_for_retest"
    assert ready["items"][0]["progress_label"] == "补救完成，等待复测"
    assert "复测" in ready["items"][0]["next_step"]
    assert ready["items"][0]["completed_at"]
    assert ready["items"][0]["action_label"] == "去复测"
    assert ready["items"][0]["action_config"]["purpose"] == "retest"
    assert ready["items"][0]["action_capability"] == "deep_question"

    evidence.append_event(
        {
            "id": "ev_retest",
            "source": "guide_v2",
            "verb": "answered",
            "object_type": "quiz",
            "object_id": "labels",
            "title": "Labels retest",
            "score": 1,
            "is_correct": True,
            "metadata": {"concepts": ["labels"]},
            "created_at": 1_777_000_200,
        }
    )
    closed = service.build_report(window="all")["remediation_loop"]
    assert closed["closed_count"] == 1
    assert closed["items"][0]["status"] == "closed"
    assert closed["items"][0]["progress_label"] == "已完成补救和复测"
    assert "复测通过" in closed["items"][0]["evidence_summary"]
    assert closed["items"][0]["closed_at"]
    assert closed["items"][0]["action_label"] == "安排复习"
    assert closed["items"][0]["action_config"]["purpose"] == "spaced_review"
