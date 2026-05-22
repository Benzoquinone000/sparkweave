from __future__ import annotations

from types import SimpleNamespace

import pytest

from sparkweave.core.contracts import StreamBus, StreamEventType, UnifiedContext
from sparkweave.core.tool_protocol import ToolResult
from sparkweave.graphs.chat import MAX_PARALLEL_TOOL_CALLS, ChatGraph


class FakeModel:
    def __init__(self, responses):
        self.responses = list(responses)
        self.bound_tools = None
        self.seen_messages = []

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self

    async def ainvoke(self, _messages):
        self.seen_messages.append(list(_messages))
        return self.responses.pop(0)


class FakeCoordinatorModel:
    def __init__(self, payload: str) -> None:
        self.payload = payload
        self.seen_messages = []

    async def ainvoke(self, messages):
        self.seen_messages.append(list(messages))
        return SimpleNamespace(content=self.payload)


class FakeToolRegistry:
    def __init__(self):
        self.calls = []

    def names(self):
        return ["echo"]

    def get_tools(self, names):
        return [SimpleNamespace(name=name) for name in names]

    async def execute(self, name, **kwargs):
        self.calls.append((name, kwargs))
        if name == "external_video_search":
            return ToolResult(
                content="Found 1 learning video.",
                sources=[{"type": "external_video", "url": "https://www.youtube.com/watch?v=abc123"}],
                metadata={
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
                    "learner_profile_hints": kwargs.get("learner_hints") or {},
                    "agent_chain": [],
                    "tool_chain": [{"label": "精选视频工具"}],
                },
            )
        if name == "external_image_search":
            return ToolResult(
                content="Found 1 learning image.",
                sources=[{"type": "external_image", "url": "https://example.com/page", "image_url": "https://example.com/image.png"}],
                metadata={
                    "success": True,
                    "render_type": "external_image",
                    "response": "Found 1 learning image.",
                    "images": [
                        {
                            "title": "Gradient descent diagram",
                            "url": "https://example.com/page",
                            "image_url": "https://example.com/image.png",
                            "source": "Example",
                            "why_recommended": "Visual reference.",
                        }
                    ],
                    "learner_profile_hints": kwargs.get("learner_hints") or {},
                    "agent_chain": [],
                    "tool_chain": [{"label": "精选图片工具"}],
                },
            )
        return ToolResult(
            content=f"echoed {kwargs['query']}",
            sources=[{"type": "test"}],
            metadata={"ok": True},
        )


class FakeExternalVideoToolRegistry(FakeToolRegistry):
    def names(self):
        return ["external_video_search"]

    async def execute(self, name, **kwargs):
        self.calls.append((name, kwargs))
        return ToolResult(
            content="Found 1 learning video.",
            sources=[{"type": "external_video", "url": "https://www.youtube.com/watch?v=abc123"}],
            metadata={
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
                "learner_profile_hints": kwargs.get("learner_hints") or {},
                "agent_chain": [],
                "tool_chain": [{"label": "精选视频工具"}],
            },
        )


class FakeRAGToolRegistry(FakeToolRegistry):
    def names(self):
        return ["rag"]

    async def execute(self, name, **kwargs):
        self.calls.append((name, kwargs))
        return ToolResult(
            content=f"ragged {kwargs['query']}",
            sources=[{"type": "rag", "chunk_id": "chunk-1"}],
            metadata={"ok": True, "retrieval_profile": kwargs.get("retrieval_profile")},
        )


class FakeCanvasToolRegistry(FakeToolRegistry):
    def names(self):
        return ["canvas"]

    async def execute(self, name, **kwargs):
        self.calls.append((name, kwargs))
        return ToolResult(
            content=f"Canvas document ready: {kwargs['title']}",
            metadata={
                "render_type": "canvas_document",
                "tool_name": "canvas",
                "canvas_document": {
                    "title": kwargs["title"],
                    "content": kwargs["content"],
                    "operation": kwargs.get("operation", "create"),
                },
            },
        )


class FakeCommonToolRegistry(FakeToolRegistry):
    def names(self):
        return ["canvas", "rag", "web_search"]

    def get_tools(self, names):
        return [SimpleNamespace(name=name) for name in names]


