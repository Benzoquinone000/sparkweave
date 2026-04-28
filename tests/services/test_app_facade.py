"""Tests for the public SparkWeave application facade."""

from __future__ import annotations

from pathlib import Path

import pytest

from sparkweave.app import SparkWeaveApp, TurnRequest


class _FakeNotebookManager:
    def __init__(self) -> None:
        self.add_calls = []
        self.update_calls = []
        self.record = {
            "id": "rec-1",
            "type": "co_writer",
            "title": "Old",
            "output": "Old body",
            "metadata": {"source": "co_writer"},
        }

    def add_record(self, **kwargs):  # noqa: ANN003
        self.add_calls.append(kwargs)
        return {"record": {"id": "rec-new", **kwargs}, "added_to_notebooks": kwargs["notebook_ids"]}

    def get_record(self, notebook_id: str, record_id: str):  # noqa: ANN001
        if notebook_id == "nb1" and record_id == "rec-1":
            return dict(self.record)
        return None

    def update_record(self, notebook_id: str, record_id: str, **kwargs):  # noqa: ANN003
        self.update_calls.append((notebook_id, record_id, kwargs))
        return {"id": record_id, **kwargs}


class _FakeRuntimeRouter:
    def __init__(self) -> None:
        self.payload: dict | None = None

    async def start_turn(self, payload):  # noqa: ANN001
        self.payload = payload
        return {"id": "session-router"}, {"id": "turn-router"}


class _SelectableRuntime:
    def __init__(self, name: str) -> None:
        self.name = name
        self.payloads: list[dict] = []

    async def start_turn(self, payload):  # noqa: ANN001
        self.payloads.append(payload)
        return {"id": f"{self.name}-session"}, {"id": f"{self.name}-turn"}


class _FakeSessionStore:
    def __init__(self) -> None:
        self.preferences: list[tuple[str, dict]] = []

    async def update_session_preferences(self, session_id: str, preferences: dict) -> None:
        self.preferences.append((session_id, preferences))


@pytest.mark.asyncio
async def test_app_facade_uses_runtime_router(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_runtime = _FakeRuntimeRouter()
    fake_store = _FakeSessionStore()
    monkeypatch.setattr("sparkweave.app.facade.get_runtime_manager", lambda: fake_runtime)
    monkeypatch.setattr("sparkweave.app.facade.get_sqlite_session_store", lambda: fake_store)

    app = SparkWeaveApp()
    session, turn = await app.start_turn(
        TurnRequest(content="hello", capability="chat", runtime="langgraph")
    )

    assert session["id"] == "session-router"
    assert turn["id"] == "turn-router"
    assert fake_runtime.payload is not None
    assert fake_runtime.payload["config"]["_runtime"] == "langgraph"
    assert fake_store.preferences == [
        (
            "session-router",
            {
                "language": "en",
                "notebook_references": [],
                "history_references": [],
            },
        )
    ]


@pytest.mark.asyncio
async def test_app_facade_default_runtime_uses_env_auto_allowlist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from sparkweave.runtime.routing import RuntimeRoutingTurnManager
    from sparkweave.services.session import create_session_store

    monkeypatch.setenv("SPARKWEAVE_RUNTIME", "auto")
    monkeypatch.setenv("SPARKWEAVE_NG_DEFAULT_CAPABILITIES", "chat")
    compatibility = _SelectableRuntime("compatibility")
    langgraph = _SelectableRuntime("langgraph")
    router = RuntimeRoutingTurnManager(
        compatibility=compatibility,
        langgraph=langgraph,
        store=create_session_store(tmp_path / "chat_history.db"),
    )
    fake_store = _FakeSessionStore()
    monkeypatch.setattr("sparkweave.app.facade.get_runtime_manager", lambda: router)
    monkeypatch.setattr("sparkweave.app.facade.get_sqlite_session_store", lambda: fake_store)

    app = SparkWeaveApp()
    session, turn = await app.start_turn(TurnRequest(content="hello", capability="chat"))

    assert session["id"] == "langgraph-session"
    assert turn["id"] == "langgraph-turn"
    assert not compatibility.payloads
    assert len(langgraph.payloads) == 1
    assert "_runtime" not in langgraph.payloads[0]["config"]
    assert fake_store.preferences[0][0] == "langgraph-session"


def test_import_markdown_into_notebook_uses_co_writer_semantics(tmp_path: Path) -> None:
    markdown = tmp_path / "lesson.md"
    markdown.write_text("# Vectors\n\nSome content.", encoding="utf-8")

    app = SparkWeaveApp()
    fake_manager = _FakeNotebookManager()
    app.notebooks = fake_manager

    result = app.import_markdown_into_notebook("nb1", markdown)

    assert result["record"]["id"] == "rec-new"
    add_call = fake_manager.add_calls[0]
    assert add_call["record_type"] == "co_writer"
    assert add_call["title"] == "Vectors"
    assert add_call["user_query"] == "Vectors"
    assert add_call["output"] == "# Vectors\n\nSome content."
    assert add_call["metadata"]["saved_via"] == "cli"
    assert add_call["metadata"]["source_path"] == str(markdown.resolve())


def test_replace_markdown_record_updates_existing_co_writer_record(tmp_path: Path) -> None:
    markdown = tmp_path / "updated.md"
    markdown.write_text("# Matrices\n\nUpdated body.", encoding="utf-8")

    app = SparkWeaveApp()
    fake_manager = _FakeNotebookManager()
    app.notebooks = fake_manager

    result = app.replace_markdown_record("nb1", "rec-1", markdown)

    assert result["id"] == "rec-1"
    notebook_id, record_id, update_call = fake_manager.update_calls[0]
    assert notebook_id == "nb1"
    assert record_id == "rec-1"
    assert update_call["title"] == "Matrices"
    assert update_call["user_query"] == "Matrices"
    assert update_call["output"] == "# Matrices\n\nUpdated body."
    assert update_call["metadata"]["saved_via"] == "cli"


def test_turn_request_runtime_maps_to_config_override() -> None:
    request = TurnRequest(
        content="Explain Fourier transform",
        capability="chat",
        runtime="langgraph",
        config={"temperature": 0.2},
    )

    payload = request.to_payload()

    assert payload["config"] == {"temperature": 0.2, "_runtime": "langgraph"}


def test_turn_request_auto_runtime_maps_to_config_override() -> None:
    request = TurnRequest(
        content="Explain Fourier transform",
        capability="chat",
        runtime="auto",
    )

    payload = request.to_payload()

    assert payload["config"] == {"_runtime": "auto"}


def test_turn_request_legacy_runtime_preserves_config() -> None:
    request = TurnRequest(
        content="Explain Fourier transform",
        runtime="legacy",
        config={"_runtime": "ng"},
    )

    payload = request.to_payload()

    assert payload["config"] == {"_runtime": "legacy"}


def test_ng_app_exports_stable_facade_types() -> None:
    from sparkweave.app import SparkWeaveApp as ExportedSparkWeaveApp
    from sparkweave.app import TurnRequest as ExportedTurnRequest

    assert ExportedSparkWeaveApp is SparkWeaveApp
    assert ExportedTurnRequest is TurnRequest


