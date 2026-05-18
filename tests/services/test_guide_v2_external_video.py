from __future__ import annotations

from typing import Any

import pytest

import sparkweave.services.guide_v2 as guide_v2_module
from sparkweave.services.guide_v2 import GuideV2CreateInput, GuideV2Manager


@pytest.mark.asyncio
async def test_guide_v2_generates_external_video_resource(tmp_path, monkeypatch) -> None:
    async def _failing_completion(**_kwargs: Any) -> str:
        raise RuntimeError("llm unavailable")

    async def _runner(_capability: str, _context: Any) -> dict[str, Any]:
        raise AssertionError("external video should not call LangGraph capability runner")

    async def _fake_recommend_learning_videos(**kwargs: Any) -> dict[str, Any]:
        assert kwargs["topic"]
        assert kwargs["learner_hints"]["weak_points"]
        return {
            "success": True,
            "render_type": "external_video",
            "response": "已筛选 1 个公开视频。",
            "videos": [
                {
                    "title": "梯度下降直观理解",
                    "url": "https://www.bilibili.com/video/BV1B7411m7LV",
                    "platform": "Bilibili",
                    "embed_url": "https://player.bilibili.com/player.html?bvid=BV1B7411m7LV",
                    "why_recommended": "贴合当前卡点。",
                    "score": 0.9,
                }
            ],
        }

    monkeypatch.setattr(guide_v2_module, "recommend_learning_videos", _fake_recommend_learning_videos)

    manager = GuideV2Manager(output_dir=tmp_path, completion_fn=_failing_completion, capability_runner=_runner)
    created = await manager.create_session(
        GuideV2CreateInput(
            goal="学习梯度下降",
            preferences=["video"],
            weak_points=["概念边界不清"],
        )
    )
    session_id = created["session"]["session_id"]
    task_id = created["session"]["current_task"]["task_id"]

    generated = await manager.generate_resource(session_id, task_id, resource_type="external_video")

    assert generated["success"] is True
    artifact = generated["artifact"]
    assert artifact["type"] == "external_video"
    assert artifact["capability"] == "external_video_search"
    assert artifact["result"]["videos"][0]["platform"] == "Bilibili"
    assert manager.get_session(session_id)["current_task"]["artifact_refs"][0]["type"] == "external_video"