class ProfileSelectingRAGModel:
    """Deterministic stand-in for a tool-calling agent.

    The model validates that the RAG tool exposes `retrieval_profile`, sees the
    system-prompt rubric, then emits the profile it would choose for the query.
    """

    def __init__(self, expected_profile: str) -> None:
        self.expected_profile = expected_profile
        self.bound_tools = []
        self.seen_messages = []

    def bind_tools(self, tools):
        self.bound_tools = list(tools)
        return self

    async def ainvoke(self, messages):
        from langchain_core.messages import AIMessage

        self.seen_messages.append(list(messages))
        if any(getattr(message, "type", "") == "tool" for message in messages):
            return AIMessage(content=f"Used {self.expected_profile} retrieval.")

        assert self.bound_tools
        rag_tool = self.bound_tools[0]
        schema = rag_tool.args_schema.model_json_schema()
        assert "retrieval_profile" in schema["properties"]
        assert set(schema["properties"]["retrieval_profile"]["enum"]) >= {
            "fast",
            "concept",
            "exact",
            "code",
            "formula",
            "guide",
            "broad",
        }
        system_prompt = str(getattr(messages[0], "content", ""))
        assert "When you call the `rag` tool" in system_prompt
        assert "retrieval_profile" in system_prompt

        query = str(getattr(messages[-1], "content", ""))
        return AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "rag",
                    "args": {
                        "query": query,
                        "retrieval_profile": self.expected_profile,
                    },
                    "id": f"rag-{self.expected_profile}",
                }
            ],
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
                "preferred_resource": "curated_public_video",
                "preferences": ["公开视频", "图解"],
                "weak_points": ["概念边界不清"],
                "mastery_needs_attention": ["梯度符号"],
                "next_action": {
                    "title": "前测补基：梯度下降的直观理解",
                    "summary": "先找精选公开视频，再做三道小题。",
                    "suggested_prompt": "围绕概念边界不清安排 10 分钟补基任务，先找精选公开视频，再用 3 道小题确认理解。",
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
async def test_chat_graph_exposes_canvas_as_tool_result_metadata():
    from langchain_core.messages import AIMessage

    registry = FakeCanvasToolRegistry()
    bus = StreamBus()
    graph = ChatGraph(
        model=FakeModel(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "canvas",
                            "args": {
                                "title": "Gradient descent study plan",
                                "content": "# Gradient descent study plan\n\n- Learn the loss curve.",
                                "operation": "create",
                            },
                            "id": "canvas-call-1",
                        }
                    ],
                ),
                AIMessage(content="I opened the study plan in the canvas."),
            ]
        ),
        tool_registry=registry,
        coordinator_enabled=False,
    )
    context = UnifiedContext(user_message="write a study plan draft", enabled_tools=["canvas"])

    state = await graph.run(context, bus)

    assert state["final_answer"] == "I opened the study plan in the canvas."
    assert registry.calls[0][0] == "canvas"
    tool_result_events = [event for event in bus._history if event.type == StreamEventType.TOOL_RESULT]
    assert tool_result_events[-1].metadata["tool_name"] == "canvas"
    assert tool_result_events[-1].metadata["result_metadata"]["render_type"] == "canvas_document"
    assert "loss curve" in tool_result_events[-1].metadata["result_metadata"]["canvas_document"]["content"]


@pytest.mark.asyncio
async def test_chat_graph_direct_answer_constraint_clears_enabled_tools():
    from langchain_core.messages import AIMessage

    model = FakeModel([AIMessage(content="Gradient descent moves parameters downhill on the loss.")])
    registry = FakeCommonToolRegistry()
    bus = StreamBus()
    graph = ChatGraph(model=model, tool_registry=registry)
    context = UnifiedContext(
        user_message="直接回答什么是梯度下降，不要用工具",
        enabled_tools=["canvas", "rag", "web_search"],
        knowledge_bases=["course"],
    )

    state = await graph.run(context, bus)

    assert state["final_answer"] == "Gradient descent moves parameters downhill on the loss."
    assert model.bound_tools is None
    assert registry.calls == []
    assert not any(event.type == StreamEventType.TOOL_CALL for event in bus._history)


