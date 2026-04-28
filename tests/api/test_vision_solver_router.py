from __future__ import annotations

from types import SimpleNamespace

import pytest

from sparkweave.api.routers import vision_solver


@pytest.mark.asyncio
async def test_vision_analyze_route_uses_ng_agent(monkeypatch):
    calls: dict[str, object] = {}

    async def fake_resolve_image_input(**kwargs):
        calls["resolve"] = kwargs
        return "data:image/png;base64,YWJj"

    class FakeVisionSolverAgent:
        def __init__(self, **kwargs):
            calls["agent_init"] = kwargs

        async def process(self, **kwargs):
            calls["process"] = kwargs
            return {
                "has_image": True,
                "bbox_output": {"elements": [{"type": "point"}]},
                "image_is_reference": False,
                "final_ggb_commands": [
                    {"command": "A=(0,0)", "description": "point A"},
                ],
            }

        def format_ggb_block(self, commands, page_id="main", title="Problem Figure"):
            calls["format"] = {"commands": commands, "page_id": page_id, "title": title}
            return "```ggbscript[analysis;figure]\nA=(0,0)\n```"

    assert vision_solver.VisionSolverAgent.__module__ == "sparkweave.services.vision"

    monkeypatch.setattr(vision_solver, "resolve_image_input", fake_resolve_image_input)
    monkeypatch.setattr(
        vision_solver,
        "get_llm_config",
        lambda: SimpleNamespace(api_key="key", base_url="https://example.test/v1"),
    )
    monkeypatch.setattr(vision_solver, "get_ui_language", lambda default="zh": default)
    monkeypatch.setattr(vision_solver, "VisionSolverAgent", FakeVisionSolverAgent)

    response = await vision_solver.analyze_image(
        vision_solver.VisionAnalyzeRequest(question="Find A", image_url="https://example.test/a.png")
    )

    assert response.session_id.startswith("vision_")
    assert response.has_image is True
    assert response.final_ggb_commands[0]["command"] == "A=(0,0)"
    assert response.analysis_summary["elements_count"] == 1
    assert calls["resolve"] == {
        "image_base64": None,
        "image_url": "https://example.test/a.png",
    }
    assert calls["agent_init"] == {
        "api_key": "key",
        "base_url": "https://example.test/v1",
        "language": "zh",
    }


