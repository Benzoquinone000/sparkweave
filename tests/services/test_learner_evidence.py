from __future__ import annotations

from sparkweave.services.learner_evidence import (
    LearnerEvidenceService,
    build_chat_statement_events,
    build_guide_resource_event,
    build_notebook_record_event,
    build_profile_calibration_event,
    build_quiz_answer_events,
)


def test_learner_evidence_appends_lists_and_summarizes(tmp_path) -> None:
    service = LearnerEvidenceService(output_dir=tmp_path)

    first = service.append_event(
        {
            "source": "question_notebook",
            "verb": "answered",
            "object_type": "quiz",
            "object_id": "gradient_descent",
            "title": "学习率过大可能发生什么？",
            "score": 0,
            "is_correct": False,
            "mistake_types": ["学习率判断错误"],
            "created_at": 1_777_000_000,
        }
    )
    service.append_event(
        {
            "source": "guide",
            "verb": "completed",
            "object_type": "guide_task",
            "title": "看图理解梯度方向",
            "score": 0.9,
            "created_at": 1_777_000_100,
        }
    )

    assert first["source"] == "question_notebook"
    listing = service.list_events(limit=10)
    assert listing["total"] == 2
    assert listing["items"][0]["source"] == "guide"
    assert listing["summary"]["average_score"] == 0.45
    assert listing["summary"]["accuracy"] == 0
    assert service.ledger_path.exists()


def test_learner_evidence_rebuild_from_profile_dedupes(tmp_path) -> None:
    service = LearnerEvidenceService(output_dir=tmp_path)
    profile = {
        "evidence_preview": [
            {
                "evidence_id": "q1",
                "source_id": "question_notebook",
                "source_label": "题目本",
                "title": "题目记录",
                "summary": "回答错误",
                "score": 0,
                "metadata": {"question_type": "choice"},
            }
        ]
    }

    first = service.rebuild_from_profile(profile)
    second = service.rebuild_from_profile(profile)

    assert first["added"] == 1
    assert second["added"] == 0
    assert second["skipped"] == 1
    listing = service.list_events(source="question_notebook")
    assert listing["total"] == 1
    assert listing["items"][0]["object_type"] == "quiz"


def test_learner_evidence_builds_profile_calibration_event(tmp_path) -> None:
    service = LearnerEvidenceService(output_dir=tmp_path)
    event = service.append_event(
        build_profile_calibration_event(
            action="correct",
            claim_type="weak_point",
            value="linear algebra",
            corrected_value="matrix multiplication",
            note="The weak point is more specific.",
        )
    )

    assert event["source"] == "profile_calibration"
    assert event["verb"] == "corrected_profile"
    assert event["object_type"] == "profile_claim"
    assert event["metadata"]["claim_type"] == "weak_point"
    assert event["metadata"]["corrected_value"] == "matrix multiplication"


def test_learner_evidence_builds_quiz_answer_events_with_concepts() -> None:
    events = build_quiz_answer_events(
        [
            {
                "question_id": "q1",
                "question": "What happens if the learning rate is too large?",
                "question_type": "choice",
                "difficulty": "easy",
                "is_correct": False,
                "user_answer": "It always converges faster.",
                "correct_answer": "It may oscillate or diverge.",
                "concepts": ["gradient descent", "learning rate"],
                "duration_seconds": 42,
                "attempt_count": 2,
            }
        ],
        source="guide_v2",
        session_id="session_1",
        task_id="task_1",
        artifact_id="artifact_1",
    )

    event = events[0]

    assert event["object_id"] == "gradient_descent"
    assert event["duration_seconds"] == 42.0
    assert event["metadata"]["question_id"] == "q1"
    assert event["metadata"]["concepts"] == ["gradient descent", "learning rate"]
    assert event["metadata"]["duration_seconds"] == 42.0
    assert event["metadata"]["attempt_count"] == 2
    assert event["metadata"]["primary_concept"] == "gradient descent"
    assert "concept:gradient descent" in event["mistake_types"]


