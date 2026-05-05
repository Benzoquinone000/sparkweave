from __future__ import annotations

import json

import pytest

from sparkweave.core.contracts import StreamBus, StreamEventType, UnifiedContext
from sparkweave.graphs.chat import ChatGraph
from sparkweave.graphs.deep_question import DeepQuestionGraph
from sparkweave.graphs.deep_research import DeepResearchGraph
from sparkweave.graphs.deep_solve import DeepSolveGraph
from sparkweave.graphs.math_animator import MathAnimatorGraph
from sparkweave.graphs.visualize import VisualizeGraph


@pytest.fixture(autouse=True)
def _disable_math_animator_tts(monkeypatch):
    monkeypatch.setattr(
        "sparkweave.graphs.math_animator.is_iflytek_tts_configured",
        lambda: False,
    )


class FakeModel:
    def __init__(self, responses):
        self.responses = list(responses)

    async def ainvoke(self, _messages):
        from langchain_core.messages import AIMessage

        return AIMessage(content=self.responses.pop(0))


class EmptyToolRegistry:
    def names(self):
        return []


class FakeMathRenderer:
    def __init__(self):
        self.calls = []

    async def render(self, **kwargs):
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


def _context(capability: str, *, config: dict | None = None) -> UnifiedContext:
    return UnifiedContext(
        session_id="session-1",
        user_message="Answer now",
        active_capability=capability,
        config_overrides={
            **(config or {}),
            "answer_now_context": {
                "original_user_message": "Explain Fourier transform",
                "partial_response": "We have a partial explanation.",
                "events": [
                    {
                        "type": "thinking",
                        "stage": "planning",
                        "content": "Use frequency-domain intuition.",
                    }
                ],
            },
        },
        metadata={"turn_id": "turn-1"},
    )


def _result(bus: StreamBus):
    results = [event for event in bus._history if event.type == StreamEventType.RESULT]
    assert len(results) == 1
    return results[0].metadata


@pytest.mark.asyncio
async def test_chat_graph_answer_now_synthesizes_without_tools():
    bus = StreamBus()
    graph = ChatGraph(model=FakeModel(["Final chat answer."]), tool_registry=EmptyToolRegistry())

    state = await graph.run(_context("chat"), bus)

    assert state["final_answer"] == "Final chat answer."
    metadata = _result(bus)
    assert metadata["metadata"]["answer_now"] is True
    assert not any(event.stage == "acting" for event in bus._history)


@pytest.mark.asyncio
async def test_deep_solve_answer_now_jumps_to_writing():
    bus = StreamBus()
    graph = DeepSolveGraph(
        model=FakeModel(["A Fourier transform decomposes a signal into frequencies."]),
        tool_registry=EmptyToolRegistry(),
    )

    state = await graph.run(_context("deep_solve"), bus)

    assert "decomposes" in state["final_answer"]
    metadata = _result(bus)
    assert metadata["metadata"]["answer_now"] is True
    assert metadata["runtime"] == "langgraph"
    assert not any(event.stage == "planning" for event in bus._history)


@pytest.mark.asyncio
async def test_deep_question_answer_now_emits_quiz_envelope():
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
        _context("deep_question", config={"num_questions": 1, "question_type": "choice"}),
        bus,
    )

    assert state["questions"][0]["qa_pair"]["question_type"] == "choice"
    metadata = _result(bus)
    assert metadata["mode"] == "answer_now"
    assert metadata["metadata"]["answer_now"] is True
    assert metadata["summary"]["results"][0]["qa_pair"]["options"]["A"] == "Frequencies"
    assert not any(event.stage == "ideation" for event in bus._history)


@pytest.mark.asyncio
async def test_deep_research_answer_now_emits_report_envelope():
    bus = StreamBus()
    graph = DeepResearchGraph(
        model=FakeModel(["# Fourier Transform\n\nIt maps signals into frequency space."]),
        tool_registry=EmptyToolRegistry(),
    )

    state = await graph.run(_context("deep_research"), bus)

    assert state["final_answer"].startswith("> Skipped")
    metadata = _result(bus)
    assert metadata["metadata"]["answer_now"] is True
    assert metadata["runtime"] == "langgraph"
    assert not any(event.stage == "researching" for event in bus._history)


@pytest.mark.asyncio
async def test_visualize_answer_now_emits_viewer_payload():
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

    state = await graph.run(_context("visualize", config={"render_mode": "svg"}), bus)

    assert state["visualization_analysis"]["render_type"] == "svg"
    metadata = _result(bus)
    assert metadata["metadata"]["answer_now"] is True
    assert metadata["code"]["language"] == "svg"
    assert "<svg" in metadata["code"]["content"]
    assert not any(event.stage == "analyzing" for event in bus._history)


@pytest.mark.asyncio
async def test_math_animator_answer_now_keeps_codegen_and_render_only():
    code = "from manim import *\n\nclass MainScene(Scene):\n    def construct(self):\n        self.wait(1)\n"
    renderer = FakeMathRenderer()
    bus = StreamBus()
    graph = MathAnimatorGraph(
        model=FakeModel([json.dumps({"code": code, "rationale": "short scene"})]),
        renderer=renderer,
    )

    state = await graph.run(_context("math_animator"), bus)

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