@pytest.mark.asyncio
async def test_chat_graph_no_canvas_constraint_removes_canvas_tool_only():
    from langchain_core.messages import AIMessage

    model = FakeModel([AIMessage(content="Gradient descent is an iterative optimization method.")])
    registry = FakeCommonToolRegistry()
    bus = StreamBus()
    graph = ChatGraph(model=model, tool_registry=registry)
    context = UnifiedContext(
        user_message="详细解释梯度下降，不要打开画布",
        enabled_tools=["canvas", "rag", "web_search"],
        knowledge_bases=["course"],
    )

    await graph.run(context, bus)

    assert model.bound_tools
    assert [tool.name for tool in model.bound_tools] == ["rag", "web_search"]
    system_prompt = model.seen_messages[0][0].content
    assert "The canvas tool is not enabled for this turn." in system_prompt
    assert registry.calls == []


@pytest.mark.asyncio
async def test_chat_graph_no_retrieval_constraint_removes_search_tools():
    from langchain_core.messages import AIMessage

    model = FakeModel([AIMessage(content="I will answer without searching external resources.")])
    registry = FakeCommonToolRegistry()
    bus = StreamBus()
    graph = ChatGraph(model=model, tool_registry=registry)
    context = UnifiedContext(
        user_message="Find a public video about gradient descent, no search",
        enabled_tools=["canvas", "rag", "web_search"],
        knowledge_bases=["course"],
    )

    await graph.run(context, bus)

    assert model.bound_tools
    assert [tool.name for tool in model.bound_tools] == ["canvas"]
    system_prompt = model.seen_messages[0][0].content
    assert "The rag tool is not enabled for this turn." in system_prompt
    assert registry.calls == []


@pytest.mark.asyncio
async def test_chat_graph_skips_tool_call_not_enabled_for_turn():
    from langchain_core.messages import AIMessage, ToolMessage

    model = FakeModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "canvas",
                        "args": {
                            "title": "Gradient descent plan",
                            "content": "# Plan",
                        },
                        "id": "canvas-disabled-1",
                    }
                ],
            ),
            AIMessage(content="I will answer in chat without opening the canvas."),
        ]
    )
    registry = FakeCommonToolRegistry()
    bus = StreamBus()
    graph = ChatGraph(model=model, tool_registry=registry, coordinator_enabled=False)
    context = UnifiedContext(
        user_message="Explain gradient descent in chat",
        enabled_tools=["rag"],
        knowledge_bases=["course"],
        config_overrides={"prefetch_rag": False},
    )

    state = await graph.run(context, bus)

    assert state["final_answer"] == "I will answer in chat without opening the canvas."
    assert model.bound_tools
    assert [tool.name for tool in model.bound_tools] == ["rag"]
    assert registry.calls == []
    assert not any(event.type == StreamEventType.TOOL_CALL for event in bus._history)
    warning_events = [
        event
        for event in bus._history
        if event.metadata.get("reason") == "disabled_tool_call"
    ]
    assert warning_events
    assert warning_events[-1].metadata["tool_name"] == "canvas"
    second_call_messages = model.seen_messages[-1]
    assert any(
        isinstance(message, ToolMessage)
        and message.tool_call_id == "canvas-disabled-1"
        and "not enabled" in str(message.content)
        for message in second_call_messages
    )


@pytest.mark.asyncio
async def test_chat_graph_sends_tool_messages_for_overflow_tool_calls():
    from langchain_core.messages import AIMessage, ToolMessage

    tool_calls = [
        {
            "name": "echo",
            "args": {"query": f"query-{index}"},
            "id": f"echo-{index}",
        }
        for index in range(MAX_PARALLEL_TOOL_CALLS + 2)
    ]
    model = FakeModel(
        [
            AIMessage(content="", tool_calls=tool_calls),
            AIMessage(content="I used the available tool results."),
        ]
    )
    registry = FakeToolRegistry()
    bus = StreamBus()
    graph = ChatGraph(model=model, tool_registry=registry, coordinator_enabled=False)
    context = UnifiedContext(
        user_message="Use many echo tools",
        enabled_tools=["echo"],
    )

    state = await graph.run(context, bus)

    assert state["final_answer"] == "I used the available tool results."
    assert len(registry.calls) == MAX_PARALLEL_TOOL_CALLS
    warning_events = [
        event
        for event in bus._history
        if event.metadata.get("reason") == "too_many_tool_calls"
    ]
    assert warning_events
    second_call_tool_messages = [
        message for message in model.seen_messages[-1] if isinstance(message, ToolMessage)
    ]
    assert len(second_call_tool_messages) == MAX_PARALLEL_TOOL_CALLS + 2
    assert any(
        message.tool_call_id == f"echo-{MAX_PARALLEL_TOOL_CALLS + 1}"
        and "parallel limit" in str(message.content)
        for message in second_call_tool_messages
    )


