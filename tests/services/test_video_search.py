from __future__ import annotations

from typing import Any

import pytest

from sparkweave.services import video_search


@pytest.mark.asyncio
async def test_recommend_learning_videos_ranks_public_video_links(monkeypatch) -> None:
    async def _fake_web_search(**kwargs: Any) -> dict[str, Any]:
        assert kwargs["query"]
        return {
            "search_results": [
                {
                    "title": "梯度下降直观理解 10分钟入门",
                    "url": "https://www.bilibili.com/video/BV1B7411m7LV/?spm_id_from=search",
                    "snippet": "用山坡类比解释梯度下降和学习率。",
                    "source": "bilibili",
                },
                {
                    "title": "Unrelated long live replay",
                    "url": "https://example.com/not-video",
                    "snippet": "no video",
                },
                {
                    "title": "Gradient Descent Explained",
                    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    "snippet": "Beginner visual tutorial.",
                    "source": "YouTube",
                },
            ],
        }

    monkeypatch.setattr(video_search, "web_search", _fake_web_search)

    result = await video_search.recommend_learning_videos(
        topic="梯度下降的直观理解",
        learner_hints={"weak_points": ["概念边界不清"], "preferences": ["video", "visual"]},
        max_results=2,
    )

    assert result["success"] is True
    assert result["render_type"] == "external_video"
    assert len(result["videos"]) == 2
    assert result["videos"][0]["platform"] == "Bilibili"
    assert result["videos"][0]["embed_url"].startswith("https://player.bilibili.com/player.html")
    assert "概念边界不清" in result["videos"][0]["why_recommended"]
    assert result["videos"][1]["thumbnail"].startswith("https://img.youtube.com/vi/")
