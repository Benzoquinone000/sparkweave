from __future__ import annotations

from typing import Any

import pytest

import sparkweave.services.question_generation as question_generation


class _FakeQuestionGraph:
    async def run(self, context, stream):  # noqa: ANN001
        assert context.active_capability == "deep_question"
        await stream.progress(
            "Generating...",
            source="deep_question",
            stage="generation",
            metadata={"trace_kind": "call_status"},
        )
        await stream.result(
            {
                "summary": {
                    "success": True,
                    "requested": context.config_overrides.get("num_questions")
                    or context.config_overrides.get("max_questions"),
                    "template_count": 1,
                    "completed": 1,
                    "failed": 0,
                    "results": [
                        {
                            "success": True,
                            "qa_pair": {
                                "question": "What is 2+2?",
                                "correct_answer": "4",
                            },
                        }
                    ],
                    "runtime": "langgraph",
                }
            },
            source="deep_question",
        )
        return {}


@pytest.mark.asyncio
async def test_agent_coordinator_uses_ng_question_graph(monkeypatch):
    events: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []

    monkeypatch.setattr(question_generation, "DeepQuestionGraph", _FakeQuestionGraph)

    coordinator = question_generation.AgentCoordinator(kb_name="demo", language="zh")
    coordinator.set_ws_callback(lambda update: events.append(update))
    coordinator.set_trace_callback(lambda update: traces.append(update))

    summary = await coordinator.generate_from_topic(
        user_topic="linear algebra",
        preference="concise",
        num_questions=1,
        difficulty="medium",
        question_type="written",
    )

    assert summary["success"] is True
    assert summary["runtime"] == "langgraph"
    assert events[0]["type"] == "progress"
    assert events[0]["stage"] == "generation"
    assert traces[0]["event"] == "llm_call"
    assert traces[0]["phase"] == "generation"
    assert traces[0]["trace_kind"] == "call_status"


@pytest.mark.asyncio
async def test_mimic_exam_questions_wraps_ng_summary(monkeypatch, tmp_path):
    sent: list[tuple[str, dict[str, Any]]] = []
    paper_dir = tmp_path / "paper"
    paper_dir.mkdir()

    monkeypatch.setattr(question_generation, "DeepQuestionGraph", _FakeQuestionGraph)

    result = await question_generation.mimic_exam_questions(
        paper_dir=str(paper_dir),
        kb_name="demo",
        output_dir=str(tmp_path / "out"),
        max_questions=1,
        ws_callback=lambda event_type, data: sent.append((event_type, data)),
    )

    assert result["success"] is True
    assert result["total_reference_questions"] == 1
    assert result["generated_questions"][0]["question"] == "What is 2+2?"
    assert sent[0][0] == "progress"

