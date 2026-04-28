"""Runtime tests for NG built-in capability graphs."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from sparkweave.core.contracts import StreamBus, StreamEventType, UnifiedContext
from sparkweave.core.tool_protocol import ToolResult
from sparkweave.graphs.chat import ChatGraph
from sparkweave.graphs.deep_question import DeepQuestionGraph
from sparkweave.graphs.deep_research import DeepResearchGraph
from sparkweave.graphs.deep_solve import DeepSolveGraph
from sparkweave.runtime.registry.capability_registry import get_capability_registry


class FakeModel:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.bound_tools: list[Any] = []
        self.calls: list[Any] = []

    def bind_tools(self, tools: list[Any]) -> FakeModel:
        self.bound_tools = tools
        return self

    async def ainvoke(self, messages: Any) -> Any:
        self.calls.append(messages)
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
        self.calls.append((name, {key: value for key, value in kwargs.items() if key != "event_sink"}))
        return ToolResult(
            content=f"{name} result",
            sources=[{"type": name, "title": "Demo source"}],
            metadata={"tool": name},
            success=True,
        )


def _result(bus: StreamBus) -> dict[str, Any]:
    result = next(event for event in bus._history if event.type == StreamEventType.RESULT)
    return result.metadata


@pytest.mark.asyncio
async def test_chat_graph_streams_tool_call_sources_and_content() -> None:
    from langchain_core.messages import AIMessage

    registry = FakeToolRegistry(["geogebra_analysis"])
    model = FakeModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "geogebra_analysis",
                        "args": {"image_name": "img.png"},
                        "id": "geo-1",
                    }
                ],
            ),
            AIMessage(content="assistant output"),
        ]
    )
    bus = StreamBus()
    graph = ChatGraph(model=model, tool_registry=registry)
    context = UnifiedContext(
        user_message="analyze triangle",
        enabled_tools=["geogebra_analysis"],
        metadata={"turn_id": "turn-1"},
    )

    state = await graph.run(context, bus)

    assert state["final_answer"] == "assistant output"
    assert registry.calls == [("geogebra_analysis", {"image_name": "img.png"})]
    assert any(event.type == StreamEventType.TOOL_CALL for event in bus._history)
    assert any(event.type == StreamEventType.SOURCES for event in bus._history)
    assert any(
        event.type == StreamEventType.CONTENT and "assistant output" in event.content
        for event in bus._history
    )


@pytest.mark.asyncio
async def test_deep_solve_graph_bridges_tool_output_to_result() -> None:
    from langchain_core.messages import AIMessage

    registry = FakeToolRegistry(["rag"])
    model = FakeModel(
        [
            '{"analysis":"Need context.","steps":[{"id":"S1","goal":"Retrieve and solve"}]}',
            AIMessage(
                content="Need RAG.",
                tool_calls=[
                    {
                        "name": "rag",
                        "args": {"query": "quadratic equation"},
                        "id": "rag-1",
                    }
                ],
            ),
            "Draft solution using context.",
            "The draft is correct.",
            "Final solution.",
        ]
    )
    bus = StreamBus()
    graph = DeepSolveGraph(model=model, tool_registry=registry)
    context = UnifiedContext(
        user_message="solve x^2=4",
        enabled_tools=["rag"],
        knowledge_bases=["algebra"],
    )

    state = await graph.run(context, bus)

    assert registry.calls == [("rag", {"query": "quadratic equation", "kb_name": "algebra"})]
    assert state["final_answer"] == "Final solution."
    assert any(event.type == StreamEventType.TOOL_CALL for event in bus._history)
    assert any(event.type == StreamEventType.TOOL_RESULT for event in bus._history)
    assert _result(bus)["response"] == "Final solution."


@pytest.mark.asyncio
async def test_deep_question_graph_uses_user_message_as_topic() -> None:
    model = FakeModel(
        [
            (
                '{"templates":[{"concentration":"linear algebra fundamentals",'
                '"question_type":"written","difficulty":"medium","rationale":"core concept"}]}'
            ),
            (
                '{"question_type":"written","question":"What is a matrix?",'
                '"options":null,"correct_answer":"A rectangular array.",'
                '"explanation":"A matrix stores values in rows and columns."}'
            ),
        ]
    )
    bus = StreamBus()
    graph = DeepQuestionGraph(model=model, tool_registry=FakeToolRegistry([]))
    context = UnifiedContext(
        user_message="linear algebra fundamentals",
        config_overrides={"num_questions": 1, "question_type": "written"},
    )

    state = await graph.run(context, bus)

    assert state["templates"][0]["concentration"] == "linear algebra fundamentals"
    assert state["questions"][0]["qa_pair"]["question"] == "What is a matrix?"
    assert any(event.type == StreamEventType.PROGRESS and event.stage == "ideation" for event in bus._history)
    assert "Question 1" in _result(bus)["response"]


@pytest.mark.asyncio
async def test_deep_question_graph_supports_interactive_question_types() -> None:
    model = FakeModel(
        [
            (
                '{"templates":['
                '{"concentration":"gradient descent convergence",'
                '"question_type":"true_false","difficulty":"easy"},'
                '{"concentration":"backpropagation derivative",'
                '"question_type":"fill_blank","difficulty":"medium"}]}'
            ),
            (
                '{"question_type":"true_false","question":"Gradient descent always finds the global optimum.",'
                '"options":null,"correct_answer":"False",'
                '"explanation":"Non-convex losses can have local optima."}'
            ),
            (
                '{"question_type":"fill_blank","question":"Backpropagation computes ____ using the chain rule.",'
                '"options":null,"correct_answer":"gradients",'
                '"explanation":"The chain rule propagates derivatives layer by layer."}'
            ),
        ]
    )
    bus = StreamBus()
    graph = DeepQuestionGraph(model=model, tool_registry=FakeToolRegistry([]))
    context = UnifiedContext(
        user_message="neural network basics",
        config_overrides={"num_questions": 2, "question_type": "mixed"},
    )

    state = await graph.run(context, bus)
    questions = [item["qa_pair"] for item in state["questions"]]

    assert questions[0]["question_type"] == "true_false"
    assert questions[0]["correct_answer"] == "False"
    assert questions[0]["options"] == {"True": "正确", "False": "错误"}
    assert questions[1]["question_type"] == "fill_blank"
    assert "____" in questions[1]["question"]
    assert _result(bus)["summary"]["completed"] == 2


@pytest.mark.asyncio
async def test_deep_research_graph_streams_tool_trace_and_report() -> None:
    registry = FakeToolRegistry(["web_search"])
    model = FakeModel(["agent-native tutoring?", "# Report\n\nReport about agent-native tutoring"])
    bus = StreamBus()
    graph = DeepResearchGraph(model=model, tool_registry=registry)
    context = UnifiedContext(
        user_message="agent-native tutoring",
        enabled_tools=["web_search"],
        config_overrides={
            "mode": "report",
            "depth": "manual",
            "sources": ["web"],
            "confirmed_outline": [
                {
                    "title": "Agent-native tutoring",
                    "overview": "Planner and tool-use loops.",
                    "queries": ["agent-native tutoring"],
                }
            ],
        },
    )

    state = await graph.run(context, bus)

    assert registry.calls == [("web_search", {"query": "agent-native tutoring"})]
    assert state["final_answer"].startswith("# Report")
    assert any(event.type == StreamEventType.PROGRESS and "Searching web" in event.content for event in bus._history)
    assert any(
        event.type == StreamEventType.TOOL_CALL and event.content == "web_search"
        for event in bus._history
    )
    assert _result(bus)["response"] == "# Report\n\nReport about agent-native tutoring"


def test_ng_capability_registry_exposes_builtin_manifests() -> None:
    registry = get_capability_registry()

    assert {
        "chat",
        "deep_question",
        "deep_research",
        "deep_solve",
        "math_animator",
        "visualize",
    }.issubset(set(registry.list_capabilities()))
    manifest = next(item for item in registry.get_manifests() if item["name"] == "deep_solve")
    assert manifest["stages"] == ["planning", "reasoning", "writing"]

