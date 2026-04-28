from __future__ import annotations

import pytest

from sparkweave.core.contracts import Attachment, StreamBus, StreamEventType, UnifiedContext
from sparkweave.graphs.math_animator import DefaultMathRenderer, MathAnimatorGraph


class FakeModel:
    def __init__(self, responses):
        self.responses = list(responses)

    async def ainvoke(self, _messages):
        from langchain_core.messages import AIMessage

        return AIMessage(content=self.responses.pop(0))


class FakeRenderer:
    def __init__(self):
        self.calls = []

    async def render(self, **kwargs):
        self.calls.append(kwargs)
        code = kwargs["code"]
        return code, {
            "output_mode": kwargs["output_mode"],
            "artifacts": [
                {
                    "type": "video",
                    "url": "/api/outputs/workspace/chat/math_animator/turn-1/artifacts/video.mp4",
                    "filename": "video.mp4",
                    "content_type": "video/mp4",
                    "label": "Animation video",
                }
            ],
            "source_code_path": "workspace/chat/math_animator/turn-1/source/scene.py",
            "quality": kwargs["quality"],
            "retry_attempts": 0,
            "retry_history": [],
            "visual_review": None,
        }


class ReviewRenderer:
    def __init__(self):
        self.review = None

    async def render(self, **kwargs):
        from sparkweave.services.math_animator_support.models import (
            RenderedArtifact,
            RenderResult,
        )

        code = kwargs["code"]
        render_result = RenderResult(
            output_mode=kwargs["output_mode"],
            artifacts=[
                RenderedArtifact(
                    type="video",
                    url="/api/outputs/workspace/chat/math_animator/turn-frames/artifacts/video.mp4",
                    filename="video.mp4",
                    content_type="video/mp4",
                    label="Animation video",
                )
            ],
            quality=kwargs["quality"],
        )
        self.review = await kwargs["review_callback"](code, render_result)
        return code, {
            **render_result.model_dump(),
            "visual_review": self.review.model_dump(),
        }


def test_math_animator_extracts_code_from_unclosed_json_fence():
    raw = (
        "```json\n"
        "{\n"
        '  "code": "from manim import *\\n\\nclass MainScene(Scene):\\n    def construct(self):\\n        self.wait(1)",\n'
        '  "rationale": "ok"\n'
        "}"
    )

    code = MathAnimatorGraph._extract_generated_code(raw)

    assert code.startswith("from manim import *")
    assert "class MainScene(Scene)" in code
    assert "```json" not in code


def test_math_animator_extracts_python_from_unclosed_python_fence():
    raw = "```python\nfrom manim import *\n\nclass MainScene(Scene):\n    pass\n"

    code = MathAnimatorGraph._extract_generated_code(raw)

    assert code == "from manim import *\n\nclass MainScene(Scene):\n    pass"


@pytest.mark.asyncio
async def test_math_animator_graph_returns_viewer_ready_video_payload():
    renderer = FakeRenderer()
    bus = StreamBus()
    code = "from manim import *\\n\\nclass MainScene(Scene):\\n    def construct(self):\\n        self.wait(1)\\n"
    graph = MathAnimatorGraph(
        model=FakeModel(
            [
                '{"learning_goal":"Explain derivatives visually","math_focus":["derivative"],"visual_targets":["tangent line"],"narrative_steps":["show curve","move tangent"],"reference_usage":"","output_intent":"video"}',
                '{"title":"Derivative as slope","scene_outline":["Draw a curve","Animate a tangent"],"visual_style":"clean","animation_notes":["avoid LaTeX"],"image_plan":[],"code_constraints":["define MainScene"]}',
                '{"code":"' + code + '","rationale":"Simple Manim scene."}',
                '{"summary_text":"Generated a derivative animation.","user_request":"Explain derivatives visually","generated_output":"video","key_points":["tangent line"]}',
            ]
        ),
        renderer=renderer,
    )
    context = UnifiedContext(
        session_id="session-1",
        user_message="Explain derivatives visually",
        active_capability="math_animator",
        config_overrides={"output_mode": "video", "quality": "low"},
        metadata={"turn_id": "turn-1"},
    )

    state = await graph.run(context, bus)

    assert renderer.calls[0]["output_mode"] == "video"
    assert renderer.calls[0]["quality"] == "low"
    assert state["math_analysis"]["learning_goal"] == "Explain derivatives visually"
    assert state["math_render"]["artifacts"][0]["filename"] == "video.mp4"
    result_events = [event for event in bus._history if event.type == StreamEventType.RESULT]
    assert len(result_events) == 1
    metadata = result_events[0].metadata
    assert metadata["output_mode"] == "video"
    assert metadata["code"]["language"] == "python"
    assert metadata["artifacts"][0]["type"] == "video"
    assert metadata["render"]["quality"] == "low"
    assert metadata["summary"]["summary_text"] == "Generated a derivative animation."


