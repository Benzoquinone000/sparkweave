from __future__ import annotations

from typing import Any

import pytest

from sparkweave.services import image_search


@pytest.mark.asyncio
async def test_recommend_learning_images_ranks_direct_image_results(monkeypatch) -> None:
    async def _fake_web_search(**kwargs: Any) -> dict[str, Any]:
        assert kwargs["query"]
        return {
            "image_results": [
                {
                    "title": "Gradient descent diagram visual explanation",
                    "url": "https://example.edu/gradient-descent",
                    "image_url": "https://example.edu/images/gradient-descent.png",
                    "thumbnail": "https://example.edu/thumbs/gradient-descent.jpg",
                    "description": "Beginner diagram showing step direction and learning rate.",
                    "source": "Example University",
                    "width": 1200,
                    "height": 720,
                    "license": "CC BY",
                },
                {
                    "title": "Unrelated wallpaper",
                    "url": "https://example.com/wallpaper",
                    "image_url": "https://example.com/wallpaper.jpg",
                    "description": "stock wallpaper",
                },
            ]
        }

    monkeypatch.setattr(image_search, "web_search", _fake_web_search)

    result = await image_search.recommend_learning_images(
        topic="gradient descent",
        learner_hints={"weak_points": ["learning rate"], "preferences": ["visual"]},
        max_results=2,
    )

    assert result["success"] is True
    assert result["render_type"] == "external_image"
    assert len(result["images"]) == 2
    assert result["images"][0]["image_url"] == "https://example.edu/images/gradient-descent.png"
    assert result["images"][0]["width"] == 1200
    assert "topic_match" in result["images"][0]["quality_signals"]
    assert "learning rate" in result["images"][0]["why_recommended"]
    assert result["view_plan"][0]
    assert result["learner_profile_hints"]["weak_points"] == ["learning rate"]


@pytest.mark.asyncio
async def test_recommend_learning_images_accepts_nested_provider_payloads(monkeypatch) -> None:
    async def _fake_web_search(**kwargs: Any) -> dict[str, Any]:
        return {
            "data": {
                "items": [
                    {
                        "name": "Derivative concept map",
                        "link": "https://example.org/calculus",
                        "metadata": {
                            "image": {
                                "contentUrl": "https://cdn.example.org/derivative.svg",
                                "width": "900",
                                "height": "600",
                            },
                            "licenseName": "Public domain",
                        },
                        "summary": "Visual concept map for derivatives.",
                    }
                ]
            },
            "answer": {
                "images": [
                    {
                        "title": "Redirected image result",
                        "url": "https://search.example.com/redirect?imgurl=https%3A%2F%2Fimg.example.com%2Fchain.webp",
                        "snippet": "diagram reference",
                    }
                ]
            },
        }

    monkeypatch.setattr(image_search, "web_search", _fake_web_search)

    result = await image_search.recommend_learning_images(topic="derivative", max_results=3)

    by_url = {item["image_url"] or item["url"]: item for item in result["images"]}
    assert "https://cdn.example.org/derivative.svg" in by_url
    assert "https://img.example.com/chain.webp" in by_url
    assert by_url["https://cdn.example.org/derivative.svg"]["height"] == 600
    assert by_url["https://cdn.example.org/derivative.svg"]["license"] == "Public domain"


@pytest.mark.asyncio
async def test_recommend_learning_images_returns_search_fallbacks(monkeypatch) -> None:
    async def _fake_web_search(**kwargs: Any) -> dict[str, Any]:
        return {
            "search_results": [
                {
                    "title": "Plain text article",
                    "url": "https://example.com/article",
                    "snippet": "No image metadata here.",
                }
            ]
        }

    monkeypatch.setattr(image_search, "web_search", _fake_web_search)

    result = await image_search.recommend_learning_images(topic="梯度下降", max_results=2)

    assert result["success"] is True
    assert result["fallback_search"] is True
    assert len(result["images"]) == 2
    assert all(item["kind"] == "search_fallback" for item in result["images"])
    assert result["images"][0]["url"].startswith("https://www.bing.com/images/search")
    assert "图片搜索入口" in result["response"]
