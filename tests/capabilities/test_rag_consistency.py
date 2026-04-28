"""RAG/KB consistency tests for NG graph capabilities."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from sparkweave.core.contracts import StreamBus, StreamEventType, UnifiedContext
from sparkweave.core.tool_protocol import ToolResult
from sparkweave.graphs.deep_research import DeepResearchGraph
from sparkweave.graphs.deep_solve import DeepSolveGraph


class FakeModel:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.bound_tool_names: list[str] = []

    def bind_tools(self, tools: list[Any]) -> FakeModel:
        self.bound_tool_names = [str(getattr(tool, "name", "")) for tool in tools]
        return self

    async def ainvoke(self, _messages: Any) -> Any:
        response = self.responses.pop(0)
        if isinstance(response, str):
            from langchain_core.messages import AIMessage

            return AIMessage(content=response)
        return response


class FakeToolRegistry:
    def __init__(self, names: list[str]) -> None:
        self._names = names
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def names(self) -> list[str]:
        return list(self._names)

    def get_tools(self, names: list[str]) -> list[Any]:
        return [SimpleNamespace(name=name) for name in names]

    async def execute(self, name: str, **kwargs: Any) -> ToolResult:
        self.calls.append((name, kwargs))
        return ToolResult(
            content=f"{name} result",
            sources=[{"type": name, "title": "Demo"}],
            metadata={"ok": True},
        )


@pytest.mark.asyncio
async def test_deep_solve_strips_rag_when_no_knowledge_base() -> None:
    model = FakeModel(
        [
            '{"analysis":"Need algebra.","steps":[{"id":"S1","goal":"Solve"}]}',
            "Use web if needed, but no RAG.",
            "Draft answer.",
            "Looks correct.",
            "Final answer.",
        ]
    )
    registry = FakeToolRegistry(["rag", "web_search"])
    bus = StreamBus()
    graph = DeepSolveGraph(model=model, tool_registry=registry)
    context = UnifiedContext(
        user_message="solve x^2 = 4",
        active_capability="deep_solve",
        enabled_tools=["rag", "web_search"],
        knowledge_bases=[],
    )

    await graph.run(context, bus)

    assert "rag" not in model.bound_tool_names
    assert "web_search" in model.bound_tool_names
    assert registry.calls == []
    warnings = [
        event
        for event in bus._history
        if event.type == StreamEventType.PROGRESS
        and event.metadata.get("reason") == "rag_without_kb"
    ]
    assert warnings


@pytest.mark.asyncio
async def test_deep_solve_keeps_rag_when_knowledge_base_attached() -> None:
    from langchain_core.messages import AIMessage

    model = FakeModel(
        [
            '{"analysis":"Need context.","steps":[{"id":"S1","goal":"Retrieve"}]}',
            AIMessage(
                content="Use RAG.",
                tool_calls=[
                    {
                        "name": "rag",
                        "args": {"query": "quadratic equations"},
                        "id": "rag-1",
                    }
                ],
            ),
            "Draft with retrieved context.",
            "Looks correct.",
            "Final answer.",
        ]
    )
    registry = FakeToolRegistry(["rag", "web_search"])
    bus = StreamBus()
    graph = DeepSolveGraph(model=model, tool_registry=registry)
    context = UnifiedContext(
        user_message="solve x^2 = 4",
        active_capability="deep_solve",
        enabled_tools=["rag", "web_search"],
        knowledge_bases=["my-kb"],
    )

    await graph.run(context, bus)

    assert "rag" in model.bound_tool_names
    assert registry.calls == [
        ("rag", {"query": "quadratic equations", "kb_name": "my-kb"})
    ]


@pytest.mark.asyncio
async def test_deep_research_drops_kb_source_when_no_knowledge_base() -> None:
    model = FakeModel(
        [
            "A topic to research?",
            "# Report\n\nWeb-backed report.",
        ]
    )
    registry = FakeToolRegistry(["rag", "web_search"])
    bus = StreamBus()
    graph = DeepResearchGraph(model=model, tool_registry=registry)
    context = UnifiedContext(
        user_message="A topic to research",
        active_capability="deep_research",
        enabled_tools=["rag", "web_search"],
        knowledge_bases=[],
        config_overrides={
            "mode": "report",
            "depth": "manual",
            "sources": ["kb", "web"],
            "confirmed_outline": [
                {
                    "title": "Subtopic 1",
                    "overview": "Overview 1",
                    "queries": ["topic web query"],
                }
            ],
        },
    )

    await graph.run(context, bus)

    assert registry.calls == [("web_search", {"query": "topic web query"})]
    warnings = [
        event
        for event in bus._history
        if event.type == StreamEventType.PROGRESS
        and event.metadata.get("reason") == "kb_unavailable"
    ]
    assert warnings


@pytest.mark.asyncio
async def test_deep_research_with_only_kb_and_no_knowledge_base_uses_safe_fallback() -> None:
    model = FakeModel(
        [
            "A topic to research?",
            "# Report\n\nInternal-knowledge fallback.",
        ]
    )
    registry = FakeToolRegistry(["rag"])
    bus = StreamBus()
    graph = DeepResearchGraph(model=model, tool_registry=registry)
    context = UnifiedContext(
        user_message="topic",
        active_capability="deep_research",
        enabled_tools=["rag"],
        knowledge_bases=[],
        config_overrides={
            "mode": "report",
            "depth": "manual",
            "sources": ["kb"],
            "confirmed_outline": [
                {"title": "Subtopic 1", "overview": "Overview 1", "queries": ["kb query"]}
            ],
        },
    )

    await graph.run(context, bus)

    assert registry.calls == []
    warnings = [
        event
        for event in bus._history
        if event.type == StreamEventType.PROGRESS
        and event.metadata.get("reason") in {"kb_unavailable", "no_sources"}
    ]
    assert {event.metadata["reason"] for event in warnings} == {
        "kb_unavailable",
        "no_sources",
    }
    result = next(event for event in bus._history if event.type == StreamEventType.RESULT)
    assert result.metadata["response"].startswith("# Report")

