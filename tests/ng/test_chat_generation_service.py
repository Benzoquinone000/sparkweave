from __future__ import annotations

from typing import Any

import pytest

import sparkweave.services.chat_generation as chat_generation


class _FakeChatGraph:
    async def run(self, context, stream):  # noqa: ANN001
        assert context.active_capability == "chat"
        assert context.enabled_tools == ["rag", "web_search"]
        assert context.knowledge_bases == ["demo"]
        await stream.progress(
            "Thinking",
            source="chat",
            stage="responding",
            metadata={"trace_kind": "call_status"},
        )
        await stream.sources(
            [
                {"type": "rag", "title": "KB"},
                {"type": "web", "title": "Web"},
            ],
            source="chat",
            stage="responding",
        )
        await stream.content("Hello", source="chat", stage="responding")
        await stream.result({"response": "Hello"}, source="chat")
        return {}


@pytest.mark.asyncio
async def test_chat_agent_streams_ng_chat_graph(monkeypatch):
    traces: list[dict[str, Any]] = []
    monkeypatch.setattr(chat_generation, "ChatGraph", _FakeChatGraph)

    agent = chat_generation.ChatAgent(language="zh")
    agent.set_trace_callback(lambda payload: traces.append(payload))
    stream = await agent.process(
        message="hi",
        history=[],
        kb_name="demo",
        enable_rag=True,
        enable_web_search=True,
    )
    events = [event async for event in stream]

    assert events == [
        {"type": "chunk", "content": "Hello"},
        {
            "type": "complete",
            "response": "Hello",
            "sources": {
                "rag": [{"type": "rag", "title": "KB"}],
                "web": [{"type": "web", "title": "Web"}],
            },
        },
    ]
    assert traces[0]["event"] == "llm_call"
    assert traces[0]["phase"] == "responding"
    assert traces[0]["trace_kind"] == "call_status"


def test_session_manager_keeps_legacy_shape():
    manager = chat_generation.SessionManager()
    session_id = manager.create_session("Demo")
    manager.add_message(session_id=session_id, role="user", content="hello")

    assert manager.get_session(session_id)["messages"][0]["content"] == "hello"
    assert manager.list_sessions()[0]["session_id"] == session_id
    assert "messages" not in manager.list_sessions()[0]
    assert manager.delete_session(session_id) is True
    assert manager.get_session(session_id) is None


@pytest.mark.asyncio
async def test_chat_agent_prefetches_rag_context_and_sources(monkeypatch):
    captured: dict[str, Any] = {}

    class _CaptureChatGraph:
        async def run(self, context, stream):  # noqa: ANN001
            captured["context"] = context
            await stream.content("Grounded answer", source="chat", stage="responding")
            await stream.result({"response": "Grounded answer"}, source="chat")
            return {}

    async def fake_rag_search(**kwargs):  # noqa: ANN001
        captured["rag_kwargs"] = kwargs
        return {
            "content": "RAG chunk about MP model.",
            "sources": [{"title": "Course PDF", "source": "/kb/course.pdf", "chunk_id": "c1"}],
            "success": True,
        }

    monkeypatch.setattr(chat_generation, "ChatGraph", _CaptureChatGraph)
    monkeypatch.setattr("sparkweave.services.rag.rag_search", fake_rag_search)

    agent = chat_generation.ChatAgent(language="zh")
    stream = await agent.process(
        message="MP模型是什么？",
        history=[],
        kb_name="demo",
        enable_rag=True,
        enable_web_search=False,
    )
    events = [event async for event in stream]

    complete = events[-1]
    assert captured["rag_kwargs"]["query"] == "MP模型是什么？"
    assert captured["rag_kwargs"]["kb_name"] == "demo"
    assert "RAG chunk about MP model." in captured["context"].memory_context
    assert complete["sources"]["rag"] == [
        {
            "type": "rag",
            "kb_name": "demo",
            "query": "MP模型是什么？",
            "title": "Course PDF",
            "source": "/kb/course.pdf",
            "chunk_id": "c1",
        }
    ]

