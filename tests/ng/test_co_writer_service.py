from __future__ import annotations

import json

import pytest

import sparkweave.services.co_writer as co_writer


@pytest.mark.asyncio
async def test_edit_agent_process_and_history_use_ng_storage(monkeypatch, tmp_path):
    async def fake_complete(*_args, **_kwargs):
        raise RuntimeError("offline")

    monkeypatch.setattr(co_writer, "HISTORY_FILE", tmp_path / "history.json")
    monkeypatch.setattr(co_writer, "TOOL_CALLS_DIR", tmp_path / "tool_calls")
    monkeypatch.setattr(co_writer, "llm_complete", fake_complete)

    agent = co_writer.EditAgent(language="en")
    result = await agent.process(text="hello world", instruction="short", action="shorten")

    assert result["edited_text"] == "hello world"
    assert co_writer.load_history()[0]["action"] == "shorten"


@pytest.mark.asyncio
async def test_agentic_pipeline_returns_tool_traces(monkeypatch):
    class FakeRegistry:
        def names(self):
            return ["reason"]

        async def execute(self, name, **kwargs):  # noqa: ANN001
            assert name == "reason"
            assert kwargs["query"]
            return type(
                "Result",
                (),
                {
                    "content": "reasoned",
                    "success": True,
                    "sources": [],
                    "metadata": {"kind": "fake"},
                },
            )()

    pipeline = co_writer.AgenticChatPipeline()
    pipeline.tool_registry = FakeRegistry()
    from sparkweave.core.contracts import StreamBus, UnifiedContext

    stream = StreamBus()
    context = UnifiedContext(user_message="edit this", enabled_tools=["reason"])
    tools = pipeline._normalize_enabled_tools(context.enabled_tools)
    traces = await pipeline._stage_acting(
        context=context,
        enabled_tools=tools,
        thinking_text="think",
        stream=stream,
    )

    assert traces[0].tool_name == "reason"
    assert traces[0].result == "reasoned"
    assert "Tool: reason" in pipeline._format_tool_traces(traces)


def test_history_io_uses_single_append_entrypoint(monkeypatch, tmp_path):
    history_file = tmp_path / "history.json"
    monkeypatch.setattr(co_writer, "HISTORY_FILE", history_file)

    co_writer.save_history([{"id": "first"}, {"id": "second"}])
    co_writer.append_history({"id": "third"})

    assert co_writer.load_history() == [
        {"id": "first"},
        {"id": "second"},
        {"id": "third"},
    ]
    assert not history_file.with_name("history.json.tmp").exists()


def test_load_history_filters_invalid_payloads(monkeypatch, tmp_path):
    history_file = tmp_path / "history.json"
    monkeypatch.setattr(co_writer, "HISTORY_FILE", history_file)
    history_file.write_text(json.dumps([{"id": "ok"}, "bad", 3]), encoding="utf-8")

    assert co_writer.load_history() == [{"id": "ok"}]

    history_file.write_text("{bad json", encoding="utf-8")

    assert co_writer.load_history() == []

