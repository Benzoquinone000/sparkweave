from __future__ import annotations

import importlib.util
import json
import os
import shutil

import pytest

from sparkweave.core.contracts import StreamBus, StreamEventType, UnifiedContext
from sparkweave.graphs.math_animator import MathAnimatorGraph
from sparkweave.services.paths import PathService


class LiveFakeModel:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def ainvoke(self, messages):
        from langchain_core.messages import AIMessage

        self.calls.append(messages)
        return AIMessage(content=self.responses.pop(0))


def _manim_live_enabled() -> bool:
    return os.getenv("SPARKWEAVE_NG_MANIM_LIVE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _skip_reason() -> str:
    if not _manim_live_enabled():
        return "Set SPARKWEAVE_NG_MANIM_LIVE=1 to run live Manim/FFmpeg render smoke tests."
    if importlib.util.find_spec("manim") is None:
        return "Manim is not importable in this Python environment."
    missing = [name for name in ("ffmpeg", "ffprobe") if shutil.which(name) is None]
    if missing:
        return f"Missing required executable(s): {', '.join(missing)}."
    return ""


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_math_animator_renders_video_and_extracts_review_frames(
    tmp_path,
    monkeypatch,
) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    service = PathService.get_instance()
    monkeypatch.setattr(service, "_project_root", tmp_path)
    monkeypatch.setattr(service, "_user_data_dir", tmp_path / "data" / "user")

    code = """from manim import *

class MainScene(Scene):
    def construct(self):
        title = Text("Derivative").scale(0.8)
        line = NumberLine(x_range=[-2, 2, 1], length=5).next_to(title, DOWN)
        dot = Dot(line.n2p(0), color=YELLOW)
        self.play(Write(title), run_time=0.2)
        self.play(Create(line), FadeIn(dot), run_time=0.3)
        self.wait(0.2)
"""
    model = LiveFakeModel(
        [
            '{"learning_goal":"Show derivative intuition","math_focus":["derivative"],"visual_targets":["number line"],"narrative_steps":["title","line","dot"],"reference_usage":"","output_intent":"video"}',
            '{"title":"Derivative intuition","scene_outline":["Show a title","Draw a number line","Mark a point"],"visual_style":"clean","animation_notes":["short timing"],"image_plan":[],"code_constraints":["avoid LaTeX"]}',
            json.dumps({"code": code, "rationale": "Simple renderable Manim scene."}),
            '{"passed":true,"summary":"Sampled frames are readable.","issues":[],"suggested_fix":"","reviewed_frames":3}',
            '{"summary_text":"Rendered and reviewed a short derivative animation.","user_request":"Show derivative intuition","generated_output":"video","key_points":["reviewed frames"]}',
        ]
    )
    bus = StreamBus()
    graph = MathAnimatorGraph(model=model)
    context = UnifiedContext(
        session_id="session-live-manim",
        user_message="Show derivative intuition with a short animation.",
        active_capability="math_animator",
        config_overrides={
            "output_mode": "video",
            "quality": "low",
            "max_retries": 0,
            "enable_visual_review": True,
        },
        metadata={"turn_id": "turn-live-manim"},
    )

    state = await graph.run(context, bus)

    artifacts = state["math_render"]["artifacts"]
    assert artifacts
    assert artifacts[0]["type"] == "video"
    assert artifacts[0]["filename"].endswith(".mp4")
    assert state["math_render"]["visual_review"]["passed"] is True
    assert state["math_render"]["visual_review"]["reviewed_frames"] == 3

    review_messages = model.calls[3]
    user_content = review_messages[1].content
    assert isinstance(user_content, list)
    assert sum(1 for item in user_content if item["type"] == "image_url") == 3

    review_dir = tmp_path / "data" / "user" / "workspace" / "chat" / "math_animator" / "turn-live-manim" / "review"
    assert len(list(review_dir.glob("review_frame_*.png"))) == 3

    result_event = next(event for event in bus._history if event.type == StreamEventType.RESULT)
    assert result_event.metadata["render"]["visual_review"]["reviewed_frames"] == 3



