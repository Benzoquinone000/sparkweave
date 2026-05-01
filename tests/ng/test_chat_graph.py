from __future__ import annotations

from types import SimpleNamespace

import pytest

from sparkweave.core.contracts import StreamBus, StreamEventType, UnifiedContext
from sparkweave.core.tool_protocol import ToolResult
from sparkweave.graphs.chat import ChatGraph


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
        return ["echo"]

    def get_tools(self, names):
        return [SimpleNamespace(name=name) for name in names]

    async def execute(self, name, **kwargs):
        self.calls.append((name, kwargs))
        return ToolResult(
            content=f"echoed {kwargs['query']}",
            sources=[{"type": "test"}],
            metadata={"ok": True},
        )


def learner_profile_metadata() -> dict:
    return {
        "learner_profile_context": {
            "available": True,
            "text": "[Learner Profile Context]\n- weak_points: 概念边界不清\n- preferences: 公开视频, 图解",
            "hints": {
                "current_focus": "梯度下降",
                "level": "beginner",
                "time_budget_minutes": 10,
                "preferences": ["公开视频", "图解"],
                "weak_points": ["概念边界不清"],
                "mastery_needs_attention": ["梯度符号"],
                "next_action": {
                    "title": "前测补基：梯度下降的直观理解",
                    "estimated_minutes": 10,
                },
            },
        }
    }


@pytest.mark.asyncio
async def test_chat_graph_runs_without_tools():
    from langchain_core.messages import AIMessage

    bus = StreamBus()
    graph = ChatGraph(
        model=FakeModel([AIMessage(content="Hello from LangGraph.")]),
        tool_registry=FakeToolRegistry(),
    )
    context = UnifiedContext(user_message="hello", enabled_tools=[])

    state = await graph.run(context, bus)

    assert state["final_answer"] == "Hello from LangGraph."
    assert any(event.type == StreamEventType.RESULT for event in bus._history)


@pytest.mark.asyncio
async def test_chat_graph_executes_model_tool_call():
    from langchain_core.messages import AIMessage

    registry = FakeToolRegistry()
    bus = StreamBus()
    graph = ChatGraph(
        model=FakeModel(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "echo",
                            "args": {"query": "langgraph"},
                            "id": "call-1",
                        }
                    ],
                ),
                AIMessage(content="The tool returned echoed langgraph."),
            ]
        ),
        tool_registry=registry,
    )
    context = UnifiedContext(user_message="hello", enabled_tools=["echo"])

    state = await graph.run(context, bus)

    assert state["final_answer"] == "The tool returned echoed langgraph."
    assert registry.calls == [("echo", {"query": "langgraph"})]
    assert any(event.type == StreamEventType.TOOL_CALL for event in bus._history)
    assert any(event.type == StreamEventType.TOOL_RESULT for event in bus._history)


@pytest.mark.asyncio
async def test_chat_graph_coordinator_delegates_visualization_request():
    captured = {}

    async def fake_specialist(capability, context, stream):
        captured["capability"] = capability
        captured["context"] = context
        await stream.content("```mermaid\ngraph LR\n  A --> B\n```", source=capability)
        await stream.result(
            {
                "response": "```mermaid\ngraph LR\n  A --> B\n```",
                "runtime": "langgraph",
            },
            source=capability,
        )
        return {"final_answer": "```mermaid\ngraph LR\n  A --> B\n```"}

    bus = StreamBus()
    graph = ChatGraph(
        model=FakeModel([]),
        tool_registry=FakeToolRegistry(),
        specialist_runner=fake_specialist,
    )
    context = UnifiedContext(
        user_message="请画一个神经网络流程图",
        metadata=learner_profile_metadata(),
    )

    state = await graph.run(context, bus)

    assert captured["capability"] == "visualize"
    assert captured["context"].active_capability == "visualize"
    assert captured["context"].config_overrides["render_mode"] == "mermaid"
    assert captured["context"].config_overrides["learner_profile_hints"]["weak_points"] == ["概念边界不清"]
    assert captured["context"].metadata["delegated_by_coordinator"] == "chat"
    assert state["final_answer"].startswith("```mermaid")
    assert any(event.stage == "coordinating" for event in bus._history)


@pytest.mark.asyncio
async def test_chat_graph_coordinator_delegates_animation_request():
    captured = {}

    async def fake_specialist(capability, context, stream):
        captured["capability"] = capability
        captured["context"] = context
        await stream.result({"response": "animation ready"}, source=capability)
        return {"final_answer": "animation ready"}

    bus = StreamBus()
    graph = ChatGraph(
        model=FakeModel([]),
        tool_registry=FakeToolRegistry(),
        specialist_runner=fake_specialist,
    )
    context = UnifiedContext(
        user_message="请生成一个极限动画讲解",
        metadata=learner_profile_metadata(),
    )

    state = await graph.run(context, bus)

    assert captured["capability"] == "math_animator"
    assert captured["context"].active_capability == "math_animator"
    assert captured["context"].config_overrides["output_mode"] == "video"
    assert "概念边界不清" in captured["context"].config_overrides["style_hint"]
    assert captured["context"].config_overrides["learner_profile_hints"]["preferences"] == ["公开视频", "图解"]
    assert "10 minutes" in captured["context"].config_overrides["style_hint"]
    handoff_events = [
        event for event in bus._history if event.metadata.get("trace_kind") == "agent_handoff"
    ]
    assert handoff_events[-1].metadata["profile_hints_applied"] is True
    assert "weak_points" in handoff_events[-1].metadata["profile_hint_keys"]
    assert state["final_answer"] == "animation ready"


