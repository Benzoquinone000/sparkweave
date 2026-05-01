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
    assert result["learner_profile_hints"]["weak_points"] == ["概念边界不清"]
    assert result["learner_profile_hints"]["preferences"] == ["video", "visual"]
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


@pytest.mark.asyncio
async def test_recommend_learning_videos_accepts_generic_provider_result_shapes(monkeypatch) -> None:
    async def _fake_web_search(**kwargs: Any) -> dict[str, Any]:
        return {
            "results": [
                {
                    "name": "Derivative intuition short visual guide",
                    "href": "https://youtu.be/abcDEF12345?si=demo",
                    "description": "Beginner intuition and tangent slope examples.",
                    "metadata": {
                        "imageUrl": "https://example.com/thumb.jpg",
                        "channel": "Calculus Lab",
                        "duration": "12:04",
                    },
                },
            ],
            "organic": [
                {
                    "title": "Derivative public live lecture",
                    "link": "https://www.youtube.com/live/LiveID12345?feature=share",
                    "body": "A longer public lecture about instantaneous rate.",
                    "duration": "1小时 5分钟",
                },
            ],
            "data": [
                {
                    "title": "Bilibili old av id video",
                    "content": "公开视频 av170001 讲解切线斜率。",
                    "source": "Bilibili",
                    "length": "8分30秒",
                },
            ],
        }

    monkeypatch.setattr(video_search, "web_search", _fake_web_search)

    result = await video_search.recommend_learning_videos(topic="导数直观理解", max_results=3)

    by_url = {item["url"]: item for item in result["videos"]}
    assert "https://www.youtube.com/watch?v=abcDEF12345" in by_url
    assert "https://www.youtube.com/watch?v=LiveID12345" in by_url
    assert "https://www.bilibili.com/video/av170001" in by_url
    assert by_url["https://www.youtube.com/watch?v=abcDEF12345"]["thumbnail"] == "https://example.com/thumb.jpg"
    assert by_url["https://www.youtube.com/watch?v=abcDEF12345"]["channel"] == "Calculus Lab"
    assert by_url["https://www.youtube.com/watch?v=abcDEF12345"]["duration_seconds"] == 724
    assert by_url["https://www.bilibili.com/video/av170001"]["embed_url"].startswith("https://player.bilibili.com/player.html?aid=170001")


@pytest.mark.asyncio
async def test_recommend_learning_videos_returns_platform_search_fallbacks(monkeypatch) -> None:
    async def _fake_web_search(**kwargs: Any) -> dict[str, Any]:
        return {
            "search_results": [
                {
                    "title": "梯度下降文字教程",
                    "url": "https://example.com/gradient-descent",
                    "snippet": "这是一篇普通网页，没有公开视频直链。",
                }
            ],
        }

    monkeypatch.setattr(video_search, "web_search", _fake_web_search)

    result = await video_search.recommend_learning_videos(topic="梯度下降", max_results=2)

    assert result["success"] is True
    assert result["fallback_search"] is True
    assert len(result["videos"]) == 2
    assert all(item["kind"] == "search_fallback" for item in result["videos"])
    assert result["videos"][0]["url"].startswith("https://search.bilibili.com/")
    assert result["videos"][1]["url"].startswith("https://www.youtube.com/results")
    assert "搜索入口" in result["response"]


@pytest.mark.asyncio
async def test_recommend_learning_videos_uses_structured_duration_and_thumbnail(monkeypatch) -> None:
    seen_queries: list[str] = []

    async def _fake_web_search(**kwargs: Any) -> dict[str, Any]:
        seen_queries.append(str(kwargs["query"]))
        return {
            "search_results": [
                {
                    "title": "梯度下降完整公开课 45分钟",
                    "url": "https://www.youtube.com/watch?v=LONG1234567",
                    "snippet": "完整课程，适合系统学习。",
                    "source": "YouTube",
                    "duration_seconds": 2700,
                    "thumbnail": "https://example.com/long.jpg",
                    "channel": "ML Course",
                },
                {
                    "title": "梯度下降直观短讲解",
                    "url": "https://www.youtube.com/watch?v=SHORT12345",
                    "snippet": "Beginner visual explanation.",
                    "source": "YouTube",
                    "duration": "08:30",
                    "thumbnail": "https://example.com/short.jpg",
                    "channel": "Quick ML",
                },
            ],
        }

    monkeypatch.setattr(video_search, "web_search", _fake_web_search)

    result = await video_search.recommend_learning_videos(
        topic="梯度下降",
        learner_hints={"time_budget_minutes": 10, "weak_points": ["公式意义不清"]},
        max_results=2,
    )

    assert "短讲解" in seen_queries[0]
    assert result["videos"][0]["title"] == "梯度下降直观短讲解"
    assert result["videos"][0]["duration_seconds"] == 510
    assert result["videos"][0]["thumbnail"] == "https://example.com/short.jpg"
    assert result["videos"][0]["channel"] == "Quick ML"
    assert "10 分钟" in result["videos"][0]["why_recommended"]