def test_learner_evidence_builds_chat_statement_events() -> None:
    events = build_chat_statement_events(
        "我想掌握梯度下降，但不理解公式含义，更喜欢图解和短视频。",
        session_id="chat_1",
        turn_id="turn_1",
        capability="chat",
        language="zh",
    )

    object_types = {event["object_type"] for event in events}
    resource_types = {event.get("resource_type") for event in events if event.get("resource_type")}
    assert "learning_goal" in object_types
    assert "learning_blocker" in object_types
    assert {"visual", "video"}.issubset(resource_types)
    assert all(event["source"] == "chat" for event in events)


def test_learner_evidence_infers_preference_from_requested_capability() -> None:
    events = build_chat_statement_events(
        "请给我找几个梯度下降的公开课视频。",
        session_id="chat_1",
        turn_id="turn_2",
        capability="external_video_search",
        language="zh",
    )

    inferred = [
        event
        for event in events
        if event.get("metadata", {}).get("inference") == "capability_usage"
    ]

    assert len(inferred) == 1
    assert inferred[0]["verb"] == "requested"
    assert inferred[0]["object_type"] == "learning_preference"
    assert inferred[0]["resource_type"] == "external_video"
    assert inferred[0]["metadata"]["capability"] == "external_video_search"


def test_notebook_record_event_infers_saved_external_video_resource() -> None:
    event = build_notebook_record_event(
        record={
            "id": "rec-video",
            "type": "chat",
            "title": "Gradient descent videos",
            "summary": "Two curated public videos.",
            "metadata": {
                "source": "chat",
                "external_video": {
                    "render_type": "external_video",
                    "videos": [{"title": "Gradient descent", "url": "https://example.com/video"}],
                },
            },
        },
        notebook_ids=["nb1"],
    )

    assert event["source"] == "chat"
    assert event["verb"] == "saved"
    assert event["object_type"] == "resource"
    assert event["resource_type"] == "external_video"
    assert event["metadata"]["record_type"] == "chat"
    assert event["metadata"]["record_object_type"] == "notebook_record"
    assert event["metadata"]["inferred_resource_type"] == "external_video"


def test_notebook_record_event_treats_plain_chat_save_as_note_resource() -> None:
    event = build_notebook_record_event(
        record={
            "id": "rec-note",
            "type": "chat",
            "title": "Learning reflection",
            "summary": "Saved a useful explanation for later review.",
            "metadata": {"source": "chat"},
        },
        notebook_ids=["nb1"],
    )

    assert event["verb"] == "saved"
    assert event["object_type"] == "resource"
    assert event["resource_type"] == "note"
    assert event["metadata"]["record_type"] == "chat"
    assert event["metadata"]["record_object_type"] == "notebook_record"


def test_notebook_record_event_infers_saved_audio_resource() -> None:
    event = build_notebook_record_event(
        record={
            "id": "rec-audio",
            "type": "guided_learning",
            "title": "Narrated review",
            "metadata": {
                "source": "guide_v2",
                "artifact_type": "audio",
                "audio_narration": {
                    "audio": {"asset_url": "/api/v1/guide/v2/sessions/s1/tasks/t1/artifacts/a1/asset"}
                },
            },
        },
        notebook_ids=["nb-audio"],
    )

    assert event["object_type"] == "resource"
    assert event["resource_type"] == "audio"
    assert event["metadata"]["inferred_resource_type"] == "audio"


def test_learner_evidence_builds_guide_resource_event() -> None:
    event = build_guide_resource_event(
        session_id="guide-session",
        task={
            "task_id": "task-1",
            "node_id": "node-1",
            "title": "Gradient descent intuition",
            "instruction": "Build intuition first.",
        },
        artifact={
            "id": "artifact-1",
            "type": "external_video",
            "capability": "external_video_search",
            "title": "Curated videos: Gradient descent intuition",
            "created_at": 1_777_000_000,
            "status": "ready",
            "result": {
                "response": "Three public videos selected.",
                "videos": [{"title": "Gradient descent", "url": "https://example.com/video"}],
            },
        },
        session_goal="Learn gradient descent",
    )

    assert event["verb"] == "generated"
    assert event["object_type"] == "resource"
    assert event["resource_type"] == "external_video"
    assert event["metadata"]["capability"] == "external_video_search"
    assert event["metadata"]["video_count"] == 1