@pytest.mark.asyncio
async def test_chat_graph_coordinator_delegates_external_video_request(monkeypatch):
    async def fake_recommend_learning_videos(**kwargs):
        assert kwargs["topic"] == "recommend video about gradient descent"
        assert kwargs["learner_hints"]["weak_points"] == ["概念边界不清"]
        assert kwargs["learner_hints"]["preferences"] == ["公开视频", "图解"]
        assert "梯度下降" in kwargs["learner_hints"]["concepts"]
        assert "profile_context" in kwargs["learner_hints"]
        return {
            "success": True,
            "render_type": "external_video",
            "response": "Found 1 learning video.",
            "videos": [
                {
                    "title": "Gradient descent explained",
                    "url": "https://www.youtube.com/watch?v=abc123",
                    "platform": "YouTube",
                    "embed_url": "https://www.youtube.com/embed/abc123",
                    "why_recommended": "Beginner friendly.",
                }
            ],
            "learner_profile_hints": kwargs["learner_hints"],
        }

    monkeypatch.setattr(
        "sparkweave.services.video_search.recommend_learning_videos",
        fake_recommend_learning_videos,
    )

    bus = StreamBus()
    graph = ChatGraph(
        model=FakeModel([]),
        tool_registry=FakeToolRegistry(),
    )
    context = UnifiedContext(
        user_message="recommend video about gradient descent",
        metadata=learner_profile_metadata(),
    )

    state = await graph.run(context, bus)

    assert state["final_answer"] == "Found 1 learning video."
    result_events = [event for event in bus._history if event.type == StreamEventType.RESULT]
    assert result_events[-1].source == "external_video_search"
    assert result_events[-1].metadata["render_type"] == "external_video"
    assert result_events[-1].metadata["videos"][0]["platform"] == "YouTube"
    assert result_events[-1].metadata["learner_profile_hints"]["weak_points"] == ["概念边界不清"]


@pytest.mark.asyncio
async def test_chat_graph_coordinator_delegates_questions_with_profile_guidance():
    captured = {}

    async def fake_specialist(capability, context, stream):
        captured["capability"] = capability
        captured["context"] = context
        await stream.result({"response": "quiz ready"}, source=capability)
        return {"final_answer": "quiz ready"}

    bus = StreamBus()
    graph = ChatGraph(
        model=FakeModel([]),
        tool_registry=FakeToolRegistry(),
        specialist_runner=fake_specialist,
    )
    context = UnifiedContext(
        user_message="请生成3道梯度下降选择题",
        metadata=learner_profile_metadata(),
    )

    state = await graph.run(context, bus)

    assert captured["capability"] == "deep_question"
    assert captured["context"].config_overrides["question_type"] == "choice"
    assert captured["context"].config_overrides["num_questions"] == 3
    assert "概念边界不清" in captured["context"].config_overrides["preference"]
    assert "前测补基" in captured["context"].config_overrides["preference"]
    assert state["final_answer"] == "quiz ready"


@pytest.mark.asyncio
async def test_chat_graph_coordinator_delegates_research_with_default_tools():
    captured = {}

    async def fake_specialist(capability, context, stream):
        captured["capability"] = capability
        captured["context"] = context
        await stream.result({"response": "path ready"}, source=capability)
        return {"final_answer": "path ready"}

    bus = StreamBus()
    graph = ChatGraph(
        model=FakeModel([]),
        tool_registry=FakeToolRegistry(),
        specialist_runner=fake_specialist,
    )
    context = UnifiedContext(
        user_message="请为机器学习规划学习路径",
        enabled_tools=[],
        knowledge_bases=["course"],
    )

    state = await graph.run(context, bus)

    assert captured["capability"] == "deep_research"
    assert captured["context"].active_capability == "deep_research"
    assert captured["context"].enabled_tools == ["rag", "web_search"]
    assert captured["context"].config_overrides["mode"] == "learning_path"
    assert captured["context"].config_overrides["sources"] == ["kb", "web"]
    assert state["final_answer"] == "path ready"


@pytest.mark.asyncio
async def test_chat_graph_coordinator_can_be_disabled_by_config():
    from langchain_core.messages import AIMessage

    bus = StreamBus()
    graph = ChatGraph(
        model=FakeModel([AIMessage(content="Stayed in chat.")]),
        tool_registry=FakeToolRegistry(),
    )
    context = UnifiedContext(
        user_message="请画一个神经网络流程图",
        config_overrides={"auto_delegate": False},
    )

    state = await graph.run(context, bus)

    assert state["final_answer"] == "Stayed in chat."