@pytest.mark.asyncio
async def test_math_animator_graph_uses_frame_attachments_for_visual_review(monkeypatch):
    class CaptureModel(FakeModel):
        def __init__(self, responses):
            super().__init__(responses)
            self.calls = []

        async def ainvoke(self, messages):
            self.calls.append(messages)
            return await super().ainvoke(messages)

    class FakeVisualReviewService:
        instances = []

        def __init__(self, turn_id, progress_callback=None):
            self.turn_id = turn_id
            self.progress_callback = progress_callback
            self.render_result = None
            self.instances.append(self)

        async def build_attachments(self, render_result):
            self.render_result = render_result
            if self.progress_callback is not None:
                await self.progress_callback("Prepared 2 review frame(s) from rendered video.", True)
            return [
                Attachment(
                    type="image",
                    filename="review_frame_01.png",
                    mime_type="image/png",
                    base64="iVBORw0KGgo=",
                ),
                Attachment(
                    type="image",
                    filename="review_frame_02.png",
                    mime_type="image/png",
                    base64="iVBORw0KGgo=",
                ),
            ]

    monkeypatch.setattr(
        "sparkweave.services.math_animator_support.visual_review.VisualReviewService",
        FakeVisualReviewService,
    )

    renderer = ReviewRenderer()
    model = CaptureModel(
        [
            '{"learning_goal":"Explain derivatives visually","math_focus":["derivative"],"visual_targets":["tangent line"],"narrative_steps":["show curve"],"reference_usage":"","output_intent":"video"}',
            '{"title":"Derivative as slope","scene_outline":["Draw a curve"],"visual_style":"clean","animation_notes":["avoid LaTeX"],"image_plan":[],"code_constraints":["define MainScene"]}',
            '{"code":"from manim import *\\n\\nclass MainScene(Scene):\\n    def construct(self):\\n        self.wait(1)\\n","rationale":"Simple Manim scene."}',
            '{"passed":true,"summary":"Frames are clear.","issues":[],"suggested_fix":"","reviewed_frames":2}',
            '{"summary_text":"Generated a reviewed derivative animation.","user_request":"Explain derivatives visually","generated_output":"video","key_points":["visual review"]}',
        ]
    )
    bus = StreamBus()
    graph = MathAnimatorGraph(model=model, renderer=renderer)
    context = UnifiedContext(
        session_id="session-1",
        user_message="Explain derivatives visually",
        active_capability="math_animator",
        config_overrides={
            "output_mode": "video",
            "quality": "low",
            "enable_visual_review": True,
        },
        metadata={"turn_id": "turn-frames"},
    )

    state = await graph.run(context, bus)

    assert FakeVisualReviewService.instances[0].turn_id == "turn-frames"
    assert FakeVisualReviewService.instances[0].render_result.artifacts[0].filename == "video.mp4"
    assert renderer.review.reviewed_frames == 2
    assert state["math_render"]["visual_review"]["passed"] is True
    assert state["math_render"]["visual_review"]["reviewed_frames"] == 2

    review_messages = model.calls[3]
    user_content = review_messages[1].content
    assert isinstance(user_content, list)
    assert user_content[0]["type"] == "text"
    assert "Number of sampled review frames: 2" in user_content[0]["text"]
    assert user_content[1]["type"] == "image_url"
    assert user_content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert user_content[2]["type"] == "image_url"

    assert any(
        event.type == StreamEventType.PROGRESS
        and "Prepared 2 review frame" in event.content
        for event in bus._history
    )


