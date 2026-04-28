from __future__ import annotations

import json
from typing import Any

import pytest

from sparkweave.core.contracts import StreamBus, StreamEventType, UnifiedContext
from sparkweave.graphs.math_animator import MathAnimatorGraph


class FakeModel:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)

    async def ainvoke(self, _messages: Any) -> Any:
        from langchain_core.messages import AIMessage

        return AIMessage(content=self.responses.pop(0))


class FakeRenderer:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def render(self, **kwargs: Any) -> tuple[str, dict[str, Any]]:
        self.calls.append(kwargs)
        return kwargs["code"], {
            "output_mode": kwargs["output_mode"],
            "artifacts": [
                {
                    "type": "video",
                    "url": "/api/outputs/agent/math_animator/turn_1/artifacts/video.mp4",
                    "filename": "video.mp4",
                    "content_type": "video/mp4",
                    "label": "Animation video",
                }
            ],
            "source_code_path": "/tmp/scene.py",
            "quality": kwargs["quality"],
            "retry_attempts": 1,
            "retry_history": [{"attempt": 1, "error": "boom"}],
            "visual_review": None,
        }


@pytest.mark.asyncio
async def test_math_animator_graph_emits_summary_and_result() -> None:
    code = "from manim import *\n\nclass MainScene(Scene):\n    pass\n"
    renderer = FakeRenderer()
    graph = MathAnimatorGraph(
        model=FakeModel(
            [
                json.dumps(
                    {
                        "learning_goal": "teach parabola",
                        "math_focus": ["quadratic functions"],
                        "visual_targets": ["parabola"],
                        "narrative_steps": ["show curve"],
                        "reference_usage": "",
                        "output_intent": "video",
                    }
                ),
                json.dumps(
                    {
                        "title": "Parabola animation",
                        "scene_outline": ["Draw a curve"],
                        "visual_style": "clean",
                        "animation_notes": ["show vertex"],
                        "image_plan": [],
                        "code_constraints": ["define MainScene"],
                    }
                ),
                json.dumps({"code": code, "rationale": "Simple Manim scene."}),
                json.dumps(
                    {
                        "summary_text": "Generated a parabola animation.",
                        "user_request": "Explain parabolas",
                        "generated_output": "video",
                        "key_points": ["parabola"],
                    }
                ),
            ]
        ),
        renderer=renderer,
    )
    bus = StreamBus()
    context = UnifiedContext(
        session_id="session_1",
        user_message="Explain parabolas",
        active_capability="math_animator",
        language="en",
        config_overrides={"output_mode": "video", "quality": "medium"},
        metadata={
            "turn_id": "turn_1",
            "conversation_context_text": "Earlier we discussed function graphs.",
        },
    )

    state = await graph.run(context, bus)

    assert [event.stage for event in bus._history if event.type == StreamEventType.STAGE_START] == [
        "concept_analysis",
        "concept_design",
        "code_generation",
        "code_retry",
        "summary",
        "render_output",
    ]
    assert renderer.calls[0]["turn_id"] == "turn_1"
    assert state["math_summary"]["summary_text"] == "Generated a parabola animation."
    content_event = next(event for event in bus._history if event.type == StreamEventType.CONTENT)
    assert "parabola animation" in content_event.content
    result_event = next(event for event in bus._history if event.type == StreamEventType.RESULT)
    assert result_event.metadata["output_mode"] == "video"
    assert result_event.metadata["code"]["language"] == "python"
    assert result_event.metadata["artifacts"][0]["filename"] == "video.mp4"

