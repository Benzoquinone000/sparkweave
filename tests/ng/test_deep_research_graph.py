from __future__ import annotations

from pathlib import Path

import pytest

from sparkweave.core.contracts import StreamBus, StreamEventType, UnifiedContext
from sparkweave.core.tool_protocol import ToolResult
from sparkweave.graphs.deep_research import DeepResearchGraph


class FakeModel:
    def __init__(self, responses):
        self.responses = list(responses)

    async def ainvoke(self, _messages):
        from langchain_core.messages import AIMessage

        return AIMessage(content=self.responses.pop(0))


class FakeToolRegistry:
    def __init__(self, names=None):
        self._names = list(names or [])
        self.calls = []

    def names(self):
        return self._names

    async def execute(self, name, **kwargs):
        self.calls.append((name, kwargs))
        return ToolResult(
            content=f"{name} evidence for {kwargs.get('query')}",
            sources=[{"type": "web", "url": "https://example.test", "title": "Example"}],
            metadata={"ok": True},
        )


@pytest.mark.asyncio
async def test_deep_research_graph_writes_report_without_external_sources():
    bus = StreamBus()
    graph = DeepResearchGraph(
        model=FakeModel(
            [
                "How should retrieval augmented generation be evaluated?",
                '{"subtopics":[{"title":"Evaluation metrics","overview":"Measure answer quality.","queries":["RAG evaluation metrics"]}]}',
                "# RAG Evaluation\n\nUse retrieval quality and answer faithfulness metrics.",
            ]
        ),
        tool_registry=FakeToolRegistry(),
    )
    context = UnifiedContext(
        user_message="RAG evaluation",
        active_capability="deep_research",
        enabled_tools=[],
    )

    state = await graph.run(context, bus)

    assert state["research_topic"] == "How should retrieval augmented generation be evaluated?"
    assert state["evidence"] == []
    assert state["final_answer"].startswith("# RAG Evaluation")
    assert any(event.type == StreamEventType.RESULT for event in bus._history)
    assert not any(event.type == StreamEventType.TOOL_CALL for event in bus._history)


@pytest.mark.asyncio
async def test_deep_research_graph_executes_selected_web_source():
    registry = FakeToolRegistry(names=["web_search"])
    bus = StreamBus()
    graph = DeepResearchGraph(
        model=FakeModel(
            [
                "What is agentic RAG and when is it useful?",
                "# Agentic RAG\n\nAgentic RAG combines retrieval with planning loops.",
            ]
        ),
        tool_registry=registry,
    )
    context = UnifiedContext(
        user_message="agentic RAG",
        active_capability="deep_research",
        enabled_tools=["web_search"],
        config_overrides={
            "mode": "report",
            "sources": ["web"],
            "depth": "manual",
            "manual_subtopics": 1,
            "confirmed_outline": [
                {
                    "title": "Agentic RAG patterns",
                    "overview": "Planner and tool-use loops.",
                    "queries": ["agentic RAG patterns"],
                }
            ],
        },
    )

    state = await graph.run(context, bus)

    assert registry.calls == [("web_search", {"query": "agentic RAG patterns"})]
    assert state["evidence"][0]["source"] == "web"
    assert state["evidence"][0]["success"] is True
    assert state["final_answer"].startswith("# Agentic RAG")
    assert any(event.type == StreamEventType.TOOL_CALL for event in bus._history)
    assert any(event.type == StreamEventType.TOOL_RESULT for event in bus._history)
    assert any(event.type == StreamEventType.SOURCES for event in bus._history)