@pytest.mark.asyncio
async def test_chat_graph_preserves_agent_selected_rag_retrieval_profile():
    from langchain_core.messages import AIMessage

    registry = FakeRAGToolRegistry()
    bus = StreamBus()
    graph = ChatGraph(
        model=FakeModel(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "rag",
                            "args": {
                                "query": "derive the cross entropy gradient",
                                "retrieval_profile": "formula",
                            },
                            "id": "rag-call-1",
                        }
                    ],
                ),
                AIMessage(content="The formula evidence is ready."),
            ]
        ),
        tool_registry=registry,
    )
    context = UnifiedContext(
        session_id="session-1",
        user_message="derive the cross entropy gradient",
        enabled_tools=["rag"],
        knowledge_bases=["course"],
        config_overrides={"prefetch_rag": False, "retrieval_profile": "concept"},
        metadata={"turn_id": "turn-1"},
    )

    state = await graph.run(context, bus)

    assert state["final_answer"] == "The formula evidence is ready."
    assert len(registry.calls) == 1
    name, args = registry.calls[0]
    assert name == "rag"
    assert args["query"] == "derive the cross entropy gradient"
    assert args["retrieval_profile"] == "formula"
    assert args["kb_name"] == "course"
    tool_call_events = [event for event in bus._history if event.type == StreamEventType.TOOL_CALL]
    assert tool_call_events[-1].metadata["args"]["retrieval_profile"] == "formula"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "expected_profile"),
    [
        ("PCA", "fast"),
        ("What is gradient descent?", "concept"),
        ("Which chapter defines gradient descent?", "exact"),
        ("Explain train_step(batch) implementation", "code"),
        ("How do we derive x^2 = 4?", "formula"),
        ("Build a learning path for PCA", "guide"),
        ("Compare and summarize PCA and SVD", "broad"),
    ],
)
async def test_chat_graph_agent_can_select_rag_profile_from_tool_schema_and_prompt(
    monkeypatch,
    query: str,
    expected_profile: str,
):
    from sparkweave.tools.registry import LangChainToolRegistry

    captured: dict[str, object] = {}

    async def fake_rag_search(**kwargs):
        captured.update(kwargs)
        return {
            "success": True,
            "content": f"retrieved with {kwargs.get('retrieval_profile')}",
            "sources": [{"title": "demo", "chunk_id": "chunk-1"}],
        }

    monkeypatch.setattr("sparkweave.services.rag.rag_search", fake_rag_search)
    model = ProfileSelectingRAGModel(expected_profile)
    bus = StreamBus()
    graph = ChatGraph(
        model=model,
        tool_registry=LangChainToolRegistry(),
        coordinator_enabled=False,
    )
    context = UnifiedContext(
        session_id="session-1",
        user_message=query,
        enabled_tools=["rag"],
        knowledge_bases=["course"],
        config_overrides={"prefetch_rag": False},
        metadata={"turn_id": "turn-1"},
    )

    state = await graph.run(context, bus)

    assert state["final_answer"] == f"Used {expected_profile} retrieval."
    assert captured["query"] == query
    assert captured["kb_name"] == "course"
    assert captured["retrieval_profile"] == expected_profile
    tool_call_events = [event for event in bus._history if event.type == StreamEventType.TOOL_CALL]
    assert tool_call_events[-1].metadata["args"]["retrieval_profile"] == expected_profile


