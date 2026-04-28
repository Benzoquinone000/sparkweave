"""CLI smoke tests for the standalone ``sparkweave-cli`` package."""

from __future__ import annotations

import json
from typing import Any

from typer.testing import CliRunner

from sparkweave_cli.main import app
from sparkweave.app import TurnRequest

runner = CliRunner()


def _install_fake_runtime(monkeypatch, captured_requests: list[TurnRequest]) -> None:
    async def _start_turn(self, request):  # noqa: ANN001
        if isinstance(request, dict):
            request = TurnRequest(**request)
        captured_requests.append(request)
        return {"id": request.session_id or "session-1"}, {"id": "turn-1"}

    async def _stream_turn(self, turn_id: str, after_seq: int = 0):  # noqa: ANN001
        yield {"type": "session", "turn_id": turn_id, "seq": after_seq}
        yield {"type": "stage_start", "stage": "responding"}
        yield {"type": "content", "content": "response body"}
        yield {"type": "result", "metadata": {"response": "response body"}}
        yield {"type": "done"}

    monkeypatch.setattr("sparkweave.app.facade.SparkWeaveApp.start_turn", _start_turn)
    monkeypatch.setattr("sparkweave.app.facade.SparkWeaveApp.stream_turn", _stream_turn)


def test_run_command_json_mode(monkeypatch) -> None:
    captured_requests: list[TurnRequest] = []
    _install_fake_runtime(monkeypatch, captured_requests)

    capabilities = [
        "chat",
        "deep_solve",
        "deep_question",
        "deep_research",
        "visualize",
        "math_animator",
    ]

    for cap in capabilities:
        result = runner.invoke(
            app,
            [
                "run",
                cap,
                "hello world",
                "--format",
                "json",
                "--tool",
                "rag",
                "--kb",
                "demo-kb",
                "--history-ref",
                "session-old",
                "--notebook-ref",
                "nb1:rec1,rec2",
            ],
        )

        assert result.exit_code == 0, result.output
        lines = [json.loads(line) for line in result.output.splitlines() if line.strip()]
        assert any(line["type"] == "result" for line in lines)

    assert len(captured_requests) == 6
    assert captured_requests[0].capability == "chat"
    assert captured_requests[0].tools == ["rag"]
    assert captured_requests[0].knowledge_bases == ["demo-kb"]
    assert captured_requests[0].history_references == ["session-old"]
    assert captured_requests[0].notebook_references == [
        {"notebook_id": "nb1", "record_ids": ["rec1", "rec2"]}
    ]
    assert captured_requests[-1].capability == "math_animator"


def test_run_command_rich_mode(monkeypatch) -> None:
    captured_requests: list[TurnRequest] = []
    _install_fake_runtime(monkeypatch, captured_requests)

    result = runner.invoke(app, ["run", "chat", "hello rich"])

    assert result.exit_code == 0, result.output
    assert "response body" in result.output
    assert "> responding" in result.output
    assert captured_requests[0].capability == "chat"


def test_run_command_with_config(monkeypatch) -> None:
    captured_requests: list[TurnRequest] = []
    _install_fake_runtime(monkeypatch, captured_requests)

    result = runner.invoke(
        app,
        [
            "run",
            "deep_research",
            "compare retrieval stacks",
            "--config-json",
            '{"mode":"report","depth":"deep","sources":["web","papers"]}',
        ],
    )

    assert result.exit_code == 0, result.output
    request = captured_requests[0]
    assert request.capability == "deep_research"
    assert request.config == {
        "mode": "report",
        "depth": "deep",
        "sources": ["web", "papers"],
    }


