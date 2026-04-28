from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from sparkweave.core.contracts import Attachment, StreamBus, StreamEventType, UnifiedContext
from sparkweave.graphs.deep_question import DeepQuestionGraph


class FakeModel:
    def __init__(self, responses):
        self.responses = list(responses)

    async def ainvoke(self, _messages):
        from langchain_core.messages import AIMessage

        return AIMessage(content=self.responses.pop(0))


class FakeToolRegistry:
    def names(self):
        return []


@pytest.mark.asyncio
async def test_deep_question_graph_generates_custom_quiz_summary():
    bus = StreamBus()
    graph = DeepQuestionGraph(
        model=FakeModel(
            [
                '{"templates":[{"concentration":"eigenvalue definition","question_type":"written","difficulty":"medium","rationale":"core concept"}]}',
                '{"question_type":"written","question":"Define an eigenvalue in the equation Av = lambda v.","options":null,"correct_answer":"lambda is an eigenvalue when a nonzero vector v satisfies Av = lambda v.","explanation":"The definition requires a scalar and a nonzero eigenvector."}',
            ]
        ),
        tool_registry=FakeToolRegistry(),
    )
    context = UnifiedContext(
        user_message="Linear algebra",
        active_capability="deep_question",
        config_overrides={"num_questions": 1, "question_type": "written"},
    )

    state = await graph.run(context, bus)

    assert state["templates"][0]["question_id"] == "q_1"
    assert state["questions"][0]["qa_pair"]["question_type"] == "written"
    assert state["questions"][0]["qa_pair"]["validation"]["schema_ok"] is True
    result_events = [event for event in bus._history if event.type == StreamEventType.RESULT]
    assert len(result_events) == 1
    summary = result_events[0].metadata["summary"]
    assert summary["results"][0]["qa_pair"]["question"].startswith("Define an eigenvalue")
    assert "### Question 1" in result_events[0].metadata["response"]


@pytest.mark.asyncio
async def test_deep_question_graph_repairs_invalid_non_choice_payload():
    bus = StreamBus()
    graph = DeepQuestionGraph(
        model=FakeModel(
            [
                '{"templates":[{"concentration":"positional bias mitigation","question_type":"coding","difficulty":"hard","rationale":"algorithmic skill"}]}',
                '{"question_type":"coding","question":"Choose the best code for alternating answer order.","options":{"A":"fixed","B":"alternate","C":"always reverse","D":"never change"},"correct_answer":"B","explanation":"B alternates."}',
                '{"question_type":"coding","question":"Write pseudocode that alternates answer order across iterations.","options":null,"correct_answer":"for i in range(n): alternate order based on i % 2","explanation":"Alternation balances positions over repeated evaluations."}',
            ]
        ),
        tool_registry=FakeToolRegistry(),
    )
    context = UnifiedContext(
        user_message="Evaluation bias",
        active_capability="deep_question",
        config_overrides={"num_questions": 1, "question_type": "coding"},
    )

    state = await graph.run(context, bus)

    qa_pair = state["questions"][0]["qa_pair"]
    assert qa_pair["question_type"] == "coding"
    assert qa_pair["options"] is None
    assert qa_pair["validation"]["repaired"] is True
    assert qa_pair["validation"]["schema_ok"] is True
    assert qa_pair["correct_answer"].startswith("for i in range")


