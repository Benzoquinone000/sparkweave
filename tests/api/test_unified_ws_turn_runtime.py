from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from sparkweave.core.contracts import StreamEvent, StreamEventType, UnifiedContext
from sparkweave.runtime import LangGraphTurnRuntimeManager
from sparkweave.services.session import create_session_store


class FakeMemory:
    def __init__(self, context: str = "") -> None:
        self.context = context
        self.refresh_calls: list[dict] = []

    def build_memory_context(self) -> str:
        return self.context

    async def refresh_from_turn(self, **kwargs) -> None:
        self.refresh_calls.append(kwargs)


class FakeRunner:
    def __init__(self, events: list[StreamEvent]) -> None:
        self.events = events
        self.contexts: list[UnifiedContext] = []

    async def handle(self, context: UnifiedContext) -> AsyncIterator[StreamEvent]:
        self.contexts.append(context)
        for event in self.events:
            yield event


class FakeEvidence:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def append_events(self, events: list[dict], *, dedupe: bool = True):  # noqa: ANN001, ANN201
        self.events.extend(events)
        return {"added": len(events), "skipped": 0, "events": events}


@pytest.mark.asyncio
async def test_turn_runtime_replays_events_and_materializes_messages(tmp_path) -> None:
    store = create_session_store(tmp_path / "chat_history.db")
    runner = FakeRunner(
        [
            StreamEvent(
                type=StreamEventType.CONTENT,
                source="chat",
                stage="responding",
                content="Hello Frank",
            ),
            StreamEvent(type=StreamEventType.DONE, source="langgraph"),
        ]
    )
    runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=runner,
        memory_service=FakeMemory(),
    )

    session, turn = await runtime.start_turn(
        {
            "type": "start_turn",
            "content": "hello, i'm frank",
            "session_id": None,
            "capability": None,
            "tools": [],
            "knowledge_bases": [],
            "attachments": [],
            "language": "en",
            "config": {},
        }
    )

    events = [event async for event in runtime.subscribe_turn(turn["id"], after_seq=0)]

    assert [event["type"] for event in events] == ["session", "content", "done"]
    assert events[-1]["metadata"]["status"] == "completed"

    detail = await store.get_session_with_messages(session["id"])
    assert detail is not None
    assert [message["role"] for message in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["content"] == "Hello Frank"
    assert detail["preferences"] == {
        "capability": "chat",
        "tools": [],
        "knowledge_bases": [],
        "language": "en",
    }

    persisted_turn = await store.get_turn(turn["id"])
    assert persisted_turn is not None
    assert persisted_turn["status"] == "completed"


@pytest.mark.asyncio
async def test_turn_runtime_appends_chat_statement_evidence(tmp_path) -> None:
    store = create_session_store(tmp_path / "chat_history.db")
    evidence = FakeEvidence()
    runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=FakeRunner(
            [
                StreamEvent(type=StreamEventType.CONTENT, source="chat", content="ok"),
                StreamEvent(type=StreamEventType.DONE, source="langgraph"),
            ]
        ),
        memory_service=FakeMemory(),
        evidence_service=evidence,
    )

    _session, turn = await runtime.start_turn(
        {
            "type": "start_turn",
            "content": "I want to master gradient descent, but I am confused. I prefer visual videos.",
            "session_id": None,
            "capability": "chat",
            "tools": [],
            "knowledge_bases": [],
            "attachments": [],
            "language": "en",
            "config": {},
        }
    )
    _events = [event async for event in runtime.subscribe_turn(turn["id"], after_seq=0)]

    object_types = {event["object_type"] for event in evidence.events}
    assert "learning_goal" in object_types
    assert "learning_blocker" in object_types
    assert "learning_preference" in object_types


@pytest.mark.asyncio
async def test_turn_runtime_preserves_langgraph_runtime_config_in_context(tmp_path) -> None:
    store = create_session_store(tmp_path / "chat_history.db")
    runner = FakeRunner(
        [
            StreamEvent(
                type=StreamEventType.CONTENT,
                source="chat",
                stage="responding",
                content="NG response",
                metadata={"runtime": "langgraph"},
            ),
            StreamEvent(
                type=StreamEventType.RESULT,
                source="chat",
                metadata={"response": "NG response", "runtime": "langgraph"},
            ),
            StreamEvent(type=StreamEventType.DONE, source="langgraph"),
        ]
    )
    runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=runner,
        memory_service=FakeMemory(),
    )

    session, turn = await runtime.start_turn(
        {
            "type": "start_turn",
            "content": "hello langgraph",
            "session_id": None,
            "capability": "chat",
            "tools": [],
            "knowledge_bases": [],
            "attachments": [],
            "language": "en",
            "config": {"_runtime": "langgraph"},
        }
    )

    events = [event async for event in runtime.subscribe_turn(turn["id"], after_seq=0)]

    assert [event["type"] for event in events] == ["session", "content", "result", "done"]
    context = runner.contexts[0]
    assert context.active_capability == "chat"
    assert context.config_overrides["_runtime"] == "langgraph"
    assert context.metadata["turn_id"] == turn["id"]
    assert events[2]["metadata"]["runtime"] == "langgraph"

    detail = await store.get_session_with_messages(session["id"])
    assert detail is not None
    assert [message["role"] for message in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["content"] == "NG response"


@pytest.mark.asyncio
async def test_turn_runtime_rejects_deep_research_without_explicit_config(tmp_path) -> None:
    store = create_session_store(tmp_path / "chat_history.db")
    runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=FakeRunner([]),
        memory_service=FakeMemory(),
    )

    with pytest.raises(RuntimeError, match="Invalid deep research config"):
        await runtime.start_turn(
            {
                "type": "start_turn",
                "content": "research transformers",
                "session_id": None,
                "capability": "deep_research",
                "tools": ["rag"],
                "knowledge_bases": ["research-kb"],
                "attachments": [],
                "language": "en",
                "config": {},
            }
        )


@pytest.mark.asyncio
async def test_turn_runtime_injects_memory_and_refreshes_after_completion(tmp_path) -> None:
    store = create_session_store(tmp_path / "chat_history.db")
    memory = FakeMemory(context="## Memory\n## Preferences\n- Prefer concise answers.")
    runner = FakeRunner(
        [
            StreamEvent(
                type=StreamEventType.CONTENT,
                source="chat",
                stage="responding",
                content="Stored reply",
            ),
            StreamEvent(type=StreamEventType.DONE, source="langgraph"),
        ]
    )
    runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=runner,
        memory_service=memory,
    )

    _session, turn = await runtime.start_turn(
        {
            "type": "start_turn",
            "content": "hello, i'm frank",
            "session_id": None,
            "capability": None,
            "tools": [],
            "knowledge_bases": [],
            "attachments": [],
            "language": "en",
            "config": {},
        }
    )

    async for _event in runtime.subscribe_turn(turn["id"], after_seq=0):
        pass

    context = runner.contexts[0]
    assert context.memory_context == "## Memory\n## Preferences\n- Prefer concise answers."
    assert memory.refresh_calls[0]["assistant_message"] == "Stored reply"