@pytest.mark.asyncio
async def test_chat_graph_prefetches_rag_context_before_model(monkeypatch):
    from langchain_core.messages import AIMessage

    captured = {}

    async def fake_rag_search(**kwargs):
        captured.update(kwargs)
        event_sink = kwargs.get("event_sink")
        if event_sink is not None:
            await event_sink("status", "Retrieval policy: auto", {"retrieval_profile": "auto"})
        return {
            "success": True,
            "content": "MP model evidence: Warren McCulloch and Walter Pitts.",
            "sources": [{"title": "Deep Learning Chapter 1", "chunk_id": "chunk-1"}],
        }

    monkeypatch.setattr("sparkweave.services.rag.rag_search", fake_rag_search)
    model = FakeModel([AIMessage(content="Grounded answer.")])
    bus = StreamBus()
    graph = ChatGraph(model=model, tool_registry=FakeToolRegistry())
    context = UnifiedContext(
        session_id="session-1",
        user_message="What is the MP model?",
        enabled_tools=["rag"],
        knowledge_bases=["course"],
        config_overrides={
            "retrieval_profile": "auto",
            "retrieval_mode": "hybrid",
            "top_k": 5,
            "candidate_top_k": 15,
            "reranker": "keyword",
            "max_context_chars": 1200,
            "agentic_rag": "auto",
            "query_transform": "hyde",
            "agentic_max_subqueries": 2,
            "agentic_max_context_chars": 5000,
            "agentic_max_sources": 8,
            "agentic_min_relevant_coverage_ratio": 0.67,
        },
        metadata={"turn_id": "turn-1"},
    )

    state = await graph.run(context, bus)

    assert state["final_answer"] == "Grounded answer."
    assert captured["query"] == "What is the MP model?"
    assert captured["kb_name"] == "course"
    assert captured["retrieval_profile"] == "auto"
    assert captured["retrieval_mode"] == "hybrid"
    assert captured["top_k"] == 5
    assert captured["candidate_top_k"] == 15
    assert captured["reranker"] == "keyword"
    assert captured["agentic_rag"] == "auto"
    assert captured["query_transform"] == "hyde"
    assert captured["agentic_max_subqueries"] == 2
    assert captured["agentic_max_context_chars"] == 5000
    assert captured["agentic_max_sources"] == 8
    assert captured["agentic_min_relevant_coverage_ratio"] == 0.67

    system_prompt = model.seen_messages[0][0].content
    assert "Retrieved knowledge base context from `course`" in system_prompt
    assert "Warren McCulloch and Walter Pitts" in system_prompt

    source_events = [event for event in bus._history if event.type == StreamEventType.SOURCES]
    assert source_events
    assert source_events[0].metadata["sources"][0]["type"] == "rag"
    assert source_events[0].metadata["sources"][0]["kb_name"] == "course"
    result = [event for event in bus._history if event.type == StreamEventType.RESULT][-1]
    assert result.metadata["tool_traces"][0]["id"] == "rag-prefetch"
    assert result.metadata["tool_traces"][0]["metadata"]["prefetch"] is True
    tool_result = [
        event
        for event in bus._history
        if event.type == StreamEventType.TOOL_RESULT
        and event.metadata.get("tool_call_id") == "rag-prefetch"
    ][0]
    assert tool_result.metadata["result_metadata"]["prefetch"] is True
    assert tool_result.metadata["result_metadata"]["kb_name"] == "course"


@pytest.mark.asyncio
async def test_chat_graph_prefetch_rag_can_be_disabled(monkeypatch):
    from langchain_core.messages import AIMessage

    called = False

    async def fake_rag_search(**_kwargs):
        nonlocal called
        called = True
        return {"content": "should not be used", "sources": []}

    monkeypatch.setattr("sparkweave.services.rag.rag_search", fake_rag_search)
    model = FakeModel([AIMessage(content="No prefetch.")])
    bus = StreamBus()
    graph = ChatGraph(model=model, tool_registry=FakeToolRegistry())
    context = UnifiedContext(
        user_message="What is in the KB?",
        enabled_tools=["rag"],
        knowledge_bases=["course"],
        config_overrides={"prefetch_rag": False},
    )

    await graph.run(context, bus)

    assert called is False
    system_prompt = model.seen_messages[0][0].content
    assert "Retrieved knowledge base context" not in system_prompt
    assert not any(event.metadata.get("prefetch") is True for event in bus._history)


