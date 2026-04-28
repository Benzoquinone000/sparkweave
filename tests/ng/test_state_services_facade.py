from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from sparkweave.services.memory import create_memory_service
from sparkweave.services.notebook import RecordType, create_notebook_manager
from sparkweave.services.paths import PathService
from sparkweave.services.prompting import load_prompt_hints
from sparkweave.services.session import (
    CompatibilityRuntimeUnavailable,
    LegacyRuntimeUnavailable,
    SQLiteSessionStore,
    create_session_store,
    create_turn_runtime_manager,
    get_compatibility_turn_runtime_manager,
    get_legacy_turn_runtime_manager,
)


class FakePathService:
    def __init__(self, memory_dir: Path) -> None:
        self._memory_dir = memory_dir

    def get_memory_dir(self) -> Path:
        return self._memory_dir


@pytest.mark.asyncio
async def test_session_facade_creates_isolated_store_and_runtime_manager(tmp_path):
    store = create_session_store(tmp_path / "chat_history.db")

    session = await store.create_session("NG session")
    await store.add_message(session["id"], "user", "hello", capability="chat")

    detail = await store.get_session_with_messages(session["id"])
    runtime = create_turn_runtime_manager(store)

    assert detail is not None
    assert detail["messages"][0]["content"] == "hello"
    assert runtime.store is store


def test_session_store_defaults_to_ng_path_service(tmp_path):
    PathService.reset_instance()
    try:
        service = PathService.get_instance()
        service._project_root = tmp_path
        service._user_data_dir = tmp_path / "data" / "user"

        store = SQLiteSessionStore()

        assert type(store).__module__ == "sparkweave.services.session_store"
        assert store.db_path == tmp_path / "data" / "user" / "chat_history.db"
        assert store.db_path.exists()
    finally:
        PathService.reset_instance()


def test_session_store_migrates_legacy_db_with_ng_path_service(tmp_path):
    PathService.reset_instance()
    try:
        service = PathService.get_instance()
        service._project_root = tmp_path
        service._user_data_dir = tmp_path / "data" / "user"
        legacy_db = tmp_path / "data" / "chat_history.db"
        legacy_db.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(legacy_db)
        try:
            conn.execute("CREATE TABLE legacy (id INTEGER PRIMARY KEY)")
            conn.commit()
        finally:
            conn.close()

        store = SQLiteSessionStore()

        assert store.db_path.exists()
        assert not legacy_db.exists()
    finally:
        PathService.reset_instance()


def test_memory_facade_creates_isolated_memory_service(tmp_path):
    service = create_memory_service(path_service=FakePathService(tmp_path / "memory"))

    snapshot = service.write_file("profile", "Likes algebra examples.")

    assert type(service).__module__ == "sparkweave.services.memory"
    assert snapshot.profile == "Likes algebra examples."
    assert "Likes algebra examples." in service.build_memory_context()


@pytest.mark.asyncio
async def test_memory_refresh_uses_ng_stream_facade(monkeypatch, tmp_path):
    calls: list[dict] = []

    async def fake_stream(**kwargs):
        calls.append(kwargs)
        yield "NO_CHANGE"

    monkeypatch.setattr("sparkweave.services.memory.llm_stream", fake_stream)
    service = create_memory_service(
        path_service=FakePathService(tmp_path / "memory"),
        store=create_session_store(tmp_path / "chat_history.db"),
    )

    result = await service.refresh_from_turn(
        user_message="Remember I like short answers.",
        assistant_message="Got it.",
    )

    assert result.changed is False
    assert len(calls) == 2
    assert calls[0]["max_tokens"] == 900


def test_notebook_facade_creates_isolated_notebook_manager(tmp_path):
    manager = create_notebook_manager(str(tmp_path / "notebooks"))

    notebook = manager.create_notebook("NG notebook")
    notebooks = manager.list_notebooks()

    assert type(manager).__module__ == "sparkweave.services.notebook"
    assert notebook["name"] == "NG notebook"
    assert notebooks[0]["id"] == notebook["id"]
    assert notebooks[0]["record_count"] == 0


def test_notebook_manager_add_record_accepts_enum(tmp_path):
    manager = create_notebook_manager(str(tmp_path / "notebooks"))
    notebook = manager.create_notebook("NG notebook")

    result = manager.add_record(
        notebook_ids=[notebook["id"]],
        record_type=RecordType.CO_WRITER,
        title="Sample",
        user_query="Sample",
        output="# Sample",
    )

    assert result["record"]["type"] == RecordType.CO_WRITER
    stored = manager.get_notebook(notebook["id"])
    assert stored is not None
    assert stored["records"][0]["type"] == "co_writer"


def test_prompt_hints_load_from_ng_assets():
    hints = load_prompt_hints("web_search", language="en")

    assert hints.short_description == "Search the web for current or external information with citations."
    assert hints.phase == "expansion"


def test_context_and_runtime_facades_are_importable():
    from sparkweave.core.contracts import StreamBus, StreamEvent, UnifiedContext
    from sparkweave.core.tool_protocol import ToolDefinition
    from sparkweave.services.context import ContextBuilder, NotebookAnalysisAgent
    from sparkweave.services.math_animator import (
        load_generated_code_model,
        load_rendering_components,
        load_visual_review_components,
    )
    from sparkweave.services.prompting import load_prompt_hints
    from sparkweave.services.question import QuestionParsingUnavailable
    from sparkweave.services.validation import validate_capability_config

    assert UnifiedContext.__name__ == "UnifiedContext"
    assert StreamBus.__name__ == "StreamBus"
    assert StreamEvent.__name__ == "StreamEvent"
    assert ToolDefinition.__name__ == "ToolDefinition"
    assert ContextBuilder.__name__ == "ContextBuilder"
    assert NotebookAnalysisAgent.__name__ == "NotebookAnalysisAgent"
    assert callable(load_generated_code_model)
    assert callable(load_prompt_hints)
    assert callable(load_rendering_components)
    assert callable(load_visual_review_components)
    assert QuestionParsingUnavailable.__name__ == "QuestionParsingUnavailable"
    assert validate_capability_config("chat", {}) == {}
    assert validate_capability_config("deep_solve", {}) == {"detailed_answer": True}
    assert validate_capability_config(
        "math_animator",
        {"output_mode": "video", "max_retries": 0, "enable_visual_review": True},
    ) == {
        "output_mode": "video",
        "quality": "medium",
        "style_hint": "",
        "max_retries": 0,
        "enable_visual_review": True,
    }
    compatibility_runtime = get_compatibility_turn_runtime_manager()
    legacy_alias_runtime = get_legacy_turn_runtime_manager()

    assert isinstance(compatibility_runtime, CompatibilityRuntimeUnavailable)
    assert isinstance(legacy_alias_runtime, CompatibilityRuntimeUnavailable)
    assert issubclass(LegacyRuntimeUnavailable, CompatibilityRuntimeUnavailable)
    assert compatibility_runtime.available is False


