from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from sparkweave.core.contracts import StreamBus, StreamEventType, UnifiedContext
from sparkweave.core.tool_protocol import ToolResult
from sparkweave.graphs.chat import ChatGraph


class FakeModel:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.bound_tools: list[Any] = []

    def bind_tools(self, tools: list[Any]) -> FakeModel:
        self.bound_tools = tools
        return self

    async def ainvoke(self, _messages: Any) -> Any:
        return self.responses.pop(0)


class ParallelRegistry:
    def __init__(self, names: list[str]) -> None:
        self._names = names
        self.inflight = 0
        self.max_inflight = 0
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def names(self) -> list[str]:
        return list(self._names)

    def get_tools(self, names: list[str]) -> list[Any]:
        return [SimpleNamespace(name=name) for name in names]

    async def execute(self, name: str, **kwargs: Any) -> ToolResult:
        self.inflight += 1
        self.max_inflight = max(self.max_inflight, self.inflight)
        await asyncio.sleep(0.02)
        self.inflight -= 1
        kwargs_without_callbacks = {
            key: value for key, value in kwargs.items() if key != "event_sink"
        }
        self.calls.append((name, kwargs_without_callbacks))
        return ToolResult(
            content=f"{name} => {kwargs.get('query', '') or kwargs.get('context', '')}".strip(),
            sources=[{"tool": name}],
            metadata={"tool": name},
            success=True,
        )


@pytest.mark.asyncio
async def test_chat_graph_executes_parallel_tool_calls() -> None:
    from langchain_core.messages import AIMessage

    registry = ParallelRegistry(["web_search", "reason"])
    model = FakeModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "web_search", "args": {"query": "first"}, "id": "tool-call-1"},
                    {"name": "reason", "args": {"context": "second"}, "id": "tool-call-2"},
                ],
            ),
            AIMessage(content="No more tools needed."),
        ]
    )
    bus = StreamBus()
    graph = ChatGraph(model=model, tool_registry=registry)
    context = UnifiedContext(
        session_id="session-1",
        user_message="compare two sources",
        enabled_tools=["web_search", "reason"],
        metadata={"turn_id": "turn-1"},
    )

    state = await graph.run(context, bus)

    assert state["final_answer"] == "No more tools needed."
    assert registry.max_inflight >= 2
    assert registry.calls == [
        ("web_search", {"query": "first"}),
        ("reason", {"context": "second"}),
    ]
    tool_result_events = [
        event for event in bus._history if event.type == StreamEventType.TOOL_RESULT
    ]
    assert len(tool_result_events) == 2
    assert tool_result_events[0].metadata["tool_call_id"] == "tool-call-1"
    assert tool_result_events[1].metadata["tool_call_id"] == "tool-call-2"
    assert tool_result_events[0].metadata["tool_index"] == 0
    assert tool_result_events[1].metadata["tool_index"] == 1
    acting_thinking_events = [
        event
        for event in bus._history
        if event.type == StreamEventType.THINKING and event.stage == "acting"
    ]
    assert acting_thinking_events == []


@pytest.mark.asyncio
async def test_chat_graph_streams_retrieve_progress_for_rag() -> None:
    from langchain_core.messages import AIMessage

    class RagRegistry(ParallelRegistry):
        async def execute(self, name: str, **kwargs: Any) -> ToolResult:
            event_sink = kwargs.get("event_sink")
            if event_sink is not None:
                await event_sink("status", "Selecting provider: llamaindex", {"provider": "llamaindex"})
                await event_sink("status", "Retrieving chunks...", {"mode": "hybrid"})
            return ToolResult(
                content="grounded answer text.",
                sources=[{"tool": name}],
                metadata={"tool": name},
                success=True,
            )

    registry = RagRegistry(["rag"])
    model = FakeModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "rag",
                        "args": {"query": "transformer model"},
                        "id": "tool-call-rag",
                    }
                ],
            ),
            AIMessage(content="A transformer uses attention."),
        ]
    )
    bus = StreamBus()
    graph = ChatGraph(model=model, tool_registry=registry)
    context = UnifiedContext(
        session_id="session-1",
        user_message="what is a transformer",
        enabled_tools=["rag"],
        knowledge_bases=["demo-kb"],
        metadata={"turn_id": "turn-1"},
    )

    await graph.run(context, bus)

    retrieve_events = [
        event
        for event in bus._history
        if event.type == StreamEventType.PROGRESS
        and event.metadata.get("trace_role") == "retrieve"
    ]
    assert [event.content for event in retrieve_events] == [
        "Query: transformer model",
        "Selecting provider: llamaindex",
        "Retrieving chunks...",
        "Retrieve complete (21 chars)",
    ]


@pytest.mark.asyncio
async def test_chat_graph_caps_parallel_tool_calls_at_eight() -> None:
    from langchain_core.messages import AIMessage

    registry = ParallelRegistry(["web_search"])
    tool_calls = [
        {"name": "web_search", "args": {"query": f"q{index}"}, "id": f"tool-call-{index}"}
        for index in range(10)
    ]
    model = FakeModel(
        [
            AIMessage(content="Use multiple tools in parallel.", tool_calls=tool_calls),
            AIMessage(content="Done."),
        ]
    )
    bus = StreamBus()
    graph = ChatGraph(model=model, tool_registry=registry)
    context = UnifiedContext(
        session_id="session-1",
        user_message="collect broad evidence",
        enabled_tools=["web_search"],
        metadata={"turn_id": "turn-1"},
    )

    await graph.run(context, bus)

    assert len(registry.calls) == 8
    assert {name for name, _args in registry.calls} == {"web_search"}
    assert {args["query"] for _name, args in registry.calls} == {
        f"q{index}" for index in range(8)
    }
    progress_events = [
        event.content for event in bus._history if event.type == StreamEventType.PROGRESS
    ]
    assert any("only 8 can run in parallel" in content for content in progress_events)

