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


def test_runner_lists_migrated_capabilities():
    assert LangGraphRunner().list_capabilities() == [
        "chat",
        "deep_question",
        "deep_research",
        "deep_solve",
        "math_animator",
        "visualize",
    ]


