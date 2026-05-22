from __future__ import annotations

import importlib
import json

import pytest

pytest.importorskip("fastapi")
FastAPI = pytest.importorskip("fastapi").FastAPI
TestClient = pytest.importorskip("fastapi.testclient").TestClient


def test_co_writer_router_uses_ng_services():
    module = importlib.import_module("sparkweave.api.routers.co_writer")

    assert module.AgenticChatPipeline.__module__ == "sparkweave.services.co_writer"
    assert module.EditAgent.__module__ == "sparkweave.services.co_writer"
    assert module.UnifiedContext.__module__ == "sparkweave.core.contracts"
    assert module.StreamBus.__module__ == "sparkweave.core.contracts"


def test_co_writer_markdown_export_sanitizes_download_filename():
    module = importlib.import_module("sparkweave.api.routers.co_writer")
    app = FastAPI()
    app.include_router(module.router, prefix="/api/v1/co_writer")

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/co_writer/export/markdown",
            json={"content": "# Notes", "filename": 'report\r\nX-Bad: injected".html'},
        )

    assert response.status_code == 200
    assert response.text == "# Notes"
    content_disposition = response.headers["content-disposition"]
    assert "\r" not in content_disposition
    assert "\n" not in content_disposition
    assert "X-Bad:" not in content_disposition
    assert 'filename="reportX-Bad__injected_.html.md"' in content_disposition
    assert "filename*=UTF-8''reportX-Bad_%20injected_.html.md" in content_disposition


def test_co_writer_tool_call_rejects_glob_operation_id(monkeypatch: pytest.MonkeyPatch, tmp_path):
    module = importlib.import_module("sparkweave.api.routers.co_writer")
    monkeypatch.setattr(module, "TOOL_CALLS_DIR", tmp_path)
    (tmp_path / "20260101_120000_abcdef_react_tools.json").write_text(
        json.dumps({"secret": "tool-call"}),
        encoding="utf-8",
    )
    app = FastAPI()
    app.include_router(module.router, prefix="/api/v1/co_writer")

    with TestClient(app) as client:
        response = client.get("/api/v1/co_writer/tool_calls/*")

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid operation id"


def test_co_writer_tool_call_reads_matching_safe_operation_id(monkeypatch: pytest.MonkeyPatch, tmp_path):
    module = importlib.import_module("sparkweave.api.routers.co_writer")
    operation_id = "20260101_120000_abcdef"
    monkeypatch.setattr(module, "TOOL_CALLS_DIR", tmp_path)
    (tmp_path / f"{operation_id}_react_tools.json").write_text(
        json.dumps({"ok": True}),
        encoding="utf-8",
    )
    app = FastAPI()
    app.include_router(module.router, prefix="/api/v1/co_writer")

    with TestClient(app) as client:
        response = client.get(f"/api/v1/co_writer/tool_calls/{operation_id}")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_co_writer_edit_rejects_oversized_text_before_agent(monkeypatch: pytest.MonkeyPatch):
    module = importlib.import_module("sparkweave.api.routers.co_writer")

    def _fail_agent():
        raise AssertionError("agent should not be constructed for invalid payload")

    monkeypatch.setattr(module, "get_edit_agent", _fail_agent)
    app = FastAPI()
    app.include_router(module.router, prefix="/api/v1/co_writer")

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/co_writer/edit",
            json={
                "text": "x" * (module.MAX_CO_WRITER_TEXT_CHARS + 1),
                "instruction": "rewrite",
                "action": "rewrite",
            },
        )

    assert response.status_code == 422


def test_co_writer_edit_rejects_oversized_instruction_before_agent(monkeypatch: pytest.MonkeyPatch):
    module = importlib.import_module("sparkweave.api.routers.co_writer")

    def _fail_agent():
        raise AssertionError("agent should not be constructed for invalid payload")

    monkeypatch.setattr(module, "get_edit_agent", _fail_agent)
    app = FastAPI()
    app.include_router(module.router, prefix="/api/v1/co_writer")

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/co_writer/edit_react",
            json={
                "selected_text": "short text",
                "instruction": "x" * (module.MAX_CO_WRITER_INSTRUCTION_CHARS + 1),
                "mode": "rewrite",
            },
        )

    assert response.status_code == 422
