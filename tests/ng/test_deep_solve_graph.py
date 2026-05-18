from __future__ import annotations

from types import SimpleNamespace

import pytest

from sparkweave.core.contracts import StreamBus, StreamEventType, UnifiedContext
from sparkweave.core.tool_protocol import ToolResult
from sparkweave.graphs.deep_solve import DeepSolveGraph


class FakeModel:
    def __init__(self, responses):
        self.responses = list(responses)
        self.bound_tools = None

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self

    async def ainvoke(self, _messages):
        return self.responses.pop(0)


class FakeToolRegistry:
    def __init__(self):
        self.calls = []

    def names(self):
        return ["rag", "web_search"]

    def get_tools(self, names):
        return [SimpleNamespace(name=name) for name in names]

    async def execute(self, name, **kwargs):
        self.calls.append((name, kwargs))
        return ToolResult(
            content="retrieved context",
            sources=[{"type": "rag", "title": "Demo"}],
            metadata={"ok": True},
        )


@pytest.mark.asyncio
async def test_deep_solve_graph_runs_plan_solve_verify_write_without_tools():
    from langchain_core.messages import AIMessage

    bus = StreamBus()
    graph = DeepSolveGraph(
        model=FakeModel(
            [
                AIMessage(
                    content='{"analysis":"Need algebra.","steps":[{"id":"S1","goal":"Solve the equation"}]}'
                ),
                AIMessage(content="x^2=4 means x=2 or x=-2."),
                AIMessage(content="The two roots are complete."),
                AIMessage(content="The solutions are x = 2 and x = -2."),
            ]
        ),
        tool_registry=FakeToolRegistry(),
    )
    context = UnifiedContext(user_message="Solve x^2 = 4", enabled_tools=[])

    state = await graph.run(context, bus)

    assert state["plan"]["steps"][0]["id"] == "S1"
    assert state["draft_answer"] == "x^2=4 means x=2 or x=-2."
    assert state["verification"] == "The two roots are complete."
    assert state["final_answer"] == "The solutions are x = 2 and x = -2."
    assert any(event.type == StreamEventType.RESULT for event in bus._history)


@pytest.mark.asyncio
async def test_deep_solve_graph_executes_selected_tool_call():
    from langchain_core.messages import AIMessage

    registry = FakeToolRegistry()
    bus = StreamBus()
    graph = DeepSolveGraph(
        model=FakeModel(
            [
                AIMessage(
                    content='{"analysis":"Need a definition.","steps":[{"id":"S1","goal":"Use context"}]}'
                ),
                AIMessage(
                    content="I should retrieve context.",
                    tool_calls=[
                        {
                            "name": "rag",
                            "args": {"query": "linear algebra eigenvalue"},
                            "id": "rag-1",
                        }
                    ],
                ),
                AIMessage(content="Using the retrieved context, eigenvalues satisfy Av=lambda v."),
                AIMessage(content="The statement is consistent."),
                AIMessage(content="An eigenvalue is a scalar lambda where Av = lambda v."),
            ]
        ),
        tool_registry=registry,
    )
    context = UnifiedContext(
        user_message="What is an eigenvalue?",
        enabled_tools=["rag"],
        knowledge_bases=["linear-algebra"],
    )

    state = await graph.run(context, bus)

    assert registry.calls == [
        (
            "rag",
            {
                "query": "linear algebra eigenvalue",
                "kb_name": "linear-algebra",
            },
        )
    ]
    assert state["tool_results"][0]["result"] == "retrieved context"
    assert state["final_answer"] == "An eigenvalue is a scalar lambda where Av = lambda v."
    assert any(event.type == StreamEventType.TOOL_CALL for event in bus._history)
    assert any(event.type == StreamEventType.TOOL_RESULT for event in bus._history)