@pytest.mark.asyncio
async def test_deep_research_graph_returns_outline_preview_for_explicit_config(
    monkeypatch,
    tmp_path,
):
    checkpoint_db = tmp_path / "checkpoints.sqlite"
    monkeypatch.setenv("SPARKWEAVE_NG_CHECKPOINT_DB", str(checkpoint_db))
    registry = FakeToolRegistry(names=["web_search"])
    bus = StreamBus()
    graph = DeepResearchGraph(
        model=FakeModel(
            [
                "What is agentic RAG and when is it useful?",
                '{"subtopics":[{"title":"Agentic RAG patterns","overview":"Planner and tool-use loops.","queries":["agentic RAG patterns"]}]}',
            ]
        ),
        tool_registry=registry,
    )
    context = UnifiedContext(
        user_message="agentic RAG",
        active_capability="deep_research",
        enabled_tools=["web_search"],
        config_overrides={
            "mode": "report",
            "sources": ["web"],
            "depth": "manual",
            "manual_subtopics": 1,
        },
    )

    state = await graph.run(context, bus)

    assert registry.calls == []
    assert state["final_answer"].startswith("**Research Outline")
    assert not any(event.type == StreamEventType.TOOL_CALL for event in bus._history)
    result_events = [event for event in bus._history if event.type == StreamEventType.RESULT]
    assert len(result_events) == 1
    metadata = result_events[0].metadata
    assert metadata["outline_preview"] is True
    assert metadata["sub_topics"] == [
        {
            "title": "Agentic RAG patterns",
            "overview": "Planner and tool-use loops.",
        }
    ]
    assert metadata["research_config"] == {
        "mode": "report",
        "depth": "manual",
        "sources": ["web"],
        "manual_subtopics": 1,
    }
    assert metadata["checkpoint_id"].startswith("deep_research:")
    assert metadata["checkpoint"]["next"] == "researching"
    assert checkpoint_db.exists()
    assert checkpoint_db.stat().st_size > 0


@pytest.mark.asyncio
async def test_deep_research_graph_resumes_from_checkpoint_after_outline_confirmation(
    monkeypatch,
    tmp_path,
):
    checkpoint_db = tmp_path / "checkpoints.sqlite"
    monkeypatch.setenv("SPARKWEAVE_NG_CHECKPOINT_DB", str(checkpoint_db))
    preview_bus = StreamBus()
    preview_graph = DeepResearchGraph(
        model=FakeModel(
            [
                "What is agentic RAG and when is it useful?",
                '{"subtopics":[{"title":"Agentic RAG patterns","overview":"Planner and tool-use loops.","queries":["agentic RAG patterns"]}]}',
            ]
        ),
        tool_registry=FakeToolRegistry(names=["web_search"]),
    )
    preview_context = UnifiedContext(
        session_id="session-resume",
        user_message="agentic RAG",
        active_capability="deep_research",
        enabled_tools=["web_search"],
        metadata={"turn_id": "turn-preview"},
        config_overrides={
            "mode": "report",
            "sources": ["web"],
            "depth": "manual",
            "manual_subtopics": 1,
        },
    )

    await preview_graph.run(preview_context, preview_bus)
    preview_result = [
        event for event in preview_bus._history if event.type == StreamEventType.RESULT
    ][0].metadata
    checkpoint_id = preview_result["checkpoint_id"]

    registry = FakeToolRegistry(names=["web_search"])
    resume_bus = StreamBus()
    resume_graph = DeepResearchGraph(
        model=FakeModel(["# Agentic RAG\n\nReport from resumed checkpoint."]),
        tool_registry=registry,
    )
    resume_context = UnifiedContext(
        session_id="session-resume",
        user_message="agentic RAG",
        active_capability="deep_research",
        enabled_tools=["web_search"],
        metadata={"turn_id": "turn-report"},
        config_overrides={
            "mode": "report",
            "sources": ["web"],
            "depth": "manual",
            "manual_subtopics": 1,
            "checkpoint_id": checkpoint_id,
            "confirmed_outline": [
                {
                    "title": "Agentic RAG patterns",
                    "overview": "Planner and tool-use loops.",
                    "queries": ["agentic RAG patterns"],
                }
            ],
        },
    )

    state = await resume_graph.run(resume_context, resume_bus)

    assert registry.calls == [("web_search", {"query": "agentic RAG patterns"})]
    assert state["final_answer"].startswith("# Agentic RAG")
    stages = [
        event.stage
        for event in resume_bus._history
        if event.type == StreamEventType.STAGE_START
    ]
    assert "researching" in stages
    assert "reporting" in stages
    assert "rephrasing" not in stages
    assert "decomposing" not in stages
    result_metadata = [
        event for event in resume_bus._history if event.type == StreamEventType.RESULT
    ][0].metadata
    assert result_metadata["metadata"]["checkpoint_id"] == checkpoint_id
    assert result_metadata["metadata"]["outline_preview"] is False
    assert Path(checkpoint_db).exists()