def test_run_command_can_select_langgraph_runtime(monkeypatch) -> None:
    captured_requests: list[TurnRequest] = []
    _install_fake_runtime(monkeypatch, captured_requests)

    result = runner.invoke(
        app,
        ["run", "chat", "hello graph", "--runtime", "langgraph", "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    assert captured_requests[0].capability == "chat"
    assert captured_requests[0].config["_runtime"] == "langgraph"


def test_run_command_can_select_auto_runtime(monkeypatch) -> None:
    captured_requests: list[TurnRequest] = []
    _install_fake_runtime(monkeypatch, captured_requests)

    result = runner.invoke(
        app,
        ["run", "chat", "hello auto", "--runtime", "auto", "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    assert captured_requests[0].capability == "chat"
    assert captured_requests[0].config["_runtime"] == "auto"


def test_run_command_default_runtime_leaves_env_auto_available(monkeypatch) -> None:
    monkeypatch.setenv("SPARKWEAVE_RUNTIME", "auto")
    monkeypatch.setenv("SPARKWEAVE_NG_DEFAULT_CAPABILITIES", "chat")
    captured_requests: list[TurnRequest] = []
    _install_fake_runtime(monkeypatch, captured_requests)

    result = runner.invoke(app, ["run", "chat", "hello env auto", "--format", "json"])

    assert result.exit_code == 0, result.output
    assert captured_requests[0].capability == "chat"
    assert "_runtime" not in captured_requests[0].config


def test_serve_command_uses_ng_api_entrypoint(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_run(app_path: str, **kwargs: Any) -> None:
        calls.append((app_path, kwargs))

    monkeypatch.setattr("uvicorn.run", fake_run)

    result = runner.invoke(app, ["serve", "--host", "127.0.0.1", "--port", "8765"])

    assert result.exit_code == 0, result.output
    assert calls == [
        (
            "sparkweave.api.main:app",
            {
                "host": "127.0.0.1",
                "port": 8765,
                "reload": False,
                "reload_excludes": None,
            },
        )
    ]


def test_session_list_command_uses_shared_store(monkeypatch) -> None:
    async def _list_sessions(self, limit: int = 50, offset: int = 0):  # noqa: ANN001
        return [
            {
                "id": "session-1",
                "title": "Algebra",
                "capability": "chat",
                "status": "completed",
                "message_count": 4,
            }
        ]

    monkeypatch.setattr("sparkweave.app.facade.SparkWeaveApp.list_sessions", _list_sessions)

    result = runner.invoke(app, ["session", "list"])

    assert result.exit_code == 0, result.output
    assert "session-1" in result.output
    assert "Algebra" in result.output


def test_plugin_commands_use_ng_registries(monkeypatch) -> None:
    from sparkweave.plugins.loader import PluginManifest

    monkeypatch.setattr(
        "sparkweave.plugins.loader.discover_plugins",
        lambda: [
            PluginManifest(
                name="demo_plugin",
                type="playground",
                description="Demo plugin",
                stages=["plan", "answer"],
                version="1.0.0",
            )
        ],
    )

    list_result = runner.invoke(app, ["plugin", "list"])
    assert list_result.exit_code == 0, list_result.output
    assert "web_search" in list_result.output
    assert "deep_solve" in list_result.output
    assert "demo_plugin" in list_result.output

    info_result = runner.invoke(app, ["plugin", "info", "chat"])
    assert info_result.exit_code == 0, info_result.output
    assert '"name": "chat"' in info_result.output
    assert "request_schema" in info_result.output

    plugin_info_result = runner.invoke(app, ["plugin", "info", "demo_plugin"])
    assert plugin_info_result.exit_code == 0, plugin_info_result.output
    assert '"name": "demo_plugin"' in plugin_info_result.output
    assert '"stages": [' in plugin_info_result.output


def test_memory_show_uses_ng_memory_service(monkeypatch) -> None:
    class FakeMemoryService:
        def read_snapshot(self):
            return type(
                "Snapshot",
                (),
                {
                    "summary": "## Summary\n- Keep practicing.",
                    "profile": "## Profile\n- Likes concise answers.",
                },
            )()

    monkeypatch.setattr("sparkweave_cli.memory.get_memory_service", lambda: FakeMemoryService())

    result = runner.invoke(app, ["memory", "show", "all"])

    assert result.exit_code == 0, result.output
    assert "Keep practicing" in result.output
    assert "Likes concise answers" in result.output


