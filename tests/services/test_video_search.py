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


@pytest.mark.asyncio
async def test_recommend_learning_videos_accepts_provider_link_aliases_and_redirects(monkeypatch) -> None:
    async def _fake_web_search(**kwargs: Any) -> dict[str, Any]:
        return {
            "search_results": [
                {
                    "title": "Gradient Descent Visual Guide",
                    "link": "https://www.google.com/url?q=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3DabcDEF12345&sa=U",
                    "content": "Beginner intuition with visual examples.",
                    "website": "Google",
                },
                {
                    "title": "网页整理：梯度下降",
                    "href": "https://example.com/gradient",
                    "snippet": "推荐视频 https://www.bilibili.com/video/BV1B7411m7LV 适合入门。",
                },
            ],
        }

    monkeypatch.setattr(video_search, "web_search", _fake_web_search)

    result = await video_search.recommend_learning_videos(topic="梯度下降", max_results=3)

    urls = {item["url"] for item in result["videos"]}
    assert "https://www.youtube.com/watch?v=abcDEF12345" in urls
    assert "https://www.bilibili.com/video/BV1B7411m7LV" in urls
