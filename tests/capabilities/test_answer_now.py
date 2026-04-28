"""Answer-now contract tests for NG LangGraph capabilities."""

from __future__ import annotations

import json
from typing import Any

import pytest

from sparkweave.core.contracts import StreamBus, StreamEventType, UnifiedContext
from sparkweave.graphs._answer_now import (
    extract_answer_now_context,
    format_trace_summary,
    join_chunks,
    labeled_block,
    make_skip_notice,
)
from sparkweave.graphs.chat import ChatGraph
from sparkweave.graphs.deep_question import DeepQuestionGraph
from sparkweave.graphs.deep_research import DeepResearchGraph
from sparkweave.graphs.deep_solve import DeepSolveGraph
from sparkweave.graphs.math_animator import MathAnimatorGraph
from sparkweave.graphs.visualize import VisualizeGraph


class FakeModel:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)

    async def ainvoke(self, _messages: Any) -> Any:
        from langchain_core.messages import AIMessage

        return AIMessage(content=self.responses.pop(0))


class EmptyToolRegistry:
    def names(self) -> list[str]:
        return []

    def get_tools(self, _names: list[str] | None = None) -> list[Any]:
        return []


class FakeMathRenderer:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def render(self, **kwargs: Any) -> tuple[str, dict[str, Any]]:
        self.calls.append(kwargs)
        return kwargs["code"], {
            "output_mode": kwargs["output_mode"],
            "artifacts": [],
            "source_code_path": "workspace/chat/math_animator/turn-1/source/scene.py",
            "quality": kwargs["quality"],
            "retry_attempts": 0,
            "retry_history": [],
            "visual_review": None,
        }