@pytest.mark.asyncio
async def test_chat_graph_injects_canvas_context_into_prompt():
    from langchain_core.messages import AIMessage

    model = FakeModel([AIMessage(content="已更新画布草稿。")])
    bus = StreamBus()
    graph = ChatGraph(model=model, tool_registry=FakeToolRegistry(), coordinator_enabled=False)
    context = UnifiedContext(
        user_message="润色这份草稿",
        enabled_tools=[],
        metadata={
            "canvas_context": {
                "title": "梯度下降解释草稿",
                "content": "# 梯度下降解释草稿\n\n已补充：学习率控制每一步的步长。",
            }
        },
    )

    await graph.run(context, bus)

    system_prompt = model.seen_messages[0][0].content
    assert "Canvas context:" in system_prompt
    assert "梯度下降解释草稿" in system_prompt
    assert "学习率控制每一步的步长" in system_prompt


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
    assert handoff_events[-1].metadata["collaboration_route_version"] == 1
    route = handoff_events[-1].metadata["collaboration_route"]
    assert route[0]["label"] == "学习画像智能体"
    assert any(item["label"] == "分镜智能体" for item in route)
    assert "Math Animation Agent" in handoff_events[-1].metadata["collaboration_summary"]
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
    assert result_events[-1].source == "chat"
    assert result_events[-1].metadata["render_type"] == "external_video"
    assert result_events[-1].metadata["videos"][0]["platform"] == "YouTube"
    assert result_events[-1].metadata["learner_profile_hints"]["weak_points"] == ["概念边界不清"]
    assert result_events[-1].metadata["tool_name"] == "external_video_search"
    assert result_events[-1].metadata["agent_chain"] == []
    assert result_events[-1].metadata["orchestration_mode"] == "direct_tool"
    assert result_events[-1].metadata["selected_route"] == "external_video_search"
    assert result_events[-1].metadata["direct_tool"] == "external_video_search"
    assert any(item["label"] == "视频检索智能体" for item in result_events[-1].metadata["collaboration_route"])
    assert "Curated Video Search Tool" in result_events[-1].metadata["collaboration_summary"]


@pytest.mark.asyncio
async def test_chat_graph_coordinator_delegates_external_image_request():
    bus = StreamBus()
    graph = ChatGraph(
        model=FakeModel([]),
        tool_registry=FakeToolRegistry(),
    )
    context = UnifiedContext(
        user_message="帮我找几张梯度下降示意图",
        metadata=learner_profile_metadata(),
    )

    state = await graph.run(context, bus)

    assert state["final_answer"] == "Found 1 learning image."
    coordinator_events = [
        event for event in bus._history if event.metadata.get("trace_kind") == "coordinator_decision"
    ]
    assert coordinator_events[-1].metadata["orchestration_mode"] == "direct_tool"
    assert coordinator_events[-1].metadata["selected_route"] == "external_image_search"
    assert coordinator_events[-1].metadata["direct_tool"] == "external_image_search"
    result_events = [event for event in bus._history if event.type == StreamEventType.RESULT]
    assert result_events[-1].source == "chat"
    assert result_events[-1].metadata["render_type"] == "external_image"
    assert result_events[-1].metadata["images"][0]["image_url"] == "https://example.com/image.png"
    assert result_events[-1].metadata["tool_name"] == "external_image_search"
    assert result_events[-1].metadata["agent_chain"] == []
    assert result_events[-1].metadata["orchestration_mode"] == "direct_tool"
    assert result_events[-1].metadata["selected_route"] == "external_image_search"
    assert result_events[-1].metadata["direct_tool"] == "external_image_search"
    assert any(item["label"] == "图片检索智能体" for item in result_events[-1].metadata["collaboration_route"])