@pytest.mark.asyncio
async def test_deep_question_graph_generates_mimic_questions_from_parsed_json(tmp_path):
    paper_dir = tmp_path / "paper"
    paper_dir.mkdir()
    question_file = paper_dir / "demo_questions.json"
    question_file.write_text(
        json.dumps(
            {
                "questions": [
                    {
                        "question_number": "1",
                        "question_text": "Explain why matrix multiplication is not commutative.",
                        "question_type": "written",
                        "answer": "AB and BA can differ.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    bus = StreamBus()
    graph = DeepQuestionGraph(
        model=FakeModel(
            [
                '{"question_type":"written","question":"Give an example showing matrix multiplication can be non-commutative.","options":null,"correct_answer":"Choose A and B such that AB != BA.","explanation":"A counterexample demonstrates the order matters."}',
            ]
        ),
        tool_registry=FakeToolRegistry(),
    )
    context = UnifiedContext(
        user_message="Mimic exam",
        active_capability="deep_question",
        config_overrides={
            "mode": "mimic",
            "paper_path": str(paper_dir),
            "max_questions": 1,
        },
    )

    state = await graph.run(context, bus)

    assert state["templates"][0]["source"] == "mimic"
    assert state["templates"][0]["reference_question"].startswith("Explain why")
    qa_pair = state["questions"][0]["qa_pair"]
    assert qa_pair["question_type"] == "written"
    assert qa_pair["validation"]["schema_ok"] is True
    result_events = [event for event in bus._history if event.type == StreamEventType.RESULT]
    summary = result_events[0].metadata["summary"]
    assert summary["source"] == "exam"
    assert summary["mode"] == "mimic"
    assert summary["trace"]["question_file"].endswith("demo_questions.json")
    assert "### Question 1" in result_events[0].metadata["response"]


@pytest.mark.asyncio
async def test_deep_question_graph_generates_mimic_questions_from_uploaded_pdf(monkeypatch):
    def fake_parse_pdf_with_mineru(pdf_path, output_base_dir=None):
        assert pdf_path.endswith("mock_exam.pdf")
        paper_dir = Path(output_base_dir) / "mock_exam"
        paper_dir.mkdir(parents=True)
        (paper_dir / "mock_exam_questions.json").write_text(
            json.dumps(
                {
                    "questions": [
                        {
                            "question_number": "7",
                            "question_text": "Find the derivative of x squared.",
                            "question_type": "written",
                            "answer": "2x",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        return True

    monkeypatch.setattr(
        "sparkweave.graphs.deep_question.parse_pdf_with_mineru",
        fake_parse_pdf_with_mineru,
    )
    bus = StreamBus()
    graph = DeepQuestionGraph(
        model=FakeModel(
            [
                '{"question_type":"written","question":"Differentiate y = x^2 + 1.","options":null,"correct_answer":"2x","explanation":"The constant differentiates to zero."}',
            ]
        ),
        tool_registry=FakeToolRegistry(),
    )
    pdf_payload = base64.b64encode(b"%PDF-1.4\nmock exam\n%%EOF").decode("ascii")
    context = UnifiedContext(
        user_message="Mimic this uploaded exam",
        active_capability="deep_question",
        attachments=[
            Attachment(
                type="pdf",
                filename="mock_exam.pdf",
                mime_type="application/pdf",
                base64=f"data:application/pdf;base64,{pdf_payload}",
            )
        ],
        config_overrides={
            "mode": "mimic",
            "max_questions": 1,
        },
    )

    state = await graph.run(context, bus)

    assert state["templates"][0]["reference_question"] == "Find the derivative of x squared."
    assert state["templates"][0]["metadata"]["question_number"] == "7"
    result_events = [event for event in bus._history if event.type == StreamEventType.RESULT]
    summary = result_events[0].metadata["summary"]
    assert summary["trace"]["paper_dir"].endswith("mock_exam")
    assert summary["trace"]["question_file"].endswith("mock_exam_questions.json")


@pytest.mark.asyncio
async def test_deep_question_graph_reports_mimic_mode_missing_paper():
    bus = StreamBus()
    graph = DeepQuestionGraph(
        model=FakeModel([]),
        tool_registry=FakeToolRegistry(),
    )
    context = UnifiedContext(
        user_message="Mimic exam",
        active_capability="deep_question",
        config_overrides={"mode": "mimic", "paper_path": ""},
    )

    await graph.run(context, bus)

    error_events = [event for event in bus._history if event.type == StreamEventType.ERROR]
    assert len(error_events) == 1
    assert "requires either an uploaded PDF or a parsed exam directory" in error_events[0].content
    result_events = [event for event in bus._history if event.type == StreamEventType.RESULT]
    assert result_events[0].metadata["summary"]["success"] is False