def _context(
    capability: str,
    *,
    payload: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> UnifiedContext:
    overrides = dict(config or {})
    if payload is not None:
        overrides["answer_now_context"] = payload
    return UnifiedContext(
        session_id="session-1",
        user_message="Answer now",
        active_capability=capability,
        config_overrides=overrides,
        metadata={"turn_id": "turn-1"},
    )


def _answer_now_payload() -> dict[str, Any]:
    return {
        "original_user_message": "Explain Fourier transform",
        "partial_response": "We have a partial explanation.",
        "events": [
            {
                "type": "thinking",
                "stage": "planning",
                "content": "Use frequency-domain intuition.",
            }
        ],
    }


def _result(bus: StreamBus) -> dict[str, Any]:
    results = [event for event in bus._history if event.type == StreamEventType.RESULT]
    assert len(results) == 1
    return results[0].metadata


def _content(bus: StreamBus) -> str:
    return "".join(
        event.content for event in bus._history if event.type == StreamEventType.CONTENT
    )


class TestAnswerNowHelpers:
    def test_extracts_payload_when_present(self) -> None:
        ctx = _context("chat", payload={"original_user_message": "hi", "events": []})
        assert extract_answer_now_context(ctx) == {
            "original_user_message": "hi",
            "events": [],
        }

    def test_rejects_missing_or_invalid_payload(self) -> None:
        assert extract_answer_now_context(_context("chat")) is None
        assert (
            extract_answer_now_context(
                _context("chat", config={"answer_now_context": "not-a-dict"})
            )
            is None
        )
        assert (
            extract_answer_now_context(
                _context("chat", payload={"original_user_message": "   "})
            )
            is None
        )

    def test_trace_summary_formats_and_truncates_events(self) -> None:
        out = format_trace_summary(
            [
                {
                    "type": "tool_call",
                    "stage": "acting",
                    "content": "rag.query",
                    "metadata": {"tool_name": "rag"},
                },
                {"type": "thinking", "stage": "planning", "content": "x" * 5000},
            ],
            language="en",
        )

        assert "1. tool_call / acting" in out
        assert "rag.query" in out
        assert "[tool=rag]" in out
        assert len(out) < 1100

    def test_trace_summary_fallbacks_and_skips_non_dict_entries(self) -> None:
        assert "No intermediate" in format_trace_summary([], language="en")
        assert "No intermediate" in format_trace_summary("nope", language="en")
        out = format_trace_summary(["bad", {"type": "thinking", "content": "good"}])
        assert "good" in out
        assert "bad" not in out

    def test_skip_notice_and_labeled_block(self) -> None:
        assert make_skip_notice(capability="chat", stages_skipped=[]) == ""
        notice = make_skip_notice(
            capability="deep_solve",
            stages_skipped=["planning", "reasoning"],
        )
        assert "planning, reasoning" in notice
        assert "`deep_solve`" in notice
        assert labeled_block("X", "hello") == "[X]\nhello"
        assert labeled_block("X", "   ") == "[X]\n(empty)"

    def test_join_chunks_strips_thinking_tags(self) -> None:
        assert join_chunks(["<think>private</think>", "Answer."]) == "Answer."


@pytest.mark.asyncio
async def test_chat_answer_now_synthesizes_without_tools() -> None:
    bus = StreamBus()
    graph = ChatGraph(model=FakeModel(["Final chat answer."]), tool_registry=EmptyToolRegistry())

    state = await graph.run(_context("chat", payload=_answer_now_payload()), bus)

    assert state["final_answer"] == "Final chat answer."
    assert "Final chat answer." in _content(bus)
    assert _result(bus)["metadata"]["answer_now"] is True
    assert not any(event.stage == "acting" for event in bus._history)


@pytest.mark.asyncio
async def test_deep_solve_answer_now_jumps_to_writing() -> None:
    bus = StreamBus()
    graph = DeepSolveGraph(
        model=FakeModel(["A Fourier transform decomposes a signal into frequencies."]),
        tool_registry=EmptyToolRegistry(),
    )

    state = await graph.run(_context("deep_solve", payload=_answer_now_payload()), bus)

    assert "decomposes" in state["final_answer"]
    assert "Skipped" in _content(bus)
    metadata = _result(bus)
    assert metadata["metadata"]["answer_now"] is True
    assert metadata["runtime"] == "langgraph"
    assert not any(event.stage == "planning" for event in bus._history)


@pytest.mark.asyncio
async def test_deep_question_answer_now_emits_quiz_envelope() -> None:
    payload = {
        "questions": [
            {
                "question_id": "q_1",
                "question": "What does a Fourier transform reveal?",
                "question_type": "choice",
                "options": {"A": "Frequencies", "B": "Colors", "C": "Mass", "D": "Charge"},
                "correct_answer": "A",
                "explanation": "It represents a signal by frequency components.",
                "difficulty": "easy",
                "concentration": "frequency domain",
            }
        ]
    }
    bus = StreamBus()
    graph = DeepQuestionGraph(
        model=FakeModel([json.dumps(payload)]),
        tool_registry=EmptyToolRegistry(),
    )

    state = await graph.run(
        _context(
            "deep_question",
            payload=_answer_now_payload(),
            config={"num_questions": 1, "question_type": "choice"},
        ),
        bus,
    )

    assert state["questions"][0]["qa_pair"]["question_type"] == "choice"
    metadata = _result(bus)
    assert metadata["mode"] == "answer_now"
    assert metadata["metadata"]["answer_now"] is True
    assert metadata["summary"]["results"][0]["qa_pair"]["options"]["A"] == "Frequencies"
    assert "What does a Fourier transform reveal?" in _content(bus)
    assert not any(event.stage == "ideation" for event in bus._history)


@pytest.mark.asyncio
async def test_deep_question_answer_now_handles_unparseable_json() -> None:
    bus = StreamBus()
    graph = DeepQuestionGraph(
        model=FakeModel(["not json at all"]),
        tool_registry=EmptyToolRegistry(),
    )

    await graph.run(
        _context("deep_question", payload=_answer_now_payload(), config={"num_questions": 1}),
        bus,
    )

    results = _result(bus)["summary"]["results"]
    assert len(results) == 1
    assert results[0]["qa_pair"]["question_type"] == "written"


@pytest.mark.asyncio
async def test_deep_research_answer_now_emits_report_envelope() -> None:
    bus = StreamBus()
    graph = DeepResearchGraph(
        model=FakeModel(["# Fourier Transform\n\nIt maps signals into frequency space."]),
        tool_registry=EmptyToolRegistry(),
    )

    state = await graph.run(_context("deep_research", payload=_answer_now_payload()), bus)

    assert state["final_answer"].startswith("> Skipped")
    metadata = _result(bus)
    assert metadata["metadata"]["answer_now"] is True
    assert metadata["runtime"] == "langgraph"
    assert "# Fourier Transform" in metadata["response"]
    assert not any(event.stage == "researching" for event in bus._history)


@pytest.mark.asyncio
async def test_visualize_answer_now_emits_viewer_payload() -> None:
    bus = StreamBus()
    graph = VisualizeGraph(
        model=FakeModel(
            [
                json.dumps(
                    {
                        "render_type": "svg",
                        "code": "<svg viewBox='0 0 10 10'><circle cx='5' cy='5' r='4'/></svg>",
                    }
                )
            ]
        )
    )

    state = await graph.run(
        _context("visualize", payload=_answer_now_payload(), config={"render_mode": "svg"}),
        bus,
    )

    assert state["visualization_analysis"]["render_type"] == "svg"
    metadata = _result(bus)
    assert metadata["metadata"]["answer_now"] is True
    assert metadata["code"]["language"] == "svg"
    assert "<svg" in metadata["code"]["content"]
    assert "```svg" in _content(bus)
    assert not any(event.stage == "analyzing" for event in bus._history)


@pytest.mark.asyncio
async def test_visualize_answer_now_strips_fenced_json_and_falls_back_to_svg() -> None:
    bus = StreamBus()
    graph = VisualizeGraph(
        model=FakeModel(
            [
                '```json\n{"render_type": "totally-bogus", "code": "graph TD;A-->B"}\n```'
            ]
        )
    )

    await graph.run(_context("visualize", payload=_answer_now_payload()), bus)

    metadata = _result(bus)
    assert metadata["render_type"] == "svg"
    assert "graph TD" in metadata["code"]["content"]


@pytest.mark.asyncio
async def test_math_animator_answer_now_keeps_codegen_and_render_only() -> None:
    code = "from manim import *\n\nclass MainScene(Scene):\n    def construct(self):\n        self.wait(1)\n"
    renderer = FakeMathRenderer()
    bus = StreamBus()
    graph = MathAnimatorGraph(
        model=FakeModel([json.dumps({"code": code, "rationale": "short scene"})]),
        renderer=renderer,
    )

    state = await graph.run(_context("math_animator", payload=_answer_now_payload()), bus)

    assert renderer.calls[0]["output_mode"] == "video"
    assert state["math_summary"]["answer_now"] is True
    metadata = _result(bus)
    assert metadata["metadata"]["answer_now"] is True
    assert metadata["code"]["content"].startswith("from manim")
    stages = [event.stage for event in bus._history if event.type == StreamEventType.STAGE_START]
    assert "code_generation" in stages
    assert "code_retry" in stages
    assert "concept_analysis" not in stages
    assert "concept_design" not in stages


@pytest.mark.asyncio
async def test_deep_solve_without_answer_now_runs_normal_graph() -> None:
    bus = StreamBus()
    graph = DeepSolveGraph(
        model=FakeModel(
            [
                json.dumps({"analysis": "Plan.", "steps": [{"id": "S1", "goal": "Solve"}]}),
                "Draft solution.",
                "Looks correct.",
                "Final solution.",
            ]
        ),
        tool_registry=EmptyToolRegistry(),
    )

    await graph.run(_context("deep_solve"), bus)

    stages = [event.stage for event in bus._history if event.type == StreamEventType.STAGE_START]
    assert "planning" in stages
    assert "writing" in stages
    result = _result(bus)
    assert result["response"] == "Final solution."
    assert "answer_now" not in result.get("metadata", {})