@pytest.mark.asyncio
async def test_default_math_renderer_returns_code_only_when_manim_is_missing(monkeypatch):
    monkeypatch.setattr(
        "sparkweave.graphs.math_animator.importlib.util.find_spec",
        lambda name: None if name == "manim" else object(),
    )
    monkeypatch.setattr("sparkweave.graphs.math_animator._resolve_manim_python", lambda: None)
    bus = StreamBus()

    code, render = await DefaultMathRenderer().render(
        turn_id="turn-1",
        code="from manim import *\n\nclass MainScene(Scene):\n    pass\n",
        output_mode="image",
        quality="medium",
        stream=bus,
        source="math_animator",
    )

    assert code.startswith("from manim")
    assert render["output_mode"] == "image"
    assert render["artifacts"] == []
    assert render["render_skipped"] is True
    assert render["skip_reason"] == "manim_not_installed"
    assert any(event.type == StreamEventType.PROGRESS for event in bus._history)


@pytest.mark.asyncio
async def test_default_math_renderer_uses_external_manim_python(monkeypatch):
    from sparkweave.services.math_animator_support import renderer as renderer_module
    from sparkweave.services.math_animator_support.models import RenderResult

    external_python = r"C:\Users\hjk\anaconda3\envs\deeptutor\python.exe"
    monkeypatch.setattr(
        "sparkweave.graphs.math_animator.importlib.util.find_spec",
        lambda name: None if name == "manim" else object(),
    )
    monkeypatch.setattr(
        "sparkweave.graphs.math_animator._resolve_manim_python",
        lambda: external_python,
    )

    class FakeManimRenderService:
        instances = []

        def __init__(self, turn_id, progress_callback=None, python_executable=None):
            self.turn_id = turn_id
            self.progress_callback = progress_callback
            self.python_executable = python_executable
            self.instances.append(self)

        async def render(self, *, code: str, output_mode: str, quality: str) -> RenderResult:
            return RenderResult(output_mode=output_mode, artifacts=[], quality=quality)

    monkeypatch.setattr(renderer_module, "ManimRenderService", FakeManimRenderService)

    bus = StreamBus()
    _, render = await DefaultMathRenderer().render(
        turn_id="turn-1",
        code="from manim import *",
        output_mode="video",
        quality="low",
        stream=bus,
        source="math_animator",
    )

    service = FakeManimRenderService.instances[0]
    assert service.python_executable == external_python
    assert render["output_mode"] == "video"
    assert render.get("render_skipped", False) is False
    assert any(
        event.type == StreamEventType.PROGRESS and "external Manim Python" in event.content
        for event in bus._history
    )


