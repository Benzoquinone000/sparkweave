from __future__ import annotations

import pytest

from sparkweave.core.contracts import StreamEventType, UnifiedContext
from sparkweave.runtime import LangGraphRunner


@pytest.mark.asyncio
async def test_runner_reports_unmigrated_capability_without_loading_langgraph():
    runner = LangGraphRunner()
    context = UnifiedContext(
        session_id="session-1",
        user_message="Research topic",
        active_capability="unknown_capability",
    )

    events = []
    async for event in runner.handle(context):
        events.append(event)

    assert events[0].type == StreamEventType.SESSION
    error_events = [event for event in events if event.type == StreamEventType.ERROR]
    assert len(error_events) == 1
    assert "has not migrated capability `unknown_capability` yet" in error_events[0].content
    assert events[-1].type == StreamEventType.DONE


@pytest.mark.asyncio
async def test_runner_executes_external_video_search_capability(monkeypatch):
    async def _fake_recommend_learning_videos(**kwargs):
        return {
            "render_type": "external_video",
            "response": "已找到 1 个精选视频。",
            "videos": [
                {
                    "title": "梯度下降入门",
                    "url": "https://example.com/video",
                    "platform": "公开平台",
                    "summary": "适合零基础先看。",
                }
            ],
        }

    monkeypatch.setattr(
        "sparkweave.services.video_search.recommend_learning_videos",
        _fake_recommend_learning_videos,
    )

    runner = LangGraphRunner()
    context = UnifiedContext(
        session_id="session-video",
        user_message="帮我找一个梯度下降讲解视频",
        active_capability="external_video_search",
        config_overrides={"topic": "梯度下降"},
    )

    events = []
    async for event in runner.handle(context):
        events.append(event)

    error_events = [event for event in events if event.type == StreamEventType.ERROR]
    assert len(error_events) == 1
    assert "has not migrated capability `external_video_search` yet" in error_events[0].content


def test_runner_lists_migrated_capabilities():
    assert LangGraphRunner().list_capabilities() == [
        "chat",
        "deep_question",
        "deep_research",
        "deep_solve",
        "math_animator",
        "visualize",
    ]