@pytest.mark.asyncio
async def test_chat_graph_profile_guided_next_step_routes_to_preferred_direct_tool():
    bus = StreamBus()
    graph = ChatGraph(
        model=FakeModel([]),
        tool_registry=FakeToolRegistry(),
    )
    context = UnifiedContext(
        user_message="继续学习",
        metadata=learner_profile_metadata(),
    )

    state = await graph.run(context, bus)

    assert state["final_answer"] == "Found 1 learning video."
    result_events = [event for event in bus._history if event.type == StreamEventType.RESULT]
    assert result_events[-1].source == "chat"
    assert result_events[-1].metadata["tool_name"] == "external_video_search"
    assert result_events[-1].metadata["agent_chain"] == []
    assert result_events[-1].metadata["orchestration_mode"] == "direct_tool"
    assert result_events[-1].metadata["selected_route"] == "external_video_search"
    assert result_events[-1].metadata["direct_tool"] == "external_video_search"
    assert result_events[-1].metadata["collaboration_route"][0]["label"] == "学习画像智能体"
    assert any(item["label"] == "视频检索智能体" for item in result_events[-1].metadata["collaboration_route"])
    handoff_events = [
        event for event in bus._history if event.metadata.get("trace_kind") == "coordinator_decision"
    ]
    assert handoff_events[-1].metadata["selected_route"] == "external_video_search"
    assert handoff_events[-1].metadata["orchestration_mode"] == "direct_tool"
    assert "preferred_resource" in handoff_events[-1].metadata["profile_hint_keys"]
    assert state["final_answer"] == "Found 1 learning video."


def test_chat_graph_distinguishes_video_search_from_video_generation():
    assert ChatGraph._looks_like_external_video_request("帮我找一个视频讲解梯度下降")
    assert ChatGraph._looks_like_external_video_request("推荐B站公开课，适合零基础")
    assert ChatGraph._looks_like_external_video_request("有没有网课视频可以补一下公式含义")
    assert ChatGraph._looks_like_external_video_request("Show me a YouTube lesson link for backpropagation")
    assert not ChatGraph._looks_like_external_video_request("请生成一个视频讲解梯度下降")
    assert not ChatGraph._looks_like_external_video_request("用 Manim 制作视频演示极限")


def test_chat_graph_distinguishes_image_search_from_image_generation():
    assert ChatGraph._looks_like_external_image_request("帮我找几张梯度下降示意图")
    assert ChatGraph._looks_like_external_image_request("find an image reference for gradient descent")
    assert ChatGraph._looks_like_external_image_request("Show me an image diagram for gradient descent")
    assert not ChatGraph._looks_like_external_image_request("请画一个梯度下降流程图")
    assert not ChatGraph._looks_like_external_image_request("Show me a diagram of gradient descent")
    assert not ChatGraph._looks_like_external_image_request("generate a diagram for gradient descent")


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


@pytest.mark.asyncio
async def test_chat_graph_uses_llm_intent_classifier_for_ambiguous_request():
    captured = {}

    async def fake_specialist(capability, context, stream):
        captured["capability"] = capability
        captured["context"] = context
        await stream.result({"response": "path ready"}, source=capability)
        return {"final_answer": "path ready"}

    coordinator_model = FakeCoordinatorModel(
        """
        {
          "capability": "deep_research",
          "confidence": 0.86,
          "reason": "The learner asks for an organized learning plan.",
          "rewritten_user_message": "围绕梯度下降整理一条学习路径",
          "tools": ["rag", "web_search"],
          "config": {"mode": "learning_path", "sources": ["kb", "web"]},
          "profile_hints_applied": true
        }
        """
    )
    bus = StreamBus()
    graph = ChatGraph(
        model=FakeModel([]),
        coordinator_model=coordinator_model,
        tool_registry=FakeToolRegistry(),
        specialist_runner=fake_specialist,
    )
    context = UnifiedContext(
        user_message="帮我系统理解梯度下降",
        enabled_tools=["rag"],
        knowledge_bases=["course"],
        config_overrides={"coordinator_llm": True},
        metadata=learner_profile_metadata(),
    )

    state = await graph.run(context, bus)

    assert captured["capability"] == "deep_research"
    assert captured["context"].user_message == "围绕梯度下降整理一条学习路径"
    assert captured["context"].enabled_tools == ["rag", "web_search"]
    assert captured["context"].config_overrides["mode"] == "learning_path"
    assert captured["context"].config_overrides["llm_classified"] is True
    assert captured["context"].config_overrides["profile_guided"] is True
    assert "Return strict JSON only" in coordinator_model.seen_messages[0][0].content
    assert state["final_answer"] == "path ready"


