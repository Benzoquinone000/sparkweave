"""CLI smoke tests for the standalone ``sparkweave-cli`` package."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from sparkweave_cli.main import app
from sparkweave.app import TurnRequest

runner = CliRunner()
ROOT = Path(__file__).resolve().parents[2]


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


def test_competition_check_command_runs_readiness_script(monkeypatch) -> None:
    calls: list[tuple[list[str], str]] = []

    def fake_run(cmd, cwd=None, check=False):  # noqa: ANN001
        calls.append((list(cmd), str(cwd)))
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr("sparkweave_cli.main.subprocess.run", fake_run)

    result = runner.invoke(app, ["competition-check"])

    assert result.exit_code == 0, result.output
    assert calls
    assert calls[0][0][1].endswith("scripts\\check_competition_readiness.py") or calls[0][0][1].endswith(
        "scripts/check_competition_readiness.py"
    )
    assert calls[0][0][-2:] == ["--format", "text"]


def test_competition_check_command_passes_report_options(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[list[str], str]] = []

    def fake_run(cmd, cwd=None, check=False):  # noqa: ANN001
        calls.append((list(cmd), str(cwd)))
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr("sparkweave_cli.main.subprocess.run", fake_run)

    output = tmp_path / "readiness.json"
    result = runner.invoke(app, ["competition-check", "--format", "json", "--output", str(output)])

    assert result.exit_code == 0, result.output
    assert calls
    assert calls[0][0][-4:] == ["--format", "json", "--output", str(output)]


def test_competition_check_command_can_render_summary(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[list[str], str]] = []

    def fake_run(cmd, cwd=None, check=False):  # noqa: ANN001
        calls.append((list(cmd), str(cwd)))
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr("sparkweave_cli.main.subprocess.run", fake_run)

    summary = tmp_path / "readiness.md"
    result = runner.invoke(app, ["competition-check", "--summary", str(summary)])

    assert result.exit_code == 0, result.output
    assert len(calls) == 2
    assert calls[0][0][1].endswith("scripts\\check_competition_readiness.py") or calls[0][0][1].endswith(
        "scripts/check_competition_readiness.py"
    )
    default_report = str(ROOT / "dist" / "competition-readiness.json")
    assert calls[0][0][-4:] == ["--format", "text", "--output", default_report]
    assert calls[1][0][1].endswith("scripts\\render_competition_summary.py") or calls[1][0][1].endswith(
        "scripts/render_competition_summary.py"
    )
    assert calls[1][0][-3:] == [
        default_report,
        "--output",
        str(summary),
    ]


def test_competition_templates_command_lists_course_templates() -> None:
    result = runner.invoke(app, ["competition-templates", "--format", "json"])

    assert result.exit_code == 0, result.output
    templates = json.loads(result.output)
    ids = {item["id"] for item in templates}
    assert "ai_learning_agents_systems" in ids
    assert "higher_math_limits_derivatives" in ids
    assert "robotics_ros_foundations" in ids


def test_competition_demo_command_runs_export_script(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[list[str], str]] = []

    def fake_run(cmd, cwd=None, check=False):  # noqa: ANN001
        calls.append((list(cmd), str(cwd)))
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr("sparkweave_cli.main.subprocess.run", fake_run)

    output = tmp_path / "demo"
    result = runner.invoke(
        app,
        ["competition-demo", "--template", "higher_math_limits_derivatives", "--output", str(output)],
    )

    assert result.exit_code == 0, result.output
    assert calls
    assert calls[0][0][1].endswith("scripts\\export_demo_materials.py") or calls[0][0][1].endswith(
        "scripts/export_demo_materials.py"
    )
    assert calls[0][0][-4:] == ["--template", "higher_math_limits_derivatives", "--output", str(output)]


def test_competition_package_command_runs_export_script(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[list[str], str]] = []

    def fake_run(cmd, cwd=None, check=False):  # noqa: ANN001
        calls.append((list(cmd), str(cwd)))
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr("sparkweave_cli.main.subprocess.run", fake_run)

    output = tmp_path / "package"
    archive = tmp_path / "package.zip"
    result = runner.invoke(
        app,
        [
            "competition-package",
            "--template",
            "robotics_ros_foundations",
            "--output",
            str(output),
            "--archive",
            str(archive),
            "--no-clean",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls
    assert calls[0][0][1].endswith("scripts\\export_competition_package.py") or calls[0][0][1].endswith(
        "scripts/export_competition_package.py"
    )
    assert calls[0][0][-7:] == [
        "--template",
        "robotics_ros_foundations",
        "--output",
        str(output),
        "--no-clean",
        "--archive",
        str(archive),
    ]


def test_competition_verify_command_runs_verify_script(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[list[str], str]] = []

    def fake_run(cmd, cwd=None, check=False):  # noqa: ANN001
        calls.append((list(cmd), str(cwd)))
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr("sparkweave_cli.main.subprocess.run", fake_run)

    package = tmp_path / "sparkweave_package.zip"
    result = runner.invoke(app, ["competition-verify", str(package)])

    assert result.exit_code == 0, result.output
    assert calls
    assert calls[0][0][1].endswith("scripts\\verify_competition_package.py") or calls[0][0][1].endswith(
        "scripts/verify_competition_package.py"
    )
    assert calls[0][0][-1] == str(package)


def test_competition_preflight_checks_then_exports_package(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[list[str], str]] = []

    def fake_run(cmd, cwd=None, check=False):  # noqa: ANN001
        calls.append((list(cmd), str(cwd)))
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr("sparkweave_cli.main.subprocess.run", fake_run)

    output = tmp_path / "package"
    report = tmp_path / "readiness.json"
    result = runner.invoke(
        app,
        [
            "competition-preflight",
            "--template",
            "higher_math_limits_derivatives",
            "--output",
            str(output),
            "--report",
            str(report),
        ],
    )

    assert result.exit_code == 0, result.output
    assert len(calls) == 3
    assert calls[0][0][1].endswith("scripts\\check_competition_readiness.py") or calls[0][0][1].endswith(
        "scripts/check_competition_readiness.py"
    )
    assert calls[0][0][-4:] == ["--format", "text", "--output", str(report)]
    assert calls[1][0][1].endswith("scripts\\export_competition_package.py") or calls[1][0][1].endswith(
        "scripts/export_competition_package.py"
    )
    assert calls[1][0][-4:] == ["--template", "higher_math_limits_derivatives", "--output", str(output)]
    assert calls[2][0][1].endswith("scripts\\verify_competition_package.py") or calls[2][0][1].endswith(
        "scripts/verify_competition_package.py"
    )
    assert calls[2][0][-1] == str(output)


def test_competition_preflight_can_build_web_before_export(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[list[str], str]] = []

    def fake_run(cmd, cwd=None, check=False):  # noqa: ANN001
        calls.append((list(cmd), str(cwd)))
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr("sparkweave_cli.main.subprocess.run", fake_run)
    monkeypatch.setattr("sparkweave_cli.main._npm_command", lambda: "npm")

    output = tmp_path / "package"
    result = runner.invoke(app, ["competition-preflight", "--with-build", "--output", str(output)])

    assert result.exit_code == 0, result.output
    assert len(calls) == 4
    assert calls[0][0][1].endswith("scripts\\check_competition_readiness.py") or calls[0][0][1].endswith(
        "scripts/check_competition_readiness.py"
    )
    assert calls[1][0] == ["npm", "run", "build"]
    assert calls[1][1].endswith("web")
    assert calls[2][0][1].endswith("scripts\\export_competition_package.py") or calls[2][0][1].endswith(
        "scripts/export_competition_package.py"
    )
    assert calls[2][0][-4:] == ["--template", "ai_learning_agents_systems", "--output", str(output)]
    assert calls[3][0][1].endswith("scripts\\verify_competition_package.py") or calls[3][0][1].endswith(
        "scripts/verify_competition_package.py"
    )
    assert calls[3][0][-1] == str(output)


def test_competition_preflight_can_render_summary(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[list[str], str]] = []

    def fake_run(cmd, cwd=None, check=False):  # noqa: ANN001
        calls.append((list(cmd), str(cwd)))
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr("sparkweave_cli.main.subprocess.run", fake_run)

    output = tmp_path / "package"
    report = tmp_path / "readiness.json"
    summary = tmp_path / "readiness.md"
    archive = tmp_path / "package.zip"
    result = runner.invoke(
        app,
        [
            "competition-preflight",
            "--output",
            str(output),
            "--report",
            str(report),
            "--summary",
            str(summary),
            "--archive",
            str(archive),
        ],
    )

    assert result.exit_code == 0, result.output
    assert len(calls) == 5
    assert calls[0][0][1].endswith("scripts\\check_competition_readiness.py") or calls[0][0][1].endswith(
        "scripts/check_competition_readiness.py"
    )
    assert calls[0][0][-4:] == ["--format", "text", "--output", str(report)]
    assert calls[1][0][1].endswith("scripts\\render_competition_summary.py") or calls[1][0][1].endswith(
        "scripts/render_competition_summary.py"
    )
    assert calls[1][0][-3:] == [str(report), "--output", str(summary)]
    assert calls[2][0][1].endswith("scripts\\export_competition_package.py") or calls[2][0][1].endswith(
        "scripts/export_competition_package.py"
    )
    assert calls[2][0][-6:] == [
        "--template",
        "ai_learning_agents_systems",
        "--output",
        str(output),
        "--archive",
        str(archive),
    ]
    assert calls[3][0][1].endswith("scripts\\verify_competition_package.py") or calls[3][0][1].endswith(
        "scripts/verify_competition_package.py"
    )
    assert calls[3][0][-1] == str(output)
    assert calls[4][0][1].endswith("scripts\\verify_competition_package.py") or calls[4][0][1].endswith(
        "scripts/verify_competition_package.py"
    )
    assert calls[4][0][-1] == str(archive)


def test_competition_preflight_stops_when_web_build_fails(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd, cwd=None, check=False):  # noqa: ANN001
        calls.append(list(cmd))
        return type("Result", (), {"returncode": 3 if len(calls) == 2 else 0})()

    monkeypatch.setattr("sparkweave_cli.main.subprocess.run", fake_run)
    monkeypatch.setattr("sparkweave_cli.main._npm_command", lambda: "npm")

    result = runner.invoke(app, ["competition-preflight", "--with-build"])

    assert result.exit_code == 3, result.output
    assert len(calls) == 2
    assert calls[1] == ["npm", "run", "build"]


def test_competition_preflight_stops_when_verification_fails(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd, cwd=None, check=False):  # noqa: ANN001
        calls.append(list(cmd))
        return type("Result", (), {"returncode": 7 if len(calls) == 3 else 0})()

    monkeypatch.setattr("sparkweave_cli.main.subprocess.run", fake_run)

    output = tmp_path / "package"
    result = runner.invoke(app, ["competition-preflight", "--output", str(output)])

    assert result.exit_code == 7, result.output
    assert len(calls) == 3
    assert calls[2][1].endswith("scripts\\verify_competition_package.py") or calls[2][1].endswith(
        "scripts/verify_competition_package.py"
    )
    assert calls[2][-1] == str(output)


def test_competition_preflight_stops_when_readiness_fails(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd, cwd=None, check=False):  # noqa: ANN001
        calls.append(list(cmd))
        return type("Result", (), {"returncode": 2 if len(calls) == 1 else 0})()

    monkeypatch.setattr("sparkweave_cli.main.subprocess.run", fake_run)

    result = runner.invoke(app, ["competition-preflight"])

    assert result.exit_code == 2, result.output
    assert len(calls) == 1


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


