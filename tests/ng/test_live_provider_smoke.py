from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import os
from typing import Any

import pytest

from sparkweave.core.contracts import StreamEvent, StreamEventType, UnifiedContext
from sparkweave.runtime import LangGraphRunner


@dataclass(frozen=True)
class LiveCase:
    capability: str
    message: str
    config: dict[str, Any] = field(default_factory=dict)
    enabled_tools: list[str] = field(default_factory=list)


LIVE_CASES = [
    LiveCase(
        capability="chat",
        message="Reply in one short sentence: what is a Fourier transform?",
    ),
    LiveCase(
        capability="deep_solve",
        message="Solve x^2 - 5x + 6 = 0. Keep the explanation short.",
    ),
    LiveCase(
        capability="deep_question",
        message="Create one short algebra practice question about factoring.",
        config={"num_questions": 1, "question_type": "written"},
    ),
    LiveCase(
        capability="deep_research",
        message="Write a very short research note about retrieval augmented generation.",
    ),
    LiveCase(
        capability="visualize",
        message="Create a tiny flowchart for a RAG pipeline.",
        config={"render_mode": "mermaid"},
    ),
    LiveCase(
        capability="math_animator",
        message="Animate the derivative as a tangent line, very briefly.",
        config={"output_mode": "image", "quality": "low", "max_retries": 0},
    ),
]


def _live_enabled() -> bool:
    return os.getenv("SPARKWEAVE_NG_LIVE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _selected_capabilities() -> set[str]:
    raw = os.getenv("SPARKWEAVE_NG_LIVE_CAPABILITIES", "chat").strip().lower()
    if raw in {"all", "*"}:
        return {case.capability for case in LIVE_CASES}
    return {item.strip() for item in raw.split(",") if item.strip()}


def _timeout_seconds() -> float:
    raw = os.getenv("SPARKWEAVE_NG_LIVE_TIMEOUT_SECONDS", "90").strip()
    try:
        return max(5.0, float(raw))
    except ValueError:
        return 90.0


@pytest.mark.live
@pytest.mark.asyncio
@pytest.mark.parametrize("case", LIVE_CASES, ids=[case.capability for case in LIVE_CASES])
async def test_live_provider_langgraph_runner_smoke(case: LiveCase) -> None:
    if not _live_enabled():
        pytest.skip("Set SPARKWEAVE_NG_LIVE=1 to run live LangGraph provider smoke tests.")
    if case.capability not in _selected_capabilities():
        pytest.skip(f"{case.capability} not selected by SPARKWEAVE_NG_LIVE_CAPABILITIES.")

    context = UnifiedContext(
        session_id=f"live-{case.capability}",
        user_message=case.message,
        active_capability=case.capability,
        enabled_tools=case.enabled_tools,
        config_overrides={"_runtime": "langgraph", **case.config},
        language="en",
    )

    events: list[StreamEvent] = []
    async with asyncio.timeout(_timeout_seconds()):
        async for event in LangGraphRunner().handle(context):
            events.append(event)

    errors = [event.content for event in events if event.type == StreamEventType.ERROR]
    result_events = [event for event in events if event.type == StreamEventType.RESULT]

    assert errors == []
    assert events[0].type == StreamEventType.SESSION
    assert result_events, "expected a result event from the live graph"
    assert result_events[-1].metadata.get("runtime") == "langgraph"
    assert events[-1].type == StreamEventType.DONE