@pytest.mark.asyncio
async def test_default_math_renderer_repairs_after_render_failure(monkeypatch):
    from sparkweave.services.math_animator_support import renderer as renderer_module
    from sparkweave.services.math_animator_support.models import GeneratedCode, RenderResult

    monkeypatch.setattr(
        "sparkweave.graphs.math_animator.importlib.util.find_spec",
        lambda name: object() if name == "manim" else None,
    )

    class FakeManimRenderService:
        instances = []

        def __init__(self, turn_id, progress_callback=None):
            self.turn_id = turn_id
            self.progress_callback = progress_callback
            self.codes = []
            self.instances.append(self)

        async def render(self, *, code: str, output_mode: str, quality: str) -> RenderResult:
            self.codes.append(code)
            if len(self.codes) == 1:
                raise renderer_module.ManimRenderError("Generated code failed to render")
            return RenderResult(output_mode=output_mode, artifacts=[], quality=quality)

    monkeypatch.setattr(renderer_module, "ManimRenderService", FakeManimRenderService)

    async def repair_callback(code: str, error_message: str, attempt: int) -> GeneratedCode:
        assert "failed to render" in error_message
        assert attempt == 1
        return GeneratedCode(code=code + "\n# repaired", rationale="fixed")

    bus = StreamBus()
    final_code, render = await DefaultMathRenderer().render(
        turn_id="turn-1",
        code="from manim import *",
        output_mode="video",
        quality="medium",
        stream=bus,
        source="math_animator",
        repair_callback=repair_callback,
        max_retries=2,
    )

    service = FakeManimRenderService.instances[0]
    assert service.codes == ["from manim import *", "from manim import *\n# repaired"]
    assert final_code.endswith("# repaired")
    assert render["retry_attempts"] == 1
    assert render["retry_history"][0]["attempt"] == 1
    assert "failed to render" in render["retry_history"][0]["error"]
    assert any(
        event.type == StreamEventType.PROGRESS and "Retry 1" in event.content
        for event in bus._history
    )


@pytest.mark.asyncio
async def test_default_math_renderer_retries_after_visual_review_failure(monkeypatch):
    from sparkweave.services.math_animator_support import renderer as renderer_module
    from sparkweave.services.math_animator_support.models import (
        GeneratedCode,
        RenderResult,
        VisualReviewResult,
    )

    monkeypatch.setattr(
        "sparkweave.graphs.math_animator.importlib.util.find_spec",
        lambda name: object() if name == "manim" else None,
    )

    class FakeManimRenderService:
        instances = []

        def __init__(self, turn_id, progress_callback=None):
            self.turn_id = turn_id
            self.progress_callback = progress_callback
            self.codes = []
            self.instances.append(self)

        async def render(self, *, code: str, output_mode: str, quality: str) -> RenderResult:
            self.codes.append(code)
            return RenderResult(output_mode=output_mode, artifacts=[], quality=quality)

    monkeypatch.setattr(renderer_module, "ManimRenderService", FakeManimRenderService)

    review_calls = 0

    async def review_callback(code: str, _render_result: RenderResult) -> VisualReviewResult:
        nonlocal review_calls
        review_calls += 1
        if review_calls == 1:
            assert "# repaired" not in code
            return VisualReviewResult(
                passed=False,
                summary="Labels overlap.",
                suggested_fix="Move labels outward.",
                reviewed_frames=3,
            )
        assert code.endswith("# repaired")
        return VisualReviewResult(passed=True, summary="Visuals are clear.", reviewed_frames=3)

    async def repair_callback(code: str, error_message: str, attempt: int) -> GeneratedCode:
        assert "Visual review failed" in error_message
        assert "Move labels outward" in error_message
        assert attempt == 1
        return GeneratedCode(code=code + "\n# repaired", rationale="layout fixed")

    bus = StreamBus()
    final_code, render = await DefaultMathRenderer().render(
        turn_id="turn-1",
        code="from manim import *",
        output_mode="video",
        quality="medium",
        stream=bus,
        source="math_animator",
        repair_callback=repair_callback,
        review_callback=review_callback,
        max_retries=2,
    )

    service = FakeManimRenderService.instances[0]
    assert service.codes == ["from manim import *", "from manim import *\n# repaired"]
    assert review_calls == 2
    assert final_code.endswith("# repaired")
    assert render["retry_attempts"] == 1
    assert render["visual_review"]["passed"] is True
    assert "Visual review failed" in render["retry_history"][0]["error"]


